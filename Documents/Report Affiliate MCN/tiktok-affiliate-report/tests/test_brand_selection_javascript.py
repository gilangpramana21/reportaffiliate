"""
Test for brand selection JavaScript functionality.
Tests the enhanced JavaScript features implemented in Task 8.2.
"""

import pytest
import re
from pathlib import Path


class TestBrandSelectionJavaScript:
    """Test the JavaScript functionality in brand selection template."""
    
    @pytest.fixture
    def template_content(self):
        """Load the brand selection template content."""
        template_path = Path(__file__).parent.parent / "app" / "templates" / "brand_selection.html"
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture
    def javascript_code(self, template_content):
        """Extract JavaScript code from template."""
        script_match = re.search(r'<script>(.*?)</script>', template_content, re.DOTALL)
        assert script_match, "No JavaScript found in template"
        return script_match.group(1)
    
    def test_javascript_functions_exist(self, javascript_code):
        """Test that all required JavaScript functions are present."""
        required_functions = [
            'initializeBrandSelection',
            'setupEventListeners',
            'setupFormValidation',
            'filterBrands',
            'sortBrands',
            'toggleSelectAll',
            'updateSelectedBrandsSummary',
            'validateReportConfiguration',
            'generateReports',
            'loadBrandPreviewData',
            'saveSelections',
            'loadSavedSelections',
            'handleKeyboardShortcuts',
            'showToast'
        ]
        
        for func_name in required_functions:
            assert f'function {func_name}(' in javascript_code, f"Function {func_name} not found"
    
    def test_event_listeners_setup(self, javascript_code):
        """Test that event listeners are properly set up."""
        # Check for addEventListener calls
        assert 'addEventListener(' in javascript_code
        
        # Check for specific event types
        event_types = ['input', 'change', 'blur', 'keydown', 'mouseenter', 'mouseleave']
        for event_type in event_types:
            assert f"'{event_type}'" in javascript_code, f"Event listener for {event_type} not found"
    
    def test_async_functions(self, javascript_code):
        """Test that async functions are properly implemented."""
        async_functions = [
            'generateReports',
            'loadBrandPreviewData',
            'applyAliasDecisions'
        ]
        
        for func_name in async_functions:
            assert f'async function {func_name}(' in javascript_code, f"Async function {func_name} not found"
    
    def test_api_endpoints_called(self, javascript_code):
        """Test that API endpoints are properly called."""
        api_endpoints = [
            '/generate-multi-brand-reports',
            '/apply-aliases',
            '/brand-preview/'
        ]
        
        for endpoint in api_endpoints:
            assert endpoint in javascript_code, f"API endpoint {endpoint} not found"
    
    def test_form_validation_features(self, javascript_code):
        """Test that form validation features are implemented."""
        validation_features = [
            'validateReportConfiguration',
            'setCustomValidity',
            'checkValidity',
            'is-invalid',
            'is-valid'
        ]
        
        for feature in validation_features:
            assert feature in javascript_code, f"Validation feature {feature} not found"
    
    def test_real_time_updates(self, javascript_code):
        """Test that real-time update features are implemented."""
        update_features = [
            'updateSelectedBrandsSummary',
            'updateFilterResults',
            'updateBrandCardVisualState',
            'animateCounterUpdate'
        ]
        
        for feature in update_features:
            assert feature in javascript_code, f"Update feature {feature} not found"
    
    def test_search_and_filter_functionality(self, javascript_code):
        """Test that search and filter functionality is implemented."""
        search_features = [
            'filterBrands',
            'clearFilters',
            'updateFilteredCounts',
            'brandSearchInput',
            'profileStatusFilter'
        ]
        
        for feature in search_features:
            assert feature in javascript_code, f"Search feature {feature} not found"
    
    def test_keyboard_shortcuts(self, javascript_code):
        """Test that keyboard shortcuts are implemented."""
        assert 'handleKeyboardShortcuts' in javascript_code
        assert 'ctrlKey' in javascript_code or 'metaKey' in javascript_code
        assert 'event.key' in javascript_code
    
    def test_local_storage_functionality(self, javascript_code):
        """Test that local storage functionality is implemented."""
        storage_features = [
            'saveSelections',
            'loadSavedSelections',
            'clearSavedSelections',
            'localStorage.setItem',
            'localStorage.getItem',
            'localStorage.removeItem'
        ]
        
        for feature in storage_features:
            assert feature in javascript_code, f"Storage feature {feature} not found"
    
    def test_progress_tracking(self, javascript_code):
        """Test that progress tracking is implemented."""
        progress_features = [
            'startProgressTracking',
            'setGenerationState',
            'progress-bar',
            'setInterval',
            'clearInterval'
        ]
        
        for feature in progress_features:
            assert feature in javascript_code, f"Progress feature {feature} not found"
    
    def test_toast_notifications(self, javascript_code):
        """Test that enhanced toast notifications are implemented."""
        toast_features = [
            'showToast',
            'getToastIcon',
            'alert-dismissible',
            'position-fixed'
        ]
        
        for feature in toast_features:
            assert feature in javascript_code, f"Toast feature {feature} not found"
    
    def test_brand_profile_integration(self, javascript_code):
        """Test that brand profile integration is implemented."""
        profile_features = [
            'createBrandProfile',
            'editBrandProfile',
            'window.open',
            'encodeURIComponent'
        ]
        
        for feature in profile_features:
            assert feature in javascript_code, f"Profile feature {feature} not found"
    
    def test_error_handling(self, javascript_code):
        """Test that proper error handling is implemented."""
        error_features = [
            'try {',
            'catch (',
            'finally {',
            'showGenerationError',
            'console.warn'
        ]
        
        for feature in error_features:
            assert feature in javascript_code, f"Error handling feature {feature} not found"
    
    def test_css_animations(self, javascript_code):
        """Test that CSS animations are included."""
        animation_features = [
            '@keyframes',
            'transition:',
            'transform:',
            'animation:'
        ]
        
        for feature in animation_features:
            assert feature in javascript_code, f"Animation feature {feature} not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])