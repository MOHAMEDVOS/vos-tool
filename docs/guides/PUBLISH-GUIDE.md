# Publishing To Docker Hub

This guide explains how to publish the React webapp and FastAPI backend images.

## Prerequisites

1. **Docker Hub Account**
   - Create account at https://hub.docker.com
   - Note your username

2. **Docker Desktop Running**
   - Ensure Docker Desktop is installed and running

## Quick Publish (Automated)

### Windows (PowerShell)

```powershell
# 1. Login to Docker Hub
docker login

# 2. Build and push the images manually
# The old Streamlit publish script is retired.
```

### Manual Steps

If you prefer to do it manually:

```bash
# 1. Login to Docker Hub
docker login

# 2. Build and tag backend image
docker build -t your-username/vos-backend:latest -f backend/Dockerfile .
docker tag your-username/vos-backend:latest your-username/vos-backend:v1.0.0

# 3. Build and tag React webapp image
docker build -t your-username/vos-webapp:latest -f webapp/Dockerfile ./webapp
docker tag your-username/vos-webapp:latest your-username/vos-webapp:v1.0.0

# 4. Push images
docker push your-username/vos-backend:latest
docker push your-username/vos-backend:v1.0.0
docker push your-username/vos-webapp:latest
docker push your-username/vos-webapp:v1.0.0
```

## After Publishing

1. **Update docker-compose.example.yml**
   - Replace `your-dockerhub-username` with your actual username
   - Commit the change

2. **Verify on Docker Hub**
   - Visit https://hub.docker.com/r/your-username/vos-backend
   - Visit https://hub.docker.com/r/your-username/vos-webapp
   - Ensure images are visible

3. **Test Pulling**
   ```bash
   # Test on a clean machine or different directory
   docker pull your-username/vos-backend:latest
   docker pull your-username/vos-webapp:latest
   ```

## Image Sizes

Expected image sizes:
- Backend: ~800MB-1.2GB
- Webapp: ~50MB-150MB

First push may take 10-30 minutes depending on your internet speed.

## Updating Images

To update images after making changes:

```bash
# Rebuild and push
docker build -t your-username/vos-backend:latest -f backend/Dockerfile .
docker build -t your-username/vos-webapp:latest -f webapp/Dockerfile ./webapp
docker push your-username/vos-backend:latest
docker push your-username/vos-webapp:latest
```

Users can update with:
```bash
docker-compose pull
docker-compose up -d
```

## Troubleshooting

### "unauthorized: authentication required"
- Run `docker login` again
- Verify your username is correct

### "denied: requested access to the resource is denied"
- Check repository name matches your Docker Hub username
- Ensure repository exists on Docker Hub (created automatically on first push)

### Build fails
- Check Docker Desktop is running
- Verify Dockerfile paths are correct
- Check available disk space

---

**Last Updated**: 2026
