"""
EchoTik API Service — ambil views, likes, comments per video TikTok.
Dokumentasi: https://opendocs.echotik.live
"""
from __future__ import annotations

import os
import re
import urllib.request
import urllib.parse
import urllib.error
import json
import base64
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoEngagement:
    video_id: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


@dataclass
class CreatorEngagementResult:
    username: str
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    video_count: int = 0
    videos: list[VideoEngagement] = field(default_factory=list)
    error: Optional[str] = None


class EchoTikService:
    BASE_URL = "https://open.echotik.live"

    def __init__(self, username: str = "", password: str = ""):
        self.username = username or os.environ.get("ECHOTIK_USERNAME", "")
        self.password = password or os.environ.get("ECHOTIK_PASSWORD", "")
        _creds = f"{self.username}:{self.password}"
        self._auth = "Basic " + base64.b64encode(_creds.encode()).decode()

    def _request(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": self._auth,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            raise Exception(f"HTTP {e.code}: {body[:300]}")

    def _resolve_video_id(self, url: str) -> str:
        """Resolve vt.tiktok.com dan ekstrak video ID."""
        if 'vt.tiktok.com' in url or 'vm.tiktok.com' in url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=10)
                url = resp.url
            except Exception:
                pass
        m = re.search(r'/video/(\d+)', url)
        return m.group(1) if m else ""

    def get_creator_videos(self, unique_id: str, page_size: int = 20) -> list[VideoEngagement]:
        """Ambil list video creator beserta stats dari EchoTik."""
        data = self._request("/api/v3/echotik/influencer/video/list", {
            "unique_id": unique_id.lstrip("@"),
            "page_num": 1,
            "page_size": page_size,
            "influencer_video_sort_field": 4,  # sort by create_time
            "sort_type": 1,  # desc
        })
        videos = []
        if data.get("code") == 0:
            for v in (data.get("data") or []):
                videos.append(VideoEngagement(
                    video_id=str(v.get("video_id", "")),
                    views=int(v.get("total_views_cnt", 0) or 0),
                    likes=int(v.get("total_digg_cnt", 0) or 0),
                    comments=int(v.get("total_comments_cnt", 0) or 0),
                    shares=int(v.get("total_shares_cnt", 0) or 0),
                ))
        return videos

    def get_videos_by_ids(self, video_ids: list[str], region: str = "ID") -> list[VideoEngagement]:
        """Ambil stats video langsung berdasarkan video IDs via EchoTik video/detail endpoint."""
        if not video_ids:
            return []
        data = self._request("/api/v3/echotik/video/detail", {
            "video_ids": ",".join(video_ids),
        })
        videos = []
        if data.get("code") == 0:
            for v in (data.get("data") or []):
                videos.append(VideoEngagement(
                    video_id=str(v.get("video_id", "")),
                    views=int(v.get("total_views_cnt", 0) or 0),
                    likes=int(v.get("total_digg_cnt", 0) or 0),
                    comments=int(v.get("total_comments_cnt", 0) or 0),
                    shares=int(v.get("total_shares_cnt", 0) or 0),
                ))
        return videos

    def get_engagement_for_video_urls(
        self,
        username: str,
        video_urls: list[str],
    ) -> CreatorEngagementResult:
        """
        Ambil engagement untuk video-video spesifik berdasarkan URL.
        Resolve video IDs dari URLs, lalu fetch langsung via video/list endpoint.
        """
        result = CreatorEngagementResult(username=username)

        # Resolve video IDs dari URLs
        target_ids = []
        for url in video_urls:
            vid = self._resolve_video_id(url)
            if vid:
                target_ids.append(vid)

        if not target_ids:
            result.error = "Tidak dapat resolve video ID dari URL"
            return result

        # Fetch langsung berdasarkan video IDs
        try:
            videos = self.get_videos_by_ids(target_ids)
            for v in videos:
                result.total_views += v.views
                result.total_likes += v.likes
                result.total_comments += v.comments
                result.video_count += 1
                result.videos.append(v)

            # Jika tidak ada yang match, coba via influencer endpoint
            if result.video_count == 0:
                try:
                    all_videos = self.get_creator_videos(username, page_size=50)
                    target_id_set = set(target_ids)
                    for v in all_videos:
                        if v.video_id in target_id_set:
                            result.total_views += v.views
                            result.total_likes += v.likes
                            result.total_comments += v.comments
                            result.video_count += 1
                            result.videos.append(v)
                except Exception:
                    pass

        except Exception as e:
            result.error = str(e)

        return result


_service: Optional[EchoTikService] = None


def get_echotik_service() -> EchoTikService:
    global _service
    if _service is None:
        _service = EchoTikService()
    return _service
