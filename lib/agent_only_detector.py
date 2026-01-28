#!/usr/bin/env python3
"""
Agent-Only Transcription System - AssemblyAI Only
Uses AssemblyAI API for cloud-based transcription with speaker diarization.
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, Any, Optional, List

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pydub import AudioSegment

# Import existing components
from analyzer.rebuttal_detection import KeywordRepository, SemanticDetectionEngine, OutputFormatter, TranscriptionEngine
from lib.egyptian_accent_correction import EgyptianAccentCorrection

# logger level is managed by lib/logging_config.py
logger = logging.getLogger(__name__)

class LocalTranscriptionEngine:
    """
    AssemblyAI-based transcription engine.
    Uses AssemblyAI API exclusively for cloud-based speech-to-text transcription.
    """

    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None):
        """
        Initialize transcription engine with AssemblyAI API.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence)
        
        Raises:
            ValueError: If API key is not available.
        """
        try:
            from lib.assemblyai_transcription import AssemblyAITranscriptionEngine
            self.assemblyai_engine = AssemblyAITranscriptionEngine(api_key=api_key, user_api_key=user_api_key)
            logger.debug("LocalTranscriptionEngine initialized with AssemblyAI API")
        except ValueError as e:
            logger.error(f"AssemblyAI API key required: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AssemblyAI transcription engine: {e}")
            raise

    def transcribe_audio(self, audio_segment: AudioSegment) -> str:
        """
        Transcribe audio using AssemblyAI API.
        
        Args:
            audio_segment: pydub AudioSegment to transcribe
            
        Returns:
            Transcript text
        """
        logger.debug(f"Transcribing {len(audio_segment)}ms audio with AssemblyAI API")
        
        try:
            import tempfile
            import os
            
            # Export audio segment to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_segment.export(tmp.name, format="wav")
                tmp_path = tmp.name
            
            result = self.assemblyai_engine.transcribe_file(
                tmp_path,
                enable_speaker_diarization=False  # Disable for single-segment transcription
            )
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            transcript = result.get("transcript", "").strip()
            if transcript:
                logger.debug(f"AssemblyAI transcription successful: {len(transcript)} characters")
                return transcript
            else:
                logger.warning("AssemblyAI returned empty transcript")
                return ""
                
        except Exception as e:
            logger.error(f"AssemblyAI transcription failed: {e}")
            raise
        """Remove consecutive repetitions of the same phrase."""
        if not text:
            return text

        words = text.split()
        if len(words) < min_repetition_length * 2:
            return text

        result = []
        i = 0

        while i < len(words):
            # Check for repetition pattern
            found_repetition = False

            # Look for patterns of length 2-5 words that repeat consecutively
            for pattern_len in range(min_repetition_length, min(6, len(words) - i + 1)):
                if i + pattern_len * 2 <= len(words):
                    pattern = words[i:i + pattern_len]
                    next_pattern = words[i + pattern_len:i + pattern_len * 2]

                    if pattern == next_pattern:
                        # Found repetition, skip all occurrences of this pattern
                        repetitions = 2
                        while (i + pattern_len * (repetitions + 1) <= len(words) and
                               words[i + pattern_len * repetitions:i + pattern_len * (repetitions + 1)] == pattern):
                            repetitions += 1

                        # Keep only one instance of the pattern
                        result.extend(pattern)
                        i += pattern_len * repetitions
                        found_repetition = True
                        break

            if not found_repetition:
                result.append(words[i])
                i += 1

        return " ".join(result)

class AgentOnlyTranscriptionEngine:
    """Transcribes only the agent channel using AssemblyAI with speaker diarization."""

    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None):
        """
        Initialize agent-only transcription engine with AssemblyAI.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence)
        """
        self.local_engine = LocalTranscriptionEngine(api_key, user_api_key)
        logger.debug("Agent-Only Transcription Engine initialized with AssemblyAI")

    def extract_agent_channel(self, audio_segment: AudioSegment) -> AudioSegment:
        """Extract agent channel from stereo audio (left channel typically)."""
        logger.debug("Extracting agent channel from audio")

        # If mono, assume it's already the agent channel
        if audio_segment.channels == 1:
            logger.debug("Audio is already mono (agent channel)")
            return audio_segment

        # For stereo, take left channel (typically agent)
        if audio_segment.channels == 2:
            agent_channel = audio_segment.split_to_mono()[0]  # Left channel
            logger.debug("Extracted left channel as agent channel")
            return agent_channel

        # Fallback: convert to mono
        logger.warning(f"Unexpected number of channels: {audio_segment.channels}, converting to mono")
        return audio_segment.set_channels(1)

    def transcribe_agent_only(self, audio_file_path: str, timeout: Optional[int] = None, audio_duration_seconds: Optional[float] = None, original_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe only the agent channel using AssemblyAI with speaker diarization.

        Args:
            audio_file_path: Path to the audio file (may be temp file)
            timeout: Transcription timeout in seconds (optional, will be calculated if None)
            audio_duration_seconds: Duration of audio file for progressive timeout calculation
            original_file_path: Original file path for cache lookup (if different from audio_file_path)

        Returns:
            Dict with transcript and metadata including transcription_status
        """
        start_time = time.time()

        try:
            # Use original path for cache lookup if provided, otherwise use audio_file_path
            cache_key_path = original_file_path if original_file_path else audio_file_path
            logger.debug(f"Starting agent-only transcription with AssemblyAI: {audio_file_path} (cache key: {cache_key_path})")

            # Calculate progressive timeout based on audio duration if not provided
            if timeout is None:
                try:
                    from lib.timeout_utils import calculate_transcription_timeout
                    timeout = calculate_transcription_timeout(audio_duration_seconds)
                    logger.debug(f"Calculated transcription timeout: {timeout}s (file duration: {audio_duration_seconds:.1f}s)" if audio_duration_seconds else f"Using default timeout: {timeout}s")
                except ImportError:
                    # Fallback to config or default
                    try:
                        from backend.core.config import settings
                        timeout = settings.ASSEMBLYAI_TRANSCRIPTION_TIMEOUT
                    except ImportError:
                        timeout = 300  # 5 minutes default

            # Check cache first using original file path
            cached_result = self.local_engine.assemblyai_engine.cache.get(cache_key_path)
            if cached_result:
                logger.debug(f"✅ CACHE HIT for transcription: {cache_key_path}")
                processing_time = int((time.time() - start_time) * 1000)
                return {
                    "transcript": cached_result.get("transcript", ""),
                    "full_transcript": cached_result.get("transcript", ""),
                    "speakers": cached_result.get("speakers", []),
                    "utterances": cached_result.get("utterances", []),
                    "processing_time_ms": processing_time,
                    "transcription_method": "assemblyai_api_cached",
                    "channels_processed": 1,
                    "transcription_status": "completed",
                    "transcription_error": None,
                    "error": ""
                }

            # Transcribe with speaker diarization enabled for dual-channel support
            # This provides full conversation context while extracting agent-only text for detection
            result = self.local_engine.assemblyai_engine.transcribe_file(
                audio_file_path,
                enable_speaker_diarization=True,  # ENABLED for dual-channel context
                timeout=timeout,
                options={
                    "language_detection": False,
                    "language_code": "en"
                }
            )
            
            # Extract agent transcript from speaker-separated utterances
            # Speaker A is typically the agent (first speaker in most call recordings)
            agent_transcript = result.get("agent_transcript", "")
            
            # Fallback: if no agent_transcript (old cache or mono audio), use full transcript
            if not agent_transcript:
                agent_transcript = result.get("transcript", "")
            
            # Store full dialogue for LLM context
            dialogue = result.get("dialogue", "")
            speakers = result.get("speakers", [])
            utterances = result.get("utterances", [])

            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Cache the result using original file path as key
            if agent_transcript and cache_key_path:
                try:
                    self.local_engine.assemblyai_engine.cache.set(cache_key_path, result)
                    logger.debug(f"💾 Cached transcription for: {cache_key_path}")
                except Exception as cache_error:
                    logger.warning(f"Failed to cache transcription: {cache_error}")
            
            return {
                "transcript": agent_transcript,  # Agent-only transcript for detection
                "full_transcript": result.get("transcript", ""),  # Full transcript (all speakers)
                "dialogue": dialogue,  # Formatted conversation for LLM context
                "owner_transcript": result.get("owner_transcript", ""),  # Owner-only transcript
                "speakers": speakers,
                "utterances": utterances,
                "processing_time_ms": processing_time,
                "transcription_method": "assemblyai_api",
                "channels_processed": 2,  # Dual-channel with speaker diarization
                "transcription_status": result.get("transcription_status", "unknown"),
                "transcription_error": result.get("transcription_error"),
                "error": "" if agent_transcript else "transcription_failed"
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Agent-only transcription failed: {e}")
            return {
                "transcript": "",
                "full_transcript": "",
                "speakers": [],
                "utterances": [],
                "processing_time_ms": processing_time,
                "transcription_method": "assemblyai_api",
                "channels_processed": 1,
                "transcription_status": "failed",
                "transcription_error": str(e),
                "error": str(e)
            }
    
    async def transcribe_agent_only_async(self, audio_file_path: str, audio_duration_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Async version of transcribe_agent_only - runs transcription in thread pool to avoid blocking.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Dict with transcript and metadata (same format as transcribe_agent_only)
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe_agent_only(audio_file_path, audio_duration_seconds=audio_duration_seconds)
        )

    def _validate_audio_quality(self, audio_segment: AudioSegment) -> Dict[str, Any]:
        """Validate audio quality for agent channel."""
        duration_ms = len(audio_segment)

        # Skip extremely short clips
        if duration_ms < 1000:
            return {"audio_quality_ok": False, "skipped_reason": "too_short"}

        # Check for very quiet audio
        import numpy as np
        audio_array = np.array(audio_segment.get_array_of_samples())
        max_amplitude = np.max(np.abs(audio_array))

        if max_amplitude < 500:  # Very quiet threshold
            return {"audio_quality_ok": False, "skipped_reason": "too_quiet"}

        # Calculate basic quality score
        mean_amplitude = np.mean(np.abs(audio_array))
        quality_score = min(1.0, max_amplitude / 32767.0) if mean_amplitude > 0 else 0.0

        return {
            "audio_quality_ok": True,
            "audio_quality_score": quality_score
        }

class AgentOnlyRebuttalDetector:
    """Complete rebuttal detection system using AssemblyAI API for agent channel transcription."""

    # Class-level cache for heavy components (P0 FIX)
    _shared_keyword_repo = None
    _shared_semantic_engine = None
    _shared_formatter = None
    _shared_corrector = None
    _shared_lock = threading.Lock()

    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None, skip_database: bool = False):
        """
        Initialize agent-only rebuttal detector with AssemblyAI.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence)
            skip_database: If True, skip database queries for learned phrases (faster for batch processing)
        """
        self.transcription_engine = AgentOnlyTranscriptionEngine(api_key, user_api_key)
        
        # Initialize shared components with lock (P0 FIX)
        with self._shared_lock:
            if AgentOnlyRebuttalDetector._shared_keyword_repo is None:
                AgentOnlyRebuttalDetector._shared_keyword_repo = KeywordRepository(skip_database=False) # Always load repo once
                AgentOnlyRebuttalDetector._shared_semantic_engine = SemanticDetectionEngine(AgentOnlyRebuttalDetector._shared_keyword_repo)
                AgentOnlyRebuttalDetector._shared_formatter = OutputFormatter()
                AgentOnlyRebuttalDetector._shared_corrector = EgyptianAccentCorrection()
        
        self.keyword_repo = AgentOnlyRebuttalDetector._shared_keyword_repo
        self.semantic_engine = AgentOnlyRebuttalDetector._shared_semantic_engine
        self.formatter = AgentOnlyRebuttalDetector._shared_formatter
        self.egyptian_corrector = AgentOnlyRebuttalDetector._shared_corrector
        
        logger.debug("Agent-Only Rebuttal Detector initialized (reusing shared engines)")

    def detect_rebuttals_in_audio(self, audio_file_path: str, original_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete pipeline: Agent-only transcription with AssemblyAI → Rebuttal detection

        Args:
            audio_file_path: Path to audio file (may be temp file)
            original_file_path: Original file path for cache lookup (if different from audio_file_path)

        Returns:
            Standardized detection result
        """
        start_time = time.time()

        try:
            # Use original path for logging if provided
            cache_key = original_file_path if original_file_path else audio_file_path
            logger.debug(f"Starting agent-only rebuttal detection with AssemblyAI: {audio_file_path} (cache key: {cache_key})")

            # Step 1: Transcribe only agent channel with AssemblyAI (with cache support)
            transcription_result = self.transcription_engine.transcribe_agent_only(
                audio_file_path, 
                original_file_path=original_file_path
            )

            if not transcription_result["transcript"]:
                return self.formatter.format_result(
                    result="Error",
                    confidence_score=0.0,
                    transcript="",
                    raw_transcript="",
                    processing_time_ms=transcription_result["processing_time_ms"],
                    error_type="transcription_failed",
                    error_message=transcription_result.get("error", "No transcript generated")
                )

            raw_transcript = transcription_result["transcript"]
            logger.debug(f"Raw AssemblyAI transcript: '{raw_transcript[:100]}...'")

            # Step 2: Apply Egyptian accent corrections for better accuracy
            corrected_transcript, accent_corrections = self.egyptian_corrector.apply_corrections(raw_transcript)
            logger.debug(f"Applied {len(accent_corrections)} Egyptian accent corrections")
            logger.debug(f"Final corrected transcript (displayed in app): '{corrected_transcript[:100]}...'")

            # Step 3: Detect rebuttals using corrected transcript with full dialogue context
            dialogue = transcription_result.get("dialogue", "")
            
            # Use dialogue for display if available (preferred for UI)
            # Apply corrections to the dialogue string too so the display is clean
            display_transcript = dialogue if dialogue else corrected_transcript
            if dialogue:
                display_transcript, _ = self.egyptian_corrector.apply_corrections(dialogue)

            matches, feedback_metadata = self.semantic_engine.detect_rebuttals(corrected_transcript, dialogue=dialogue)

            # Step 4: Determine final result
            if matches:
                best_match = matches[0]  # Highest confidence
                result = "Yes"
                confidence = best_match['confidence']
                logger.debug(f"REBUTTAL DETECTED: {best_match['phrase']} (confidence: {confidence:.3f})")
            else:
                result = "No"
                confidence = 0.0
                logger.debug("No rebuttals detected")

            # Step 5: Format final result
            processing_time = int((time.time() - start_time) * 1000)
            
            # Prepare feedback string for dashboard
            feedback_str = None
            if feedback_metadata and 'llm_reasoning' in feedback_metadata:
                feedback_str = feedback_metadata['llm_reasoning']
                # Format specific feedback if LLM triggered
                if 'llm_confidence' in feedback_metadata:
                    conf = feedback_metadata['llm_confidence']
                    feedback_str = f"LLM evaluation: not_interested -> False (confidence: {conf:.2f})\n{feedback_str}"
            elif result == "No":
                 # If no LLM reasoning but result is No, we might want to explain why LLM didn't run?
                 # Or just leave it empty if it was skipped due to high confidence or other reasons
                 pass

            return self.formatter.format_result(
                result=result,
                confidence_score=confidence,
                matched_phrases=matches,
                transcript=display_transcript,  # ✅ DISPLAY TRANSCRIPT (Formatted Dialogue) - appears in App
                raw_transcript=raw_transcript,    # Raw transcript - For debugging
                corrections_made=accent_corrections,
                processing_time_ms=processing_time,
                metadata={
                    "audio_quality_score": transcription_result.get("audio_quality_score", 0.0),
                    "transcription_method": "assemblyai_api",
                    "channels_processed": 2,  # Dual-channel with speaker diarization
                    "agent_only_mode": False,  # Now processing both speakers
                    "accent_corrections_applied": len(accent_corrections),
                    "speakers": transcription_result.get("speakers", []),
                    "utterances_count": len(transcription_result.get("utterances", [])),
                    "dialogue": dialogue,  # Full conversation for LLM (also used for display now)
                    "owner_transcript": transcription_result.get("owner_transcript", ""),  # Owner's words
                    "feedback": feedback_str  # Pass feedback to formatter
                }
            )

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Agent-only detection failed: {e}")
            return self.formatter.format_result(
                result="Error",
                confidence_score=0.0,
                processing_time_ms=processing_time,
                error_type="processing_error",
                error_message=str(e)
            )
    
    async def detect_rebuttals_in_audio_async(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Async version of detect_rebuttals_in_audio - uses async transcription for better concurrency.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Standardized detection result (same format as detect_rebuttals_in_audio)
        """
        start_time = time.time()

        try:
            logger.debug(f"Starting async agent-only rebuttal detection with AssemblyAI: {audio_file_path}")
            
            # Get audio duration for timeout calculation and logging
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_file_path)
                audio_duration_seconds = len(audio) / 1000.0
                logger.debug(f"Audio file duration: {audio_duration_seconds:.1f}s")
            except Exception as e:
                logger.warning(f"Could not determine audio duration: {e}")
                audio_duration_seconds = None

            # Step 1: Transcribe only agent channel with AssemblyAI (async)
            transcription_start = time.time()
            transcription_result = await self.transcription_engine.transcribe_agent_only_async(
                audio_file_path, 
                audio_duration_seconds=audio_duration_seconds
            )
            transcription_elapsed = time.time() - transcription_start
            logger.debug(f"Transcription step completed in {transcription_elapsed:.2f}s")

            if not transcription_result["transcript"]:
                # Check if it's a timeout error - if so, return "No" instead of "Error"
                error_msg = transcription_result.get("error", "No transcript generated")
                is_timeout = 'ReadTimeout' in error_msg or 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower()
                
                result_value = "No"  # Always return "No" for failed transcription (treat as no rebuttal detected)
                logger.warning(f"Transcription failed for agent-only detection: {error_msg}. Returning '{result_value}'.")
                
                return self.formatter.format_result(
                    result=result_value,
                    confidence_score=0.0,
                    transcript="",
                    raw_transcript="",
                    processing_time_ms=transcription_result["processing_time_ms"],
                    error_type="transcription_failed",
                    error_message=error_msg
                )

            raw_transcript = transcription_result["transcript"]
            logger.debug(f"Raw AssemblyAI transcript: '{raw_transcript[:100]}...'")

            # Step 2: Apply Egyptian accent corrections for better accuracy (CPU-bound, run in executor)
            import asyncio
            loop = asyncio.get_event_loop()
            correction_start = time.time()
            corrected_result = await loop.run_in_executor(
                None,
                self.egyptian_corrector.apply_corrections,
                raw_transcript
            )
            corrected_transcript, accent_corrections = corrected_result
            correction_elapsed = time.time() - correction_start
            logger.debug(
                f"Applied {len(accent_corrections)} Egyptian accent corrections "
                f"in {correction_elapsed:.2f}s"
            )
            logger.debug(f"Final corrected transcript (displayed in app): '{corrected_transcript[:100]}...'")

            # Step 3: Detect rebuttals using corrected transcript (CPU-bound, run in executor)
            detection_start = time.time()
            matches = await loop.run_in_executor(
                None,
                self.semantic_engine.detect_rebuttals,
                corrected_transcript
            )
            detection_elapsed = time.time() - detection_start
            logger.debug(f"Semantic rebuttal detection completed in {detection_elapsed:.2f}s")

            # Step 4: Determine final result
            if matches:
                best_match = matches[0]  # Highest confidence
                result = "Yes"
                confidence = best_match['confidence']
                logger.debug(f"REBUTTAL DETECTED: {best_match['phrase']} (confidence: {confidence:.3f})")
            else:
                result = "No"
                confidence = 0.0
                logger.debug("No rebuttals detected")

            # Step 5: Format final result
            processing_time = int((time.time() - start_time) * 1000)

            return self.formatter.format_result(
                result=result,
                confidence_score=confidence,
                matched_phrases=matches,
                transcript=corrected_transcript,  # ✅ CORRECTED TRANSCRIPT - This is what appears in the app's "Transcription" column
                raw_transcript=raw_transcript,    # ❌ Raw transcript - For debugging only
                corrections_made=accent_corrections,
                processing_time_ms=processing_time,
                metadata={
                    "audio_quality_score": transcription_result.get("audio_quality_score", 0.0),
                    "transcription_method": "assemblyai_api",
                    "channels_processed": 1,
                    "agent_only_mode": True,
                    "accent_corrections_applied": len(accent_corrections),
                    "speakers": transcription_result.get("speakers", []),
                    "utterances_count": len(transcription_result.get("utterances", []))
                }
            )

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Async agent-only detection failed: {e}")
            return self.formatter.format_result(
                result="Error",
                confidence_score=0.0,
                processing_time_ms=processing_time,
                error_type="processing_error",
                error_message=str(e)
            )

def test_agent_only_system():
    """Test the agent-only system with AssemblyAI API."""
    print("Testing Agent-Only Rebuttal Detection System (AssemblyAI)")
    print("=" * 65)

    detector = AgentOnlyRebuttalDetector()

    # Test with sample audio file if it exists
    test_files = ["sample1.flac", "test_audio.wav", "sample.wav"]

    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\nTesting with: {test_file}")
            result = detector.detect_rebuttals_in_audio(test_file)

            print(f"Result: {result['result']}")
            print(".3f")
            print(f"Processing time: {result['metadata']['processing_time_ms']}ms")
            print(f"Transcription method: {result['metadata']['transcription_method']}")
            print(f"Transcript: '{result['transcript'][:100]}...'")
            break
    else:
        print("No test audio files found in current directory")
        print("   Place a sample audio file (sample1.flac, test_audio.wav, etc.) to test")
        print("\nSample test code:")
        print("   result = detector.detect_rebuttals_in_audio('your_audio_file.wav')")
        print("   print(f'Rebuttal detected: {result[\"result\"]}')")

if __name__ == "__main__":
    print("Agent-Only Rebuttal Detection System (AssemblyAI)")
    print("=" * 55)
    print()
    print("Features:")
    print("• Transcribes ONLY agent channel (where rebuttals occur)")
    print("• Uses AssemblyAI API for transcription (cloud-based, high accuracy)")
    print("• Speaker diarization for better channel separation")
    print("• 50% less audio processing than dual-channel")
    print("• More focused on rebuttal detection")
    print("• Scalable cloud processing")
    print()
    print("Usage:")
    print("   detector = AgentOnlyRebuttalDetector()")
    print("   result = detector.detect_rebuttals_in_audio('audio_file.wav')")
    print()
    print("Testing:")
    test_agent_only_system()
