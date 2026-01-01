# Railway Docker Configuration Guide

## Problem
Railway is using Nixpacks (buildpack) instead of Docker, causing build timeouts. We need to force Railway to use Docker builds.

## Solution: Configure Railway Service Settings

### Step 1: Configure Backend Service

1. **Go to Railway Dashboard** → Your Project → **Backend Service**
2. **Click "Settings" tab**
3. **Scroll to "Build & Deploy" section**
4. **Set the following:**
   - **Root Directory**: Leave empty (or set to `.`)
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Build Command**: Leave empty (Docker will handle it)
5. **Save changes**

### Step 2: Configure Frontend Service (if separate)

1. **Go to Railway Dashboard** → Your Project → **Frontend Service**
2. **Click "Settings" tab**
3. **Scroll to "Build & Deploy" section**
4. **Set the following:**
   - **Root Directory**: Leave empty (or set to `.`)
   - **Dockerfile Path**: `frontend/Dockerfile`
   - **Build Command**: Leave empty (Docker will handle it)
5. **Save changes**

### Step 3: Alternative - Delete and Recreate Services

If the above doesn't work:

1. **Delete the existing service** in Railway
2. **Create a new service** → **GitHub Repo**
3. **Select your repository**: `MOHAMEDVOS/vos-tool`
4. **In the service settings**, before deploying:
   - Set **Root Directory**: `.`
   - Set **Dockerfile Path**: `backend/Dockerfile` (for backend) or `frontend/Dockerfile` (for frontend)
5. **Deploy**

## Why This Happens

Railway auto-detects build methods:
- If it finds `requirements.txt` → Uses Nixpacks (buildpack)
- If it finds `Dockerfile` → Uses Docker

When both exist, Railway may choose Nixpacks. By explicitly setting the Dockerfile path in service settings, we force Railway to use Docker.

## Verification

After configuration:
1. **Trigger a new deployment**
2. **Check build logs** - You should see:
   - `FROM python:3.11-slim` (Docker build)
   - NOT `install mise packages` (Nixpacks)
3. **Build should complete** without timeout

## Files Created

- `nixpacks.toml` - Attempts to disable Nixpacks (may not be sufficient alone)
- This guide - Manual configuration steps

**Note**: Railway service settings override file-based configuration, so manual configuration in the UI is the most reliable method.

