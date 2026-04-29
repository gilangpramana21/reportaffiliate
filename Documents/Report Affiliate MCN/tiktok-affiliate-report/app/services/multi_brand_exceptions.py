"""
Multi-Brand Detection Exceptions

This module defines the exception hierarchy for multi-brand detection and processing.
It provides specific error types for different failure scenarios with actionable
error messages and recovery suggestions.
"""

from typing import List, Optional, Dict, Any


class BrandDetectionError(Exception):
    """Base exception for brand detection errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize BrandDetectionError.
        
        Args:
            message: Human-readable error message
            details: Additional error details for debugging
        """
        super().__init__(message)
        self.details = details or {}
        self.recovery_suggestions = []
    
    def add_recovery_suggestion(self, suggestion: str) -> None:
        """Add a recovery suggestion to help users fix the issue."""
        self.recovery_suggestions.append(suggestion)
    
    def get_user_message(self) -> str:
        """Get a user-friendly error message with recovery suggestions."""
        message = str(self)
        if self.recovery_suggestions:
            message += "\n\nSuggested actions:"
            for i, suggestion in enumerate(self.recovery_suggestions, 1):
                message += f"\n{i}. {suggestion}"
        return message


class BrandColumnNotFoundError(BrandDetectionError):
    """Raised when BRAND column cannot be found or mapped."""
    
    def __init__(self, available_columns: List[str]):
        """
        Initialize BrandColumnNotFoundError.
        
        Args:
            available_columns: List of available columns in the file
        """
        message = "BRAND column not found in the Excel file"
        super().__init__(message, {"available_columns": available_columns})
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Add a column named 'BRAND' to your Excel file with brand names for each creator"
        )
        self.add_recovery_suggestion(
            "Rename an existing column to 'BRAND' if it contains brand information"
        )
        if available_columns:
            similar_columns = [col for col in available_columns 
                             if any(keyword in col.upper() for keyword in ['CLIENT', 'COMPANY', 'SPONSOR'])]
            if similar_columns:
                self.add_recovery_suggestion(
                    f"Consider renaming one of these columns to 'BRAND': {', '.join(similar_columns)}"
                )


class InsufficientBrandDataError(BrandDetectionError):
    """Raised when brand data quality is too low for reliable detection."""
    
    def __init__(self, total_creators: int, valid_brands: int, confidence: float):
        """
        Initialize InsufficientBrandDataError.
        
        Args:
            total_creators: Total number of creators in the file
            valid_brands: Number of creators with valid brand data
            confidence: Detection confidence score
        """
        message = f"Brand data quality too low for reliable detection: {valid_brands}/{total_creators} creators have valid brand data (confidence: {confidence:.1%})"
        super().__init__(message, {
            "total_creators": total_creators,
            "valid_brands": valid_brands,
            "confidence": confidence
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Fill in missing brand names in the BRAND column"
        )
        self.add_recovery_suggestion(
            "Replace placeholder values like 'TBD', 'N/A', '-' with actual brand names"
        )
        self.add_recovery_suggestion(
            "Ensure at least 50% of creators have valid brand data for reliable multi-brand detection"
        )


class BrandNormalizationError(BrandDetectionError):
    """Raised when brand normalization fails."""
    
    def __init__(self, brand_name: str, error_details: str):
        """
        Initialize BrandNormalizationError.
        
        Args:
            brand_name: Brand name that failed normalization
            error_details: Details about the normalization failure
        """
        message = f"Failed to normalize brand name '{brand_name}': {error_details}"
        super().__init__(message, {"brand_name": brand_name, "error_details": error_details})
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Check for special characters or encoding issues in brand names"
        )
        self.add_recovery_suggestion(
            "Ensure brand names are not excessively long or contain invalid characters"
        )


class BrandGroupingError(BrandDetectionError):
    """Raised when creator grouping by brand fails."""
    
    def __init__(self, error_details: str, problematic_creators: Optional[List[str]] = None):
        """
        Initialize BrandGroupingError.
        
        Args:
            error_details: Details about the grouping failure
            problematic_creators: List of creator usernames that caused issues
        """
        message = f"Failed to group creators by brand: {error_details}"
        super().__init__(message, {
            "error_details": error_details,
            "problematic_creators": problematic_creators or []
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Check for data consistency issues in creator records"
        )
        if problematic_creators:
            self.add_recovery_suggestion(
                f"Review data for these creators: {', '.join(problematic_creators[:5])}"
            )


class BrandProfileError(BrandDetectionError):
    """Raised when Brand Profile operations fail."""
    
    def __init__(self, brand_name: str, operation: str, error_details: str):
        """
        Initialize BrandProfileError.
        
        Args:
            brand_name: Brand name that caused the error
            operation: Operation that failed (e.g., 'lookup', 'create', 'update')
            error_details: Details about the failure
        """
        message = f"Brand Profile {operation} failed for '{brand_name}': {error_details}"
        super().__init__(message, {
            "brand_name": brand_name,
            "operation": operation,
            "error_details": error_details
        })
        
        # Add recovery suggestions based on operation
        if operation == 'lookup':
            self.add_recovery_suggestion(
                f"Create a Brand Profile for '{brand_name}' before generating reports"
            )
        elif operation == 'create':
            self.add_recovery_suggestion(
                "Check that all required Brand Profile fields are provided"
            )
        elif operation == 'update':
            self.add_recovery_suggestion(
                "Verify that the Brand Profile exists and you have permission to modify it"
            )


class MultiBrandReportError(BrandDetectionError):
    """Raised when multi-brand report generation fails."""
    
    def __init__(self, failed_brands: List[str], error_details: str):
        """
        Initialize MultiBrandReportError.
        
        Args:
            failed_brands: List of brand names that failed to generate reports
            error_details: Details about the failure
        """
        message = f"Multi-brand report generation failed for {len(failed_brands)} brands: {error_details}"
        super().__init__(message, {
            "failed_brands": failed_brands,
            "error_details": error_details
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Check that all selected brands have valid creator data"
        )
        self.add_recovery_suggestion(
            "Ensure Brand Profiles are configured for all selected brands"
        )
        if failed_brands:
            self.add_recovery_suggestion(
                f"Try generating reports individually for failed brands: {', '.join(failed_brands)}"
            )


class TemplateCompatibilityError(BrandDetectionError):
    """Raised when template is not compatible with multi-brand processing."""
    
    def __init__(self, template_type: str, compatibility_issues: List[str]):
        """
        Initialize TemplateCompatibilityError.
        
        Args:
            template_type: Type of template that has compatibility issues
            compatibility_issues: List of specific compatibility problems
        """
        message = f"Template '{template_type}' is not compatible with multi-brand processing"
        super().__init__(message, {
            "template_type": template_type,
            "compatibility_issues": compatibility_issues
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Add a BRAND column to your Excel file to enable multi-brand processing"
        )
        for issue in compatibility_issues:
            self.add_recovery_suggestion(f"Address compatibility issue: {issue}")


class ValidationError(BrandDetectionError):
    """Raised when input validation fails."""
    
    def __init__(self, field_name: str, field_value: Any, validation_rule: str):
        """
        Initialize ValidationError.
        
        Args:
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            validation_rule: Description of the validation rule that was violated
        """
        message = f"Validation failed for field '{field_name}': {validation_rule}"
        super().__init__(message, {
            "field_name": field_name,
            "field_value": field_value,
            "validation_rule": validation_rule
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            f"Correct the value for '{field_name}' to meet the validation requirement: {validation_rule}"
        )


class CacheError(BrandDetectionError):
    """Raised when caching operations fail."""
    
    def __init__(self, operation: str, cache_type: str, error_details: str):
        """
        Initialize CacheError.
        
        Args:
            operation: Cache operation that failed (e.g., 'load', 'save', 'invalidate')
            cache_type: Type of cache (e.g., 'brand_detection', 'normalization')
            error_details: Details about the cache failure
        """
        message = f"Cache {operation} failed for {cache_type}: {error_details}"
        super().__init__(message, {
            "operation": operation,
            "cache_type": cache_type,
            "error_details": error_details
        })
        
        # Add recovery suggestions
        self.add_recovery_suggestion(
            "Clear the cache and retry the operation"
        )
        self.add_recovery_suggestion(
            "Check disk space and file permissions for cache directory"
        )


def handle_brand_detection_error(error: Exception, context: str = "") -> BrandDetectionError:
    """
    Convert generic exceptions to BrandDetectionError with appropriate context.
    
    Args:
        error: Original exception
        context: Context where the error occurred
        
    Returns:
        BrandDetectionError with appropriate type and recovery suggestions
    """
    if isinstance(error, BrandDetectionError):
        return error
    
    # Convert common exceptions to appropriate BrandDetectionError types
    error_message = str(error)
    
    if "column" in error_message.lower() and "not found" in error_message.lower():
        return BrandColumnNotFoundError([])
    
    if "validation" in error_message.lower():
        return ValidationError("unknown", None, error_message)
    
    if "cache" in error_message.lower():
        return CacheError("unknown", "unknown", error_message)
    
    # Generic BrandDetectionError for unhandled exceptions
    generic_error = BrandDetectionError(f"Unexpected error in {context}: {error_message}")
    generic_error.add_recovery_suggestion("Check the application logs for more details")
    generic_error.add_recovery_suggestion("Try the operation again or contact support if the issue persists")
    
    return generic_error