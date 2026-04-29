"""Tests for brand alias management interface"""
import pytest
from app import create_app
from app.models.db import db, BrandAlias


@pytest.fixture
def app():
    """Create test app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def sample_aliases(app):
    """Create sample aliases"""
    with app.app_context():
        aliases = [
            BrandAlias(canonical_name='Nike', alias_name='NIKE', similarity_score=1.0),
            BrandAlias(canonical_name='Nike', alias_name='nike', similarity_score=1.0),
            BrandAlias(canonical_name='Nike', alias_name='Nike Inc', similarity_score=0.95),
            BrandAlias(canonical_name='Adidas', alias_name='ADIDAS', similarity_score=1.0),
            BrandAlias(canonical_name='Adidas', alias_name='adidas', similarity_score=1.0),
        ]
        for alias in aliases:
            db.session.add(alias)
        db.session.commit()
        return aliases


class TestBrandAliasInterface:
    """Test brand alias management interface"""
    
    def test_brands_page_renders_with_tabs(self, client):
        """Test that brands page renders with both tabs"""
        response = client.get('/brands')
        assert response.status_code == 200
        assert b'Brand Profiles' in response.data
        assert b'Brand Aliases' in response.data
    
    def test_get_all_aliases(self, client, sample_aliases):
        """Test getting all aliases"""
        response = client.get('/api/brands/aliases')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert len(data['aliases']) == 5
    
    def test_create_alias(self, client):
        """Test creating a new alias"""
        response = client.post('/api/brands/aliases', json={
            'canonical_brand': 'Nike',
            'alias': 'Nike Sports',
            'confidence_score': 0.9
        })
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'alias' in data
        assert data['alias']['canonical_brand'] == 'Nike'
        assert data['alias']['alias'] == 'Nike Sports'
    
    def test_create_alias_validation(self, client):
        """Test alias creation validation"""
        # Missing canonical_brand
        response = client.post('/api/brands/aliases', json={
            'alias': 'Nike Sports'
        })
        assert response.status_code == 400
        
        # Missing alias
        response = client.post('/api/brands/aliases', json={
            'canonical_brand': 'Nike'
        })
        assert response.status_code == 400
    
    def test_update_alias(self, client, sample_aliases):
        """Test updating an alias"""
        with client.application.app_context():
            alias = BrandAlias.query.first()
            alias_id = alias.id
        
        response = client.put(f'/api/brands/aliases/{alias_id}', json={
            'canonical_brand': 'Nike',
            'alias': 'Nike Updated',
            'confidence_score': 0.85
        })
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['alias']['alias'] == 'Nike Updated'
        assert data['alias']['confidence_score'] == 0.85
    
    def test_delete_alias(self, client, sample_aliases):
        """Test deleting a single alias"""
        with client.application.app_context():
            alias = BrandAlias.query.first()
            alias_id = alias.id
        
        response = client.delete(f'/api/brands/aliases/{alias_id}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        
        # Verify deletion
        with client.application.app_context():
            deleted_alias = BrandAlias.query.get(alias_id)
            assert deleted_alias is None
    
    def test_delete_alias_group(self, client, sample_aliases):
        """Test deleting all aliases for a canonical brand"""
        response = client.delete('/api/brands/aliases/group/Nike')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['deleted_count'] == 3  # Nike has 3 aliases
        
        # Verify deletion
        with client.application.app_context():
            remaining_nike = BrandAlias.query.filter_by(canonical_name='Nike').all()
            assert len(remaining_nike) == 0
            
            # Adidas aliases should still exist
            remaining_adidas = BrandAlias.query.filter_by(canonical_name='Adidas').all()
            assert len(remaining_adidas) == 2
    
    def test_delete_nonexistent_alias(self, client):
        """Test deleting a nonexistent alias"""
        response = client.delete('/api/brands/aliases/99999')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['success'] is False
    
    def test_delete_nonexistent_alias_group(self, client):
        """Test deleting aliases for a nonexistent brand"""
        response = client.delete('/api/brands/aliases/group/NonexistentBrand')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['success'] is False
    
    def test_alias_grouping_in_response(self, client, sample_aliases):
        """Test that aliases are properly grouped by canonical brand"""
        response = client.get('/api/brands/aliases')
        assert response.status_code == 200
        
        data = response.get_json()
        aliases = data['aliases']
        
        # Group by canonical brand
        nike_aliases = [a for a in aliases if a['canonical_brand'] == 'Nike']
        adidas_aliases = [a for a in aliases if a['canonical_brand'] == 'Adidas']
        
        assert len(nike_aliases) == 3
        assert len(adidas_aliases) == 2
        
        # Check confidence scores
        nike_inc = next(a for a in nike_aliases if a['alias'] == 'Nike Inc')
        assert nike_inc['confidence_score'] == 0.95
