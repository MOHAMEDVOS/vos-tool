# VOS Tool Cloud Migration Guide

This directory contains all the necessary files and configurations to deploy your VOS Tool to the cloud using modern DevOps practices.

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- Terraform >= 1.6.0
- Docker
- Git

### 1. One-Command Deployment
```bash
# Make the deployment script executable
chmod +x cloud-migration/deploy.sh

# Run full deployment
./cloud-migration/deploy.sh
```

### 2. Manual Step-by-Step Deployment

#### Step 1: Configure Variables
```bash
# Copy and edit Terraform variables
cp cloud-migration/terraform/terraform.tfvars.example cloud-migration/terraform/terraform.tfvars
# Edit terraform.tfvars with your values

# Copy and edit environment variables
cp cloud-migration/.env.example cloud-migration/.env
# Edit .env with your values
```

#### Step 2: Deploy Infrastructure
```bash
cd cloud-migration/terraform
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

#### Step 3: Build and Deploy Application
```bash
# Get ECR repository URL from Terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)

# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
docker build -f cloud-migration/Dockerfile -t vos-tool .
docker tag vos-tool:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Update ECS service
aws ecs update-service --cluster vos-tool-cluster --service vos-tool-service --force-new-deployment
```

## 📁 Directory Structure

```
cloud-migration/
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Local development setup
├── deploy.sh                  # Automated deployment script
├── nginx.conf                 # Reverse proxy configuration
├── init.sql                   # Database initialization
├── .env.example               # Environment variables template
├── terraform/                 # Infrastructure as Code
│   ├── main.tf               # Main Terraform configuration
│   ├── variables.tf          # Variable definitions
│   ├── outputs.tf            # Output values
│   └── terraform.tfvars.example
├── kubernetes/                # Kubernetes manifests (alternative)
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── postgres.yaml
│   ├── secrets.yaml
│   ├── storage.yaml
│   └── ingress.yaml
├── monitoring/                # Monitoring stack
│   ├── prometheus.yaml
│   └── grafana.yaml
├── .github/workflows/         # CI/CD pipeline
│   └── deploy.yml
└── README.md                  # This file
```

## 🏗️ Architecture Overview

### AWS Infrastructure
- **ECS Fargate**: Containerized application hosting
- **Application Load Balancer**: Traffic distribution and SSL termination
- **RDS Aurora Serverless v2**: PostgreSQL database with auto-scaling
- **S3**: Call recordings storage
- **ECR**: Docker image registry
- **VPC**: Isolated network with public/private subnets
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Logging and monitoring

### Security Features
- **VPC with private subnets** for database and application
- **Security groups** with least-privilege access
- **SSL/TLS encryption** in transit and at rest
- **Secrets Manager** for credential management
- **Rate limiting** and DDoS protection
- **Security headers** via Nginx reverse proxy

## 💰 Cost Estimates

### AWS Monthly Costs (US East 1)

#### Production Setup (2 instances, 24/7):
- **ECS Fargate**: ~$200/month (2 × 4 vCPU, 16GB RAM)
- **RDS Aurora Serverless v2**: ~$150/month (average 2 ACU)
- **Application Load Balancer**: ~$20/month
- **S3 Storage**: ~$25/month (1TB recordings)
- **Data Transfer**: ~$30/month
- **CloudWatch Logs**: ~$10/month
- **NAT Gateway**: ~$45/month (2 AZs)
- **Other services**: ~$20/month

**Total: ~$500/month**

#### Development Setup (1 instance, 8 hours/day):
- **ECS Fargate**: ~$35/month
- **RDS Aurora Serverless v2**: ~$25/month (0.5 ACU minimum)
- **Other services**: ~$50/month

**Total: ~$110/month**

#### Cost Optimization Options:
- Use **Spot instances** for development: -50% cost
- **Reserved instances** for production: -30% cost
- **S3 Intelligent Tiering**: -20% storage cost
- **Single AZ** for development: -50% NAT costs

## 🔧 Configuration Options

### Environment Variables
```bash
# Application
DEPLOYMENT_MODE=enterprise
FORCE_READYMODE=true
MAX_CONCURRENT_DOWNLOADS=10

# Database
POSTGRES_HOST=your-rds-endpoint
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=secure_password

# ReadyMode
READYMODE_USER=your_username
READYMODE_PASSWORD=your_password
```

### Terraform Variables
```hcl
# Instance sizing
ecs_cpu = 4096        # 4 vCPUs
ecs_memory = 16384    # 16 GB RAM
ecs_desired_count = 2 # Number of instances

# Database sizing
rds_min_capacity = 0.5  # Minimum Aurora capacity
rds_max_capacity = 4    # Maximum Aurora capacity

# Network
vpc_cidr = "10.0.0.0/16"
aws_region = "us-east-1"
```

## 🔍 Monitoring & Logging

### CloudWatch Dashboards
- Application metrics (CPU, memory, requests)
- Database performance
- Error rates and response times
- Custom business metrics

### Alerts
- High CPU/memory usage
- Application downtime
- Database connection issues
- High error rates

### Log Aggregation
- Application logs in CloudWatch
- Structured JSON logging
- Log retention policies
- Search and filtering

## 🚀 CI/CD Pipeline

### GitHub Actions Workflow
1. **Test**: Run unit tests and linting
2. **Build**: Create Docker image
3. **Push**: Upload to ECR
4. **Deploy**: Update ECS service
5. **Verify**: Health checks and smoke tests

### Deployment Strategies
- **Blue-Green**: Zero-downtime deployments
- **Rolling**: Gradual instance replacement
- **Canary**: Traffic-based rollouts

## 🔒 Security Best Practices

### Infrastructure Security
- Private subnets for application and database
- Security groups with minimal access
- VPC Flow Logs for network monitoring
- AWS Config for compliance

### Application Security
- Secrets stored in AWS Secrets Manager
- SSL/TLS encryption everywhere
- Rate limiting and DDoS protection
- Security headers and CSP

### Access Control
- IAM roles with least privilege
- MFA for administrative access
- Audit logging for all actions
- Regular security reviews

## 🔄 Backup & Recovery

### Database Backups
- Automated daily backups (7-day retention)
- Point-in-time recovery
- Cross-region backup replication
- Backup encryption

### Application Data
- S3 versioning for call recordings
- Cross-region replication
- Lifecycle policies for cost optimization

### Disaster Recovery
- Multi-AZ deployment
- Infrastructure as Code for quick recovery
- Documented recovery procedures
- Regular disaster recovery testing

## 🐛 Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check ECS service status
aws ecs describe-services --cluster vos-tool-cluster --services vos-tool-service

# Check CloudWatch logs
aws logs tail /ecs/vos-tool --follow
```

#### Database Connection Issues
```bash
# Check RDS status
aws rds describe-db-clusters --db-cluster-identifier vos-tool-cluster

# Test connectivity from ECS task
aws ecs execute-command --cluster vos-tool-cluster --task TASK_ID --interactive --command "/bin/bash"
```

#### High Costs
- Review CloudWatch billing alerts
- Check for unused resources
- Consider Reserved Instances
- Optimize storage classes

### Support Resources
- AWS Support (if you have a support plan)
- AWS Documentation
- Community forums
- This project's GitHub issues

## 📈 Scaling Considerations

### Horizontal Scaling
- Increase `ecs_desired_count` in Terraform
- Configure auto-scaling based on CPU/memory
- Load balancer handles traffic distribution

### Vertical Scaling
- Increase `ecs_cpu` and `ecs_memory`
- Aurora Serverless auto-scales database
- Monitor performance metrics

### Storage Scaling
- S3 scales automatically
- EFS for shared file storage
- Consider data archival policies

## 🔄 Maintenance

### Regular Tasks
- Update Docker base images
- Apply security patches
- Review and rotate secrets
- Monitor costs and optimize
- Backup verification
- Performance tuning

### Automated Updates
- Dependabot for dependency updates
- Automated security scanning
- Infrastructure drift detection
- Cost optimization recommendations

---

## 📞 Support

For issues with this deployment:
1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Open a GitHub issue with details
4. Contact your cloud administrator

**Happy deploying! 🚀**
