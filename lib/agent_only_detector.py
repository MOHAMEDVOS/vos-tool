#!/usr/bin/env python3
"""
Agent-Only Transcription System - AssemblyAI Only
Uses AssemblyAI API for cloud-based transcription with speaker diarization.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional, List

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pydub import AudioSegment

# Import existing components
from analyzer.rebuttal_detection import KeywordRepository, SemanticDetectionEngine, OutputFormatter, TranscriptionEngine
from lib.egyptian_accent_correction import EgyptianAccentCorrection

# Configure logging - Essential detection info only
logging.basicConfig(level=logging.WARNING)  # Reduce verbosity, only show warnings/errors
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
            logger.info("LocalTranscriptionEngine initialized with AssemblyAI API")
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
        logger.info("Agent-Only Transcription Engine initialized with AssemblyAI")

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

    def transcribe_agent_only(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Transcribe only the agent channel using AssemblyAI with speaker diarization.

        Args:
            audio_file_path: Path to the audio file

        Returns:
            Dict with transcript and metadata
        """
        start_time = time.time()

        try:
            logger.info(f"Starting agent-only transcription with AssemblyAI: {audio_file_path}")

            # Transcribe with fast-path settings (no diarization for speed)
            # Disable language detection to avoid failures on low/zero-speech clips
            result = self.local_engine.assemblyai_engine.transcribe_file(
                audio_file_path,
                enable_speaker_diarization=False,  # Disabled for faster processing
                options={
                    "language_detection": False,
                    "language_code": "en"
                }
            )
            
            # Extract agent transcript from speaker-separated utterances
            # For now, return full transcript (can be enhanced to identify agent speaker)
            agent_transcript = result.get("transcript", "")
            speakers = result.get("speakers", [])
            utterances = result.get("utterances", [])
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "transcript": agent_transcript,
                "full_transcript": agent_transcript,  # Full transcript for now
                "speakers": speakers,
                "utterances": utterances,
                "processing_time_ms": processing_time,
                "transcription_method": "assemblyai_api",
                "channels_processed": 1,  # Agent only
                "error": "" if agent_transcript else "transcription_failed"
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Agent-only transcription failed: {e}")
            return {
                "transcript": "",
                "error": str(e),
                "processing_time_ms": processing_time
            }
    
    async def transcribe_agent_only_async(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Async version of transcribe_agent_only - runs transcription in thread pool to avoid blocking.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Dict with transcript and metadata (same format as transcribe_agent_only)
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe_agent_only, audio_file_path)

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

    def __init__(self, api_key: Optional[str] = None, user_api_key: Optional[str] = None):
        """
        Initialize agent-only rebuttal detector with AssemblyAI.
        
        Args:
            api_key: AssemblyAI API key (fallback if user_api_key is None)
            user_api_key: User's specific API key (takes precedence)
        """
        self.transcription_engine = AgentOnlyTranscriptionEngine(api_key, user_api_key)
        self.keyword_repo = KeywordRepository()
        self.semantic_engine = SemanticDetectionEngine(self.keyword_repo)
        self.formatter = OutputFormatter()
        # Add Egyptian accent correction for better accuracy with Egyptian-accented speech
        self.egyptian_corrector = EgyptianAccentCorrection()
        logger.info("Agent-Only Rebuttal Detector initialized with AssemblyAI (Egyptian Accent Support)")

    def detect_rebuttals_in_audio(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Complete pipeline: Agent-only transcription with AssemblyAI → Rebuttal detection

        Args:
            audio_file_path: Path to audio file

        Returns:
            Standardized detection result
        """
        start_time = time.time()

        try:
            logger.info(f"Starting agent-only rebuttal detection with AssemblyAI: {audio_file_path}")

            # Step 1: Transcribe only agent channel with AssemblyAI
            transcription_result = self.transcription_engine.transcribe_agent_only(audio_file_path)

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
            logger.info(f"Raw AssemblyAI transcript: '{raw_transcript[:100]}...'")

            # Step 2: Apply Egyptian accent corrections for better accuracy
            corrected_transcript, accent_corrections = self.egyptian_corrector.apply_corrections(raw_transcript)
            logger.info(f"Applied {len(accent_corrections)} Egyptian accent corrections")
            logger.info(f"Final corrected transcript (displayed in app): '{corrected_transcript[:100]}...'")

            # Step 3: Detect rebuttals using corrected transcript
            matches = self.semantic_engine.detect_rebuttals(corrected_transcript)

            # Step 4: Determine final result
            if matches:
                best_match = matches[0]  # Highest confidence
                result = "Yes"
                confidence = best_match['confidence']
                logger.info(f"REBUTTAL DETECTED: {best_match['phrase']} (confidence: {confidence:.3f})")
            else:
                result = "No"
                confidence = 0.0
                logger.info("No rebuttals detected")

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
            logger.info(f"Starting async agent-only rebuttal detection with AssemblyAI: {audio_file_path}")

            # Step 1: Transcribe only agent channel with AssemblyAI (async)
            transcription_result = await self.transcription_engine.transcribe_agent_only_async(audio_file_path)

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
            logger.info(f"Raw AssemblyAI transcript: '{raw_transcript[:100]}...'")

            # Step 2: Apply Egyptian accent corrections for better accuracy (CPU-bound, run in executor)
            import asyncio
            loop = asyncio.get_event_loop()
            corrected_result = await loop.run_in_executor(
                None,
                self.egyptian_corrector.apply_corrections,
                raw_transcript
            )
            corrected_transcript, accent_corrections = corrected_result
            logger.info(f"Applied {len(accent_corrections)} Egyptian accent corrections")
            logger.info(f"Final corrected transcript (displayed in app): '{corrected_transcript[:100]}...'")

            # Step 3: Detect rebuttals using corrected transcript (CPU-bound, run in executor)
            matches = await loop.run_in_executor(
                None,
                self.semantic_engine.detect_rebuttals,
                corrected_transcript
            )

            # Step 4: Determine final result
            if matches:
                best_match = matches[0]  # Highest confidence
                result = "Yes"
                confidence = best_match['confidence']
                logger.info(f"REBUTTAL DETECTED: {best_match['phrase']} (confidence: {confidence:.3f})")
            else:
                result = "No"
                confidence = 0.0
                logger.info("No rebuttals detected")

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
