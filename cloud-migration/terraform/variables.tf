# Terraform variables for VOS Tool deployment

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "vos-tool"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ECS Configuration
variable "ecs_cpu" {
  description = "CPU units for ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 4096  # 4 vCPUs
}

variable "ecs_memory" {
  description = "Memory for ECS task in MB"
  type        = number
  default     = 16384  # 16 GB
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

# RDS Configuration
variable "db_name" {
  description = "Database name"
  type        = string
  default     = "vos_tool"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "vos_user"
}

variable "rds_min_capacity" {
  description = "Minimum RDS Aurora capacity"
  type        = number
  default     = 0.5
}

variable "rds_max_capacity" {
  description = "Maximum RDS Aurora capacity"
  type        = number
  default     = 4
}

# Application Configuration
variable "readymode_username" {
  description = "ReadyMode username"
  type        = string
  sensitive   = true
}

variable "readymode_password" {
  description = "ReadyMode password"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate in ACM (optional)"
  type        = string
  default     = ""
}
