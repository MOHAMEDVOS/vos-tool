# Frontend Dockerfile - Optimized Multi-Stage Build
# Stage 1: Builder (for compiling Python packages)
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements-frontend.txt /app/requirements-frontend.txt

# Install Python dependencies
# Install CPU-only PyTorch (only torch, not torchvision/torchaudio - saves ~500MB-1GB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user -r /app/requirements-frontend.txt

# Stage 2: Runtime (minimal image)
FROM python:3.11-slim

WORKDIR /app

# Install only runtime system dependencies (no build tools)
# Include Chrome/ChromeDriver for ReadyMode automation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    wget \
    gnupg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and ChromeDriver for ReadyMode automation
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

# Copy only required frontend code (excludes archive/, test files, etc. via .dockerignore)
COPY frontend/ /app/frontend/
COPY app.py /app/
COPY call_review.py /app/
COPY static/ /app/static/
COPY config.py /app/
COPY lib/ /app/lib/
COPY analyzer/ /app/analyzer/
COPY audio_pipeline/ /app/audio_pipeline/
COPY processing/ /app/processing/
COPY models/ /app/models/
COPY ui/ /app/ui/
COPY tools/ /app/tools/
COPY automation/ /app/automation/

# Create Streamlit config directory and file
RUN mkdir -p /root/.streamlit && \
    echo "[server]\n\
port = 8501\n\
address = \"0.0.0.0\"\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
headless = true\n\
\n\
[browser]\n\
gatherUsageStats = false\n" > /root/.streamlit/config.toml

# Create necessary directories (will be mounted as volumes in production)
RUN mkdir -p /app/Recordings /app/dashboard_data /app/logs && \
    chmod -R 755 /app

# Expose Streamlit port
EXPOSE 8501

# Health check (requires requests package from requirements)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8501/_stcore/health', timeout=5)" || exit 1

# Run Streamlit
# Use $PORT environment variable from Railway, fallback to 8501
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
