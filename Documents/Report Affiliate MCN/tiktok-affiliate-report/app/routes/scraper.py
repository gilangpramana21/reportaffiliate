"""
TikTok scraper endpoints.

POST /api/scrape/engagement      — scrape engagement dari list username
GET  /api/scrape/status/<job_id> — cek status scraping job
"""
from __future__ import annotations

import os
import sys
import threading
import uuid
import concurrent.futures

from flask import Blueprint, jsonify, request

scraper_bp = Blueprint("scraper", __name__, url_prefix="/api")

_jobs: dict[str, dict] = {}


@scraper_bp.route("/scrape/engagement", methods=["POST"])
def start_scrape():
    body = request.get_json(silent=True) or {}
    usernames = body.get("usernames", [])
    max_videos = int(body.get("max_videos", 20))
    video_links_map = body.get("video_links_map", {})

    if not usernames or not isinstance(usernames, list):
        return jsonify({"error": "Field 'usernames' wajib diisi sebagai array"}), 400

    usernames = [u.strip().lstrip('@') for u in usernames if u and u.strip()]
    if not usernames:
        return jsonify({"error": "Tidak ada username valid"}), 400

    print(f"[SCRAPER] Starting job: {len(usernames)} users, links: {len(video_links_map)}", file=sys.stderr)

    job_id = uuid.uuid4().hex

    tiktok_cookies = ""
    try:
        from app.routes.settings import _get_setting
        tiktok_cookies = _get_setting("tiktok_cookies", "")
    except Exception:
        pass

    use_echotik = bool(os.environ.get("ECHOTIK_USERNAME", ""))

    _jobs[job_id] = {
        "status": "running",
        "total": len(usernames),
        "done": 0,
        "results": [],
        "error": None,
        "video_links_map": video_links_map,
        "tiktok_cookies": tiktok_cookies,
        "use_echotik": use_echotik,
    }

    thread = threading.Thread(
        target=_run_scrape_job,
        args=(job_id, usernames, max_videos),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "total": len(usernames)}), 202


@scraper_bp.route("/scrape/status/<job_id>", methods=["GET"])
def scrape_status(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": f"job_id '{job_id}' tidak ditemukan"}), 404

    return jsonify({
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "results": job["results"],
        "error": job["error"],
    }), 200


def _make_result(username, r):
    """Convert CreatorEngagement to dict."""
    has_data = r.total_views > 0 or r.total_likes > 0 or r.total_comments > 0
    # Include per-video breakdown
    videos = []
    for v in (r.videos or []):
        if v.views > 0 or v.likes > 0 or v.comments > 0:
            videos.append({
                "url": v.url,
                "views": v.views,
                "likes": v.likes,
                "comments": v.comments,
            })
    return {
        "username": r.username,
        "total_views": r.total_views,
        "total_likes": r.total_likes,
        "total_comments": r.total_comments,
        "video_count": r.video_count,
        "videos": videos,
        "error": None if has_data else r.error,
    }


def _run_scrape_job(job_id: str, usernames: list[str], max_videos: int):
    from app.services.tiktok_scraper import scrape_video_urls, scrape_batch
    from app.services.echotik_service import get_echotik_service

    job = _jobs[job_id]
    video_links_map = job["video_links_map"]
    tiktok_cookies = job["tiktok_cookies"]
    use_echotik = job["use_echotik"]
    use_cookies = bool(tiktok_cookies.strip())

    print(f"[SCRAPER] {len(usernames)} users, cookies={len(tiktok_cookies)}, echotik={use_echotik}", file=sys.stderr)

    results = [None] * len(usernames)
    done_count = 0
    lock = threading.Lock()

    def update_result(idx, data):
        nonlocal done_count
        results[idx] = data
        with lock:
            done_count += 1
            job["done"] = done_count
            job["results"] = [r for r in results if r is not None]

    if use_echotik:
        # EchoTik: paralel via ThreadPoolExecutor
        def scrape_one_echotik(args):
            idx, username = args
            links = video_links_map.get(username, [])
            if not links:
                return idx, {"username": username, "total_views": 0, "total_likes": 0,
                             "total_comments": 0, "video_count": 0, "error": "skip"}
            try:
                svc = get_echotik_service()
                eng = svc.get_engagement_for_video_urls(username, links)
                return idx, _make_result(username, eng)
            except Exception as exc:
                return idx, {"username": username, "total_views": 0, "total_likes": 0,
                             "total_comments": 0, "video_count": 0, "error": str(exc)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(scrape_one_echotik, (i, u)): i
                       for i, u in enumerate(usernames)}
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, data = future.result()
                    update_result(idx, data)
                except Exception:
                    pass

    else:
        # Playwright: 2 browser paralel, tiap browser handle setengah creator
        half = max(1, len(usernames) // 2)
        chunks = [usernames[:half], usernames[half:]]

        def make_url_map(chunk):
            return {u: video_links_map.get(u, []) for u in chunk if video_links_map.get(u)}

        def run_chunk(chunk):
            url_map = make_url_map(chunk)

            # Mark creators without links as skip immediately
            for u in chunk:
                if u not in url_map:
                    idx = next((i for i, un in enumerate(usernames) if un == u), -1)
                    if idx >= 0:
                        update_result(idx, {"username": u, "total_views": 0, "total_likes": 0,
                                            "total_comments": 0, "video_count": 0, "error": "skip"})

            if not url_map:
                return

            def on_progress(username, result):
                idx = next((i for i, u in enumerate(usernames) if u == username), -1)
                if idx >= 0:
                    update_result(idx, _make_result(username, result))

            scrape_batch(
                url_map,
                cookies_str=tiktok_cookies if use_cookies else "",
                progress_callback=on_progress,
            )

        t1 = threading.Thread(target=run_chunk, args=(chunks[0],), daemon=True)
        t2 = threading.Thread(target=run_chunk, args=(chunks[1],), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Fill any remaining None slots
        for i, u in enumerate(usernames):
            if results[i] is None:
                results[i] = {"username": u, "total_views": 0, "total_likes": 0,
                              "total_comments": 0, "video_count": 0, "error": "skip"}

    job["results"] = [r for r in results if r is not None]
    job["done"] = len(usernames)
    job["status"] = "done"


@scraper_bp.route("/scrape/config", methods=["GET"])
def scrape_config():
    use_echotik = bool(os.environ.get("ECHOTIK_USERNAME", ""))
    return jsonify({
        "method": "echotik" if use_echotik else "playwright",
        "echotik_configured": use_echotik,
    }), 200
