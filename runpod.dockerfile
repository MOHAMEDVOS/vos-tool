# RunPod-Optimized Dockerfile
# Specifically optimized for RTX 4090 (24GB VRAM), 35GB RAM, 6 vCPU

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    git \
    wget \
    curl \
    ca-certificates \
    unzip \
    build-essential \
    cmake \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (more reliable than Chromium on Ubuntu 22.04)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install ChromeDriver using webdriver-manager (handled by Python package)
# The webdriver-manager package will handle ChromeDriver automatically
RUN ln -s /usr/bin/google-chrome /usr/bin/chromium || true

# Make "python" point to python3 and upgrade pip
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    python -m pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /workspace

# Copy requirements first (better caching)
COPY requirements.txt ./

# Install PyTorch with CUDA 12.1 support first (required for other packages)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install llama-cpp-python with CUDA support (for RTX 4090)

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Ensure start scripts are executable
RUN chmod +x /workspace/start.sh

# Default port for Streamlit
ENV PORT=8501

# GPU optimization environment variables
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
ENV TOKENIZERS_PARALLELISM=false

# Expose Streamlit port
EXPOSE 8501

# Default command: run the start script
CMD ["/workspace/start.sh"]
