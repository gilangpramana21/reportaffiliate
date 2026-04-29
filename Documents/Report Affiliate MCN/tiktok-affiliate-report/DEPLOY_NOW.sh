#!/bin/bash
# Quick Deploy Script untuk VPS Hostinger
# Jalankan script ini di VPS: ssh root@72.62.244.186

set -e

echo "=== TikTok Affiliate Report - Quick Deploy ==="
echo ""

# 1. Update sistem
echo "→ Updating system..."
apt update
apt upgrade -y

# 2. Install dependencies
echo "→ Installing dependencies..."
apt install -y python3 python3-pip python3-venv nginx git

# 3. Clone dari GitHub
echo "→ Cloning from GitHub..."
cd /tmp
rm -rf reportaffiliate
git clone https://github.com/gilangpramana21/reportaffiliate.git
cd reportaffiliate/tiktok-affiliate-report

# 4. Setup aplikasi directory
APP_DIR="/var/www/tiktok-affiliate-report"
echo "→ Setting up application directory..."
mkdir -p $APP_DIR
cp -r . $APP_DIR/
cd $APP_DIR

# 5. Create virtual environment
echo "→ Creating virtual environment..."
python3 -m venv venv

# 6. Install Python dependencies
echo "→ Installing Python packages..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install gunicorn

# 7. Setup directories
echo "→ Creating directories..."
mkdir -p uploads reports logs instance

# 8. Setup environment file
echo "→ Setting up environment..."
SECRET_KEY=$(openssl rand -hex 32)
cat > .env << EOF
FLASK_ENV=production
SECRET_KEY=$SECRET_KEY
DATABASE_URL=sqlite:///instance/app.db

# TikTok API (opsional)
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
EOF

# 9. Set permissions
echo "→ Setting permissions..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR
chmod -R 775 $APP_DIR/uploads
chmod -R 775 $APP_DIR/reports
chmod -R 775 $APP_DIR/logs
chmod -R 775 $APP_DIR/instance
chmod 600 $APP_DIR/.env

# 10. Initialize database
echo "→ Initializing database..."
cd $APP_DIR
sudo -u www-data $APP_DIR/venv/bin/python3 << 'PYEOF'
from app import create_app
from app.models.db import db

app = create_app()
with app.app_context():
    db.create_all()
    print("✓ Database initialized")
PYEOF

# 11. Create systemd service
echo "→ Creating systemd service..."
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

# 12. Configure Nginx
echo "→ Configuring Nginx..."
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

ln -sf /etc/nginx/sites-available/tiktok-affiliate /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
nginx -t

# 13. Setup firewall
echo "→ Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 14. Start services
echo "→ Starting services..."
systemctl daemon-reload
systemctl enable tiktok-affiliate
systemctl start tiktok-affiliate
systemctl restart nginx

# 15. Check status
echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "✓ Application deployed successfully!"
echo ""
echo "Access your application at: http://72.62.244.186"
echo ""
echo "Useful commands:"
echo "  - View logs: journalctl -u tiktok-affiliate -f"
echo "  - Restart app: systemctl restart tiktok-affiliate"
echo "  - Check status: systemctl status tiktok-affiliate"
echo ""
echo "Checking service status..."
systemctl status tiktok-affiliate --no-pager -l
