#!/bin/bash

# MinIO Startup Script for Linux/Production
# This script starts MinIO server with local data storage

# Set MinIO credentials
export MINIO_ROOT_USER=thaipbs_admin
export MINIO_ROOT_PASSWORD='TpbS!R3s34rch@M1n10#2024$'

# Create data directory if it doesn't exist
mkdir -p ./minio-data

# Download MinIO binary for Linux if not exists
if [ ! -f "./minio" ]; then
    echo "⬇️  Downloading MinIO binary for Linux..."
    wget -O minio https://dl.min.io/server/minio/release/linux-amd64/minio
    chmod +x minio
    echo "✅ MinIO binary downloaded"
fi

echo "🚀 Starting MinIO Server..."
echo "   Data Directory: ./minio-data"
echo "   API Endpoint: http://localhost:9000"
echo "   Console: http://localhost:9001"
echo "   Username: thaipbs_admin"
echo "   Password: TpbS!R3s34rch@M1n10#2024$"
echo ""

# Start MinIO server
./minio server ./minio-data --console-address ":9001"