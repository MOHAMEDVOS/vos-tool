#!/usr/bin/env python3
"""
Agent-Only Transcription System - Local Only
Uses only local Whisper Medium model for transcription
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional, List

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pydub import AudioSegment
# Remove cloud imports - using only local Whisper Medium

# Import existing components
from analyzer.rebuttal_detection import KeywordRepository, SemanticDetectionEngine, OutputFormatter, TranscriptionEngine
from models import get_whisper_model
from lib.egyptian_accent_correction import EgyptianAccentCorrection

# Configure logging - Essential detection info only
logging.basicConfig(level=logging.WARNING)  # Reduce verbosity, only show warnings/errors
logger = logging.getLogger(__name__)

class LocalTranscriptionEngine:
    """Local-only transcription using Whisper Medium."""

    def __init__(self):
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize local Whisper Medium model using singleton with CPU optimizations."""
        try:
            # Apply CPU optimizations before loading model
            from lib.whisper_optimizer import apply_whisper_optimizations
            self.whisper_optimizer = apply_whisper_optimizations()
            
            # Use shared singleton model
            self.model = get_whisper_model()
            if self.model is not None:
                logger.info("Local Whisper Medium model loaded successfully (using singleton with CPU optimizations)")
            else:
                logger.error("Failed to load singleton Whisper model")
        except Exception as e:
            logger.error(f"Failed to load local Whisper model: {e}")
            self.model = None
            self.whisper_optimizer = None

    def transcribe_audio(self, audio_segment: AudioSegment) -> str:
        """Transcribe audio using local Whisper Medium with optimizations for short calls."""
        if self.model is None:
            logger.warning("Local model not available")
            return ""

        logger.info(f"Starting local transcription of {len(audio_segment)}ms audio")

        # Validate audio
        if len(audio_segment) < 500:  # Less than 0.5 seconds
            logger.warning("Audio too short for transcription")
            return ""

        # AUDIO PREPROCESSING FOR BETTER TRANSCRIPTION
        # Normalize volume for consistent quality
        audio_segment = audio_segment.normalize()
        
        # Add silence padding for short audio (helps Whisper get context)
        is_short_audio = len(audio_segment) < 15000  # < 15 seconds
        if is_short_audio:
            silence = AudioSegment.silent(duration=2000)  # 2 seconds
            audio_segment = silence + audio_segment + silence
            logger.info("Added silence padding for short audio")

        # Export to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_segment.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
            tmp_path = tmp.name

        try:
            start_time = time.time()

            # CPU-OPTIMIZED WHISPER PARAMETERS
            if is_short_audio:
                # Get CPU-optimized parameters for short audio
                if hasattr(self, 'whisper_optimizer') and self.whisper_optimizer:
                    params = self.whisper_optimizer.get_optimized_whisper_params()
                    # Override for MAXIMUM SPEED
                    params.update({
                        'beam_size': 1,  # Fastest possible (greedy decoding)
                        'patience': 1.0,  # Minimum patience
                        'temperature': [0.0]  # Single temperature for speed
                    })
                else:
                    # Fallback parameters - MAXIMUM SPEED
                    params = {
                        'language': 'en',
                        'task': 'transcribe',
                        'beam_size': 1,  # Fastest possible
                        'patience': 1.0,  # Minimum patience
                        'temperature': [0.0],  # Single temperature
                        'compression_ratio_threshold': 2.0,  # More strict for speed
                        'logprob_threshold': -0.5,  # More strict for speed
                        'no_speech_threshold': 0.8,  # Higher threshold for speed
                        'condition_on_previous_text': False,  # Disable for speed
                        'initial_prompt': None  # Remove prompt for speed
                    }
                
                result = self.model(tmp_path, **params)
                logger.info("Used optimized Whisper parameters for short audio")
            else:
                # OPTIMIZED: Increase chunking threshold - don't chunk audio under 3 minutes
                is_long_audio = len(audio_segment) > 180000  # > 3 minutes (180 seconds)
                if is_long_audio:
                    # For long audio, use chunking approach: split into segments and combine transcripts
                    logger.info("Using chunking approach for long audio")
                    transcript = self._transcribe_long_audio_chunked(audio_segment)
                    if transcript:
                        logger.info("Chunked transcription completed successfully")
                        return transcript
                    else:
                        # Fallback to basic transcription if chunking fails
                        logger.warning("Chunking failed, falling back to basic transcription")
                        result = self.model(tmp_path, return_timestamps=True)
                        transcript = result.get("text", "").strip()
                        return transcript.lower() if transcript else ""
                else:
                    # For moderately long audio (< 3 minutes), use single-pass transcription
                    logger.info("Using single-pass transcription for moderately long audio")
                    result = self.model(tmp_path, return_timestamps=True)
                    logger.info("Single-pass transcription completed")

            processing_time = time.time() - start_time
            logger.info(f"Local transcription completed in {processing_time:.2f} seconds")

            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                # Ignore file cleanup errors
                pass
            
            transcript = result.get("text", "").strip()
            
            # CRITICAL: Clear memory after transcription to prevent accumulation
            import gc
            gc.collect()
            
            # Validate transcript
            if not transcript or len(transcript.strip()) < 2:
                logger.warning("Transcription resulted in empty or very short text")
                return ""
                
            logger.info(f"Local transcription completed in {processing_time:.2f}s")
            return transcript.lower()

        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            return ""

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                # Ignore file cleanup errors
                pass

    def _transcribe_long_audio_chunked(self, audio_segment: AudioSegment) -> str:
        """Transcribe long audio by splitting into chunks and combining results."""
        # OPTIMIZED: Maintain chunk size safely under Whisper's 30s limit
        chunk_length_ms = 28000  # Keep < 30s so long-form mode isn't triggered
        overlap_ms = 200         # Reduced overlap for minimal duplication

        total_duration = len(audio_segment)

        logger.info(f"Splitting {total_duration}ms audio into {chunk_length_ms}ms chunks with {overlap_ms}ms overlap")

        chunks = []
        start_time = 0

        while start_time < total_duration:
            end_time = min(start_time + chunk_length_ms, total_duration)
            chunk = audio_segment[start_time:end_time]

            # Add overlap with previous chunk (except for first chunk)
            if start_time > 0 and overlap_ms > 0:
                overlap_start = max(0, start_time - overlap_ms)
                overlap_chunk = audio_segment[overlap_start:start_time]
                chunk = overlap_chunk + chunk

            chunks.append((start_time, chunk))
            start_time += chunk_length_ms - overlap_ms  # Advance with overlap

        logger.info(f"Created {len(chunks)} chunks for transcription")

        # Optimized for i7-1255U with 16GB RAM - can handle more workers
        import concurrent.futures
        chunk_transcripts = []

        # Use more workers - up to 6 for better utilization
        max_workers = min(6, len(chunks))
        logger.info(f"Processing {len(chunks)} chunks concurrently with {max_workers} workers...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all transcription tasks
            future_to_chunk = {
                executor.submit(self._transcribe_single_chunk, chunk_audio): (i, chunk_start)
                for i, (chunk_start, chunk_audio) in enumerate(chunks)
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_chunk):
                i, chunk_start = future_to_chunk[future]
                try:
                    chunk_transcript = future.result()
                    if chunk_transcript:
                        chunk_transcripts.append((i, chunk_transcript.strip()))  # Keep index for sorting
                        logger.debug(f"Chunk {i+1} completed: '{chunk_transcript[:50]}...'")
                except Exception as e:
                    logger.warning(f"Chunk {i+1} failed: {e}")

        # Sort transcripts by chunk index to maintain order
        chunk_transcripts.sort(key=lambda x: x[0])
        chunk_transcripts = [transcript for _, transcript in chunk_transcripts]

        if not chunk_transcripts:
            logger.warning("No chunks were successfully transcribed")
            return ""

        # Combine transcripts with intelligent merging
        combined_transcript = self._merge_chunk_transcripts(chunk_transcripts)
        logger.info(f"Combined transcript length: {len(combined_transcript)} characters")

        return combined_transcript.lower()

    def _transcribe_single_chunk(self, chunk_audio: AudioSegment) -> str:
        """Transcribe a single audio chunk using pipeline-compatible parameters."""
        if self.model is None:
            return ""

        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                chunk_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                tmp_path = tmp.name

            # Use transformers pipeline compatible parameters for chunk transcription
            # Disable timestamps for chunks since they're cut off mid-word and cause warnings
            result = self.model(
                tmp_path,
                return_timestamps=False,  # Disabled for chunks to avoid timestamp warnings
                generate_kwargs={
                    "max_new_tokens": 200,  # Allow reasonable length for chunks
                    "do_sample": False,  # Deterministic for consistency
                    "temperature": 0.0,  # No randomness
                }
            )

            transcript = result.get("text", "").strip()
            
            # CRITICAL: Clear memory after each chunk to prevent accumulation
            import gc
            gc.collect()
            
            return transcript

        except Exception as e:
            logger.warning(f"Chunk transcription failed: {e}")
            return ""
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                # Ignore file cleanup errors
                pass

    def _merge_chunk_transcripts(self, transcripts: List[str]) -> str:
        """Merge chunk transcripts with intelligent overlap handling and deduplication."""
        if not transcripts:
            return ""

        if len(transcripts) == 1:
            return transcripts[0]

        # Start with the first transcript
        merged = transcripts[0]

        for next_transcript in transcripts[1:]:
            if not next_transcript.strip():
                continue

            # Try to find overlap between end of current merged text and start of next transcript
            overlap_removed = self._remove_overlap(merged, next_transcript)

            # If overlap removal worked, use that; otherwise, just concatenate
            if overlap_removed != next_transcript:
                merged += " " + overlap_removed
            else:
                merged += " " + next_transcript

        # Remove consecutive repetitions (like "this is pedro jimenez" repeated)
        merged = self._remove_consecutive_repetitions(merged)

        # Additional pass: Remove longer repetitive sequences that span across merge points
        merged = self._remove_long_repetitions(merged)

        return merged.strip()

    def _remove_overlap(self, text1: str, text2: str, max_overlap_words: int = 20) -> str:
        """Remove overlapping text between two transcript segments with improved detection."""
        words1 = text1.split()
        words2 = text2.split()

        # Look for longer overlaps to catch repetitive phrases (from 20 down to 6 words)
        for overlap_len in range(min(max_overlap_words, len(words1), len(words2)), 5, -1):
            suffix = words1[-overlap_len:]
            prefix = words2[:overlap_len]

            if suffix == prefix:
                # Found overlap, remove it from text2
                return " ".join(words2[overlap_len:])

        # If no exact overlap found, try fuzzy matching for similar content
        # This helps with slight transcription variations
        for overlap_len in range(min(15, len(words1), len(words2)), 8, -1):
            suffix = words1[-overlap_len:]
            prefix = words2[:overlap_len]

            # Check if most words match (allow for small differences)
            matches = sum(1 for w1, w2 in zip(suffix, prefix) if w1.lower() == w2.lower())
            if matches >= overlap_len * 0.8:  # 80% match
                return " ".join(words2[overlap_len:])

        # No overlap found, return text2 as-is
        return text2

    def _remove_long_repetitions(self, text: str, min_phrase_length: int = 10) -> str:
        """Remove longer repetitive phrases that weren't caught by consecutive repetition removal."""
        if not text:
            return text

        words = text.split()
        if len(words) < min_phrase_length * 2:
            return text

        result = []
        i = 0

        while i < len(words):
            # Look for repeated phrases of 10-25 words
            found_repetition = False

            for phrase_len in range(min(25, len(words) - i), min_phrase_length - 1, -1):
                if i + phrase_len * 2 <= len(words):
                    phrase = words[i:i + phrase_len]
                    next_phrase = words[i + phrase_len:i + phrase_len * 2]

                    # Check if phrases are very similar (accounting for minor variations)
                    if self._phrases_similar(phrase, next_phrase, threshold=0.9):
                        # Found repetition, skip all occurrences
                        repetitions = 2
                        while (i + phrase_len * (repetitions + 1) <= len(words) and
                               self._phrases_similar(words[i + phrase_len * repetitions:i + phrase_len * (repetitions + 1)],
                                                   phrase, threshold=0.9)):
                            repetitions += 1

                        # Keep only one instance
                        result.extend(phrase)
                        i += phrase_len * repetitions
                        found_repetition = True
                        break

            if not found_repetition:
                result.append(words[i])
                i += 1

        return " ".join(result)

    def _phrases_similar(self, phrase1: List[str], phrase2: List[str], threshold: float = 0.9) -> bool:
        """Check if two phrases are similar above the given threshold."""
        if len(phrase1) != len(phrase2):
            return False

        matches = sum(1 for w1, w2 in zip(phrase1, phrase2) if w1.lower() == w2.lower())
        similarity = matches / len(phrase1)

        return similarity >= threshold

    def _remove_consecutive_repetitions(self, text: str, min_repetition_length: int = 3) -> str:
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
    """Transcribes only the agent channel using local Whisper Medium."""

    def __init__(self):
        self.local_engine = LocalTranscriptionEngine()
        logger.info("Agent-Only Transcription Engine initialized (Local Only)")

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
        Transcribe only the agent channel using local Whisper Medium.

        Args:
            audio_file_path: Path to the audio file

        Returns:
            Dict with transcript and metadata
        """
        start_time = time.time()

        try:
            logger.info(f"Starting agent-only transcription: {audio_file_path}")

            # Load audio
            audio_segment = AudioSegment.from_file(audio_file_path)
            logger.info(f"Loaded audio: {len(audio_segment)}ms, {audio_segment.channels} channels")

            # Extract agent channel
            agent_audio = self.extract_agent_channel(audio_segment)
            logger.info(f"Agent channel extracted: {len(agent_audio)}ms")

            # Validate audio quality
            quality_result = self._validate_audio_quality(agent_audio)
            if not quality_result["audio_quality_ok"]:
                return {
                    "transcript": "",
                    "error": quality_result.get("skipped_reason", "poor_quality"),
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }

            # Transcribe with local model
            transcript = self.local_engine.transcribe_audio(agent_audio)

            processing_time = int((time.time() - start_time) * 1000)

            result = {
                "transcript": transcript,
                "processing_time_ms": processing_time,
                "audio_quality_score": quality_result.get("audio_quality_score", 0.0),
                "transcription_method": "local_whisper_medium",
                "channels_processed": 1,  # Agent only
                "error": "" if transcript else "transcription_failed"
            }

            logger.info(f"Agent-only transcription completed in {processing_time}ms")
            return result

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Agent-only transcription failed: {e}")
            return {
                "transcript": "",
                "error": str(e),
                "processing_time_ms": processing_time
            }

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
    """Complete rebuttal detection system using only agent channel transcription with local Whisper Medium."""

    def __init__(self):
        self.transcription_engine = AgentOnlyTranscriptionEngine()
        self.keyword_repo = KeywordRepository()
        self.semantic_engine = SemanticDetectionEngine(self.keyword_repo)
        self.formatter = OutputFormatter()
        # Add Egyptian accent correction for better accuracy with Egyptian-accented speech
        self.egyptian_corrector = EgyptianAccentCorrection()
        logger.info("Agent-Only Rebuttal Detector initialized (Local Only - Egyptian Accent Support)")

    def detect_rebuttals_in_audio(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Complete pipeline: Agent-only transcription with local Whisper Medium → Rebuttal detection

        Args:
            audio_file_path: Path to audio file

        Returns:
            Standardized detection result
        """
        start_time = time.time()

        try:
            logger.info(f"Starting agent-only rebuttal detection (local): {audio_file_path}")

            # Step 1: Transcribe only agent channel with local model
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
            logger.info(f"Raw local transcript: '{raw_transcript[:100]}...'")

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
                    "transcription_method": "local_whisper_medium",
                    "channels_processed": 1,
                    "agent_only_mode": True,
                    "local_processing": True,
                    "accent_corrections_applied": len(accent_corrections)
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

def test_agent_only_system():
    """Test the agent-only system with local Whisper Medium."""
    print("Testing Agent-Only Rebuttal Detection System (Local Only)")
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
    print("Agent-Only Rebuttal Detection System (Local Only)")
    print("=" * 55)
    print()
    print("Features:")
    print("• Transcribes ONLY agent channel (where rebuttals occur)")
    print("• Uses LOCAL Whisper Medium model (higher accuracy than small)")
    print("• Faster processing than cloud (once model loads)")
    print("• 50% less audio processing than dual-channel")
    print("• More focused on rebuttal detection")
    print("• Free - no API costs")
    print()
    print("Usage:")
    print("   detector = AgentOnlyRebuttalDetector()")
    print("   result = detector.detect_rebuttals_in_audio('audio_file.wav')")
    print()
    print("Testing:")
    test_agent_only_system()
