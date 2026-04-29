"""
Webhook Service — kirim notifikasi HTTP saat event terjadi.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime


def _send_webhook(url: str, payload: dict, secret: str = "") -> bool:
    """Send HTTP POST to webhook URL. Returns True if successful."""
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TikTokAffiliateReport/1.0",
        "X-Event-Type": payload.get("event", ""),
    }
    if secret:
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Signature-SHA256"] = f"sha256={sig}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception:
        return False


def fire_event(event: str, data: dict, app=None) -> None:
    """
    Fire a webhook event asynchronously.
    Loads webhook configs from DB and sends to all enabled webhooks.
    """
    def _run():
        try:
            from app.models.db import WebhookConfig, db
            if app:
                with app.app_context():
                    _dispatch(event, data)
            else:
                _dispatch(event, data)
        except Exception:
            pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _dispatch(event: str, data: dict) -> None:
    from app.models.db import WebhookConfig, db
    try:
        webhooks = db.session.query(WebhookConfig).filter_by(enabled=True).all()
    except Exception:
        return

    payload = {
        "event": event,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }

    for wh in webhooks:
        try:
            events = json.loads(wh.events or '[]')
            if event in events or "*" in events:
                _send_webhook(wh.url, payload, wh.secret or "")
        except Exception:
            continue
