#!/bin/bash

# Deployment Script untuk VPS Hostinger
# Jalankan script ini di VPS setelah upload kode

set -e  # Exit on error

echo "=== TikTok Affiliate Report - Deployment Script ==="
echo ""

# Warna untuk output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fungsi helper
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# 1. Update sistem
print_info "Updating system packages..."
sudo apt update
sudo apt upgrade -y
print_success "System updated"

# 2. Install dependencies
print_info "Installing required packages..."
sudo apt install -y python3 python3-pip python3-venv nginx
print_success "Packages installed"

# 3. Setup aplikasi directory
APP_DIR="/var/www/tiktok-affiliate-report"
print_info "Setting up application directory at $APP_DIR..."

if [ ! -d "$APP_DIR" ]; then
    sudo mkdir -p $APP_DIR
fi

# Copy files (assuming script runs from app directory)
print_info "Copying application files..."
sudo cp -r . $APP_DIR/
cd $APP_DIR

# 4. Create virtual environment
print_info "Creating Python virtual environment..."
sudo python3 -m venv venv
print_success "Virtual environment created"

# 5. Install Python dependencies
print_info "Installing Python dependencies..."
sudo $APP_DIR/venv/bin/pip install --upgrade pip
sudo $APP_DIR/venv/bin/pip install -r requirements.txt
sudo $APP_DIR/venv/bin/pip install gunicorn
print_success "Dependencies installed"

# 6. Setup directories
print_info "Creating required directories..."
sudo mkdir -p $APP_DIR/uploads
sudo mkdir -p $APP_DIR/reports
sudo mkdir -p $APP_DIR/logs
sudo mkdir -p $APP_DIR/instance
print_success "Directories created"

# 7. Setup environment file
print_info "Setting up environment variables..."
if [ ! -f "$APP_DIR/.env" ]; then
    sudo bash -c "cat > $APP_DIR/.env << 'EOF'
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///instance/app.db

# TikTok API (opsional)
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
EOF"
    print_success "Environment file created"
else
    print_info "Environment file already exists, skipping..."
fi

# 8. Set permissions
print_info "Setting permissions..."
sudo chown -R www-data:www-data $APP_DIR
sudo chmod -R 755 $APP_DIR
sudo chmod -R 775 $APP_DIR/uploads
sudo chmod -R 775 $APP_DIR/reports
sudo chmod -R 775 $APP_DIR/logs
sudo chmod -R 775 $APP_DIR/instance
sudo chmod 600 $APP_DIR/.env
print_success "Permissions set"

# 9. Initialize database
print_info "Initializing database..."
cd $APP_DIR
sudo -u www-data $APP_DIR/venv/bin/python3 << 'PYEOF'
from app import create_app
from app.models.db import db

app = create_app()
with app.app_context():
    db.create_all()
    print("Database initialized successfully")
PYEOF
print_success "Database initialized"

# 10. Create systemd service
print_info "Creating systemd service..."
sudo bash -c "cat > /etc/systemd/system/tiktok-affiliate.service << 'EOF'
[Unit]
Description=TikTok Affiliate Report Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/tiktok-affiliate-report
Environment=\"PATH=/var/www/tiktok-affiliate-report/venv/bin\"
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
EOF"
print_success "Systemd service created"

# 11. Configure Nginx
print_info "Configuring Nginx..."
sudo bash -c "cat > /etc/nginx/sites-available/tiktok-affiliate << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static {
        alias /var/www/tiktok-affiliate-report/app/static;
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
}
EOF"

# Enable site
sudo ln -sf /etc/nginx/sites-available/tiktok-affiliate /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
print_success "Nginx configured"

# 12. Test Nginx configuration
print_info "Testing Nginx configuration..."
sudo nginx -t
print_success "Nginx configuration valid"

# 13. Setup firewall
print_info "Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
print_success "Firewall configured"

# 14. Start services
print_info "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable tiktok-affiliate
sudo systemctl start tiktok-affiliate
sudo systemctl restart nginx
print_success "Services started"

# 15. Check status
echo ""
echo "=== Deployment Status ==="
echo ""
print_info "Checking service status..."
sudo systemctl status tiktok-affiliate --no-pager -l

echo ""
print_info "Checking Nginx status..."
sudo systemctl status nginx --no-pager -l

echo ""
echo "=== Deployment Complete! ==="
echo ""
print_success "Application deployed successfully!"
echo ""
echo "Access your application at: http://YOUR_VPS_IP"
echo ""
echo "Useful commands:"
echo "  - View logs: sudo journalctl -u tiktok-affiliate -f"
echo "  - Restart app: sudo systemctl restart tiktok-affiliate"
echo "  - Check status: sudo systemctl status tiktok-affiliate"
echo ""
