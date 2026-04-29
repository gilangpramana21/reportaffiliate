"""
ColumnMapper — menangani pemetaan kolom file ke field standar dan
penyimpanan/pemuatan ColumnConfig dari database.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from app.services.data_parser import CreatorRow, DataParser
from app.models.db import ColumnConfig as ColumnConfigModel


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class ColumnConfig:
    brand_id: int
    mappings: dict[str, str] = field(default_factory=dict)   # {nama_kolom_file: field_standar}
    custom_columns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ColumnMapper
# ---------------------------------------------------------------------------

class ColumnMapper:
    STANDARD_FIELDS = [
        'tanggal', 'username', 'link_acc', 'followers', 'contact',
        'brand', 'pic', 'avg_gmv_month', 'gmv_per_pembeli', 'update',
        'respon_speed', 'result', 'sampel_gratis', 'note',
        'total_vt', 'note_deal', 'gmv_perbulan',
    ]

    _REFERENCE_MAP: dict[str, str] = {
        'TANGGAL': 'tanggal',
        'USERNAME': 'username',
        'LINK ACC': 'link_acc',
        'FOLLS': 'followers',
        'CONTACT': 'contact',
        'BRAND': 'brand',
        'PIC': 'pic',
        'APPROVED BY RARA': 'pic',
        'AVG GMV/MONTH': 'avg_gmv_month',
        'GMV PER PEMBELI': 'gmv_per_pembeli',
        'UPDATE': 'update',
        'RESPON SPEED': 'respon_speed',
        'RESULT': 'result',
        'SAMPEL GRATIS': 'sampel_gratis',
        'NOTE': 'note',
        'NOTE DEAL': 'note_deal',
        'NOTE DARI RARA': 'note_deal',
        'TOTAL VT': 'total_vt',
        'GMV PERBULAN AFTER JOIN': 'gmv_perbulan',
    }

    _INT_FIELDS = {'followers', 'total_vt'}
    _FLOAT_FIELDS = {'avg_gmv_month', 'gmv_per_pembeli', 'gmv_perbulan'}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def auto_map(self, file_columns: list[str]) -> dict[str, str]:
        """
        Coba mapping otomatis berdasarkan kesamaan nama kolom.
        Strategi: exact match (case-insensitive, strip) dulu, lalu partial match.
        Return dict {nama_kolom_file: field_standar}.
        """
        result: dict[str, str] = {}
        already_mapped: set[str] = set()

        # Pass 1: exact match
        for col in file_columns:
            col_upper = col.strip().upper()
            if col_upper in self._REFERENCE_MAP:
                field_name = self._REFERENCE_MAP[col_upper]
                if field_name not in already_mapped:
                    result[col] = field_name
                    already_mapped.add(field_name)

        # Pass 2: partial match untuk kolom yang belum ter-mapping
        for col in file_columns:
            if col in result:
                continue
            col_upper = col.strip().upper()
            for ref_col, field_name in self._REFERENCE_MAP.items():
                if field_name in already_mapped:
                    continue
                if ref_col in col_upper or col_upper in ref_col:
                    result[col] = field_name
                    already_mapped.add(field_name)
                    break

        return result

    def apply_mapping(
        self,
        rows: list[dict],
        mapping: dict[str, str],
        custom_columns: list[str],
    ) -> list[CreatorRow]:
        """
        Terapkan mapping ke raw rows (list of dict) dan hasilkan list CreatorRow.
        Bersifat idempotent — hasil sama jika dipanggil dua kali dengan input sama.
        """
        creator_rows: list[CreatorRow] = []

        for row in rows:
            kwargs: dict = {}

            # Isi field standar berdasarkan mapping
            for file_col, std_field in mapping.items():
                raw = row.get(file_col)
                value = DataParser._clean_value(raw)

                if value is not None:
                    if std_field in self._INT_FIELDS:
                        value = DataParser._to_int(value)
                    elif std_field in self._FLOAT_FIELDS:
                        value = DataParser._to_float(value)
                    else:
                        value = str(value)

                kwargs[std_field] = value

            # Isi custom_fields dari custom_columns
            custom: dict[str, str] = {}
            for col in custom_columns:
                raw = row.get(col)
                val = DataParser._clean_value(raw)
                custom[col] = str(val) if val is not None else ''

            kwargs['custom_fields'] = custom
            creator_rows.append(CreatorRow(**kwargs))

        return creator_rows

    def save_config(self, brand_id: int, config: ColumnConfig, db_session) -> None:
        """
        Simpan atau update ColumnConfig ke database (tabel column_configs).
        Jika sudah ada untuk brand_id, update. Jika belum, insert baru.
        """
        existing = db_session.query(ColumnConfigModel).filter_by(brand_id=brand_id).first()

        mappings_json = json.dumps(config.mappings, ensure_ascii=False)
        custom_cols_json = json.dumps(config.custom_columns, ensure_ascii=False)

        if existing:
            existing.mappings = mappings_json
            existing.custom_cols = custom_cols_json
        else:
            new_record = ColumnConfigModel(
                brand_id=brand_id,
                mappings=mappings_json,
                custom_cols=custom_cols_json,
            )
            db_session.add(new_record)

        db_session.commit()

    def load_config(self, brand_id: int, db_session) -> Optional[ColumnConfig]:
        """
        Load ColumnConfig dari database untuk brand_id tertentu.
        Return None jika tidak ada.
        """
        record = db_session.query(ColumnConfigModel).filter_by(brand_id=brand_id).first()
        if record is None:
            return None

        mappings = json.loads(record.mappings)
        custom_columns = json.loads(record.custom_cols)

        return ColumnConfig(
            brand_id=brand_id,
            mappings=mappings,
            custom_columns=custom_columns,
        )
