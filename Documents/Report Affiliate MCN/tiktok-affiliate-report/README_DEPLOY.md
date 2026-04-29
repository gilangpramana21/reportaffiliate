# Deploy ke VPS Hostinger - Panduan Cepat

## Langkah Deploy (Super Simple!)

### 1. SSH ke VPS
```bash
ssh root@72.62.244.186
```
Password: `Mcn12345678@`

### 2. Download & Jalankan Script
```bash
curl -o deploy.sh https://raw.githubusercontent.com/gilangpramana21/reportaffiliate/main/tiktok-affiliate-report/DEPLOY_NOW.sh
chmod +x deploy.sh
./deploy.sh
```

**ATAU** jika curl tidak ada:
```bash
wget https://raw.githubusercontent.com/gilangpramana21/reportaffiliate/main/tiktok-affiliate-report/DEPLOY_NOW.sh -O deploy.sh
chmod +x deploy.sh
./deploy.sh
```

**ATAU** copy-paste manual:
```bash
# Clone repo
cd /tmp
git clone https://github.com/gilangpramana21/reportaffiliate.git
cd reportaffiliate/tiktok-affiliate-report

# Jalankan script
chmod +x DEPLOY_NOW.sh
./DEPLOY_NOW.sh
```

### 3. Tunggu Sampai Selesai
Script akan otomatis:
- ✓ Install semua dependencies
- ✓ Clone kode dari GitHub
- ✓ Setup Python virtual environment
- ✓ Install packages
- ✓ Setup database
- ✓ Configure Nginx
- ✓ Setup systemd service
- ✓ Start aplikasi

### 4. Akses Aplikasi
Buka browser: **http://72.62.244.186**

---

## Perintah Berguna

```bash
# Lihat logs real-time
journalctl -u tiktok-affiliate -f

# Restart aplikasi
systemctl restart tiktok-affiliate

# Check status
systemctl status tiktok-affiliate

# Stop aplikasi
systemctl stop tiktok-affiliate

# Start aplikasi
systemctl start tiktok-affiliate
```

---

## Update Aplikasi

Jika ada update kode di GitHub:

```bash
cd /var/www/tiktok-affiliate-report
git pull origin main
systemctl restart tiktok-affiliate
```

---

## Troubleshooting

### Aplikasi tidak jalan
```bash
# Lihat error
journalctl -u tiktok-affiliate -n 50

# Cek port
netstat -tlnp | grep 8080
```

### Nginx error
```bash
nginx -t
tail -f /var/log/nginx/error.log
```

### Reset permissions
```bash
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 775 /var/www/tiktok-affiliate-report/uploads
chmod -R 775 /var/www/tiktok-affiliate-report/reports
```

---

## Setup Domain (Opsional)

Jika mau pakai domain:

1. **Point domain ke VPS** di DNS settings:
   - A Record: `@` → `72.62.244.186`

2. **Update Nginx config**:
```bash
nano /etc/nginx/sites-available/tiktok-affiliate
```
Ganti `server_name _;` dengan `server_name yourdomain.com;`

3. **Install SSL**:
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

4. **Restart Nginx**:
```bash
systemctl restart nginx
```

---

## Selesai!

Aplikasi sekarang berjalan di: **http://72.62.244.186**

Jika ada masalah, cek logs atau hubungi support.
