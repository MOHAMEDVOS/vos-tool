# Backend Dockerfile - Optimized Multi-Stage Build
# Stage 1: Builder (for compiling Python packages)
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements-backend.txt /app/requirements-backend.txt

# Install Python dependencies
# Install CPU-only PyTorch (only torch, not torchvision/torchaudio - saves ~500MB-1GB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user -r /app/requirements-backend.txt && \
    # Clean up pip cache and unnecessary files
    pip cache purge && \
    find /root/.local -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type d -name "*.dist-info" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type f -name "*.pyc" -delete && \
    find /root/.local -type f -name "*.pyo" -delete

# Stage 2: Runtime (minimal image)
FROM python:3.11-slim

WORKDIR /app

# Install only runtime system dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/America/New_York /etc/localtime && echo America/New_York > /etc/timezone

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Clean up unnecessary files to reduce image size
RUN find /root/.local -type d -name "tests" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type d -name "test" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type d -name "*.dist-info" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type f -name "*.pyc" -delete && \
    find /root/.local -type f -name "*.pyo" -delete && \
    # Remove HuggingFace cache if present (models will be downloaded at runtime if needed)
    rm -rf /root/.cache/huggingface 2>/dev/null || true && \
    # Remove pip cache
    rm -rf /root/.cache/pip 2>/dev/null || true

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TZ=America/New_York \
    # Prevent HuggingFace from downloading models during build
    HF_HOME=/tmp/.cache/huggingface \
    TRANSFORMERS_CACHE=/tmp/.cache/transformers

# Debug: Check what's available in build context
RUN echo "=== Build Context Debug ===" && \
    echo "Current directory:" && pwd && \
    echo "Listing root:" && (ls -la / 2>&1 | head -20 || true) && \
    echo "Checking for backend directory:" && \
    (test -d backend && echo "backend/ exists" || echo "backend/ NOT found") && \
    (test -d backend/models && echo "backend/models/ exists" || echo "backend/models/ NOT found") && \
    (test -f backend/models/schemas.py && echo "backend/models/schemas.py exists" || echo "backend/models/schemas.py NOT found") || true

# Copy only required backend code (excludes archive/, test files, etc. via .dockerignore)
# Backend doesn't need: app.py, frontend/, ui/, static/ (frontend-only)
# Copy backend directory structure
COPY backend/api/ /app/backend/api/
COPY backend/core/ /app/backend/core/
COPY backend/services/ /app/backend/services/
COPY backend/models/ /app/backend/models/
COPY backend/__init__.py /app/backend/__init__.py
COPY backend/main.py /app/backend/main.py
COPY backend/requirements.txt /app/backend/requirements.txt
# Verify backend/models was copied correctly
RUN ls -la /app/backend/models/ && \
    test -f /app/backend/models/__init__.py && \
    test -f /app/backend/models/schemas.py || \
    (echo "ERROR: backend/models files not found!" && \
     echo "Debug: Listing /app/backend/ contents:" && \
     ls -la /app/backend/ && \
     echo "Debug: Checking if models directory exists:" && \
     ls -la /app/backend/models/ 2>&1 || echo "models directory does not exist" && \
     exit 1)
COPY lib/ /app/lib/
COPY analyzer/ /app/analyzer/
COPY audio_pipeline/ /app/audio_pipeline/
COPY processing/ /app/processing/
COPY models/ /app/models/
COPY tools/ /app/tools/
COPY automation/ /app/automation/

# Cache-bust for schema files: change this value to force Railway to rebuild the schema COPY layer.
ARG SCHEMA_CACHEBUST=2026-01-02-001
RUN echo "Schema cachebust=${SCHEMA_CACHEBUST}"

COPY cloud-migration/init.sql /app/cloud-migration/init.sql
COPY cloud-migration/migration_schema.sql /app/cloud-migration/migration_schema.sql
COPY config.py /app/

# Hard fail if schema files are not actually present in the built image.
RUN echo "Schema files check:" && \
    ls -la /app/cloud-migration/ && \
    test -f /app/cloud-migration/init.sql && \
    test -f /app/cloud-migration/migration_schema.sql

# Create necessary directories (will be mounted as volumes in production)
RUN mkdir -p /app/Recordings /app/dashboard_data /app/logs && \
    chmod -R 755 /app && \
    # Final cleanup: remove any remaining cache or temporary files
    rm -rf /tmp/* /var/tmp/* 2>/dev/null || true && \
    # Remove Python package documentation and examples
    find /root/.local -type d -name "doc" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type d -name "docs" -exec rm -r {} + 2>/dev/null || true && \
    find /root/.local -type d -name "examples" -exec rm -r {} + 2>/dev/null || true

# Expose backend port
EXPOSE 8000

# Health check (requires requests package from requirements)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD sh -c "python -c \"import os, requests; port=os.getenv('PORT','8000'); requests.get(f'http://localhost:{port}/health', timeout=5)\"" || exit 1

# Run backend
# Use $PORT environment variable from Railway, fallback to 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
