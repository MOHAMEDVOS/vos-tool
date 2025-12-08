#!/usr/bin/env bash
set -e

# RunPod GPU-Optimized Startup Script
# Optimized for: RTX 4090 (24GB VRAM), 35GB RAM, 6 vCPU

echo "ًںڑ€ Starting VOS Tool on RunPod with GPU acceleration..."

# Set environment variables for GPU optimization
export FORCE_READYMODE=${FORCE_READYMODE:-true}
export DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-enterprise}
export CUDA_VISIBLE_DEVICES=0

# GPU optimization settings
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export TOKENIZERS_PARALLELISM=false

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "ًں“ٹ GPU Information:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
    echo ""
fi

# Check CUDA availability in Python
python3 << EOF
import torch
if torch.cuda.is_available():
    print(f"âœ… CUDA Available: {torch.cuda.get_device_name(0)}")
    print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
    print(f"   CUDA Version: {torch.version.cuda}")
else:
    print("âڑ ï¸ڈ  CUDA not available - falling back to CPU")
EOF

# Default port if not provided by RunPod
PORT=${PORT:-8501}

# Go to project folder
cd /workspace

# Run Streamlit app with GPU-optimized settings
echo "ًںŒگ Starting Streamlit on port $PORT..."
exec streamlit run app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
