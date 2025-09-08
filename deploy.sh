#!/bin/bash

# Thai PBS Research API - Cloud Run Deployment Script
# This script deploys the FastAPI application to Google Cloud Run
# Usage: ./deploy.sh [--env production|development] [--dry-run]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENV_FILE=".env.production"
DRY_RUN=false
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            if [[ "$2" == "development" ]]; then
                ENV_FILE=".env"
            elif [[ "$2" == "production" ]]; then
                ENV_FILE=".env.production"
            else
                echo -e "${RED}Error: Invalid environment. Use 'production' or 'development'${NC}"
                exit 1
            fi
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--env production|development] [--dry-run] [--verbose]"
            echo "  --env: Environment to deploy (default: production)"
            echo "  --dry-run: Show commands without executing"
            echo "  --verbose: Show detailed output"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run commands (with dry-run support)
run_command() {
    local cmd="$1"
    local description="$2"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $description"
        echo -e "${YELLOW}Would run:${NC} $cmd"
        return 0
    fi
    
    log_info "$description"
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}Running:${NC} $cmd"
    fi
    
    eval "$cmd"
}

# Function to load environment variables from file
load_env_file() {
    local env_file="$1"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file $env_file not found!"
        exit 1
    fi
    
    log_info "Loading environment variables from $env_file"
    
    # Load variables but don't export them yet
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        
        # Export the variable
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            if [[ "$VERBOSE" == "true" ]]; then
                key=$(echo "$line" | cut -d'=' -f1)
                echo -e "${BLUE}Loading:${NC} $key"
            fi
            export "$line"
        fi
    done < "$env_file"
}

# Function to validate required environment variables
validate_env_vars() {
    local required_vars=(
        "GCLOUD_PROJECT"
        "GCLOUD_REGION"
        "GCLOUD_ACCOUNT"
        "CLOUD_RUN_SERVICE"
        "DATABASE_URL"
        "SUPABASE_URL"
        "SUPABASE_SERVICE_ROLE_KEY"
        "JWT_SECRET_KEY"
    )
    
    log_info "Validating required environment variables"
    
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo -e "  ${RED}✗${NC} $var"
        done
        exit 1
    fi
    
    log_success "All required environment variables are set"
}

# Function to save current gcloud configuration
save_current_gcloud_config() {
    ORIGINAL_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
    ORIGINAL_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Current gcloud config - Account: $ORIGINAL_ACCOUNT, Project: $ORIGINAL_PROJECT"
    fi
}

# Function to restore gcloud configuration
restore_gcloud_config() {
    if [[ -n "$ORIGINAL_ACCOUNT" ]]; then
        run_command "gcloud config set account $ORIGINAL_ACCOUNT" "Restoring original gcloud account"
    fi
    if [[ -n "$ORIGINAL_PROJECT" ]]; then
        run_command "gcloud config set project $ORIGINAL_PROJECT" "Restoring original gcloud project"
    fi
}

# Function to set up gcloud for deployment
setup_gcloud() {
    save_current_gcloud_config
    
    run_command "gcloud config set account $GCLOUD_ACCOUNT" "Setting gcloud account to $GCLOUD_ACCOUNT"
    run_command "gcloud config set project $GCLOUD_PROJECT" "Setting gcloud project to $GCLOUD_PROJECT"
    
    # Configure Docker for GCR
    run_command "gcloud auth configure-docker" "Configuring Docker for Google Container Registry"
}

# Function to build Docker image
build_docker_image() {
    local image_name="gcr.io/$GCLOUD_PROJECT/$CLOUD_RUN_SERVICE:latest"
    
    log_info "Building Docker image: $image_name"
    run_command "docker build --platform linux/amd64 -t $image_name ." "Building Docker image for x86_64 architecture"
    
    log_success "Docker image built successfully"
    return 0
}

# Function to push Docker image
push_docker_image() {
    local image_name="gcr.io/$GCLOUD_PROJECT/$CLOUD_RUN_SERVICE:latest"
    
    run_command "docker push $image_name" "Pushing Docker image to Google Container Registry"
    log_success "Docker image pushed successfully"
}

# Function to prepare environment variables for Cloud Run
prepare_env_vars() {
    local env_vars_file="/tmp/cloudrun_env_vars.txt"
    
    # List of environment variables to pass to Cloud Run
    local cloud_run_vars=(
        "ENVIRONMENT"
        "DEBUG" 
        "DATABASE_URL"
        "SUPABASE_URL"
        "SUPABASE_SERVICE_ROLE_KEY"
        "JWT_SECRET_KEY"
        "JWT_ALGORITHM"
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS"
        "FILE_UPLOAD_MAX_SIZE"
        "IMAGE_COMPRESSION_QUALITY"
        "UPLOAD_PATH"
        "RATE_LIMIT_ENABLED"
        "CORS_ORIGINS"
        "DB_POOL_MIN_SIZE"
        "DB_POOL_MAX_SIZE"
        "LOG_LEVEL"
        "ENABLE_QUERY_LOGGING"
    )
    
    # Build env vars string
    local env_string=""
    for var in "${cloud_run_vars[@]}"; do
        if [[ -n "${!var}" ]]; then
            if [[ -n "$env_string" ]]; then
                env_string="$env_string,"
            fi
            env_string="$env_string$var=${!var}"
        fi
    done
    
    echo "$env_string" > "$env_vars_file"
    echo "$env_vars_file"
}

# Function to deploy to Cloud Run
deploy_to_cloud_run() {
    local image_name="gcr.io/$GCLOUD_PROJECT/$CLOUD_RUN_SERVICE:latest"
    local env_vars_file=$(prepare_env_vars)
    local env_vars=$(cat "$env_vars_file")
    
    # Set defaults if not specified
    local memory="${CLOUD_RUN_MEMORY:-1Gi}"
    local cpu="${CLOUD_RUN_CPU:-1}"
    local timeout="${CLOUD_RUN_TIMEOUT:-300}"
    
    local deploy_cmd="gcloud run deploy $CLOUD_RUN_SERVICE \
        --image $image_name \
        --platform managed \
        --region $GCLOUD_REGION \
        --allow-unauthenticated \
        --port 8080 \
        --memory $memory \
        --cpu $cpu \
        --timeout $timeout"
    
    if [[ -n "$env_vars" ]]; then
        deploy_cmd="$deploy_cmd --set-env-vars=\"$env_vars\""
    fi
    
    run_command "$deploy_cmd" "Deploying to Cloud Run service: $CLOUD_RUN_SERVICE"
    
    # Clean up temp file
    rm -f "$env_vars_file"
}

# Function to get service URL
get_service_url() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} Would get service URL"
        return 0
    fi
    
    local service_url=$(gcloud run services describe "$CLOUD_RUN_SERVICE" \
        --platform managed \
        --region "$GCLOUD_REGION" \
        --format 'value(status.url)' 2>/dev/null || echo "")
    
    if [[ -n "$service_url" ]]; then
        log_success "Service deployed successfully!"
        echo -e "${GREEN}Service URL:${NC} $service_url"
        echo -e "${BLUE}Health Check:${NC} $service_url/health"
    else
        log_warning "Could not retrieve service URL"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    restore_gcloud_config
    
    # Clean up any temporary files
    rm -f /tmp/cloudrun_env_vars.txt
}

# Set up cleanup on exit
trap cleanup EXIT

# Main deployment function
main() {
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}  Thai PBS Research API - Cloud Run Deploy${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo
    
    # Load environment variables
    load_env_file "$ENV_FILE"
    
    # Validate environment
    validate_env_vars
    
    echo -e "${BLUE}Deployment Configuration:${NC}"
    echo -e "  Environment File: ${YELLOW}$ENV_FILE${NC}"
    echo -e "  GCloud Project: ${YELLOW}$GCLOUD_PROJECT${NC}"
    echo -e "  GCloud Account: ${YELLOW}$GCLOUD_ACCOUNT${NC}"
    echo -e "  Cloud Run Service: ${YELLOW}$CLOUD_RUN_SERVICE${NC}"
    echo -e "  Region: ${YELLOW}$GCLOUD_REGION${NC}"
    echo -e "  Dry Run: ${YELLOW}$DRY_RUN${NC}"
    echo
    
    if [[ "$DRY_RUN" == "false" ]]; then
        read -p "Do you want to continue with deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled by user"
            exit 0
        fi
    fi
    
    # Deployment steps
    log_info "Starting deployment process..."
    
    # Step 1: Setup gcloud
    setup_gcloud
    
    # Step 2: Build Docker image  
    build_docker_image
    
    # Step 3: Push Docker image
    push_docker_image
    
    # Step 4: Deploy to Cloud Run
    deploy_to_cloud_run
    
    # Step 5: Get service URL
    get_service_url
    
    log_success "Deployment completed successfully!"
}

# Check if script is being run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi