"""
Brand Normalization Service

This module provides functionality to normalize brand names and manage aliases
for consistent brand grouping. It handles case-insensitive normalization,
whitespace trimming, similarity detection, and persistent alias management.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
import logging
import re
import json
import os
import hashlib
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from flask import current_app

from app.models.db import BrandAlias as BrandAliasModel, db

logger = logging.getLogger(__name__)


@dataclass
class BrandAlias:
    """Brand alias configuration."""
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    similarity_threshold: float = 0.8


@dataclass
class BrandNormalizationResult:
    """Result of brand normalization."""
    normalized_brands: Dict[str, str]  # original -> normalized
    suggested_aliases: List[Tuple[str, str, float]]  # (brand1, brand2, similarity)
    applied_aliases: Dict[str, str]  # alias -> canonical
    
    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BrandNormalizationResult':
        """Create from dictionary for cache loading."""
        return cls(**data)


@dataclass
class BrandNormalizationCacheEntry:
    """Cache entry for brand normalization results."""
    result: BrandNormalizationResult
    timestamp: datetime
    brands_hash: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'result': self.result.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'brands_hash': self.brands_hash
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BrandNormalizationCacheEntry':
        """Create from dictionary for cache loading."""
        return cls(
            result=BrandNormalizationResult.from_dict(data['result']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            brands_hash=data['brands_hash']
        )


class BrandNormalizer:
    """
    Normalizes brand names and manages aliases for consistent grouping.
    
    This class provides case-insensitive normalization, whitespace trimming,
    similarity-based alias suggestions, and persistent alias configuration
    storage and retrieval.
    """
    
    def __init__(self):
        """Initialize BrandNormalizer with default settings."""
        self.aliases: Dict[str, BrandAlias] = {}
        self.similarity_threshold = 0.8
        
        # Cache configuration
        self._cache_file = "uploads/.brand_normalization_cache.json"
        self._cache_ttl_hours = 12  # Cache entries expire after 12 hours
        self._max_cache_entries = 50  # Maximum number of cache entries
        self._cache: Dict[str, BrandNormalizationCacheEntry] = {}
        
        self._load_aliases_from_db()
        self._load_cache()
    
    def normalize_brands(self, brand_names: List[str]) -> BrandNormalizationResult:
        """
        Normalize brand names and apply aliases.
        
        Args:
            brand_names: List of raw brand names from data
            
        Returns:
            BrandNormalizationResult with normalization mappings
        """
        logger.info(f"Starting brand normalization for {len(brand_names)} brands")
        
        # Generate cache key for this brand list
        cache_key = self._generate_cache_key(brand_names)
        
        # Check if we have a cached result
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            logger.info("Returning cached brand normalization result")
            return cached_result
        
        # Apply basic normalization to all brand names
        normalized_brands = {}
        for brand_name in brand_names:
            normalized = self._apply_basic_normalization(brand_name)
            normalized_brands[brand_name] = normalized
        
        # Get unique normalized brands for alias processing
        unique_normalized = list(set(normalized_brands.values()))
        
        # Apply existing aliases
        applied_aliases = {}
        final_normalized = {}
        
        for original, normalized in normalized_brands.items():
            # Check if this normalized brand has an alias
            canonical = self._resolve_alias(normalized)
            final_normalized[original] = canonical
            
            if canonical != normalized:
                applied_aliases[normalized] = canonical
        
        # Suggest similar brands that might be aliases
        suggested_aliases = self.suggest_similar_brands(unique_normalized)
        
        result = BrandNormalizationResult(
            normalized_brands=final_normalized,
            suggested_aliases=suggested_aliases,
            applied_aliases=applied_aliases
        )
        
        # Cache the result
        self._cache_result(cache_key, result)
        
        logger.info(f"Brand normalization completed: {len(applied_aliases)} aliases applied, "
                   f"{len(suggested_aliases)} suggestions generated")
        
        return result
    
    def _load_cache(self) -> None:
        """Load brand normalization cache from disk."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                # Convert dictionary entries back to cache objects
                for cache_key, entry_data in cache_data.items():
                    try:
                        entry = BrandNormalizationCacheEntry.from_dict(entry_data)
                        # Only load entries that haven't expired
                        if self._is_cache_entry_valid(entry):
                            self._cache[cache_key] = entry
                    except Exception as e:
                        logger.warning(f"Failed to load normalization cache entry {cache_key}: {e}")
                        
                logger.info(f"Loaded {len(self._cache)} brand normalization cache entries")
        except Exception as e:
            logger.warning(f"Failed to load brand normalization cache: {e}")
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Save brand normalization cache to disk."""
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
                
            logger.debug(f"Saved {len(self._cache)} brand normalization cache entries")
        except Exception as e:
            logger.warning(f"Failed to save brand normalization cache: {e}")
    
    def _is_cache_entry_valid(self, entry: BrandNormalizationCacheEntry) -> bool:
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
            logger.debug(f"Cleaned up {len(expired_keys)} expired normalization cache entries")
    
    def _generate_cache_key(self, brand_names: List[str]) -> str:
        """Generate a cache key based on the brand names and current aliases."""
        # Sort brand names for consistent hashing
        sorted_brands = sorted(brand_names)
        
        # Include current aliases in the hash to invalidate cache when aliases change
        alias_data = []
        for canonical, alias_obj in self.aliases.items():
            alias_data.append(f"{canonical}:{','.join(sorted(alias_obj.aliases))}")
        alias_data.sort()
        
        # Combine brand names and alias data
        data_string = "|".join(sorted_brands) + "||" + "|".join(alias_data)
        
        # Generate hash
        brands_hash = hashlib.md5(data_string.encode('utf-8')).hexdigest()
        return brands_hash
    
    def _get_cached_result(self, cache_key: str) -> Optional[BrandNormalizationResult]:
        """Get cached brand normalization result if available and valid."""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if self._is_cache_entry_valid(entry):
                logger.info(f"Using cached brand normalization result for key: {cache_key[:8]}...")
                return entry.result
            else:
                # Remove expired entry
                del self._cache[cache_key]
                logger.debug(f"Removed expired normalization cache entry: {cache_key[:8]}...")
        
        return None
    
    def _cache_result(self, cache_key: str, result: BrandNormalizationResult) -> None:
        """Cache a brand normalization result."""
        entry = BrandNormalizationCacheEntry(
            result=result,
            timestamp=datetime.now(),
            brands_hash=cache_key
        )
        
        self._cache[cache_key] = entry
        self._save_cache()
        logger.debug(f"Cached brand normalization result for key: {cache_key[:8]}...")
    
    def add_alias(self, canonical_name: str, alias: str) -> None:
        """
        Add a brand alias mapping.
        
        Args:
            canonical_name: The canonical (main) brand name
            alias: The alias that should map to the canonical name
        """
        # Normalize both names
        canonical_normalized = self._apply_basic_normalization(canonical_name)
        alias_normalized = self._apply_basic_normalization(alias)
        
        logger.info(f"Adding alias mapping: '{alias_normalized}' -> '{canonical_normalized}'")
        
        # Add to in-memory cache
        if canonical_normalized not in self.aliases:
            self.aliases[canonical_normalized] = BrandAlias(
                canonical_name=canonical_normalized,
                aliases=[]
            )
        
        if alias_normalized not in self.aliases[canonical_normalized].aliases:
            self.aliases[canonical_normalized].aliases.append(alias_normalized)
        
        # Persist to database
        self._save_alias_to_db(canonical_normalized, alias_normalized)
    
    def suggest_similar_brands(self, brands: List[str]) -> List[Tuple[str, str, float]]:
        """
        Suggest brands that might be aliases based on similarity.
        
        Args:
            brands: List of normalized brand names
            
        Returns:
            List of tuples (brand1, brand2, similarity_score) for similar brands
        """
        suggestions = []
        
        # Compare each brand with every other brand
        for i, brand1 in enumerate(brands):
            for j, brand2 in enumerate(brands[i+1:], i+1):
                similarity = self._calculate_similarity(brand1, brand2)
                
                if similarity >= self.similarity_threshold:
                    suggestions.append((brand1, brand2, similarity))
        
        # Sort by similarity score (descending)
        suggestions.sort(key=lambda x: x[2], reverse=True)
        
        logger.debug(f"Generated {len(suggestions)} similarity suggestions")
        return suggestions
    
    def _apply_basic_normalization(self, brand_name: str) -> str:
        """
        Apply basic normalization (case, whitespace).
        
        Args:
            brand_name: Raw brand name
            
        Returns:
            Normalized brand name
        """
        if not brand_name:
            return ""
        
        # Convert to string and strip whitespace
        normalized = str(brand_name).strip()
        
        # Convert to uppercase for consistency
        normalized = normalized.upper()
        
        # Remove common punctuation that might cause inconsistencies, but preserve spaces
        normalized = re.sub(r'[.,;:!?]', ' ', normalized)
        
        # Remove extra whitespace (multiple spaces become single space)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Final trim
        normalized = normalized.strip()
        
        return normalized
    
    def _resolve_alias(self, brand_name: str) -> str:
        """
        Resolve a brand name to its canonical form using aliases.
        
        Args:
            brand_name: Normalized brand name to resolve
            
        Returns:
            Canonical brand name if alias exists, otherwise original name
        """
        # Check if this brand is an alias for any canonical brand
        for canonical, alias_config in self.aliases.items():
            if brand_name in alias_config.aliases:
                return canonical
        
        # If no alias found, return the original name
        return brand_name
    
    def _calculate_similarity(self, brand1: str, brand2: str) -> float:
        """
        Calculate similarity score between two brand names.
        
        Uses a combination of sequence matching and token-based comparison
        to handle various types of brand name variations.
        
        Args:
            brand1: First brand name
            brand2: Second brand name
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not brand1 or not brand2:
            return 0.0
        
        if brand1 == brand2:
            return 1.0
        
        # Basic sequence similarity
        sequence_similarity = SequenceMatcher(None, brand1, brand2).ratio()
        
        # Token-based similarity (for brands with different word orders)
        tokens1 = set(brand1.split())
        tokens2 = set(brand2.split())
        
        if tokens1 and tokens2:
            common_tokens = tokens1.intersection(tokens2)
            all_tokens = tokens1.union(tokens2)
            token_similarity = len(common_tokens) / len(all_tokens)
        else:
            token_similarity = 0.0
        
        # Weighted combination (sequence similarity is more important)
        final_similarity = 0.7 * sequence_similarity + 0.3 * token_similarity
        
        return final_similarity
    
    def _load_aliases_from_db(self) -> None:
        """Load existing aliases from database into memory cache."""
        try:
            # Only load if we're in an application context
            if current_app:
                aliases = db.session.query(BrandAliasModel).all()
                
                for alias_record in aliases:
                    canonical = alias_record.canonical_name
                    alias_name = alias_record.alias_name
                    
                    if canonical not in self.aliases:
                        self.aliases[canonical] = BrandAlias(
                            canonical_name=canonical,
                            aliases=[]
                        )
                    
                    if alias_name not in self.aliases[canonical].aliases:
                        self.aliases[canonical].aliases.append(alias_name)
                
                logger.info(f"Loaded {len(aliases)} brand aliases from database")
        
        except Exception as e:
            logger.warning(f"Could not load aliases from database: {e}")
            # Continue without database aliases - they can be added later
    
    def _save_alias_to_db(self, canonical_name: str, alias_name: str) -> None:
        """
        Save alias mapping to database.
        
        Args:
            canonical_name: Canonical brand name
            alias_name: Alias brand name
        """
        try:
            # Check if alias already exists
            existing = db.session.query(BrandAliasModel).filter_by(
                canonical_name=canonical_name,
                alias_name=alias_name
            ).first()
            
            if not existing:
                # Calculate similarity score for storage
                similarity_score = self._calculate_similarity(canonical_name, alias_name)
                
                alias_record = BrandAliasModel(
                    canonical_name=canonical_name,
                    alias_name=alias_name,
                    similarity_score=similarity_score
                )
                
                db.session.add(alias_record)
                db.session.commit()
                
                logger.info(f"Saved alias to database: '{alias_name}' -> '{canonical_name}'")
        
        except Exception as e:
            logger.error(f"Failed to save alias to database: {e}")
            db.session.rollback()
    
    def get_all_aliases(self) -> Dict[str, List[str]]:
        """
        Get all configured aliases.
        
        Returns:
            Dictionary mapping canonical names to their aliases
        """
        return {canonical: alias_config.aliases 
                for canonical, alias_config in self.aliases.items()}
    
    def remove_alias(self, canonical_name: str, alias_name: str) -> bool:
        """
        Remove an alias mapping.
        
        Args:
            canonical_name: Canonical brand name
            alias_name: Alias to remove
            
        Returns:
            True if alias was removed, False if not found
        """
        canonical_normalized = self._apply_basic_normalization(canonical_name)
        alias_normalized = self._apply_basic_normalization(alias_name)
        
        # Remove from memory cache
        if canonical_normalized in self.aliases:
            if alias_normalized in self.aliases[canonical_normalized].aliases:
                self.aliases[canonical_normalized].aliases.remove(alias_normalized)
                
                # Remove from database
                try:
                    alias_record = db.session.query(BrandAliasModel).filter_by(
                        canonical_name=canonical_normalized,
                        alias_name=alias_normalized
                    ).first()
                    
                    if alias_record:
                        db.session.delete(alias_record)
                        db.session.commit()
                        logger.info(f"Removed alias: '{alias_normalized}' -> '{canonical_normalized}'")
                
                except Exception as e:
                    logger.error(f"Failed to remove alias from database: {e}")
                    db.session.rollback()
                
                return True
        
        return False