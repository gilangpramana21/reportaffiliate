"""
TikTok scraper endpoints.

POST /api/scrape/engagement      — scrape engagement dari list username
GET  /api/scrape/status/<job_id> — cek status scraping job
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
import concurrent.futures

from flask import Blueprint, jsonify, request

scraper_bp = Blueprint("scraper", __name__, url_prefix="/api")

# In-memory jobs dict (per worker)
_jobs: dict[str, dict] = {}

# File-based job storage untuk cross-worker access
_JOBS_DIR = "uploads/.scrape_jobs"
_jobs_lock = threading.Lock()


def _job_file(job_id: str) -> str:
    return os.path.join(_JOBS_DIR, f"{job_id}.json")


def _save_job(job_id: str, job: dict):
    """Simpan job status ke disk (tanpa video_links_map dan tiktok_cookies untuk hemat space)."""
    try:
        os.makedirs(_JOBS_DIR, exist_ok=True)
        payload = {
            "status": job["status"],
            "total": job["total"],
            "done": job["done"],
            "results": job["results"],
            "error": job["error"],
        }
        with open(_job_file(job_id), 'w') as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        print(f"[SCRAPER] Warning: failed to save job {job_id}: {e}", file=sys.stderr)


def _load_job(job_id: str) -> dict | None:
    """Load job dari disk jika tidak ada di memory."""
    try:
        path = _job_file(job_id)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _cleanup_old_jobs():
    """Hapus job files yang lebih dari 2 jam."""
    try:
        import time
        now = time.time()
        for fname in os.listdir(_JOBS_DIR):
            fpath = os.path.join(_JOBS_DIR, fname)
            if os.path.getmtime(fpath) < now - 7200:
                os.remove(fpath)
    except Exception:
        pass


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
    
    # Simpan ke disk untuk cross-worker access
    _save_job(job_id, _jobs[job_id])
    _cleanup_old_jobs()

    thread = threading.Thread(
        target=_run_scrape_job,
        args=(job_id, usernames, max_videos),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "total": len(usernames)}), 202


@scraper_bp.route("/scrape/status/<job_id>", methods=["GET"])
def scrape_status(job_id: str):
    # Selalu coba baca dari disk dulu (paling fresh, cross-worker)
    job = _load_job(job_id)
    
    # Fallback ke memory jika file belum ada (baru saja dibuat)
    if job is None:
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
    import time

    job = _jobs[job_id]
    video_links_map = job["video_links_map"]
    tiktok_cookies = job["tiktok_cookies"]
    use_echotik = job["use_echotik"]
    use_cookies = bool(tiktok_cookies.strip())

    print(f"[SCRAPER] {len(usernames)} users, cookies={len(tiktok_cookies)}, echotik={use_echotik}", file=sys.stderr)
    print(f"[SCRAPER] video_links_map keys ({len(video_links_map)}): {list(video_links_map.keys())[:5]}", file=sys.stderr)
    print(f"[SCRAPER] usernames sample: {usernames[:5]}", file=sys.stderr)
    # Cek apakah username ada di video_links_map
    matched = [u for u in usernames if video_links_map.get(u)]
    print(f"[SCRAPER] usernames with links: {len(matched)}/{len(usernames)} -> {matched[:5]}", file=sys.stderr)

    results = [None] * len(usernames)
    done_count = 0
    lock = threading.Lock()
    last_update_time = time.time()

    def update_result(idx, data):
        nonlocal done_count, last_update_time
        results[idx] = data
        with lock:
            done_count += 1
            last_update_time = time.time()
            job["done"] = done_count
            job["results"] = [r for r in results if r is not None]
            # Simpan progress ke disk setiap update agar cross-worker sync
            _save_job(job_id, job)
            print(f"[SCRAPER] Progress: {done_count}/{len(usernames)} ({data.get('username', 'unknown')})", file=sys.stderr)

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
                    idx, data = future.result(timeout=120)  # Timeout per creator
                    update_result(idx, data)
                except concurrent.futures.TimeoutError:
                    # Timeout untuk creator ini
                    idx = futures[future]
                    username = usernames[idx]
                    print(f"[SCRAPER] Timeout for {username}", file=sys.stderr)
                    update_result(idx, {"username": username, "total_views": 0, "total_likes": 0,
                                       "total_comments": 0, "video_count": 0, "error": "timeout"})
                except Exception as e:
                    print(f"[SCRAPER] Exception in future: {e}", file=sys.stderr)
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

            try:
                scrape_batch(
                    url_map,
                    cookies_str=tiktok_cookies if use_cookies else "",
                    progress_callback=on_progress,
                )
            except Exception as e:
                print(f"[SCRAPER] scrape_batch exception: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

        t1 = threading.Thread(target=run_chunk, args=(chunks[0],), daemon=True)
        t2 = threading.Thread(target=run_chunk, args=(chunks[1],), daemon=True)
        t1.start()
        t2.start()
        
        # Join dengan timeout untuk menghindari stuck forever
        # Timeout: 60 detik per creator (konservatif)
        timeout_per_creator = 60
        total_timeout = max(300, len(usernames) * timeout_per_creator)  # Minimal 5 menit
        
        t1.join(timeout=total_timeout)
        t2.join(timeout=total_timeout)
        
        # Cek apakah thread masih hidup (stuck)
        if t1.is_alive() or t2.is_alive():
            print(f"[SCRAPER] Warning: Thread timeout after {total_timeout}s, some results may be incomplete", file=sys.stderr)
            job["error"] = f"Scraping timeout setelah {total_timeout}s. Beberapa hasil mungkin tidak lengkap."

        # Fill any remaining None slots
        for i, u in enumerate(usernames):
            if results[i] is None:
                results[i] = {"username": u, "total_views": 0, "total_likes": 0,
                              "total_comments": 0, "video_count": 0, "error": "timeout atau skip"}

    job["results"] = [r for r in results if r is not None]
    job["done"] = len(usernames)
    job["status"] = "done"
    _save_job(job_id, job)
    print(f"[SCRAPER] Job {job_id} completed: {len(job['results'])} results", file=sys.stderr)


@scraper_bp.route("/scrape/config", methods=["GET"])
def scrape_config():
    use_echotik = bool(os.environ.get("ECHOTIK_USERNAME", ""))
    return jsonify({
        "method": "echotik" if use_echotik else "playwright",
        "echotik_configured": use_echotik,
    }), 200
