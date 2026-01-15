"""
Fast audio processor for quick transcription-only processing.
Skips heavy rebuttal detection for much faster processing times.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor
import tempfile

from audio_pipeline.detections import releasing_detection, late_hello_detection
from lib.agent_only_detector import AgentOnlyTranscriptionEngine

logger = logging.getLogger(__name__)


class FastAudioProcessor:
    """Optimized audio processor for fast transcription-only processing."""
    
    def __init__(self):
        """Initialize fast audio processor."""
        self.transcription_engine = None
        
    def _get_transcription_engine(self, user_api_key: Optional[str] = None):
        """Get or create transcription engine."""
        if self.transcription_engine is None:
            self.transcription_engine = AgentOnlyTranscriptionEngine(user_api_key=user_api_key)
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
    
    def process_single_file_fast(
        self, 
        file_path: Path, 
        additional_metadata: Optional[dict] = None,
        username: Optional[str] = None,
        user_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fast single-file processing - transcription + basic detections only.
        
        Args:
            file_path: Path to audio file
            additional_metadata: Additional metadata to include
            username: Username for job tracking
            user_api_key: User's AssemblyAI API key
            
        Returns:
            Processing result with transcript and basic detections
        """
        start_time = time.time()
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting FAST processing of file: {file_path}")
        
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
        agent_name = agent_name_raw.replace("([a-z])([A-Z])", r"\1 \2")  # Simple spacing
        
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
        
        # Fast parallel processing: transcription + basic detections
        try:
            result = self._process_fast_parallel(
                agent_audio, file_path, agent_name, phone_number, 
                timestamp, disposition, username, user_api_key, start_time
            )
            return result
            
        except Exception as e:
            logger.error(f"Fast processing failed for {file_path}: {e}", exc_info=True)
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
    
    def _process_fast_parallel(
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
        """Process with fast parallel execution."""
        
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
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            future_releasing = executor.submit(releasing_detection, agent_audio)
            future_late_hello = executor.submit(late_hello_detection, agent_audio, file_path.name)
            
            # Transcription task (if temp file available)
            future_transcription = None
            if temp_file:
                transcription_engine = self._get_transcription_engine(user_api_key)
                future_transcription = executor.submit(
                    transcription_engine.transcribe_agent_only, 
                    temp_file
                )
            
            # Collect results
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
            
            # Transcription (slower, but we have timeout)
            transcript = ""
            transcription_status = "failed"
            transcription_error = None
            
            if future_transcription:
                try:
                    transcription_result = future_transcription.result(timeout=120)  # 2 minute timeout
                    transcript = transcription_result.get("transcript", "")
                    transcription_status = transcription_result.get("transcription_status", "completed")
                    transcription_error = transcription_result.get("transcription_error")
                    
                    logger.info(f"Transcription completed: {len(transcript)} chars, status: {transcription_status}")
                    
                except Exception as e:
                    logger.error(f"Transcription failed: {e}")
                    transcription_status = "timeout" if "timeout" in str(e).lower() else "failed"
                    transcription_error = str(e)
            
            result['transcript'] = transcript
            result['transcription_status'] = transcription_status
            result['transcription_error'] = transcription_error
            
            # Skip rebuttal detection for speed (can be added later if needed)
            result['rebuttal_detection'] = {
                'result': 'Skipped',
                'transcript': transcript,
                'reason': 'fast_processing_mode'
            }
            
            # Clean up temp file
            if temp_file and Path(temp_file).exists():
                try:
                    Path(temp_file).unlink()
                except Exception:
                    pass
            
            return result
    
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
