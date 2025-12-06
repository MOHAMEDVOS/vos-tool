#!/bin/bash

# VOS Tool Cloud Deployment Script
# This script automates the deployment process to AWS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="vos-tool"
AWS_REGION="us-east-1"
TERRAFORM_DIR="cloud-migration/terraform"

# Functions
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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    log_success "All prerequisites met!"
}

setup_terraform_backend() {
    log_info "Setting up Terraform backend..."
    
    # Create S3 bucket for Terraform state
    aws s3api create-bucket \
        --bucket "${PROJECT_NAME}-terraform-state" \
        --region $AWS_REGION \
        --create-bucket-configuration LocationConstraint=$AWS_REGION \
        2>/dev/null || log_warning "S3 bucket may already exist"
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${PROJECT_NAME}-terraform-state" \
        --versioning-configuration Status=Enabled
    
    # Create DynamoDB table for state locking
    aws dynamodb create-table \
        --table-name "${PROJECT_NAME}-terraform-locks" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
        --region $AWS_REGION \
        2>/dev/null || log_warning "DynamoDB table may already exist"
    
    log_success "Terraform backend setup complete!"
}

validate_terraform_vars() {
    log_info "Validating Terraform variables..."
    
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        log_error "terraform.tfvars file not found. Please copy terraform.tfvars.example and fill in your values."
        exit 1
    fi
    
    # Check for required variables
    required_vars=("readymode_username" "readymode_password")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var" "$TERRAFORM_DIR/terraform.tfvars"; then
            log_error "Required variable '$var' not found in terraform.tfvars"
            exit 1
        fi
    done
    
    log_success "Terraform variables validated!"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."
    
    cd $TERRAFORM_DIR
    
    # Initialize Terraform
    terraform init
    
    # Plan deployment
    log_info "Creating Terraform plan..."
    terraform plan -var-file="terraform.tfvars" -out=tfplan
    
    # Ask for confirmation
    echo
    read -p "Do you want to apply this Terraform plan? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Deployment cancelled by user."
        exit 0
    fi
    
    # Apply changes
    log_info "Applying Terraform changes..."
    terraform apply tfplan
    
    # Get outputs
    ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url)
    LOAD_BALANCER_DNS=$(terraform output -raw load_balancer_dns)
    
    cd - > /dev/null
    
    log_success "Infrastructure deployment complete!"
    log_info "ECR Repository: $ECR_REPOSITORY_URL"
    log_info "Load Balancer DNS: $LOAD_BALANCER_DNS"
}

build_and_push_image() {
    log_info "Building and pushing Docker image..."
    
    # Get ECR repository URL from Terraform output
    cd $TERRAFORM_DIR
    ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url)
    cd - > /dev/null
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY_URL
    
    # Build image
    log_info "Building Docker image..."
    docker build -f cloud-migration/Dockerfile -t $PROJECT_NAME .
    
    # Tag image
    docker tag $PROJECT_NAME:latest $ECR_REPOSITORY_URL:latest
    docker tag $PROJECT_NAME:latest $ECR_REPOSITORY_URL:$(git rev-parse --short HEAD)
    
    # Push image
    log_info "Pushing image to ECR..."
    docker push $ECR_REPOSITORY_URL:latest
    docker push $ECR_REPOSITORY_URL:$(git rev-parse --short HEAD)
    
    log_success "Docker image pushed successfully!"
}

update_ecs_service() {
    log_info "Updating ECS service..."
    
    # Force new deployment
    aws ecs update-service \
        --cluster "${PROJECT_NAME}-cluster" \
        --service "${PROJECT_NAME}-service" \
        --force-new-deployment \
        --region $AWS_REGION
    
    log_info "Waiting for service to stabilize..."
    aws ecs wait services-stable \
        --cluster "${PROJECT_NAME}-cluster" \
        --services "${PROJECT_NAME}-service" \
        --region $AWS_REGION
    
    log_success "ECS service updated successfully!"
}

show_deployment_info() {
    log_info "Deployment Information:"
    echo "========================"
    
    cd $TERRAFORM_DIR
    echo "Application URL: http://$(terraform output -raw load_balancer_dns)"
    echo "ECR Repository: $(terraform output -raw ecr_repository_url)"
    echo "RDS Endpoint: $(terraform output -raw rds_endpoint)"
    echo "S3 Bucket: $(terraform output -raw s3_bucket_name)"
    echo "CloudWatch Logs: $(terraform output -raw cloudwatch_log_group)"
    cd - > /dev/null
    
    echo
    log_success "Deployment completed successfully!"
    log_info "You can now access your VOS Tool at the Application URL above."
}

# Main deployment flow
main() {
    log_info "Starting VOS Tool deployment to AWS..."
    
    check_prerequisites
    setup_terraform_backend
    validate_terraform_vars
    deploy_infrastructure
    build_and_push_image
    update_ecs_service
    show_deployment_info
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "infrastructure-only")
        check_prerequisites
        setup_terraform_backend
        validate_terraform_vars
        deploy_infrastructure
        ;;
    "image-only")
        check_prerequisites
        build_and_push_image
        update_ecs_service
        ;;
    "destroy")
        log_warning "This will destroy all infrastructure!"
        read -p "Are you sure? Type 'yes' to confirm: " -r
        if [[ $REPLY == "yes" ]]; then
            cd $TERRAFORM_DIR
            terraform destroy -var-file="terraform.tfvars"
            cd - > /dev/null
            log_success "Infrastructure destroyed!"
        else
            log_info "Destruction cancelled."
        fi
        ;;
    *)
        echo "Usage: $0 [deploy|infrastructure-only|image-only|destroy]"
        echo "  deploy            - Full deployment (default)"
        echo "  infrastructure-only - Deploy infrastructure only"
        echo "  image-only        - Build and deploy image only"
        echo "  destroy           - Destroy all infrastructure"
        exit 1
        ;;
esac
