# Railway Setup Steps - Fix 9GB Image Issue

## Current Problem
- Railway is building a 9GB image (exceeds 4GB limit)
- Local build is only 2.57GB (within limit)
- Railway is using "Railpack Default" instead of Docker

## Solution: Configure Railway Settings

### Step 1: Set Root Directory
1. In the "Root Directory" field (you can see it in the Source section):
   - **Set to**: `.` (a single dot) OR leave it **empty**
   - This tells Railway to use the repository root as the build context

### Step 2: Change Builder to Dockerfile
1. Scroll down or click **"Build"** in the right sidebar
2. Find the **"Builder"** section (you should see a dropdown)
3. Click the dropdown that currently shows **"Railpack Default"**
4. Select **"Dockerfile"** from the dropdown
   - It should say: "Build with a Dockerfile using BuildKit. Docs"
5. This tells Railway to use your Dockerfile instead of Railpack

### Step 3: Set Dockerfile Path (Environment Variable)
Since your Dockerfile is in `backend/Dockerfile` (not root), you need to tell Railway where it is:

1. Go to **"Variables"** tab (next to "Settings")
2. Click **"+ New Variable"** or **"Add Variable"**
3. Set:
   - **Name**: `RAILWAY_DOCKERFILE_PATH`
   - **Value**: `backend/Dockerfile` (for backend service) OR `frontend/Dockerfile` (for frontend service)
4. Click **"Add"** or **"Save"**

### Step 4: Save and Deploy
1. Go back to **"Settings"** tab
2. Click the purple **"Deploy"** button (or "Apply X changes" button)
3. Railway will trigger a new build

### Step 5: Verify Build
1. Go to **"Deployments"** tab
2. Click **"View logs"** on the new deployment
3. Look for:
   - ✅ `Using detected Dockerfile!` or `Using Dockerfile: backend/Dockerfile`
   - ❌ NOT `Using Railpack` or `Using Nixpacks`

## Expected Result
- Image size should be ~2.5-3GB (within 4GB limit)
- Build should complete successfully
- Deployment should start

## If You Have Two Services (Backend + Frontend)
You need to configure EACH service separately:

1. **Backend Service**:
   - Root Directory: `.` (or empty)
   - Builder: Select "Dockerfile"
   - Environment Variable: `RAILWAY_DOCKERFILE_PATH` = `backend/Dockerfile`

2. **Frontend Service**:
   - Root Directory: `.` (or empty)
   - Builder: Select "Dockerfile"
   - Environment Variable: `RAILWAY_DOCKERFILE_PATH` = `frontend/Dockerfile`

## What You Should See
- **Builder dropdown** with options:
  - Railpack Default (currently selected - change this!)
  - Dockerfile ← **SELECT THIS**
  - Nixpacks Deprecated

## Troubleshooting
- If you don't see "Builder" dropdown: Click "Build" in the right sidebar
- If build still fails: Check the build logs for error messages
- If image still too large: The Dockerfile optimizations should help, but check logs for what's being included

