#!/usr/bin/env python3
"""
CPU-Specific Optimizer for 12th Gen Intel i7-1255U
Optimizes pipeline performance for hybrid P-core/E-core architecture with 16GB RAM.
"""

import os
import sys
import psutil
import platform
import multiprocessing
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)

class IntelCPUOptimizer:
    """Optimizes performance for 12th Gen Intel i7-1255U hybrid architecture."""
    
    def __init__(self):
        self.cpu_info = self._detect_cpu_capabilities()
        self.memory_info = self._detect_memory_capabilities()
        self.optimal_settings = self._calculate_optimal_settings()
        
        logger.info(f"CPU Optimizer initialized for {self.cpu_info['brand']}")
        logger.info(f"Detected: {self.cpu_info['cores']} cores, {self.memory_info['total_gb']:.1f}GB RAM")
    
    def _detect_cpu_capabilities(self) -> Dict[str, Any]:
        """Detect CPU capabilities and architecture."""
        try:
            cpu_count = multiprocessing.cpu_count()
            
            # 12th Gen i7-1255U has 10 cores (2 P-cores + 8 E-cores)
            # Logical cores = 12 (P-cores have hyperthreading)
            cpu_info = {
                'brand': platform.processor(),
                'cores': cpu_count,
                'physical_cores': psutil.cpu_count(logical=False),
                'logical_cores': psutil.cpu_count(logical=True),
                'is_12th_gen_intel': '12th Gen Intel' in platform.processor(),
                'has_hybrid_architecture': cpu_count >= 10,  # Likely P+E cores
                'base_frequency': 1.7,  # GHz - your CPU's base frequency
                'max_frequency': 4.7   # GHz - typical boost for i7-1255U
            }
            
            # Detect if we have hybrid P+E core architecture
            if cpu_info['logical_cores'] > cpu_info['physical_cores']:
                cpu_info['has_hyperthreading'] = True
                # Estimate P-cores (with HT) and E-cores (without HT)
                # i7-1255U: 2 P-cores (4 logical) + 8 E-cores (8 logical) = 12 logical
                cpu_info['estimated_p_cores'] = 2
                cpu_info['estimated_e_cores'] = 8
            
            return cpu_info
            
        except Exception as e:
            logger.warning(f"Could not detect CPU capabilities: {e}")
            return {
                'brand': 'Unknown',
                'cores': multiprocessing.cpu_count(),
                'physical_cores': multiprocessing.cpu_count(),
                'logical_cores': multiprocessing.cpu_count(),
                'is_12th_gen_intel': False,
                'has_hybrid_architecture': False
            }
    
    def _detect_memory_capabilities(self) -> Dict[str, Any]:
        """Detect memory capabilities and usage."""
        try:
            memory = psutil.virtual_memory()
            
            memory_info = {
                'total_bytes': memory.total,
                'total_gb': memory.total / (1024**3),
                'available_bytes': memory.available,
                'available_gb': memory.available / (1024**3),
                'usage_percent': memory.percent,
                'optimal_for_ml': memory.total >= 8 * (1024**3),  # 8GB+
                'can_load_large_models': memory.total >= 16 * (1024**3)  # 16GB+
            }
            
            return memory_info
            
        except Exception as e:
            logger.warning(f"Could not detect memory capabilities: {e}")
            return {
                'total_gb': 16.0,  # Fallback to your specs
                'available_gb': 12.0,
                'optimal_for_ml': True,
                'can_load_large_models': True
            }
    
    def _calculate_optimal_settings(self) -> Dict[str, Any]:
        """Calculate optimal settings based on hardware."""
        settings = {
            # Thread settings optimized for hybrid architecture
            'max_worker_threads': min(6, self.cpu_info['logical_cores']),  # Conservative for stability
            'whisper_threads': 4,  # Optimal for Whisper on your CPU
            'semantic_threads': 2,  # For sentence transformers
            
            # Memory settings for 16GB RAM
            'max_model_cache_size': 4,  # GB - models to keep in memory
            'audio_chunk_size': 30,  # seconds - optimal for your RAM
            'batch_size': 8,  # For semantic processing
            
            # CPU-specific optimizations
            'use_mkl_optimization': True,  # Intel MKL for faster math
            'cpu_affinity_optimization': self.cpu_info['has_hybrid_architecture'],
            'memory_mapping': True,  # Use memory mapping for large files
            
            # Performance tuning
            'aggressive_caching': True,  # With 16GB, we can cache aggressively
            'preload_models': True,  # Preload models for faster access
            'optimize_for_latency': True  # Optimize for single-file speed
        }
        
        # Adjust for hybrid architecture
        if self.cpu_info.get('has_hybrid_architecture', False):
            # Use P-cores for heavy tasks, E-cores for background
            settings['heavy_task_threads'] = 2  # P-cores for transcription
            settings['light_task_threads'] = 4  # E-cores for detection
            settings['background_threads'] = 2  # E-cores for I/O
        
        return settings
    
    def optimize_environment(self):
        """Set environment variables for optimal performance."""
        optimizations = {}
        
        try:
            # Intel MKL optimizations for faster math operations
            os.environ['MKL_NUM_THREADS'] = str(self.optimal_settings['whisper_threads'])
            os.environ['OMP_NUM_THREADS'] = str(self.optimal_settings['whisper_threads'])
            optimizations['MKL_NUM_THREADS'] = self.optimal_settings['whisper_threads']
            
            # PyTorch optimizations for CPU
            os.environ['TORCH_NUM_THREADS'] = str(self.optimal_settings['whisper_threads'])
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            optimizations['TORCH_NUM_THREADS'] = self.optimal_settings['whisper_threads']
            
            # Memory optimizations
            os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'  # Disable MPS on Intel
            os.environ['TOKENIZERS_PARALLELISM'] = 'true'  # Enable parallel tokenization
            optimizations['TOKENIZERS_PARALLELISM'] = True
            
            # Transformers optimizations
            os.environ['TRANSFORMERS_CACHE'] = str(Path.home() / '.cache' / 'transformers')
            os.environ['HF_DATASETS_CACHE'] = str(Path.home() / '.cache' / 'datasets')
            
            logger.info("Environment optimized for Intel 12th Gen i7-1255U")
            return optimizations
            
        except Exception as e:
            logger.warning(f"Could not optimize environment: {e}")
            return optimizations
    
    def get_optimal_whisper_config(self) -> Dict[str, Any]:
        """Get optimal Whisper configuration for your CPU."""
        return {
            'device': 'cpu',  # Your CPU doesn't have dedicated GPU
            'num_workers': self.optimal_settings['whisper_threads'],
            'batch_size': 1,  # Single file processing is optimal
            'fp16': False,  # CPU doesn't support FP16, use FP32
            'use_fast_tokenizer': True,
            'low_mem': False,  # With 16GB, we can use more memory for speed
            'compression_ratio_threshold': 2.4,
            'logprob_threshold': -1.0,
            'no_speech_threshold': 0.6,
            'condition_on_previous_text': True,
            'temperature': [0.0, 0.2, 0.4],  # Multiple temperatures for robustness
            'beam_size': 5,  # Good balance for your CPU
            'patience': 2.0,
            'length_penalty': 1.0,
            'suppress_tokens': [-1],
            'initial_prompt': "This is a phone call conversation:",
            'word_timestamps': False,  # Disable for speed unless needed
            'prepend_punctuations': "\"'([{-",
            'append_punctuations': "\"'.,:)]}!"
        }
    
    def get_optimal_parallel_config(self) -> Dict[str, Any]:
        """Get optimal parallel processing configuration."""
        return {
            'max_workers': self.optimal_settings['max_worker_threads'],
            'thread_pool_executor': True,  # Better for I/O bound tasks
            'process_pool_executor': False,  # Avoid overhead on single machine
            'chunk_size': self.optimal_settings['audio_chunk_size'],
            'prefetch_factor': 2,  # Prefetch next chunks
            'memory_limit_gb': min(8, self.memory_info['available_gb'] * 0.8),
            'enable_cpu_affinity': self.optimal_settings['cpu_affinity_optimization']
        }
    
    def get_memory_optimization_config(self) -> Dict[str, Any]:
        """Get memory optimization configuration for 16GB RAM."""
        return {
            'model_cache_size_gb': self.optimal_settings['max_model_cache_size'],
            'audio_cache_size_mb': 512,  # Cache processed audio
            'enable_memory_mapping': True,
            'garbage_collection_threshold': 0.8,  # GC when 80% memory used
            'preload_models': True,  # With 16GB, preload for speed
            'use_shared_memory': True,  # Share memory between threads
            'optimize_model_loading': True
        }
    
    def apply_cpu_affinity(self, process_type: str = 'heavy'):
        """Apply CPU affinity for optimal performance on hybrid architecture."""
        if not self.optimal_settings.get('cpu_affinity_optimization', False):
            return
        
        try:
            current_process = psutil.Process()
            
            if process_type == 'heavy':
                # Bind heavy tasks (transcription) to P-cores (typically 0-3)
                # P-cores usually have lower CPU IDs
                p_core_cpus = list(range(0, 4))  # First 4 logical cores (2 P-cores with HT)
                current_process.cpu_affinity(p_core_cpus)
                logger.debug(f"Set CPU affinity for heavy task to P-cores: {p_core_cpus}")
                
            elif process_type == 'light':
                # Bind light tasks to E-cores (typically 4-11)
                e_core_cpus = list(range(4, min(12, self.cpu_info['logical_cores'])))
                current_process.cpu_affinity(e_core_cpus)
                logger.debug(f"Set CPU affinity for light task to E-cores: {e_core_cpus}")
                
        except Exception as e:
            logger.warning(f"Could not set CPU affinity: {e}")
    
    def monitor_performance(self) -> Dict[str, Any]:
        """Monitor current system performance."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            performance = {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'available_memory_gb': memory.available / (1024**3),
                'cpu_frequency_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
                'optimal_performance': cpu_percent < 80 and memory.percent < 85
            }
            
            return performance
            
        except Exception as e:
            logger.warning(f"Could not monitor performance: {e}")
            return {'optimal_performance': True}
    
    def get_system_info_summary(self) -> str:
        """Get a summary of system capabilities and optimizations."""
        summary = f"""
🖥️ SYSTEM OPTIMIZATION SUMMARY
{'='*50}

💻 CPU Information:
   Processor: {self.cpu_info['brand']}
   Logical Cores: {self.cpu_info['logical_cores']}
   Physical Cores: {self.cpu_info['physical_cores']}
   Hybrid Architecture: {'Yes' if self.cpu_info.get('has_hybrid_architecture') else 'No'}
   Estimated P-cores: {self.cpu_info.get('estimated_p_cores', 'Unknown')}
   Estimated E-cores: {self.cpu_info.get('estimated_e_cores', 'Unknown')}

💾 Memory Information:
   Total RAM: {self.memory_info['total_gb']:.1f} GB
   Available RAM: {self.memory_info['available_gb']:.1f} GB
   Usage: {self.memory_info['usage_percent']:.1f}%
   ML Optimized: {'Yes' if self.memory_info['optimal_for_ml'] else 'No'}

⚡ Optimization Settings:
   Max Worker Threads: {self.optimal_settings['max_worker_threads']}
   Whisper Threads: {self.optimal_settings['whisper_threads']}
   Model Cache Size: {self.optimal_settings['max_model_cache_size']} GB
   Audio Chunk Size: {self.optimal_settings['audio_chunk_size']} seconds
   CPU Affinity: {'Enabled' if self.optimal_settings['cpu_affinity_optimization'] else 'Disabled'}
   Aggressive Caching: {'Enabled' if self.optimal_settings['aggressive_caching'] else 'Disabled'}

🎯 Performance Recommendations:
   - Use P-cores for transcription (heavy tasks)
   - Use E-cores for detection (light tasks)
   - Enable model preloading with 16GB RAM
   - Use Intel MKL optimizations
   - Cache models aggressively
   - Process audio in 30-second chunks
"""
        return summary

# Global optimizer instance
_cpu_optimizer = None

def get_cpu_optimizer() -> IntelCPUOptimizer:
    """Get the global CPU optimizer instance."""
    global _cpu_optimizer
    if _cpu_optimizer is None:
        _cpu_optimizer = IntelCPUOptimizer()
        _cpu_optimizer.optimize_environment()
    return _cpu_optimizer
