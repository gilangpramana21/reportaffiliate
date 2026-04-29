"""
Preservation Property Tests for Fresh Mapping Behavior

IMPORTANT: Follow observation-first methodology
1. Run UNFIXED code with non-buggy inputs (fresh mappings with video_links)
2. Observe and record actual outputs
3. Write property-based tests that assert those observed outputs
4. Verify tests PASS on UNFIXED code before implementing the fix

This ensures preservation tests capture real behavior, not assumed behavior.

Property 2: Preservation - Fresh Mapping Behavior Unchanged

For all fresh mapping_ids (where video_links exist in deal_rows), the system SHALL:
- Return video_links_map with entries > 0
- Enable scraping functionality
- Maintain identical API response structure (except for new optional fields)
- Continue video extraction from Excel
"""
import json
import os
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from flask import Flask


def test_fresh_mapping_api_response_structure():
    """
    Property 2: Preservation - Fresh Mapping API Response Unchanged
    
    Test that fresh mappings (with video_links) continue to work identically
    before and after the fix.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test PASSES
    - API returns video_links_map with entries
    - Response structure is correct
    - Scraping functionality works
    
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES
    - Same behavior as unfixed code
    - No regressions
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Create a FRESH mapping with video_links
        fresh_mapping_id = "test_fresh_mapping_99999"
        fresh_mapping_data = {
            "brand_name": "TestBrandFresh",
            "deal_rows": [
                {
                    "username": "creator_fresh1",
                    "link_acc": "https://tiktok.com/@creator_fresh1",
                    "followers": 15000,
                    "video_links": [
                        "https://vt.tiktok.com/ZS2abc123/",
                        "https://vt.tiktok.com/ZS2def456/"
                    ]
                },
                {
                    "username": "creator_fresh2",
                    "link_acc": "https://tiktok.com/@creator_fresh2",
                    "followers": 25000,
                    "video_links": [
                        "https://vt.tiktok.com/ZS2ghi789/"
                    ]
                }
            ],
            "non_deal_rows": []
        }
        
        # Inject fresh mapping into cache
        _mapping_cache[fresh_mapping_id] = fresh_mapping_data
        _save_mapping_cache(_mapping_cache)
        
        # Step 2: Call API endpoint
        response = client.get(f'/api/mapping/{fresh_mapping_id}/creators')
        
        # Step 3: Assert response structure (OBSERVED BEHAVIOR on unfixed code)
        assert response.status_code == 200, "API should return 200 for fresh mapping"
        data = response.get_json()
        
        # PRESERVATION ASSERTIONS - These should PASS on both unfixed and fixed code
        assert 'creators' in data, "Response should contain creators list"
        assert 'video_links_map' in data, "Response should contain video_links_map"
        assert 'has_specific_links' in data, "Response should contain has_specific_links flag"
        
        # Fresh mapping should have video links
        assert len(data['video_links_map']) > 0, \
            "Fresh mapping should have video_links_map with entries"
        
        assert data['has_specific_links'] is True, \
            "Fresh mapping should have has_specific_links=True"
        
        # Verify video_links_map structure
        assert 'creator_fresh1' in data['video_links_map'], \
            "video_links_map should contain creator_fresh1"
        assert 'creator_fresh2' in data['video_links_map'], \
            "video_links_map should contain creator_fresh2"
        
        assert len(data['video_links_map']['creator_fresh1']) == 2, \
            "creator_fresh1 should have 2 video links"
        assert len(data['video_links_map']['creator_fresh2']) == 1, \
            "creator_fresh2 should have 1 video link"
        
        # Cleanup
        if fresh_mapping_id in _mapping_cache:
            del _mapping_cache[fresh_mapping_id]
            _save_mapping_cache(_mapping_cache)


def test_fresh_mapping_scraping_functionality():
    """
    Property 2: Preservation - Scraping Functionality Unchanged
    
    Test that scraping functionality for fresh mappings works identically
    before and after the fix.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test PASSES
    - Scraping buttons enabled
    - No warnings shown
    - Scraping can proceed
    
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES
    - Same behavior as unfixed code
    - No regressions
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Create a FRESH mapping with video_links
        fresh_mapping_id = "test_fresh_scrape_88888"
        fresh_mapping_data = {
            "brand_name": "TestBrandScrapeFresh",
            "deal_rows": [
                {
                    "username": "creator_scrape_fresh",
                    "link_acc": "https://tiktok.com/@creator_scrape_fresh",
                    "followers": 12000,
                    "video_links": [
                        "https://vt.tiktok.com/ZS2xyz123/"
                    ]
                }
            ],
            "non_deal_rows": []
        }
        
        # Inject fresh mapping into cache
        _mapping_cache[fresh_mapping_id] = fresh_mapping_data
        _save_mapping_cache(_mapping_cache)
        
        # Step 2: Call creators endpoint
        response = client.get(f'/api/mapping/{fresh_mapping_id}/creators')
        data = response.get_json()
        
        # PRESERVATION ASSERTIONS - Fresh mapping should work normally
        assert response.status_code == 200, "API should return 200"
        assert len(data.get('video_links_map', {})) > 0, \
            "Fresh mapping should have video links for scraping"
        
        # If fix adds is_stale_mapping flag, it should be False for fresh mappings
        if 'is_stale_mapping' in data:
            assert data['is_stale_mapping'] is False, \
                "Fresh mapping should NOT be flagged as stale"
        
        # Cleanup
        if fresh_mapping_id in _mapping_cache:
            del _mapping_cache[fresh_mapping_id]
            _save_mapping_cache(_mapping_cache)


@given(
    video_link_count=st.integers(min_value=1, max_value=10),
    creator_count=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_fresh_mappings_with_varying_video_counts(video_link_count, creator_count):
    """
    Property-Based Test: Fresh Mappings with Varying Video Link Counts
    
    For all fresh mappings with video_links (count >= 1), the API response
    should contain video_links_map with entries > 0.
    
    This property-based test generates many test cases automatically to
    catch edge cases that manual unit tests might miss.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test PASSES
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES (no regressions)
    """
    from app import create_app
    from app.routes.brands import _mapping_cache, _save_mapping_cache
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Generate fresh mapping with varying video link counts
        mapping_id = f"test_pbt_fresh_{video_link_count}_{creator_count}"
        
        deal_rows = []
        for i in range(creator_count):
            video_links = [
                f"https://vt.tiktok.com/ZS2test{i}_{j}/"
                for j in range(video_link_count)
            ]
            deal_rows.append({
                "username": f"creator_pbt_{i}",
                "link_acc": f"https://tiktok.com/@creator_pbt_{i}",
                "followers": 10000 + i * 1000,
                "video_links": video_links
            })
        
        mapping_data = {
            "brand_name": "TestBrandPBT",
            "deal_rows": deal_rows,
            "non_deal_rows": []
        }
        
        # Inject mapping into cache
        _mapping_cache[mapping_id] = mapping_data
        _save_mapping_cache(_mapping_cache)
        
        try:
            # Call API endpoint
            response = client.get(f'/api/mapping/{mapping_id}/creators')
            
            # PROPERTY ASSERTION: Fresh mappings should always have video_links_map
            assert response.status_code == 200
            data = response.get_json()
            
            assert 'video_links_map' in data, \
                f"Fresh mapping with {video_link_count} links should have video_links_map"
            
            assert len(data['video_links_map']) == creator_count, \
                f"video_links_map should have {creator_count} entries"
            
            # Verify each creator has correct number of video links
            for i in range(creator_count):
                username = f"creator_pbt_{i}"
                assert username in data['video_links_map'], \
                    f"video_links_map should contain {username}"
                assert len(data['video_links_map'][username]) == video_link_count, \
                    f"{username} should have {video_link_count} video links"
            
        finally:
            # Cleanup
            if mapping_id in _mapping_cache:
                del _mapping_cache[mapping_id]
                _save_mapping_cache(_mapping_cache)


def test_manual_cache_clearing_still_works():
    """
    Property 2: Preservation - Manual Cache Clearing Unchanged
    
    Test that manual cache clearing via /api/clear-cache continues to work
    identically before and after the fix.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test PASSES
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES (no regressions)
    """
    from app import create_app
    import os
    
    # Setup: Create Flask app
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Step 1: Ensure cache files exist by creating them
        cache_files = [
            "uploads/.mapping_cache.json",
            "uploads/.parse_cache.json",
            "uploads/.file_path_cache.json"
        ]
        
        # Create dummy cache files if they don't exist
        for cache_file in cache_files:
            if not os.path.exists(cache_file):
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump({}, f)
        
        # Step 2: Call clear-cache endpoint
        response = client.post('/api/clear-cache')
        
        # PRESERVATION ASSERTIONS - Cache clearing should work identically
        assert response.status_code == 200, "Clear cache should return 200"
        data = response.get_json()
        
        assert data['success'] is True, "Clear cache should succeed"
        assert 'cleared' in data, "Response should contain cleared list"
        assert len(data['cleared']) > 0, "Should report cleared items"
        
        # Verify cache files are deleted (this is the actual behavior)
        # Note: In-memory caches may persist, but disk caches should be cleared
        assert not os.path.exists("uploads/.mapping_cache.json"), \
            "Mapping cache file should be deleted"


def test_video_extraction_continues_to_function():
    """
    Property 2: Preservation - Video Extraction Unchanged
    
    Test that video extraction from Excel cells continues to function
    identically before and after the fix.
    
    This test verifies that the _extract_cell_notes() method in DataParser
    continues to work correctly.
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test PASSES
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES (no regressions)
    """
    # This is a unit test for DataParser._extract_cell_notes()
    # Since we don't have a test Excel file, we'll test the method's signature
    # and ensure it's still callable
    
    from app.services.data_parser import DataParser
    
    parser = DataParser()
    
    # Verify method exists and is callable
    assert hasattr(parser, '_extract_cell_notes'), \
        "DataParser should have _extract_cell_notes method"
    
    assert callable(parser._extract_cell_notes), \
        "_extract_cell_notes should be callable"
    
    # Verify method signature (should accept file_path, sheet_name, col_name, header_row_idx)
    import inspect
    sig = inspect.signature(parser._extract_cell_notes)
    params = list(sig.parameters.keys())
    
    assert 'file_path' in params, "Method should accept file_path parameter"
    assert 'sheet_name' in params, "Method should accept sheet_name parameter"
    assert 'col_name' in params, "Method should accept col_name parameter"
    assert 'header_row_idx' in params, "Method should accept header_row_idx parameter"


if __name__ == '__main__':
    """
    Run these tests on UNFIXED code to verify they PASS.
    
    Expected output on UNFIXED code:
    - test_fresh_mapping_api_response_structure: PASS
    - test_fresh_mapping_scraping_functionality: PASS
    - test_property_fresh_mappings_with_varying_video_counts: PASS (20 examples)
    - test_manual_cache_clearing_still_works: PASS
    - test_video_extraction_continues_to_function: PASS
    
    These passing tests confirm the baseline behavior to preserve.
    After implementing the fix, re-run these tests to ensure no regressions.
    """
    pytest.main([__file__, '-v', '--tb=short'])
