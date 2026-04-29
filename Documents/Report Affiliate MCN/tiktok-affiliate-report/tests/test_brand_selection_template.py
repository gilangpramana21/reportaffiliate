"""
Test for Brand Selection Template Integration

This test verifies that the brand selection template integrates correctly
with the multi-brand detection system and renders properly.
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask
from app.routes.pages import pages_bp
from app.routes.upload import upload_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    import os
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'templates')
    app = Flask(__name__, template_folder=template_dir)
    app.config['TESTING'] = True
    app.register_blueprint(pages_bp)
    app.register_blueprint(upload_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_brand_selection_page_missing_params(client):
    """Test brand selection page with missing parameters."""
    response = client.get('/brand-selection')
    assert response.status_code == 400


def test_brand_selection_page_invalid_json(client):
    """Test brand selection page with invalid JSON."""
    response = client.get('/brand-selection?parse_id=test123&brand_data=invalid_json')
    assert response.status_code == 400


def test_brand_selection_page_valid_params(client):
    """Test brand selection page with valid parameters."""
    brand_data = {
        "detected_brands": ["FLORIST", "BRAND_X"],
        "total_creators": 100,
        "brand_previews": {
            "FLORIST": {
                "brand_name": "FLORIST",
                "creator_count": 45,
                "total_gmv": 125500000,
                "avg_gmv": 2800000,
                "top_creators": [
                    {
                        "username": "creator1",
                        "gmv": 5000000,
                        "followers": 100000,
                        "status": "Deal"
                    }
                ],
                "has_brand_profile": True,
                "brand_profile_status": "complete",
                "video_count": 150,
                "deal_ratio": 0.8
            },
            "BRAND_X": {
                "brand_name": "BRAND_X",
                "creator_count": 55,
                "total_gmv": 200000000,
                "avg_gmv": 3600000,
                "top_creators": [
                    {
                        "username": "creator2",
                        "gmv": 8000000,
                        "followers": 200000,
                        "status": "Deal"
                    }
                ],
                "has_brand_profile": False,
                "brand_profile_status": "missing",
                "video_count": 200,
                "deal_ratio": 0.9
            }
        },
        "brand_statistics": {
            "FLORIST": {
                "brand_name": "FLORIST",
                "creator_count": 45,
                "total_gmv": 125500000,
                "avg_gmv": 2800000,
                "video_count": 150,
                "deal_ratio": 0.8
            },
            "BRAND_X": {
                "brand_name": "BRAND_X", 
                "creator_count": 55,
                "total_gmv": 200000000,
                "avg_gmv": 3600000,
                "video_count": 200,
                "deal_ratio": 0.9
            }
        },
        "suggested_aliases": [
            ["FLORIST", "Florist", 0.95]
        ]
    }
    
    import json
    brand_data_json = json.dumps(brand_data)
    
    response = client.get(f'/brand-selection?parse_id=test123&brand_data={brand_data_json}')
    assert response.status_code == 200
    
    # Check that key elements are present in the response
    html = response.get_data(as_text=True)
    assert "Brand Selection" in html
    assert "FLORIST" in html
    assert "BRAND_X" in html
    assert "2 brands detected" in html
    assert "Profile Complete" in html
    assert "Profile Missing" in html


def test_brand_selection_template_handles_empty_data(client):
    """Test brand selection template handles empty/missing data gracefully."""
    brand_data = {
        "detected_brands": ["EMPTY_BRAND"],
        "total_creators": 10,
        "brand_previews": {
            "EMPTY_BRAND": {
                "brand_name": "EMPTY_BRAND",
                "creator_count": 10,
                "total_gmv": 0,  # No GMV data
                "avg_gmv": 0,
                "top_creators": [
                    {
                        "username": None,  # Missing username
                        "gmv": None,       # Missing GMV
                        "followers": None, # Missing followers
                        "status": None     # Missing status
                    }
                ],
                "has_brand_profile": False,
                "brand_profile_status": "missing",
                "video_count": 0,
                "deal_ratio": 0.0
            }
        },
        "brand_statistics": {
            "EMPTY_BRAND": {
                "brand_name": "EMPTY_BRAND",
                "creator_count": 10,
                "total_gmv": 0,
                "avg_gmv": 0,
                "video_count": 0,
                "deal_ratio": 0.0
            }
        },
        "suggested_aliases": []
    }
    
    import json
    brand_data_json = json.dumps(brand_data)
    
    response = client.get(f'/brand-selection?parse_id=test123&brand_data={brand_data_json}')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    assert "EMPTY_BRAND" in html
    assert "Unknown" in html  # Should show "Unknown" for missing username
    assert "N/A" in html      # Should show "N/A" for missing data


if __name__ == "__main__":
    pytest.main([__file__])