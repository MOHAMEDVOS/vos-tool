"""
Semantic audio processor - AssemblyAI + FAST semantic rebuttal detection.
Optimized semantic analysis with pre-loaded models and efficient processing.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, List
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading

from audio_pipeline.detections import releasing_detection, late_hello_detection
from lib.assemblyai_transcription import AssemblyAITranscriptionEngine

logger = logging.getLogger(__name__)


class SemanticAudioProcessor:
    """Audio processor with optimized semantic rebuttal detection."""
    
    def __init__(self):
        """Initialize semantic audio processor with pre-loaded models."""
        self.transcription_engine = None
        self.semantic_engine = None
        self._model_lock = threading.Lock()
        self._models_loaded = False
        
    def _ensure_models_loaded(self):
        """Lazy-load semantic models only when needed."""
        if self._models_loaded:
            return
            
        with self._model_lock:
            if self._models_loaded:
                return
                
            logger.info("Loading semantic models for rebuttal detection...")
            start_time = time.time()
            
            try:
                # Import and initialize semantic engine
                from analyzer.rebuttal_detection import SemanticDetectionEngine
                from lib.keyword_repo import KeywordRepository
                
                keyword_repo = KeywordRepository()
                self.semantic_engine = SemanticDetectionEngine(keyword_repo)
                
                # Pre-warm the models with a dummy transcript
                dummy_transcript = "Hello, how are you today?"
                self.semantic_engine.detect_rebuttals(dummy_transcript)
                
                self._models_loaded = True
                load_time = time.time() - start_time
                logger.info(f"Semantic models loaded in {load_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Failed to load semantic models: {e}")
                # Fall back to keyword-only mode
                self.semantic_engine = None
                self._models_loaded = True
    
    def _get_transcription_engine(self, user_api_key: Optional[str] = None):
        """Get or create AssemblyAI transcription engine."""
        if self.transcription_engine is None:
            self.transcription_engine = AssemblyAITranscriptionEngine(user_api_key=user_api_key)
        return self.transcription_engine
    
    def _check_audio_duration(self, audio: AudioSegment, min_seconds: int = 3) -> bool:
        """Check if audio meets minimum duration requirement."""
        duration_ms = len(audio)
        duration_seconds = duration_ms / 1000.0
        return duration_seconds >= min_seconds
    
    def _extract_agent_audio(self, audio: AudioSegment) -> AudioSegment:
        """Extract agent channel from stereo audio."""
        if audio.channels == 1:
            return audio
        
        if audio.channels == 2:
            return audio.split_to_mono()[0]  # Left channel (agent)
        
        # Fallback: convert to mono
        return audio.set_channels(1)
    
    def process_single_file_semantic(
        self, 
        file_path: Path, 
        additional_metadata: Optional[dict] = None,
        include_debug: bool = False,
        username: Optional[str] = None,
        user_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process single file with semantic rebuttal detection.
        AssemblyAI transcription + optimized semantic analysis.
        """
        start_time = time.time()
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting SEMANTIC processing of file: {file_path}")
        
        # Extract metadata from filename
        stem = file_path.stem
        parts = stem.split(" _ ")
        
        if len(parts) == 4:
            agent_name_raw, timestamp, phone_number, disposition = parts
        elif len(parts) == 2:
            agent_name_raw, phone_number = parts
            timestamp = ""
            disposition = ""
        else:
            agent_name_raw = stem
            phone_number = ""
            timestamp = ""
            disposition = ""
        
        agent_name_raw = agent_name_raw.replace("-", "").replace(".", "")
        agent_name = agent_name_raw.replace("([a-z])([A-Z])", r"\1 \2")
        
        # Validate audio file
        if not self._is_valid_audio_file(file_path):
            logger.warning(f"Invalid audio file: {file_path}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Invalid audio file: {file_path}",
                'processing_time': time.time() - start_time,
                'classification_success': False,
                'transcription_status': 'failed',
                'transcription_error': 'invalid_file'
            }
        
        # Load audio
        try:
            audio = self.load_audio_file(file_path)
        except Exception as e:
            logger.error(f"Failed to load audio {file_path}: {e}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Failed to load audio: {e}",
                'processing_time': time.time() - start_time,
                'classification_success': False,
                'transcription_status': 'failed',
                'transcription_error': 'load_failed'
            }
        
        # Extract agent audio
        agent_audio = self._extract_agent_audio(audio)
        
        if len(agent_audio) < 1000:  # Less than 1 second
            logger.warning(f"Audio too short: {len(agent_audio)}ms for {file_path}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Audio too short: {len(agent_audio)}ms",
                'processing_time': time.time() - start_time,
                'classification_success': False,
                'transcription_status': 'failed',
                'transcription_error': 'too_short'
            }
        
        # Semantic processing with parallel execution
        try:
            result = self._process_semantic_parallel(
                agent_audio, file_path, agent_name, phone_number, 
                timestamp, disposition, username, user_api_key, start_time
            )
            return result
            
        except Exception as e:
            logger.error(f"Semantic processing failed for {file_path}: {e}", exc_info=True)
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': str(e),
                'processing_time': time.time() - start_time,
                'classification_success': False,
                'transcription_status': 'failed',
                'transcription_error': str(e)
            }
    
    def _process_semantic_parallel(
        self, 
        agent_audio: AudioSegment, 
        file_path: Path,
        agent_name: str,
        phone_number: str,
        timestamp: str,
        disposition: str,
        username: Optional[str],
        user_api_key: Optional[str],
        start_time: float
    ) -> Dict[str, Any]:
        """Process with semantic analysis in parallel."""
        
        # Create temp file for transcription
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                agent_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                temp_file = tmp.name
        except Exception as e:
            logger.error(f"Failed to create temp file: {e}")
            temp_file = None
        
        # Parallel execution with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            future_releasing = executor.submit(releasing_detection, agent_audio)
            future_late_hello = executor.submit(late_hello_detection, agent_audio, file_path.name)
            
            # AssemblyAI transcription task
            future_transcription = None
            if temp_file:
                transcription_engine = self._get_transcription_engine(user_api_key)
                future_transcription = executor.submit(
                    transcription_engine.transcribe_file,
                    temp_file,
                    enable_speaker_diarization=False,
                    timeout=180  # 3 minute timeout
                )
            
            # Collect basic results first (fast)
            result = {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'processing_time': time.time() - start_time,
                'classification_success': True,
                'transcription_status': 'completed',
                'transcription_error': None
            }
            
            # Basic detections (fast)
            try:
                result['releasing_detection'] = future_releasing.result(timeout=5)
            except Exception as e:
                logger.error(f"Releasing detection failed: {e}")
                result['releasing_detection'] = 'Error'
            
            try:
                result['late_hello_detection'] = future_late_hello.result(timeout=5)
            except Exception as e:
                logger.error(f"Late hello detection failed: {e}")
                result['late_hello_detection'] = 'Error'
            
            # AssemblyAI transcription
            transcript = ""
            transcription_status = "failed"
            transcription_error = None
            
            if future_transcription:
                try:
                    transcription_result = future_transcription.result(timeout=180)
                    transcript = transcription_result.get("transcript", "")
                    transcription_status = transcription_result.get("transcription_status", "completed")
                    transcription_error = transcription_result.get("transcription_error")
                    
                    logger.info(f"AssemblyAI transcription completed: {len(transcript)} chars")
                    
                except Exception as e:
                    logger.error(f"AssemblyAI transcription failed: {e}")
                    transcription_status = "timeout" if "timeout" in str(e).lower() else "failed"
                    transcription_error = str(e)
            
            result['transcription'] = transcript
            result['transcription_status'] = transcription_status
            result['transcription_error'] = transcription_error
            
            # Semantic rebuttal detection (if transcript available)
            if transcript and self.semantic_engine is not None:
                try:
                    # Run semantic analysis in thread pool
                    future_semantic = executor.submit(
                        self._fast_semantic_detection,
                        transcript
                    )
                    
                    semantic_result = future_semantic.result(timeout=30)  # 30 second timeout for semantic
                    # Ensure transcript is always included in result
                    if 'transcript' not in semantic_result:
                        semantic_result['transcript'] = transcript
                    result['rebuttal_detection'] = semantic_result
                    
                except Exception as e:
                    logger.error(f"Semantic detection failed: {e}")
                    result['rebuttal_detection'] = {
                        'result': 'Error',
                        'transcript': transcript,
                        'method': 'semantic',
                        'error': str(e)
                    }
            else:
                # Fallback to keyword-only if no semantic engine
                fallback_result = self._fast_keyword_detection(transcript)
                # Ensure transcript is included in fallback result
                if 'transcript' not in fallback_result:
                    fallback_result['transcript'] = transcript
                result['rebuttal_detection'] = fallback_result
            
            # Clean up temp file
            if temp_file and Path(temp_file).exists():
                try:
                    Path(temp_file).unlink()
                except Exception:
                    pass
            
            return result
    
    def _fast_semantic_detection(self, transcript: str) -> Dict[str, Any]:
        """Fast semantic detection using pre-loaded models."""
        if not transcript or not self.semantic_engine:
            return self._fast_keyword_detection(transcript)
        
        try:
            # Use pre-loaded semantic engine
            matches = self.semantic_engine.detect_rebuttals(transcript)
            
            if matches and len(matches) > 0:
                best_match = matches[0]  # Highest confidence
                return {
                    'result': 'Yes',
                    'transcript': transcript,
                    'method': 'semantic',
                    'confidence': best_match.get('confidence', 0.0),
                    'matched_phrase': best_match.get('phrase', ''),
                    'category': best_match.get('category', ''),
                    'all_matches': matches[:3]  # Top 3 matches
                }
            else:
                return {
                    'result': 'No',
                    'transcript': transcript,
                    'method': 'semantic',
                    'confidence': 0.0,
                    'matches': []
                }
                
        except Exception as e:
            logger.error(f"Semantic detection error: {e}")
            return self._fast_keyword_detection(transcript)
    
    def _fast_keyword_detection(self, transcript: str) -> Dict[str, Any]:
        """Fast keyword detection fallback."""
        if not transcript:
            return {'result': 'No', 'transcript': '', 'method': 'keyword'}
        
        # Simple rebuttal indicators
        rebuttal_indicators = [
            "can't afford", "too expensive", "don't have", "out of stock",
            "not available", "call back", "think about it", "let me",
            "competitor", "cheaper elsewhere", "not interested"
        ]
        
        transcript_lower = transcript.lower()
        for indicator in rebuttal_indicators:
            if indicator in transcript_lower:
                return {
                    'result': 'Yes',
                    'transcript': transcript,
                    'method': 'keyword',
                    'matched_phrase': indicator,
                    'confidence': 0.7
                }
        
        return {
            'result': 'No', 
            'transcript': transcript,
            'method': 'keyword',
            'confidence': 0.0
        }
    
    def _is_valid_audio_file(self, file_path: Path) -> bool:
        """Check if file is a valid audio file."""
        valid_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
        return file_path.suffix.lower() in valid_extensions
    
    def load_audio_file(self, file_path: Path) -> AudioSegment:
        """Load audio file with error handling."""
        try:
            return AudioSegment.from_file(str(file_path))
        except Exception as e:
            raise Exception(f"Failed to load audio file {file_path}: {e}")
