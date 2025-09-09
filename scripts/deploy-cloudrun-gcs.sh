#!/bin/bash

# Google Cloud Run Deployment Script with Cloud Storage
# This script deploys Thai PBS Research system to Cloud Run using GCS instead of MinIO

set -e

echo "🚀 Thai PBS Research - Cloud Run Deployment (with Cloud Storage)"
echo "================================================================"

# Configuration
PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
REGION="${REGION:-asia-southeast1}"
SERVICE_NAME="${SERVICE_NAME:-thaipbs-research}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-thaipbs-research-files}"
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
    BUCKET_NAME="${PROJECT_ID}-thaipbs-research-files"
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
gcloud services enable storage.googleapis.com

# Create Cloud Storage bucket for files
echo "🪣 Creating Cloud Storage bucket: $BUCKET_NAME"
if ! gsutil ls -b "gs://$BUCKET_NAME" &> /dev/null; then
    gsutil mb -l "$REGION" "gs://$BUCKET_NAME"
    gsutil uniformbucketlevelaccess set on "gs://$BUCKET_NAME"
    echo "✅ Bucket created: gs://$BUCKET_NAME"
else
    echo "✅ Bucket already exists: gs://$BUCKET_NAME"
fi

# Set bucket CORS policy for web access
echo "🌐 Setting CORS policy for bucket..."
cat > /tmp/cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST", "PUT", "DELETE", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Range", "Content-Encoding", "Date", "Server", "Transfer-Encoding"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set /tmp/cors.json "gs://$BUCKET_NAME"
rm /tmp/cors.json

# Build Docker image (using regular Dockerfile, not MinIO version)
echo "🏗️  Building Docker image with Cloud Build..."
gcloud builds submit \
    --tag "$IMAGE_NAME" \
    --file Dockerfile \
    --timeout=20m \
    .

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --concurrency 100 \
    --max-instances 10 \
    --port 8000 \
    --set-env-vars "FILE_STORAGE_TYPE=gcs" \
    --set-env-vars "GCS_BUCKET_NAME=$BUCKET_NAME" \
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
echo "   • Storage: Cloud Storage (gs://$BUCKET_NAME)"
echo "   • Memory: 1Gi"
echo "   • CPU: 1"
echo ""
echo "🌐 Access Points:"
echo "   • API: $SERVICE_URL"
echo "   • API Docs: $SERVICE_URL/docs"
echo "   • Health Check: $SERVICE_URL/health"
echo ""
echo "💡 Advantages of this setup:"
echo "   • ✅ Persistent file storage"
echo "   • ✅ Scalable and managed storage"
echo "   • ✅ No storage limits"
echo "   • ✅ Automatic backups available"
echo ""
echo "🔧 To update environment variables:"
echo "   gcloud run services update $SERVICE_NAME --region=$REGION --set-env-vars KEY=VALUE"
echo ""
echo "📊 To view logs:"
echo "   gcloud logs tail \"cloudrun.googleapis.com%2Fstdout\" --filter=\"resource.labels.service_name=$SERVICE_NAME\""
echo ""
echo "📁 To manage files:"
echo "   gsutil ls gs://$BUCKET_NAME"