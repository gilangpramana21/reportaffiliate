"""
TikTok scraper menggunakan Playwright.
Scrape views, likes, comments dari profil TikTok creator berdasarkan username.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoStats:
    url: str
    views: int = 0
    likes: int = 0
    comments: int = 0


@dataclass
class CreatorEngagement:
    username: str
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    video_count: int = 0
    error: Optional[str] = None
    videos: list[VideoStats] = field(default_factory=list)


def _parse_count(text: str) -> int:
    """Parse TikTok count string ke int. Contoh: '1.2M' -> 1200000, '3.4K' -> 3400"""
    if not text:
        return 0
    text = text.strip().replace(',', '').replace(' ', '')
    try:
        if text.upper().endswith('M'):
            return int(float(text[:-1]) * 1_000_000)
        if text.upper().endswith('K'):
            return int(float(text[:-1]) * 1_000)
        if text.upper().endswith('B'):
            return int(float(text[:-1]) * 1_000_000_000)
        return int(float(text))
    except (ValueError, TypeError):
        return 0


async def _scrape_creator_async(
    username: str,
    max_videos: int = 20,
    period_start=None,
    period_end=None,
) -> CreatorEngagement:
    """Scrape engagement data dari profil TikTok creator."""
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

    result = CreatorEngagement(username=username)
    clean_username = username.strip().lstrip('@')
    profile_url = f"https://www.tiktok.com/@{clean_username}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 800},
                locale='id-ID',
            )
            page = await context.new_page()

            # Sembunyikan webdriver flag
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            try:
                await page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(3000)

                # Cek apakah halaman ter-load (bukan CAPTCHA/block)
                title = await page.title()
                if 'captcha' in title.lower() or 'verify' in title.lower():
                    result.error = "TikTok meminta verifikasi CAPTCHA"
                    return result

                # TikTok memblokir scraping profil via headless browser
                # Gunakan link video spesifik dari cell notes Excel untuk hasil yang akurat
                result.error = "Scraping profil tidak didukung (TikTok anti-bot). Pastikan link video ada di kolom LINK VIDEO di spreadsheet."
                return result

                videos_scraped = 0
                for item in video_items[:max_videos]:
                    try:
                        # Ambil link video
                        href = await item.get_attribute('href')
                        if not href:
                            link_el = await item.query_selector('a[href*="/video/"]')
                            if link_el:
                                href = await link_el.get_attribute('href')

                        if not href or '/video/' not in href:
                            continue

                        video_url = href if href.startswith('http') else f"https://www.tiktok.com{href}"

                        # Ambil view count dari thumbnail
                        views = 0
                        view_el = await item.query_selector(
                            '[data-e2e="video-views"], '
                            'strong[class*="video-count"], '
                            'span[class*="SpanVideoCount"]'
                        )
                        if view_el:
                            views_text = await view_el.inner_text()
                            views = _parse_count(views_text)

                        video_stat = VideoStats(url=video_url, views=views)
                        result.videos.append(video_stat)
                        result.total_views += views
                        videos_scraped += 1

                    except Exception:
                        continue

                result.video_count = videos_scraped

                # Untuk likes & comments, perlu buka video satu per satu
                # Ambil dari video pertama saja sebagai sample jika banyak video
                likes_total = 0
                comments_total = 0

                videos_to_detail = result.videos[:min(5, len(result.videos))]
                for vs in videos_to_detail:
                    try:
                        await page.goto(vs.url, wait_until='domcontentloaded', timeout=20000)
                        await page.wait_for_timeout(2000)

                        # Likes
                        like_el = await page.query_selector(
                            '[data-e2e="like-count"], '
                            'strong[data-e2e="like-count"]'
                        )
                        if like_el:
                            vs.likes = _parse_count(await like_el.inner_text())

                        # Comments
                        comment_el = await page.query_selector(
                            '[data-e2e="comment-count"], '
                            'strong[data-e2e="comment-count"]'
                        )
                        if comment_el:
                            vs.comments = _parse_count(await comment_el.inner_text())

                        likes_total += vs.likes
                        comments_total += vs.comments

                        await page.wait_for_timeout(1000)
                    except Exception:
                        continue

                result.total_likes = likes_total
                result.total_comments = comments_total

            except PlaywrightTimeout:
                result.error = f"Timeout saat membuka profil {profile_url}"
            finally:
                await browser.close()

    except Exception as exc:
        result.error = str(exc)

    return result


def scrape_creator(
    username: str,
    max_videos: int = 20,
) -> CreatorEngagement:
    """Synchronous wrapper untuk scrape satu creator."""
    return asyncio.run(_scrape_creator_async(username, max_videos))


def scrape_creators_batch(
    usernames: list[str],
    max_videos: int = 20,
    delay_seconds: float = 2.0,
) -> list[CreatorEngagement]:
    """
    Scrape beberapa creator secara sequential dengan delay antar request
    untuk menghindari rate limiting.
    """
    results = []
    for i, username in enumerate(usernames):
        if i > 0:
            time.sleep(delay_seconds)
        result = scrape_creator(username, max_videos)
        results.append(result)
    return results


async def _scrape_video_urls_async(username: str, video_urls: list[str], cookies_str: str = "") -> CreatorEngagement:
    """Scrape stats dari list URL video TikTok yang spesifik."""
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

    result = CreatorEngagement(username=username)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 800},
                locale='id-ID',
                extra_http_headers={
                    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
            )

            # Inject cookies jika tersedia
            if cookies_str and cookies_str.strip():
                try:
                    import json as _json
                    cookies_list = _json.loads(cookies_str)
                    if isinstance(cookies_list, list):
                        playwright_cookies = []
                        for c in cookies_list:
                            if isinstance(c, dict) and c.get('name') and c.get('value'):
                                cookie = {
                                    'name': c['name'],
                                    'value': c['value'],
                                    'domain': c.get('domain', '.tiktok.com'),
                                    'path': c.get('path', '/'),
                                }
                                playwright_cookies.append(cookie)
                        if playwright_cookies:
                            await context.add_cookies(playwright_cookies)
                except Exception:
                    try:
                        playwright_cookies = []
                        for part in cookies_str.split(';'):
                            part = part.strip()
                            if '=' in part:
                                name, value = part.split('=', 1)
                                playwright_cookies.append({
                                    'name': name.strip(),
                                    'value': value.strip(),
                                    'domain': '.tiktok.com',
                                    'path': '/',
                                })
                        if playwright_cookies:
                            await context.add_cookies(playwright_cookies)
                    except Exception:
                        pass

            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            for url in video_urls:
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    # Tunggu konten video load
                    try:
                        await page.wait_for_selector('[data-e2e="like-count"], [data-e2e="browse-like-count"]', timeout=8000)
                    except Exception:
                        await page.wait_for_timeout(4000)

                    vs = VideoStats(url=url)

                    # Likes — coba berbagai selector
                    for sel in [
                        '[data-e2e="like-count"]',
                        '[data-e2e="browse-like-count"]',
                        'strong[data-e2e="like-count"]',
                        'button[data-e2e="like-icon"] strong',
                    ]:
                        el = await page.query_selector(sel)
                        if el:
                            text = await el.inner_text()
                            if text and text.strip():
                                vs.likes = _parse_count(text.strip())
                                break

                    # Comments — coba berbagai selector
                    for sel in [
                        '[data-e2e="comment-count"]',
                        '[data-e2e="browse-comment-count"]',
                        'strong[data-e2e="comment-count"]',
                        'button[data-e2e="comment-icon"] strong',
                    ]:
                        el = await page.query_selector(sel)
                        if el:
                            text = await el.inner_text()
                            if text and text.strip():
                                vs.comments = _parse_count(text.strip())
                                break

                    # Views — dari JSON embedded di HTML
                    import re as _re2
                    html_content = await page.content()
                    play_matches = _re2.findall(r'"playCount"\s*:\s*(\d+)', html_content)
                    if play_matches:
                        vs.views = int(play_matches[0])
                    else:
                        play_matches2 = _re2.findall(r'"play_count"\s*:\s*(\d+)', html_content)
                        if play_matches2:
                            vs.views = int(play_matches2[0])
                        else:
                            # Fallback: cari di meta tags
                            play_matches3 = _re2.findall(r'"stats":\{"playCount":(\d+)', html_content)
                            if play_matches3:
                                vs.views = int(play_matches3[0])

                    result.videos.append(vs)
                    result.total_views += vs.views
                    result.total_likes += vs.likes
                    result.total_comments += vs.comments
                    result.video_count += 1

                    await page.wait_for_timeout(1500)
                except Exception as e:
                    # Lanjut ke video berikutnya meski satu gagal
                    continue

            await browser.close()

            # Set error hanya jika tidak ada data sama sekali
            if result.video_count == 0 and not result.total_views:
                result.error = "Tidak dapat mengambil data dari TikTok. Coba tambahkan cookies TikTok di halaman Settings."

    except Exception as exc:
        result.error = str(exc)

    return result


def scrape_video_urls(username: str, video_urls: list[str], cookies_str: str = "") -> CreatorEngagement:
    """Scrape engagement dari list URL video spesifik."""
    return asyncio.run(_scrape_video_urls_async(username, video_urls, cookies_str))


async def _scrape_batch_async(
    creator_url_map: dict[str, list[str]],
    cookies_str: str = "",
    progress_callback=None,
) -> list[CreatorEngagement]:
    """
    Scrape banyak creator dengan 1 browser yang sama (lebih efisien).
    creator_url_map: {username: [url1, url2, ...]}
    Mengembalikan list CreatorEngagement.
    """
    from playwright.async_api import async_playwright
    import re as _re

    results: list[CreatorEngagement] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 800},
                locale='id-ID',
            )

            # Inject cookies
            if cookies_str and cookies_str.strip():
                try:
                    import json as _json
                    cookies_list = _json.loads(cookies_str)
                    if isinstance(cookies_list, list):
                        pw_cookies = [
                            {'name': c['name'], 'value': c['value'],
                             'domain': c.get('domain', '.tiktok.com'), 'path': c.get('path', '/')}
                            for c in cookies_list if c.get('name') and c.get('value')
                        ]
                        if pw_cookies:
                            await context.add_cookies(pw_cookies)
                except Exception:
                    pass

            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            for username, video_urls in creator_url_map.items():
                result = CreatorEngagement(username=username)

                for url in video_urls:
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=25000)
                        try:
                            await page.wait_for_selector(
                                '[data-e2e="like-count"], [data-e2e="browse-like-count"]',
                                timeout=6000
                            )
                        except Exception:
                            await page.wait_for_timeout(3000)

                        vs = VideoStats(url=url)

                        for sel in ['[data-e2e="like-count"]', '[data-e2e="browse-like-count"]',
                                    'strong[data-e2e="like-count"]']:
                            el = await page.query_selector(sel)
                            if el:
                                t = await el.inner_text()
                                if t and t.strip():
                                    vs.likes = _parse_count(t.strip())
                                    break

                        for sel in ['[data-e2e="comment-count"]', '[data-e2e="browse-comment-count"]',
                                    'strong[data-e2e="comment-count"]']:
                            el = await page.query_selector(sel)
                            if el:
                                t = await el.inner_text()
                                if t and t.strip():
                                    vs.comments = _parse_count(t.strip())
                                    break

                        html = await page.content()
                        for pat in [r'"playCount"\s*:\s*(\d+)', r'"play_count"\s*:\s*(\d+)',
                                    r'"stats":\{"playCount":(\d+)']:
                            m = _re.search(pat, html)
                            if m:
                                vs.views = int(m.group(1))
                                break

                        result.videos.append(vs)
                        result.total_views += vs.views
                        result.total_likes += vs.likes
                        result.total_comments += vs.comments
                        result.video_count += 1

                        # Delay lebih pendek karena reuse browser (sudah warm)
                        await page.wait_for_timeout(800)

                    except Exception:
                        continue

                if result.video_count == 0:
                    result.error = "Tidak ada data"

                results.append(result)

                if progress_callback:
                    progress_callback(username, result)

            await browser.close()

    except Exception as exc:
        # Jika browser crash, return hasil yang sudah ada
        pass

    return results


def scrape_batch(
    creator_url_map: dict[str, list[str]],
    cookies_str: str = "",
    progress_callback=None,
) -> list[CreatorEngagement]:
    """Scrape banyak creator dengan 1 browser (lebih efisien dari scrape satu per satu)."""
    return asyncio.run(_scrape_batch_async(creator_url_map, cookies_str, progress_callback))
