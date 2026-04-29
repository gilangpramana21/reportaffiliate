"""
Upload & Parsing endpoints.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, fields as dc_fields
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from app.services.data_parser import DataParser, ParseResult, UnsupportedFormatError, CreatorRow
from app.services.multi_brand_detector import MultiBrandDetector
from app.services.brand_normalizer import BrandNormalizer
from app.services.brand_grouper import BrandGrouper
from app.services.brand_ui_models import BrandUIDataBuilder

upload_bp = Blueprint("upload", __name__, url_prefix="/api")

_PARSE_CACHE_FILE = "uploads/.parse_cache.json"
_FILE_PATH_CACHE_FILE = "uploads/.file_path_cache.json"

# Valid field names for CreatorRow — used for safe deserialization
_CREATOR_ROW_FIELDS = {f.name for f in dc_fields(CreatorRow)}


def _safe_creator_row(d: dict) -> CreatorRow:
    """Deserialize dict to CreatorRow, ignoring unknown fields and filling missing ones."""
    filtered = {k: v for k, v in d.items() if k in _CREATOR_ROW_FIELDS}
    return CreatorRow(**filtered)


def _load_parse_cache() -> dict:
    try:
        if os.path.exists(_PARSE_CACHE_FILE):
            with open(_PARSE_CACHE_FILE, 'r') as f:
                raw = json.load(f)
            result = {}
            for k, v in raw.items():
                try:
                    deal = [_safe_creator_row(r) for r in v.get('deal_rows', [])]
                    non_deal = [_safe_creator_row(r) for r in v.get('non_deal_rows', [])]
                    result[k] = ParseResult(
                        deal_rows=deal,
                        non_deal_rows=non_deal,
                        detected_columns=v.get('detected_columns', []),
                        errors=v.get('errors', [])
                    )
                except Exception:
                    continue  # skip corrupted entries
            return result
    except Exception:
        pass
    return {}


def _save_parse_cache(cache: dict):
    try:
        os.makedirs("uploads", exist_ok=True)
        # Keep only last 10 entries (reduced from 20 for faster saving)
        keys = list(cache.keys())
        if len(keys) > 10:
            for old_key in keys[:-10]:
                cache.pop(old_key, None)
        serializable = {}
        for k, v in cache.items():
            try:
                # Only save first 50 rows for faster serialization
                # Full data is still in memory cache
                serializable[k] = {
                    'deal_rows': [asdict(r) for r in v.deal_rows[:50]],
                    'non_deal_rows': [asdict(r) for r in v.non_deal_rows[:50]],
                    'detected_columns': v.detected_columns,
                    'errors': v.errors,
                }
            except Exception:
                continue
        with open(_PARSE_CACHE_FILE, 'w') as f:
            json.dump(serializable, f, ensure_ascii=False)
    except Exception:
        pass


def _load_file_path_cache() -> dict:
    try:
        if os.path.exists(_FILE_PATH_CACHE_FILE):
            with open(_FILE_PATH_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_file_path_cache(cache: dict):
    try:
        os.makedirs("uploads", exist_ok=True)
        # Keep only last 20 entries
        keys = list(cache.keys())
        if len(keys) > 20:
            for old_key in keys[:-20]:
                cache.pop(old_key, None)
        with open(_FILE_PATH_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass


_parse_cache: dict = _load_parse_cache()
_file_path_cache: dict[str, str] = _load_file_path_cache()  # persistent now

_STANDARD_COLUMNS = [
    "TANGGAL", "USERNAME", "LINK ACC", "FOLLS", "CONTACT",
    "BRAND", "PIC", "AVG GMV/MONTH", "GMV PER PEMBELI",
    "UPDATE", "RESPON SPEED", "RESULT", "SAMPEL GRATIS", "NOTE",
]

_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".ods"}


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in _ALLOWED_EXTENSIONS


def _get_sheets(file_path: str) -> list:
    """Safely get sheet names from Excel file."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheets = list(wb.sheetnames)
        wb.close()
        return sheets
    except Exception:
        return []


@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Tidak ada file yang dikirim"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nama file kosong"}), 400

    if not _allowed_file(file.filename):
        ext = Path(file.filename).suffix.lower()
        return jsonify({
            "error": f"Format '{ext}' tidak didukung. "
                     f"Format yang diterima: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        }), 400

    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, unique_name)

    try:
        file.save(file_path)
    except Exception as exc:
        return jsonify({"error": f"Gagal menyimpan file: {exc}"}), 500

    try:
        import time
        start_time = time.time()
        
        parser = DataParser()
        
        # Skip video extraction during upload for faster processing
        # Video links will be extracted during report generation
        os.environ['SKIP_VIDEO_EXTRACTION'] = 'true'
        
        parse_start = time.time()
        result = parser.parse(file_path)
        parse_time = time.time() - parse_start
        
        # Reset environment variable
        os.environ.pop('SKIP_VIDEO_EXTRACTION', None)
        
        # Log parsing results for debugging
        import sys
        print(f"[UPLOAD] Parse completed in {parse_time:.2f}s: {len(result.deal_rows)} deal rows, {len(result.non_deal_rows)} non-deal rows", file=sys.stderr)
        if result.errors:
            print(f"[UPLOAD] Parse errors: {result.errors}", file=sys.stderr)
        
    except UnsupportedFormatError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback
        error_detail = traceback.format_exc()
        import sys
        print(f"[UPLOAD] Parse failed: {exc}\n{error_detail}", file=sys.stderr)
        return jsonify({
            "error": f"Gagal memproses file: {exc}",
            "detail": error_detail
        }), 500

    parse_id = uuid.uuid4().hex
    _parse_cache[parse_id] = result
    _file_path_cache[parse_id] = file_path
    # Save file path cache to disk for re-parse functionality
    _save_file_path_cache(_file_path_cache)

    available_sheets = _get_sheets(file_path) if ext in ('.xlsx', '.xls', '.ods') else []
    
    total_time = time.time() - start_time
    import sys
    print(f"[UPLOAD] Total upload time: {total_time:.2f}s (parse: {parse_time:.2f}s)", file=sys.stderr)
    
    # Add warning if no data found
    warnings = []
    if len(result.deal_rows) == 0 and len(result.non_deal_rows) == 0:
        warnings.append("Tidak ada data creator yang terdeteksi. Pastikan file memiliki kolom USERNAME dan BRAND.")
        if available_sheets:
            warnings.append(f"Sheet yang tersedia: {', '.join(available_sheets)}. Coba pilih sheet yang berbeda jika data tidak terdeteksi.")

    return jsonify({
        "parse_id": parse_id,
        "detected_columns": result.detected_columns,
        "deal_row_count": len(result.deal_rows),
        "non_deal_row_count": len(result.non_deal_rows),
        "errors": result.errors,
        "warnings": warnings,
        "available_sheets": available_sheets,
        "file_path": file_path,
    }), 200


@upload_bp.route("/parse/<parse_id>/select-sheet", methods=["POST"])
def select_sheet(parse_id: str):
    body = request.get_json(silent=True) or {}
    deal_sheet = body.get("deal_sheet", "")
    non_deal_sheet = body.get("non_deal_sheet", "")

    if _parse_cache.get(parse_id) is None:
        return jsonify({"error": f"parse_id '{parse_id}' tidak ditemukan"}), 404

    file_path = _file_path_cache.get(parse_id)
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File tidak ditemukan di server. Silakan upload ulang."}), 404

    try:
        parser = DataParser()
        if deal_sheet:
            parser.SHEET_DEAL = deal_sheet
        if non_deal_sheet:
            parser.SHEET_NON_DEAL = non_deal_sheet
        result = parser.parse(file_path)
    except Exception as exc:
        return jsonify({"error": f"Gagal parse sheet: {exc}"}), 500

    _parse_cache[parse_id] = result
    _save_parse_cache(_parse_cache)

    return jsonify({
        "parse_id": parse_id,
        "detected_columns": result.detected_columns,
        "deal_row_count": len(result.deal_rows),
        "non_deal_row_count": len(result.non_deal_rows),
        "errors": result.errors,
    }), 200


@upload_bp.route("/parse/<parse_id>/preview", methods=["GET"])
def parse_preview(parse_id: str):
    result = _parse_cache.get(parse_id)
    if result is None:
        return jsonify({"error": f"parse_id '{parse_id}' tidak ditemukan"}), 404

    sample_rows = [asdict(row) for row in result.deal_rows[:5]]
    detected_upper = {col.strip().upper() for col in result.detected_columns}
    missing_standard_columns = [
        col for col in _STANDARD_COLUMNS if col.upper() not in detected_upper
    ]

    return jsonify({
        "columns": result.detected_columns,
        "sample_rows": sample_rows,
        "missing_standard_columns": missing_standard_columns,
    }), 200


@upload_bp.route("/reparse", methods=["POST"])
def reparse_existing():
    body = request.get_json(silent=True) or {}
    file_name = body.get("file_name", "")
    deal_sheet = body.get("deal_sheet", "")

    if not file_name or not deal_sheet:
        return jsonify({"error": "file_name dan deal_sheet wajib diisi"}), 400

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = os.path.join(upload_folder, file_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File tidak ditemukan"}), 404

    try:
        parser = DataParser()
        parser.SHEET_DEAL = deal_sheet
        non_deal = body.get("non_deal_sheet", "")
        if non_deal:
            parser.SHEET_NON_DEAL = non_deal
        result = parser.parse(file_path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    parse_id = uuid.uuid4().hex
    _parse_cache[parse_id] = result
    _file_path_cache[parse_id] = file_path
    _save_parse_cache(_parse_cache)
    _save_file_path_cache(_file_path_cache)

    available_sheets = _get_sheets(file_path)

    return jsonify({
        "parse_id": parse_id,
        "detected_columns": result.detected_columns,
        "deal_row_count": len(result.deal_rows),
        "non_deal_row_count": len(result.non_deal_rows),
        "errors": result.errors,
        "available_sheets": available_sheets,
        "file_path": file_path,
    }), 200


@upload_bp.route("/list-uploads", methods=["GET"])
def list_uploads():
    import glob
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    files = []
    for ext in ['*.xlsx', '*.xls']:
        for f in glob.glob(os.path.join(upload_folder, ext)):
            name = os.path.basename(f)
            if name.startswith('.') or name.startswith('brand_config_'):
                continue
            size = os.path.getsize(f)
            files.append({"name": name, "size": size, "sheets": _get_sheets(f)})
    files.sort(key=lambda x: x["size"], reverse=True)
    return jsonify({"files": files}), 200


@upload_bp.route("/clear-cache", methods=["POST"])
def clear_cache():
    """
    Clear all parsing and mapping caches.
    Useful when code changes require re-parsing files.
    """
    global _parse_cache, _file_path_cache
    
    cleared = []
    errors = []
    
    # Clear in-memory caches
    parse_count = len(_parse_cache)
    file_path_count = len(_file_path_cache)
    _parse_cache.clear()
    _file_path_cache.clear()
    cleared.append(f"In-memory parse cache: {parse_count} entries")
    cleared.append(f"In-memory file path cache: {file_path_count} entries")
    
    # Clear parse cache file
    try:
        if os.path.exists(_PARSE_CACHE_FILE):
            os.remove(_PARSE_CACHE_FILE)
            cleared.append(f"Deleted: {_PARSE_CACHE_FILE}")
    except Exception as exc:
        errors.append(f"Failed to delete {_PARSE_CACHE_FILE}: {exc}")
    
    # Clear file path cache file
    try:
        if os.path.exists(_FILE_PATH_CACHE_FILE):
            os.remove(_FILE_PATH_CACHE_FILE)
            cleared.append(f"Deleted: {_FILE_PATH_CACHE_FILE}")
    except Exception as exc:
        errors.append(f"Failed to delete {_FILE_PATH_CACHE_FILE}: {exc}")
    
    # Clear mapping cache file (from brands module)
    mapping_cache_file = "uploads/.mapping_cache.json"
    try:
        if os.path.exists(mapping_cache_file):
            os.remove(mapping_cache_file)
            cleared.append(f"Deleted: {mapping_cache_file}")
    except Exception as exc:
        errors.append(f"Failed to delete {mapping_cache_file}: {exc}")
    
    return jsonify({
        "success": len(errors) == 0,
        "cleared": cleared,
        "errors": errors,
        "message": "Cache cleared successfully. Please re-upload your files." if len(errors) == 0 else "Cache partially cleared with errors."
    }), 200 if len(errors) == 0 else 207


# ---------------------------------------------------------------------------
# Multi-Brand Detection Endpoints
# ---------------------------------------------------------------------------

@upload_bp.route("/parse/<parse_id>/detect-brands", methods=["POST"])
def detect_brands(parse_id: str):
    """
    Detect brands from parsed data and return brand selection interface data.
    
    Returns:
        BrandSelectionData with detected brands, statistics, and previews
    """
    try:
        # Get parsed data from cache
        parse_result = _parse_cache.get(parse_id)
        if not parse_result:
            return jsonify({
                "success": False,
                "error": "Parse result not found. Please upload and parse the file first."
            }), 404
        
        # Initialize multi-brand components
        brand_normalizer = BrandNormalizer()
        multi_brand_detector = MultiBrandDetector(brand_normalizer)
        brand_grouper = BrandGrouper()
        ui_builder = BrandUIDataBuilder()
        
        # Perform brand detection
        brand_detection_result = multi_brand_detector.detect_brands(parse_result)
        
        if not brand_detection_result.is_multi_brand:
            return jsonify({
                "success": True,
                "is_multi_brand": False,
                "message": "Single brand detected. Use regular workflow.",
                "brand_detection_result": {
                    "brands_detected": brand_detection_result.brands_detected,
                    "total_creators": brand_detection_result.total_creators,
                    "detection_confidence": brand_detection_result.detection_confidence
                }
            }), 200
        
        # Perform brand normalization
        normalization_result = brand_normalizer.normalize_brands(
            brand_detection_result.brands_detected
        )
        
        # Group creators by brand
        all_creators = parse_result.deal_rows + parse_result.non_deal_rows
        brand_group_result = brand_grouper.group_by_brand(all_creators, normalization_result)
        
        # Build preview data for each brand
        brand_preview_data = {}
        for brand_name, creators in brand_group_result.brand_groups.items():
            if brand_name != "UNASSIGNED":  # Skip unassigned for preview
                preview_data = ui_builder.build_brand_preview_data(brand_name, creators)
                brand_preview_data[brand_name] = preview_data
        
        # Build complete brand selection data
        brand_selection_data = ui_builder.build_brand_selection_data(
            brand_detection_result,
            brand_group_result.brand_statistics,
            normalization_result,
            brand_preview_data
        )
        
        # Cache the brand group result for later use
        _brand_group_cache = getattr(_parse_cache, '_brand_group_cache', {})
        _brand_group_cache[parse_id] = brand_group_result
        _parse_cache._brand_group_cache = _brand_group_cache
        
        return jsonify({
            "success": True,
            "is_multi_brand": True,
            "brand_selection_data": {
                "detected_brands": brand_selection_data.detected_brands,
                "total_creators": brand_selection_data.total_creators,
                "detection_confidence": brand_selection_data.detection_confidence,
                "has_unassigned": brand_selection_data.has_unassigned,
                "brand_previews": {
                    name: {
                        "brand_name": preview.brand_name,
                        "creator_count": preview.creator_count,
                        "total_gmv": preview.total_gmv,
                        "avg_gmv": preview.avg_gmv,
                        "top_creators": preview.top_creators,
                        "has_brand_profile": preview.has_brand_profile,
                        "brand_profile_status": preview.brand_profile_status,
                        "video_count": preview.video_count,
                        "deal_ratio": preview.deal_ratio
                    }
                    for name, preview in brand_selection_data.brand_previews.items()
                },
                "suggested_aliases": brand_selection_data.suggested_aliases
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Brand detection failed for parse_id {parse_id}: {e}")
        return jsonify({
            "success": False,
            "error": f"Brand detection failed: {str(e)}"
        }), 500


@upload_bp.route("/parse/<parse_id>/normalize-brands", methods=["POST"])
def normalize_brands(parse_id: str):
    """
    Apply brand normalization and alias resolution.
    
    Request Body:
        {
            "alias_decisions": {
                "FLORIST": ["Florist", "florist"],
                "BRAND_X": ["Brand X", "BrandX"]
            }
        }
    
    Returns:
        Updated BrandSelectionData with normalized brands
    """
    try:
        # Get request data
        body = request.get_json(silent=True) or {}
        alias_decisions = body.get("alias_decisions", {})
        
        # Get parsed data from cache
        parse_result = _parse_cache.get(parse_id)
        if not parse_result:
            return jsonify({
                "success": False,
                "error": "Parse result not found. Please upload and parse the file first."
            }), 404
        
        # Initialize components
        brand_normalizer = BrandNormalizer()
        
        # Apply user-defined aliases
        for canonical_name, aliases in alias_decisions.items():
            for alias in aliases:
                brand_normalizer.add_alias(canonical_name, alias)
        
        # Re-run brand detection with updated aliases
        multi_brand_detector = MultiBrandDetector(brand_normalizer)
        brand_detection_result = multi_brand_detector.detect_brands(parse_result)
        
        # Re-run normalization
        normalization_result = brand_normalizer.normalize_brands(
            brand_detection_result.brands_detected
        )
        
        # Re-group creators
        brand_grouper = BrandGrouper()
        all_creators = parse_result.deal_rows + parse_result.non_deal_rows
        brand_group_result = brand_grouper.group_by_brand(all_creators, normalization_result)
        
        # Update cache
        _brand_group_cache = getattr(_parse_cache, '_brand_group_cache', {})
        _brand_group_cache[parse_id] = brand_group_result
        _parse_cache._brand_group_cache = _brand_group_cache
        
        # Build updated UI data
        ui_builder = BrandUIDataBuilder()
        brand_preview_data = {}
        for brand_name, creators in brand_group_result.brand_groups.items():
            if brand_name != "UNASSIGNED":
                preview_data = ui_builder.build_brand_preview_data(brand_name, creators)
                brand_preview_data[brand_name] = preview_data
        
        brand_selection_data = ui_builder.build_brand_selection_data(
            brand_detection_result,
            brand_group_result.brand_statistics,
            normalization_result,
            brand_preview_data
        )
        
        return jsonify({
            "success": True,
            "message": "Brand normalization applied successfully",
            "brand_selection_data": {
                "detected_brands": brand_selection_data.detected_brands,
                "total_creators": brand_selection_data.total_creators,
                "detection_confidence": brand_selection_data.detection_confidence,
                "has_unassigned": brand_selection_data.has_unassigned,
                "brand_previews": {
                    name: {
                        "brand_name": preview.brand_name,
                        "creator_count": preview.creator_count,
                        "total_gmv": preview.total_gmv,
                        "avg_gmv": preview.avg_gmv,
                        "top_creators": preview.top_creators,
                        "has_brand_profile": preview.has_brand_profile,
                        "brand_profile_status": preview.brand_profile_status,
                        "video_count": preview.video_count,
                        "deal_ratio": preview.deal_ratio
                    }
                    for name, preview in brand_selection_data.brand_previews.items()
                },
                "suggested_aliases": brand_selection_data.suggested_aliases,
                "applied_aliases": normalization_result.applied_aliases
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Brand normalization failed for parse_id {parse_id}: {e}")
        return jsonify({
            "success": False,
            "error": f"Brand normalization failed: {str(e)}"
        }), 500


@upload_bp.route("/parse/<parse_id>/generate-multi-brand-reports", methods=["POST"])
def generate_multi_brand_reports(parse_id: str):
    """
    Generate reports for selected brands.
    
    Request Body:
        {
            "selected_brands": ["FLORIST", "BRAND_X"],
            "report_mode": "separate",  // or "consolidated"
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "batch_number": "Batch 1",
            "include_brand_comparison": true
        }
    
    Returns:
        MultiBrandReportResult with generated report paths
    """
    try:
        # Get request data
        body = request.get_json(silent=True) or {}
        
        # Validate required fields
        required_fields = ["selected_brands", "report_mode", "period_start", "period_end", "batch_number"]
        for field in required_fields:
            if field not in body:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        # Validate report mode
        if body["report_mode"] not in ["separate", "consolidated"]:
            return jsonify({
                "success": False,
                "error": "report_mode must be 'separate' or 'consolidated'"
            }), 400
        
        # Validate selected brands
        selected_brands = body["selected_brands"]
        if not isinstance(selected_brands, list) or len(selected_brands) == 0:
            return jsonify({
                "success": False,
                "error": "selected_brands must be a non-empty list"
            }), 400
        
        # Get brand group result from cache
        _brand_group_cache = getattr(_parse_cache, '_brand_group_cache', {})
        brand_group_result = _brand_group_cache.get(parse_id)
        
        if not brand_group_result:
            return jsonify({
                "success": False,
                "error": "Brand group data not found. Please run brand detection first."
            }), 404
        
        # Validate that selected brands exist in the data
        available_brands = set(brand_group_result.brand_groups.keys())
        selected_brands_set = set(selected_brands)
        missing_brands = selected_brands_set - available_brands
        
        if missing_brands:
            return jsonify({
                "success": False,
                "error": f"Selected brands not found in data: {list(missing_brands)}"
            }), 400
        
        # Create report configuration
        from app.services.brand_ui_models import MultiBrandReportConfig
        
        config = MultiBrandReportConfig(
            selected_brands=selected_brands,
            report_mode=body["report_mode"],
            period_start=body["period_start"],
            period_end=body["period_end"],
            batch_number=body["batch_number"],
            include_brand_comparison=body.get("include_brand_comparison", True)
        )
        
        # Initialize report generator
        from app.services.multi_brand_report_generator import MultiBrandReportGenerator
        from app.services.brand_profile import BrandProfileService
        from app.services.pdf_renderer import PDFRenderer
        from app.services.ppt_renderer import PPTRenderer
        from app.models.db import db
        
        brand_profile_service = BrandProfileService()
        pdf_renderer = PDFRenderer()
        ppt_renderer = PPTRenderer()
        report_generator = MultiBrandReportGenerator(
            brand_profile_service=brand_profile_service,
            pdf_renderer=pdf_renderer,
            ppt_renderer=ppt_renderer
        )
        
        # Generate reports
        result = report_generator.generate_reports(
            config, brand_group_result, db.session
        )
        
        # Format response
        response_data = {
            "success": result.success,
            "report_mode": config.report_mode,
            "total_brands_processed": result.total_brands_processed,
            "total_reports_generated": result.total_reports_generated,
            "generation_summary": result.generation_summary
        }
        
        if result.success:
            if config.report_mode == "separate":
                response_data["generated_reports"] = result.generated_reports
            else:
                response_data["consolidated_report_path"] = result.consolidated_report_path
            
            response_data["message"] = f"Successfully generated {result.total_reports_generated} report(s)"
        else:
            response_data["failed_brands"] = result.failed_brands
            response_data["error"] = "Report generation failed for some or all brands"
        
        status_code = 200 if result.success else 207  # 207 for partial success
        return jsonify(response_data), status_code
        
    except Exception as e:
        current_app.logger.error(f"Multi-brand report generation failed for parse_id {parse_id}: {e}")
        return jsonify({
            "success": False,
            "error": f"Report generation failed: {str(e)}"
        }), 500
