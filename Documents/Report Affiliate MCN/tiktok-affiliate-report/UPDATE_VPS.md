# 🚀 Panduan Update Aplikasi di VPS

## ✅ Status Push ke GitHub

### Update 1: Perbaikan Link Parsing
- **Commit:** bf71b7a
- **Fitur:** Parsing link video yang bersambungan

### Update 2: Perbaikan Scraping Stuck ⭐ TERBARU
- **Commit:** 19a5b55
- **Fitur:** Fix scraping yang stuck/berhenti di tengah jalan
- **Branch:** main
- **Repository:** https://github.com/gilangpramana21/reportaffiliate.git

## 📋 File yang Diupdate:

### Update 1 (bf71b7a):
1. `app/services/data_parser.py` - Perbaikan parsing link video
2. `PANDUAN_LENGKAP_DOCS.html` - Update dokumentasi
3. `PERBAIKAN_LINK_PARSING.md` - Dokumentasi teknis
4. `RINGKASAN_PERBAIKAN.md` - Panduan lengkap
5. `test_link_parsing.py` - Test script

### Update 2 (19a5b55): ⭐ TERBARU
1. `app/services/tiktok_scraper.py` - Timeout lebih pendek, better error handling
2. `app/routes/scraper.py` - Thread timeout, progress logging
3. `PERBAIKAN_SCRAPING_STUCK.md` - Dokumentasi perbaikan scraping

---

## 🔄 Cara Update di VPS

### Step 1: Login ke VPS
```bash
ssh root@72.62.244.186
```

### Step 2: Masuk ke Folder Aplikasi
```bash
cd /var/www/tiktok-affiliate-report
```

### Step 3: Backup (Opsional tapi Recommended)
```bash
# Backup file yang akan diupdate
cp app/services/data_parser.py app/services/data_parser.py.backup
```

### Step 4: Pull Perubahan dari GitHub
```bash
git pull origin main
```

**Expected Output:**
```
remote: Enumerating objects: 19, done.
remote: Counting objects: 100% (19/19), done.
remote: Compressing objects: 100% (7/7), done.
remote: Total 12 (delta 4), reused 12 (delta 4), pack-reused 0
Unpacking objects: 100% (12/12), done.
From https://github.com/gilangpramana21/reportaffiliate
   2001265..bf71b7a  main       -> origin/main
Updating 2001265..bf71b7a
Fast-forward
 app/services/data_parser.py      | 58 ++++++++++++++++++++++++++++++++++++++++
 PANDUAN_LENGKAP_DOCS.html        | 123 +++++++++++++++++++++++++++++++++
 PERBAIKAN_LINK_PARSING.md        | 156 ++++++++++++++++++++++++++++++++++++++++
 RINGKASAN_PERBAIKAN.md           | 234 ++++++++++++++++++++++++++++++++++++++++++++
 test_link_parsing.py             | 118 +++++++++++++++++++++++++++++
 5 files changed, 689 insertions(+)
```

### Step 5: Set Permission (Jika Perlu)
```bash
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 755 /var/www/tiktok-affiliate-report
```

### Step 6: Restart Aplikasi
```bash
systemctl restart tiktok-affiliate
```

### Step 7: Cek Status
```bash
systemctl status tiktok-affiliate
```

**Expected Output:**
```
● tiktok-affiliate.service - TikTok Affiliate Report Gunicorn Service
   Loaded: loaded (/etc/systemd/system/tiktok-affiliate.service; enabled)
   Active: active (running) since Thu 2026-04-30 XX:XX:XX UTC
```

### Step 8: Monitor Log (Opsional)
```bash
# Monitor log real-time
journalctl -u tiktok-affiliate -f

# Atau cek error log
tail -f /var/www/tiktok-affiliate-report/logs/error.log
```

---

## ✅ Verifikasi Update Berhasil

### 1. Cek Aplikasi Berjalan
```bash
curl http://localhost:8080
```

Jika berhasil, akan muncul HTML response.

### 2. Test dari Browser
Buka: `http://72.62.244.186:8082`

### 3. Test Parsing Link
1. Upload file Excel yang bermasalah
2. Klik **Apply Mapping**
3. Periksa apakah link yang bersambungan terdeteksi dengan benar
4. Klik expand (>) pada creator dengan multiple videos
5. Pastikan semua link terpisah dengan baik

### 4. Test dengan File Lama
Jika ada file yang sudah diupload sebelumnya:
1. Klik tombol **Re-parse File**
2. Klik **Apply Mapping** ulang
3. Periksa hasilnya

---

## 🔧 Troubleshooting

### Masalah: Git pull gagal dengan "error: Your local changes..."
**Solusi:**
```bash
# Stash perubahan lokal
git stash

# Pull ulang
git pull origin main

# Restore perubahan lokal (jika perlu)
git stash pop
```

### Masalah: Service gagal restart
**Solusi:**
```bash
# Cek error detail
journalctl -u tiktok-affiliate -n 50 --no-pager

# Cek syntax error Python
cd /var/www/tiktok-affiliate-report
sudo -u www-data venv/bin/python3 -m py_compile app/services/data_parser.py
```

### Masalah: Permission denied
**Solusi:**
```bash
# Fix permission
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 755 /var/www/tiktok-affiliate-report
chmod -R 775 /var/www/tiktok-affiliate-report/uploads
chmod -R 775 /var/www/tiktok-affiliate-report/reports
chmod -R 775 /var/www/tiktok-affiliate-report/logs
chmod -R 775 /var/www/tiktok-affiliate-report/instance
```

### Masalah: Port 8082 tidak bisa diakses
**Solusi:**
```bash
# Cek apakah Nginx berjalan
systemctl status nginx

# Restart Nginx jika perlu
systemctl restart nginx

# Cek firewall
ufw status
```

---

## 📝 Catatan Penting

1. **Backup Selalu**: Sebelum update, backup file penting
2. **Test Dulu**: Test di local sebelum deploy ke production
3. **Monitor Log**: Pantau log setelah restart untuk memastikan tidak ada error
4. **Rollback Plan**: Jika ada masalah, restore dari backup:
   ```bash
   cp app/services/data_parser.py.backup app/services/data_parser.py
   systemctl restart tiktok-affiliate
   ```

---

## 🎯 Quick Commands

```bash
# One-liner untuk update cepat
ssh root@72.62.244.186 "cd /var/www/tiktok-affiliate-report && git pull origin main && systemctl restart tiktok-affiliate && systemctl status tiktok-affiliate"
```

---

## 📞 Jika Ada Masalah

1. Cek log error: `journalctl -u tiktok-affiliate -n 100`
2. Cek file syntax: `python3 -m py_compile app/services/data_parser.py`
3. Rollback ke backup jika perlu
4. Contact developer

---

**Last Updated:** 30 April 2026  
**Commit Hash:** bf71b7a  
**Status:** ✅ Ready to Deploy
