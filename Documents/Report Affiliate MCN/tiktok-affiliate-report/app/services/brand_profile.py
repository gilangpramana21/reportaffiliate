"""
BrandProfileService — mengelola CRUD untuk Brand Profile
termasuk SKU List dan SOW.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from app.models.db import BrandProfile, ColumnConfig


# ---------------------------------------------------------------------------
# Data Transfer Object
# ---------------------------------------------------------------------------

@dataclass
class BrandProfileData:
    name: str
    sku_list: list[str] = field(default_factory=list)
    sow: str = ""
    has_column_config: bool = False
    id: Optional[int] = None


# ---------------------------------------------------------------------------
# BrandProfileService
# ---------------------------------------------------------------------------

class BrandProfileService:

    def get_or_create(self, brand_name: str, db_session) -> BrandProfileData:
        model = db_session.query(BrandProfile).filter_by(name=brand_name).first()
        if model is None:
            model = BrandProfile(name=brand_name, sku_list="[]", sow="")
            db_session.add(model)
            db_session.commit()
            db_session.refresh(model)
        return self._to_data(model)

    def save(self, profile: BrandProfileData, db_session) -> BrandProfileData:
        sku_json = json.dumps(profile.sku_list, ensure_ascii=False)
        if profile.id is not None:
            model = db_session.query(BrandProfile).filter_by(id=profile.id).first()
            if model is None:
                raise ValueError(f"BrandProfile dengan id={profile.id} tidak ditemukan.")
            model.name = profile.name
            model.sku_list = sku_json
            model.sow = profile.sow
        else:
            model = BrandProfile(name=profile.name, sku_list=sku_json, sow=profile.sow)
            db_session.add(model)
        db_session.commit()
        db_session.refresh(model)
        return self._to_data(model)

    def update_sku_list(self, brand_id: int, sku_list: list[str], db_session) -> None:
        model = db_session.query(BrandProfile).filter_by(id=brand_id).first()
        if model is None:
            raise ValueError(f"BrandProfile dengan id={brand_id} tidak ditemukan.")
        model.sku_list = json.dumps(sku_list, ensure_ascii=False)
        db_session.commit()

    def update_sow(self, brand_id: int, sow: str, db_session) -> None:
        model = db_session.query(BrandProfile).filter_by(id=brand_id).first()
        if model is None:
            raise ValueError(f"BrandProfile dengan id={brand_id} tidak ditemukan.")
        model.sow = sow
        db_session.commit()

    def list_all(self, db_session) -> list[BrandProfileData]:
        models = db_session.query(BrandProfile).all()
        return [self._to_data(m) for m in models]

    def get_by_name(self, brand_name: str, db_session) -> Optional[BrandProfileData]:
        model = db_session.query(BrandProfile).filter_by(name=brand_name).first()
        return self._to_data(model) if model else None

    def get_by_id(self, brand_id: int, db_session) -> Optional[BrandProfileData]:
        model = db_session.query(BrandProfile).filter_by(id=brand_id).first()
        return self._to_data(model) if model else None

    def delete(self, brand_id: int, db_session) -> None:
        model = db_session.query(BrandProfile).filter_by(id=brand_id).first()
        if model is None:
            raise ValueError(f"BrandProfile dengan id={brand_id} tidak ditemukan.")
        db_session.delete(model)
        db_session.commit()

    def _to_data(self, model: BrandProfile) -> BrandProfileData:
        try:
            sku_list = json.loads(model.sku_list) if model.sku_list else []
        except (json.JSONDecodeError, TypeError):
            sku_list = []
        return BrandProfileData(
            id=model.id,
            name=model.name,
            sku_list=sku_list,
            sow=model.sow or "",
            has_column_config=model.column_config is not None,
        )

    # Multi-brand support methods

    def get_profiles_for_brands(
        self, 
        brand_names: list[str], 
        db_session
    ) -> dict[str, Optional[BrandProfileData]]:
        """
        Get Brand Profiles for multiple brands at once.
        
        Args:
            brand_names: List of brand names to lookup
            db_session: Database session
            
        Returns:
            Dictionary mapping brand names to their profiles (None if not found)
        """
        if not brand_names:
            return {}
        
        # Bulk query for efficiency
        models = db_session.query(BrandProfile).filter(
            BrandProfile.name.in_(brand_names)
        ).all()
        
        # Create lookup dictionary
        model_by_name = {model.name: model for model in models}
        
        # Build result dictionary with all requested brands
        result = {}
        for brand_name in brand_names:
            model = model_by_name.get(brand_name)
            result[brand_name] = self._to_data(model) if model else None
        
        return result

    def get_profile_status_summary(
        self, 
        brand_names: list[str], 
        db_session
    ) -> dict[str, str]:
        """
        Get profile status for UI display.
        
        Args:
            brand_names: List of brand names to check
            db_session: Database session
            
        Returns:
            Dictionary mapping brand names to status strings:
            - "complete": Has both SKU list and SOW
            - "partial": Has either SKU list or SOW but not both
            - "empty": Profile exists but has no data
            - "missing": No profile found
        """
        profiles = self.get_profiles_for_brands(brand_names, db_session)
        status_summary = {}
        
        for brand_name, profile in profiles.items():
            if profile is None:
                status_summary[brand_name] = "missing"
            elif not profile.sku_list and not profile.sow:
                status_summary[brand_name] = "empty"
            elif profile.sku_list and profile.sow:
                status_summary[brand_name] = "complete"
            else:
                status_summary[brand_name] = "partial"
        
        return status_summary

    def create_profiles_for_brands(
        self,
        brand_names: list[str],
        db_session
    ) -> dict[str, BrandProfileData]:
        """
        Create Brand Profiles for multiple brands that don't exist yet.
        
        Args:
            brand_names: List of brand names to create profiles for
            db_session: Database session
            
        Returns:
            Dictionary mapping brand names to created profiles
        """
        # Check which profiles already exist
        existing_profiles = self.get_profiles_for_brands(brand_names, db_session)
        
        created_profiles = {}
        
        for brand_name in brand_names:
            if existing_profiles.get(brand_name) is None:
                # Create new profile
                try:
                    profile = self.get_or_create(brand_name, db_session)
                    created_profiles[brand_name] = profile
                except Exception as e:
                    # Log error but continue with other brands
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to create profile for {brand_name}: {e}")
            else:
                # Profile already exists
                created_profiles[brand_name] = existing_profiles[brand_name]
        
        return created_profiles

    def bulk_update_profiles(
        self,
        profile_updates: dict[str, dict[str, any]],
        db_session
    ) -> dict[str, bool]:
        """
        Update multiple Brand Profiles efficiently.
        
        Args:
            profile_updates: Dictionary mapping brand names to update data
                           Format: {brand_name: {"sku_list": [...], "sow": "..."}}
            db_session: Database session
            
        Returns:
            Dictionary mapping brand names to success status (True/False)
        """
        results = {}
        
        # Get existing profiles
        brand_names = list(profile_updates.keys())
        existing_profiles = self.get_profiles_for_brands(brand_names, db_session)
        
        for brand_name, updates in profile_updates.items():
            try:
                profile = existing_profiles.get(brand_name)
                if profile is None:
                    # Create new profile
                    profile = self.get_or_create(brand_name, db_session)
                
                # Apply updates
                if "sku_list" in updates:
                    profile.sku_list = updates["sku_list"]
                if "sow" in updates:
                    profile.sow = updates["sow"]
                
                # Save the updated profile
                self.save(profile, db_session)
                results[brand_name] = True
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to update profile for {brand_name}: {e}")
                results[brand_name] = False
        
        return results

    def get_brands_with_complete_profiles(self, db_session) -> list[str]:
        """
        Get list of brand names that have complete profiles (both SKU list and SOW).
        
        Args:
            db_session: Database session
            
        Returns:
            List of brand names with complete profiles
        """
        models = db_session.query(BrandProfile).all()
        complete_brands = []
        
        for model in models:
            try:
                sku_list = json.loads(model.sku_list) if model.sku_list else []
                sow = model.sow or ""
                
                if sku_list and sow:
                    complete_brands.append(model.name)
                    
            except (json.JSONDecodeError, TypeError):
                # Skip profiles with invalid data
                continue
        
        return complete_brands

    def get_profile_completeness_stats(self, db_session) -> dict[str, int]:
        """
        Get statistics about profile completeness across all brands.
        
        Args:
            db_session: Database session
            
        Returns:
            Dictionary with completeness statistics
        """
        models = db_session.query(BrandProfile).all()
        stats = {
            "total": len(models),
            "complete": 0,
            "partial": 0,
            "empty": 0
        }
        
        for model in models:
            try:
                sku_list = json.loads(model.sku_list) if model.sku_list else []
                sow = model.sow or ""
                
                if sku_list and sow:
                    stats["complete"] += 1
                elif sku_list or sow:
                    stats["partial"] += 1
                else:
                    stats["empty"] += 1
                    
            except (json.JSONDecodeError, TypeError):
                stats["empty"] += 1
        
        return stats
