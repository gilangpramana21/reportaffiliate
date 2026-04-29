"""
Brand Profile & Column Mapping endpoints.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict

from flask import Blueprint, jsonify, request

from app.models.db import BrandProfile, ColumnConfig, db
from app.services.brand_profile import BrandProfileService
from app.services.column_mapper import ColumnConfig as ColumnConfigData, ColumnMapper
from app.routes.upload import _parse_cache

brands_bp = Blueprint("brands", __name__, url_prefix="/api")

# Persistent mapping cache — disimpan ke disk
_MAPPING_CACHE_FILE = "uploads/.mapping_cache.json"

def _load_mapping_cache() -> dict:
    try:
        if os.path.exists(_MAPPING_CACHE_FILE):
            with open(_MAPPING_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_mapping_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(_MAPPING_CACHE_FILE), exist_ok=True)
        # Keep only last 30 entries to prevent unbounded growth
        keys = list(cache.keys())
        if len(keys) > 30:
            for old_key in keys[:-30]:
                cache.pop(old_key, None)
        with open(_MAPPING_CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass

_mapping_cache: dict = _load_mapping_cache()

_brand_service = BrandProfileService()
_column_mapper = ColumnMapper()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _brand_to_dict(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "sku_list": profile.sku_list,
        "sow": profile.sow,
        "has_column_config": profile.has_column_config,
    }


def _brand_to_dict_full(profile, column_config=None) -> dict:
    d = _brand_to_dict(profile)
    if column_config is not None:
        d["column_config"] = {
            "mappings": column_config.mappings,
            "custom_columns": column_config.custom_columns,
        }
    else:
        d["column_config"] = None
    return d


# ---------------------------------------------------------------------------
# Brand Profile endpoints
# ---------------------------------------------------------------------------

@brands_bp.route("/brands", methods=["GET"])
def list_brands():
    profiles = _brand_service.list_all(db.session)
    return jsonify([_brand_to_dict(p) for p in profiles]), 200


@brands_bp.route("/brands/<brand_name>", methods=["GET"])
def get_brand(brand_name: str):
    profile = _brand_service.get_by_name(brand_name, db.session)
    if profile is None:
        return jsonify({"error": f"Brand '{brand_name}' tidak ditemukan"}), 404

    # Load column config jika ada
    col_config = None
    if profile.has_column_config and profile.id is not None:
        col_config = _column_mapper.load_config(profile.id, db.session)

    return jsonify(_brand_to_dict_full(profile, col_config)), 200


@brands_bp.route("/brands", methods=["POST"])
def create_brand():
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "Field 'name' wajib diisi"}), 400

    sku_list = body.get("sku_list", [])
    sow = body.get("sow", "")

    if not isinstance(sku_list, list):
        return jsonify({"error": "Field 'sku_list' harus berupa array"}), 400

    # Cek duplikat
    existing = _brand_service.get_by_name(name, db.session)
    if existing is not None:
        return jsonify({"error": f"Brand '{name}' sudah ada"}), 409

    from app.services.brand_profile import BrandProfileData
    profile_data = BrandProfileData(name=name, sku_list=sku_list, sow=sow)
    saved = _brand_service.save(profile_data, db.session)

    return jsonify({"brand_profile": _brand_to_dict(saved)}), 201


@brands_bp.route("/brands/<int:brand_id>", methods=["PUT"])
def update_brand(brand_id: int):
    body = request.get_json(silent=True) or {}

    profile = _brand_service.get_by_id(brand_id, db.session)
    if profile is None:
        return jsonify({"error": f"Brand dengan id={brand_id} tidak ditemukan"}), 404

    if "sku_list" in body:
        sku_list = body["sku_list"]
        if not isinstance(sku_list, list):
            return jsonify({"error": "Field 'sku_list' harus berupa array"}), 400
        _brand_service.update_sku_list(brand_id, sku_list, db.session)

    if "sow" in body:
        _brand_service.update_sow(brand_id, str(body["sow"]), db.session)

    updated = _brand_service.get_by_id(brand_id, db.session)
    return jsonify({"brand_profile": _brand_to_dict(updated)}), 200


@brands_bp.route("/brands/<int:brand_id>", methods=["DELETE"])
def delete_brand(brand_id: int):
    profile = _brand_service.get_by_id(brand_id, db.session)
    if profile is None:
        return jsonify({"error": f"Brand dengan id={brand_id} tidak ditemukan"}), 404

    _brand_service.delete(brand_id, db.session)
    return "", 204


# ---------------------------------------------------------------------------
# Column Mapping endpoints
# ---------------------------------------------------------------------------

@brands_bp.route("/mapping", methods=["POST"])
def apply_mapping():
    body = request.get_json(silent=True) or {}

    parse_id = body.get("parse_id", "")
    brand_name = body.get("brand_name", "").strip()
    mappings = body.get("mappings", {})
    custom_columns = body.get("custom_columns", [])
    save_config = bool(body.get("save_config", False))

    if not parse_id:
        return jsonify({"error": "Field 'parse_id' wajib diisi"}), 400
    if not brand_name:
        return jsonify({"error": "Field 'brand_name' wajib diisi"}), 400
    if not isinstance(mappings, dict):
        return jsonify({"error": "Field 'mappings' harus berupa object"}), 400
    if not isinstance(custom_columns, list):
        return jsonify({"error": "Field 'custom_columns' harus berupa array"}), 400

    # Ambil ParseResult dari cache
    parse_result = _parse_cache.get(parse_id)
    if parse_result is None:
        return jsonify({"error": f"parse_id '{parse_id}' tidak ditemukan"}), 404

    # DataParser sudah menghasilkan CreatorRow — simpan langsung ke mapping_cache
    # apply_mapping hanya dipakai jika ada custom re-mapping dari user
    # Untuk sekarang, gunakan rows yang sudah di-parse langsung
    mapped_deal = parse_result.deal_rows
    mapped_non_deal = parse_result.non_deal_rows

    # Simpan ColumnConfig ke database jika diminta
    if save_config:
        profile = _brand_service.get_or_create(brand_name, db.session)
        if profile.id is not None:
            config = ColumnConfigData(
                brand_id=profile.id,
                mappings=mappings,
                custom_columns=custom_columns,
            )
            _column_mapper.save_config(profile.id, config, db.session)

    # Simpan hasil mapping ke _mapping_cache (persistent)
    mapping_id = uuid.uuid4().hex
    mapping_data = {
        "brand_name": brand_name,
        "deal_rows": [asdict(r) for r in mapped_deal],
        "non_deal_rows": [asdict(r) for r in mapped_non_deal],
    }
    
    # Tambahkan template info jika tersedia dari parse result
    if hasattr(parse_result, 'template_info') and parse_result.template_info:
        mapping_data["template_info"] = {
            "template_type": parse_result.template_info.template_type,
            "confidence": parse_result.template_info.confidence,
            "multi_video_support": parse_result.template_info.multi_video_support,
            "video_columns": parse_result.template_info.video_columns,
            "parsing_strategy": parse_result.template_info.parsing_strategy,
        }
    
    _mapping_cache[mapping_id] = mapping_data
    _save_mapping_cache(_mapping_cache)

    applied_rows_count = len(mapped_deal) + len(mapped_non_deal)

    return jsonify({
        "mapping_id": mapping_id,
        "applied_rows_count": applied_rows_count,
    }), 200


@brands_bp.route("/brands/import", methods=["POST"])
def import_brands():
    """
    Upload file Excel berisi SOW dan SKU per brand untuk di-import ke database.
    Body: multipart/form-data { file }
    """
    import os, uuid
    from flask import current_app
    from app.services.brand_importer import import_brands_to_db

    if "file" not in request.files:
        return jsonify({"error": "Tidak ada file yang dikirim"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "Hanya file Excel (.xlsx/.xls) yang didukung"}), 400

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    tmp_path = os.path.join(upload_folder, f"brand_config_{uuid.uuid4().hex}.xlsx")
    file.save(tmp_path)

    try:
        result = import_brands_to_db(tmp_path, db.session, _brand_service)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@brands_bp.route("/mapping/<mapping_id>/creators", methods=["GET"])
def get_mapping_creators(mapping_id: str):
    """Return daftar username + video_links dari deal_rows untuk scraping engagement."""
    mapping_data = _mapping_cache.get(mapping_id)
    if mapping_data is None:
        return jsonify({"error": f"mapping_id '{mapping_id}' tidak ditemukan"}), 404

    import re as _re
    def _clean_url(url: str) -> str:
        url = url.strip()
        if ',' in url:
            url = url.split(',')[0].strip()
        url = url.rstrip('.,;: ')
        return url

    def _is_valid_tiktok_url(url: str) -> bool:
        return bool(url) and 'tiktok.com' in url.lower() and url.startswith('http')

    creators = []
    video_links_map = {}
    total_with_links = 0
    template_info = mapping_data.get("template_info")

    for row in mapping_data["deal_rows"]:
        username = row.get("username") or ""
        if not username:
            continue
        raw_links = row.get("video_links") or []
        clean_links = []
        seen = set()
        for link in raw_links:
            cleaned = _clean_url(str(link))
            if _is_valid_tiktok_url(cleaned) and cleaned not in seen:
                clean_links.append(cleaned)
                seen.add(cleaned)

        creators.append({"username": username, "has_video_links": len(clean_links) > 0,
                         "video_count": len(clean_links)})
        if clean_links:
            video_links_map[username] = clean_links
            total_with_links += 1

    # STALE MAPPING DETECTION
    # Check if this is a stale mapping (has deal_rows but no video_links)
    is_stale_mapping = False
    original_file_path = None
    file_exists = False
    
    if len(mapping_data["deal_rows"]) > 0 and total_with_links == 0:
        # This mapping has creators but no video links - likely stale
        is_stale_mapping = True
        
        # Try to find the original file path from file_path_cache
        from app.routes.upload import _file_path_cache
        
        # Search for matching parse_id by comparing row counts
        n_rows = len(mapping_data["deal_rows"])
        for pid, file_path in _file_path_cache.items():
            # Check if this parse_id might correspond to this mapping
            # (heuristic: same number of rows)
            from app.routes.upload import _parse_cache
            parse_data = _parse_cache.get(pid)
            if parse_data and len(parse_data.deal_rows) == n_rows:
                original_file_path = file_path
                file_exists = __import__('os').path.exists(file_path)
                break

    # Jika tidak ada video links sama sekali, coba re-parse dari file asli
    # (Keep existing auto-recovery logic for backward compatibility)
    if total_with_links == 0 and creators and not is_stale_mapping:
        try:
            from app.routes.upload import _file_path_cache, _parse_cache, _save_parse_cache
            from app.services.data_parser import DataParser
            from dataclasses import asdict

            # Cari parse_id yang menghasilkan mapping ini
            # Coba semua parse cache yang punya jumlah rows sama
            n_rows = len(mapping_data["deal_rows"])
            for pid, parse_data in _parse_cache.items():
                if len(parse_data.deal_rows) == n_rows:
                    file_path = _file_path_cache.get(pid)
                    if file_path and __import__('os').path.exists(file_path):
                        import sys
                        print(f"[MAPPING] Re-parsing {file_path} to recover video links", file=sys.stderr)
                        parser = DataParser()
                        result = parser.parse(file_path)
                        link_lookup = {r.username: r.video_links for r in result.deal_rows if r.username}

                        # Update mapping cache với template info
                        for row in mapping_data["deal_rows"]:
                            u = row.get("username", "")
                            if u and u in link_lookup:
                                row["video_links"] = link_lookup[u]
                        
                        # Simpan template info ke mapping cache
                        if result.template_info:
                            mapping_data["template_info"] = {
                                "template_type": result.template_info.template_type,
                                "confidence": result.template_info.confidence,
                                "multi_video_support": result.template_info.multi_video_support,
                                "video_columns": result.template_info.video_columns,
                                "parsing_strategy": result.template_info.parsing_strategy,
                            }

                        # Update parse cache
                        parse_data_new = {
                            'deal_rows': [asdict(r) for r in result.deal_rows],
                            'non_deal_rows': [asdict(r) for r in result.non_deal_rows],
                            'detected_columns': result.detected_columns,
                            'errors': result.errors,
                        }
                        _parse_cache[pid] = __import__('app.services.data_parser', fromlist=['ParseResult']).ParseResult(
                            deal_rows=result.deal_rows,
                            non_deal_rows=result.non_deal_rows,
                            detected_columns=result.detected_columns,
                            errors=result.errors,
                            template_info=result.template_info,
                        )
                        _save_parse_cache(_parse_cache)
                        _save_mapping_cache(_mapping_cache)

                        # Rebuild video_links_map
                        video_links_map = {}
                        for row in mapping_data["deal_rows"]:
                            u = row.get("username", "")
                            links = [_clean_url(l) for l in (row.get("video_links") or []) if _is_valid_tiktok_url(_clean_url(l))]
                            if links:
                                video_links_map[u] = links
                        break
        except Exception as e:
            import sys
            print(f"[MAPPING] Auto re-parse failed: {e}", file=sys.stderr)

    response_data = {
        "creators": creators,
        "video_links_map": video_links_map,
        "has_specific_links": len(video_links_map) > 0,
    }
    
    # Add stale mapping detection flags
    if is_stale_mapping:
        response_data["is_stale_mapping"] = True
        response_data["original_file_path"] = original_file_path
        response_data["file_exists"] = file_exists
    
    # Tambahkan informasi template jika tersedia
    if template_info:
        response_data["template_info"] = template_info
    
    return jsonify(response_data), 200


@brands_bp.route("/brands/<brand_name>/column-config", methods=["GET"])
def get_column_config(brand_name: str):
    profile = _brand_service.get_by_name(brand_name, db.session)
    if profile is None:
        return jsonify({"error": f"Brand '{brand_name}' tidak ditemukan"}), 404

    if not profile.has_column_config or profile.id is None:
        return jsonify({"error": f"Column config untuk brand '{brand_name}' tidak ditemukan"}), 404

    col_config = _column_mapper.load_config(profile.id, db.session)
    if col_config is None:
        return jsonify({"error": f"Column config untuk brand '{brand_name}' tidak ditemukan"}), 404

    return jsonify({
        "column_config": {
            "mappings": col_config.mappings,
            "custom_columns": col_config.custom_columns,
        }
    }), 200


@brands_bp.route("/mapping/<mapping_id>/reparse", methods=["POST"])
def reparse_mapping(mapping_id: str):
    """
    Re-parse the original Excel file to extract video links for a stale mapping.
    
    This endpoint:
    1. Validates mapping_id exists
    2. Retrieves original file path from file_path_cache
    3. Checks if file exists in uploads/
    4. If file missing: returns 404 with clear error message
    5. If file exists: clears stale mapping, re-parses file, re-applies mapping, returns new mapping_id
    """
    import os
    import uuid
    from dataclasses import asdict
    from app.services.data_parser import DataParser
    from app.routes.upload import _file_path_cache, _parse_cache, _save_parse_cache
    
    # Step 1: Validate mapping_id exists
    mapping_data = _mapping_cache.get(mapping_id)
    if mapping_data is None:
        return jsonify({
            "success": False,
            "error": f"mapping_id '{mapping_id}' tidak ditemukan"
        }), 404
    
    # Step 2: Find original file path
    # Search for matching parse_id by comparing row counts (heuristic)
    n_rows = len(mapping_data.get("deal_rows", []))
    brand_name = mapping_data.get("brand_name", "")
    
    original_file_path = None
    matching_parse_id = None
    
    for pid, file_path in _file_path_cache.items():
        # Check if this parse_id might correspond to this mapping
        parse_data = _parse_cache.get(pid)
        if parse_data and len(parse_data.deal_rows) == n_rows:
            original_file_path = file_path
            matching_parse_id = pid
            break
    
    if not original_file_path:
        return jsonify({
            "success": False,
            "error": "File Excel asli tidak ditemukan di cache. Silakan upload ulang file Excel Anda.",
            "suggestion": "Gunakan halaman Upload untuk upload file Excel baru."
        }), 404
    
    # Step 3: Check if file exists
    if not os.path.exists(original_file_path):
        return jsonify({
            "success": False,
            "error": "File Excel asli tidak ditemukan. Silakan upload ulang file Excel Anda.",
            "original_path": original_file_path,
            "suggestion": "File mungkin sudah dihapus dari server. Gunakan halaman Upload untuk upload file Excel baru."
        }), 404
    
    # Step 4: Re-parse file
    try:
        import sys
        print(f"[REPARSE] Re-parsing {original_file_path} for mapping {mapping_id}", file=sys.stderr)
        
        parser = DataParser()
        
        # Enable video extraction for re-parse
        os.environ.pop('SKIP_VIDEO_EXTRACTION', None)
        
        result = parser.parse(original_file_path)
        
        print(f"[REPARSE] Parse completed: {len(result.deal_rows)} deal rows", file=sys.stderr)
        
        # Count video links extracted
        video_links_count = sum(
            len(row.video_links) for row in result.deal_rows if row.video_links
        )
        
        print(f"[REPARSE] Extracted {video_links_count} video links", file=sys.stderr)
        
    except Exception as exc:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[REPARSE] Parse failed: {exc}\n{error_detail}", file=sys.stderr)
        return jsonify({
            "success": False,
            "error": f"Gagal re-parse file: {exc}",
            "detail": str(exc)
        }), 500
    
    # Step 5: Clear stale mapping from cache
    if mapping_id in _mapping_cache:
        del _mapping_cache[mapping_id]
        _save_mapping_cache(_mapping_cache)
        print(f"[REPARSE] Cleared stale mapping {mapping_id}", file=sys.stderr)
    
    # Step 6: Update parse cache with new result
    if matching_parse_id:
        _parse_cache[matching_parse_id] = result
        _save_parse_cache(_parse_cache)
    
    # Step 7: Create new mapping with video links
    new_mapping_id = uuid.uuid4().hex
    new_mapping_data = {
        "brand_name": brand_name,
        "deal_rows": [asdict(r) for r in result.deal_rows],
        "non_deal_rows": [asdict(r) for r in result.non_deal_rows],
    }
    
    # Add template info if available
    if result.template_info:
        new_mapping_data["template_info"] = {
            "template_type": result.template_info.template_type,
            "confidence": result.template_info.confidence,
            "multi_video_support": result.template_info.multi_video_support,
            "video_columns": result.template_info.video_columns,
            "parsing_strategy": result.template_info.parsing_strategy,
        }
    
    _mapping_cache[new_mapping_id] = new_mapping_data
    _save_mapping_cache(_mapping_cache)
    
    print(f"[REPARSE] Created new mapping {new_mapping_id} with {video_links_count} video links", file=sys.stderr)
    
    # Step 8: Return success response
    return jsonify({
        "success": True,
        "new_mapping_id": new_mapping_id,
        "video_links_count": video_links_count,
        "message": f"File berhasil di-parse ulang. Ditemukan {video_links_count} video links.",
        "brand_name": brand_name
    }), 200


@brands_bp.route("/mapping/latest", methods=["GET"])
def get_latest_mapping():
    """Return mapping_id terbaru yang tersimpan di cache."""
    if not _mapping_cache:
        return jsonify({"error": "Tidak ada mapping tersimpan"}), 404
    latest_id = list(_mapping_cache.keys())[-1]
    data = _mapping_cache[latest_id]
    return jsonify({
        "mapping_id": latest_id,
        "brand_name": data.get("brand_name", ""),
        "deal_row_count": len(data.get("deal_rows", [])),
    }), 200


@brands_bp.route("/mapping/list", methods=["GET"])
def list_mappings():
    """Return semua mapping yang tersimpan (untuk batch generate)."""
    result = []
    for mid, data in _mapping_cache.items():
        result.append({
            "mapping_id": mid,
            "brand_name": data.get("brand_name", ""),
            "deal_row_count": len(data.get("deal_rows", [])),
        })
    # Sort by most recent (last in dict)
    result.reverse()
    return jsonify({"mappings": result}), 200


@brands_bp.route("/mapping/clear-cache", methods=["POST"])
def clear_mapping_cache():
    """
    Clear mapping cache only.
    Useful when you want to re-apply mappings without re-uploading files.
    """
    global _mapping_cache
    
    count = len(_mapping_cache)
    _mapping_cache.clear()
    
    try:
        if os.path.exists(_MAPPING_CACHE_FILE):
            os.remove(_MAPPING_CACHE_FILE)
            return jsonify({
                "success": True,
                "message": f"Mapping cache cleared: {count} entries removed",
                "cleared_count": count
            }), 200
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Failed to clear mapping cache: {exc}",
            "cleared_count": count
        }), 500


@brands_bp.route("/template/analyze", methods=["POST"])
def analyze_template():
    """
    Analisis template Excel dan berikan rekomendasi.
    Body: { parse_id }
    """
    body = request.get_json(silent=True) or {}
    parse_id = body.get("parse_id", "")
    
    if not parse_id:
        return jsonify({"error": "Field 'parse_id' wajib diisi"}), 400
    
    # Ambil ParseResult dari cache
    parse_result = _parse_cache.get(parse_id)
    if parse_result is None:
        return jsonify({"error": f"parse_id '{parse_id}' tidak ditemukan"}), 404
    
    if not hasattr(parse_result, 'template_info') or not parse_result.template_info:
        return jsonify({"error": "Template info tidak tersedia"}), 404
    
    template_info = parse_result.template_info
    
    # Gunakan template detector untuk mendapatkan rekomendasi
    from app.services.template_detector import TemplateDetector
    detector = TemplateDetector()
    
    recommendations = detector.get_parsing_recommendations(template_info)
    suggestions = detector.suggest_template_improvements(template_info)
    
    return jsonify({
        "template_info": {
            "template_type": template_info.template_type,
            "confidence": template_info.confidence,
            "multi_video_support": template_info.multi_video_support,
            "video_columns": template_info.video_columns,
            "special_features": template_info.special_features,
            "parsing_strategy": template_info.parsing_strategy,
        },
        "recommendations": recommendations,
        "suggestions": suggestions,
        "compatibility": {
            "single_video": True,
            "multi_video": template_info.multi_video_support,
            "collapsible_table": template_info.multi_video_support,
            "engagement_scraping": len(template_info.video_columns) > 0,
        }
    }), 200


# ---------------------------------------------------------------------------
# Brand Alias Management Endpoints (Multi-Brand Detection Compatible)
# ---------------------------------------------------------------------------

@brands_bp.route("/brand-aliases", methods=["GET"])
def list_brand_aliases():
    """List all brand aliases grouped by canonical name"""
    try:
        from app.models.db import BrandAlias
        
        # Group aliases by canonical name
        aliases_query = db.session.query(BrandAlias).order_by(BrandAlias.canonical_name, BrandAlias.alias_name).all()
        
        # Group by canonical name
        grouped_aliases = {}
        for alias in aliases_query:
            canonical = alias.canonical_name
            if canonical not in grouped_aliases:
                grouped_aliases[canonical] = {
                    'canonical_name': canonical,
                    'aliases': [],
                    'similarity_scores': []
                }
            grouped_aliases[canonical]['aliases'].append(alias.alias_name)
            grouped_aliases[canonical]['similarity_scores'].append(alias.similarity_score)
        
        return jsonify(list(grouped_aliases.values())), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brand-aliases", methods=["POST"])
def create_brand_alias():
    """Create brand aliases for a canonical name"""
    try:
        body = request.get_json(silent=True) or {}
        
        canonical_name = body.get("canonical_name", "").strip()
        aliases = body.get("aliases", [])
        similarity_threshold = body.get("similarity_threshold", 0.8)
        
        if not canonical_name:
            return jsonify({"error": "canonical_name is required"}), 400
        
        if not aliases or not isinstance(aliases, list):
            return jsonify({"error": "aliases must be a non-empty list"}), 400
        
        from app.models.db import BrandAlias
        
        # Remove existing aliases for this canonical name
        db.session.query(BrandAlias).filter_by(canonical_name=canonical_name).delete()
        
        # Add new aliases
        for alias_name in aliases:
            if alias_name.strip():
                new_alias = BrandAlias(
                    canonical_name=canonical_name,
                    alias_name=alias_name.strip(),
                    similarity_score=similarity_threshold
                )
                db.session.add(new_alias)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "canonical_name": canonical_name,
            "aliases_count": len(aliases)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brand-aliases/<canonical_name>", methods=["PUT"])
def update_brand_alias(canonical_name: str):
    """Update aliases for a canonical brand name"""
    try:
        body = request.get_json(silent=True) or {}
        aliases = body.get("aliases", [])
        
        if not isinstance(aliases, list):
            return jsonify({"error": "aliases must be a list"}), 400
        
        from app.models.db import BrandAlias
        
        # Remove existing aliases for this canonical name
        db.session.query(BrandAlias).filter_by(canonical_name=canonical_name).delete()
        
        # Add updated aliases
        for alias_name in aliases:
            if alias_name.strip():
                new_alias = BrandAlias(
                    canonical_name=canonical_name,
                    alias_name=alias_name.strip(),
                    similarity_score=0.8  # Default similarity
                )
                db.session.add(new_alias)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "canonical_name": canonical_name,
            "aliases_count": len(aliases)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brand-aliases/<canonical_name>", methods=["DELETE"])
def delete_brand_alias(canonical_name: str):
    """Delete all aliases for a canonical brand name"""
    try:
        from app.models.db import BrandAlias
        
        deleted_count = db.session.query(BrandAlias).filter_by(canonical_name=canonical_name).delete()
        db.session.commit()
        
        if deleted_count == 0:
            return jsonify({"error": "No aliases found for this brand"}), 404
        
        return "", 204
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brand-aliases/suggestions", methods=["GET"])
def get_alias_suggestions():
    """Get suggestions for similar brand names that could be aliases"""
    try:
        from app.services.brand_normalizer import BrandNormalizer
        
        # Get all existing brand names from brand profiles
        profiles = _brand_service.list_all(db.session)
        brand_names = [p.name for p in profiles]
        
        # Use BrandNormalizer to find similar brands
        normalizer = BrandNormalizer()
        suggestions = normalizer.suggest_similar_brands(brand_names)
        
        # Format suggestions for frontend
        formatted_suggestions = []
        for brand1, brand2, similarity in suggestions:
            formatted_suggestions.append({
                "brand1": brand1,
                "brand2": brand2,
                "similarity": similarity
            })
        
        return jsonify({
            "suggestions": formatted_suggestions
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brand-aliases/apply-suggestions", methods=["POST"])
def apply_alias_suggestions():
    """Apply selected alias suggestions"""
    try:
        body = request.get_json(silent=True) or {}
        suggestions = body.get("suggestions", [])
        
        if not isinstance(suggestions, list):
            return jsonify({"error": "suggestions must be a list"}), 400
        
        from app.models.db import BrandAlias
        
        applied_count = 0
        
        for suggestion in suggestions:
            canonical_name = suggestion.get("canonical_name", "").strip()
            alias_name = suggestion.get("alias_name", "").strip()
            
            if canonical_name and alias_name:
                # Check if alias already exists
                existing = db.session.query(BrandAlias).filter_by(
                    canonical_name=canonical_name,
                    alias_name=alias_name
                ).first()
                
                if not existing:
                    new_alias = BrandAlias(
                        canonical_name=canonical_name,
                        alias_name=alias_name,
                        similarity_score=0.8  # Default similarity
                    )
                    db.session.add(new_alias)
                    applied_count += 1
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "applied": applied_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route("/brands/aliases", methods=["GET"])
def get_aliases():
    """Get all brand aliases (frontend-compatible endpoint)"""
    try:
        from app.models.db import BrandAlias
        
        aliases = db.session.query(BrandAlias).all()
        
        return jsonify({
            "success": True,
            "aliases": [{
                "id": alias.id,
                "canonical_brand": alias.canonical_name,
                "alias": alias.alias_name,
                "confidence_score": alias.similarity_score,
                "created_at": alias.created_at.isoformat() if alias.created_at else None
            } for alias in aliases]
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brands_bp.route("/brands/aliases", methods=["POST"])
def add_alias():
    """Add a new brand alias (frontend-compatible endpoint)"""
    try:
        body = request.get_json(silent=True) or {}
        
        canonical_brand = body.get("canonical_brand", "").strip()
        alias = body.get("alias", "").strip()
        confidence_score = body.get("confidence_score", 1.0)
        
        if not canonical_brand or not alias:
            return jsonify({
                "success": False,
                "error": "canonical_brand and alias are required"
            }), 400
        
        from app.models.db import BrandAlias
        
        # Check if alias already exists
        existing = db.session.query(BrandAlias).filter_by(
            canonical_name=canonical_brand,
            alias_name=alias
        ).first()
        
        if existing:
            return jsonify({
                "success": False,
                "error": "This alias already exists"
            }), 409
        
        # Create new alias
        new_alias = BrandAlias(
            canonical_name=canonical_brand,
            alias_name=alias,
            similarity_score=confidence_score
        )
        
        db.session.add(new_alias)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "alias": {
                "id": new_alias.id,
                "canonical_brand": new_alias.canonical_name,
                "alias": new_alias.alias_name,
                "confidence_score": new_alias.similarity_score
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brands_bp.route("/brands/aliases/<int:alias_id>", methods=["PUT"])
def update_alias(alias_id):
    """Update a brand alias (frontend-compatible endpoint)"""
    try:
        from app.models.db import BrandAlias
        
        alias = db.session.query(BrandAlias).get(alias_id)
        if not alias:
            return jsonify({
                "success": False,
                "error": "Alias not found"
            }), 404
        
        body = request.get_json(silent=True) or {}
        
        canonical_brand = body.get("canonical_brand", "").strip()
        alias_name = body.get("alias", "").strip()
        confidence_score = body.get("confidence_score")
        
        if not canonical_brand or not alias_name:
            return jsonify({
                "success": False,
                "error": "canonical_brand and alias are required"
            }), 400
        
        alias.canonical_name = canonical_brand
        alias.alias_name = alias_name
        if confidence_score is not None:
            alias.similarity_score = confidence_score
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "alias": {
                "id": alias.id,
                "canonical_brand": alias.canonical_name,
                "alias": alias.alias_name,
                "confidence_score": alias.similarity_score
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brands_bp.route("/brands/aliases/<int:alias_id>", methods=["DELETE"])
def delete_alias(alias_id):
    """Delete a brand alias (frontend-compatible endpoint)"""
    try:
        from app.models.db import BrandAlias
        
        alias = db.session.query(BrandAlias).get(alias_id)
        if not alias:
            return jsonify({
                "success": False,
                "error": "Alias not found"
            }), 404
        
        db.session.delete(alias)
        db.session.commit()
        
        return jsonify({
            "success": True
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brands_bp.route("/brands/aliases/group/<canonical_brand>", methods=["DELETE"])
def delete_alias_group(canonical_brand):
    """Delete all aliases for a canonical brand (frontend-compatible endpoint)"""
    try:
        from app.models.db import BrandAlias
        
        aliases = db.session.query(BrandAlias).filter_by(canonical_name=canonical_brand).all()
        if not aliases:
            return jsonify({
                "success": False,
                "error": "No aliases found for this brand"
            }), 404
        
        for alias in aliases:
            db.session.delete(alias)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "deleted_count": len(aliases)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
