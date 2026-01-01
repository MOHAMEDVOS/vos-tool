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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class AssemblyAITranscriptionEngine:
    """Transcription engine using AssemblyAI API."""
    
    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None):
        """
        Initialize AssemblyAI transcription engine.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence over api_key)
        """
        # Use user's API key first, then fallback to provided key, then environment
        effective_api_key = user_api_key or api_key or os.getenv("ASSEMBLYAI_API_KEY", "")
        
        if not effective_api_key:
            raise ValueError("AssemblyAI API key required. Set ASSEMBLYAI_API_KEY environment variable or provide user API key.")
        
        aai.settings.api_key = effective_api_key
        self.transcriber = aai.Transcriber()
        logger.info("AssemblyAI transcription engine initialized")
    
    def transcribe_file(
        self, 
        audio_file_path: str, 
        options: Optional[Dict[str, Any]] = None,
        enable_speaker_diarization: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using AssemblyAI API.
        
        Args:
            audio_file_path: Path to audio file (local file path)
            options: Optional transcription parameters
            enable_speaker_diarization: Enable speaker diarization (default: True)
            
        Returns:
            Dict with transcript and metadata:
            - transcript: Full transcript text
            - words: Word-level timestamps (list of dicts)
            - utterances: Speaker-separated segments (list of dicts)
            - speakers: Speaker labels (list)
            - confidence: Overall confidence score (float)
            - language_code: Detected language code (str)
            - processing_time_ms: Processing time in milliseconds (int, optional)
        """
        start_time = time.time()
        
        try:
            # Default configuration - optimized for fast processing (30-60s files)
            # Diarization disabled by default for speed (can be enabled via env var or parameter)
            default_config = {
                "speaker_labels": enable_speaker_diarization if enable_speaker_diarization is not None 
                    else os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "false").lower() == "true",
                "language_detection": False,  # Disabled for speed (set language_code instead)
                "language_code": "en",  # Fixed to English for faster processing
                "punctuate": True,  # Keep punctuation for quality
                "format_text": True,  # Keep formatting for quality
            }
            
            # Merge with user-provided options
            config_dict = {**default_config, **(options or {})}
            config = aai.TranscriptionConfig(**config_dict)
            
            logger.info(f"Transcribing audio file: {Path(audio_file_path).name}")
            logger.debug(f"Configuration: speaker_labels={config_dict.get('speaker_labels')}, "
                        f"language_detection={config_dict.get('language_detection')}")
            
            # Transcribe the file
            transcript = self.transcriber.transcribe(audio_file_path, config=config)
            
            # Check for errors
            if transcript.error:
                logger.error(f"AssemblyAI transcription error: {transcript.error}")
                raise Exception(f"Transcription failed: {transcript.error}")
            
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
                "status": transcript.status.value if hasattr(transcript, 'status') else "completed"
            }
            
            logger.info(f"Transcription completed in {processing_time_ms}ms. "
                       f"Transcript length: {len(result['transcript'])} characters")
            
            return result
            
        except Exception as e:
            logger.error(f"AssemblyAI transcription error: {e}", exc_info=True)
            raise
    
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
            
            logger.info(f"Transcribing audio from URL: {audio_url}")
            
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
            
            logger.info(f"Transcription from URL completed in {processing_time_ms}ms")
            
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

