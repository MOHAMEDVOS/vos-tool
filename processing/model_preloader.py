"""
Model Pre-loader for Batch Processing
Pre-loads models before batch processing starts to avoid sequential loading.
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

class ModelPreloader:
    """Pre-loads models before batch processing to avoid sequential loading."""
    
    def __init__(self):
        self.whisper_model = None
        self.semantic_model = None
        self.embeddings = None
        self.agent_detector = None
        self._load_lock = threading.Lock()
        self._loaded = False
    
    def preload_all_models(self) -> bool:
        """
        Pre-load all models before batch processing starts.
        Returns True if all models loaded successfully.
        """
        if self._loaded:
            logger.info("Models already pre-loaded")
            return True
        
        with self._load_lock:
            # Double-check after acquiring lock
            if self._loaded:
                return True
            
            logger.info("Pre-loading all models for batch processing...")
            start_time = time.time()
            
            success = True
            
            # 1. Skip Whisper model preloading (using AssemblyAI for transcription instead)
            # The app uses AssemblyAI API for cloud-based transcription, so local Whisper is not needed
            logger.info("Skipping Whisper model pre-load (using AssemblyAI for transcription)")
            self.whisper_model = None
            
            # 2. Pre-load semantic model
            try:
                logger.info("Pre-loading semantic model...")
                from analyzer.rebuttal_detection import _get_semantic_model
                self.semantic_model, self.embeddings = _get_semantic_model()
                if self.semantic_model is None:
                    logger.warning("Semantic model pre-load failed")
                    success = False
                else:
                    logger.info("✓ Semantic model pre-loaded")
            except Exception as e:
                logger.error(f"Failed to pre-load semantic model: {e}")
                success = False
            
            # 3. Pre-load agent detector (uses AssemblyAI for transcription)
            try:
                logger.info("Pre-loading agent detector...")
                from lib.agent_only_detector import AgentOnlyRebuttalDetector
                self.agent_detector = AgentOnlyRebuttalDetector()
                if self.agent_detector is None:
                    logger.warning("Agent detector pre-load failed")
                    success = False
                else:
                    logger.info("✓ Agent detector pre-loaded")
            except Exception as e:
                logger.error(f"Failed to pre-load agent detector: {e}")
                success = False
            
            load_time = time.time() - start_time
            
            if success:
                self._loaded = True
                logger.info(f"All models pre-loaded successfully in {load_time:.2f}s")
            else:
                logger.warning(f"Some models failed to pre-load (took {load_time:.2f}s)")
            
            return success
    
    def is_loaded(self) -> bool:
        """Check if models are pre-loaded."""
        return self._loaded
    
    def get_whisper_model(self):
        """Get pre-loaded Whisper model."""
        if not self._loaded:
            logger.warning("Models not pre-loaded, loading on-demand...")
            self.preload_all_models()
        return self.whisper_model
    
    def get_semantic_model(self):
        """Get pre-loaded semantic model and embeddings."""
        if not self._loaded:
            logger.warning("Models not pre-loaded, loading on-demand...")
            self.preload_all_models()
        return self.semantic_model, self.embeddings
    
    def get_agent_detector(self):
        """Get pre-loaded agent detector."""
        if not self._loaded:
            logger.warning("Models not pre-loaded, loading on-demand...")
            self.preload_all_models()
        return self.agent_detector


# Global preloader instance
_preloader = None
_preloader_lock = threading.Lock()

def get_model_preloader() -> ModelPreloader:
    """Get or create the global model preloader instance."""
    global _preloader
    
    if _preloader is None:
        with _preloader_lock:
            if _preloader is None:
                _preloader = ModelPreloader()
    
    return _preloader

