# Thai PBS Research API - Deployment Guide

## Overview

This guide explains how to deploy the Thai PBS Research API to Google Cloud Run using the automated deployment script.

## Prerequisites

1. **Docker** installed and running
2. **Google Cloud SDK (gcloud)** installed and authenticated
3. **Access to the Google Cloud Project** `alphatex-source`
4. **Environment file** configured (`.env.production`)

## Quick Start

### 1. Deploy to Production

```bash
./deploy.sh
```

This will:
- Use `.env.production` for configuration
- Build and deploy to Cloud Run
- Show the service URL when complete

### 2. Deploy Development Version

```bash
./deploy.sh --env development
```

This will use `.env` instead of `.env.production`.

### 3. Dry Run (Preview Changes)

```bash
./deploy.sh --dry-run
```

Shows what would be executed without actually running commands.

## Script Options

| Option | Description | Example |
|--------|-------------|---------|
| `--env production\|development` | Choose environment file | `--env production` |
| `--dry-run` | Preview commands without executing | `--dry-run` |
| `--verbose` | Show detailed output | `--verbose` |
| `--help` | Show help message | `--help` |

## Environment Configuration

### Production Environment (`.env.production`)

The production environment file contains:

```bash
# Cloud Run Configuration
GCLOUD_PROJECT=alphatex-source
GCLOUD_REGION=asia-southeast1
GCLOUD_ACCOUNT=nirawork.general@gmail.com
CLOUD_RUN_SERVICE=thaipbs-research
CLOUD_RUN_MEMORY=1Gi
CLOUD_RUN_CPU=1
CLOUD_RUN_TIMEOUT=300

# Application Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
ENABLE_QUERY_LOGGING=false

# Database & Supabase
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...

# Security
JWT_SECRET_KEY=...
RATE_LIMIT_ENABLED=true
CORS_ORIGINS=https://your-domain.com
```

### Required Environment Variables

The script validates these required variables:

- `GCLOUD_PROJECT` - Google Cloud project ID
- `GCLOUD_REGION` - Cloud Run region
- `GCLOUD_ACCOUNT` - Google Cloud account email
- `CLOUD_RUN_SERVICE` - Cloud Run service name
- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `JWT_SECRET_KEY` - JWT signing key

## Deployment Process

The script performs these steps automatically:

1. **Load Environment** - Reads variables from `.env.production`
2. **Validate Config** - Checks all required variables are set
3. **Setup gcloud** - Switches to deployment account and project
4. **Build Image** - Creates Docker image for x86_64 architecture
5. **Push Image** - Uploads to Google Container Registry
6. **Deploy Service** - Creates/updates Cloud Run service
7. **Get URL** - Shows the deployed service URL
8. **Cleanup** - Restores original gcloud configuration

## Examples

### Basic Production Deployment
```bash
./deploy.sh
```

### Development Deployment with Verbose Output
```bash
./deploy.sh --env development --verbose
```

### Preview Production Changes
```bash
./deploy.sh --dry-run --verbose
```

## Troubleshooting

### Common Issues

1. **Docker Build Fails**
   - Check if Docker is running
   - Verify Dockerfile syntax
   - Check for missing dependencies in requirements.txt

2. **gcloud Authentication Issues**
   - Run `gcloud auth login` 
   - Verify account has access to project
   - Check project permissions for Cloud Run

3. **Environment Variable Issues**
   - Verify `.env.production` exists and is readable
   - Check all required variables are set
   - Ensure no typos in variable names

4. **Cloud Run Deployment Fails**
   - Check Cloud Run API is enabled
   - Verify service account permissions
   - Review Cloud Run logs for startup errors

### Viewing Logs

```bash
# View deployment logs
gcloud run services logs read thaipbs-research --region asia-southeast1

# Follow live logs
gcloud run services logs tail thaipbs-research --region asia-southeast1
```

### Manual Cleanup

If deployment fails and cleanup doesn't run:

```bash
# Restore original gcloud config
gcloud config set account your-original-account@gmail.com
gcloud config set project your-original-project
```

## Security Notes

1. **Never commit `.env.production`** - It contains sensitive credentials
2. **Rotate secrets regularly** - Update JWT keys and database passwords
3. **Use least privilege** - Grant minimal required permissions
4. **Monitor access** - Review Cloud Run access logs

## Service URLs

After deployment, the service will be available at:

- **Production**: `https://thaipbs-research-333367812150.asia-southeast1.run.app`
- **Health Check**: `/health`
- **API Documentation**: `/docs` (only in development)

## Next Steps

1. Set up custom domain (optional)
2. Configure load balancing (if needed)
3. Set up monitoring and alerting
4. Configure backup strategies
5. Set up CI/CD pipeline (optional)

## Support

For issues with deployment, check:
1. This documentation
2. Google Cloud Run documentation
3. Project logs and error messages
4. Contact system administrator if needed