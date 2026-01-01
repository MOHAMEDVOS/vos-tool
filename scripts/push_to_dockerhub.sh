#!/bin/bash

# Docker Hub Push Script for VOS Tool
# This script builds, tags, and pushes Docker images to Docker Hub
#
# Usage:
#   ./scripts/push_to_dockerhub.sh <dockerhub_username> [version_tag]
#
# Example:
#   ./scripts/push_to_dockerhub.sh myusername
#   ./scripts/push_to_dockerhub.sh myusername v1.0.0

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running${NC}"
    exit 1
fi

# Get Docker Hub username from argument
if [ -z "$1" ]; then
    echo -e "${RED}Error: Docker Hub username is required${NC}"
    echo "Usage: $0 <dockerhub_username> [version_tag]"
    echo "Example: $0 myusername"
    echo "Example: $0 myusername v1.0.0"
    exit 1
fi

DOCKERHUB_USERNAME=$1
VERSION_TAG=${2:-latest}

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VOS Tool - Docker Hub Push Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Docker Hub Username: ${DOCKERHUB_USERNAME}"
echo "Version Tag: ${VERSION_TAG}"
echo ""

# Get the project root directory (parent of scripts/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# Image names
BACKEND_IMAGE="${DOCKERHUB_USERNAME}/vos-backend"
FRONTEND_IMAGE="${DOCKERHUB_USERNAME}/vos-frontend"

echo -e "${YELLOW}Step 1: Building Backend Image...${NC}"
docker build -t "${BACKEND_IMAGE}:${VERSION_TAG}" \
             -t "${BACKEND_IMAGE}:latest" \
             -f backend/Dockerfile .

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Backend image build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backend image built successfully${NC}"
echo ""

echo -e "${YELLOW}Step 2: Building Frontend Image...${NC}"
docker build -t "${FRONTEND_IMAGE}:${VERSION_TAG}" \
             -t "${FRONTEND_IMAGE}:latest" \
             -f frontend/Dockerfile .

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Frontend image build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Frontend image built successfully${NC}"
echo ""

echo -e "${YELLOW}Step 3: Logging into Docker Hub...${NC}"
echo "Please enter your Docker Hub credentials:"
docker login

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker Hub login failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Successfully logged into Docker Hub${NC}"
echo ""

echo -e "${YELLOW}Step 4: Pushing Backend Image...${NC}"
docker push "${BACKEND_IMAGE}:${VERSION_TAG}"
docker push "${BACKEND_IMAGE}:latest"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Backend image push failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backend image pushed successfully${NC}"
echo ""

echo -e "${YELLOW}Step 5: Pushing Frontend Image...${NC}"
docker push "${FRONTEND_IMAGE}:${VERSION_TAG}"
docker push "${FRONTEND_IMAGE}:latest"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Frontend image push failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Frontend image pushed successfully${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All images pushed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Images available at:"
echo "  - ${BACKEND_IMAGE}:${VERSION_TAG}"
echo "  - ${BACKEND_IMAGE}:latest"
echo "  - ${FRONTEND_IMAGE}:${VERSION_TAG}"
echo "  - ${FRONTEND_IMAGE}:latest"
echo ""
echo "To pull these images on another machine:"
echo "  docker pull ${BACKEND_IMAGE}:latest"
echo "  docker pull ${FRONTEND_IMAGE}:latest"
echo ""
echo "See DOCKER_HUB_DEPLOYMENT.md for deployment instructions."

