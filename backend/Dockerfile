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

# Copy only required backend code (excludes archive/, test files, etc. via .dockerignore)
# Backend doesn't need: app.py, frontend/, ui/, static/ (frontend-only)
# Copy backend directory (includes backend/models/, backend/api/, backend/core/, etc.)
COPY backend/ /app/backend/
COPY lib/ /app/lib/
COPY analyzer/ /app/analyzer/
COPY audio_pipeline/ /app/audio_pipeline/
COPY processing/ /app/processing/
COPY models/ /app/models/
COPY tools/ /app/tools/
COPY automation/ /app/automation/
COPY config.py /app/

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
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run backend
# Use $PORT environment variable from Railway, fallback to 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
