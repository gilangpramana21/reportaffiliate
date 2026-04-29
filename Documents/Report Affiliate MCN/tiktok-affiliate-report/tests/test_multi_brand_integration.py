"""
Multi-Brand Integration Tests

This module contains comprehensive integration tests for the multi-brand
detection and processing system. It tests the complete workflow from
file parsing to report generation.
"""

import pytest
import tempfile
import os
import pandas as pd
from unittest.mock import Mock, patch
from datetime import date

from app.services.multi_brand_integration import MultiBrandIntegrationService
from app.services.data_parser import ParseResult, CreatorRow
from app.services.multi_brand_detector import BrandDetectionResult
from app.services.brand_ui_models import MultiBrandReportConfig
from app.services.multi_brand_exceptions import BrandDetectionError, BrandColumnNotFoundError


class TestMultiBrandIntegration:
    """Test suite for multi-brand integration functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.integration_service = MultiBrandIntegrationService()
        
        # Create sample creator data
        self.sample_creators = [
            CreatorRow(
                username="creator1", brand="FLORIST", followers=10000,
                avg_gmv_month=5000000, link_acc="https://tiktok.com/@creator1"
            ),
            CreatorRow(
                username="creator2", brand="FLORIST", followers=15000,
                avg_gmv_month=7000000, link_acc="https://tiktok.com/@creator2"
            ),
            CreatorRow(
                username="creator3", brand="BRAND_X", followers=8000,
                avg_gmv_month=3000000, link_acc="https://tiktok.com/@creator3"
            ),
            CreatorRow(
                username="creator4", brand="BRAND_X", followers=12000,
                avg_gmv_month=4500000, link_acc="https://tiktok.com/@creator4"
            ),
            CreatorRow(
                username="creator5", brand="COMPANY_A", followers=20000,
                avg_gmv_month=8000000, link_acc="https://tiktok.com/@creator5"
            ),
        ]
    
    def create_test_excel_file(self, creators=None, include_brand_column=True):
        """Create a test Excel file with sample data."""
        if creators is None:
            creators = self.sample_creators
        
        # Create DataFrame
        data = []
        for creator in creators:
            row = {
                'USERNAME': creator.username,
                'LINK ACC': creator.link_acc,
                'FOLLS': creator.followers,
                'AVG GMV/MONTH': creator.avg_gmv_month,
            }
            
            if include_brand_column:
                row['BRAND'] = creator.brand
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        df.to_excel(temp_file.name, index=False, sheet_name='Deal')
        temp_file.close()
        
        return temp_file.name
    
    def test_multi_brand_workflow_success(self):
        """Test successful multi-brand workflow execution."""
        # Create test file
        test_file = self.create_test_excel_file()
        
        try:
            # Process file
            result = self.integration_service.process_file_for_multi_brand(test_file)
            
            # Verify results
            assert result.success is True
            assert result.is_multi_brand is True
            assert result.brand_detection_result is not None
            assert len(result.brand_detection_result.brands_detected) >= 2
            assert result.brand_selection_data is not None
            assert result.workflow_stage == "completed"
            
            # Verify brand detection
            detected_brands = result.brand_detection_result.brands_detected
            assert "FLORIST" in detected_brands
            assert "BRAND_X" in detected_brands
            assert "COMPANY_A" in detected_brands
            
            # Verify brand selection data
            selection_data = result.brand_selection_data
            assert selection_data.is_multi_brand is True
            assert len(selection_data.brand_previews) >= 2
            
            # Check brand previews
            for brand_name in detected_brands:
                assert brand_name in selection_data.brand_previews
                preview = selection_data.brand_previews[brand_name]
                assert preview.creator_count > 0
                assert len(preview.top_creators) > 0
            
        finally:
            # Clean up
            os.unlink(test_file)
    
    def test_single_brand_workflow(self):
        """Test workflow with single-brand file."""
        # Create single-brand data
        single_brand_creators = [
            CreatorRow(
                username="creator1", brand="FLORIST", followers=10000,
                avg_gmv_month=5000000, link_acc="https://tiktok.com/@creator1"
            ),
            CreatorRow(
                username="creator2", brand="FLORIST", followers=15000,
                avg_gmv_month=7000000, link_acc="https://tiktok.com/@creator2"
            ),
        ]
        
        test_file = self.create_test_excel_file(single_brand_creators)
        
        try:
            # Process file
            result = self.integration_service.process_file_for_multi_brand(test_file)
            
            # Verify results
            assert result.success is True
            assert result.is_multi_brand is False
            assert result.brand_detection_result is not None
            assert len(result.brand_detection_result.brands_detected) == 1
            assert result.brand_selection_data is None  # No selection needed for single brand
            
        finally:
            os.unlink(test_file)
    
    def test_no_brand_column_error(self):
        """Test error handling when BRAND column is missing."""
        test_file = self.create_test_excel_file(include_brand_column=False)
        
        try:
            # Process file
            result = self.integration_service.process_file_for_multi_brand(test_file)
            
            # Verify error handling
            assert result.success is False
            assert result.error_message is not None
            assert "BRAND column" in result.error_message or "brand" in result.error_message.lower()
            
        finally:
            os.unlink(test_file)
    
    def test_brand_validation(self):
        """Test brand name validation."""
        validator = self.integration_service.validator
        
        # Test valid brand names
        valid_brands = ["FLORIST", "Brand X", "Company-A", "Brand_123"]
        for brand in valid_brands:
            validated = validator.validate_brand_name(brand)
            assert validated is not None
            assert len(validated) > 0
        
        # Test invalid brand names
        invalid_brands = ["", "   ", "A" * 200, "<script>alert('xss')</script>"]
        for brand in invalid_brands:
            with pytest.raises(Exception):
                validator.validate_brand_name(brand)
    
    def test_brand_selection_data_preparation(self):
        """Test preparation of brand selection data."""
        # Create mock parse result
        parse_result = ParseResult(
            deal_rows=self.sample_creators,
            non_deal_rows=[],
            detected_columns=['USERNAME', 'BRAND', 'FOLLS'],
            errors=[],
            is_multi_brand=True
        )
        
        # Mock brand detection result
        parse_result.brand_detection_result = BrandDetectionResult(
            brands_detected=["FLORIST", "BRAND_X", "COMPANY_A"],
            brand_counts={"FLORIST": 2, "BRAND_X": 2, "COMPANY_A": 1},
            total_creators=5,
            has_unassigned=False,
            detection_confidence=0.9,
            is_multi_brand=True
        )
        
        # Get brand selection data
        selection_data = self.integration_service.get_brand_selection_data(parse_result)
        
        # Verify results
        assert selection_data is not None
        assert selection_data.is_multi_brand is True
        assert len(selection_data.detected_brands) == 3
        assert len(selection_data.brand_previews) == 3
        
        # Check specific brand data
        florist_preview = selection_data.brand_previews["FLORIST"]
        assert florist_preview.creator_count == 2
        assert florist_preview.total_gmv > 0
        assert len(florist_preview.top_creators) == 2
    
    @patch('app.services.multi_brand_integration.MultiBrandReportGenerator')
    def test_report_generation(self, mock_report_generator_class):
        """Test multi-brand report generation."""
        # Mock report generator
        mock_generator = Mock()
        mock_report_generator_class.return_value = mock_generator
        
        # Mock successful report generation
        from app.services.brand_ui_models import MultiBrandReportResult
        mock_result = MultiBrandReportResult(
            success=True,
            generated_reports={"FLORIST": "florist_report.pdf", "BRAND_X": "brandx_report.pdf"},
            failed_brands=[],
            consolidated_report_path=None
        )
        mock_generator.generate_reports.return_value = mock_result
        
        # Create test configuration
        config = MultiBrandReportConfig(
            selected_brands=["FLORIST", "BRAND_X"],
            report_mode="separate",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            batch_number="Test Batch"
        )
        
        # Create mock parse result
        parse_result = ParseResult(
            deal_rows=self.sample_creators,
            non_deal_rows=[],
            detected_columns=['USERNAME', 'BRAND'],
            errors=[],
            is_multi_brand=True
        )
        parse_result.brand_detection_result = BrandDetectionResult(
            brands_detected=["FLORIST", "BRAND_X"],
            brand_counts={"FLORIST": 2, "BRAND_X": 2},
            total_creators=4,
            has_unassigned=False,
            detection_confidence=0.9,
            is_multi_brand=True
        )
        
        # Generate reports
        result = self.integration_service.generate_multi_brand_reports(
            config, parse_result, Mock()
        )
        
        # Verify results
        assert result.success is True
        assert len(result.generated_reports) == 2
        assert "FLORIST" in result.generated_reports
        assert "BRAND_X" in result.generated_reports
        assert len(result.failed_brands) == 0
    
    def test_compatibility_validation(self):
        """Test multi-brand compatibility validation."""
        # Create parse result with template info
        parse_result = ParseResult(
            deal_rows=self.sample_creators,
            non_deal_rows=[],
            detected_columns=['USERNAME', 'BRAND'],
            errors=[]
        )
        
        # Mock template info
        from app.services.template_detector import TemplateInfo
        parse_result.template_info = TemplateInfo(
            template_type="florist",
            confidence=0.9,
            multi_video_support=True,
            video_columns=["LINK VIDEO"],
            special_features={},
            parsing_strategy="single_column",
            brand_column="BRAND",
            has_mixed_structures=False,
            brand_structures={},
            multi_brand_compatible=True
        )
        
        # Test compatibility
        is_compatible, issues = self.integration_service.validate_multi_brand_compatibility(parse_result)
        
        assert is_compatible is True
        assert len(issues) == 0
    
    def test_cache_operations(self):
        """Test cache clearing and status operations."""
        # Test cache clearing
        self.integration_service.clear_caches()
        
        # Test system status
        status = self.integration_service.get_system_status()
        
        assert 'components_initialized' in status
        assert 'auto_detect_enabled' in status
        assert 'cache_status' in status
        assert status['components_initialized'] is True
    
    def test_error_recovery(self):
        """Test error recovery and graceful degradation."""
        # Test with corrupted file path
        result = self.integration_service.process_file_for_multi_brand("nonexistent_file.xlsx")
        
        assert result.success is False
        assert result.error_message is not None
        assert result.workflow_stage != "completed"
    
    def test_performance_with_large_dataset(self):
        """Test performance with larger dataset."""
        # Create larger dataset
        large_creators = []
        brands = ["FLORIST", "BRAND_X", "COMPANY_A", "BRAND_Y", "COMPANY_B"]
        
        for i in range(100):  # 100 creators
            brand = brands[i % len(brands)]
            creator = CreatorRow(
                username=f"creator{i}",
                brand=brand,
                followers=10000 + (i * 100),
                avg_gmv_month=1000000 + (i * 50000),
                link_acc=f"https://tiktok.com/@creator{i}"
            )
            large_creators.append(creator)
        
        test_file = self.create_test_excel_file(large_creators)
        
        try:
            # Process file and measure basic performance
            import time
            start_time = time.time()
            
            result = self.integration_service.process_file_for_multi_brand(test_file)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verify results
            assert result.success is True
            assert result.is_multi_brand is True
            assert len(result.brand_detection_result.brands_detected) == 5
            
            # Basic performance check (should complete within reasonable time)
            assert processing_time < 30  # Should complete within 30 seconds
            
            print(f"Processed 100 creators with 5 brands in {processing_time:.2f} seconds")
            
        finally:
            os.unlink(test_file)


class TestMultiBrandExceptionHandling:
    """Test suite for multi-brand exception handling."""
    
    def test_brand_detection_error_handling(self):
        """Test brand detection error handling."""
        from app.services.multi_brand_exceptions import handle_brand_detection_error
        
        # Test generic exception conversion
        generic_error = Exception("Something went wrong")
        brand_error = handle_brand_detection_error(generic_error, "testing")
        
        assert isinstance(brand_error, BrandDetectionError)
        assert "testing" in str(brand_error)
        assert len(brand_error.recovery_suggestions) > 0
    
    def test_validation_error_messages(self):
        """Test validation error messages are user-friendly."""
        from app.services.multi_brand_validator import MultiBrandValidator
        from app.services.multi_brand_exceptions import ValidationError
        
        validator = MultiBrandValidator()
        
        # Test brand name validation error
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_brand_name("")
        
        error = exc_info.value
        assert "cannot be empty" in error.get_user_message()
        assert len(error.recovery_suggestions) > 0
    
    def test_error_context_preservation(self):
        """Test that error context is preserved through the workflow."""
        integration_service = MultiBrandIntegrationService()
        
        # Test with invalid file
        result = integration_service.process_file_for_multi_brand("invalid_file.xlsx")
        
        assert result.success is False
        assert result.error_message is not None
        assert result.workflow_stage != "completed"
        
        # Error message should be user-friendly
        assert "Suggested actions:" in result.error_message or "suggestion" in result.error_message.lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])