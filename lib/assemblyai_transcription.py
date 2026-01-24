"""
AssemblyAI transcription service to replace local Whisper.
Provides cloud-based speech-to-text transcription with speaker diarization.
"""

import assemblyai as aai
from typing import Dict, Any, Optional, List
import logging
import time
import os
import sys
import asyncio
from pathlib import Path
import signal
import hashlib
import json
from datetime import datetime, timedelta
from functools import wraps

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Auto-initialize API key from database if possible
try:
    # Try to get user's API key from database
    #  Attempt to determine current user from session state or environment
    current_user = None
    try:
        import streamlit as st
        if hasattr(st, 'session_state') and 'username' in st.session_state:
            current_user = st.session_state['username']
    except:
        pass
    
    if not current_user:
        current_user = os.getenv('VOS_USER', 'Mohamed Abdo')  # Fallback
    
    from lib.dashboard_manager import user_manager
    user_api_key = user_manager.get_user_assemblyai_key(current_user)
    
    if user_api_key:
        aai.settings.api_key = user_api_key
        logger.debug(f"Auto-initialized AssemblyAI API key from database for user: {current_user}")
    else:
        # Fallback to environment variable
        env_key = os.getenv("ASSEMBLYAI_API_KEY")
        if env_key:
            aai.settings.api_key = env_key
            logger.debug("Using AssemblyAI API key from environment variable")
except Exception as e:
    logger.warning(f"Could not auto-initialize API key from database: {e}")
    # Try environment fallback
    try:
        env_key = os.getenv("ASSEMBLYAI_API_KEY")
        if env_key:
            aai.settings.api_key = env_key
    except:
        pass


def retry_api_call(max_retries=3, backoff_factor=2, retry_on_rate_limit=True):
    """
    Decorator to retry API calls with exponential backoff.
    
    Handles:
    - Rate limiting (429 errors)
    - Server errors (5xx)
    - Timeout errors
    - Connection errors
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Exponential backoff multiplier (default: 2)
        retry_on_rate_limit: Whether to retry on rate limit (default: True)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    
                    # Check if retryable
                    is_rate_limit = '429' in error_str or 'rate limit' in error_str
                    is_server_error = any(f'{code}' in error_str for code in range(500, 600))
                    is_timeout = 'timeout' in error_str or 'timed out' in error_str
                    is_connection_error = 'connection' in error_str and ('refused' in error_str or 'reset' in error_str)
                    
                    should_retry = (is_rate_limit and retry_on_rate_limit) or \
                                   is_server_error or is_timeout or is_connection_error
                    
                    if should_retry and attempt < max_retries - 1:
                        # Rate limit: wait longer
                        if is_rate_limit:
                            wait_time = 60  # Wait 1 minute for rate limit
                            logger.warning(f"⚠️ Rate limit hit, waiting {wait_time}s before retry...")
                        else:
                            wait_time = backoff_factor ** attempt
                        
                        logger.warning(
                            f"API call failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        if attempt == max_retries - 1:
                            logger.error(f"All {max_retries} retry attempts exhausted")
                        raise
            
            raise last_exception
        return wrapper
    return decorator


class TranscriptionCache:
    """File-based cache for transcription results to avoid duplicate API calls."""
    
    def __init__(self, cache_dir=".cache/transcriptions", ttl_days=30):
        """
        Initialize transcription cache.
        
        Args:
            cache_dir: Directory to store cache files (default: .cache/transcriptions)
            ttl_days: Time-to-live in days for cache entries (default: 30)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        self.enabled = os.getenv('TRANSCRIPTION_CACHE_ENABLED', 'true').lower() == 'true'
        
        if self.enabled:
            logger.debug(f"Transcription cache enabled: {self.cache_dir} (TTL: {ttl_days} days)")
        else:
            logger.debug("Transcription cache disabled")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get MD5 hash of audio file for cache key."""
        md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            logger.warning(f"Error hashing file {file_path}: {e}")
            return None
    
    def get(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached transcription if exists and not expired.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Cached transcription result or None
        """
        if not self.enabled:
            return None
        
        try:
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                return None
            
            cache_file = self.cache_dir / f"{file_hash}.json"
            
            if not cache_file.exists():
                return None
            
            # Check expiration
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age > timedelta(days=self.ttl_days):
                cache_file.unlink()  # Delete expired cache
                logger.debug(f"Cache expired for {Path(file_path).name}")
                return None
            
            # Load cached result
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            logger.debug(f"✅ Cache HIT for {Path(file_path).name} (age: {cache_age.days}d)")
            return cached_data
            
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, file_path: str, transcription_result: Dict[str, Any]):
        """
        Cache transcription result.
        
        Args:
            file_path: Path to audio file
            transcription_result: Transcription result to cache
        """
        if not self.enabled:
            return
        
        try:
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                return
            
            cache_file = self.cache_dir / f"{file_hash}.json"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(transcription_result, f, indent=2)
            
            logger.debug(f"💾 Cached transcription for {Path(file_path).name}")
            
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        if not self.enabled:
            return 0
        
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if cache_age > timedelta(days=self.ttl_days):
                    cache_file.unlink()
                    count += 1
            
            if count > 0:
                logger.info(f"Cleared {count} expired cache entries")
        except Exception as e:
            logger.warning(f"Error clearing expired cache: {e}")
        
        return count



class AssemblyAITranscriptionEngine:
    """Transcription engine using AssemblyAI API."""
    
    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None):
        """
        Initialize AssemblyAI transcription engine.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence over api_key)
        """
        # Use user's API key first, then fallback to provided key, then environment, then global settings
        effective_api_key = user_api_key or api_key or os.getenv("ASSEMBLYAI_API_KEY", "") or aai.settings.api_key
        
        if not effective_api_key:
            raise ValueError("AssemblyAI API key required. Set ASSEMBLYAI_API_KEY environment variable or provide user API key.")
        
        if effective_api_key == aai.settings.api_key:
            logger.debug("Using AssemblyAI API key from aai.settings fallback")
        else:
            aai.settings.api_key = effective_api_key
        
        self.transcriber = aai.Transcriber()
        
        # Initialize transcription cache
        cache_dir = os.getenv('TRANSCRIPTION_CACHE_DIR', '.cache/transcriptions')
        cache_ttl = int(os.getenv('TRANSCRIPTION_CACHE_TTL_DAYS', '30'))
        self.cache = TranscriptionCache(cache_dir=cache_dir, ttl_days=cache_ttl)
        
        logger.debug("AssemblyAI transcription engine initialized")
    
    def transcribe_file(
        self, 
        audio_file_path: str, 
        options: Optional[Dict[str, Any]] = None,
        enable_speaker_diarization: Optional[bool] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using AssemblyAI API with robust polling for timeout support.
        
        Uses polling loop to enforce timeout regardless of OS.
        """
        start_time = time.time()
        
        # Check cache first
        cached_result = self.cache.get(audio_file_path)
        if cached_result:
            return cached_result
        
        # Get timeout from config if not provided
        if timeout is None:
            try:
                # Use string-based access or default to avoid import errors
                timeout = int(os.environ.get("ASSEMBLYAI_TRANSCRIPTION_TIMEOUT", 300))
            except (ValueError, TypeError):
                timeout = 300

        # Container for results
        result_container = {"result": None, "exception": None}

        try:
            # Configure settings
            config_params = {
                "speaker_labels": enable_speaker_diarization if enable_speaker_diarization is not None else os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "true").lower() == "true",
                "language_detection": True,
                "punctuate": True,
                "format_text": True,
            }
            
            # Merge with user provided options
            if options:
                config_params.update(options)
                
            config = aai.TranscriptionConfig(**config_params)
            
            logger.debug(f"Transcribing file: {audio_file_path} (timeout: {timeout}s)")
            
            # Submit for transcription with local retry for connection issues
            transcript_submission = None
            submission_error = None
            for attempt in range(3):
                try:
                    transcript_submission = self.transcriber.submit(audio_file_path, config=config)
                    break
                except Exception as e:
                    submission_error = e
                    # Only retry connection/server errors, not logic/auth errors
                    error_str = str(e).lower()
                    if '401' in error_str or '403' in error_str:
                        raise # Auth error, don't retry
                    time.sleep(1)
            
            if not transcript_submission:
                raise Exception(f"Failed to submit to AssemblyAI after 3 attempts: {submission_error}")

            transcript_id = transcript_submission.id
            
            # Poll for completion
            poll_interval = 2.0
            elapsed = 0.0
            
            while elapsed < timeout:
                try:
                    transcript = aai.Transcript.get_by_id(transcript_id)
                except Exception as e:
                    # Check for 404 Not Found (fatal error, transcript ID invalid/deleted)
                    error_str = str(e)
                    if "404" in error_str and "Not Found" in error_str:
                        logger.error(f"Fatal error polling AssemblyAI: Transcript {transcript_id} not found (404). Aborting polling.")
                        raise e
                        
                    # Ignore other transient network errors during polling
                    logger.warning(f"Transient error polling AssemblyAI: {e}")
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                if transcript.status == aai.TranscriptStatus.completed:
                    processing_time_ms = int((time.time() - start_time) * 1000)
                    
                    # Extract results
                    result = {
                        "transcript": transcript.text or "",
                        "words": self._extract_words(transcript.words) if transcript.words else [],
                        "utterances": self._extract_utterances(transcript.utterances) if transcript.utterances else [],
                        "speakers": self._extract_speakers(transcript.utterances) if transcript.utterances else [],
                        "confidence": transcript.confidence if hasattr(transcript, 'confidence') else None,
                        "language_code": transcript.language_code if hasattr(transcript, 'language_code') else None,
                        "processing_time_ms": processing_time_ms,
                        "transcription_method": "assemblyai_api",
                        "transcription_status": "completed"
                    }
                    
                    # Cache successful result
                    self.cache.set(audio_file_path, result)
                    
                    result_container["result"] = result
                    break
                    
                elif transcript.status == aai.TranscriptStatus.error:
                     raise Exception(f"Transcription failed: {transcript.error}")
                
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            if result_container["result"] is None and elapsed >= timeout:
                raise TimeoutError(f"Transcription timed out after {timeout} seconds")

        except Exception as e:
            result_container["exception"] = e
        
        if result_container["exception"]:
            logger.error(f"AssemblyAI transcription error: {result_container['exception']}", exc_info=True)
            return {
                "transcript": "",
                "words": [],
                "utterances": [],
                "speakers": [],
                "confidence": None,
                "language_code": None,
                "processing_time_ms": processing_time_ms,
                "transcription_method": "assemblyai_api",
                "transcription_status": "failed",
                "transcription_error": str(result_container["exception"])
            }
        
        # Return result
        if result_container["result"]:
            return result_container["result"]
        else:
            # Fallback (shouldn't happen)
            processing_time_ms = int((time.time() - start_time) * 1000)
            return {
                "transcript": "",
                "words": [],
                "utterances": [],
                "speakers": [],
                "confidence": None,
                "language_code": None,
                "processing_time_ms": processing_time_ms,
                "transcription_method": "assemblyai_api",
                "transcription_status": "failed",
                "transcription_error": "Unknown error - no result returned"
            }
    
    def _extract_words(self, words: List) -> List[Dict[str, Any]]:
        """Extract word-level timestamps from transcript."""
        if not words:
            return []
        
        result = []
        for word in words:
            word_dict = {
                "text": word.text if hasattr(word, 'text') else str(word),
                "start": word.start if hasattr(word, 'start') else None,
                "end": word.end if hasattr(word, 'end') else None,
                "confidence": word.confidence if hasattr(word, 'confidence') else None,
            }
            if hasattr(word, 'speaker'):
                word_dict["speaker"] = word.speaker
            result.append(word_dict)
        
        return result
    
    def _extract_utterances(self, utterances: List) -> List[Dict[str, Any]]:
        """Extract speaker-separated utterances from transcript."""
        if not utterances:
            return []
        
        result = []
        for utterance in utterances:
            utterance_dict = {
                "text": utterance.text if hasattr(utterance, 'text') else str(utterance),
                "start": utterance.start if hasattr(utterance, 'start') else None,
                "end": utterance.end if hasattr(utterance, 'end') else None,
                "speaker": utterance.speaker if hasattr(utterance, 'speaker') else None,
                "confidence": utterance.confidence if hasattr(utterance, 'confidence') else None,
            }
            result.append(utterance_dict)
        
        return result
    
    def _extract_speakers(self, utterances: List) -> List[str]:
        """Extract unique speaker labels from utterances."""
        if not utterances:
            return []
        
        speakers = set()
        for utterance in utterances:
            if hasattr(utterance, 'speaker') and utterance.speaker:
                speakers.add(utterance.speaker)
        
        return sorted(list(speakers))
    
    def transcribe_audio_segment(self, audio_segment, temp_file_path: str) -> str:
        """
        Transcribe audio segment (for compatibility with existing code).
        
        Args:
            audio_segment: pydub AudioSegment (will be saved to temp file)
            temp_file_path: Path to save temporary audio file
            
        Returns:
            Transcript text
        """
        # Save segment to temp file
        audio_segment.export(temp_file_path, format="wav")
        
        # Transcribe
        result = self.transcribe_file(temp_file_path, enable_speaker_diarization=False)
        return result["transcript"]
    
    def transcribe_url(self, audio_url: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Transcribe audio from URL using AssemblyAI API.
        
        Args:
            audio_url: URL to audio file
            options: Optional transcription parameters
            
        Returns:
            Dict with transcript and metadata (same format as transcribe_file)
        """
        start_time = time.time()
        
        try:
            # Default configuration
            default_config = {
                "speaker_labels": os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "true").lower() == "true",
                "language_detection": True,
                "punctuate": True,
                "format_text": True,
            }
            
            # Merge with user-provided options
            config_dict = {**default_config, **(options or {})}
            config = aai.TranscriptionConfig(**config_dict)
            
            logger.debug(f"Transcribing audio from URL: {audio_url}")
            
            # Transcribe from URL
            transcript = self.transcriber.transcribe(audio_url, config=config)
            
            # Check for errors
            if transcript.error:
                logger.error(f"AssemblyAI transcription error: {transcript.error}")
                raise Exception(f"Transcription failed: {transcript.error}")
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract results (same format as transcribe_file)
            result = {
                "transcript": transcript.text or "",
                "words": self._extract_words(transcript.words) if transcript.words else [],
                "utterances": self._extract_utterances(transcript.utterances) if transcript.utterances else [],
                "speakers": self._extract_speakers(transcript.utterances) if transcript.utterances else [],
                "confidence": transcript.confidence if hasattr(transcript, 'confidence') else None,
                "language_code": transcript.language_code if hasattr(transcript, 'language_code') else None,
                "processing_time_ms": processing_time_ms,
                "transcription_method": "assemblyai_api",
                "status": transcript.status.value if hasattr(transcript, 'status') else "completed"
            }
            
            logger.debug(f"Transcription from URL completed in {processing_time_ms}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"AssemblyAI URL transcription error: {e}", exc_info=True)
            raise
    
    async def transcribe_file_async(
        self, 
        audio_file_path: str, 
        options: Optional[Dict[str, Any]] = None,
        enable_speaker_diarization: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Async wrapper for transcribe_file - runs transcription in thread pool to avoid blocking.
        
        Args:
            audio_file_path: Path to audio file (local file path)
            options: Optional transcription parameters
            enable_speaker_diarization: Enable speaker diarization (default: True)
            
        Returns:
            Dict with transcript and metadata (same format as transcribe_file)
        """
        # Run synchronous transcription in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.transcribe_file,
            audio_file_path,
            options,
            enable_speaker_diarization
        )
    
    async def transcribe_url_async(
        self, 
        audio_url: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Async wrapper for transcribe_url - runs transcription in thread pool to avoid blocking.
        
        Args:
            audio_url: URL to audio file
            options: Optional transcription parameters
            
        Returns:
            Dict with transcript and metadata (same format as transcribe_url)
        """
        # Run synchronous transcription in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.transcribe_url,
            audio_url,
            options
        )

