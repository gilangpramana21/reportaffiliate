#!/bin/bash
# Script Deploy Manual ke VPS
# Jalankan script ini di VPS setelah login

set -e

echo "=========================================="
echo "🚀 Deploy TikTok Affiliate Report"
echo "=========================================="
echo ""

# Warna untuk output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Cek apakah di VPS
if [ ! -d "/var/www/tiktok-affiliate-report" ]; then
    echo -e "${RED}❌ Error: Folder /var/www/tiktok-affiliate-report tidak ditemukan${NC}"
    echo "Script ini harus dijalankan di VPS"
    exit 1
fi

cd /var/www/tiktok-affiliate-report

echo -e "${YELLOW}📦 Step 1: Backup file penting...${NC}"
# Backup file yang akan diupdate
cp app/services/data_parser.py app/services/data_parser.py.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp app/services/tiktok_scraper.py app/services/tiktok_scraper.py.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp app/routes/scraper.py app/routes/scraper.py.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
echo -e "${GREEN}✅ Backup selesai${NC}"
echo ""

echo -e "${YELLOW}📥 Step 2: Pull perubahan dari GitHub...${NC}"
git pull origin main
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Git pull gagal${NC}"
    echo "Coba jalankan: git stash && git pull origin main"
    exit 1
fi
echo -e "${GREEN}✅ Pull selesai${NC}"
echo ""

echo -e "${YELLOW}🔧 Step 3: Set permission...${NC}"
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 755 /var/www/tiktok-affiliate-report
chmod -R 775 /var/www/tiktok-affiliate-report/uploads
chmod -R 775 /var/www/tiktok-affiliate-report/reports
chmod -R 775 /var/www/tiktok-affiliate-report/logs
chmod -R 775 /var/www/tiktok-affiliate-report/instance
echo -e "${GREEN}✅ Permission selesai${NC}"
echo ""

echo -e "${YELLOW}🔄 Step 4: Restart aplikasi...${NC}"
systemctl restart tiktok-affiliate
sleep 2
echo -e "${GREEN}✅ Restart selesai${NC}"
echo ""

echo -e "${YELLOW}📊 Step 5: Cek status aplikasi...${NC}"
systemctl status tiktok-affiliate --no-pager -l
echo ""

echo -e "${YELLOW}🧪 Step 6: Test aplikasi...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Aplikasi berjalan dengan baik (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}⚠️  Warning: HTTP response code: $HTTP_CODE${NC}"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}🎉 Deploy Selesai!${NC}"
echo "=========================================="
echo ""
echo "📋 Yang Diupdate:"
echo "  1. Perbaikan link parsing (link bersambungan)"
echo "  2. Perbaikan scraping stuck (timeout & error handling)"
echo ""
echo "🔍 Monitoring:"
echo "  - Akses: http://72.62.244.186:8082"
echo "  - Log: journalctl -u tiktok-affiliate -f"
echo "  - Status: systemctl status tiktok-affiliate"
echo ""
echo "✅ Testing:"
echo "  1. Upload file Excel"
echo "  2. Klik Apply Mapping (cek link terdeteksi)"
echo "  3. Klik Scrape 20 Creator (cek tidak stuck)"
echo ""
