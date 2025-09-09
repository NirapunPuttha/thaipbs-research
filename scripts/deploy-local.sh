#!/bin/bash

# Local Development Deployment Script
# This script sets up the complete Thai PBS Research system locally

echo "🚀 Thai PBS Research - Local Deployment"
echo "======================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "❌ pip is required but not installed."
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file from example if not exists
if [ ! -f ".env" ]; then
    echo "🔧 Creating .env file from example..."
    cp .env.example .env
    echo "✅ Please edit .env file with your configuration"
fi

# Download MinIO binary if not exists
if [ ! -f "./bin/minio" ]; then
    echo "⬇️  Downloading MinIO binary..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        wget -O bin/minio https://dl.min.io/server/minio/release/linux-amd64/minio
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        wget -O bin/minio https://dl.min.io/server/minio/release/darwin-amd64/minio
    else
        echo "❌ Unsupported operating system"
        exit 1
    fi
    chmod +x bin/minio
    echo "✅ MinIO binary downloaded"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p minio-data uploads/profiles uploads/articles uploads/covers

# Start MinIO server in background
echo "🗄️  Starting MinIO server..."
if pgrep -f "./bin/minio server" > /dev/null; then
    echo "⚠️  MinIO is already running"
else
    nohup ./bin/start-minio.sh > minio.log 2>&1 &
    echo "✅ MinIO server started (check minio.log for details)"
fi

# Wait for MinIO to be ready
echo "⏳ Waiting for MinIO to be ready..."
sleep 3

# Test MinIO connection
echo "🧪 Testing MinIO connection..."
python scripts/test_minio_integration.py

echo ""
echo "🎉 Local deployment completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Update your .env file with database connection"
echo "   2. Run database migrations:"
echo "      psql -d your_database -f sql/migration_minio_support.sql"
echo "   3. Start the API server:"
echo "      python main.py"
echo ""
echo "🌐 Access points:"
echo "   • API: http://localhost:8000"
echo "   • MinIO Console: http://localhost:9001 (thaipbs_admin/TpbS!R3s34rch@M1n10#2024$)"
echo "   • API Docs: http://localhost:8000/docs"