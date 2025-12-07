#!/usr/bin/env python3
"""
Optimized Pipeline - Implements all performance fixes to beat 60.43s target
Pre-loads models, optimizes parameters, reduces overhead.
"""

import time
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths for imports
parent_dir = str(Path(__file__).parent.parent)
lib_dir = str(Path(__file__).parent)
for path in [parent_dir, lib_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Set logging to INFO for progress tracking in CMD
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedPipeline:
    """Optimized pipeline designed to beat 60.43s target."""
    
    def __init__(self):
        self.models_preloaded = False
        self.whisper_model = None
        self.semantic_engine = None
        self.detector = None
        
        # Apply system optimizations
        self._apply_system_optimizations()
    
    def _apply_system_optimizations(self):
        """Apply system-level optimizations."""
        try:
            # Set environment variables for optimal performance
            os.environ['MKL_NUM_THREADS'] = '4'
            os.environ['OMP_NUM_THREADS'] = '4'
            os.environ['TORCH_NUM_THREADS'] = '4'
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # Disable to avoid warnings
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            
            # Set process priority to high (Windows)
            try:
                import psutil
                current_process = psutil.Process()
                current_process.nice(psutil.HIGH_PRIORITY_CLASS)
            except:
                pass
                
        except Exception as e:
            logger.error(f"System optimization failed: {e}")
    
    def preload_models(self):
        """Pre-load all models to eliminate initialization overhead."""
        if self.models_preloaded:
            return
        
        print("🔄 Pre-loading models (one-time overhead)...")
        preload_start = time.time()
        
        try:
            # 1. Load Whisper model
            from models import get_whisper_model
            self.whisper_model = get_whisper_model()
            
            # 2. Load Semantic engine
            from analyzer.rebuttal_detection import SemanticDetectionEngine, KeywordRepository
            keyword_repo = KeywordRepository()
            self.semantic_engine = SemanticDetectionEngine(keyword_repo)
            
            # 3. Create optimized detector
            from lib.agent_only_detector import AgentOnlyRebuttalDetector
            self.detector = AgentOnlyRebuttalDetector()
            
            preload_time = time.time() - preload_start
            print(f"✅ Models pre-loaded in {preload_time:.2f}s")
            self.models_preloaded = True
            
        except Exception as e:
            logger.error(f"Model preloading failed: {e}")
            self.models_preloaded = False
    
    def run_releasing_detection_fast(self, audio) -> Dict[str, Any]:
        """Fast releasing detection."""
        start_time = time.time()
        
        try:
            from audio_pipeline.detections import releasing_detection
            result = releasing_detection(audio)
            
            processing_time = time.time() - start_time
            return {
                'detection_type': 'releasing',
                'result': result,
                'processing_time': processing_time,
                'success': True
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                'detection_type': 'releasing',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False
            }
    
    def run_late_hello_detection_fast(self, audio) -> Dict[str, Any]:
        """Fast late-hello detection."""
        start_time = time.time()
        
        try:
            from audio_pipeline.detections import late_hello_detection
            result = late_hello_detection(audio)
            
            processing_time = time.time() - start_time
            return {
                'detection_type': 'late_hello',
                'result': result,
                'processing_time': processing_time,
                'success': True
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                'detection_type': 'late_hello',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False
            }
    
    def run_rebuttal_detection_fast(self, file_path: str) -> Dict[str, Any]:
        """Fast rebuttal detection with optimized parameters."""
        start_time = time.time()
        
        try:
            # Use pre-loaded detector
            if not self.models_preloaded:
                self.preload_models()
            
            # Run detection with pre-loaded models (no initialization overhead)
            result = self.detector.detect_rebuttals_in_audio(file_path)
            
            processing_time = time.time() - start_time
            return {
                'detection_type': 'rebuttal',
                'result': result.get('result', 'Unknown'),
                'confidence_score': result.get('confidence_score', 0),
                'transcript': result.get('transcript', ''),
                'processing_time': processing_time,
                'success': True,
                'full_result': result
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                'detection_type': 'rebuttal',
                'result': 'Error',
                'error': str(e),
                'processing_time': processing_time,
                'success': False
            }
    
    def run_optimized_pipeline(self, audio_file_path: str) -> Dict[str, Any]:
        """Run the complete optimized pipeline."""
        overall_start = time.time()
        
        # Ensure models are pre-loaded
        if not self.models_preloaded:
            self.preload_models()
        
        # Load audio once
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_file_path)
        except Exception as e:
            return {'error': f'Failed to load audio: {e}'}
        
        # Run detections in parallel with pre-loaded models
        results = {}
        
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="OptimizedTask") as executor:
            # Submit all tasks
            future_releasing = executor.submit(self.run_releasing_detection_fast, audio)
            future_late_hello = executor.submit(self.run_late_hello_detection_fast, audio)
            future_rebuttal = executor.submit(self.run_rebuttal_detection_fast, audio_file_path)
            
            futures = {
                future_releasing: 'releasing',
                future_late_hello: 'late_hello',
                future_rebuttal: 'rebuttal'
            }
            
            # Collect results
            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    result = future.result()
                    results[task_name] = result
                except Exception as e:
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
        
        # Log essential results only
        file_name = Path(audio_file_path).name
        print(f"📁 {file_name}")
        
        for detection_type, result in results.items():
            if result.get('success'):
                detection_result = result.get('result', 'Unknown')
                if detection_type == 'releasing':
                    print(f"   🔄 Releasing: {detection_result}")
                elif detection_type == 'late_hello':
                    print(f"   👋 Late Hello: {detection_result}")
                elif detection_type == 'rebuttal':
                    confidence = result.get('confidence_score', 0)
                    print(f"   🎯 Rebuttal: {detection_result} (confidence: {confidence:.3f})")
            else:
                print(f"   ❌ {detection_type.upper()}: Failed")
        
        return {
            'results': results,
            'performance': {
                'overall_time': overall_time,
                'total_sequential_time': total_sequential_time,
                'speedup': speedup,
                'parallel_efficiency': speedup / len(results) if results else 0,
                'models_preloaded': self.models_preloaded
            },
            'audio_info': {
                'file': Path(audio_file_path).name,
                'duration_ms': len(audio) if audio else 0,
                'channels': audio.channels if audio else 0
            }
        }

# Global optimized pipeline instance
_optimized_pipeline = None

def get_optimized_pipeline() -> OptimizedPipeline:
    """Get the global optimized pipeline instance."""
    global _optimized_pipeline
    if _optimized_pipeline is None:
        _optimized_pipeline = OptimizedPipeline()
    return _optimized_pipeline
