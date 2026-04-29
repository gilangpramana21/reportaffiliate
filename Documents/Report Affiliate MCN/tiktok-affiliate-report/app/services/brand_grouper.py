"""
Brand Grouping Service

This module provides functionality to group creators by normalized brand names
and calculate comprehensive statistics for each brand group. It handles creator
grouping, statistics calculation, top performer identification, and unassigned
creator management.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Iterator, Tuple
import logging
import time
from collections import defaultdict

from app.services.data_parser import CreatorRow
from app.services.brand_normalizer import BrandNormalizationResult

logger = logging.getLogger(__name__)


@dataclass
class BrandStatistics:
    """Statistics for a single brand."""
    brand_name: str
    creator_count: int
    total_gmv: float
    avg_gmv: float
    top_performers: List[CreatorRow]  # Top 3 by GMV
    video_count: int
    deal_ratio: float  # deal_count / total_approached if available


@dataclass
class BrandGroupResult:
    """Result of brand grouping operation."""
    brand_groups: Dict[str, List[CreatorRow]]  # brand_name -> creators
    brand_statistics: Dict[str, BrandStatistics]
    unassigned_creators: List[CreatorRow]
    total_creators_processed: int


class BrandGrouper:
    """
    Groups creators by normalized brand names and calculates statistics.
    
    This class takes creator data and brand normalization results to create
    brand-based groups, calculate comprehensive statistics for each brand,
    and handle creators with missing or invalid brand data.
    """
    
    def __init__(self):
        """Initialize BrandGrouper."""
        self.unassigned_brand_name = "UNASSIGNED"
        self.batch_size = 1000  # Process creators in batches for memory efficiency
        self.progress_interval = 5000  # Log progress every N creators
    
    def group_by_brand(
        self, 
        creator_rows: List[CreatorRow], 
        normalization_result: BrandNormalizationResult
    ) -> BrandGroupResult:
        """
        Group creators by normalized brand names with memory-efficient processing.
        
        Args:
            creator_rows: List of all creator rows
            normalization_result: Brand normalization mappings
            
        Returns:
            BrandGroupResult with grouped creators and statistics
        """
        start_time = time.time()
        total_creators = len(creator_rows)
        logger.info(f"Starting optimized brand grouping for {total_creators} creators")
        
        # Use memory-efficient grouping for large datasets
        if total_creators > 10000:
            return self._group_by_brand_streaming(creator_rows, normalization_result)
        else:
            return self._group_by_brand_standard(creator_rows, normalization_result)
    
    def _group_by_brand_standard(
        self, 
        creator_rows: List[CreatorRow], 
        normalization_result: BrandNormalizationResult
    ) -> BrandGroupResult:
        """Standard grouping for smaller datasets."""
        logger.info(f"Using standard grouping for {len(creator_rows)} creators")
        
        # Initialize brand groups
        brand_groups = defaultdict(list)
        unassigned_creators = []
        
        # Group creators by their normalized brand
        for i, creator in enumerate(creator_rows):
            # Log progress for large datasets
            if i > 0 and i % self.progress_interval == 0:
                logger.info(f"Processed {i}/{len(creator_rows)} creators ({i/len(creator_rows)*100:.1f}%)")
            
            # Get the original brand value
            original_brand = creator.brand
            
            if original_brand is None or str(original_brand).strip() == "":
                # Creator has no brand data
                unassigned_creators.append(creator)
                continue
            
            # Look up the normalized brand name
            normalized_brand = normalization_result.normalized_brands.get(original_brand)
            
            if normalized_brand:
                # Add to the appropriate brand group
                brand_groups[normalized_brand].append(creator)
            else:
                # Brand not found in normalization result (shouldn't happen normally)
                logger.warning(f"Creator {creator.username} has brand '{original_brand}' not found in normalization result")
                unassigned_creators.append(creator)
        
        return self._finalize_grouping_result(brand_groups, unassigned_creators, len(creator_rows))
    
    def _group_by_brand_streaming(
        self, 
        creator_rows: List[CreatorRow], 
        normalization_result: BrandNormalizationResult
    ) -> BrandGroupResult:
        """Memory-efficient streaming grouping for large datasets."""
        logger.info(f"Using streaming grouping for {len(creator_rows)} creators")
        
        # Use generators and batch processing for memory efficiency
        brand_groups = defaultdict(list)
        unassigned_creators = []
        
        # Process creators in batches to manage memory
        for batch_start in range(0, len(creator_rows), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(creator_rows))
            batch = creator_rows[batch_start:batch_end]
            
            logger.info(f"Processing batch {batch_start//self.batch_size + 1}: "
                       f"creators {batch_start}-{batch_end} ({batch_end/len(creator_rows)*100:.1f}%)")
            
            # Process batch
            for creator in batch:
                original_brand = creator.brand
                
                if original_brand is None or str(original_brand).strip() == "":
                    unassigned_creators.append(creator)
                    continue
                
                normalized_brand = normalization_result.normalized_brands.get(original_brand)
                
                if normalized_brand:
                    brand_groups[normalized_brand].append(creator)
                else:
                    logger.warning(f"Creator {creator.username} has brand '{original_brand}' not found in normalization result")
                    unassigned_creators.append(creator)
        
        return self._finalize_grouping_result(brand_groups, unassigned_creators, len(creator_rows))
    
    def _finalize_grouping_result(
        self,
        brand_groups: defaultdict,
        unassigned_creators: List[CreatorRow],
        total_creators: int
    ) -> BrandGroupResult:
        """Finalize the grouping result with statistics calculation."""
        start_time = time.time()
        
        # Convert defaultdict to regular dict
        brand_groups = dict(brand_groups)
        
        # Calculate statistics for each brand using optimized method
        brand_statistics = {}
        for brand_name, creators in brand_groups.items():
            brand_statistics[brand_name] = self._calculate_brand_statistics_optimized(brand_name, creators)
        
        # Add unassigned group if there are unassigned creators
        if unassigned_creators:
            brand_groups[self.unassigned_brand_name] = unassigned_creators
            brand_statistics[self.unassigned_brand_name] = self._calculate_brand_statistics_optimized(
                self.unassigned_brand_name, unassigned_creators
            )
        
        result = BrandGroupResult(
            brand_groups=brand_groups,
            brand_statistics=brand_statistics,
            unassigned_creators=unassigned_creators,
            total_creators_processed=total_creators
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Brand grouping completed in {elapsed_time:.2f}s: {len(brand_groups)} groups created, "
                   f"{len(unassigned_creators)} unassigned creators")
        
        return result
    
    def _calculate_brand_statistics_optimized(
        self, 
        brand_name: str, 
        creators: List[CreatorRow]
    ) -> BrandStatistics:
        """
        Calculate comprehensive statistics for a brand group with optimizations.
        
        This method uses optimized algorithms for large datasets:
        - Single-pass statistics calculation
        - Efficient sorting for top performers
        - Memory-efficient data structures
        
        Args:
            brand_name: Name of the brand
            creators: List of creators in this brand group
            
        Returns:
            BrandStatistics with calculated metrics
        """
        if not creators:
            return BrandStatistics(
                brand_name=brand_name,
                creator_count=0,
                total_gmv=0.0,
                avg_gmv=0.0,
                top_performers=[],
                video_count=0,
                deal_ratio=0.0
            )
        
        # Single-pass calculation for efficiency
        total_gmv = 0.0
        video_count = 0
        deal_count = 0
        gmv_values = []  # For top performers calculation
        
        # Process creators in a single pass
        for creator in creators:
            # Calculate GMV
            gmv = self._get_creator_gmv(creator)
            if gmv is not None and gmv > 0:
                total_gmv += gmv
                gmv_values.append((gmv, creator))
            
            # Count videos
            if hasattr(creator, 'video_links') and creator.video_links:
                if isinstance(creator.video_links, list):
                    video_count += len(creator.video_links)
                else:
                    video_count += 1
            
            # Count deals (creators with status indicating they made a deal)
            if hasattr(creator, 'status') and creator.status:
                status_lower = str(creator.status).lower()
                if 'deal' in status_lower and 'belum' not in status_lower:
                    deal_count += 1
        
        # Calculate averages
        creator_count = len(creators)
        avg_gmv = total_gmv / creator_count if creator_count > 0 else 0.0
        
        # Calculate deal ratio
        deal_ratio = deal_count / creator_count if creator_count > 0 else 0.0
        
        # Get top performers efficiently using partial sort
        top_performers = self._get_top_performers_optimized(gmv_values, limit=3)
        
        return BrandStatistics(
            brand_name=brand_name,
            creator_count=creator_count,
            total_gmv=total_gmv,
            avg_gmv=avg_gmv,
            top_performers=top_performers,
            video_count=video_count,
            deal_ratio=deal_ratio
        )
    
    def _get_top_performers_optimized(
        self, 
        gmv_values: List[Tuple[float, CreatorRow]], 
        limit: int = 3
    ) -> List[CreatorRow]:
        """
        Get top performing creators efficiently using partial sort.
        
        For large datasets, this is more efficient than sorting the entire list.
        
        Args:
            gmv_values: List of (gmv, creator) tuples
            limit: Number of top performers to return
            
        Returns:
            List of top performing CreatorRow objects
        """
        if not gmv_values:
            return []
        
        # For small lists, just sort normally
        if len(gmv_values) <= limit * 2:
            sorted_creators = sorted(gmv_values, key=lambda x: x[0], reverse=True)
            return [creator for _, creator in sorted_creators[:limit]]
        
        # For larger lists, use partial sort (heapq.nlargest equivalent)
        import heapq
        top_gmv_creators = heapq.nlargest(limit, gmv_values, key=lambda x: x[0])
        return [creator for _, creator in top_gmv_creators]
    
    def _calculate_brand_statistics(
        self, 
        brand_name: str, 
        creators: List[CreatorRow]
    ) -> BrandStatistics:
        """
        Calculate comprehensive statistics for a brand group.
        
        Args:
            brand_name: Name of the brand
            creators: List of creators in this brand group
            
        Returns:
            BrandStatistics with calculated metrics
        """
        if not creators:
            return BrandStatistics(
                brand_name=brand_name,
                creator_count=0,
                total_gmv=0.0,
                avg_gmv=0.0,
                top_performers=[],
                video_count=0,
                deal_ratio=0.0
            )
        
        creator_count = len(creators)
        
        # Calculate GMV statistics
        gmv_values = []
        for creator in creators:
            gmv = self._get_creator_gmv(creator)
            if gmv is not None and gmv > 0:
                gmv_values.append(gmv)
        
        total_gmv = sum(gmv_values)
        avg_gmv = total_gmv / len(gmv_values) if gmv_values else 0.0
        
        # Calculate video count
        video_count = 0
        for creator in creators:
            # Count from total_vt field if available
            if creator.total_vt is not None and creator.total_vt > 0:
                video_count += creator.total_vt
            # Also count from video_links if available
            elif hasattr(creator, 'video_links') and creator.video_links:
                video_count += len(creator.video_links)
        
        # Calculate deal ratio if possible
        deal_ratio = self._calculate_deal_ratio(creators)
        
        # Get top performers
        top_performers = self._get_top_performers(creators, limit=3)
        
        return BrandStatistics(
            brand_name=brand_name,
            creator_count=creator_count,
            total_gmv=total_gmv,
            avg_gmv=avg_gmv,
            top_performers=top_performers,
            video_count=video_count,
            deal_ratio=deal_ratio
        )
    
    def _get_creator_gmv(self, creator: CreatorRow) -> Optional[float]:
        """
        Extract GMV value from creator row.
        
        Tries multiple fields that might contain GMV data.
        
        Args:
            creator: CreatorRow to extract GMV from
            
        Returns:
            GMV value or None if not available
        """
        # Try gmv_perbulan first (most common)
        if creator.gmv_perbulan is not None and creator.gmv_perbulan > 0:
            return float(creator.gmv_perbulan)
        
        # Try avg_gmv_month as fallback
        if creator.avg_gmv_month is not None and creator.avg_gmv_month > 0:
            return float(creator.avg_gmv_month)
        
        # Try gmv_per_pembeli as another fallback
        if creator.gmv_per_pembeli is not None and creator.gmv_per_pembeli > 0:
            return float(creator.gmv_per_pembeli)
        
        return None
    
    def _calculate_deal_ratio(self, creators: List[CreatorRow]) -> float:
        """
        Calculate deal ratio (successful deals / total approached).
        
        This is based on the 'result' field if available.
        
        Args:
            creators: List of creators to analyze
            
        Returns:
            Deal ratio between 0.0 and 1.0
        """
        total_approached = 0
        successful_deals = 0
        
        for creator in creators:
            if creator.result is not None:
                total_approached += 1
                
                # Check if result indicates a successful deal
                result_str = str(creator.result).lower().strip()
                if result_str in ['deal', 'success', 'yes', 'approved', 'accepted', 'done']:
                    successful_deals += 1
        
        if total_approached == 0:
            return 0.0
        
        return successful_deals / total_approached
    
    def _get_top_performers(self, creators: List[CreatorRow], limit: int = 3) -> List[CreatorRow]:
        """
        Get top performing creators by GMV.
        
        Args:
            creators: List of creators to analyze
            limit: Maximum number of top performers to return
            
        Returns:
            List of top performing creators sorted by GMV (descending)
        """
        # Filter creators with valid GMV data
        creators_with_gmv = []
        for creator in creators:
            gmv = self._get_creator_gmv(creator)
            if gmv is not None and gmv > 0:
                creators_with_gmv.append((creator, gmv))
        
        # Sort by GMV (descending)
        creators_with_gmv.sort(key=lambda x: x[1], reverse=True)
        
        # Return top performers (without GMV values)
        return [creator for creator, gmv in creators_with_gmv[:limit]]
    
    def get_brand_preview_data(
        self, 
        brand_name: str, 
        creators: List[CreatorRow], 
        limit: int = 5
    ) -> List[Dict[str, any]]:
        """
        Get preview data for a brand (top creators for UI display).
        
        Args:
            brand_name: Name of the brand
            creators: List of creators in the brand
            limit: Maximum number of creators to include in preview
            
        Returns:
            List of creator preview data dictionaries
        """
        top_creators = self._get_top_performers(creators, limit=limit)
        
        preview_data = []
        for creator in top_creators:
            gmv = self._get_creator_gmv(creator)
            
            preview_data.append({
                'username': creator.username or 'Unknown',
                'gmv': gmv or 0.0,
                'followers': creator.followers or 0,
                'status': creator.result or 'Unknown',
                'contact': creator.contact or '',
                'video_count': creator.total_vt or len(creator.video_links) if hasattr(creator, 'video_links') and creator.video_links else 0
            })
        
        return preview_data
    
    def calculate_cross_brand_statistics(
        self, 
        brand_groups: Dict[str, List[CreatorRow]]
    ) -> Dict[str, any]:
        """
        Calculate statistics across all brands for comparison.
        
        Args:
            brand_groups: Dictionary of brand groups
            
        Returns:
            Dictionary with cross-brand statistics
        """
        total_creators = sum(len(creators) for creators in brand_groups.values())
        total_brands = len(brand_groups)
        
        # Calculate total GMV across all brands
        total_gmv = 0.0
        gmv_by_brand = {}
        
        for brand_name, creators in brand_groups.items():
            brand_gmv = 0.0
            for creator in creators:
                gmv = self._get_creator_gmv(creator)
                if gmv:
                    brand_gmv += gmv
            
            gmv_by_brand[brand_name] = brand_gmv
            total_gmv += brand_gmv
        
        # Find top performing brand
        top_brand = max(gmv_by_brand.items(), key=lambda x: x[1]) if gmv_by_brand else ("None", 0.0)
        
        # Calculate average creators per brand
        avg_creators_per_brand = total_creators / total_brands if total_brands > 0 else 0
        
        return {
            'total_creators': total_creators,
            'total_brands': total_brands,
            'total_gmv': total_gmv,
            'avg_creators_per_brand': avg_creators_per_brand,
            'top_performing_brand': top_brand[0],
            'top_brand_gmv': top_brand[1],
            'gmv_by_brand': gmv_by_brand
        }