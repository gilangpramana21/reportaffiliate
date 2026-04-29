"""
Report Generation & History endpoints.

  POST /api/reports/generate   — generate PDF report
  GET  /api/reports            — list report history
  GET  /api/reports/<id>/download — download PDF
"""
from __future__ import annotations

import json
import os
from datetime import date
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_file, current_app

from app.models.db import ReportRecord, db
from app.routes.brands import _mapping_cache
from app.services.brand_profile import BrandProfileService
from app.services.data_parser import CreatorRow
import dataclasses
from app.services.pdf_renderer import PDFRenderer
from app.services.report_gen import (
    EngagementData,
    ReportConfig,
    ReportGenerator,
    ValidationError,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/api")

_brand_service = BrandProfileService()
_report_gen = ReportGenerator()
_pdf_renderer = PDFRenderer()


# ---------------------------------------------------------------------------
# POST /api/reports/generate
# ---------------------------------------------------------------------------

@reports_bp.route("/reports/generate", methods=["POST"])
def generate_report():
    body = request.get_json(silent=True) or {}

    mapping_id = body.get("mapping_id", "")
    brand_name = body.get("brand_name", "").strip()
    batch_number = str(body.get("batch_number", "")).strip()
    period_start_str = body.get("period_start", "")
    period_end_str = body.get("period_end", "")

    # Validasi field wajib
    if not mapping_id:
        return jsonify({"error": "Field 'mapping_id' wajib diisi"}), 400
    if not brand_name:
        return jsonify({"error": "Field 'brand_name' wajib diisi"}), 400
    if not batch_number:
        return jsonify({"error": "Field 'batch_number' wajib diisi"}), 400
    if not period_start_str:
        return jsonify({"error": "Field 'period_start' wajib diisi"}), 400
    if not period_end_str:
        return jsonify({"error": "Field 'period_end' wajib diisi"}), 400

    # Parse tanggal
    try:
        period_start = date.fromisoformat(period_start_str)
        period_end = date.fromisoformat(period_end_str)
    except ValueError as exc:
        return jsonify({"error": f"Format tanggal tidak valid: {exc}"}), 400

    # Ambil mapping dari cache
    mapping_data = _mapping_cache.get(mapping_id)
    if mapping_data is None:
        return jsonify({"error": f"mapping_id '{mapping_id}' tidak ditemukan"}), 404

    # Convert dict → CreatorRow (handle field baru yang mungkin tidak ada di cache lama)
    def _safe_creator_row(r: dict):
        valid_fields = {f for f in dataclasses.fields(CreatorRow)}
        field_names = {f.name for f in valid_fields}
        filtered = {k: v for k, v in r.items() if k in field_names}
        return CreatorRow(**filtered)

    deal_rows = [_safe_creator_row(r) for r in mapping_data["deal_rows"]]
    non_deal_rows = [_safe_creator_row(r) for r in mapping_data["non_deal_rows"]]

    # Ambil BrandProfile
    brand_profile = _brand_service.get_or_create(brand_name, db.session)

    # Build EngagementData (opsional)
    engagement = None
    eng_body = body.get("engagement")
    if eng_body and isinstance(eng_body, dict):
        from app.services.report_gen import CreatorEngagementItem, VideoEngagementItem
        top_creators = []
        # Parse top_creators jika ada
        if eng_body.get("top_creators") and isinstance(eng_body["top_creators"], list):
            print(f"[DEBUG] Parsing {len(eng_body['top_creators'])} top creators")
            for item in eng_body["top_creators"][:5]:  # max 5
                if isinstance(item, dict) and item.get("username"):
                    # Parse videos jika ada
                    videos = []
                    if item.get("videos") and isinstance(item["videos"], list):
                        print(f"[DEBUG] Creator {item['username']} has {len(item['videos'])} videos")
                        for vid in item["videos"]:
                            if isinstance(vid, dict):
                                videos.append(VideoEngagementItem(
                                    url=vid.get("url", ""),
                                    views=int(vid.get("views", 0)),
                                    likes=int(vid.get("likes", 0)),
                                    comments=int(vid.get("comments", 0)),
                                ))
                    else:
                        print(f"[DEBUG] Creator {item['username']} has NO videos array")
                    
                    creator = CreatorEngagementItem(
                        username=item["username"],
                        total_views=int(item.get("total_views", 0)),
                        total_likes=int(item.get("total_likes", 0)),
                        total_comments=int(item.get("total_comments", 0)),
                        videos=videos,
                    )
                    print(f"[DEBUG] Created CreatorEngagementItem: {creator.username}, videos count: {len(creator.videos)}")
                    top_creators.append(creator)
        engagement = EngagementData(
            total_views=int(eng_body.get("total_views", 0)),
            total_likes=int(eng_body.get("total_likes", 0)),
            total_comments=int(eng_body.get("total_comments", 0)),
            top_creators=top_creators,
        )
        print(f"[DEBUG] Final engagement data: {len(engagement.top_creators)} creators")
        for c in engagement.top_creators:
            print(f"[DEBUG]   - {c.username}: {len(c.videos)} videos")

    # Build ReportConfig
    config = ReportConfig(
        brand_name=brand_name,
        batch_number=batch_number,
        period_start=period_start,
        period_end=period_end,
        prev_gmv=float(body["prev_gmv"]) if body.get("prev_gmv") is not None else None,
        engagement=engagement,
        insight=body.get("insight"),
        next_plan=body.get("next_plan"),
        total_pesanan=int(body["total_pesanan"]) if body.get("total_pesanan") else None,
        total_produk_terjual=int(body["total_produk_terjual"]) if body.get("total_produk_terjual") else None,
        total_create_sale=int(body["total_create_sale"]) if body.get("total_create_sale") else None,
        overall_conclusion=body.get("overall_conclusion"),
        next_planning=body.get("next_planning"),
        section_images=body.get("section_images", {}),
    )

    # Assemble report data (juga validasi tanggal)
    try:
        report_data = _report_gen.assemble_report_data(
            config, deal_rows, non_deal_rows, brand_profile
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    # Generate PDF — gunakan path absolut
    reports_folder = current_app.config.get("REPORTS_FOLDER", "reports")
    os.makedirs(reports_folder, exist_ok=True)
    safe_brand = "".join(c for c in brand_name if c.isalnum() or c in "-_")[:30]
    safe_batch = "".join(c for c in batch_number if c.isalnum() or c in "-_")[:10]
    output_filename = f"{safe_brand}_{safe_batch}_{uuid4().hex[:8]}.pdf"
    output_path = os.path.join(reports_folder, output_filename)

    try:
        _pdf_renderer.render(report_data, output_path)
    except Exception as exc:
        import traceback
        return jsonify({"error": f"Gagal generate PDF: {exc}", "detail": traceback.format_exc()}), 500

    # Generate PPT
    ppt_path = output_path.replace('.pdf', '.pptx')
    ppt_generated = False
    try:
        from app.services.ppt_renderer import PPTRenderer
        PPTRenderer().render(report_data, ppt_path)
        ppt_generated = True
    except Exception as exc:
        import sys
        print(f"[PPT] Gagal generate PPT: {exc}", file=sys.stderr)

    # Simpan ReportRecord ke database
    config_snapshot = {
        "brand_name": brand_name,
        "batch_number": batch_number,
        "period_start": period_start_str,
        "period_end": period_end_str,
        "prev_gmv": body.get("prev_gmv"),
        "engagement": eng_body,
        "insight": body.get("insight"),
        "next_plan": body.get("next_plan"),
    }

    record = ReportRecord(
        brand_name=brand_name,
        batch_number=batch_number,
        period_start=period_start,
        period_end=period_end,
        pdf_path=output_path,
        config_snapshot=json.dumps(config_snapshot, ensure_ascii=False),
    )
    db.session.add(record)
    db.session.commit()
    db.session.refresh(record)

    return jsonify({
        "report_id": record.id,
        "pdf_url": f"/api/reports/{record.id}/download",
        "ppt_url": f"/api/reports/{record.id}/download-ppt" if ppt_generated else None,
    }), 201


# ---------------------------------------------------------------------------
# GET /api/reports
# ---------------------------------------------------------------------------

@reports_bp.route("/reports", methods=["GET"])
def list_reports():
    records = (
        db.session.query(ReportRecord)
        .order_by(ReportRecord.generated_at.desc())
        .limit(50)
        .all()
    )
    result = [
        {
            "id": r.id,
            "brand_name": r.display_name,  # Use display_name for multi-brand support
            "batch_number": r.batch_number,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "pdf_url": f"/api/reports/{r.id}/download",
            "ppt_url": f"/api/reports/{r.id}/download-ppt" if r.ppt_path else None,
            # Multi-brand specific fields
            "is_multi_brand": r.is_multi_brand,
            "brand_count": r.brand_count,
            "brands_list": r.brands_list,
            "report_mode": r.report_mode,
        }
        for r in records
    ]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/reports/<report_id>/download
# ---------------------------------------------------------------------------

@reports_bp.route("/reports/<int:report_id>/download", methods=["GET"])
def download_report(report_id: int):
    record = db.session.query(ReportRecord).filter_by(id=report_id).first()
    if record is None:
        return jsonify({"error": f"Report dengan id={report_id} tidak ditemukan"}), 404

    pdf_path = record.pdf_path
    # Handle both relative and absolute paths
    if not os.path.isabs(pdf_path):
        pdf_path = os.path.join(os.getcwd(), pdf_path)

    if not os.path.isfile(pdf_path):
        return jsonify({"error": "File PDF tidak ditemukan di server. Coba generate ulang laporan."}), 404

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=os.path.basename(pdf_path),
    )


@reports_bp.route("/reports/<int:report_id>/download-ppt", methods=["GET"])
def download_report_ppt(report_id: int):
    record = db.session.query(ReportRecord).filter_by(id=report_id).first()
    if record is None:
        return jsonify({"error": f"Report dengan id={report_id} tidak ditemukan"}), 404

    # Use ppt_path if available, otherwise derive from pdf_path
    ppt_path = record.ppt_path or record.pdf_path.replace('.pdf', '.pptx')
    
    if not os.path.isabs(ppt_path):
        ppt_path = os.path.join(os.getcwd(), ppt_path)

    if not os.path.isfile(ppt_path):
        return jsonify({"error": "File PPT tidak ditemukan. Coba generate ulang laporan."}), 404

    return send_file(
        ppt_path,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=os.path.basename(ppt_path),
    )


# ---------------------------------------------------------------------------
# POST /api/reports/batch-generate  — generate laporan beberapa brand sekaligus
# ---------------------------------------------------------------------------

_batch_jobs: dict[str, dict] = {}


@reports_bp.route("/reports/batch-generate", methods=["POST"])
def batch_generate():
    """
    Body: {
        jobs: [
            {
                mapping_id, brand_name, batch_number,
                period_start, period_end,
                prev_gmv?, engagement?, insight?, next_plan?,
                total_pesanan?, total_produk_terjual?, total_create_sale?
            },
            ...
        ]
    }
    """
    body = request.get_json(silent=True) or {}
    jobs = body.get("jobs", [])

    if not jobs or not isinstance(jobs, list):
        return jsonify({"error": "Field 'jobs' wajib diisi sebagai array"}), 400
    if len(jobs) > 20:
        return jsonify({"error": "Maksimal 20 laporan per batch"}), 400

    batch_id = uuid4().hex
    _batch_jobs[batch_id] = {
        "status": "running",
        "total": len(jobs),
        "done": 0,
        "results": [],
        "errors": [],
    }

    import threading
    from flask import current_app
    app = current_app._get_current_object()

    def run_batch():
        for i, job_body in enumerate(jobs):
            try:
                with app.test_request_context():
                    result = _generate_single(job_body, app, batch_id)
                    _batch_jobs[batch_id]["results"].append(result)
            except Exception as exc:
                _batch_jobs[batch_id]["errors"].append({
                    "index": i,
                    "brand": job_body.get("brand_name", "?"),
                    "error": str(exc),
                })
            _batch_jobs[batch_id]["done"] = i + 1

        _batch_jobs[batch_id]["status"] = "done"

        # Fire webhook
        try:
            from app.services.webhook_service import fire_event
            fire_event("batch.completed", {
                "batch_id": batch_id,
                "total": len(jobs),
                "done": _batch_jobs[batch_id]["done"],
                "results": _batch_jobs[batch_id]["results"],
            }, app=app)
        except Exception:
            pass

    threading.Thread(target=run_batch, daemon=True).start()

    return jsonify({"batch_id": batch_id, "total": len(jobs)}), 202


@reports_bp.route("/reports/batch-status/<batch_id>", methods=["GET"])
def batch_status(batch_id: str):
    job = _batch_jobs.get(batch_id)
    if job is None:
        return jsonify({"error": f"batch_id '{batch_id}' tidak ditemukan"}), 404
    return jsonify(job), 200


def _generate_single(body: dict, app, batch_id: str = None) -> dict:
    """Generate satu laporan dari body dict. Dipakai oleh batch generate."""
    import dataclasses as _dc

    mapping_id = body.get("mapping_id", "")
    brand_name = str(body.get("brand_name", "")).strip()
    batch_number = str(body.get("batch_number", "")).strip()
    period_start_str = body.get("period_start", "")
    period_end_str = body.get("period_end", "")

    if not all([mapping_id, brand_name, batch_number, period_start_str, period_end_str]):
        raise ValueError("mapping_id, brand_name, batch_number, period_start, period_end wajib diisi")

    period_start = date.fromisoformat(period_start_str)
    period_end = date.fromisoformat(period_end_str)

    mapping_data = _mapping_cache.get(mapping_id)
    if mapping_data is None:
        raise ValueError(f"mapping_id '{mapping_id}' tidak ditemukan")

    def _safe(r):
        valid = {f.name for f in _dc.fields(CreatorRow)}
        return CreatorRow(**{k: v for k, v in r.items() if k in valid})

    deal_rows = [_safe(r) for r in mapping_data["deal_rows"]]
    non_deal_rows = [_safe(r) for r in mapping_data["non_deal_rows"]]

    with app.app_context():
        brand_profile = _brand_service.get_or_create(brand_name, db.session)

    eng_body = body.get("engagement")
    engagement = None
    if eng_body and isinstance(eng_body, dict):
        engagement = EngagementData(
            total_views=int(eng_body.get("total_views", 0)),
            total_likes=int(eng_body.get("total_likes", 0)),
            total_comments=int(eng_body.get("total_comments", 0)),
        )

    config = ReportConfig(
        brand_name=brand_name, batch_number=batch_number,
        period_start=period_start, period_end=period_end,
        prev_gmv=float(body["prev_gmv"]) if body.get("prev_gmv") is not None else None,
        engagement=engagement,
        insight=body.get("insight"), next_plan=body.get("next_plan"),
        total_pesanan=int(body["total_pesanan"]) if body.get("total_pesanan") else None,
        total_produk_terjual=int(body["total_produk_terjual"]) if body.get("total_produk_terjual") else None,
        total_create_sale=int(body["total_create_sale"]) if body.get("total_create_sale") else None,
    )

    report_data = _report_gen.assemble_report_data(config, deal_rows, non_deal_rows, brand_profile)

    reports_folder = app.config.get("REPORTS_FOLDER", "reports")
    os.makedirs(reports_folder, exist_ok=True)
    safe_brand = "".join(c for c in brand_name if c.isalnum() or c in "-_")[:30]
    safe_batch = "".join(c for c in batch_number if c.isalnum() or c in "-_")[:10]
    output_path = os.path.join(reports_folder, f"{safe_brand}_{safe_batch}_{uuid4().hex[:8]}.pdf")

    _pdf_renderer.render(report_data, output_path)

    ppt_path = output_path.replace('.pdf', '.pptx')
    ppt_generated = False
    try:
        from app.services.ppt_renderer import PPTRenderer
        PPTRenderer().render(report_data, ppt_path)
        ppt_generated = True
    except Exception:
        pass

    with app.app_context():
        record = ReportRecord(
            brand_name=brand_name, batch_number=batch_number,
            period_start=period_start, period_end=period_end,
            pdf_path=output_path,
            config_snapshot=json.dumps({"brand_name": brand_name, "batch_number": batch_number}, ensure_ascii=False),
            batch_job_id=batch_id,
        )
        db.session.add(record)
        db.session.commit()
        db.session.refresh(record)
        record_id = record.id

    # Fire webhook for single report
    try:
        from app.services.webhook_service import fire_event
        fire_event("report.created", {
            "report_id": record_id,
            "brand_name": brand_name,
            "batch_number": batch_number,
            "pdf_url": f"/api/reports/{record_id}/download",
            "ppt_url": f"/api/reports/{record_id}/download-ppt" if ppt_generated else None,
        }, app=app)
    except Exception:
        pass

    return {
        "report_id": record_id,
        "brand_name": brand_name,
        "pdf_url": f"/api/reports/{record_id}/download",
        "ppt_url": f"/api/reports/{record_id}/download-ppt" if ppt_generated else None,
    }


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

@reports_bp.route("/webhooks", methods=["GET"])
def list_webhooks():
    from app.models.db import WebhookConfig
    whs = db.session.query(WebhookConfig).all()
    return jsonify([{
        "id": w.id, "url": w.url, "enabled": w.enabled,
        "events": json.loads(w.events or '[]'),
        "has_secret": bool(w.secret),
    } for w in whs]), 200


@reports_bp.route("/webhooks", methods=["POST"])
def create_webhook():
    from app.models.db import WebhookConfig
    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    if not url or not url.startswith("http"):
        return jsonify({"error": "URL webhook tidak valid"}), 400

    wh = WebhookConfig(
        url=url,
        secret=body.get("secret", ""),
        enabled=bool(body.get("enabled", True)),
        events=json.dumps(body.get("events", ["report.created"])),
    )
    db.session.add(wh)
    db.session.commit()
    return jsonify({"id": wh.id, "url": wh.url, "enabled": wh.enabled}), 201


@reports_bp.route("/webhooks/<int:wh_id>", methods=["DELETE"])
def delete_webhook(wh_id: int):
    from app.models.db import WebhookConfig
    wh = db.session.query(WebhookConfig).filter_by(id=wh_id).first()
    if not wh:
        return jsonify({"error": "Webhook tidak ditemukan"}), 404
    db.session.delete(wh)
    db.session.commit()
    return "", 204


@reports_bp.route("/webhooks/<int:wh_id>/test", methods=["POST"])
def test_webhook(wh_id: int):
    from app.models.db import WebhookConfig
    from app.services.webhook_service import _send_webhook
    wh = db.session.query(WebhookConfig).filter_by(id=wh_id).first()
    if not wh:
        return jsonify({"error": "Webhook tidak ditemukan"}), 404
    ok = _send_webhook(wh.url, {"event": "test", "message": "Test dari TikTok Affiliate Report"}, wh.secret or "")
    return jsonify({"success": ok}), 200


# ---------------------------------------------------------------------------
# GET /api/dashboard  — ringkasan semua brand
# ---------------------------------------------------------------------------

@reports_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Return ringkasan semua brand: total laporan, GMV terbaru, batch terbaru."""
    from app.models.db import BrandProfile
    from sqlalchemy import func

    brands = db.session.query(BrandProfile).all()
    result = []

    for brand in brands:
        # Ambil laporan terbaru untuk brand ini
        latest = (
            db.session.query(ReportRecord)
            .filter_by(brand_name=brand.name)
            .order_by(ReportRecord.generated_at.desc())
            .first()
        )
        total_reports = (
            db.session.query(func.count(ReportRecord.id))
            .filter_by(brand_name=brand.name)
            .scalar()
        )

        # Parse GMV dari config_snapshot laporan terbaru
        latest_gmv = None
        latest_batch = None
        latest_period = None
        if latest:
            try:
                snap = json.loads(latest.config_snapshot)
                latest_batch = snap.get("batch_number")
                latest_period = f"{snap.get('period_start', '')} s/d {snap.get('period_end', '')}"
            except Exception:
                pass
            latest_batch = latest_batch or latest.batch_number

        import json as _json
        try:
            sku_list = _json.loads(brand.sku_list) if brand.sku_list else []
        except Exception:
            sku_list = []

        result.append({
            "brand_id": brand.id,
            "brand_name": brand.name,
            "sku_count": len(sku_list),
            "has_column_config": brand.column_config is not None,
            "total_reports": total_reports,
            "latest_batch": latest_batch,
            "latest_period": latest_period,
            "latest_report_id": latest.id if latest else None,
            "latest_generated_at": latest.generated_at.isoformat() if latest and latest.generated_at else None,
        })

    # Sort by total_reports desc
    result.sort(key=lambda x: x["total_reports"], reverse=True)
    return jsonify(result), 200
