"""
Brand Importer — parse file Excel berisi SOW dan SKU per brand
dan import ke database Brand Profile.

Format file:
- Row 0: header (nama brand di kolom 2+)
- Row "LINK SKU AFFILIATE": berisi SKU/link per brand
- Row "SOW": berisi SOW per brand
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import openpyxl


def parse_brand_config_file(file_path: str) -> list[dict]:
    """
    Parse file Excel brand config.
    Return list of { name, sku_list, sow, affiliate_links }
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # Baris pertama berisi nama brand (kolom 2 ke kanan)
    header_row = rows[0]
    brand_names = []
    brand_col_indices = []
    for i, val in enumerate(header_row):
        if val and str(val).strip() and i >= 1:
            brand_names.append(str(val).strip())
            brand_col_indices.append(i)

    if not brand_names:
        return []

    # Inisialisasi data per brand
    brands = {name: {"name": name, "sku_list": [], "sow": "", "affiliate_links": []} for name in brand_names}

    # Scan baris untuk cari LINK SKU AFFILIATE dan SOW
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        row_label = str(row[0]).strip().upper()

        if 'LINK SKU' in row_label or 'SKU' in row_label:
            # Baris SKU/link affiliate
            for name, col_idx in zip(brand_names, brand_col_indices):
                if col_idx < len(row) and row[col_idx]:
                    cell_text = str(row[col_idx]).strip()
                    # Ekstrak SKU names dan links
                    sku_names = _extract_sku_names(cell_text)
                    links = _extract_urls(cell_text)
                    brands[name]["sku_list"].extend(sku_names)
                    brands[name]["affiliate_links"].extend(links)

        elif 'SOW' in row_label:
            # Baris SOW
            for name, col_idx in zip(brand_names, brand_col_indices):
                if col_idx < len(row) and row[col_idx]:
                    brands[name]["sow"] = str(row[col_idx]).strip()

    return list(brands.values())


def _extract_sku_names(text: str) -> list[str]:
    """Ekstrak nama produk dari teks SKU."""
    skus = []
    # Cari pola: "1. Nama Produk" atau "- Nama Produk"
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        # Skip baris yang hanya berisi URL atau kosong
        if not line or line.startswith('http') or line.startswith('Link:') or line.startswith('Harga'):
            continue
        # Hapus nomor di awal (1., 2., -)
        cleaned = re.sub(r'^[\d]+\.\s*', '', line)
        cleaned = re.sub(r'^[-•]\s*', '', cleaned)
        # Hapus URL inline
        cleaned = re.sub(r'https?://\S+', '', cleaned).strip()
        if cleaned and len(cleaned) > 5:
            skus.append(cleaned)
    return skus[:5]  # Max 5 SKU per brand


def _extract_urls(text: str) -> list[str]:
    """Ekstrak semua URL dari teks."""
    return re.findall(r'https?://\S+', text)


def import_brands_to_db(file_path: str, db_session, brand_service) -> dict:
    """
    Import brand data dari file ke database.
    Return { imported: int, updated: int, errors: list }
    """
    brands_data = parse_brand_config_file(file_path)
    imported = 0
    updated = 0
    errors = []

    for brand_data in brands_data:
        name = brand_data["name"]
        if not name:
            continue
        try:
            existing = brand_service.get_by_name(name, db_session)
            if existing:
                # Update SKU dan SOW jika ada data baru
                if brand_data["sku_list"]:
                    brand_service.update_sku_list(existing.id, brand_data["sku_list"], db_session)
                if brand_data["sow"]:
                    brand_service.update_sow(existing.id, brand_data["sow"], db_session)
                updated += 1
            else:
                from app.services.brand_profile import BrandProfileData
                profile = BrandProfileData(
                    name=name,
                    sku_list=brand_data["sku_list"],
                    sow=brand_data["sow"],
                )
                brand_service.save(profile, db_session)
                imported += 1
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    return {"imported": imported, "updated": updated, "errors": errors}
