"""
RunPod GPU Configuration
Optimized settings for RTX 4090 (24GB VRAM), 35GB RAM, 6 vCPU
"""

import os
import torch

# GPU Configuration
GPU_CONFIG = {
    'device': 'cuda' if torch.cuda.is_available() else 'cpu',
    'device_id': 0,
    'max_memory': {0: "22GB"},  # Reserve 2GB for system, use 22GB for models
    'dtype': torch.float16 if torch.cuda.is_available() else torch.float32,
}

# Model Configuration for RTX 4090
MODEL_CONFIG = {
    'whisper': {
        'model': 'openai/whisper-medium',  # Using medium model for better accuracy
        'device': GPU_CONFIG['device'],
        'dtype': GPU_CONFIG['dtype'],
        'batch_size': 6 if GPU_CONFIG['device'] == 'cuda' else 1,  # Increased batch size for better throughput
    },
    'llama': {
        'n_gpu_layers': 40,  # Increased GPU offloading for RTX 4090 (from 35)
        'n_ctx': 4096,  # Larger context window (4K tokens)
        'n_batch': 512,  # Batch size for prompt processing
        'n_threads': 6,  # Increased to match vCPU count
    },
    'sentence_transformer': {
        'device': GPU_CONFIG['device'],
        'batch_size': 32 if GPU_CONFIG['device'] == 'cuda' else 8,
    }
}

# Batch Processing Configuration
BATCH_CONFIG = {
    'max_workers': 6,  # Increased to match vCPU count (from 4)
    'gpu_batch_size': 12,  # Increased parallel processing (from 8)
    'cpu_batch_size': 4,  # Increased CPU batch size (from 2)
}

def get_gpu_info():
    """Get GPU information for logging."""
    if torch.cuda.is_available():
        return {
            'name': torch.cuda.get_device_name(0),
            'memory_total': torch.cuda.get_device_properties(0).total_memory / 1e9,
            'memory_allocated': torch.cuda.memory_allocated(0) / 1e9,
            'memory_reserved': torch.cuda.memory_reserved(0) / 1e9,
            'cuda_version': torch.version.cuda,
        }
    return None

def print_gpu_status():
    """Print current GPU status."""
    gpu_info = get_gpu_info()
    if gpu_info:
        print(f"🚀 GPU: {gpu_info['name']}")
        print(f"   Total VRAM: {gpu_info['memory_total']:.1f}GB")
        print(f"   Allocated: {gpu_info['memory_allocated']:.2f}GB")
        print(f"   Reserved: {gpu_info['memory_reserved']:.2f}GB")
        print(f"   CUDA Version: {gpu_info['cuda_version']}")
    else:
        print("⚠️  No GPU detected - using CPU mode")

if __name__ == "__main__":
    print_gpu_status()
