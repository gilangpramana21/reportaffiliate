"""
Settings endpoints — simpan dan ambil konfigurasi aplikasi termasuk TikTok cookies.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from app.models.db import AppSettings, db

settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _get_setting(key: str, default: str = "") -> str:
    row = db.session.query(AppSettings).filter_by(key=key).first()
    return row.value if row else default


def _set_setting(key: str, value: str) -> None:
    row = db.session.query(AppSettings).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(AppSettings(key=key, value=value))
    db.session.commit()


@settings_bp.route("/settings/tiktok-cookies", methods=["GET"])
def get_tiktok_cookies():
    cookies = _get_setting("tiktok_cookies", "")
    has_cookies = bool(cookies.strip())
    # Jangan return nilai cookie langsung — hanya status
    return jsonify({
        "has_cookies": has_cookies,
        "cookie_preview": cookies[:50] + "..." if len(cookies) > 50 else cookies,
    }), 200


@settings_bp.route("/settings/tiktok-cookies", methods=["POST"])
def save_tiktok_cookies():
    body = request.get_json(silent=True) or {}
    cookies = body.get("cookies", "").strip()
    if not cookies:
        return jsonify({"error": "Cookie tidak boleh kosong"}), 400
    _set_setting("tiktok_cookies", cookies)
    return jsonify({"message": "Cookie berhasil disimpan"}), 200


@settings_bp.route("/settings/tiktok-cookies", methods=["DELETE"])
def delete_tiktok_cookies():
    _set_setting("tiktok_cookies", "")
    return jsonify({"message": "Cookie dihapus"}), 200


@settings_bp.route("/settings/scrape-method", methods=["GET"])
def get_scrape_method():
    import os
    use_echotik = bool(os.environ.get("ECHOTIK_USERNAME", ""))
    cookies = _get_setting("tiktok_cookies", "")
    has_cookies = bool(cookies.strip())

    if use_echotik:
        method = "echotik"
    elif has_cookies:
        method = "cookie"
    else:
        method = "playwright"

    return jsonify({
        "method": method,
        "echotik_configured": use_echotik,
        "has_cookies": has_cookies,
    }), 200
