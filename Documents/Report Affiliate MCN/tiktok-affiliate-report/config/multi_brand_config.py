"""
Multi-Brand Configuration

This module contains configuration settings for the multi-brand detection
and processing system. These settings can be adjusted based on deployment
environment and performance requirements.
"""

import os
from typing import Dict, Any


class MultiBrandConfig:
    """Configuration class for multi-brand functionality."""
    
    # Feature toggles
    ENABLE_MULTI_BRAND_DETECTION = os.getenv('ENABLE_MULTI_BRAND_DETECTION', 'true').lower() == 'true'
    ENABLE_BRAND_CACHING = os.getenv('ENABLE_BRAND_CACHING', 'true').lower() == 'true'
    ENABLE_PARALLEL_PROCESSING = os.getenv('ENABLE_PARALLEL_PROCESSING', 'true').lower() == 'true'
    
    # Detection thresholds
    MIN_BRANDS_FOR_MULTI_MODE = int(os.getenv('MIN_BRANDS_FOR_MULTI_MODE', '2'))
    BRAND_SIMILARITY_THRESHOLD = float(os.getenv('BRAND_SIMILARITY_THRESHOLD', '0.8'))
    MIN_DETECTION_CONFIDENCE = float(os.getenv('MIN_DETECTION_CONFIDENCE', '0.3'))
    
    # File and dataset limits
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))
    MAX_CREATORS_PER_FILE = int(os.getenv('MAX_CREATORS_PER_FILE', '50000'))
    MAX_BRANDS_PER_FILE = int(os.getenv('MAX_BRANDS_PER_FILE', '100'))
    MAX_SELECTED_BRANDS = int(os.getenv('MAX_SELECTED_BRANDS', '50'))
    
    # Performance settings
    BRAND_GROUPER_BATCH_SIZE = int(os.getenv('BRAND_GROUPER_BATCH_SIZE', '1000'))
    PROGRESS_LOG_INTERVAL = int(os.getenv('PROGRESS_LOG_INTERVAL', '5000'))
    PARALLEL_PROCESSING_THRESHOLD = int(os.getenv('PARALLEL_PROCESSING_THRESHOLD', '3'))
    MAX_PARALLEL_WORKERS = int(os.getenv('MAX_PARALLEL_WORKERS', '4'))
    
    # Cache settings
    BRAND_DETECTION_CACHE_TTL_HOURS = int(os.getenv('BRAND_DETECTION_CACHE_TTL_HOURS', '24'))
    BRAND_NORMALIZATION_CACHE_TTL_HOURS = int(os.getenv('BRAND_NORMALIZATION_CACHE_TTL_HOURS', '12'))
    MAX_CACHE_ENTRIES = int(os.getenv('MAX_CACHE_ENTRIES', '100'))
    
    # Cache file paths
    CACHE_DIRECTORY = os.getenv('CACHE_DIRECTORY', 'uploads')
    BRAND_DETECTION_CACHE_FILE = os.path.join(CACHE_DIRECTORY, '.brand_detection_cache.json')
    BRAND_NORMALIZATION_CACHE_FILE = os.path.join(CACHE_DIRECTORY, '.brand_normalization_cache.json')
    
    # Brand name validation
    MAX_BRAND_NAME_LENGTH = int(os.getenv('MAX_BRAND_NAME_LENGTH', '100'))
    MIN_BRAND_NAME_LENGTH = int(os.getenv('MIN_BRAND_NAME_LENGTH', '1'))
    
    # Report generation settings
    ENABLE_CONSOLIDATED_REPORTS = os.getenv('ENABLE_CONSOLIDATED_REPORTS', 'true').lower() == 'true'
    ENABLE_SEPARATE_REPORTS = os.getenv('ENABLE_SEPARATE_REPORTS', 'true').lower() == 'true'
    REPORT_GENERATION_TIMEOUT_MINUTES = int(os.getenv('REPORT_GENERATION_TIMEOUT_MINUTES', '30'))
    
    # Database settings
    BRAND_ALIAS_TABLE_NAME = os.getenv('BRAND_ALIAS_TABLE_NAME', 'brand_aliases')
    
    # Logging settings
    ENABLE_PERFORMANCE_LOGGING = os.getenv('ENABLE_PERFORMANCE_LOGGING', 'true').lower() == 'true'
    ENABLE_BUSINESS_METRICS = os.getenv('ENABLE_BUSINESS_METRICS', 'true').lower() == 'true'
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Get all configuration settings as a dictionary."""
        settings = {}
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and attr_name.isupper():
                settings[attr_name] = getattr(cls, attr_name)
        return settings
    
    @classmethod
    def validate_settings(cls) -> Dict[str, str]:
        """Validate configuration settings and return any issues."""
        issues = {}
        
        # Validate thresholds
        if not 0.0 <= cls.BRAND_SIMILARITY_THRESHOLD <= 1.0:
            issues['BRAND_SIMILARITY_THRESHOLD'] = 'Must be between 0.0 and 1.0'
        
        if not 0.0 <= cls.MIN_DETECTION_CONFIDENCE <= 1.0:
            issues['MIN_DETECTION_CONFIDENCE'] = 'Must be between 0.0 and 1.0'
        
        # Validate limits
        if cls.MIN_BRANDS_FOR_MULTI_MODE < 2:
            issues['MIN_BRANDS_FOR_MULTI_MODE'] = 'Must be at least 2'
        
        if cls.MAX_FILE_SIZE_MB <= 0:
            issues['MAX_FILE_SIZE_MB'] = 'Must be positive'
        
        if cls.MAX_CREATORS_PER_FILE <= 0:
            issues['MAX_CREATORS_PER_FILE'] = 'Must be positive'
        
        if cls.MAX_BRANDS_PER_FILE <= 0:
            issues['MAX_BRANDS_PER_FILE'] = 'Must be positive'
        
        # Validate performance settings
        if cls.BRAND_GROUPER_BATCH_SIZE <= 0:
            issues['BRAND_GROUPER_BATCH_SIZE'] = 'Must be positive'
        
        if cls.MAX_PARALLEL_WORKERS <= 0:
            issues['MAX_PARALLEL_WORKERS'] = 'Must be positive'
        
        # Validate cache settings
        if cls.BRAND_DETECTION_CACHE_TTL_HOURS <= 0:
            issues['BRAND_DETECTION_CACHE_TTL_HOURS'] = 'Must be positive'
        
        if cls.MAX_CACHE_ENTRIES <= 0:
            issues['MAX_CACHE_ENTRIES'] = 'Must be positive'
        
        # Validate brand name settings
        if cls.MIN_BRAND_NAME_LENGTH <= 0:
            issues['MIN_BRAND_NAME_LENGTH'] = 'Must be positive'
        
        if cls.MAX_BRAND_NAME_LENGTH <= cls.MIN_BRAND_NAME_LENGTH:
            issues['MAX_BRAND_NAME_LENGTH'] = 'Must be greater than MIN_BRAND_NAME_LENGTH'
        
        return issues
    
    @classmethod
    def get_cache_config(cls) -> Dict[str, Any]:
        """Get cache-specific configuration."""
        return {
            'enabled': cls.ENABLE_BRAND_CACHING,
            'detection_ttl_hours': cls.BRAND_DETECTION_CACHE_TTL_HOURS,
            'normalization_ttl_hours': cls.BRAND_NORMALIZATION_CACHE_TTL_HOURS,
            'max_entries': cls.MAX_CACHE_ENTRIES,
            'cache_directory': cls.CACHE_DIRECTORY,
            'detection_cache_file': cls.BRAND_DETECTION_CACHE_FILE,
            'normalization_cache_file': cls.BRAND_NORMALIZATION_CACHE_FILE
        }
    
    @classmethod
    def get_performance_config(cls) -> Dict[str, Any]:
        """Get performance-specific configuration."""
        return {
            'parallel_processing_enabled': cls.ENABLE_PARALLEL_PROCESSING,
            'parallel_threshold': cls.PARALLEL_PROCESSING_THRESHOLD,
            'max_workers': cls.MAX_PARALLEL_WORKERS,
            'batch_size': cls.BRAND_GROUPER_BATCH_SIZE,
            'progress_interval': cls.PROGRESS_LOG_INTERVAL,
            'report_timeout_minutes': cls.REPORT_GENERATION_TIMEOUT_MINUTES
        }
    
    @classmethod
    def get_validation_config(cls) -> Dict[str, Any]:
        """Get validation-specific configuration."""
        return {
            'max_file_size_mb': cls.MAX_FILE_SIZE_MB,
            'max_creators_per_file': cls.MAX_CREATORS_PER_FILE,
            'max_brands_per_file': cls.MAX_BRANDS_PER_FILE,
            'max_selected_brands': cls.MAX_SELECTED_BRANDS,
            'max_brand_name_length': cls.MAX_BRAND_NAME_LENGTH,
            'min_brand_name_length': cls.MIN_BRAND_NAME_LENGTH,
            'similarity_threshold': cls.BRAND_SIMILARITY_THRESHOLD,
            'min_detection_confidence': cls.MIN_DETECTION_CONFIDENCE
        }


# Environment-specific configurations
class DevelopmentConfig(MultiBrandConfig):
    """Development environment configuration."""
    
    # More verbose logging in development
    ENABLE_PERFORMANCE_LOGGING = True
    ENABLE_BUSINESS_METRICS = True
    
    # Smaller limits for development
    MAX_CREATORS_PER_FILE = 10000
    MAX_BRANDS_PER_FILE = 50
    
    # Shorter cache TTL for development
    BRAND_DETECTION_CACHE_TTL_HOURS = 1
    BRAND_NORMALIZATION_CACHE_TTL_HOURS = 1


class ProductionConfig(MultiBrandConfig):
    """Production environment configuration."""
    
    # Conservative settings for production
    MAX_PARALLEL_WORKERS = 2  # Limit resource usage
    REPORT_GENERATION_TIMEOUT_MINUTES = 60  # Longer timeout for large files
    
    # Longer cache TTL for production
    BRAND_DETECTION_CACHE_TTL_HOURS = 48
    BRAND_NORMALIZATION_CACHE_TTL_HOURS = 24


class TestingConfig(MultiBrandConfig):
    """Testing environment configuration."""
    
    # Disable caching for consistent test results
    ENABLE_BRAND_CACHING = False
    
    # Smaller limits for faster tests
    MAX_CREATORS_PER_FILE = 1000
    MAX_BRANDS_PER_FILE = 10
    MAX_PARALLEL_WORKERS = 1
    
    # Disable parallel processing for deterministic tests
    ENABLE_PARALLEL_PROCESSING = False


def get_config() -> MultiBrandConfig:
    """Get configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Global config instance
config = get_config()