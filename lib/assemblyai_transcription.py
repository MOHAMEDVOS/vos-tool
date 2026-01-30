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
    """
    Cache for transcription results to avoid duplicate API calls.
    Uses PostgreSQL database if available, falls back to file system.
    """
    
    def __init__(self, cache_dir=".cache/transcriptions", ttl_days=30):
        """
        Initialize transcription cache.
        
        Args:
            cache_dir: Directory to store cache files (default: .cache/transcriptions)
            ttl_days: Time-to-live in days for cache entries (default: 30)
        """
        self.enabled = os.getenv('TRANSCRIPTION_CACHE_ENABLED', 'true').lower() == 'true'
        
        # Try to initialize DB cache manager
        self.db_manager = None
        try:
            from lib.transcription_caching import TranscriptionCacheManager
            self.db_manager = TranscriptionCacheManager()
            if self.db_manager.enabled:
                logger.debug("✅ Using Database Transcription Cache")
            else:
                self.db_manager = None
        except Exception as e:
            logger.debug(f"Database cache not available: {e}")
            self.db_manager = None
            
        # Fallback to file cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        
        if self.enabled:
            cache_type = "Database + File" if self.db_manager else "File-only"
            logger.debug(f"Transcription cache enabled ({cache_type}): {self.cache_dir} (TTL: {ttl_days} days)")
        else:
            logger.debug("Transcription cache disabled")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get MD5 hash of audio file for cache key."""
        # Use DB key generator if available for consistency
        if self.db_manager:
            return self.db_manager.calculate_file_hash(file_path)
            
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
        Get cached transcription if exists.
        Checks Database first, then File System.
        """
        if not self.enabled:
            return None
        
        try:
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                return None
            
            # Level 1: Check Database
            if self.db_manager:
                cached = self.db_manager.get_cached_transcript(file_hash)
                if cached and cached.get('raw_response'):
                    logger.debug(f"✅ DB Cache HIT for {Path(file_path).name}")
                    return cached['raw_response']
            
            # Level 2: Check File System (Fallback)
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
            
            logger.debug(f"✅ File Cache HIT for {Path(file_path).name} (age: {cache_age.days}d)")
            
            # Backfill DB if missing
            if self.db_manager and cached_data:
                try:
                    file_size = os.path.getsize(file_path)
                    transcript_text = cached_data.get('transcript', '')
                    self.db_manager.cache_transcript(file_hash, file_size, transcript_text, cached_data)
                except:
                    pass
                    
            return cached_data
            
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, file_path: str, transcription_result: Dict[str, Any]):
        """
        Cache transcription result to Database and File System.
        """
        if not self.enabled:
            return
        
        try:
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                return
            
            # Write to Database
            if self.db_manager:
                try:
                    file_size = os.path.getsize(file_path)
                    transcript_text = transcription_result.get('transcript', '')
                    self.db_manager.cache_transcript(file_hash, file_size, transcript_text, transcription_result)
                except Exception as e:
                    logger.warning(f"Failed to write to DB cache: {e}")
            
            # Write to File System
            cache_file = self.cache_dir / f"{file_hash}.json"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(transcription_result, f, indent=2)
            
            logger.debug(f"💾 Cached transcription for {Path(file_path).name}")
            
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries from file system.
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
        
        # CRITICAL FIX: Store API key as instance variable instead of using global aai.settings
        # This prevents race conditions when multiple users process files simultaneously
        self.api_key = effective_api_key
        
        # Initialize transcription cache
        cache_dir = os.getenv('TRANSCRIPTION_CACHE_DIR', '.cache/transcriptions')
        cache_ttl = int(os.getenv('TRANSCRIPTION_CACHE_TTL_DAYS', '30'))
        self.cache = TranscriptionCache(cache_dir=cache_dir, ttl_days=cache_ttl)
        
        logger.debug("AssemblyAI transcription engine initialized with isolated API key")
    
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
            # CRITICAL FIX: Create a new Transcriber with this instance's API key
            # This ensures complete isolation between concurrent users
            # We temporarily set the global key, create the transcriber, then restore
            original_global_key = aai.settings.api_key
            try:
                aai.settings.api_key = self.api_key
                transcriber = aai.Transcriber()
            finally:
                # Restore original global key immediately
                aai.settings.api_key = original_global_key
            
            # Configure settings
            config_params = {
                "speaker_labels": enable_speaker_diarization if enable_speaker_diarization is not None else True,  # Enable by default for dual-channel
                "multichannel": True,  # Enable multichannel for stereo audio (left=agent, right=owner)
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
                    # Use the instance-specific transcriber
                    transcript_submission = transcriber.submit(audio_file_path, config=config)
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
            
            # Poll for completion using instance-specific API key
            poll_interval = 2.0
            elapsed = 0.0
            
            while elapsed < timeout:
                try:
                    # CRITICAL FIX: Set instance API key before polling
                    # This ensures we use the correct API key for this specific user
                    original_global_key = aai.settings.api_key
                    try:
                        aai.settings.api_key = self.api_key
                        transcript = aai.Transcript.get_by_id(transcript_id)
                    finally:
                        # Restore original global key immediately
                        aai.settings.api_key = original_global_key
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
                    
                    # Extract utterances first
                    utterances = self._extract_utterances(transcript.utterances) if transcript.utterances else []
                    
                    # Extract results with dual-channel support
                    result = {
                        "transcript": transcript.text or "",  # Full transcript (all speakers)
                        "words": self._extract_words(transcript.words) if transcript.words else [],
                        "utterances": utterances,
                        "speakers": self._extract_speakers(transcript.utterances) if transcript.utterances else [],
                        "confidence": transcript.confidence if hasattr(transcript, 'confidence') else None,
                        "language_code": transcript.language_code if hasattr(transcript, 'language_code') else None,
                        "processing_time_ms": processing_time_ms,
                        "transcription_method": "assemblyai_api",
                        "transcription_status": "completed",
                        # NEW: Dual-channel fields
                        "dialogue": self.format_as_dialogue(utterances),  # Formatted conversation
                        "agent_transcript": self.extract_speaker_transcript(utterances, "A"),  # Agent only
                        "owner_transcript": self.extract_speaker_transcript(utterances, "B")   # Owner only
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
                "channel": utterance.channel if hasattr(utterance, 'channel') else None,  # Multichannel support
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
    
    def format_as_dialogue(self, utterances: List[Dict[str, Any]]) -> str:
        """
        Format speaker-separated utterances as chronological dialogue.
        Supports both channel-based (multichannel) and speaker-based (diarization) formatting.
        
        Args:
            utterances: List of utterance dicts with 'speaker', 'channel', 'text', 'start' fields
            
        Returns:
            Formatted dialogue string like:
            Agent: Hello there
            Owner: Who is this?
            Agent: This is Mark calling about your property
        """
        if not utterances:
            return ""
        
        # Sort utterances chronologically by start time
        sorted_utterances = sorted(utterances, key=lambda u: u.get('start', 0))
        
        # Determine if we're using multichannel (channel-based) or diarization (speaker-based)
        has_channels = any(u.get('channel') is not None for u in sorted_utterances)
        
        # Format as dialogue
        dialogue_lines = []
        for utterance in sorted_utterances:
            text = utterance.get('text', '').strip()
            if not text:
                continue
            
            # Determine speaker label
            if has_channels:
                # Multichannel mode: Use channel numbers to determine speaker
                channel = utterance.get('channel')
                speaker = "Agent" if channel == 0 else "Owner" if channel == 1 else f"Channel {channel}"
            else:
                # Diarization mode: Use speaker labels
                speaker = utterance.get('speaker', 'Unknown')
            
            dialogue_lines.append(f"{speaker}: {text}")
        
        return "\n".join(dialogue_lines)
    
    def extract_speaker_transcript(self, utterances: List[Dict[str, Any]], speaker_label: str) -> str:
        """
        Extract transcript for a specific speaker only.
        Supports both channel-based (multichannel) and speaker-based (diarization) extraction.
        
        Args:
            utterances: List of utterance dicts with 'speaker', 'channel', and 'text' fields
            speaker_label: Speaker label to extract:
                          - For multichannel: "A" = channel 0 (left/agent), "B" = channel 1 (right/owner)
                          - For diarization: "A", "B", "Speaker A", "Speaker B", etc.
            
        Returns:
            Concatenated transcript for the specified speaker
        """
        if not utterances:
            return ""
        
        # Determine if we're using multichannel (channel-based) or diarization (speaker-based)
        has_channels = any(u.get('channel') is not None for u in utterances)
        
        speaker_texts = []
        
        if has_channels:
            # Multichannel mode: Use channel numbers
            # Channel 0 (left) = Agent (A), Channel 1 (right) = Owner (B)
            target_channel = 0 if speaker_label == "A" else 1
            
            for utterance in utterances:
                if utterance.get('channel') == target_channel:
                    text = utterance.get('text', '').strip()
                    if text:
                        speaker_texts.append(text)
        else:
            # Diarization mode: Use speaker labels
            for utterance in utterances:
                if utterance.get('speaker') == speaker_label:
                    text = utterance.get('text', '').strip()
                    if text:
                        speaker_texts.append(text)
        
        return " ".join(speaker_texts)
    
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
            # CRITICAL FIX: Create a new Transcriber with this instance's API key
            # This ensures complete isolation between concurrent users
            original_global_key = aai.settings.api_key
            try:
                aai.settings.api_key = self.api_key
                transcriber = aai.Transcriber()
            finally:
                # Restore original global key immediately
                aai.settings.api_key = original_global_key
            
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
            
            # Transcribe from URL using instance-specific transcriber
            transcript = transcriber.transcribe(audio_url, config=config)
            
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

