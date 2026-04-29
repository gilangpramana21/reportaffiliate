"""
Image upload endpoints untuk screenshot per section laporan.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

images_bp = Blueprint("images", __name__, url_prefix="/api")

_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_IMAGES_FOLDER = "uploads/images"


def _allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in _ALLOWED_IMAGE_EXTS


@images_bp.route("/images/upload", methods=["POST"])
def upload_image():
    """
    Upload satu atau lebih gambar untuk section tertentu.
    Body: multipart/form-data { files[], section }
    """
    section = request.form.get("section", "general").strip()
    if not section:
        return jsonify({"error": "Field 'section' wajib diisi"}), 400

    files = request.files.getlist("files")
    if not files or all(not f.filename for f in files):
        # Fallback: coba key 'file' (single)
        single = request.files.get("file")
        if single and single.filename:
            files = [single]
        else:
            return jsonify({"error": "Tidak ada file yang dikirim"}), 400

    os.makedirs(_IMAGES_FOLDER, exist_ok=True)
    saved = []

    for file in files:
        if not file.filename:
            continue
        if not _allowed_image(file.filename):
            continue
        ext = Path(file.filename).suffix.lower()
        filename = f"{section}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(_IMAGES_FOLDER, filename)
        try:
            file.save(filepath)
            saved.append({
                "image_id": filename,
                "url": f"/api/images/{filename}",
                "section": section,
            })
        except Exception as exc:
            continue

    if not saved:
        return jsonify({"error": "Tidak ada gambar yang berhasil disimpan"}), 400

    return jsonify({"images": saved}), 201


@images_bp.route("/images/<image_id>", methods=["GET"])
def get_image(image_id: str):
    """Serve gambar yang sudah diupload."""
    # Sanitize — hanya izinkan filename tanpa path traversal
    safe_name = Path(image_id).name
    filepath = os.path.join(_IMAGES_FOLDER, safe_name)
    if not os.path.isfile(filepath):
        return jsonify({"error": "Gambar tidak ditemukan"}), 404
    return send_file(filepath)


@images_bp.route("/images/<image_id>", methods=["DELETE"])
def delete_image(image_id: str):
    """Hapus gambar."""
    safe_name = Path(image_id).name
    filepath = os.path.join(_IMAGES_FOLDER, safe_name)
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
    except Exception:
        pass
    return "", 204
