"""
Template Detector — deteksi jenis template Excel dan adaptasi parsing strategy.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import pandas as pd

# Initialize logger
logger = logging.getLogger(__name__)


@dataclass
class TemplateInfo:
    """Informasi template yang terdeteksi dengan dukungan multi-brand."""
    template_type: str  # 'florist', 'untitled_spreadsheet', 'generic'
    confidence: float   # 0.0 - 1.0
    multi_video_support: bool
    video_columns: List[str]
    special_features: Dict[str, bool]
    parsing_strategy: str  # 'single_column', 'multi_column', 'hybrid'
    # Multi-brand support fields
    brand_column: Optional[str] = None
    has_mixed_structures: bool = False
    brand_structures: Dict[str, List[str]] = None
    multi_brand_compatible: bool = True


class TemplateDetector:
    """
    Deteksi jenis template Excel berdasarkan struktur kolom dan konten.
    Menentukan strategi parsing yang optimal untuk setiap template.
    """
    
    # Template signatures - pola kolom yang mengidentifikasi template tertentu
    TEMPLATE_SIGNATURES = {
        'florist': {
            'required_columns': ['USERNAME', 'LINK ACC'],
            'optional_columns': [
                'TANGGAL DEAL', 'FOLLOWERS', 'SAMPEL APA', 'NOTE RARA',
                'UPDATE VT', 'TOTAL VT', 'NOTE DEAL VT', 'NOTE DEAL',
                'LINK VIDEO', 'FOLLOWUP'
            ],
            'video_columns': ['LINK VIDEO', 'UPDATE VT', 'UPDATE VT FOLLOWUP'],
            'multi_video_indicators': ['FOLLOWUP', 'UPDATE VT'],
            'confidence_boost': 0.2,
            'filename_keywords': ['florist'],  # Keyword untuk filename matching
        },
        'untitled_spreadsheet': {
            'required_columns': ['TGL DEAL', 'USERNAME', 'LINK ACC', 'FOLLS'],
            'optional_columns': ['UPDATE VT FOLLOWUP', 'LINK VIDEO FOLLOWUP'],
            'video_columns': ['LINK VIDEO', 'UPDATE VT FOLLOWUP', 'LINK VIDEO FOLLOWUP'],
            'multi_video_indicators': ['FOLLOWUP', 'UPDATE VT'],
            'confidence_boost': 0.2,
            'filename_keywords': ['untitled', 'spreadsheet'],
        },
        'generic': {
            'required_columns': ['USERNAME'],
            'optional_columns': [],
            'video_columns': ['LINK VIDEO', 'VIDEO LINK', 'UPDATE VT'],
            'multi_video_indicators': ['FOLLOWUP', 'UPDATE', 'VT'],
            'confidence_boost': 0.1,
            'filename_keywords': [],
        }
    }
    
    def detect_template(self, df: pd.DataFrame, file_path: str = '') -> TemplateInfo:
        """
        Deteksi template berdasarkan struktur kolom dan konten dengan dukungan multi-brand.
        
        Args:
            df: DataFrame yang sudah di-promote header
            file_path: Path file untuk hint tambahan
            
        Returns:
            TemplateInfo dengan detail template yang terdeteksi
        """
        columns = [str(col).upper().strip() for col in df.columns]
        
        # Normalize kolom untuk matching
        normalized_columns = []
        for col in columns:
            # Strip karakter non-alphanumeric kecuali spasi dan /
            cleaned = re.sub(r'[^\w\s/]', '', col)
            normalized = ' '.join(cleaned.replace('\n', ' ').split())
            normalized_columns.append(normalized)
        
        # Detect brand column for multi-brand support
        brand_column_detected = self._detect_brand_column(normalized_columns, df)
        
        # Check for mixed template structures per brand
        mixed_structure_info = self._analyze_mixed_structures(df, brand_column_detected)
        
        best_template = None
        best_confidence = 0.0
        
        # Test setiap template signature
        for template_name, signature in self.TEMPLATE_SIGNATURES.items():
            confidence = self._calculate_confidence(
                normalized_columns, signature, file_path
            )
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_template = template_name
        
        # Jika tidak ada template yang cocok dengan confidence tinggi, gunakan generic
        if best_confidence < 0.3:
            best_template = 'generic'
            best_confidence = 0.5
        
        # Analisis kemampuan multi-video
        template_sig = self.TEMPLATE_SIGNATURES[best_template]
        multi_video_support = self._detect_multi_video_support(
            normalized_columns, template_sig
        )
        
        # Identifikasi kolom video yang tersedia
        video_columns = self._identify_video_columns(columns, template_sig)
        
        # Tentukan strategi parsing
        parsing_strategy = self._determine_parsing_strategy(
            multi_video_support, len(video_columns)
        )
        
        # Deteksi fitur khusus
        special_features = self._detect_special_features(normalized_columns, df)
        
        # Determine multi-brand compatibility
        multi_brand_compatible = self._determine_multi_brand_compatibility(
            best_template, brand_column_detected, mixed_structure_info
        )
        
        return TemplateInfo(
            template_type=best_template,
            confidence=best_confidence,
            multi_video_support=multi_video_support,
            video_columns=video_columns,
            special_features=special_features,
            parsing_strategy=parsing_strategy,
            brand_column=brand_column_detected,
            has_mixed_structures=mixed_structure_info['has_mixed_structures'],
            brand_structures=mixed_structure_info['brand_structures'],
            multi_brand_compatible=multi_brand_compatible
        )
    
    def _calculate_confidence(
        self, 
        columns: List[str], 
        signature: Dict, 
        file_path: str
    ) -> float:
        """Hitung confidence score untuk template signature."""
        confidence = 0.0
        
        # Check required columns (weight: 0.5)
        required_matches = 0
        for req_col in signature['required_columns']:
            if any(req_col in col for col in columns):
                required_matches += 1
        
        if signature['required_columns']:
            confidence += (required_matches / len(signature['required_columns'])) * 0.5
        
        # Check optional columns (weight: 0.3)
        optional_matches = 0
        for opt_col in signature['optional_columns']:
            if any(opt_col in col for col in columns):
                optional_matches += 1
        
        if signature['optional_columns']:
            # Berikan bonus untuk setiap optional column yang match
            optional_score = min(optional_matches / max(len(signature['optional_columns']), 3), 1.0)
            confidence += optional_score * 0.3
        
        # Filename hints (weight: 0.3 - lebih tinggi untuk prioritas filename)
        file_lower = file_path.lower()
        filename_keywords = signature.get('filename_keywords', [])
        if filename_keywords:
            for keyword in filename_keywords:
                if keyword in file_lower:
                    confidence += 0.3
                    break
        
        # Template-specific confidence boost
        confidence += signature.get('confidence_boost', 0.0)
        
        return min(confidence, 1.0)
    
    def _detect_multi_video_support(
        self, 
        columns: List[str], 
        signature: Dict
    ) -> bool:
        """Deteksi apakah template mendukung multiple video per creator."""
        indicators = signature.get('multi_video_indicators', [])
        
        # Jika ada indikator multi-video, cek apakah ada di kolom
        if indicators:
            for indicator in indicators:
                if any(indicator in col for col in columns):
                    return True
        
        # Jika ada lebih dari 1 kolom video, kemungkinan support multi-video
        video_cols = signature.get('video_columns', [])
        video_count = sum(1 for vcol in video_cols if any(vcol in col for col in columns))
        
        return video_count > 1
    
    def _identify_video_columns(
        self, 
        original_columns: List[str], 
        signature: Dict
    ) -> List[str]:
        """Identifikasi kolom yang berisi link video."""
        video_columns = []
        template_video_cols = signature.get('video_columns', [])
        
        for col in original_columns:
            col_upper = str(col).upper().strip()
            col_normalized = ' '.join(re.sub(r'[^\w\s/]', '', col_upper).split())
            
            # Check exact match dengan template signature
            for template_vcol in template_video_cols:
                if template_vcol in col_normalized:
                    video_columns.append(col)
                    break
            else:
                # Fallback: cek keyword umum
                video_keywords = ['LINK VIDEO', 'VIDEO LINK', 'UPDATE VT', 'FOLLOWUP', 'VT']
                if any(kw in col_normalized for kw in video_keywords):
                    video_columns.append(col)
        
        return video_columns
    
    def _determine_parsing_strategy(
        self, 
        multi_video_support: bool, 
        video_column_count: int
    ) -> str:
        """Tentukan strategi parsing berdasarkan kemampuan template."""
        if not multi_video_support or video_column_count <= 1:
            return 'single_column'
        elif video_column_count >= 3:
            return 'multi_column'
        else:
            return 'hybrid'
    
    def _detect_special_features(
        self, 
        columns: List[str], 
        df: pd.DataFrame
    ) -> Dict[str, bool]:
        """Deteksi fitur khusus template."""
        features = {
            'has_gmv_columns': False,
            'has_engagement_columns': False,
            'has_followup_system': False,
            'has_batch_tracking': False,
            'has_sample_tracking': False,
        }
        
        # GMV columns
        gmv_keywords = ['GMV', 'TOTAL GMV', 'AVG GMV']
        features['has_gmv_columns'] = any(
            any(kw in col for kw in gmv_keywords) for col in columns
        )
        
        # Engagement columns
        engagement_keywords = ['VIEWS', 'LIKES', 'COMMENTS', 'ENGAGEMENT']
        features['has_engagement_columns'] = any(
            any(kw in col for kw in engagement_keywords) for col in columns
        )
        
        # Followup system
        followup_keywords = ['FOLLOWUP', 'UPDATE VT', 'FOLLOW UP']
        features['has_followup_system'] = any(
            any(kw in col for kw in followup_keywords) for col in columns
        )
        
        # Batch tracking
        batch_keywords = ['BATCH', 'NOMOR BATCH', 'NO BATCH']
        features['has_batch_tracking'] = any(
            any(kw in col for kw in batch_keywords) for col in columns
        )
        
        # Sample tracking
        sample_keywords = ['SAMPEL', 'SAMPLE', 'GRATIS', 'STATUS SEMPEL']
        features['has_sample_tracking'] = any(
            any(kw in col for kw in sample_keywords) for col in columns
        )
        
        return features
    
    def get_parsing_recommendations(self, template_info: TemplateInfo) -> Dict[str, any]:
        """
        Berikan rekomendasi parsing berdasarkan template yang terdeteksi.
        
        Returns:
            Dict dengan konfigurasi parsing yang direkomendasikan
        """
        recommendations = {
            'video_extraction_method': 'cell_notes',  # atau 'cell_value'
            'video_columns_to_scan': template_info.video_columns,
            'max_videos_per_creator': 1,
            'enable_multi_video_aggregation': False,
            'fallback_strategies': [],
        }
        
        if template_info.multi_video_support:
            recommendations.update({
                'max_videos_per_creator': 10,
                'enable_multi_video_aggregation': True,
                'video_extraction_method': 'cell_notes_multi_column',
            })
        
        # Template-specific recommendations
        if template_info.template_type == 'florist':
            recommendations.update({
                'video_extraction_method': 'cell_notes_multi_column',
                'max_videos_per_creator': 5,
                'fallback_strategies': ['cell_value', 'hyperlink_extraction'],
            })
        elif template_info.template_type == 'untitled_spreadsheet':
            recommendations.update({
                'video_extraction_method': 'cell_notes_multi_column',
                'max_videos_per_creator': 5,
                'fallback_strategies': ['cell_value_multi_column', 'hyperlink_extraction'],
            })
        elif template_info.template_type == 'generic':
            recommendations.update({
                'video_extraction_method': 'hybrid',
                'max_videos_per_creator': 3,
                'fallback_strategies': ['cell_notes', 'cell_value', 'hyperlink_extraction'],
            })
        
        return recommendations
    
    def suggest_template_improvements(self, template_info: TemplateInfo) -> List[str]:
        """Berikan saran perbaikan template untuk user."""
        suggestions = []
        
        if template_info.confidence < 0.7:
            suggestions.append(
                "Template tidak sepenuhnya dikenali. Pertimbangkan untuk "
                "menggunakan nama kolom standar seperti 'USERNAME', 'LINK VIDEO', dll."
            )
        
        if len(template_info.video_columns) == 0:
            suggestions.append(
                "Tidak ditemukan kolom video. Pastikan ada kolom dengan nama "
                "'LINK VIDEO', 'VIDEO LINK', atau 'UPDATE VT'."
            )
        
        if not template_info.special_features.get('has_gmv_columns', False):
            suggestions.append(
                "Tidak ditemukan kolom GMV. Tambahkan kolom 'AVG GMV/MONTH' "
                "atau 'TOTAL GMV' untuk analisis performa yang lebih baik."
            )
        
        return suggestions
    
    def _detect_brand_column(self, normalized_columns: List[str], df: pd.DataFrame) -> Optional[str]:
        """
        Detect BRAND column for multi-brand support.
        
        Args:
            normalized_columns: List of normalized column names
            df: DataFrame to analyze
            
        Returns:
            Column name if BRAND column detected, None otherwise
        """
        # Common brand column patterns
        brand_patterns = [
            'BRAND', 'BRAND NAME', 'BRAND_NAME', 'BRANDNAME',
            'CLIENT', 'CLIENT NAME', 'CLIENT_NAME', 'CLIENTNAME',
            'COMPANY', 'COMPANY NAME', 'COMPANY_NAME', 'COMPANYNAME',
            'SPONSOR', 'SPONSOR NAME', 'SPONSOR_NAME', 'SPONSORNAME'
        ]
        
        # Check for exact matches first
        for i, col in enumerate(normalized_columns):
            if col in brand_patterns:
                logger.info(f"Brand column detected: {df.columns[i]} (normalized: {col})")
                return df.columns[i]
        
        # Check for partial matches
        for i, col in enumerate(normalized_columns):
            for pattern in brand_patterns:
                if pattern in col or col in pattern:
                    # Verify this column contains brand-like data
                    if self._validate_brand_column(df, df.columns[i]):
                        logger.info(f"Brand column detected (partial match): {df.columns[i]} (normalized: {col})")
                        return df.columns[i]
        
        logger.debug("No brand column detected")
        return None
    
    def _validate_brand_column(self, df: pd.DataFrame, column_name: str) -> bool:
        """
        Validate that a column contains brand-like data.
        
        Args:
            df: DataFrame to analyze
            column_name: Column name to validate
            
        Returns:
            True if column appears to contain brand data
        """
        try:
            # Get non-null values from the column
            values = df[column_name].dropna().astype(str).str.strip()
            
            if len(values) == 0:
                return False
            
            # Check for reasonable brand name characteristics
            unique_values = values.unique()
            
            # Should have multiple unique values but not too many
            if len(unique_values) < 2 or len(unique_values) > len(values) * 0.8:
                return False
            
            # Brand names should be reasonably short (not descriptions)
            avg_length = values.str.len().mean()
            if avg_length > 50:  # Too long for typical brand names
                return False
            
            # Should not be mostly numeric
            numeric_count = sum(1 for v in unique_values if v.replace('.', '').replace(',', '').isdigit())
            if numeric_count > len(unique_values) * 0.5:
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating brand column {column_name}: {e}")
            return False
    
    def _analyze_mixed_structures(self, df: pd.DataFrame, brand_column: Optional[str]) -> Dict[str, Any]:
        """
        Analyze if different brands have different column structures.
        
        Args:
            df: DataFrame to analyze
            brand_column: Name of the brand column if detected
            
        Returns:
            Dictionary with mixed structure analysis results
        """
        mixed_info = {
            'has_mixed_structures': False,
            'brand_structures': {},
            'common_columns': [],
            'brand_specific_columns': {}
        }
        
        if not brand_column or brand_column not in df.columns:
            return mixed_info
        
        try:
            # Group by brand and analyze column usage
            brands = df[brand_column].dropna().unique()
            
            if len(brands) < 2:
                return mixed_info
            
            brand_structures = {}
            all_columns = set(df.columns)
            
            for brand in brands:
                brand_data = df[df[brand_column] == brand]
                
                # Find columns that have non-null data for this brand
                used_columns = []
                for col in df.columns:
                    if col != brand_column:
                        non_null_count = brand_data[col].notna().sum()
                        if non_null_count > 0:
                            used_columns.append(col)
                
                brand_structures[str(brand)] = used_columns
            
            mixed_info['brand_structures'] = brand_structures
            
            # Find common columns (used by all brands)
            if brand_structures:
                common_columns = set(list(brand_structures.values())[0])
                for columns in brand_structures.values():
                    common_columns &= set(columns)
                mixed_info['common_columns'] = list(common_columns)
                
                # Find brand-specific columns
                for brand, columns in brand_structures.items():
                    specific_columns = set(columns) - common_columns
                    if specific_columns:
                        mixed_info['brand_specific_columns'][brand] = list(specific_columns)
                
                # Determine if there are mixed structures
                mixed_info['has_mixed_structures'] = len(mixed_info['brand_specific_columns']) > 0
            
            if mixed_info['has_mixed_structures']:
                logger.info(f"Mixed template structures detected across {len(brands)} brands")
            
        except Exception as e:
            logger.warning(f"Error analyzing mixed structures: {e}")
        
        return mixed_info
    
    def _determine_multi_brand_compatibility(
        self, 
        template_type: str, 
        brand_column: Optional[str], 
        mixed_structure_info: Dict[str, Any]
    ) -> bool:
        """
        Determine if the detected template is compatible with multi-brand processing.
        
        Args:
            template_type: Detected template type
            brand_column: Brand column if detected
            mixed_structure_info: Mixed structure analysis results
            
        Returns:
            True if template supports multi-brand processing
        """
        # If no brand column detected, not multi-brand compatible
        if not brand_column:
            return False
        
        # All template types can support multi-brand if they have a brand column
        # Mixed structures are supported but may require special handling
        if mixed_structure_info['has_mixed_structures']:
            logger.info(f"Template {template_type} has mixed structures but is multi-brand compatible")
        
        return True