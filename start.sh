#!/usr/bin/env bash
set -e

# Default to Full Mode (ReadyMode enabled) inside container, can be overridden by env
export FORCE_READYMODE=${FORCE_READYMODE:-true}
# Suggest enterprise deployment mode by default
export DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-enterprise}

# GPU optimization settings (if GPU available)
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export TOKENIZERS_PARALLELISM=false

# Default port if not provided by RunPod
PORT=${PORT:-8501}

# Go to project folder
cd /workspace

# Check if RunPod-specific script exists, otherwise use default
if [ -f "/workspace/runpod_start.sh" ]; then
    exec /workspace/runpod_start.sh
else
    # Run Streamlit app (same as your run_app.bat, but Linux style)
    exec streamlit run app.py --server.port "$PORT" --server.address 0.0.0.0
fi
