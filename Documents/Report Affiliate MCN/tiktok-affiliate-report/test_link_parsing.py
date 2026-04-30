#!/usr/bin/env python3
"""
Test script untuk memverifikasi perbaikan parsing link yang bersambungan.
"""

import re

def test_url_extraction():
    """Test ekstraksi URL yang bersambungan."""
    
    # Pattern untuk mendeteksi TikTok URLs
    _url_re = re.compile(r'https?://[^\s,;"<>\n\r]+tiktok[^\s,;"<>\n\r]*', re.IGNORECASE)
    
    def _clean_url(url: str) -> str:
        """Bersihkan URL dari suffix tanggal/komentar yang ikut terbawa."""
        url = url.strip()
        # Hapus whitespace dan karakter kontrol
        url = re.sub(r'[\s\r\n\t]+', '', url)
        # Potong di koma pertama jika ada (tanggal sering dipisah koma)
        if ',' in url:
            url = url.split(',')[0].strip()
        
        # Potong jika ada URL lain yang langsung bersambung
        next_url = re.search(r'(https?://)', url[8:])  # Skip first https://
        if next_url:
            url = url[:8 + next_url.start()]
        
        # Hapus trailing punctuation
        url = url.rstrip('.,;:!?_')
        
        # Pastikan URL valid
        if not url.startswith('http'):
            return ''
        if 'tiktok' not in url.lower():
            return ''
        
        # Hapus trailing underscore atau karakter aneh di akhir
        url = re.sub(r'[_\-]+$', '', url)
        
        return url
    
    def _extract_urls_from_text(text: str) -> list[str]:
        """Ekstrak semua TikTok URLs dari text, handling multiple separators."""
        if not text:
            return []
        
        urls = []
        
        # Method 1: Regex extraction
        found_urls = _url_re.findall(text)
        for url in found_urls:
            cleaned = _clean_url(url)
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
        
        # Method 2: Handle concatenated URLs
        if 'httpshttps' in text.lower() or text.count('https://') > len(urls):
            parts = text.split('https://')
            for i, part in enumerate(parts):
                if i == 0 and not part.startswith('http'):
                    continue
                
                url = 'https://' + part
                
                # Find where this URL ends
                next_url_match = re.search(r'(https?://)', url[8:])
                if next_url_match:
                    url = url[:8 + next_url_match.start()]
                
                cleaned = _clean_url(url)
                if cleaned and 'tiktok' in cleaned.lower() and cleaned not in urls:
                    urls.append(cleaned)
        
        # Method 3: Split by newline/comma
        if not urls:
            parts = re.split(r'[\n\r,;]+', text)
            for part in parts:
                part = part.strip()
                if 'tiktok' in part.lower() and part.startswith('http'):
                    cleaned = _clean_url(part)
                    if cleaned and cleaned not in urls:
                        urls.append(cleaned)
        
        return urls
    
    # Test cases
    test_cases = [
        {
            'name': 'URL bersambungan dengan ?_',
            'input': 'https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448?_https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID',
            'expected': [
                'https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448',
                'https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID'
            ]
        },
        {
            'name': 'URL bersambungan tanpa separator',
            'input': 'https://www.tiktok.com/@user1/video/123456https://www.tiktok.com/@user2/video/789012',
            'expected': [
                'https://www.tiktok.com/@user1/video/123456',
                'https://www.tiktok.com/@user2/video/789012'
            ]
        },
        {
            'name': 'URL dengan trailing underscore',
            'input': 'https://www.tiktok.com/@jollashope/video/7631585336346545429?_',
            'expected': [
                'https://www.tiktok.com/@jollashope/video/7631585336346545429'
            ]
        },
        {
            'name': 'Multiple URLs dengan newline',
            'input': 'https://www.tiktok.com/@user1/video/123\nhttps://www.tiktok.com/@user2/video/456',
            'expected': [
                'https://www.tiktok.com/@user1/video/123',
                'https://www.tiktok.com/@user2/video/456'
            ]
        },
        {
            'name': 'URL dengan shop_region parameter',
            'input': 'https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID',
            'expected': [
                'https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID'
            ]
        },
        {
            'name': 'vt.tiktok.com short links',
            'input': 'https://vt.tiktok.com/ZS9DhfK9h/',
            'expected': [
                'https://vt.tiktok.com/ZS9DhfK9h/'
            ]
        },
        {
            'name': 'Multiple vt.tiktok.com links',
            'input': 'https://vt.tiktok.com/ZS9A8Qnrx/https://vt.tiktok.com/ZS9A84rwW/https://vt.tiktok.com/ZS9A84sWe/',
            'expected': [
                'https://vt.tiktok.com/ZS9A8Qnrx/',
                'https://vt.tiktok.com/ZS9A84rwW/',
                'https://vt.tiktok.com/ZS9A84sWe/'
            ]
        }
    ]
    
    print("=" * 80)
    print("TEST PARSING LINK VIDEO YANG BERSAMBUNGAN")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"Input: {test['input'][:100]}...")
        
        result = _extract_urls_from_text(test['input'])
        
        print(f"Expected: {len(test['expected'])} URLs")
        for url in test['expected']:
            print(f"  - {url}")
        
        print(f"Got: {len(result)} URLs")
        for url in result:
            print(f"  - {url}")
        
        if result == test['expected']:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            failed += 1
            
            # Show differences
            missing = set(test['expected']) - set(result)
            extra = set(result) - set(test['expected'])
            
            if missing:
                print(f"Missing URLs: {missing}")
            if extra:
                print(f"Extra URLs: {extra}")
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return failed == 0

if __name__ == '__main__':
    success = test_url_extraction()
    exit(0 if success else 1)
