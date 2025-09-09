#!/bin/bash

# Production Deployment Script
# This script deploys Thai PBS Research system to production server

echo "🚀 Thai PBS Research - Production Deployment"
echo "============================================"

# Set production environment
export ENVIRONMENT=production
export FILE_STORAGE_TYPE=minio

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root for production deployment"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor \
    wget \
    curl

# Create application user
if ! id "thaipbs" &>/dev/null; then
    echo "👤 Creating application user..."
    useradd -m -s /bin/bash thaipbs
fi

# Set up application directory
APP_DIR="/opt/thaipbs-research"
echo "📁 Setting up application directory: $APP_DIR"

# Copy application files
mkdir -p $APP_DIR
cp -r . $APP_DIR/
chown -R thaipbs:thaipbs $APP_DIR

# Switch to application directory
cd $APP_DIR

# Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
sudo -u thaipbs python3 -m venv venv
sudo -u thaipbs ./venv/bin/pip install --upgrade pip
sudo -u thaipbs ./venv/bin/pip install -r requirements.txt

# Download MinIO binary for Linux
if [ ! -f "./minio" ]; then
    echo "⬇️  Downloading MinIO binary for Linux..."
    sudo -u thaipbs wget -O minio https://dl.min.io/server/minio/release/linux-amd64/minio
    chmod +x minio
    chown thaipbs:thaipbs minio
fi

# Create necessary directories
echo "📁 Creating directories..."
sudo -u thaipbs mkdir -p minio-data uploads/profiles uploads/articles uploads/covers

# Create .env file for production
echo "🔧 Creating production .env file..."
cat > .env << EOF
# Database (Update with your production database)
DATABASE_URL=postgresql://username:password@localhost/thaipbs_research

# MinIO Configuration (Local)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=\$(openssl rand -base64 32)
MINIO_SECURE=false
MINIO_BUCKET_NAME=research-file
FILE_STORAGE_TYPE=minio

# JWT Configuration
JWT_SECRET_KEY=\$(openssl rand -base64 64)
JWT_ALGORITHM=HS256

# Production Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# CORS (Update with your domain)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
EOF

chown thaipbs:thaipbs .env

# Create systemd service for MinIO
echo "🗄️  Creating MinIO systemd service..."
cat > /etc/systemd/system/thaipbs-minio.service << EOF
[Unit]
Description=Thai PBS MinIO Object Storage
After=network.target
Wants=network.target

[Service]
Type=simple
User=thaipbs
Group=thaipbs
WorkingDirectory=$APP_DIR
Environment=MINIO_ROOT_USER=admin
Environment=MINIO_ROOT_PASSWORD=\$(openssl rand -base64 32)
ExecStart=$APP_DIR/minio server $APP_DIR/minio-data --console-address :9001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for API
echo "🚀 Creating API systemd service..."
cat > /etc/systemd/system/thaipbs-api.service << EOF
[Unit]
Description=Thai PBS Research API
After=network.target thaipbs-minio.service
Wants=network.target
Requires=thaipbs-minio.service

[Service]
Type=simple
User=thaipbs
Group=thaipbs
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx configuration
echo "🌐 Creating Nginx configuration..."
cat > /etc/nginx/sites-available/thaipbs-research << EOF
server {
    listen 80;
    server_name _;  # Update with your domain
    
    client_max_body_size 50M;
    
    # API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # MinIO Console (optional, for admin access)
    location /minio {
        proxy_pass http://127.0.0.1:9001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
EOF

# Enable Nginx site
ln -sf /etc/nginx/sites-available/thaipbs-research /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Enable and start services
echo "🔄 Starting services..."
systemctl daemon-reload

systemctl enable thaipbs-minio
systemctl start thaipbs-minio

sleep 5

systemctl enable thaipbs-api  
systemctl start thaipbs-api

systemctl enable nginx
systemctl restart nginx

# Check service status
echo "📊 Service Status:"
systemctl status thaipbs-minio --no-pager -l
systemctl status thaipbs-api --no-pager -l
systemctl status nginx --no-pager -l

echo ""
echo "🎉 Production deployment completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Update database connection in $APP_DIR/.env"
echo "   2. Run database migrations"
echo "   3. Update Nginx server_name with your domain"
echo "   4. Set up SSL certificate (Let's Encrypt recommended)"
echo ""
echo "🌐 Your application should be available at:"
echo "   • API: http://your-server-ip/api"
echo "   • MinIO Console: http://your-server-ip/minio (admin access)"
echo "   • Health Check: http://your-server-ip/health"