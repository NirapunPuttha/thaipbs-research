# Thai PBS Research Management System

A modern research management system built with FastAPI and MinIO object storage.

## 🚀 Quick Start

### Local Development
```bash
# Run automated setup
./scripts/deploy-local.sh

# Or manual setup:
pip install -r requirements.txt
./bin/start-minio.sh &
python main.py
```

### Docker Compose
```bash
docker-compose up -d
```

## 📁 Project Structure

```
thaipbs-research/
├── app/                    # FastAPI application
├── bin/                    # MinIO binary & startup scripts
├── docs/                   # Documentation
├── scripts/                # Deployment & utility scripts
├── sql/                    # Database schemas & migrations
└── documents/              # API documentation
```

## 🌐 Access Points

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001

## 📚 Documentation

- [Deployment Guide](docs/DEPLOYMENT_MINIO.md)
- [API Documentation](documents/minio-api-documentation.md)

## 🔐 Default Credentials

**MinIO Console:**
- Username: `thaipbs_admin`
- Password: `TpbS!R3s34rch@M1n10#2024$`

**Note:** Change credentials in production!