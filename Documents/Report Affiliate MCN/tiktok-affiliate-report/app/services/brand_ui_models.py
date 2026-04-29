"""
Brand UI Data Transfer Objects

This module provides data transfer objects (DTOs) for the brand selection
and management user interface. These classes structure data for efficient
transfer between the backend services and frontend components.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.services.brand_grouper import BrandStatistics
from app.services.multi_brand_detector import BrandDetectionResult
from app.services.brand_normalizer import BrandNormalizationResult


@dataclass
class BrandPreviewData:
    """Data for brand preview in UI."""
    brand_name: str
    creator_count: int
    total_gmv: float
    avg_gmv: float
    top_creators: List[Dict[str, Any]]  # Top 5 for preview
    has_brand_profile: bool
    brand_profile_status: str  # "complete", "partial", "missing"
    video_count: int = 0
    deal_ratio: float = 0.0


@dataclass
class BrandSelectionData:
    """Complete data for brand selection interface."""
    detected_brands: List[str]
    brand_previews: Dict[str, BrandPreviewData]
    brand_statistics: Dict[str, BrandStatistics]
    suggested_aliases: List[tuple[str, str, float]]  # (brand1, brand2, similarity)
    total_creators: int
    is_multi_brand: bool
    detection_confidence: float = 0.0
    has_unassigned: bool = False


@dataclass
class BrandAliasConfig:
    """Persistent brand alias configuration."""
    id: Optional[int] = None
    canonical_name: str = ""
    alias_name: str = ""
    similarity_score: float = 1.0
    created_at: Optional[datetime] = None


@dataclass
class MultiBrandReportConfig:
    """Configuration for multi-brand report generation."""
    selected_brands: List[str]
    report_mode: str  # "separate" or "consolidated"
    period_start: str  # ISO date string
    period_end: str    # ISO date string
    batch_number: str
    include_brand_comparison: bool = True


@dataclass
class MultiBrandReportResult:
    """Result of multi-brand report generation."""
    generated_reports: Dict[str, str]  # brand_name -> file_path
    consolidated_report_path: Optional[str] = None
    failed_brands: List[tuple[str, str]] = field(default_factory=list)  # (brand_name, error_message)
    generation_summary: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    total_brands_processed: int = 0
    total_reports_generated: int = 0
    report_record_id: Optional[int] = None  # Database record ID for multi-brand report


class BrandUIDataBuilder:
    """
    Helper class to build UI data transfer objects from service layer data.
    
    This class provides methods to convert service layer objects into
    UI-friendly data structures with proper formatting and additional
    metadata needed for the frontend.
    """
    
    def __init__(self, brand_profile_service=None):
        """
        Initialize the UI data builder.
        
        Args:
            brand_profile_service: Optional BrandProfileService for profile status lookup
        """
        self.brand_profile_service = brand_profile_service
    
    def build_brand_selection_data(
        self,
        brand_detection_result: BrandDetectionResult,
        brand_statistics: Dict[str, BrandStatistics],
        normalization_result: BrandNormalizationResult,
        brand_preview_data: Dict[str, List[Dict[str, Any]]] = None
    ) -> BrandSelectionData:
        """
        Build complete brand selection data for UI.
        
        Args:
            brand_detection_result: Result from MultiBrandDetector
            brand_statistics: Statistics for each brand from BrandGrouper
            normalization_result: Result from BrandNormalizer
            brand_preview_data: Optional preview data for each brand
            
        Returns:
            BrandSelectionData ready for UI consumption
        """
        brand_previews = {}
        
        for brand_name in brand_detection_result.brands_detected:
            # Get statistics for this brand
            stats = brand_statistics.get(brand_name)
            if not stats:
                continue
            
            # Get brand profile status
            has_profile, profile_status = self._get_brand_profile_status(brand_name)
            
            # Get preview data (top creators)
            top_creators = brand_preview_data.get(brand_name, []) if brand_preview_data else []
            
            # Create preview data object
            preview = BrandPreviewData(
                brand_name=brand_name,
                creator_count=stats.creator_count,
                total_gmv=stats.total_gmv,
                avg_gmv=stats.avg_gmv,
                top_creators=top_creators,
                has_brand_profile=has_profile,
                brand_profile_status=profile_status,
                video_count=stats.video_count,
                deal_ratio=stats.deal_ratio
            )
            
            brand_previews[brand_name] = preview
        
        return BrandSelectionData(
            detected_brands=brand_detection_result.brands_detected,
            brand_previews=brand_previews,
            brand_statistics=brand_statistics,
            suggested_aliases=normalization_result.suggested_aliases,
            total_creators=brand_detection_result.total_creators,
            is_multi_brand=brand_detection_result.is_multi_brand,
            detection_confidence=brand_detection_result.detection_confidence,
            has_unassigned=brand_detection_result.has_unassigned
        )
    
    def build_brand_preview_data(
        self,
        brand_name: str,
        creators: List[Any],  # List[CreatorRow]
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Build preview data for a specific brand.
        
        Args:
            brand_name: Name of the brand
            creators: List of CreatorRow objects for this brand
            limit: Maximum number of creators to include in preview
            
        Returns:
            List of creator preview dictionaries
        """
        from app.services.brand_grouper import BrandGrouper
        
        grouper = BrandGrouper()
        return grouper.get_brand_preview_data(brand_name, creators, limit)
    
    def _get_brand_profile_status(self, brand_name: str) -> tuple[bool, str]:
        """
        Get brand profile status for a brand.
        
        Args:
            brand_name: Name of the brand to check
            
        Returns:
            Tuple of (has_profile, status_string)
            status_string is one of: "complete", "partial", "missing"
        """
        if not self.brand_profile_service:
            return False, "missing"
        
        try:
            # This would need to be implemented based on the actual BrandProfileService
            # For now, return default values
            return False, "missing"
        except Exception:
            return False, "missing"
    
    def format_gmv_for_display(self, gmv: float) -> str:
        """
        Format GMV value for display in UI.
        
        Args:
            gmv: GMV value in rupiah
            
        Returns:
            Formatted string (e.g., "Rp2.5JT", "Rp125.5RB")
        """
        if gmv >= 1_000_000:
            return f"Rp{gmv / 1_000_000:.1f}JT"
        elif gmv >= 1_000:
            return f"Rp{gmv / 1_000:.1f}RB"
        else:
            return f"Rp{gmv:,.0f}"
    
    def format_creator_count_for_display(self, count: int) -> str:
        """
        Format creator count for display in UI.
        
        Args:
            count: Number of creators
            
        Returns:
            Formatted string with proper pluralization
        """
        if count == 1:
            return "1 creator"
        else:
            return f"{count:,} creators"
    
    def calculate_brand_comparison_data(
        self,
        brand_statistics: Dict[str, BrandStatistics]
    ) -> Dict[str, Any]:
        """
        Calculate comparison data across all brands for UI charts and summaries.
        
        Args:
            brand_statistics: Statistics for all brands
            
        Returns:
            Dictionary with comparison data for UI
        """
        if not brand_statistics:
            return {}
        
        total_creators = sum(stats.creator_count for stats in brand_statistics.values())
        total_gmv = sum(stats.total_gmv for stats in brand_statistics.values())
        
        # Calculate brand shares
        brand_shares = {}
        for brand_name, stats in brand_statistics.items():
            creator_share = (stats.creator_count / total_creators * 100) if total_creators > 0 else 0
            gmv_share = (stats.total_gmv / total_gmv * 100) if total_gmv > 0 else 0
            
            brand_shares[brand_name] = {
                'creator_share': creator_share,
                'gmv_share': gmv_share,
                'creator_count': stats.creator_count,
                'total_gmv': stats.total_gmv,
                'avg_gmv': stats.avg_gmv
            }
        
        # Find top performing brand
        top_brand = max(brand_statistics.items(), key=lambda x: x[1].total_gmv)
        
        return {
            'total_creators': total_creators,
            'total_gmv': total_gmv,
            'total_brands': len(brand_statistics),
            'avg_gmv_per_brand': total_gmv / len(brand_statistics) if brand_statistics else 0,
            'brand_shares': brand_shares,
            'top_performing_brand': {
                'name': top_brand[0],
                'gmv': top_brand[1].total_gmv,
                'creators': top_brand[1].creator_count
            }
        }