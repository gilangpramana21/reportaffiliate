"""
Multi-Brand Validation Service

This module provides comprehensive input validation and sanitization for
multi-brand detection and processing. It ensures data security, validates
business rules, and sanitizes inputs for safe processing.
"""

import re
import os
from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path

from app.services.multi_brand_exceptions import ValidationError, BrandDetectionError

logger = logging.getLogger(__name__)


class MultiBrandValidator:
    """
    Validates and sanitizes inputs for multi-brand processing.
    
    This class provides validation for brand names, file inputs, configuration
    parameters, and other multi-brand related data to ensure security and
    data integrity.
    """
    
    def __init__(self):
        """Initialize MultiBrandValidator with security rules."""
        # Security patterns
        self.dangerous_patterns = [
            r'\.\./',  # Directory traversal
            r'<script',  # XSS attempts
            r'javascript:',  # JavaScript injection
            r'data:',  # Data URLs
            r'vbscript:',  # VBScript injection
            r'onload=',  # Event handlers
            r'onerror=',  # Event handlers
        ]
        
        # Brand name validation rules
        self.max_brand_name_length = 100
        self.min_brand_name_length = 1
        self.valid_brand_chars = re.compile(r'^[a-zA-Z0-9\s\-_&.,()]+$')
        
        # File and dataset limits
        self.max_file_size_mb = 50
        self.max_creators_per_file = 50000
        self.max_brands_per_file = 100
        self.max_selected_brands = 50
        
        # Path sanitization
        self.safe_filename_chars = re.compile(r'[^a-zA-Z0-9\-_.]')
    
    def validate_brand_name(self, brand_name: str, context: str = "brand") -> str:
        """
        Validate and sanitize a brand name.
        
        Args:
            brand_name: Brand name to validate
            context: Context for error messages
            
        Returns:
            Sanitized brand name
            
        Raises:
            ValidationError: If brand name is invalid
        """
        if not brand_name:
            raise ValidationError(
                context, brand_name, 
                "Brand name cannot be empty"
            )
        
        # Convert to string and strip whitespace
        brand_str = str(brand_name).strip()
        
        # Check length
        if len(brand_str) < self.min_brand_name_length:
            raise ValidationError(
                context, brand_str,
                f"Brand name must be at least {self.min_brand_name_length} character long"
            )
        
        if len(brand_str) > self.max_brand_name_length:
            raise ValidationError(
                context, brand_str,
                f"Brand name must be no more than {self.max_brand_name_length} characters long"
            )
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, brand_str, re.IGNORECASE):
                raise ValidationError(
                    context, brand_str,
                    "Brand name contains potentially dangerous content"
                )
        
        # Check character validity
        if not self.valid_brand_chars.match(brand_str):
            raise ValidationError(
                context, brand_str,
                "Brand name contains invalid characters. Only letters, numbers, spaces, hyphens, underscores, and basic punctuation are allowed"
            )
        
        # Additional sanitization
        sanitized = self._sanitize_brand_name(brand_str)
        
        logger.debug(f"Validated brand name: '{brand_name}' -> '{sanitized}'")
        return sanitized
    
    def validate_brand_list(self, brand_names: List[str], context: str = "brand_list") -> List[str]:
        """
        Validate and sanitize a list of brand names.
        
        Args:
            brand_names: List of brand names to validate
            context: Context for error messages
            
        Returns:
            List of sanitized brand names
            
        Raises:
            ValidationError: If any brand name is invalid or list constraints are violated
        """
        if not brand_names:
            raise ValidationError(
                context, brand_names,
                "Brand list cannot be empty"
            )
        
        if len(brand_names) > self.max_brands_per_file:
            raise ValidationError(
                context, brand_names,
                f"Too many brands: {len(brand_names)}. Maximum allowed: {self.max_brands_per_file}"
            )
        
        # Validate each brand name
        sanitized_brands = []
        for i, brand_name in enumerate(brand_names):
            try:
                sanitized = self.validate_brand_name(brand_name, f"{context}[{i}]")
                sanitized_brands.append(sanitized)
            except ValidationError as e:
                # Re-raise with more context
                raise ValidationError(
                    f"{context}[{i}]", brand_name,
                    f"Invalid brand name at position {i}: {e.details['validation_rule']}"
                )
        
        # Check for duplicates after sanitization
        unique_brands = list(set(sanitized_brands))
        if len(unique_brands) != len(sanitized_brands):
            raise ValidationError(
                context, sanitized_brands,
                "Duplicate brand names found after sanitization"
            )
        
        return sanitized_brands
    
    def validate_selected_brands(self, selected_brands: List[str], available_brands: List[str]) -> List[str]:
        """
        Validate selected brands against available brands.
        
        Args:
            selected_brands: List of selected brand names
            available_brands: List of available brand names
            
        Returns:
            List of validated selected brands
            
        Raises:
            ValidationError: If selection is invalid
        """
        if not selected_brands:
            raise ValidationError(
                "selected_brands", selected_brands,
                "At least one brand must be selected"
            )
        
        if len(selected_brands) > self.max_selected_brands:
            raise ValidationError(
                "selected_brands", selected_brands,
                f"Too many brands selected: {len(selected_brands)}. Maximum allowed: {self.max_selected_brands}"
            )
        
        # Validate each selected brand
        validated_brands = []
        for brand in selected_brands:
            sanitized_brand = self.validate_brand_name(brand, "selected_brand")
            
            if sanitized_brand not in available_brands:
                raise ValidationError(
                    "selected_brands", brand,
                    f"Selected brand '{brand}' is not available in the detected brands"
                )
            
            validated_brands.append(sanitized_brand)
        
        return validated_brands
    
    def validate_file_constraints(self, total_creators: int, total_brands: int, file_size_mb: float = None) -> None:
        """
        Validate file size and data constraints.
        
        Args:
            total_creators: Total number of creators in the file
            total_brands: Total number of brands detected
            file_size_mb: File size in megabytes (optional)
            
        Raises:
            ValidationError: If constraints are violated
        """
        if total_creators > self.max_creators_per_file:
            raise ValidationError(
                "file_size", total_creators,
                f"File contains too many creators: {total_creators}. Maximum allowed: {self.max_creators_per_file}"
            )
        
        if total_brands > self.max_brands_per_file:
            raise ValidationError(
                "file_size", total_brands,
                f"File contains too many brands: {total_brands}. Maximum allowed: {self.max_brands_per_file}"
            )
        
        if file_size_mb and file_size_mb > self.max_file_size_mb:
            raise ValidationError(
                "file_size", file_size_mb,
                f"File is too large: {file_size_mb:.1f}MB. Maximum allowed: {self.max_file_size_mb}MB"
            )
    
    def sanitize_filename(self, filename: str, brand_name: str = None) -> str:
        """
        Sanitize filename for safe file system operations.
        
        Args:
            filename: Original filename
            brand_name: Brand name to include in filename (optional)
            
        Returns:
            Sanitized filename safe for file system operations
        """
        # Start with base filename
        if brand_name:
            # Include brand name in filename
            sanitized_brand = self._sanitize_for_filename(brand_name)
            base_name = f"{sanitized_brand}_{filename}"
        else:
            base_name = filename
        
        # Remove or replace unsafe characters
        sanitized = self.safe_filename_chars.sub('_', base_name)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Ensure filename is not empty
        if not sanitized:
            sanitized = "report"
        
        # Limit filename length (keeping extension)
        name_part, ext = os.path.splitext(sanitized)
        if len(name_part) > 100:
            name_part = name_part[:100]
        
        sanitized = name_part + ext
        
        # Ensure no directory traversal
        sanitized = os.path.basename(sanitized)
        
        logger.debug(f"Sanitized filename: '{filename}' -> '{sanitized}'")
        return sanitized
    
    def validate_report_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate multi-brand report configuration.
        
        Args:
            config: Report configuration dictionary
            
        Returns:
            Validated and sanitized configuration
            
        Raises:
            ValidationError: If configuration is invalid
        """
        validated_config = {}
        
        # Validate required fields
        required_fields = ['selected_brands', 'report_mode', 'period_start', 'period_end']
        for field in required_fields:
            if field not in config:
                raise ValidationError(
                    "config", config,
                    f"Required field '{field}' is missing from configuration"
                )
        
        # Validate selected brands
        if 'selected_brands' in config:
            validated_config['selected_brands'] = self.validate_brand_list(
                config['selected_brands'], 'config.selected_brands'
            )
        
        # Validate report mode
        if 'report_mode' in config:
            valid_modes = ['separate', 'consolidated']
            if config['report_mode'] not in valid_modes:
                raise ValidationError(
                    "config.report_mode", config['report_mode'],
                    f"Invalid report mode. Must be one of: {', '.join(valid_modes)}"
                )
            validated_config['report_mode'] = config['report_mode']
        
        # Validate dates (basic format check)
        for date_field in ['period_start', 'period_end']:
            if date_field in config:
                date_value = config[date_field]
                if not isinstance(date_value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}$', date_value):
                    raise ValidationError(
                        f"config.{date_field}", date_value,
                        "Date must be in YYYY-MM-DD format"
                    )
                validated_config[date_field] = date_value
        
        # Validate optional fields
        if 'batch_number' in config:
            batch_number = str(config['batch_number']).strip()
            if len(batch_number) > 50:
                raise ValidationError(
                    "config.batch_number", batch_number,
                    "Batch number must be no more than 50 characters"
                )
            validated_config['batch_number'] = batch_number
        
        return validated_config
    
    def _sanitize_brand_name(self, brand_name: str) -> str:
        """Internal method to sanitize brand name."""
        # Remove extra whitespace
        sanitized = ' '.join(brand_name.split())
        
        # Remove potentially dangerous characters while preserving readability
        # This is less restrictive than filename sanitization
        sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)
        
        return sanitized
    
    def _sanitize_for_filename(self, text: str) -> str:
        """Internal method to sanitize text for use in filenames."""
        # More aggressive sanitization for filenames
        sanitized = self.safe_filename_chars.sub('_', text)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')
        
        # Limit length for filename component
        if len(sanitized) > 30:
            sanitized = sanitized[:30]
        
        return sanitized or "brand"
    
    def validate_alias_config(self, canonical_name: str, aliases: List[str]) -> Tuple[str, List[str]]:
        """
        Validate brand alias configuration.
        
        Args:
            canonical_name: Canonical brand name
            aliases: List of alias names
            
        Returns:
            Tuple of (validated_canonical_name, validated_aliases)
            
        Raises:
            ValidationError: If alias configuration is invalid
        """
        # Validate canonical name
        validated_canonical = self.validate_brand_name(canonical_name, "canonical_name")
        
        # Validate aliases
        if not aliases:
            raise ValidationError(
                "aliases", aliases,
                "At least one alias must be provided"
            )
        
        validated_aliases = []
        for i, alias in enumerate(aliases):
            validated_alias = self.validate_brand_name(alias, f"aliases[{i}]")
            
            # Ensure alias is different from canonical name
            if validated_alias.lower() == validated_canonical.lower():
                raise ValidationError(
                    f"aliases[{i}]", alias,
                    "Alias cannot be the same as the canonical name"
                )
            
            validated_aliases.append(validated_alias)
        
        # Check for duplicate aliases
        unique_aliases = list(set(alias.lower() for alias in validated_aliases))
        if len(unique_aliases) != len(validated_aliases):
            raise ValidationError(
                "aliases", aliases,
                "Duplicate aliases found"
            )
        
        return validated_canonical, validated_aliases


# Global validator instance
validator = MultiBrandValidator()


def validate_brand_name(brand_name: str) -> str:
    """Convenience function for brand name validation."""
    return validator.validate_brand_name(brand_name)


def validate_brand_list(brand_names: List[str]) -> List[str]:
    """Convenience function for brand list validation."""
    return validator.validate_brand_list(brand_names)


def sanitize_filename(filename: str, brand_name: str = None) -> str:
    """Convenience function for filename sanitization."""
    return validator.sanitize_filename(filename, brand_name)