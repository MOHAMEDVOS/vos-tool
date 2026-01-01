# How to Check Docker Image Size

## Method 1: After Building Locally

Build the image locally and check its size:

```bash
# Build the backend image
docker build -f backend/Dockerfile -t vos-backend:test .

# Check image size
docker images vos-backend:test

# Or get detailed size information
docker image inspect vos-backend:test --format='{{.Size}}' | numfmt --to=iec-i --suffix=B
```

## Method 2: Check During Build

Add this to the end of your Dockerfile to see layer sizes:

```dockerfile
# At the end of Dockerfile, add:
RUN du -sh /root/.local && \
    du -sh /app && \
    df -h
```

## Method 3: Analyze Image Layers

See what's taking up space in each layer:

```bash
# Build with history
docker build -f backend/Dockerfile -t vos-backend:test .

# Show image history with sizes
docker history vos-backend:test --human --format "table {{.CreatedBy}}\t{{.Size}}"

# Or use dive (if installed) for interactive analysis
dive vos-backend:test
```

## Method 4: Check Specific Directories

Add to Dockerfile to see what's large:

```dockerfile
RUN echo "=== Size Analysis ===" && \
    du -sh /root/.local/* 2>/dev/null | sort -h && \
    du -sh /app/* 2>/dev/null | sort -h && \
    echo "=== Top 10 Largest ===" && \
    find /root/.local -type f -exec du -h {} + 2>/dev/null | sort -rh | head -10
```

## Method 5: Railway Build Logs

Railway shows the final image size in the build logs:
- Go to Railway Dashboard → Your Service → Deployments
- Click "View logs" on the failed deployment
- Look for: `Image of size X.XX GB exceeded limit of 4.0 GB`

## Method 6: Quick Size Check Script

Create a script to check size after build:

```bash
# check-size.ps1 (PowerShell)
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | Select-String "vos-"
```

## Expected Sizes

- **Base Python image**: ~150-200MB
- **PyTorch CPU-only**: ~1-2GB
- **transformers + sentence-transformers**: ~1-2GB
- **Other dependencies**: ~500MB-1GB
- **Application code**: ~50-100MB
- **Chrome (frontend only)**: ~200-300MB

**Total should be**: ~3-4GB (we're at 9GB, so something is wrong)

## What to Look For

1. **HuggingFace models cached**: Check `/root/.cache/huggingface` - can be 2-4GB
2. **PyTorch with GPU support**: Should be CPU-only (~1GB vs ~3GB)
3. **Duplicate packages**: Check if packages are installed multiple times
4. **Large model files**: Check if models are being downloaded during build

## Quick Fix: Check Current Image Size

Run this to see your current local build size:

```bash
docker build -f backend/Dockerfile -t vos-backend:size-test . && docker images vos-backend:size-test
```

