# Perbaikan Parsing Link Video yang Bersambungan

## Masalah
Beberapa link video di Excel tidak terbaca dengan baik karena:
1. Link yang langsung bersambungan tanpa separator (contoh: `https://...video/123https://...video/456`)
2. Link yang dipisahkan dengan karakter aneh atau underscore
3. Multiple URLs dalam satu cell tanpa pemisah yang jelas

## Contoh Kasus dari Excel
```
https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448?_https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID
```

Link di atas seharusnya 2 link terpisah:
1. `https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448`
2. `https://www.tiktok.com/@dailyliyaa/video/7633063068888485127?shop_region=ID`

## Solusi yang Diterapkan

### 1. Perbaikan Fungsi `_clean_url`
- Mendeteksi jika ada URL lain yang langsung bersambung
- Memotong URL di titik di mana URL berikutnya dimulai
- Membersihkan trailing underscore dan karakter aneh

```python
def _clean_url(url: str) -> str:
    # Potong jika ada URL lain yang langsung bersambung
    next_url = _re.search(r'(https?://)', url[8:])  # Skip first https://
    if next_url:
        url = url[:8 + next_url.start()]
    
    # Hapus trailing punctuation dan underscore
    url = url.rstrip('.,;:!?_')
    url = _re.sub(r'[_\-]+$', '', url)
```

### 2. Perbaikan Fungsi `_extract_urls_from_text`
Menambahkan Method 2 baru untuk menangani URL yang bersambungan:

```python
# Method 2: Handle concatenated URLs
if 'httpshttps' in text.lower() or text.count('https://') > len(urls):
    # Split by 'https://' and reconstruct URLs
    parts = text.split('https://')
    for i, part in enumerate(parts):
        if i == 0 and not part.startswith('http'):
            continue
        
        url = 'https://' + part
        
        # Find where this URL ends
        next_url_match = _re.search(r'(https?://)', url[8:])
        if next_url_match:
            url = url[:8 + next_url_match.start()]
        
        cleaned = _clean_url(url)
        if cleaned and 'tiktok' in cleaned.lower() and cleaned not in urls:
            urls.append(cleaned)
```

## Cara Kerja

1. **Deteksi URL Bersambungan**: Cek apakah ada pattern `httpshttps` atau jumlah `https://` lebih banyak dari URL yang terdeteksi
2. **Split by https://**: Pisahkan text berdasarkan `https://`
3. **Rekonstruksi URL**: Gabungkan kembali setiap bagian dengan `https://`
4. **Potong di URL Berikutnya**: Jika ada URL lain yang bersambung, potong di titik tersebut
5. **Clean URL**: Bersihkan trailing characters dan validasi

## Testing

Untuk test perbaikan ini:

1. Upload file Excel yang bermasalah
2. Klik **Apply Mapping**
3. Periksa di tabel apakah semua link video terdeteksi dengan benar
4. Klik expand (>) pada creator yang punya multiple videos
5. Pastikan setiap link terpisah dengan baik

## Contoh Output yang Diharapkan

**Sebelum perbaikan:**
- Row 26 (@ibunya.ehan): 1 link (salah, seharusnya 2)
- Link: `https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448?_https://...` (rusak)

**Setelah perbaikan:**
- Row 26 (@ibunya.ehan): 2 links
- Link 1: `https://www.tiktok.com/@ibunya.ehan/video/7632124375688547592`
- Link 2: `https://www.tiktok.com/@ibunya.ehan/video/7633013465635933448`

## File yang Dimodifikasi
- `app/services/data_parser.py` - Fungsi `_extract_cell_notes`, `_clean_url`, dan `_extract_urls_from_text`

## Catatan
- Perbaikan ini backward compatible - tidak akan merusak parsing link yang sudah benar
- Jika masih ada link yang tidak terbaca, pastikan link di Excel memiliki format yang valid
- Untuk hasil terbaik, pisahkan link dengan newline atau koma di Excel
