#!/bin/bash
set -e

# Default to Full Mode (ReadyMode enabled) inside container
export FORCE_READYMODE=${FORCE_READYMODE:-true}
export DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-enterprise}
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export TOKENIZERS_PARALLELISM=false
PORT=${PORT:-8501}

cd /workspace

if [ -f "/workspace/runpod_start.sh" ]; then
    exec /workspace/runpod_start.sh
else
    exec streamlit run app.py --server.port "$PORT" --server.address 0.0.0.0
fi