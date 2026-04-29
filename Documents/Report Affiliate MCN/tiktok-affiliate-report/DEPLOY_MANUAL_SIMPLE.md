# Panduan Deploy Manual - Simple & Cepat

## Cara Tercepat: Upload via Git

### 1. Push kode ke GitHub/GitLab (dari komputer lokal)
```bash
cd tiktok-affiliate-report

# Init git (jika belum)
git init
git add .
git commit -m "Initial commit"

# Push ke GitHub (buat repo dulu di github.com)
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

### 2. SSH ke VPS dan Clone
```bash
# SSH ke VPS
ssh root@72.62.244.186

# Clone dari GitHub
cd /tmp
git clone https://github.com/USERNAME/REPO_NAME.git
cd REPO_NAME
```

### 3. Jalankan Deploy Script
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## Cara Alternatif: Deploy Manual Step-by-Step

Jika tidak mau pakai Git, ikuti langkah ini di VPS:

### 1. SSH ke VPS
```bash
ssh root@72.62.244.186
```

### 2. Install Dependencies
```bash
apt update
apt install -y python3 python3-pip python3-venv nginx git
```

### 3. Buat Struktur Directory
```bash
mkdir -p /var/www/tiktok-affiliate-report
cd /var/www/tiktok-affiliate-report
```

### 4. Upload Kode (Pilih salah satu)

**Opsi A: Via Git (Recommended)**
```bash
# Clone dari repo Anda
git clone https://github.com/USERNAME/REPO_NAME.git .
```

**Opsi B: Buat Manual (Copy-Paste)**
```bash
# Buat file-file penting
mkdir -p app/models app/routes app/services app/templates config

# Upload file via SFTP atau buat manual
# Minimal yang dibutuhkan:
# - run.py
# - requirements.txt
# - app/__init__.py
# - app/models/db.py
# - dll
```

### 5. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 6. Buat Environment File
```bash
cat > .env << 'EOF'
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///instance/app.db

# TikTok API (opsional)
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
EOF
```

Generate SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy hasilnya dan paste ke .env
```

### 7. Buat Directories
```bash
mkdir -p uploads reports logs instance
```

### 8. Set Permissions
```bash
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 755 /var/www/tiktok-affiliate-report
chmod -R 775 /var/www/tiktok-affiliate-report/uploads
chmod -R 775 /var/www/tiktok-affiliate-report/reports
chmod -R 775 /var/www/tiktok-affiliate-report/logs
chmod -R 775 /var/www/tiktok-affiliate-report/instance
chmod 600 /var/www/tiktok-affiliate-report/.env
```

### 9. Initialize Database
```bash
cd /var/www/tiktok-affiliate-report
sudo -u www-data venv/bin/python3 << 'PYEOF'
from app import create_app
from app.models.db import db

app = create_app()
with app.app_context():
    db.create_all()
    print("Database initialized successfully")
PYEOF
```

### 10. Create Systemd Service
```bash
cat > /etc/systemd/system/tiktok-affiliate.service << 'EOF'
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
EOF
```

### 11. Configure Nginx
```bash
cat > /etc/nginx/sites-available/tiktok-affiliate << 'EOF'
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
EOF

# Enable site
ln -sf /etc/nginx/sites-available/tiktok-affiliate /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test config
nginx -t
```

### 12. Setup Firewall
```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### 13. Start Services
```bash
systemctl daemon-reload
systemctl enable tiktok-affiliate
systemctl start tiktok-affiliate
systemctl restart nginx
```

### 14. Check Status
```bash
# Cek aplikasi
systemctl status tiktok-affiliate

# Cek Nginx
systemctl status nginx

# Lihat logs
journalctl -u tiktok-affiliate -f
```

### 15. Test Aplikasi
Buka browser: `http://72.62.244.186`

---

## Troubleshooting

### Aplikasi tidak jalan
```bash
# Lihat error logs
journalctl -u tiktok-affiliate -n 50

# Cek apakah port 8080 dipakai
netstat -tlnp | grep 8080

# Test manual
cd /var/www/tiktok-affiliate-report
sudo -u www-data venv/bin/gunicorn --bind 127.0.0.1:8080 'run:app'
```

### Nginx error
```bash
# Test config
nginx -t

# Lihat error logs
tail -f /var/log/nginx/error.log
```

### Permission error
```bash
# Reset permissions
chown -R www-data:www-data /var/www/tiktok-affiliate-report
chmod -R 775 /var/www/tiktok-affiliate-report/uploads
chmod -R 775 /var/www/tiktok-affiliate-report/reports
chmod -R 775 /var/www/tiktok-affiliate-report/instance
```

---

## Perintah Berguna

```bash
# Restart aplikasi
systemctl restart tiktok-affiliate

# Lihat logs real-time
journalctl -u tiktok-affiliate -f

# Stop aplikasi
systemctl stop tiktok-affiliate

# Start aplikasi
systemctl start tiktok-affiliate

# Check status
systemctl status tiktok-affiliate
```

---

## Update Kode

```bash
cd /var/www/tiktok-affiliate-report

# Backup dulu
cp -r . /tmp/backup-$(date +%Y%m%d-%H%M%S)

# Pull update (jika pakai git)
git pull

# Atau upload file baru via SFTP

# Restart
systemctl restart tiktok-affiliate
```
