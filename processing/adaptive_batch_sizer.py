"""
Adaptive Batch Sizer for Batch Processing
Dynamically calculates optimal batch size based on system resources and file characteristics.
"""

import logging
import os
import threading
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available, using fixed batch sizing")


class AdaptiveBatchSizer:
    """
    Calculates optimal batch size based on:
    - Available system memory
    - CPU load
    - File sizes
    - Processing history
    """
    
    def __init__(self):
        self.min_batch_size = 10
        self.max_batch_size = 1000
        self.default_batch_size = 1000
        self.memory_threshold = 0.75  # Use max 75% of available memory
        self.cpu_threshold = 0.80  # Reduce batch size if CPU > 80%
        
        # Track processing history for adaptive sizing
        self.processing_times = []
        self.avg_processing_time = None
    
    def calculate_batch_size(self, 
                           file_paths: List[Path], 
                           current_batch_index: int = 0,
                           completed_files: int = 0,
                           total_files: int = 0) -> int:
        """
        Calculate optimal batch size based on current system state.
        
        Args:
            file_paths: List of file paths in current batch window
            current_batch_index: Current batch number (0-indexed)
            completed_files: Number of files already processed
            total_files: Total number of files to process
            
        Returns:
            Optimal batch size
        """
        if not PSUTIL_AVAILABLE:
            # Fallback to default if psutil not available
            return self.default_batch_size
        
        # Start with base batch size
        batch_size = self.default_batch_size
        
        try:
            # 1. Adjust based on available memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent / 100.0
            available_memory_gb = memory.available / (1024 ** 3)
            
            if memory_percent > self.memory_threshold:
                # Memory is high, reduce batch size
                reduction_factor = (memory_percent - self.memory_threshold) / (1.0 - self.memory_threshold)
                batch_size = int(batch_size * (1.0 - reduction_factor * 0.5))  # Reduce up to 50%
                logger.debug(f"High memory usage ({memory_percent:.1%}), reducing batch size to {batch_size}")
            elif memory_percent < 0.5 and available_memory_gb > 4:
                # Memory is low, can increase batch size
                increase_factor = (0.5 - memory_percent) * 2  # Scale from 0 to 1
                batch_size = int(batch_size * (1.0 + increase_factor * 0.5))  # Increase up to 50%
                logger.debug(f"Low memory usage ({memory_percent:.1%}), increasing batch size to {batch_size}")
            
            # 2. Adjust based on CPU load
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_load = cpu_percent / 100.0
            
            if cpu_load > self.cpu_threshold:
                # CPU is busy, reduce batch size
                reduction_factor = (cpu_load - self.cpu_threshold) / (1.0 - self.cpu_threshold)
                batch_size = int(batch_size * (1.0 - reduction_factor * 0.4))  # Reduce up to 40%
                logger.debug(f"High CPU load ({cpu_percent:.1f}%), reducing batch size to {batch_size}")
            elif cpu_load < 0.5:
                # CPU is idle, can increase batch size
                increase_factor = (0.5 - cpu_load) * 2
                batch_size = int(batch_size * (1.0 + increase_factor * 0.3))  # Increase up to 30%
                logger.debug(f"Low CPU load ({cpu_percent:.1f}%), increasing batch size to {batch_size}")
            
            # 3. Adjust based on file sizes
            if file_paths:
                total_size = sum(f.stat().st_size for f in file_paths[:min(100, len(file_paths))] if f.exists())
                avg_file_size_mb = (total_size / len(file_paths[:min(100, len(file_paths))])) / (1024 ** 2) if file_paths else 0
                
                if avg_file_size_mb > 10:  # Large files (>10MB)
                    # Reduce batch size for large files
                    reduction = min(0.5, (avg_file_size_mb - 10) / 20)  # Reduce up to 50% for very large files
                    batch_size = int(batch_size * (1.0 - reduction))
                    logger.debug(f"Large files detected (avg {avg_file_size_mb:.1f}MB), reducing batch size to {batch_size}")
                elif avg_file_size_mb < 2:  # Small files (<2MB)
                    # Can increase batch size for small files
                    increase = min(0.3, (2 - avg_file_size_mb) / 2)  # Increase up to 30%
                    batch_size = int(batch_size * (1.0 + increase))
                    logger.debug(f"Small files detected (avg {avg_file_size_mb:.1f}MB), increasing batch size to {batch_size}")
            
            # 4. Adjust based on processing history (if available)
            if self.avg_processing_time and self.avg_processing_time > 30:
                # Slow processing, reduce batch size
                reduction = min(0.3, (self.avg_processing_time - 30) / 60)  # Reduce up to 30% for very slow processing
                batch_size = int(batch_size * (1.0 - reduction))
                logger.debug(f"Slow processing detected ({self.avg_processing_time:.1f}s/file), reducing batch size to {batch_size}")
            
            # 5. Ensure batch size is within bounds
            batch_size = max(self.min_batch_size, min(self.max_batch_size, batch_size))
            
            # 6. Adjust for remaining files (smaller batches near the end)
            remaining_files = total_files - completed_files
            if remaining_files < batch_size * 2:
                # Near the end, use smaller batches to avoid over-allocation
                batch_size = min(batch_size, max(self.min_batch_size, remaining_files // 2))
                logger.debug(f"Near end of processing ({remaining_files} files left), adjusting batch size to {batch_size}")
            
            return batch_size
            
        except Exception as e:
            logger.warning(f"Error calculating adaptive batch size: {e}, using default {self.default_batch_size}")
            return self.default_batch_size
    
    def update_processing_time(self, processing_time: float):
        """
        Update average processing time based on recent history.
        
        Args:
            processing_time: Time taken to process a file (seconds)
        """
        self.processing_times.append(processing_time)
        
        # Keep only last 20 processing times
        if len(self.processing_times) > 20:
            self.processing_times.pop(0)
        
        # Calculate average
        if self.processing_times:
            self.avg_processing_time = sum(self.processing_times) / len(self.processing_times)
    
    def reset(self):
        """Reset processing history."""
        self.processing_times = []
        self.avg_processing_time = None


# Per-user batch sizer instances
_batch_sizers: Dict[str, AdaptiveBatchSizer] = {}
_batch_sizer_lock = threading.Lock()

def get_adaptive_batch_sizer(username: Optional[str] = None) -> AdaptiveBatchSizer:
    """
    Get or create an adaptive batch sizer instance for a user.
    
    Args:
        username: Username for per-user isolation. If None, uses default instance.
        
    Returns:
        AdaptiveBatchSizer instance for the user
    """
    global _batch_sizers
    
    # Use default key if no username
    user_key = username or "__default__"
    
    if user_key not in _batch_sizers:
        with _batch_sizer_lock:
            if user_key not in _batch_sizers:
                _batch_sizers[user_key] = AdaptiveBatchSizer()
                logger.info(f"Created AdaptiveBatchSizer instance for {user_key}")
    
    return _batch_sizers[user_key]

