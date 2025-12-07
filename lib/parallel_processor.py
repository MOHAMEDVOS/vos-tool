#!/usr/bin/env python3
"""
Parallel Processing System
Runs multiple detection operations concurrently for faster processing.
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Callable, List, Tuple
from pathlib import Path
import sys
import os

# Add paths for imports
parent_dir = str(Path(__file__).parent.parent)
lib_dir = str(Path(__file__).parent)
for path in [parent_dir, lib_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

from pydub import AudioSegment

logger = logging.getLogger(__name__)

class ParallelDetectionProcessor:
    """Runs multiple detection operations in parallel for faster processing."""
    
    def __init__(self, max_workers: int = 3):
        """
        Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of concurrent threads
        """
        self.max_workers = max_workers
        self.results = {}
        self.timings = {}
        
        logger.info(f"ParallelDetectionProcessor initialized with {max_workers} workers")
    
    def run_releasing_detection(self, audio: AudioSegment) -> Dict[str, Any]:
        """Run releasing detection with error handling."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            logger.debug(f"[Thread {thread_id}] Starting releasing detection")
            
            from audio_pipeline.detections import releasing_detection
            result = releasing_detection(audio)
            
            processing_time = time.time() - start_time
            logger.debug(f"[Thread {thread_id}] Releasing detection completed in {processing_time:.2f}s")
            
            return {
                'detection_type': 'releasing',
                'result': result,
                'processing_time': processing_time,
                'success': True,
                'thread_id': thread_id
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
    
    def run_late_hello_detection(self, audio: AudioSegment) -> Dict[str, Any]:
        """Run late-hello detection with error handling."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            logger.debug(f"[Thread {thread_id}] Starting late-hello detection")
            
            from audio_pipeline.detections import late_hello_detection
            result = late_hello_detection(audio)
            
            processing_time = time.time() - start_time
            logger.debug(f"[Thread {thread_id}] Late-hello detection completed in {processing_time:.2f}s")
            
            return {
                'detection_type': 'late_hello',
                'result': result,
                'processing_time': processing_time,
                'success': True,
                'thread_id': thread_id
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
    
    def run_rebuttal_detection(self, file_path: str, use_optimization: bool = True) -> Dict[str, Any]:
        """Run rebuttal detection with optional audio optimization."""
        start_time = time.time()
        thread_id = threading.current_thread().ident
        
        try:
            logger.debug(f"[Thread {thread_id}] Starting rebuttal detection")
            
            # Import here to avoid circular imports
            from lib.agent_only_detector import AgentOnlyRebuttalDetector
            
            # Optionally use audio optimization
            if use_optimization:
                from lib.audio_optimizer import get_audio_optimizer
                optimizer = get_audio_optimizer()
                
                # Preprocess audio for better performance
                optimized_file, optimization_stats = optimizer.preprocess_for_whisper(file_path)
                logger.debug(f"[Thread {thread_id}] Audio optimized in {optimization_stats.get('processing_time', 0):.2f}s")
                
                # Use optimized file for detection
                detection_file = optimized_file
            else:
                detection_file = file_path
                optimization_stats = {}
            
            # Run detection
            detector = AgentOnlyRebuttalDetector()
            result = detector.detect_rebuttals_in_audio(detection_file)
            
            # Clean up optimized temp file if created
            if use_optimization and 'temp_file' in optimization_stats:
                try:
                    os.unlink(optimization_stats['temp_file'])
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
    
    def run_parallel_detections(self, audio_file_path: str, 
                              run_releasing: bool = True,
                              run_late_hello: bool = True,
                              run_rebuttal: bool = True,
                              use_audio_optimization: bool = True) -> Dict[str, Any]:
        """
        Run multiple detections in parallel.
        
        Args:
            audio_file_path: Path to audio file
            run_releasing: Whether to run releasing detection
            run_late_hello: Whether to run late-hello detection
            run_rebuttal: Whether to run rebuttal detection
            use_audio_optimization: Whether to use audio optimization for rebuttal detection
            
        Returns:
            Dictionary with all detection results and timing information
        """
        overall_start = time.time()
        
        logger.info(f"Starting parallel detections for: {Path(audio_file_path).name}")
        
        # Load audio once for intro detections
        audio = None
        if run_releasing or run_late_hello:
            try:
                audio = AudioSegment.from_file(audio_file_path)
                logger.debug(f"Audio loaded: {len(audio)}ms, {audio.channels} channels")
            except Exception as e:
                logger.error(f"Failed to load audio: {e}")
                return {'error': f'Failed to load audio: {e}'}
        
        # Prepare tasks
        tasks = []
        task_functions = []
        
        if run_releasing and audio is not None:
            tasks.append(('releasing', self.run_releasing_detection, audio))
        
        if run_late_hello and audio is not None:
            tasks.append(('late_hello', self.run_late_hello_detection, audio))
        
        if run_rebuttal:
            tasks.append(('rebuttal', self.run_rebuttal_detection, audio_file_path, use_audio_optimization))
        
        if not tasks:
            return {'error': 'No tasks to execute'}
        
        # Execute tasks in parallel
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tasks))) as executor:
            # Submit all tasks
            future_to_task = {}
            
            for task_name, task_func, *args in tasks:
                future = executor.submit(task_func, *args)
                future_to_task[future] = task_name
                logger.debug(f"Submitted {task_name} detection task")
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                
                try:
                    result = future.result()
                    results[task_name] = result
                    
                    status = "✅" if result.get('success', False) else "❌"
                    time_taken = result.get('processing_time', 0)
                    thread_id = result.get('thread_id', 'unknown')
                    
                    logger.info(f"{status} {task_name} completed in {time_taken:.2f}s (thread {thread_id})")
                    
                except Exception as e:
                    logger.error(f"Task {task_name} generated an exception: {e}")
                    results[task_name] = {
                        'detection_type': task_name,
                        'result': 'Error',
                        'error': str(e),
                        'success': False
                    }
        
        overall_time = time.time() - overall_start
        
        # Calculate performance metrics
        total_sequential_time = sum(r.get('processing_time', 0) for r in results.values())
        speedup = total_sequential_time / overall_time if overall_time > 0 else 1
        
        # Compile final results
        final_results = {
            'results': results,
            'performance': {
                'overall_time': overall_time,
                'total_sequential_time': total_sequential_time,
                'speedup': speedup,
                'parallel_efficiency': speedup / len(tasks) if tasks else 0
            },
            'audio_info': {
                'file': Path(audio_file_path).name,
                'duration_ms': len(audio) if audio else 0,
                'channels': audio.channels if audio else 0
            }
        }
        
        logger.info(f"Parallel processing completed in {overall_time:.2f}s")
        logger.info(f"Speedup: {speedup:.1f}x (vs {total_sequential_time:.2f}s sequential)")
        
        return final_results

# Global processor instance
_parallel_processor = None

def get_parallel_processor(max_workers: int = 3) -> ParallelDetectionProcessor:
    """Get the global parallel processor instance."""
    global _parallel_processor
    if _parallel_processor is None:
        _parallel_processor = ParallelDetectionProcessor(max_workers)
    return _parallel_processor
