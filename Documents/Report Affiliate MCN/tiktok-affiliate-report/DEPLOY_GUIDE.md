# Panduan Deploy ke VPS Hostinger

## Persiapan

### 1. Akses VPS via SSH
```bash
ssh root@YOUR_VPS_IP
```

### 2. Upload Kode ke VPS

**Opsi A: Menggunakan Git (Recommended)**
```bash
# Di VPS
cd /tmp
git clone YOUR_REPO_URL
cd YOUR_REPO_NAME/tiktok-affiliate-report
```

**Opsi B: Menggunakan SCP dari komputer lokal**
```bash
# Di komputer lokal
cd tiktok-affiliate-report
tar -czf app.tar.gz .
scp app.tar.gz root@YOUR_VPS_IP:/tmp/

# Di VPS
cd /tmp
mkdir tiktok-affiliate-report
tar -xzf app.tar.gz -C tiktok-affiliate-report
cd tiktok-affiliate-report
```

**Opsi C: Menggunakan SFTP Client (FileZilla, WinSCP)**
- Upload seluruh folder `tiktok-affiliate-report` ke `/tmp/tiktok-affiliate-report`

## Deployment Otomatis

### Jalankan Script Deployment
```bash
cd /tmp/tiktok-affiliate-report
chmod +x deploy.sh
sudo ./deploy.sh
```

Script akan otomatis:
- ✓ Update sistem
- ✓ Install Nginx, Python3, dependencies
- ✓ Setup virtual environment
- ✓ Install Python packages
- ✓ Setup directories (uploads, reports, logs)
- ✓ Generate SECRET_KEY
- ✓ Initialize database
- ✓ Setup Gunicorn service
- ✓ Configure Nginx
- ✓ Setup firewall
- ✓ Start semua services

### Cek Status
```bash
# Cek aplikasi
sudo systemctl status tiktok-affiliate

# Cek Nginx
sudo systemctl status nginx

# Lihat logs
sudo journalctl -u tiktok-affiliate -f
```

### Akses Aplikasi
Buka browser: `http://YOUR_VPS_IP`

---

## Deployment Manual (Jika Script Gagal)

### 1. Install Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx
```

### 2. Setup Aplikasi
```bash
sudo mkdir -p /var/www/tiktok-affiliate-report
sudo cp -r /tmp/tiktok-affiliate-report/* /var/www/tiktok-affiliate-report/
cd /var/www/tiktok-affiliate-report
```

### 3. Virtual Environment
```bash
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt
sudo venv/bin/pip install gunicorn
```

### 4. Setup Directories
```bash
sudo mkdir -p uploads reports logs instance
```

### 5. Environment Variables
```bash
sudo nano .env
```

Isi dengan:
```
FLASK_ENV=production
SECRET_KEY=ganti-dengan-random-string-panjang
DATABASE_URL=sqlite:///instance/app.db

# TikTok API (opsional)
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
```

Generate SECRET_KEY:
```bash
openssl rand -hex 32
```

### 6. Set Permissions
```bash
sudo chown -R www-data:www-data /var/www/tiktok-affiliate-report
sudo chmod -R 755 /var/www/tiktok-affiliate-report
sudo chmod -R 775 /var/www/tiktok-affiliate-report/uploads
sudo chmod -R 775 /var/www/tiktok-affiliate-report/reports
sudo chmod -R 775 /var/www/tiktok-affiliate-report/logs
sudo chmod -R 775 /var/www/tiktok-affiliate-report/instance
sudo chmod 600 /var/www/tiktok-affiliate-report/.env
```

### 7. Initialize Database
```bash
cd /var/www/tiktok-affiliate-report
sudo -u www-data venv/bin/python3 -c "
from app import create_app
from app.models.db import db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database initialized')
"
```

### 8. Create Systemd Service
```bash
sudo nano /etc/systemd/system/tiktok-affiliate.service
```

Isi dengan:
```ini
[Unit]
Description=TikTok Affiliate Report Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/tiktok-affiliate-report
Environment="PATH=/var/www/tiktok-affiliate-report/venv/bin"
EnvironmentFile=/var/www/tiktok-affiliate-report/.env
ExecStart=/var/www/tiktok-affiliate-report/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8080 \
    --timeout 300 \
    --access-logfile /var/www/tiktok-affiliate-report/logs/access.log \
    --error-logfile /var/www/tiktok-affiliate-report/logs/error.log \
    --log-level info \
    'run:app'

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9. Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/tiktok-affiliate
```

Isi dengan:
```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static {
        alias /var/www/tiktok-affiliate-report/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/tiktok-affiliate /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
```

### 10. Setup Firewall
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 11. Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable tiktok-affiliate
sudo systemctl start tiktok-affiliate
sudo systemctl restart nginx
```

---

## Perintah Berguna

### Restart Aplikasi
```bash
sudo systemctl restart tiktok-affiliate
```

### Lihat Logs Real-time
```bash
# Application logs
sudo journalctl -u tiktok-affiliate -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Application logs
sudo tail -f /var/www/tiktok-affiliate-report/logs/error.log
```

### Check Status
```bash
sudo systemctl status tiktok-affiliate
sudo systemctl status nginx
```

### Update Kode
```bash
cd /var/www/tiktok-affiliate-report

# Backup dulu
sudo cp -r . /tmp/backup-$(date +%Y%m%d-%H%M%S)

# Update kode (via git atau upload manual)
# ...

# Restart
sudo systemctl restart tiktok-affiliate
```

### Troubleshooting

**Aplikasi tidak jalan:**
```bash
# Cek logs
sudo journalctl -u tiktok-affiliate -n 50

# Cek apakah port 8080 dipakai
sudo netstat -tlnp | grep 8080

# Test manual
cd /var/www/tiktok-affiliate-report
sudo -u www-data venv/bin/gunicorn --bind 127.0.0.1:8080 'run:app'
```

**Nginx error:**
```bash
# Test config
sudo nginx -t

# Cek logs
sudo tail -f /var/log/nginx/error.log
```

**Permission error:**
```bash
# Reset permissions
sudo chown -R www-data:www-data /var/www/tiktok-affiliate-report
sudo chmod -R 775 /var/www/tiktok-affiliate-report/uploads
sudo chmod -R 775 /var/www/tiktok-affiliate-report/reports
sudo chmod -R 775 /var/www/tiktok-affiliate-report/instance
```

---

## Setup Domain (Opsional)

### 1. Point Domain ke VPS
Di DNS provider (Hostinger):
- A Record: `@` atau `subdomain` → `YOUR_VPS_IP`

### 2. Update Nginx Config
```bash
sudo nano /etc/nginx/sites-available/tiktok-affiliate
```

Ganti `server_name _;` dengan:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

### 3. Install SSL (Let's Encrypt)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot akan otomatis:
- Generate SSL certificate
- Update Nginx config
- Setup auto-renewal

### 4. Restart Nginx
```bash
sudo systemctl restart nginx
```

Akses: `https://yourdomain.com`

---

## Monitoring & Maintenance

### Auto-restart on Crash
Sudah dikonfigurasi di systemd service dengan `Restart=always`

### Log Rotation
```bash
sudo nano /etc/logrotate.d/tiktok-affiliate
```

Isi:
```
/var/www/tiktok-affiliate-report/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload tiktok-affiliate > /dev/null 2>&1 || true
    endscript
}
```

### Backup Database
```bash
# Manual backup
sudo cp /var/www/tiktok-affiliate-report/instance/app.db /tmp/backup-$(date +%Y%m%d).db

# Auto backup (crontab)
sudo crontab -e
```

Tambahkan:
```
0 2 * * * cp /var/www/tiktok-affiliate-report/instance/app.db /var/backups/app-$(date +\%Y\%m\%d).db
```

---

## Selesai!

Aplikasi sekarang berjalan di: `http://YOUR_VPS_IP`

Jika ada masalah, cek logs atau hubungi support.
