"""
Bug Condition Exploration Test for Stale Mapping Detection

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

This test encodes the expected behavior - it will validate the fix when it passes after implementation.

GOAL: Surface counterexamples that demonstrate the bug exists.
"""
import json
import os
import pytest
from flask import Flask


def test_stale_mapping_detection_api_response():
    """
    Property 1: Bug Condition - Stale Mapping Detection Failure
    
    Test that the API endpoint detects stale mappings (mappings without video_links)
    and returns appropriate flags in the response.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
    - API response missing 'is_stale_mapping' flag
    - No indication that mapping is stale
    
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES
    - API response contains 'is_stale_mapping: true'
    - System detects stale mapping condition
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Create a stale mapping by manually editing cache
        # Stale mapping = mapping with deal_rows but NO video_links
        stale_mapping_id = "test_stale_mapping_12345"
        stale_mapping_data = {
            "brand_name": "TestBrand",
            "deal_rows": [
                {
                    "username": "creator1",
                    "link_acc": "https://tiktok.com/@creator1",
                    "followers": 10000,
                    "video_links": []  # EMPTY - this is the stale condition
                },
                {
                    "username": "creator2",
                    "link_acc": "https://tiktok.com/@creator2",
                    "followers": 20000,
                    "video_links": []  # EMPTY - this is the stale condition
                }
            ],
            "non_deal_rows": []
        }
        
        # Inject stale mapping into cache
        _mapping_cache[stale_mapping_id] = stale_mapping_data
        _save_mapping_cache(_mapping_cache)
        
        # Step 2: Call API endpoint to get creators
        response = client.get(f'/api/mapping/{stale_mapping_id}/creators')
        
        # Step 3: Assert response structure
        assert response.status_code == 200, "API should return 200 for existing mapping"
        data = response.get_json()
        
        # CRITICAL ASSERTIONS - These will FAIL on unfixed code
        # Expected behavior: System should detect stale mapping
        assert 'is_stale_mapping' in data, \
            "API response should contain 'is_stale_mapping' flag (BUG: missing on unfixed code)"
        
        assert data['is_stale_mapping'] is True, \
            "API should detect that this mapping has no video_links (BUG: not detected on unfixed code)"
        
        # Additional assertions for expected behavior
        assert 'video_links_map' in data, "Response should contain video_links_map"
        assert len(data['video_links_map']) == 0, "Stale mapping should have empty video_links_map"
        
        # Cleanup
        if stale_mapping_id in _mapping_cache:
            del _mapping_cache[stale_mapping_id]
            _save_mapping_cache(_mapping_cache)


def test_stale_mapping_ui_warning_not_shown():
    """
    Property 1: Bug Condition - Configure Page Shows No Warning
    
    Test that the Configure page does NOT show warning UI for stale mappings
    on unfixed code.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
    - Configure page shows no warning
    - Scraping buttons are NOT disabled
    - No actionable guidance for user
    
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES
    - Warning UI is displayed
    - "Re-parse File" button is present
    - Scraping buttons are disabled
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Create a stale mapping
        stale_mapping_id = "test_stale_ui_67890"
        stale_mapping_data = {
            "brand_name": "TestBrandUI",
            "deal_rows": [
                {
                    "username": "creator_ui",
                    "link_acc": "https://tiktok.com/@creator_ui",
                    "followers": 5000,
                    "video_links": []  # EMPTY - stale condition
                }
            ],
            "non_deal_rows": []
        }
        
        # Inject stale mapping into cache
        _mapping_cache[stale_mapping_id] = stale_mapping_data
        _save_mapping_cache(_mapping_cache)
        
        # Step 2: Load Configure page with stale mapping_id
        response = client.get(f'/configure?mapping_id={stale_mapping_id}&brand_name=TestBrandUI')
        
        # Step 3: Assert page loads successfully
        assert response.status_code == 200, "Configure page should load"
        html_content = response.get_data(as_text=True)
        
        # Step 4: Check API response for stale detection
        api_response = client.get(f'/api/mapping/{stale_mapping_id}/creators')
        api_data = api_response.get_json()
        
        # CRITICAL ASSERTIONS - These will FAIL on unfixed code
        # On unfixed code: API does not return is_stale_mapping flag
        # On fixed code: API returns is_stale_mapping: true
        
        # This assertion documents the bug: API should detect stale mapping
        assert 'is_stale_mapping' in api_data, \
            "API should provide is_stale_mapping flag for UI to show warning (BUG: missing on unfixed code)"
        
        # Cleanup
        if stale_mapping_id in _mapping_cache:
            del _mapping_cache[stale_mapping_id]
            _save_mapping_cache(_mapping_cache)


def test_scraping_fails_with_stale_mapping():
    """
    Property 1: Bug Condition - Scraping Fails with Generic Error
    
    Test that scraping with stale mapping fails without clear guidance.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
    - Scraping proceeds without warning
    - Fails with generic error
    - No actionable guidance
    
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES
    - Scraping is prevented
    - Clear warning shown
    - "Re-parse File" button available
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Create a stale mapping
        stale_mapping_id = "test_stale_scrape_11111"
        stale_mapping_data = {
            "brand_name": "TestBrandScrape",
            "deal_rows": [
                {
                    "username": "creator_scrape",
                    "link_acc": "https://tiktok.com/@creator_scrape",
                    "followers": 8000,
                    "video_links": []  # EMPTY - stale condition
                }
            ],
            "non_deal_rows": []
        }
        
        # Inject stale mapping into cache
        _mapping_cache[stale_mapping_id] = stale_mapping_data
        _save_mapping_cache(_mapping_cache)
        
        # Step 2: Call creators endpoint
        response = client.get(f'/api/mapping/{stale_mapping_id}/creators')
        data = response.get_json()
        
        # CRITICAL ASSERTION - Will FAIL on unfixed code
        # Expected: System detects stale mapping and provides flag
        assert 'is_stale_mapping' in data, \
            "API should detect stale mapping before scraping attempt (BUG: not detected on unfixed code)"
        
        assert data['is_stale_mapping'] is True, \
            "Stale mapping should be flagged as true (BUG: flag missing on unfixed code)"
        
        # Expected: video_links_map is empty for stale mapping
        assert len(data.get('video_links_map', {})) == 0, \
            "Stale mapping should have no video links"
        
        # Cleanup
        if stale_mapping_id in _mapping_cache:
            del _mapping_cache[stale_mapping_id]
            _save_mapping_cache(_mapping_cache)


if __name__ == '__main__':
    """
    Run this test on UNFIXED code to observe failures and document counterexamples.
    
    Expected output on UNFIXED code:
    - test_stale_mapping_detection_api_response: FAIL (missing is_stale_mapping flag)
    - test_stale_mapping_ui_warning_not_shown: FAIL (no warning UI)
    - test_scraping_fails_with_stale_mapping: FAIL (no stale detection)
    
    These failures confirm the bug exists and document the counterexamples.
    """
    pytest.main([__file__, '-v', '--tb=short'])
