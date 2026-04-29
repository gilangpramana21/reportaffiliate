"""
Multi-Brand Integration Service

This module provides the main integration point for multi-brand functionality.
It orchestrates the complete multi-brand workflow from detection to report generation,
ensuring seamless integration with existing single-brand workflows.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.services.data_parser import DataParser, ParseResult
from app.services.multi_brand_detector import MultiBrandDetector, BrandDetectionResult
from app.services.brand_normalizer import BrandNormalizer, BrandNormalizationResult
from app.services.brand_grouper import BrandGrouper, BrandGroupResult
from app.services.multi_brand_report_generator import MultiBrandReportGenerator
from app.services.multi_brand_validator import MultiBrandValidator
from app.services.multi_brand_exceptions import (
    BrandDetectionError, BrandColumnNotFoundError, InsufficientBrandDataError,
    TemplateCompatibilityError, handle_brand_detection_error
)
from app.services.brand_ui_models import (
    BrandSelectionData, BrandPreviewData, MultiBrandReportConfig, MultiBrandReportResult
)

logger = logging.getLogger(__name__)


@dataclass
class MultiBrandWorkflowResult:
    """Result of complete multi-brand workflow execution."""
    success: bool
    is_multi_brand: bool
    brand_detection_result: Optional[BrandDetectionResult] = None
    brand_selection_data: Optional[BrandSelectionData] = None
    report_result: Optional[MultiBrandReportResult] = None
    error_message: Optional[str] = None
    workflow_stage: str = "initialization"  # Track where workflow stopped


class MultiBrandIntegrationService:
    """
    Main integration service for multi-brand functionality.
    
    This service provides a unified interface for multi-brand operations,
    handling the complete workflow from file parsing to report generation
    while maintaining backward compatibility with single-brand workflows.
    """
    
    def __init__(self):
        """Initialize MultiBrandIntegrationService with all required components."""
        self.data_parser = DataParser()
        self.brand_normalizer = BrandNormalizer()
        self.multi_brand_detector = MultiBrandDetector(self.brand_normalizer)
        self.brand_grouper = BrandGrouper()
        self.validator = MultiBrandValidator()
        self.report_generator = None  # Will be initialized when needed
        
        # Configuration
        self.auto_detect_multi_brand = True
        self.fallback_to_single_brand = True
        
        logger.info("MultiBrandIntegrationService initialized")
    
    def process_file_for_multi_brand(self, file_path: str) -> MultiBrandWorkflowResult:
        """
        Process a file through the complete multi-brand workflow.
        
        This method handles:
        1. File parsing with template detection
        2. Multi-brand detection and validation
        3. Brand normalization and grouping
        4. Preparation of brand selection data for UI
        
        Args:
            file_path: Path to the Excel/CSV file to process
            
        Returns:
            MultiBrandWorkflowResult with processing results
        """
        result = MultiBrandWorkflowResult(
            success=False,
            is_multi_brand=False,
            workflow_stage="initialization"
        )
        
        try:
            # Stage 1: Parse file
            logger.info(f"Starting multi-brand workflow for file: {file_path}")
            result.workflow_stage = "parsing"
            
            parse_result = self.data_parser.parse(file_path)
            
            if parse_result.errors:
                logger.warning(f"Parse errors encountered: {parse_result.errors}")
            
            # Stage 2: Multi-brand detection
            result.workflow_stage = "brand_detection"
            
            # Check template compatibility first
            if parse_result.template_info and hasattr(parse_result.template_info, 'multi_brand_compatible'):
                if not parse_result.template_info.multi_brand_compatible:
                    # Template not compatible, but we can still try detection
                    logger.warning(f"Template {parse_result.template_info.template_type} may not be fully compatible with multi-brand processing")
            
            # Perform multi-brand detection
            enhanced_parse_result = self.data_parser.detect_multi_brand(parse_result)
            result.brand_detection_result = enhanced_parse_result.brand_detection_result
            result.is_multi_brand = enhanced_parse_result.is_multi_brand
            
            if not result.brand_detection_result:
                raise BrandDetectionError("Brand detection failed to produce results")
            
            # Validate detection results
            self._validate_detection_results(result.brand_detection_result)
            
            # Stage 3: Brand normalization and grouping (if multi-brand)
            if result.is_multi_brand:
                result.workflow_stage = "brand_processing"
                
                # Normalize brand names
                normalization_result = self.brand_normalizer.normalize_brands(
                    result.brand_detection_result.brands_detected
                )
                
                # Group creators by brand
                brand_group_result = self.brand_grouper.group_by_brand(
                    enhanced_parse_result.deal_rows + enhanced_parse_result.non_deal_rows,
                    normalization_result
                )
                
                # Stage 4: Prepare brand selection data
                result.workflow_stage = "ui_preparation"
                result.brand_selection_data = self._prepare_brand_selection_data(
                    result.brand_detection_result,
                    brand_group_result,
                    normalization_result
                )
                
                logger.info(f"Multi-brand workflow completed successfully: {len(result.brand_detection_result.brands_detected)} brands detected")
            else:
                logger.info("Single-brand file detected, multi-brand workflow not needed")
            
            result.success = True
            result.workflow_stage = "completed"
            
        except Exception as e:
            error = handle_brand_detection_error(e, result.workflow_stage)
            result.error_message = error.get_user_message()
            logger.error(f"Multi-brand workflow failed at stage {result.workflow_stage}: {error}")
        
        return result
    
    def generate_multi_brand_reports(
        self,
        config: MultiBrandReportConfig,
        parse_result: ParseResult,
        db_session
    ) -> MultiBrandReportResult:
        """
        Generate multi-brand reports based on configuration.
        
        Args:
            config: Report generation configuration
            parse_result: Parsed file data with multi-brand information
            db_session: Database session for Brand Profile access
            
        Returns:
            MultiBrandReportResult with generation results
        """
        try:
            # Validate configuration
            validated_config = self.validator.validate_report_config(config.__dict__)
            
            # Ensure we have multi-brand data
            if not parse_result.is_multi_brand or not parse_result.brand_detection_result:
                raise BrandDetectionError("Multi-brand data not available for report generation")
            
            # Re-run brand processing to get current grouping
            normalization_result = self.brand_normalizer.normalize_brands(
                parse_result.brand_detection_result.brands_detected
            )
            
            brand_group_result = self.brand_grouper.group_by_brand(
                parse_result.deal_rows + parse_result.non_deal_rows,
                normalization_result
            )
            
            # Validate selected brands
            validated_brands = self.validator.validate_selected_brands(
                config.selected_brands,
                parse_result.brand_detection_result.brands_detected
            )
            
            # Initialize report generator if needed
            if not self.report_generator:
                from app.services.report_gen import ReportGenerator
                from app.services.brand_profile import BrandProfileService
                self.report_generator = MultiBrandReportGenerator(
                    ReportGenerator(),
                    BrandProfileService()
                )
            
            # Generate reports
            result = self.report_generator.generate_reports(
                config, brand_group_result, db_session
            )
            
            logger.info(f"Multi-brand report generation completed: {len(result.generated_reports)} reports generated")
            return result
            
        except Exception as e:
            error = handle_brand_detection_error(e, "report_generation")
            logger.error(f"Multi-brand report generation failed: {error}")
            
            # Return failed result
            return MultiBrandReportResult(
                success=False,
                generated_reports={},
                failed_brands=[(brand, str(error)) for brand in config.selected_brands],
                error_message=error.get_user_message()
            )
    
    def get_brand_selection_data(self, parse_result: ParseResult) -> Optional[BrandSelectionData]:
        """
        Get brand selection data for UI from a parsed result.
        
        Args:
            parse_result: ParseResult with multi-brand detection completed
            
        Returns:
            BrandSelectionData for UI or None if not multi-brand
        """
        if not parse_result.is_multi_brand or not parse_result.brand_detection_result:
            return None
        
        try:
            # Re-run brand processing
            normalization_result = self.brand_normalizer.normalize_brands(
                parse_result.brand_detection_result.brands_detected
            )
            
            brand_group_result = self.brand_grouper.group_by_brand(
                parse_result.deal_rows + parse_result.non_deal_rows,
                normalization_result
            )
            
            return self._prepare_brand_selection_data(
                parse_result.brand_detection_result,
                brand_group_result,
                normalization_result
            )
            
        except Exception as e:
            logger.error(f"Failed to prepare brand selection data: {e}")
            return None
    
    def validate_multi_brand_compatibility(self, parse_result: ParseResult) -> Tuple[bool, List[str]]:
        """
        Validate if a parsed file is compatible with multi-brand processing.
        
        Args:
            parse_result: ParseResult to validate
            
        Returns:
            Tuple of (is_compatible, compatibility_issues)
        """
        issues = []
        
        # Check if template info is available
        if not parse_result.template_info:
            issues.append("Template information not available")
        elif hasattr(parse_result.template_info, 'multi_brand_compatible'):
            if not parse_result.template_info.multi_brand_compatible:
                issues.append("Template type not compatible with multi-brand processing")
            
            if hasattr(parse_result.template_info, 'brand_column') and not parse_result.template_info.brand_column:
                issues.append("No BRAND column detected in template")
        
        # Check data quality
        total_creators = len(parse_result.deal_rows) + len(parse_result.non_deal_rows)
        if total_creators == 0:
            issues.append("No creator data found in file")
        
        # Check for brand detection results
        if parse_result.brand_detection_result:
            if parse_result.brand_detection_result.detection_confidence < 0.5:
                issues.append(f"Low brand detection confidence: {parse_result.brand_detection_result.detection_confidence:.1%}")
        
        is_compatible = len(issues) == 0
        return is_compatible, issues
    
    def _validate_detection_results(self, detection_result: BrandDetectionResult) -> None:
        """Validate brand detection results and raise appropriate errors."""
        if not detection_result.brands_detected:
            raise BrandColumnNotFoundError([])
        
        if detection_result.detection_confidence < 0.3:
            raise InsufficientBrandDataError(
                detection_result.total_creators,
                sum(detection_result.brand_counts.values()),
                detection_result.detection_confidence
            )
        
        # Validate file constraints
        self.validator.validate_file_constraints(
            detection_result.total_creators,
            len(detection_result.brands_detected)
        )
    
    def _prepare_brand_selection_data(
        self,
        detection_result: BrandDetectionResult,
        group_result: BrandGroupResult,
        normalization_result: BrandNormalizationResult
    ) -> BrandSelectionData:
        """Prepare brand selection data for UI."""
        brand_previews = {}
        
        for brand_name in detection_result.brands_detected:
            if brand_name in group_result.brand_statistics:
                stats = group_result.brand_statistics[brand_name]
                
                # Get top creators for preview
                creators = group_result.brand_groups.get(brand_name, [])
                top_creators = []
                
                for creator in creators[:5]:  # Top 5 for preview
                    creator_data = {
                        'username': creator.username or '',
                        'gmv': getattr(creator, 'avg_gmv_month', 0) or 0,
                        'followers': getattr(creator, 'followers', 0) or 0,
                        'status': getattr(creator, 'result', '') or ''
                    }
                    top_creators.append(creator_data)
                
                # Check Brand Profile status (placeholder for now)
                brand_profile_status = "unknown"  # Will be updated by actual Brand Profile service
                
                preview = BrandPreviewData(
                    brand_name=brand_name,
                    creator_count=stats.creator_count,
                    total_gmv=stats.total_gmv,
                    avg_gmv=stats.avg_gmv,
                    top_creators=top_creators,
                    has_brand_profile=False,  # Will be updated by Brand Profile service
                    brand_profile_status=brand_profile_status
                )
                
                brand_previews[brand_name] = preview
        
        return BrandSelectionData(
            detected_brands=detection_result.brands_detected,
            brand_previews=brand_previews,
            brand_statistics=group_result.brand_statistics,
            suggested_aliases=normalization_result.suggested_aliases,
            total_creators=detection_result.total_creators,
            is_multi_brand=detection_result.is_multi_brand
        )
    
    def clear_caches(self) -> None:
        """Clear all caches used by multi-brand components."""
        try:
            # Clear detection cache
            if hasattr(self.multi_brand_detector, '_cache'):
                self.multi_brand_detector._cache.clear()
                logger.info("Cleared brand detection cache")
            
            # Clear normalization cache
            if hasattr(self.brand_normalizer, '_cache'):
                self.brand_normalizer._cache.clear()
                logger.info("Cleared brand normalization cache")
            
        except Exception as e:
            logger.warning(f"Failed to clear some caches: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status information about the multi-brand system."""
        status = {
            'components_initialized': True,
            'auto_detect_enabled': self.auto_detect_multi_brand,
            'fallback_enabled': self.fallback_to_single_brand,
            'cache_status': {}
        }
        
        # Check cache status
        try:
            if hasattr(self.multi_brand_detector, '_cache'):
                status['cache_status']['detection_cache_size'] = len(self.multi_brand_detector._cache)
            
            if hasattr(self.brand_normalizer, '_cache'):
                status['cache_status']['normalization_cache_size'] = len(self.brand_normalizer._cache)
        except Exception as e:
            status['cache_status']['error'] = str(e)
        
        return status


# Global integration service instance
integration_service = MultiBrandIntegrationService()


def process_file_for_multi_brand(file_path: str) -> MultiBrandWorkflowResult:
    """Convenience function for multi-brand file processing."""
    return integration_service.process_file_for_multi_brand(file_path)


def generate_multi_brand_reports(
    config: MultiBrandReportConfig,
    parse_result: ParseResult,
    db_session
) -> MultiBrandReportResult:
    """Convenience function for multi-brand report generation."""
    return integration_service.generate_multi_brand_reports(config, parse_result, db_session)


def get_brand_selection_data(parse_result: ParseResult) -> Optional[BrandSelectionData]:
    """Convenience function for getting brand selection data."""
    return integration_service.get_brand_selection_data(parse_result)