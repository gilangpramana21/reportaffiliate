"""
Multi-Brand Detection Service

This module provides functionality to detect and analyze brands from parsed Excel data.
It identifies unique brands, calculates statistics, and determines if multi-brand mode
should be activated based on the detected brand data.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import logging
import json
import os
import hashlib
from collections import Counter
from datetime import datetime, timedelta

from app.services.data_parser import ParseResult, CreatorRow

logger = logging.getLogger(__name__)


@dataclass
class BrandDetectionResult:
    """Result of brand detection analysis."""
    brands_detected: List[str]
    brand_counts: Dict[str, int]  # brand_name -> creator_count
    total_creators: int
    has_unassigned: bool
    detection_confidence: float
    is_multi_brand: bool  # True if ≥2 brands detected
    
    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BrandDetectionResult':
        """Create from dictionary for cache loading."""
        return cls(**data)


@dataclass
class BrandDetectionCacheEntry:
    """Cache entry for brand detection results."""
    result: BrandDetectionResult
    timestamp: datetime
    file_hash: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'result': self.result.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'file_hash': self.file_hash
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BrandDetectionCacheEntry':
        """Create from dictionary for cache loading."""
        return cls(
            result=BrandDetectionResult.from_dict(data['result']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            file_hash=data['file_hash']
        )


class MultiBrandDetector:
    """
    Detects and analyzes brands from parsed Excel data.
    
    This class identifies brands from the BRAND column in creator data,
    filters invalid values, calculates statistics, and determines if
    multi-brand mode should be activated.
    """
    
    def __init__(self, brand_normalizer=None):
        """
        Initialize MultiBrandDetector.
        
        Args:
            brand_normalizer: Optional BrandNormalizer instance for normalization
        """
        self.brand_normalizer = brand_normalizer
        self.min_brands_for_multi_mode = 2
        
        # Invalid brand values that should be filtered out
        self.invalid_brand_values = {
            '', None, 'TBD', 'N/A', '-', 'NULL', 'null', 'NONE', 'none',
            'UNKNOWN', 'unknown', '?', 'TBA', 'tbd', 'n/a', 'pending'
        }
        
        # Cache configuration
        self._cache_file = "uploads/.brand_detection_cache.json"
        self._cache_ttl_hours = 24  # Cache entries expire after 24 hours
        self._max_cache_entries = 100  # Maximum number of cache entries
        self._cache: Dict[str, BrandDetectionCacheEntry] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load brand detection cache from disk."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                # Convert dictionary entries back to cache objects
                for cache_key, entry_data in cache_data.items():
                    try:
                        entry = BrandDetectionCacheEntry.from_dict(entry_data)
                        # Only load entries that haven't expired
                        if self._is_cache_entry_valid(entry):
                            self._cache[cache_key] = entry
                    except Exception as e:
                        logger.warning(f"Failed to load cache entry {cache_key}: {e}")
                        
                logger.info(f"Loaded {len(self._cache)} brand detection cache entries")
        except Exception as e:
            logger.warning(f"Failed to load brand detection cache: {e}")
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Save brand detection cache to disk."""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            
            # Clean up expired entries before saving
            self._cleanup_expired_entries()
            
            # Limit cache size
            if len(self._cache) > self._max_cache_entries:
                # Remove oldest entries
                sorted_entries = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].timestamp
                )
                entries_to_keep = sorted_entries[-self._max_cache_entries:]
                self._cache = dict(entries_to_keep)
            
            # Convert cache to dictionary for JSON serialization
            cache_data = {
                cache_key: entry.to_dict()
                for cache_key, entry in self._cache.items()
            }
            
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Saved {len(self._cache)} brand detection cache entries")
        except Exception as e:
            logger.warning(f"Failed to save brand detection cache: {e}")
    
    def _is_cache_entry_valid(self, entry: BrandDetectionCacheEntry) -> bool:
        """Check if a cache entry is still valid (not expired)."""
        expiry_time = entry.timestamp + timedelta(hours=self._cache_ttl_hours)
        return datetime.now() < expiry_time
    
    def _cleanup_expired_entries(self) -> None:
        """Remove expired entries from cache."""
        expired_keys = [
            cache_key for cache_key, entry in self._cache.items()
            if not self._is_cache_entry_valid(entry)
        ]
        
        for key in expired_keys:
            del self._cache[key]
            
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _generate_cache_key(self, parse_result: ParseResult) -> str:
        """Generate a cache key based on the parse result data."""
        # Create a hash based on the creator data
        all_creators = parse_result.deal_rows + parse_result.non_deal_rows
        
        # Create a string representation of the brand data
        brand_data = []
        for creator in all_creators:
            brand_data.append(f"{creator.username}:{creator.brand}")
        
        # Sort to ensure consistent hashing regardless of order
        brand_data.sort()
        data_string = "|".join(brand_data)
        
        # Generate hash
        file_hash = hashlib.md5(data_string.encode('utf-8')).hexdigest()
        return file_hash
    
    def _get_cached_result(self, cache_key: str) -> Optional[BrandDetectionResult]:
        """Get cached brand detection result if available and valid."""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if self._is_cache_entry_valid(entry):
                logger.info(f"Using cached brand detection result for key: {cache_key[:8]}...")
                return entry.result
            else:
                # Remove expired entry
                del self._cache[cache_key]
                logger.debug(f"Removed expired cache entry: {cache_key[:8]}...")
        
        return None
    
    def _cache_result(self, cache_key: str, result: BrandDetectionResult) -> None:
        """Cache a brand detection result."""
        entry = BrandDetectionCacheEntry(
            result=result,
            timestamp=datetime.now(),
            file_hash=cache_key
        )
        
        self._cache[cache_key] = entry
        self._save_cache()
        logger.debug(f"Cached brand detection result for key: {cache_key[:8]}...")
    
    def detect_brands(self, parse_result: ParseResult) -> BrandDetectionResult:
        """
        Detect brands from ParseResult.
        
        Args:
            parse_result: ParseResult containing creator data
            
        Returns:
            BrandDetectionResult with detected brands and statistics
        """
        logger.info("Starting brand detection analysis")
        
        # Generate cache key for this parse result
        cache_key = self._generate_cache_key(parse_result)
        
        # Check if we have a cached result
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            logger.info("Returning cached brand detection result")
            return cached_result
        
        # Combine all creator rows for analysis
        all_creators = parse_result.deal_rows + parse_result.non_deal_rows
        total_creators = len(all_creators)
        
        if total_creators == 0:
            logger.warning("No creator data found for brand detection")
            result = BrandDetectionResult(
                brands_detected=[],
                brand_counts={},
                total_creators=0,
                has_unassigned=False,
                detection_confidence=0.0,
                is_multi_brand=False
            )
            # Cache the empty result
            self._cache_result(cache_key, result)
            return result
        
        # Extract brand values from creator rows
        brand_values = self._extract_brand_column(all_creators)
        
        # Filter out invalid brand values
        valid_brands = self._filter_valid_brands(brand_values)
        
        # Count brand frequencies
        brand_counter = Counter(valid_brands)
        brand_counts = dict(brand_counter)
        
        # Get unique brands sorted by frequency (descending)
        brands_detected = sorted(brand_counts.keys(), key=lambda x: brand_counts[x], reverse=True)
        
        # Check if there are unassigned creators (those with invalid/missing brand data)
        assigned_creators = len(valid_brands)
        has_unassigned = assigned_creators < total_creators
        
        # Calculate detection confidence
        detection_confidence = self._calculate_detection_confidence(valid_brands, total_creators)
        
        # Determine if multi-brand mode should be activated
        is_multi_brand = len(brands_detected) >= self.min_brands_for_multi_mode
        
        result = BrandDetectionResult(
            brands_detected=brands_detected,
            brand_counts=brand_counts,
            total_creators=total_creators,
            has_unassigned=has_unassigned,
            detection_confidence=detection_confidence,
            is_multi_brand=is_multi_brand
        )
        
        # Cache the result
        self._cache_result(cache_key, result)
        
        logger.info(f"Brand detection completed: {len(brands_detected)} brands detected, "
                   f"multi-brand mode: {is_multi_brand}, confidence: {detection_confidence:.2f}")
        
        return result
    
    def _extract_brand_column(self, creator_rows: List[CreatorRow]) -> List[str]:
        """
        Extract brand values from creator rows.
        
        Args:
            creator_rows: List of CreatorRow objects
            
        Returns:
            List of brand values (may contain invalid values)
        """
        brand_values = []
        
        for creator in creator_rows:
            # Get brand value from the creator row
            brand_value = creator.brand
            
            # Convert to string and strip whitespace if not None
            if brand_value is not None:
                brand_value = str(brand_value).strip()
            
            brand_values.append(brand_value)
        
        logger.debug(f"Extracted {len(brand_values)} brand values from creator rows")
        return brand_values
    
    def _filter_valid_brands(self, brand_values: List[str]) -> List[str]:
        """
        Filter out invalid brand values (empty, null, placeholders).
        
        Args:
            brand_values: List of raw brand values
            
        Returns:
            List of valid brand values
        """
        valid_brands = []
        
        for brand_value in brand_values:
            # Check if brand value is valid
            if self._is_valid_brand_value(brand_value):
                valid_brands.append(brand_value)
        
        logger.debug(f"Filtered to {len(valid_brands)} valid brands from {len(brand_values)} total values")
        return valid_brands
    
    def _is_valid_brand_value(self, brand_value: str) -> bool:
        """
        Check if a brand value is valid (not empty, null, or placeholder).
        
        Args:
            brand_value: Brand value to validate
            
        Returns:
            True if brand value is valid, False otherwise
        """
        if brand_value is None:
            return False
        
        # Convert to string and strip whitespace
        brand_str = str(brand_value).strip()
        
        # Check if empty after stripping
        if not brand_str:
            return False
        
        # Check against invalid values (case-insensitive)
        if brand_str.upper() in {v.upper() if v else v for v in self.invalid_brand_values}:
            return False
        
        # Check for common placeholder patterns
        if brand_str.startswith('TBD') or brand_str.startswith('TBA'):
            return False
        
        return True
    
    def _calculate_detection_confidence(self, valid_brands: List[str], total_creators: int) -> float:
        """
        Calculate confidence score for brand detection.
        
        The confidence score is based on:
        - Percentage of creators with valid brand data
        - Distribution of brands (more even distribution = higher confidence)
        - Minimum threshold for reliable detection
        
        Args:
            valid_brands: List of valid brand values
            total_creators: Total number of creators
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if total_creators == 0:
            return 0.0
        
        # Base confidence from data completeness
        data_completeness = len(valid_brands) / total_creators
        
        if data_completeness == 0:
            return 0.0
        
        # Adjust confidence based on brand distribution
        if len(valid_brands) > 0:
            brand_counter = Counter(valid_brands)
            unique_brands = len(brand_counter)
            
            if unique_brands == 1:
                # Single brand - high confidence if most creators have brand data
                confidence = data_completeness * 0.9
            else:
                # Multiple brands - calculate distribution evenness
                brand_counts = list(brand_counter.values())
                max_count = max(brand_counts)
                min_count = min(brand_counts)
                
                # More even distribution = higher confidence
                distribution_factor = min_count / max_count if max_count > 0 else 0
                confidence = data_completeness * (0.7 + 0.3 * distribution_factor)
        else:
            confidence = 0.0
        
        # Apply minimum threshold - need at least 50% data completeness for reasonable confidence
        if data_completeness < 0.5:
            confidence *= data_completeness * 2  # Scale down confidence for low completeness
        
        return min(confidence, 1.0)