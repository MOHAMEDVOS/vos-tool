#!/usr/bin/env python3
"""
Simple CPU Optimizer for 12th Gen Intel i7-1255U
Applies only the most effective optimizations without interfering with existing system.
"""

import os
import logging
import psutil

logger = logging.getLogger(__name__)

class SimpleCPUOptimizer:
    """Simple, non-intrusive CPU optimizations for Intel i7-1255U."""
    
    def __init__(self):
        self.applied = False
        
    def apply_environment_optimizations(self):
        """Apply only the most effective environment optimizations."""
        if self.applied:
            return
            
        try:
            # Only set the most critical environment variables
            # These won't interfere with existing optimizations
            
            # Intel MKL - most important for Intel CPUs
            if 'MKL_NUM_THREADS' not in os.environ:
                os.environ['MKL_NUM_THREADS'] = '4'
            
            # OpenMP - helps with parallel processing
            if 'OMP_NUM_THREADS' not in os.environ:
                os.environ['OMP_NUM_THREADS'] = '4'
            
            # Tokenizer parallelism - safe to enable
            if 'TOKENIZERS_PARALLELISM' not in os.environ:
                os.environ['TOKENIZERS_PARALLELISM'] = 'true'
            
            # Disable MPS on Intel CPU (safe)
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'
            
            self.applied = True
            logger.info("Applied simple CPU optimizations for Intel i7-1255U")
            
        except Exception as e:
            logger.warning(f"Could not apply CPU optimizations: {e}")
    
    def get_system_info(self) -> dict:
        """Get basic system information."""
        try:
            return {
                'cpu_cores': psutil.cpu_count(logical=True),
                'physical_cores': psutil.cpu_count(logical=False),
                'memory_gb': psutil.virtual_memory().total / (1024**3),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent
            }
        except:
            return {}

# Global simple optimizer
_simple_optimizer = None

def apply_simple_cpu_optimizations():
    """Apply simple CPU optimizations globally."""
    global _simple_optimizer
    if _simple_optimizer is None:
        _simple_optimizer = SimpleCPUOptimizer()
        _simple_optimizer.apply_environment_optimizations()
    return _simple_optimizer
