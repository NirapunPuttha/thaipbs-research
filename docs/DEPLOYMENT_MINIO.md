# Thai PBS Research - MinIO Integration Deployment Guide

## 🏗️ Architecture Overview

The system now includes **integrated MinIO object storage** that runs alongside the API application:

```
┌─────────────────────────────────────┐
│           Server/Container          │
├─────────────────────────────────────┤
│  📱 Thai PBS Research API (Port 8000) │
│  🗄️  MinIO Object Storage (Port 9000) │
│  🖥️  MinIO Console (Port 9001)        │
│  🗃️  PostgreSQL Database             │
└─────────────────────────────────────┘
```

## 📁 File Structure

After setup, your project structure will be:

```
thaipbs-research/
├── app/                    # API application
├── minio                   # MinIO binary
├── minio-data/             # MinIO data storage
├── uploads/                # Fallback for local files
├── start-minio.sh          # MinIO startup script
├── start-minio-linux.sh    # Linux version
├── docker-compose.yml      # Docker deployment
├── deploy-local.sh         # Local deployment script
├── deploy-production.sh    # Production deployment script
└── test_minio_integration.py
```

## 🚀 Deployment Options

### Option 1: Local Development

Perfect for development and testing:

```bash
# Run the automated setup
./deploy-local.sh

# Or manual setup:
chmod +x start-minio.sh
./start-minio.sh &
python main.py
```

**Access Points:**
- API: http://localhost:8000
- MinIO Console: http://localhost:9001
- API Docs: http://localhost:8000/docs

### Option 2: Docker Compose

Ideal for consistent environments:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Access Points:**
- API: http://localhost:8000
- MinIO Console: http://localhost:9001

### Option 3: Production Server

For production deployment:

```bash
# Run as root on production server
sudo ./deploy-production.sh
```

This will:
- Install system dependencies
- Create systemd services
- Configure Nginx reverse proxy
- Set up proper security

## ⚙️ Configuration

### Environment Variables

Create `.env` file based on `.env.example`:

```env
# File Storage Type
FILE_STORAGE_TYPE=minio           # Use MinIO
# FILE_STORAGE_TYPE=local         # Use local files

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000     # MinIO server address
MINIO_ACCESS_KEY=admin            # MinIO username
MINIO_SECRET_KEY=password123      # MinIO password
MINIO_BUCKET_NAME=research-file   # Default bucket name
MINIO_SECURE=false               # Use HTTP (set true for HTTPS)
```

### Database Migration

Run the MinIO support migration:

```bash
psql -d your_database -f migration_minio_support.sql
```

## 🧪 Testing

Test the MinIO integration:

```bash
python test_minio_integration.py
```

This will verify:
- ✅ MinIO connection
- ✅ Bucket creation
- ✅ File upload/download
- ✅ Presigned URL generation
- ✅ File deletion

## 🔄 Migration from Local Files

To migrate existing local files to MinIO:

1. **Start MinIO server**
2. **Set `FILE_STORAGE_TYPE=minio`** in `.env`
3. **New uploads will go to MinIO**
4. **Old files remain accessible via local serving**

### Migration Script (Optional)

```python
# migrate_to_minio.py
import os
from pathlib import Path
from app.services.minio_service import minio_service

async def migrate_files():
    uploads_dir = Path("uploads")
    for file_path in uploads_dir.rglob("*"):
        if file_path.is_file():
            with open(file_path, 'rb') as f:
                data = f.read()
            
            relative_path = str(file_path.relative_to(uploads_dir))
            success, url = await minio_service.upload_file(
                data, relative_path
            )
            print(f"Migrated: {file_path} -> {url}")

# Run migration
import asyncio
asyncio.run(migrate_files())
```

## 🔒 Security Considerations

### Production Security

1. **Change default credentials:**
   ```env
   MINIO_ACCESS_KEY=your-secure-username
   MINIO_SECRET_KEY=your-very-long-secure-password
   ```

2. **Use HTTPS in production:**
   ```env
   MINIO_SECURE=true
   MINIO_ENDPOINT=your-domain.com:9000
   ```

3. **Firewall configuration:**
   ```bash
   # Allow only necessary ports
   ufw allow 80    # HTTP
   ufw allow 443   # HTTPS
   ufw deny 9000   # Block direct MinIO API access
   ufw deny 9001   # Block MinIO console
   ```

### Access Control

MinIO files are accessed via:
- **Direct API calls** - Through your application APIs
- **Presigned URLs** - Temporary, secure access links
- **Console access** - Admin interface (production: restrict access)

## 🚨 Troubleshooting

### Common Issues

1. **Port already in use:**
   ```bash
   lsof -ti:9000 | xargs kill -9
   lsof -ti:9001 | xargs kill -9
   ```

2. **Permission denied:**
   ```bash
   chmod +x minio start-minio.sh
   sudo chown -R $USER:$USER minio-data
   ```

3. **Connection refused:**
   - Check if MinIO is running: `ps aux | grep minio`
   - Check logs: `tail -f minio.log`
   - Test connectivity: `curl http://localhost:9000/minio/health/live`

4. **Bucket not found:**
   - MinIO creates buckets automatically
   - Check bucket name in configuration
   - Use MinIO Console to verify: http://localhost:9001

### Log Locations

- **MinIO logs:** `minio.log` (local) or `journalctl -u thaipbs-minio` (systemd)
- **API logs:** Application logs or `journalctl -u thaipbs-api`
- **Nginx logs:** `/var/log/nginx/access.log` and `/var/log/nginx/error.log`

## 📚 API Endpoints

### File Upload
```http
POST /api/v1/files/articles/upload/{article_id}
Content-Type: multipart/form-data
```

### File Download  
```http
GET /api/v1/files/download/{file_path}
# Automatically redirects to MinIO presigned URL
```

### MinIO Direct Access
```http
GET /api/v1/files/minio/presigned-url/{object_name}
# Returns presigned URL for direct access
```

## 🎯 Benefits

### Self-Contained Deployment
- ✅ **Single server deployment** - Everything in one place
- ✅ **No external dependencies** - No need for AWS S3, etc.
- ✅ **Cost effective** - No bandwidth charges
- ✅ **Fast performance** - Local network access

### Scalability
- ✅ **Docker support** - Easy containerization
- ✅ **Horizontal scaling** - Multiple MinIO instances
- ✅ **Backup friendly** - File-based storage
- ✅ **Migration ready** - S3-compatible APIs

## 📞 Support

For deployment issues:

1. **Check logs first** - Most issues are logged
2. **Test components individually** - MinIO, API, Database
3. **Verify configuration** - Environment variables, ports
4. **Network connectivity** - Firewalls, DNS resolution

The system is designed to be **production-ready** and **customer-deployable** with minimal configuration required.