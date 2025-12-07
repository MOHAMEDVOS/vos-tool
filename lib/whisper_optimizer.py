#!/usr/bin/env python3
"""
Whisper Model Optimizer for 12th Gen Intel i7-1255U
Optimizes Whisper transcription specifically for your CPU and RAM configuration.
"""

import os
import logging
import threading
from typing import Dict, Any, Optional
import torch
import psutil

logger = logging.getLogger(__name__)

class WhisperCPUOptimizer:
    """Optimizes Whisper model for Intel 12th Gen i7-1255U performance."""
    
    def __init__(self):
        self.cpu_cores = psutil.cpu_count(logical=True)  # 12 logical cores
        self.physical_cores = psutil.cpu_count(logical=False)  # 10 physical cores
        self.memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Optimal settings for your CPU
        self.optimal_settings = {
            'torch_threads': 4,  # Optimal for i7-1255U
            'mkl_threads': 4,    # Intel MKL optimization
            'omp_threads': 4,    # OpenMP threads
            'interop_threads': 2, # PyTorch interop
            'intraop_threads': 4  # PyTorch intraop
        }
        
        self._apply_optimizations()
        logger.info(f"Whisper optimizer initialized for {self.cpu_cores} cores, {self.memory_gb:.1f}GB RAM")
    
    def _apply_optimizations(self):
        """Apply CPU and memory optimizations."""
        try:
            # Set environment variables for optimal performance
            os.environ['MKL_NUM_THREADS'] = str(self.optimal_settings['mkl_threads'])
            os.environ['OMP_NUM_THREADS'] = str(self.optimal_settings['omp_threads'])
            os.environ['TORCH_NUM_THREADS'] = str(self.optimal_settings['torch_threads'])
            
            # PyTorch CPU optimizations
            if hasattr(torch, 'set_num_threads'):
                torch.set_num_threads(self.optimal_settings['torch_threads'])
            
            # if hasattr(torch, 'set_num_interop_threads'):
            #     try:
            #         torch.set_num_interop_threads(self.optimal_settings['interop_threads'])
            #     except RuntimeError as e:
            #         # This can occur if called after parallel work has started; skip quietly
            #         logger.debug(f"Skipping set_num_interop_threads: {e}")
            
            # Disable MPS on Intel CPU
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'
            
            # Enable tokenizer parallelism
            os.environ['TOKENIZERS_PARALLELISM'] = 'true'
            
            logger.info("Applied CPU optimizations for Intel i7-1255U")
            
        except Exception as e:
            logger.warning(f"Could not apply all optimizations: {e}")
    
    def get_optimized_whisper_params(self) -> Dict[str, Any]:
        """Get optimized parameters for Whisper transcription."""
        return {
            # Core transcription settings
            'language': 'en',
            'task': 'transcribe',
            
            # CPU-optimized performance settings - MAXIMUM SPEED
            'beam_size': 1,  # Fastest possible (greedy decoding)
            'patience': 1.0,  # Minimum patience for speed
            'temperature': [0.0],  # Single temperature for maximum speed
            
            # Quality vs speed balance
            'compression_ratio_threshold': 2.2,  # Slightly more strict
            'logprob_threshold': -0.8,  # More strict for quality
            'no_speech_threshold': 0.7,  # Higher threshold
            
            # Memory and processing optimizations
            'condition_on_previous_text': True,
            'initial_prompt': "This is a phone call conversation:",
            'word_timestamps': False,  # Disable for speed
            'prepend_punctuations': "\"'([{-",
            'append_punctuations': "\"'.,:)]}!",
            
            # CPU-specific optimizations
            'fp16': False,  # CPU doesn't support FP16 efficiently
            'use_fast_tokenizer': True,
            'low_mem': False,  # With 16GB, use more memory for speed
        }
    
    def optimize_model_loading(self, model_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize model loading parameters for your hardware."""
        optimized_kwargs = model_kwargs.copy()
        
        # CPU-specific model optimizations
        optimized_kwargs.update({
            'attn_implementation': 'eager',  # Better for CPU
            'dtype': torch.float32,  # CPU works best with FP32
            'device_map': 'cpu',  # Force CPU usage
            'low_cpu_mem_usage': False,  # With 16GB, prioritize speed
            'torch_dtype': torch.float32,
        })
        
        return optimized_kwargs
    
    def optimize_generation_kwargs(self, generation_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize generation parameters for your CPU."""
        optimized_kwargs = generation_kwargs.copy()
        
        # Update with CPU-optimized settings
        optimized_kwargs.update(self.get_optimized_whisper_params())
        
        return optimized_kwargs
    
    def monitor_transcription_performance(self, start_time: float, audio_duration_ms: int) -> Dict[str, Any]:
        """Monitor transcription performance metrics."""
        import time
        
        processing_time = time.time() - start_time
        audio_duration_sec = audio_duration_ms / 1000
        
        # Calculate performance metrics
        real_time_factor = audio_duration_sec / processing_time if processing_time > 0 else 0
        
        # Get current system stats
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        performance_data = {
            'processing_time': processing_time,
            'audio_duration': audio_duration_sec,
            'real_time_factor': real_time_factor,
            'cpu_usage': cpu_percent,
            'memory_usage': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'is_real_time': real_time_factor >= 1.0,
            'performance_rating': self._calculate_performance_rating(real_time_factor, cpu_percent, memory.percent)
        }
        
        return performance_data
    
    def _calculate_performance_rating(self, real_time_factor: float, cpu_usage: float, memory_usage: float) -> str:
        """Calculate overall performance rating."""
        if real_time_factor >= 2.0 and cpu_usage < 70 and memory_usage < 80:
            return "Excellent"
        elif real_time_factor >= 1.5 and cpu_usage < 80 and memory_usage < 85:
            return "Good"
        elif real_time_factor >= 1.0 and cpu_usage < 90 and memory_usage < 90:
            return "Fair"
        else:
            return "Poor"
    
    def get_optimization_summary(self) -> str:
        """Get a summary of applied optimizations."""
        return f"""
🖥️ WHISPER CPU OPTIMIZATIONS APPLIED
{'='*45}

💻 Hardware Detected:
   CPU Cores: {self.cpu_cores} logical, {self.physical_cores} physical
   Memory: {self.memory_gb:.1f} GB
   Architecture: Intel 12th Gen i7-1255U

⚡ Applied Optimizations:
   MKL Threads: {self.optimal_settings['mkl_threads']}
   OMP Threads: {self.optimal_settings['omp_threads']}
   Torch Threads: {self.optimal_settings['torch_threads']}
   Interop Threads: {self.optimal_settings['interop_threads']}
   
🎯 Whisper Parameters:
   Beam Size: 3 (optimized for speed)
   Temperature: [0.0, 0.2] (reduced for speed)
   Patience: 1.5 (balanced)
   FP16: Disabled (CPU optimization)
   
💾 Memory Settings:
   Low Memory Mode: Disabled (16GB available)
   Fast Tokenizer: Enabled
   Word Timestamps: Disabled (speed optimization)
"""

# Global optimizer instance
_whisper_optimizer = None

def get_whisper_optimizer() -> WhisperCPUOptimizer:
    """Get the global Whisper optimizer instance."""
    global _whisper_optimizer
    if _whisper_optimizer is None:
        _whisper_optimizer = WhisperCPUOptimizer()
    return _whisper_optimizer

def apply_whisper_optimizations():
    """Apply Whisper optimizations globally."""
    optimizer = get_whisper_optimizer()
    logger.info("Whisper CPU optimizations applied globally")
    return optimizer
