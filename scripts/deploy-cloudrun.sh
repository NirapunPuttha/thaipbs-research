#!/bin/bash

# Google Cloud Run Deployment Script
# This script deploys Thai PBS Research system to Cloud Run with embedded MinIO

set -e

echo "🚀 Thai PBS Research - Cloud Run Deployment"
echo "==========================================="

# Configuration
PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
REGION="${REGION:-asia-southeast1}"
SERVICE_NAME="${SERVICE_NAME:-thaipbs-research}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is required but not installed."
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is required but not running."
    exit 1
fi

# Prompt for project ID if not set
if [ "$PROJECT_ID" = "your-gcp-project-id" ]; then
    echo "📝 Please set your GCP Project ID:"
    read -p "Project ID: " PROJECT_ID
    IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
fi

# Set gcloud project
echo "🔧 Setting gcloud project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build Docker image with Cloud Build (recommended for Cloud Run)
echo "🏗️  Building Docker image with Cloud Build..."
gcloud builds submit \
    --tag "$IMAGE_NAME" \
    --file Dockerfile.cloudrun \
    --timeout=20m \
    .

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --concurrency 100 \
    --max-instances 10 \
    --port 8000 \
    --set-env-vars "FILE_STORAGE_TYPE=minio" \
    --set-env-vars "MINIO_ENDPOINT=localhost:9000" \
    --set-env-vars "MINIO_ACCESS_KEY=thaipbs_admin" \
    --set-env-vars "MINIO_SECRET_KEY=TpbS!R3s34rch@M1n10#2024$" \
    --set-env-vars "MINIO_SECURE=false" \
    --set-env-vars "MINIO_BUCKET_NAME=research-file" \
    --set-env-vars "ENVIRONMENT=production"

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Deployment Information:"
echo "   • Service Name: $SERVICE_NAME"
echo "   • Region: $REGION"
echo "   • Image: $IMAGE_NAME"
echo "   • Memory: 2Gi"
echo "   • CPU: 2"
echo ""
echo "🌐 Access Points:"
echo "   • API: $SERVICE_URL"
echo "   • API Docs: $SERVICE_URL/docs"
echo "   • Health Check: $SERVICE_URL/health"
echo ""
echo "⚠️  Important Notes:"
echo "   • MinIO data is NOT persistent in Cloud Run"
echo "   • For production, consider using Cloud Storage instead"
echo "   • Files uploaded will be lost when container restarts"
echo ""
echo "🔧 To update environment variables:"
echo "   gcloud run services update $SERVICE_NAME --region=$REGION --set-env-vars KEY=VALUE"
echo ""
echo "📊 To view logs:"
echo "   gcloud logs tail \"cloudrun.googleapis.com%2Fstdout\" --filter=\"resource.labels.service_name=$SERVICE_NAME\""