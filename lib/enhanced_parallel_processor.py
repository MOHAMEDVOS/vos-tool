#!/usr/bin/env python3
"""
Enhanced Parallel Processor with CPU Optimizations
Optimized for 12th Gen Intel i7-1255U with hybrid P-core/E-core architecture.
"""

import time
import logging
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple
from pathlib import Path
import sys
import os
import psutil

# Add paths for imports
parent_dir = str(Path(__file__).parent.parent)
lib_dir = str(Path(__file__).parent)
for path in [parent_dir, lib_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

from pydub import AudioSegment
from lib.cpu_optimizer import get_cpu_optimizer

logger = logging.getLogger(__name__)

class EnhancedParallelProcessor:
    """Enhanced parallel processor optimized for Intel 12th Gen hybrid architecture."""
    
    def __init__(self):
        self.cpu_optimizer = get_cpu_optimizer()
        self.parallel_config = self.cpu_optimizer.get_optimal_parallel_config()
        self.whisper_config = self.cpu_optimizer.get_optimal_whisper_config()
        self.memory_config = self.cpu_optimizer.get_memory_optimization_config()
        
        # Set optimal worker counts based on CPU architecture
        self.max_workers = self.parallel_config['max_workers']
        self.heavy_task_workers = 2  # P-cores for transcription
        self.light_task_workers = 4  # E-cores for detection
        
        logger.info(f"Enhanced processor initialized with {self.max_workers} workers")
        logger.info(f"Heavy tasks: {self.heavy_task_workers} workers, Light tasks: {self.light_task_workers} workers")
    
    def _set_thread_priority(self, task_type: str):
        """Set thread priority and CPU affinity based on task type."""
        try:
            current_thread = threading.current_thread()
            
            if task_type == 'transcription':
                # High priority for transcription (CPU intensive)
                self.cpu_optimizer.apply_cpu_affinity('heavy')
                if hasattr(os, 'nice'):
                    os.nice(-5)  # Higher priority on Unix systems
                    
            elif task_type in ['releasing', 'late_hello']:
                # Normal priority for detection tasks
                self.cpu_optimizer.apply_cpu_affinity('light')
                
        except Exception as e:
            logger.debug(f"Could not set thread priority for {task_type}: {e}")
    
    def run_releasing_detection_optimized(self, audio: AudioSegment) -> Dict[str, Any]:
        """Run releasing detection with CPU optimizations."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            self._set_thread_priority('releasing')
            logger.debug(f"[Thread {thread_id}] Starting optimized releasing detection")
            
            from audio_pipeline.detections import releasing_detection
            result = releasing_detection(audio)
            
            processing_time = time.time() - start_time
            logger.debug(f"[Thread {thread_id}] Releasing detection completed in {processing_time:.2f}s")
            
            return {
                'detection_type': 'releasing',
                'result': result,
                'processing_time': processing_time,
                'success': True,
                'thread_id': thread_id,
                'cpu_optimized': True
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"[Thread {thread_id}] Releasing detection failed: {e}")
            
            return {
                'detection_type': 'releasing',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False,
                'thread_id': thread_id
            }
    
    def run_late_hello_detection_optimized(self, audio: AudioSegment) -> Dict[str, Any]:
        """Run late-hello detection with CPU optimizations."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            self._set_thread_priority('late_hello')
            logger.debug(f"[Thread {thread_id}] Starting optimized late-hello detection")
            
            from audio_pipeline.detections import late_hello_detection
            result = late_hello_detection(audio)
            
            processing_time = time.time() - start_time
            logger.debug(f"[Thread {thread_id}] Late-hello detection completed in {processing_time:.2f}s")
            
            return {
                'detection_type': 'late_hello',
                'result': result,
                'processing_time': processing_time,
                'success': True,
                'thread_id': thread_id,
                'cpu_optimized': True
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"[Thread {thread_id}] Late-hello detection failed: {e}")
            
            return {
                'detection_type': 'late_hello',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False,
                'thread_id': thread_id
            }
    
    def run_rebuttal_detection_optimized(self, file_path: str) -> Dict[str, Any]:
        """Run rebuttal detection with full CPU and memory optimizations."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            self._set_thread_priority('transcription')
            logger.debug(f"[Thread {thread_id}] Starting optimized rebuttal detection")
            
            # Import here to avoid circular imports
            from lib.agent_only_detector import AgentOnlyRebuttalDetector
            from lib.audio_optimizer import get_audio_optimizer
            
            # Use enhanced audio optimization
            optimizer = get_audio_optimizer()
            optimized_file, optimization_stats = optimizer.preprocess_for_whisper(file_path)
            
            logger.debug(f"[Thread {thread_id}] Audio optimized in {optimization_stats.get('processing_time', 0):.2f}s")
            
            # Create detector with CPU optimizations
            detector = AgentOnlyRebuttalDetector()
            
            # Apply Whisper optimizations
            if hasattr(detector.transcription_engine.local_engine, 'model') and detector.transcription_engine.local_engine.model:
                # Apply CPU-specific Whisper settings
                whisper_model = detector.transcription_engine.local_engine.model
                # Note: Some settings may need to be applied at model creation time
            
            # Run detection on optimized audio
            result = detector.detect_rebuttals_in_audio(optimized_file)
            
            # Clean up optimized temp file
            if optimized_file != file_path:
                try:
                    os.unlink(optimized_file)
                except:
                    pass
            
            processing_time = time.time() - start_time
            logger.debug(f"[Thread {thread_id}] Rebuttal detection completed in {processing_time:.2f}s")
            
            return {
                'detection_type': 'rebuttal',
                'result': result.get('result', 'Unknown'),
                'confidence_score': result.get('confidence_score', 0),
                'transcript': result.get('transcript', ''),
                'processing_time': processing_time,
                'optimization_stats': optimization_stats,
                'success': True,
                'thread_id': thread_id,
                'cpu_optimized': True,
                'full_result': result
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"[Thread {thread_id}] Rebuttal detection failed: {e}")
            
            return {
                'detection_type': 'rebuttal',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False,
                'thread_id': thread_id
            }
    
    def run_enhanced_parallel_pipeline(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Run the complete pipeline with CPU-specific optimizations.
        
        Uses hybrid architecture efficiently:
        - P-cores for heavy transcription tasks
        - E-cores for light detection tasks
        - Optimized memory usage for 16GB RAM
        """
        overall_start = time.time()
        
        logger.info(f"Starting enhanced parallel pipeline for: {Path(audio_file_path).name}")
        
        # Monitor system performance before starting
        initial_performance = self.cpu_optimizer.monitor_performance()
        logger.info(f"Initial CPU usage: {initial_performance.get('cpu_usage_percent', 0):.1f}%, "
                   f"Memory usage: {initial_performance.get('memory_usage_percent', 0):.1f}%")
        
        # Load audio once for intro detections (memory efficient)
        audio = None
        try:
            audio = AudioSegment.from_file(audio_file_path)
            logger.debug(f"Audio loaded: {len(audio)}ms, {audio.channels} channels")
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            return {'error': f'Failed to load audio: {e}'}
        
        # Create separate thread pools for different task types
        results = {}
        
        # Use different executors for different task types
        with ThreadPoolExecutor(max_workers=self.light_task_workers, 
                               thread_name_prefix="LightTask") as light_executor, \
             ThreadPoolExecutor(max_workers=self.heavy_task_workers, 
                               thread_name_prefix="HeavyTask") as heavy_executor:
            
            # Submit light tasks (intro detections) to E-cores
            light_futures = {}
            
            future_releasing = light_executor.submit(self.run_releasing_detection_optimized, audio)
            light_futures[future_releasing] = 'releasing'
            
            future_late_hello = light_executor.submit(self.run_late_hello_detection_optimized, audio)
            light_futures[future_late_hello] = 'late_hello'
            
            # Submit heavy task (rebuttal detection) to P-cores
            heavy_futures = {}
            
            future_rebuttal = heavy_executor.submit(self.run_rebuttal_detection_optimized, audio_file_path)
            heavy_futures[future_rebuttal] = 'rebuttal'
            
            # Collect light task results first (they should finish quickly)
            for future in as_completed(light_futures):
                task_name = light_futures[future]
                try:
                    result = future.result()
                    results[task_name] = result
                    
                    status = "✅" if result.get('success', False) else "❌"
                    time_taken = result.get('processing_time', 0)
                    thread_id = result.get('thread_id', 'unknown')
                    
                    logger.info(f"{status} {task_name} completed in {time_taken:.2f}s (light task, thread {thread_id})")
                    
                except Exception as e:
                    logger.error(f"Light task {task_name} generated an exception: {e}")
                    results[task_name] = {
                        'detection_type': task_name,
                        'result': 'Error',
                        'error': str(e),
                        'success': False
                    }
            
            # Collect heavy task results
            for future in as_completed(heavy_futures):
                task_name = heavy_futures[future]
                try:
                    result = future.result()
                    results[task_name] = result
                    
                    status = "✅" if result.get('success', False) else "❌"
                    time_taken = result.get('processing_time', 0)
                    thread_id = result.get('thread_id', 'unknown')
                    
                    logger.info(f"{status} {task_name} completed in {time_taken:.2f}s (heavy task, thread {thread_id})")
                    
                except Exception as e:
                    logger.error(f"Heavy task {task_name} generated an exception: {e}")
                    results[task_name] = {
                        'detection_type': task_name,
                        'result': 'Error',
                        'error': str(e),
                        'success': False
                    }
        
        overall_time = time.time() - overall_start
        
        # Monitor final performance
        final_performance = self.cpu_optimizer.monitor_performance()
        
        # Calculate performance metrics
        total_sequential_time = sum(r.get('processing_time', 0) for r in results.values())
        speedup = total_sequential_time / overall_time if overall_time > 0 else 1
        
        # Compile enhanced results
        final_results = {
            'results': results,
            'performance': {
                'overall_time': overall_time,
                'total_sequential_time': total_sequential_time,
                'speedup': speedup,
                'parallel_efficiency': speedup / len(results) if results else 0,
                'cpu_optimized': True,
                'hybrid_architecture_used': True
            },
            'system_performance': {
                'initial': initial_performance,
                'final': final_performance,
                'cpu_usage_change': final_performance.get('cpu_usage_percent', 0) - initial_performance.get('cpu_usage_percent', 0),
                'memory_usage_change': final_performance.get('memory_usage_percent', 0) - initial_performance.get('memory_usage_percent', 0)
            },
            'audio_info': {
                'file': Path(audio_file_path).name,
                'duration_ms': len(audio) if audio else 0,
                'channels': audio.channels if audio else 0
            },
            'optimization_info': {
                'cpu_model': self.cpu_optimizer.cpu_info.get('brand', 'Unknown'),
                'total_cores': self.cpu_optimizer.cpu_info.get('logical_cores', 0),
                'p_cores_used': self.heavy_task_workers,
                'e_cores_used': self.light_task_workers,
                'memory_gb': self.cpu_optimizer.memory_info.get('total_gb', 0)
            }
        }
        
        logger.info(f"Enhanced parallel processing completed in {overall_time:.2f}s")
        logger.info(f"CPU-optimized speedup: {speedup:.1f}x (vs {total_sequential_time:.2f}s sequential)")
        
        return final_results

# Global enhanced processor instance
_enhanced_processor = None

def get_enhanced_processor() -> EnhancedParallelProcessor:
    """Get the global enhanced processor instance."""
    global _enhanced_processor
    if _enhanced_processor is None:
        _enhanced_processor = EnhancedParallelProcessor()
    return _enhanced_processor
