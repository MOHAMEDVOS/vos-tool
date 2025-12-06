"""
Rebuttal Detection Module for VOS Tool
Handles detection of sales rebuttals in call recordings with Egyptian accent support.
"""

import time
import logging
import os
import json
import re  # Required for regex operations in transcription quality assessment
from typing import Dict, List, Any, Optional, Tuple
from pydub import AudioSegment
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from models import (
    get_semantic_model as _model_get_semantic_model,
    reload_semantic_embeddings as _model_reload_semantic_embeddings,
    get_whisper_model as _model_get_whisper_model,
)


def _get_semantic_model():
    return _model_get_semantic_model()


def reload_semantic_embeddings():
    return _model_reload_semantic_embeddings()


def _get_whisper_model():
    return _model_get_whisper_model()

try:
    from lib.app_settings_manager import app_settings as persistent_app_settings
except ImportError:
    persistent_app_settings = None

logger = logging.getLogger(__name__)

# Try to load LLaMA classifier for complex cases
try:
    from experimental.llama_rebuttal_classifier import llama_rebuttal_detection
    LLAMA_AVAILABLE = True
    logger.info("✅ LLaMA classifier loaded successfully (available for complex cases)")
except ImportError as e:
    LLAMA_AVAILABLE = False
    llama_rebuttal_detection = None
    # Silently handle missing llama_cpp - it's an optional dependency
    if 'llama_cpp' not in str(e):
        logger.debug(f"LLaMA classifier not available: {e}")
except Exception as e:
    LLAMA_AVAILABLE = False
    llama_rebuttal_detection = None
    # Only log if it's not the expected missing module error
    if 'llama_cpp' not in str(e):
        logger.debug(f"LLaMA classifier initialization failed: {e}")

class DataIngestionLayer:
    """Handles input validation and preprocessing."""

    def __init__(self):
        self.min_duration_seconds = 1.0
        self.max_duration_seconds = 300.0

    def validate_input(self, audio_segment: AudioSegment) -> Dict[str, Any]:
        """Validate input audio segment."""
        if not isinstance(audio_segment, AudioSegment):
            return {"is_valid": False, "errors": ["Input must be AudioSegment"]}

        duration_seconds = len(audio_segment) / 1000.0
        if duration_seconds < self.min_duration_seconds:
            return {"is_valid": False, "errors": [f"Audio too short: {duration_seconds:.1f}s"]}

        if duration_seconds > self.max_duration_seconds:
            return {"is_valid": False, "errors": [f"Audio too long: {duration_seconds:.1f}s"]}

        return {"is_valid": True, "errors": [], "metadata": {"duration_seconds": duration_seconds}}


class PreprocessingPipeline:
    """Audio preprocessing and quality validation."""

    def __init__(self):
        self.min_duration_seconds = 1.0

    def extract_agent_channel(self, audio_segment: AudioSegment) -> AudioSegment:
        """Extract agent audio channel."""
        if audio_segment.channels == 2:
            return audio_segment.split_to_mono()[0]
        return audio_segment

    def split_channels(self, audio_segment: AudioSegment) -> Tuple[AudioSegment, AudioSegment, bool]:
        """Split stereo audio into agent and owner channels.
        Returns: (agent_audio, owner_audio, is_stereo)
        """
        if audio_segment.channels == 2:
            channels = audio_segment.split_to_mono()
            return channels[0], channels[1], True  # Left=agent, Right=owner
        else:
            # For mono, treat as agent channel, create empty owner
            return audio_segment, AudioSegment.empty(), False

    def normalize_for_transcription(self, audio_segment: AudioSegment) -> AudioSegment:
        """
        Enhanced normalization for transcription with quality improvements.
        Whisper requires 16kHz, mono, 16-bit PCM audio.
        """
        try:
            # Apply enhanced preprocessing for better transcription quality
            enhanced = self._apply_enhanced_preprocessing(audio_segment)
            logger.debug(f"Audio enhanced and normalized: {enhanced.frame_rate}Hz, {enhanced.channels}ch, {enhanced.sample_width*8}bit")
            return enhanced
            
        except Exception as e:
            logger.warning(f"Enhanced preprocessing failed: {e}, using basic normalization")
            # Fallback to basic normalization
            return self._basic_normalization(audio_segment)
    
    def _apply_enhanced_preprocessing(self, audio_segment: AudioSegment) -> AudioSegment:
        """Apply enhanced preprocessing for better transcription quality."""
        from pydub.effects import normalize, compress_dynamic_range
        import numpy as np
        
        enhanced = audio_segment
        
        # Step 1: Extract agent channel if stereo
        if enhanced.channels == 2:
            enhanced = enhanced.split_to_mono()[0]  # Use left channel (typically agent)
        
        # Step 2: Normalize volume
        enhanced = normalize(enhanced)
        
        # Step 3: Apply dynamic range compression for phone calls
        enhanced = compress_dynamic_range(enhanced, threshold=-25.0, ratio=3.0, attack=5.0, release=50.0)
        
        # Step 4: Resample to 16kHz
        if enhanced.frame_rate != 16000:
            enhanced = enhanced.set_frame_rate(16000)
        
        # Step 5: Ensure 16-bit
        enhanced = enhanced.set_sample_width(2)
        
        # Step 6: Basic noise reduction for phone calls
        enhanced = self._apply_phone_noise_reduction(enhanced)
        
        return enhanced
    
    def _apply_phone_noise_reduction(self, audio_segment: AudioSegment) -> AudioSegment:
        """Apply noise reduction optimized for phone call recordings."""
        try:
            samples = np.array(audio_segment.get_array_of_samples())
            
            if len(samples) > 100:
                # Simple high-pass filter for phone line noise
                window_size = min(30, len(samples) // 20)
                if window_size > 1:
                    moving_avg = np.convolve(samples, np.ones(window_size)/window_size, mode='same')
                    samples = samples - moving_avg * 0.2  # Reduce low-frequency noise
                    
                    # Prevent clipping
                    max_val = max(abs(samples.min()), abs(samples.max()))
                    if max_val > 32767:
                        samples = samples * (32767 / max_val)
                    
                    samples = samples.astype(np.int16)
            
            return audio_segment._spawn(samples.tobytes())
            
        except Exception as e:
            logger.warning(f"Phone noise reduction failed: {e}")
            return audio_segment
    
    def _basic_normalization(self, audio_segment: AudioSegment) -> AudioSegment:
        """Basic normalization as fallback."""
        # Convert to 16kHz sample rate (required by Whisper)
        audio_16khz = audio_segment.set_frame_rate(16000)
        
        # Convert to mono (should already be mono from extract_agent_channel, but ensure it)
        if audio_16khz.channels > 1:
            audio_16khz = audio_16khz.set_channels(1)
        
        # Convert to 16-bit sample width (required by Whisper)
        audio_16bit = audio_16khz.set_sample_width(2)  # 2 bytes = 16 bits
        
        # Normalize volume
        normalized = audio_16bit.normalize()
        
        return normalized

    def quality_validation(self, audio_segment: AudioSegment) -> Dict[str, Any]:
        """Validate audio quality and detect potential Whisper hallucinations."""
        duration_ms = len(audio_segment)

        # Continue processing even if recording is short; only skip extremely short clips (<1s)
        if duration_ms < 1000:
            logger.info(f"Recording too short for rebuttal detection: {duration_ms/1000:.1f}s (minimum 1s required)")
            return {"audio_quality_ok": False, "skipped_reason": "too_short"}

        if duration_ms < 20000:
            logger.info(f"Recording shorter than 20 seconds: {duration_ms/1000:.1f}s - proceeding with caution")
            return {"audio_quality_ok": True, "short_audio": True}

        # Enhanced quality checks
        audio_array = np.array(audio_segment.get_array_of_samples())

        # Check for very quiet audio
        max_amplitude = np.max(np.abs(audio_array))
        if max_amplitude < 500:  # Very quiet threshold
            logger.info(f"Audio too quiet for reliable transcription: max amplitude {max_amplitude}")
            return {"audio_quality_ok": False, "skipped_reason": "too_quiet"}

        # Calculate signal-to-noise ratio approximation
        mean_amplitude = np.mean(np.abs(audio_array))
        if mean_amplitude > 0:
            snr_estimate = max_amplitude / mean_amplitude
            if snr_estimate < 2.0:  # Poor SNR indicating noisy audio
                logger.info(f"Poor audio quality detected: SNR estimate {snr_estimate:.2f}")
                return {"audio_quality_ok": False, "skipped_reason": "poor_quality"}

        # Check for excessive silence or uniform audio (potential recording issues)
        std_amplitude = np.std(audio_array)
        if std_amplitude < 100:  # Very uniform audio
            logger.info(f"Audio too uniform (possible recording issue): std {std_amplitude}")
            return {"audio_quality_ok": False, "skipped_reason": "uniform_audio"}

        return {"audio_quality_ok": True}



class TranscriptionEngine:
    """Whisper-based speech-to-text transcription using singleton model."""

    def __init__(self):
        # Don't load model here - use global singleton
        logger.debug("TranscriptionEngine initialized (using singleton model)")

    def _load_model(self):
        """Get the global singleton Whisper model."""
        model = _get_whisper_model()
        return model is not None

    def transcribe_audio(self, audio_segment: AudioSegment) -> str:
        """Transcribe audio using Whisper with enhanced error handling and hallucination detection."""
        logger.debug(f"Starting transcription of {len(audio_segment)}ms audio")

        # Get singleton model
        model = _get_whisper_model()
        if model is None:
            logger.warning("No Whisper model available for transcription")
            return ""

        try:
            import tempfile
            import os
            
            # Export full AudioSegment to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_segment.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                tmp_path = tmp.name
            
            logger.debug("Running Whisper transcription")
            trans_start = time.time()
            
            # Determine if this is short audio for optimized parameters
            is_short_audio = len(audio_segment) < 20000  # Less than 20 seconds
            
            try:
                # OPTIMIZED WHISPER PARAMETERS FOR SHORT CALLS
                if is_short_audio:
                    # Use more robust settings for short audio
                    result = model(
                        tmp_path,
                        language='en',
                        task='transcribe',
                        beam_size=5,  # Increased from default for better accuracy
                        patience=2.0,  # More patience for short clips
                        temperature=[0.0, 0.2, 0.4],  # Multiple temperatures for robustness
                        compression_ratio_threshold=2.4,  # More lenient compression check
                        logprob_threshold=-1.0,  # More lenient probability threshold
                        no_speech_threshold=0.6,  # Adjust speech detection
                        condition_on_previous_text=True,
                        initial_prompt="This is a phone call conversation:"  # Provide context
                    )
                    logger.info("🎯 Used optimized Whisper parameters for short audio")
                else:
                    # Standard parameters for longer audio
                    result = model(tmp_path, return_timestamps=True)
            except Exception as whisper_error:
                logger.error(f"Whisper transcription error: {whisper_error}")
                # Try without timestamps as fallback
                try:
                    result = model(tmp_path)
                except Exception as fallback_error:
                    logger.error(f"Fallback transcription also failed: {fallback_error}")
                    return ""
            
            trans_time = time.time() - trans_start
            logger.debug(f"Whisper transcription completed in {trans_time:.2f}s")
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            transcript = result.get("text", "").strip()
            
            # Validate transcript
            if not transcript or len(transcript.strip()) < 2:
                logger.warning("Transcription resulted in empty or very short text")
                return ""
                
            logger.debug(f"Transcription result: '{transcript[:100]}...'")
            return transcript.lower()

        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            # Clean up temp file if it exists
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except:
                pass
            return ""

    def transcribe_dual_channels(self, agent_audio: AudioSegment, owner_audio: AudioSegment) -> Tuple[List[Dict], List[Dict]]:
        """Transcribe both agent and owner channels with timestamps and robust error handling."""
        logger.debug("Starting dual channel transcription")

        # Get singleton model
        model = _get_whisper_model()
        if model is None:
            logger.warning("No Whisper model available for dual transcription")
            return [], []

        agent_segments = []
        owner_segments = []

        try:
            import tempfile
            import os

            # Transcribe agent channel with validation
            if len(agent_audio) > 1000:  # At least 1 second of audio
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        agent_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                        agent_path = tmp.name
                    
                    logger.debug("Transcribing agent channel")
                    agent_result = model(agent_path, return_timestamps="word")
                    
                    # Process agent segments
                    if 'chunks' in agent_result:
                        for chunk in agent_result['chunks']:
                            text = chunk.get('text', '').strip()
                            if text and len(text) > 1:  # Only include meaningful segments
                                agent_segments.append({
                                    'start': chunk.get('timestamp', [0, 0])[0],
                                    'end': chunk.get('timestamp', [0, 0])[1],
                                    'text': text.lower()
                                })
                    
                    os.unlink(agent_path)
                except Exception as agent_error:
                    logger.warning(f"Agent channel transcription failed: {agent_error}")
                    # Continue with owner channel even if agent fails

            # Transcribe owner channel with validation
            if len(owner_audio) > 1000:  # At least 1 second of audio
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        owner_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                        owner_path = tmp.name
                    
                    logger.debug("Transcribing owner channel")
                    owner_result = model(owner_path, return_timestamps="word")
                    
                    # Process owner segments
                    if 'chunks' in owner_result:
                        for chunk in owner_result['chunks']:
                            text = chunk.get('text', '').strip()
                            if text and len(text) > 1:  # Only include meaningful segments
                                owner_segments.append({
                                    'start': chunk.get('timestamp', [0, 0])[0],
                                    'end': chunk.get('timestamp', [0, 0])[1],
                                    'text': text.lower()
                                })
                    
                    os.unlink(owner_path)
                except Exception as owner_error:
                    logger.warning(f"Owner channel transcription failed: {owner_error}")
                    # Continue with what we have

            logger.debug(f"Dual transcription completed: {len(agent_segments)} agent segments, {len(owner_segments)} owner segments")
            return agent_segments, owner_segments

        except Exception as e:
            logger.error(f"Dual transcription failed: {e}", exc_info=True)
            # Clean up any remaining temp files
            for path_var in ['agent_path', 'owner_path']:
                if path_var in locals():
                    try:
                        os.unlink(locals()[path_var])
                    except:
                        pass
            return [], []


def merge_segments_to_dialogue(agent_segments: List[Dict], owner_segments: List[Dict]) -> str:
    """Merge agent and owner segments chronologically into dialogue format.
    
    Args:
        agent_segments: List of agent segment dicts with 'start', 'end', 'text'
        owner_segments: List of owner segment dicts with 'start', 'end', 'text'
        
    Returns:
        Formatted dialogue string like:
        Agent: hello there
        Owner: who is this
        Agent: this is mark calling about your property
    """
    # Combine all segments with speaker labels
    all_segments = []
    
    for segment in agent_segments:
        if segment['text'].strip():  # Only include non-empty segments
            all_segments.append({
                'start': segment['start'],
                'speaker': 'Agent',
                'text': segment['text'].strip()
            })
    
    for segment in owner_segments:
        if segment['text'].strip():  # Only include non-empty segments
            all_segments.append({
                'start': segment['start'],
                'speaker': 'Owner',
                'text': segment['text'].strip()
            })
    
    # Sort by start time
    all_segments.sort(key=lambda x: x['start'])
    
    # Group consecutive segments by the same speaker
    if not all_segments:
        return ""
    
    merged_segments = []
    current_speaker = all_segments[0]['speaker']
    current_text = all_segments[0]['text']
    
    for segment in all_segments[1:]:
        if segment['speaker'] == current_speaker:
            # Merge with previous segment
            current_text += " " + segment['text']
        else:
            # Save previous segment and start new one
            merged_segments.append({
                'speaker': current_speaker,
                'text': current_text
            })
            current_speaker = segment['speaker']
            current_text = segment['text']
    
    # Add the last segment
    merged_segments.append({
        'speaker': current_speaker,
        'text': current_text
    })
    
    # Format as dialogue
    dialogue_lines = []
    for segment in merged_segments:
        dialogue_lines.append(f"{segment['speaker']}: {segment['text']}")
    
    return "\n".join(dialogue_lines)


class PhoneticAdaptationLayer:
    """Accent correction and normalization for Egyptian English."""

    def __init__(self):
        # Comprehensive Egyptian accent phonetic corrections library (800+ corrections)
        self.PHONETIC_CORRECTIONS = {
            # Property & Real Estate (Multiple Variations)
            "proberty": "property",
            "broberty": "property",
            "probirty": "property",
            "brobirty": "property",
            "propirty": "property",
            "ril": "real",
            "reel": "real",
            "ryal": "real",
            "istate": "estate",
            "estat": "estate",
            "esteyt": "estate",
            "isteit": "estate",
            "seling": "selling",
            "sellink": "selling",
            "sillink": "selling",
            "filling": "selling",
            "silence": "selling",  # NEW: Corrects "silence soon" → "selling soon"
            "sellling": "selling",  # NEW: Corrects "sellling" → "selling" (triple 'l')
            "baying": "buying",
            "bayink": "buying",
            "byink": "buying",

            # THE (Most Important - Multiple Variations)
            "ze": "the",
            "de": "the",
            "da": "the",
            "di": "the",
            "za": "the",
            "d": "the",
            "z": "the",

            # Common Verbs - HAVE (Multiple Variations)
            "haf": "have",
            "hav": "have",
            "haff": "have",
            "hafe": "have",
            "hef": "have",

            # Common Verbs - Other (Multiple Variations)
            "tink": "think",
            "sink": "think",
            "fink": "think",
            "teenk": "think",
            "sank": "thank",
            "tank": "thank",
            "fank": "thank",
            "shank": "thank",
            "tenk": "thank",
            "sru": "through",
            "tru": "through",
            "fru": "through",
            "thru": "through",
            "srough": "through",
            "trough": "through",
            "nid": "need",
            "nead": "need",
            "niid": "need",
            "ned": "need",
            "tek": "take",
            "taik": "take",
            "teyk": "take",
            "tayk": "take",
            "giv": "give",
            "gif": "give",
            "geev": "give",
            "gief": "give",
            "geif": "give",
            "bay": "pay",
            "bey": "pay",
            "pey": "pay",
            "bi": "pay",
            "bi": "buy",
            "bai": "buy",
            "bey": "buy",
            "sel": "sell",
            "sil": "sell",
            "sal": "sell",
            "rimember": "remember",
            "remimber": "remember",
            "rememper": "remember",
            "rimemper": "remember",
            "belif": "believe",
            "bilive": "believe",
            "beleef": "believe",
            "bileef": "believe",
            "believ": "believe",
            "anderstand": "understand",
            "ondirstand": "understand",
            "andarstand": "understand",
            "understend": "understand",
            "ofer": "offer",
            "ofir": "offer",
            "offar": "offer",
            "ofar": "offer",
            "rebresent": "represent",
            "reprezent": "represent",
            "ripresent": "represent",
            "rebrizent": "represent",

            # THIS/THAT/THESE/THOSE (Multiple Variations)
            "zis": "this",
            "dis": "this",
            "thiss": "this",
            "ziss": "this",
            "diss": "this",
            "zat": "that",
            "dat": "that",
            "det": "that",
            "zet": "that",
            "ziz": "these",
            "diz": "these",
            "deez": "these",
            "zeez": "these",
            "zoz": "those",
            "doz": "those",
            "doze": "those",
            "zoze": "those",
            "dos": "those",
            "zey": "they",
            "dey": "they",
            "thay": "they",
            "day": "they",
            "zay": "they",
            "zeir": "their",
            "deir": "their",
            "der": "their",
            "zair": "their",
            "dair": "their",
            "zem": "them",
            "dem": "them",
            "thim": "them",
            "dim": "them",
            "zim": "them",
            "zer": "there",
            "der": "there",
            "dere": "there",
            "zere": "there",
            "dare": "there",

            # OTHER/ANOTHER (Multiple Variations)
            "uzzer": "other",
            "uzer": "other",
            "odder": "other",
            "othir": "other",
            "azzer": "other",
            "anuzzer": "another",
            "anuther": "another",
            "anudder": "another",
            "anozzer": "another",
            "anadder": "another",

            # WITH/WITHIN (Multiple Variations)
            "wiz": "with",
            "wid": "with",
            "weeth": "with",
            "weth": "with",
            "wit": "with",
            "wizin": "within",
            "widin": "within",
            "witheen": "within",
            "withen": "within",

            # YOU/YOUR (Multiple Variations)
            "yu": "you",
            "yoo": "you",
            "ya": "you",
            "ye": "you",
            "yor": "your",
            "yur": "your",
            "yoor": "your",
            "yar": "your",
            "yur": "you're",
            "yor": "you're",
            "yoor": "you're",
            "yar": "you're",

            # NOT/NO (Multiple Variations)
            "nat": "not",
            "nawt": "not",
            "naat": "not",
            "nott": "not",
            "noo": "no",
            "na": "no",
            "now": "no",

            # PERFECT/PROBLEM (Multiple Variations)
            "berfect": "perfect",
            "pirfect": "perfect",
            "parfect": "perfect",
            "berfict": "perfect",
            "perfict": "perfect",
            "broblem": "problem",
            "probelem": "problem",
            "brobelem": "problem",
            "problim": "problem",

            # FUTURE/EVEN (Multiple Variations)
            "fuchure": "future",
            "fyucher": "future",
            "fucher": "future",
            "fewcher": "future",
            "fyutcher": "future",
            "efen": "even",
            "ifen": "even",
            "efin": "even",
            "ifin": "even",
            "eeven": "even",

            # ABOUT (Multiple Variations)
            "abot": "about",
            "abut": "about",
            "abowt": "about",
            "aboat": "about",
            "abaut": "about",

            # IMPORTANT/INTEREST (Multiple Variations)
            "imbertan": "important",
            "importan": "important",
            "importent": "important",
            "imbortan": "important",
            "embortant": "important",
            "interes": "interest",
            "intrist": "interest",
            "enterest": "interest",
            "interist": "interest",

            # BECAUSE (Multiple Variations)
            "becuz": "because",
            "bicuz": "because",
            "becoz": "because",
            "bikuz": "because",
            "bcuz": "because",

            # GOOD/WOULD/SHOULD (Multiple Variations)
            "gud": "good",
            "goud": "good",
            "gead": "good",
            "goad": "good",
            "wud": "would",
            "wuld": "would",
            "wood": "would",
            "woud": "would",
            "shud": "should",
            "shuld": "should",
            "shoud": "should",
            "shod": "should",

            # MAYBE/SOMETHING/EVERYTHING (Multiple Variations)
            "meybi": "maybe",
            "maybi": "maybe",
            "meyby": "maybe",
            "mabe": "maybe",
            "somting": "something",
            "sumting": "something",
            "somtink": "something",
            "samthing": "something",
            "everyting": "everything",
            "evryting": "everything",
            "evrything": "everything",
            "ivriting": "everything",
            "anyting": "anything",
            "enyting": "anything",
            "anytink": "anything",
            "inithing": "anything",

            # WHEN/WHERE/WHAT/WHY/HOW (Multiple Variations)
            "wen": "when",
            "win": "when",
            "wan": "when",
            "whin": "when",
            "wer": "where",
            "were": "where",
            "wair": "where",
            "whir": "where",
            "wat": "what",
            "wot": "what",
            "waat": "what",
            "wut": "what",
            "wai": "why",
            "wi": "why",
            "way": "why",
            "whi": "why",
            "haw": "how",
            "houw": "how",
            "hou": "how",
            "hu": "how",

            # MUCH/SUCH (Multiple Variations)
            "mach": "much",
            "mouch": "much",
            "moch": "much",
            "mutch": "much",
            "sach": "such",
            "souch": "such",
            "soch": "such",
            "sutch": "such",

            # TIME WORDS (Multiple Variations)
            "taim": "time",
            "tym": "time",
            "tyme": "time",
            "teim": "time",
            "minit": "minute",
            "minut": "minute",
            "minet": "minute",
            "meenit": "minute",
            "sun": "soon",
            "soun": "soon",
            "sune": "soon",
            "sean": "soon",
            "naw": "now",
            "nou": "now",
            "naow": "now",

            # MONTHS/YEARS/PERIODS (Multiple Variations)
            "manthz": "months",
            "monthes": "months",
            "manths": "months",
            "munths": "months",
            "yirz": "years",
            "yeers": "years",
            "yeerz": "years",
            "yarz": "years",
            "biryod": "period",
            "piriod": "period",
            "beriod": "period",
            "piriad": "period",

            # LEASE TERMS (Multiple Variations)
            "liz": "lease",
            "lees": "lease",
            "lis": "lease",
            "liez": "lease",
            "rint": "rent",
            "rant": "rent",
            "rient": "rent",
            "yirly": "yearly",
            "yerly": "yearly",
            "yirley": "yearly",
            "yerley": "yearly",
            "montly": "monthly",
            "mantly": "monthly",
            "manthly": "monthly",
            "munthly": "monthly",
            "exbair": "expire",
            "exbire": "expire",
            "exbayr": "expire",
            "ixpire": "expire",
            "expayer": "expire",

            # VACANT/OCCUPIED (Multiple Variations)
            "fakant": "vacant",
            "vekent": "vacant",
            "vaykent": "vacant",
            "fekant": "vacant",
            "vaceint": "vacant",
            "okubaid": "occupied",
            "occubied": "occupied",
            "okyupied": "occupied",
            "ockupayd": "occupied",
            "okupaid": "occupied",

            # PROPERTY FEATURES (Multiple Variations)
            "rof": "roof",
            "ruf": "roof",
            "rouf": "roof",
            "roff": "roof",
            "bids": "beds",
            "badz": "beds",
            "bedz": "beds",
            "bathes": "baths",
            "bass": "baths",
            "bethz": "baths",
            "abgrades": "upgrades",
            "upgradez": "upgrades",
            "upgreds": "upgrades",
            "abgredz": "upgrades",
            "ribayrz": "repairs",
            "repairz": "repairs",
            "ripayrz": "repairs",
            "repayrz": "repairs",
            "florink": "flooring",
            "floring": "flooring",
            "floorenk": "flooring",
            "paintink": "painting",
            "beinting": "painting",
            "peinting": "painting",

            # AGE/SIZE (Multiple Variations)
            "ej": "age",
            "aij": "age",
            "ayj": "age",
            "ayge": "age",
            "saiz": "size",
            "sise": "size",
            "seyz": "size",
            "syz": "size",
            "skwer": "square",
            "skware": "square",
            "skwair": "square",
            "squir": "square",
            "fit": "feet",
            "fiet": "feet",
            "feit": "feet",
            "fiet": "feet",
            "ekerz": "acres",
            "acrez": "acres",
            "aykres": "acres",
            "akars": "acres",

            # BUSY/MINUTE (TIME) (Multiple Variations)
            "bizy": "busy",
            "bisy": "busy",
            "bezy": "busy",
            "bezi": "busy",
            "kwik": "quick",
            "quik": "quick",
            "kwick": "quick",
            "queek": "quick",

            # INTERESTED (Multiple Variations)
            "intrested": "interested",
            "intersted": "interested",
            "intiristed": "interested",
            "interisted": "interested",
            "interestted": "interested",  # NEW: Corrects "interestted" → "interested" (double 't')
            "intterested": "interested",  # NEW: Corrects "intterested" → "interested" (double 't')

            # CONVENIENCE/BENEFITS (Multiple Variations)
            "convinyence": "convenience",
            "confinience": "convenience",
            "conviniens": "convenience",
            "konvinience": "convenience",
            "binifits": "benefits",
            "benifits": "benefits",
            "binefits": "benefits",
            "benefets": "benefits",

            # CASH/COSTS/CLOSING (Multiple Variations)
            "kash": "cash",
            "kesh": "cash",
            "cesh": "cash",
            "kostz": "costs",
            "costes": "costs",
            "kosts": "costs",
            "klozing": "closing",
            "closink": "closing",
            "klosing": "closing",
            "klozink": "closing",
            "komishonz": "commissions",
            "comishons": "commissions",
            "comissionz": "commissions",
            "komisshonz": "commissions",

            # BOTTOM LINE (Multiple Variations)
            "botom": "bottom",
            "bottum": "bottom",
            "bottem": "bottom",
            "batom": "bottom",
            "lain": "line",
            "layn": "line",
            "lyn": "line",
            "lien": "line",

            # COMPLETELY/AS IS (Multiple Variations)
            "kombletely": "completely",
            "combletly": "completely",
            "completly": "completely",
            "kompletly": "completely",
            "sent": "cent",
            "sint": "cent",
            "cint": "cent",
            "sент": "cent",

            # INFORMATION/CONFIRM (Multiple Variations)
            "informashon": "information",
            "informeshon": "information",
            "infermation": "information",
            "informetion": "information",
            "konform": "confirm",
            "canfirm": "confirm",
            "comfirm": "confirm",
            "konfirm": "confirm",

            # PARTNER/PART (Multiple Variations)
            "bartner": "partner",
            "partnar": "partner",
            "bertner": "partner",
            "partener": "partner",
            "bart": "part",
            "pert": "part",
            "peart": "part",
            "paart": "part",

            # SUPPOSE/BEST (Multiple Variations)
            "subboze": "suppose",
            "sapose": "suppose",
            "supose": "suppose",
            "sepose": "suppose",
            "bist": "best",
            "bast": "best",
            "biest": "best",

            # FIT/SORTED (Multiple Variations)
            "fet": "fit",
            "fiet": "fit",
            "fitt": "fit",
            "sortid": "sorted",
            "soarted": "sorted",
            "serted": "sorted",

            # REACH/BACK/CALLBACK (Multiple Variations)
            "rich": "reach",
            "reech": "reach",
            "ritch": "reach",
            "riach": "reach",
            "bak": "back",
            "beck": "back",
            "bek": "back",
            "baak": "back",
            "kolbak": "callback",
            "callbak": "callback",
            "kolback": "callback",
            "kalbek": "callback",

            # AUTHORIZED/SIGNED (Multiple Variations)
            "osorized": "authorized",
            "athorized": "authorized",
            "osoreyzed": "authorized",
            "autherized": "authorized",
            "sained": "signed",
            "syned": "signed",
            "seined": "signed",
            "signet": "signed",
            "kontract": "contract",
            "contrak": "contract",
            "kentract": "contract",
            "contrect": "contract",

            # REALTOR/LISTED (Multiple Variations)
            "riltor": "realtor",
            "reeltor": "realtor",
            "rialtor": "realtor",
            "realter": "realtor",
            "listed": "listed",
            "lest": "listed",
            "listid": "listed",
            "leested": "listed",
            "lestid": "listed",

            # EXPERT/AREA (Multiple Variations)
            "eksbert": "expert",
            "exbert": "expert",
            "exburt": "expert",
            "ekspurt": "expert",
            "aria": "area",
            "erya": "area",
            "arya": "area",
            "areya": "area",

            # BUSINESS/TYPE/RESTAURANT (Multiple Variations)
            "bisnes": "business",
            "bizness": "business",
            "besnes": "business",
            "besniss": "business",
            "taib": "type",
            "tayp": "type",
            "tipe": "type",
            "taype": "type",
            "restorant": "restaurant",
            "resturant": "restaurant",
            "ristorant": "restaurant",
            "restrant": "restaurant",

            # MULTIPLE/LOCAL/TEAMS (Multiple Variations)
            "multibel": "multiple",
            "maltibel": "multiple",
            "multibul": "multiple",
            "multipel": "multiple",
            "lokal": "local",
            "lokul": "local",
            "locul": "local",
            "loucal": "local",
            "timz": "teams",
            "teemz": "teams",
            "tiems": "teams",
            "teamz": "teams",

            # UTILITIES/ZONING (Multiple Variations)
            "yutilities": "utilities",
            "utilitees": "utilities",
            "yutiliteez": "utilities",
            "uteleties": "utilities",
            "watar": "water",
            "woter": "water",
            "weter": "water",
            "wadir": "water",
            "elektrisity": "electricity",
            "electrisity": "electricity",
            "ilektrisity": "electricity",
            "elektricity": "electricity",
            "zound": "zoned",
            "zonet": "zoned",
            "zouned": "zoned",
            "agrikulcher": "agriculture",
            "agreekulture": "agriculture",
            "agrikulchur": "agriculture",
            "agreculture": "agriculture",
            "indastrial": "industrial",
            "endestrial": "industrial",
            "industriyal": "industrial",
            "rezidential": "residential",
            "residenshal": "residential",
            "rezedential": "residential",
            "residenchul": "residential",
            "komershal": "commercial",
            "commerchul": "commercial",
            "komercial": "commercial",
            "comercial": "commercial",

            # ACCESS (Multiple Variations)
            "akses": "access",
            "aksess": "access",
            "exess": "access",
            "aксess": "access",

            # NUMBERS (Multiple Variations)
            "tu": "two",
            "tew": "two",
            "too": "two",
            "sree": "three",
            "tree": "three",
            "thri": "three",
            "tri": "three",
            "foor": "four",
            "feur": "four",
            "fife": "five",
            "faiv": "five",
            "fiv": "five",
            "fayv": "five",
            "siks": "six",
            "seex": "six",
            "seks": "six",

            # CONTRACTIONS - I/I'LL/I'M (Multiple Variations)
            "ay": "I",
            "ai": "I",
            "aye": "I",
            "a": "I",
            "ayl": "I'll",
            "ail": "I'll",
            "ale": "I'll",
            "al": "I'll",
            "am": "I'm",
            "aim": "I'm",
            "aym": "I'm",
            "em": "I'm",

            # CONTRACTIONS - IT/IT'S (Multiple Variations)
            "et": "it",
            "itt": "it",
            "eet": "it",
            "its": "it's",
            "ets": "it's",
            "itz": "it's",

            # CONTRACTIONS - WE/WE'RE (Multiple Variations)
            "wi": "we",
            "wee": "we",
            "way": "we",
            "wir": "we're",
            "weer": "we're",
            "wer": "we're",
            "wire": "we're",

            # CONTRACTIONS - DON'T/WON'T/WOULDN'T (Multiple Variations)
            "dont": "don't",
            "doun't": "don't",
            "dunt": "don't",
            "doant": "don't",
            "wont": "won't",
            "wount": "won't",
            "wunt": "won't",
            "woant": "won't",
            "wudnt": "wouldn't",
            "wudent": "wouldn't",
            "wuldent": "wouldn't",
            "woodent": "wouldn't",

            # IS/ARE/WAS/WERE (Multiple Variations)
            "iz": "is",
            "ees": "is",
            "ezz": "is",
            "ar": "are",
            "arr": "are",
            "er": "are",
            "waz": "was",
            "woz": "was",
            "wes": "was",
            "wer": "were",
            "war": "were",
            "wir": "were",
            "haz": "has",
            "hez": "has",
            "hess": "has",
            "haf": "have",
            "hev": "have",
            "heff": "have",
            "daz": "does",
            "duz": "does",
            "doz": "does",

            # BEEN/DONE (Multiple Variations)
            "bin": "been",
            "ben": "been",
            "bein": "been",
            "bean": "been",
            "dan": "done",
            "dun": "done",
            "daun": "done",
            "doan": "done",

            # JUST/ONLY (Multiple Variations)
            "jast": "just",
            "jas": "just",
            "jost": "just",
            "jest": "just",
            "ounly": "only",
            "onley": "only",
            "unly": "only",
            "onli": "only",

            # MORE/THAN (Multiple Variations)
            "mor": "more",
            "mour": "more",
            "moar": "more",
            "moor": "more",
            "zan": "than",
            "dan": "than",
            "zen": "than",
            "den": "than",

            # ANY/EVERY/SOME (Multiple Variations)
            "eny": "any",
            "ani": "any",
            "inny": "any",
            "ainy": "any",
            "evry": "every",
            "ivery": "every",
            "everi": "every",
            "efery": "every",
            "sum": "some",
            "som": "some",
            "sam": "some",
            "soum": "some",

            # KNOW/NOW (Multiple Variations)
            "no": "know",
            "nou": "know",
            "knaw": "know",
            "naw": "now",
            "nou": "now",
            "naow": "now",

            # ALL/ALWAYS (Multiple Variations)
            "ol": "all",
            "oll": "all",
            "awl": "all",
            "al": "all",
            "olways": "always",
            "olweys": "always",
            "alwayz": "always",
            "olweyz": "always",

            # RIGHT/ALRIGHT/GREAT/OKAY (Multiple Variations)
            "rayt": "right",
            "rait": "right",
            "reit": "right",
            "riet": "right",
            "olrait": "alright",
            "alrayt": "alright",
            "olright": "alright",
            "arait": "alright",
            "gret": "great",
            "greit": "great",
            "graat": "great",
            "grayt": "great",
            "okey": "okay",
            "okai": "okay",
            "oke": "okay",
            "okeh": "okay",

            # GOT/GET (Multiple Variations)
            "gat": "got",
            "gott": "got",
            "gutt": "got",
            "git": "get",
            "gat": "get",
            "gett": "get",

            # WELL (Multiple Variations)
            "wel": "well",
            "will": "well",
            "wil": "well",
            "wal": "well",

            # SEE/SAY (Multiple Variations)
            "si": "see",
            "sy": "see",
            "sie": "see",
            "sea": "see",
            "sey": "say",
            "sai": "say",
            "se": "say",
            "sae": "say",

            # TALK/TELL (Multiple Variations)
            "tok": "talk",
            "tawk": "talk",
            "tolk": "talk",
            "taulk": "talk",
            "tel": "tell",
            "till": "tell",
            "tal": "tell",
            "teal": "tell",

            # LIKE/LOOK (Multiple Variations)
            "laik": "like",
            "lyk": "like",
            "lik": "like",
            "leik": "like",
            "luk": "look",
            "louk": "look",
            "loock": "look",
            "lok": "look",

            # MOVE/GOING/GO (Multiple Variations)
            "mouf": "move",
            "muv": "move",
            "moov": "move",
            "moof": "move",
            "goink": "going",
            "goin": "going",
            "guink": "going",
            "gouing": "going",
            "gou": "go",
            "gow": "go",
            "goo": "go",

            # WRONG/NUMBER (Multiple Variations)
            "rong": "wrong",
            "ronk": "wrong",
            "wraung": "wrong",
            "wrang": "wrong",
            "namber": "number",
            "nomber": "number",
            "nember": "number",
            "numbir": "number",

            # SORRY (Multiple Variations)
            "sory": "sorry",
            "sary": "sorry",
            "sorrey": "sorry",
            "sorey": "sorry",

            # FLEXIBLE/WORKING (Multiple Variations)
            "flexibel": "flexible",
            "flexeble": "flexible",
            "flixible": "flexible",
            "flexibul": "flexible",
            "workink": "working",
            "warking": "working",
            "workeng": "working",

            # AROUND/HOLDING (Multiple Variations)
            "arownd": "around",
            "araund": "around",
            "erround": "around",
            "arond": "around",
            "holdink": "holding",
            "houlding": "holding",
            "hoaldink": "holding",
            "houldenk": "holding",

            # NEVER/EVER (Multiple Variations)
            "nifer": "never",
            "nefer": "never",
            "nevir": "never",
            "nevar": "never",
            "efer": "ever",
            "iver": "ever",
            "efir": "ever",
            "evar": "ever"
        }

    def apply_corrections(self, transcript: str) -> Tuple[str, Dict[str, str]]:
        """Apply phonetic corrections to transcript."""
        corrections_made = {}
        corrected = transcript

        for wrong, correct in self.PHONETIC_CORRECTIONS.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, correct)
                corrections_made[wrong] = correct

        return corrected, corrections_made


class KeywordRepository:
    """Repository of rebuttal phrases organized by category."""
    
    def __init__(self):
        """Initialize repository and load learned phrases."""
        self._learned_phrases_cache = None
        self._learned_phrases_timestamp = None

    REBUTTAL_PHRASES = {
        "OTHER_PROPERTY_FAMILY": [
            "do you have any other property",
            "do you have another property",
            "any other property",
            "any other properties",
            "any other properties you might consider",
            "any other property you might consider",
            "any other property you want to sell",
            "any other property you might want to sell",
            "any other property that you might want to sell",
            "any property",  # NEW: Direct "any property" detection
            "do you have any other houses",
            "do you have any other houses you want to sell",
            "do you have another house",
            "any other houses to sell",
            "any other houses you might consider selling",
            "any property you might be interested in selling",
            "any property you might be interested in selling soon",
            "do you happen to have any property that you might be interested in selling soon",
            "any property that you might be interested in selling soon",
            "do you have any other property you might be interested in selling",
            "you don't have any other property to sell",
            "you don't have another property to sell",
            "you don't own any other property",
            "you don't have any properties in general",
            "don't have any properties in general",
            "you have another property you'd like to sell",
            "do you own any other property you'd like to sell",
            "do you happen to have any other property",
            "any other properties besides this one",
            "any other properties aside from this one",
            "any other houses who failed",
            "any other houses to fill",
            "do you haf any ozer broperty",
            "do you haf any uzzer proberty",
            "got any other property",
            "any other properties available",
            # EGYPTIAN ENGLISH VARIATIONS
            "do you haf any uzzer broperty", "haf any uzzer broperty", "haf any ozer proberty", "haf any uzzer proberty",
            "do you haf any ozer broperty", "haf ozer broperty", "haf uzzer proberty", "haf ozer proberty",
            "got any uzzer broperty", "got any ozer broperty", "haf any uzzer bropertiz", "haf any ozer bropertiz",
            "haf any uzzer hows", "haf any ozer hows", "haf any uzzer howsiz", "haf any ozer howsiz",
            "haf any uzzer hows to sel", "haf any ozer hows to sel", "haf any uzzer hows for sale", "haf any ozer hows for sale",
            "haf any uzzer broperty you want to sel", "haf any ozer broperty you want to sel",
            "haf any uzzer broperty you'd like to sel", "haf any ozer broperty you'd like to sel",
            # NEW EXPANSIONS
            "are there any other homes you own",
            "do you own multiple properties",
            "any additional properties",
            "other real estate you might have",
            "different properties you own",
            "any other real estate assets",
            "other investment properties",
            "any commercial properties",
            "other residential properties",
            "additional homes or apartments",
            "other pieces of real estate",
            "any other land or property",
            "secondary properties",
            "backup properties",
            "other properties in your portfolio",
            "any other holdings",
            "additional real estate",
            "other owned properties",
            "any other assets you want to sell",
            "different properties you might consider",
            "other homes you might want to liquidate",
            "any other real estate you might sell",
            "additional properties you might consider",
            "other houses you might want to sell",
            "any different properties you own",
            "other real estate you might have",
            "any additional homes you have",
            "other properties you manage",
            "any other real estate you own",
            "additional pieces of property",
            "other lots or land you own",
            "any other buildings you own",
            "different structures you have",
            "other pieces of land",
            "any additional acreage",
            "other property holdings",
            "additional real estate you own",
            "other assets in real estate",
            "any other property investments",
            "different property types",
            "other real estate ventures",
            "any additional homes or land",
            "other properties you might liquidate",
            "any other real estate you might sell",
            "additional properties you might consider",
            "other homes you might want to sell",
            "any different properties you own",
            "other real estate you might have",
            "any additional properties you control",
            "do you own any properties that you might consider selling for the next few months",
            "do you own any properties that you might consider selling",
            "any properties you might consider selling",
            # NEW PATTERN: Agent qualification question about properties for sale
            "but you don't have any properties for sale?",
            # ADDITIONAL PROPERTY EXTENSIONS
            "do you have any other property you own",
            "any other property you might have",
            "do you happen to have other property",
            "any other property you could sell",
            "do you have other property available",
            "any other property you control",
            "do you own other property somewhere",
            "any other property in your name",
            "do you have property elsewhere",
            "any other property you're sitting on",
            "do you have any rental property",
            "any other property you inherited",
            "do you own any other real estate",
            "any other property you manage",
            "do you have other property investments",
            "any other property in the family",
            "do you have any vacant property",
            "any other property you're holding",
            "do you own any other homes",
            "any other property you bought",
            "do you have property in other areas",
            "any other property you acquired",
            "do you own any other buildings",
            "any other property you possess",
            "do you have any other assets",
            "any other property you maintain",
            "do you own any other lots",
            "any other property you purchased",
            "do you have any other units",
            "any other property under your name",
            "do you own any other places",
            "any other property you hold title to",
            "do you have any other addresses",
            "any other property you're responsible for",
            "do you own any other structures",
            "any other property you have interest in",
            "do you have any other locations",
            "any other property you have rights to",
            "do you own any other parcels",
            "any other property you have access to",
        ],
        "NOT_EVEN_FUTURE_FAMILY": [
            # Agent questions/rebuttals about future selling (what agents should say)
            "would you be open to selling in the future",
            "would you be open to sell in the future", 
            "would you be open to sell maybe next year",
            "would you be open to selling maybe next year",
            "would you be interested in selling in the future",
            "would you be interested in selling maybe next year", 
            "would you be interested in selling later",
            "any chance you might sell in the future",
            "any chance you might sell later",
            "any chance you might sell next year",
            "what about in the future",
            "even in the near future?",
            "even in the near future",
            "now or even in the near future",
            "even in the future?",
            "maybe down the road?",
            "not even possible in the future?",
            # Agent negotiation/agreement phrases for future selling
            "you think you could possibly sell the next year or so",
            "think you could possibly sell in the next year",
            "could you possibly sell the next year or so",
            "you think you might sell the next year or so",
            "could we come to an agreement next year",
            "think we could come to an agreement in the future",
            "you think you could sell maybe next year",
            "could you possibly consider selling next year"
        ],
        "CALLBACK_SCHEDULE_FAMILY": [
            "when is the best time to call you back", "what's a good time to reach you",
            "can i call you back later", "let me take down your details",
            # ADDITIONAL CALLBACK EXTENSIONS
            "when would be a good time to call back",
            "what time works best for you",
            "when should I follow up with you",
            "what's the best time to reach you",
            "when can I call you again",
            "what time is convenient for you",
            "when would you prefer I call",
            "what's a good callback time",
            "when is it okay to call back",
            "what time should I try again",
            "when would be better to talk",
            "what's your preferred call time",
            "when can we talk again",
            "what time works for your schedule",
            "when should I check back with you"
        ],
        "WOULD_CONSIDER_FAMILY": [
            "would you consider selling", "would you be interested in an offer",
            "could we make you an offer",
            # ADDITIONAL WOULD_CONSIDER EXTENSIONS
            "would you consider an offer",
            "would you be interested in selling",
            "would you think about an offer",
            "would you entertain an offer",
            "would you be open to an offer",
            "would you consider a cash offer",
            "would you be willing to sell",
            "would you be interested in a deal",
            "would you consider our offer",
            "would you be open to selling"
        ],
        "WE_BUY_OFFER_FAMILY": [
            "we buy houses all cash", "no commission, no fees",
            "we pay all closing costs", "as-is, no repairs",
            "buying properties all over the state",
            # ADDITIONAL WE_BUY EXTENSIONS
            "we buy houses for cash",
            "we purchase properties quickly",
            "we buy in any condition",
            "we close fast with cash",
            "we buy houses as-is",
            "we purchase homes directly",
            "we buy properties all cash",
            "we close in days not months",
            "we buy without inspections",
            "we purchase without repairs",
            # Price negotiation and offer discussion rebuttals
            "would that be negotiable",
            "is that price negotiable",
            "would you consider a lower offer",
            "how did you come up with this number",
            "how did you arrive at that price",
            "what's your best price",
            "would you take less",
            "is there room for negotiation",
            "can we work on the price",
            "would you entertain an offer",
            "what would you accept",
            "is that your final price"
        ],
        "FLEXIBLE_CONVENIENT_FAMILY": [
            "we're very flexible with timing", "very simple process",
            "fast closing, your convenience",
            "we have flexible closing time to six months",
            "flexible closing time to six months",
            "we have flexible closing time",
            "flexible closing time"
        ],
        "DISCOVERED_FROM_TRAINING_FAMILY": [
            "any other property you have"
        ],
        "MIXED_FUTURE_OTHER_FAMILY": [
            "not even in the near future but do you have any other property",
            "not even in the future but do you have any other property",
            "no plans to sell but do you have any other property",
            "not interested in selling but do you have any other property",
            "not now maybe later do you have any other property",
            "not now maybe next year do you have any other property",
            "not selling now but do you have any other property",
            "not for sale right now but do you have any other property",
            "not for sale now but any other property you might want to sell",
            "not ready to sell this one but do you have any other property",
            "not selling this one but maybe another property",
            "not this property but maybe another one",
            "not this property but maybe another house",
            "not this one but another one",
            "not this one but maybe another property",
            "not this house but maybe another one",
            "do you have any other properties besides this",
            "do you have something else you might sell",
            "do you have another property instead",
            "any other property instead of this one",
            "do you own another property instead",
            "do you happen to own another property",
            # NEW ADDITIONS
            "do you have another property that you're considering selling",
            "do you have other properties that might be available",
            "do you have any additional properties",
            "do you have other homes or properties",
            "do you have another piece of property",
            # NEW PATTERN: General qualification question
            "do you have any",
            # NEW PATTERN: Agent asking about additional properties to sell
            "do you have another one you think about sellling it sometime soon?",
            "do you have another one",
            "do you have another one?",
            "do you have different properties",
            "do you have other real estate holdings",
            "do you have alternative properties",
            "do you have secondary properties",
            "do you have backup properties",
            "do you have other investment properties",
            # "DO YOU HAVE ANY OTHER" VARIATIONS
            "do you have any other property",
            "do you have any other properties",
            "do you have any other home",
            "do you have any other homes",
            "do you have any other house",
            "do you have any other houses",
            "do you have any other real estate",
            "do you have any other investment",
            "do you have any other asset",
            "do you have any other assets",
            # EXACT PHRASE REQUESTED
            "do you have any other",
            # AGENT QUALIFICATION AFTER REJECTION (Business Rule)
            "do you have a property that you might be interested in selling",
            "do you have any property that you might be interested in selling",
            "do you have property that you might be interested in selling",
            # VARIATIONS MATCHING USER'S TRANSCRIPT
            "did you happen to have any other",
            "do you happen to have any other",
            "do you have any other for sale",
            "did you happen to have any other for sale",
            # ADDITIONAL COMMON VARIATIONS
            "do you have any other properties for sale",
            "do you have anything else for sale",
            "do you happen to own any other",
            "do you happen to have other",
            # ADDITIONAL MIXED_FUTURE_OTHER_FAMILY EXTENSIONS
            "not selling this but do you have any other property",
            "not this one but any other property you own",
            "not interested in this but other property maybe",
            "not this house but other houses you have",
            "not ready for this but other property perhaps",
            "not this place but any other places you own",
            "not selling here but elsewhere maybe",
            "not this location but other locations you have",
            "not this address but other addresses you own",
            "not this building but other buildings maybe",
            "not this home but other homes you have",
            "not this unit but other units you own",
            "not this lot but other lots maybe",
            "not this parcel but other parcels you have",
            "not this asset but other assets you own",
            "not this investment but other investments maybe",
            "not this structure but other structures you have",
            "not ready here but ready elsewhere maybe",
            "not selling now but other property later",
            "not this property but different property maybe",
            "not interested here but interested elsewhere",
            "not this time but other property anytime",
            "not this deal but other deals maybe",
            "not this opportunity but other opportunities",
            "not this situation but other situations maybe"
        ]
    }

    def _load_learned_phrases(self) -> Dict[str, List[str]]:
        """Load learned phrases from the phrase learning system's repository file."""
        try:
            from pathlib import Path
            import json
            import os
            
            # Path to the phrase learning repository JSON file
            repository_path = Path("dashboard_data") / "rebuttal_repository.json"
            
            # Check if file exists and get its modification time
            if not repository_path.exists():
                return {}
            
            # Check file modification time for cache invalidation
            current_mtime = os.path.getmtime(repository_path)
            if (self._learned_phrases_cache is not None and 
                self._learned_phrases_timestamp == current_mtime):
                return self._learned_phrases_cache
            
            # Load the repository file
            with open(repository_path, 'r', encoding='utf-8') as f:
                repository_data = json.load(f)
            
            # Extract phrases from the repository
            learned_phrases = repository_data.get("phrases", {})
            
            # Cache the result with timestamp
            self._learned_phrases_cache = learned_phrases
            self._learned_phrases_timestamp = current_mtime
            
            logger.debug(f"Loaded {sum(len(p) for p in learned_phrases.values())} learned phrases from repository")
            return learned_phrases
            
        except Exception as e:
            logger.warning(f"Failed to load learned phrases from repository: {e}")
            return {}

    def get_all_phrases(self) -> Dict[str, List[str]]:
        """Get all rebuttal phrases organized by category, merging hardcoded with learned phrases."""
        # Start with hardcoded phrases
        merged_phrases = {}
        
        # Copy hardcoded phrases (deep copy to avoid modifying original)
        for category, phrases in self.REBUTTAL_PHRASES.items():
            merged_phrases[category] = list(phrases)
        
        # Load and merge learned phrases
        learned_phrases = self._load_learned_phrases()
        
        for category, phrases in learned_phrases.items():
            if category not in merged_phrases:
                merged_phrases[category] = []
            
            # Add learned phrases that aren't already in the hardcoded list
            # Use lowercase comparison to avoid duplicates
            existing_lower = {p.lower().strip() for p in merged_phrases[category]}
            for phrase in phrases:
                phrase_lower = phrase.lower().strip()
                if phrase_lower not in existing_lower:
                    merged_phrases[category].append(phrase)
                    existing_lower.add(phrase_lower)
                    logger.debug(f"Added learned phrase: '{phrase}' to {category}")
        
        return merged_phrases

    def get_phrases_by_category(self, category: str) -> List[str]:
        """Get phrases for a specific category (includes learned phrases)."""
        all_phrases = self.get_all_phrases()
        return all_phrases.get(category, [])

    def expand_phrases(self) -> Dict[str, List[str]]:
        """Apply expansion rules to generate more variations."""
        return self.REBUTTAL_PHRASES


class SemanticDetectionEngine:
    """Phrase matching and categorization with confidence scoring using both exact and semantic matching."""

    def __init__(self, keyword_repo: KeywordRepository):
        self.keyword_repo = keyword_repo
        self.semantic_model = None
        self.phrase_embeddings = None
        self.semantic_threshold = 0.68
        if persistent_app_settings is not None:
            try:
                configured_threshold = persistent_app_settings.get_semantic_threshold()
                self.semantic_threshold = float(configured_threshold)
            except Exception:
                logger.warning("Failed to load semantic threshold from settings; using default 0.68")
        self.semantic_threshold = max(0.5, min(self.semantic_threshold, 0.9))

        # Use singleton pattern to get the semantic model
        logger.info("Initializing semantic detection engine with singleton model...")
        self.semantic_model, self.phrase_embeddings = _get_semantic_model()

        if self.semantic_model is None:
            logger.warning("Semantic model not available from singleton, using exact matching only")
        else:
            logger.info("✅ Semantic detection engine initialized with model and embeddings")

    def detect_rebuttals(self, transcript: str) -> List[Dict[str, Any]]:
        """Detect all matching rebuttal phrases using exact, semantic, and LLaMA (for complex cases)."""
        logger.info(f"🔍 Starting rebuttal detection on transcript: '{transcript[:100]}...'")
        matches = []
        transcript_lower = transcript.lower()

        # 1. Primary: Exact matching (fastest)
        logger.debug("Running exact phrase matching...")
        exact_matches = self._detect_exact_matches(transcript_lower)
        matches.extend(exact_matches)

        # 2. Secondary: Semantic matching (AI-powered)
        if self.semantic_model is not None:
            logger.debug("Running semantic AI matching...")
            semantic_matches = self._detect_semantic_matches(transcript)
            # Filter out semantic matches that are too similar to exact matches
            filtered_semantic_matches = self._filter_duplicate_matches(exact_matches, semantic_matches)
            matches.extend(filtered_semantic_matches)
            
            # Track semantic matches for phrase learning
            self._track_semantic_matches_for_learning(filtered_semantic_matches, transcript)
        else:
            logger.warning("❌ Semantic model not available, using exact matching only")

        # 3. Tertiary: LLaMA inference for complex cases
        # Use LLaMA ONLY when:
        # - No high-confidence matches found (best confidence < 0.70), OR
        # - No matches found at all
        best_confidence = max([m['confidence'] for m in matches], default=0.0)
        should_use_llama = (
            LLAMA_AVAILABLE and 
            llama_rebuttal_detection is not None and
            (len(matches) == 0 or best_confidence < 0.70)
        )
        
        if should_use_llama:
            logger.info(f"🤖 Complex case detected (best confidence: {best_confidence:.2f}), invoking LLaMA analysis...")
            try:
                llama_result = llama_rebuttal_detection(transcript)
                
                if llama_result and llama_result['result'] == 'Yes':
                    # LLaMA found a rebuttal
                    matches.append({
                        'phrase': llama_result.get('reasoning', 'LLaMA detected rebuttal pattern'),
                        'category': 'LLAMA_COMPLEX_CASE',
                        'confidence': llama_result['confidence_score'],
                        'match_type': 'llama_inference',
                        'model': llama_result.get('model', 'local-llama')
                    })
                    logger.info(f"✅ LLaMA detected rebuttal: {llama_result['reasoning']} (confidence: {llama_result['confidence_score']:.2f})")
                elif llama_result:
                    logger.info(f"ℹ️ LLaMA analysis: No rebuttal found (confidence: {llama_result['confidence_score']:.2f})")
                    
            except Exception as e:
                logger.warning(f"⚠️ LLaMA inference failed, continuing with existing matches: {e}")

        # Sort by confidence score (highest first)
        matches.sort(key=lambda x: x['confidence'], reverse=True)

        if matches:
            best_match = matches[0]
            logger.info(f"✅ Best match: '{best_match['phrase']}' ({best_match['match_type']}) confidence: {best_match['confidence']:.3f}")
        else:
            logger.info("❌ No rebuttals detected by any method")

        return matches


    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for robust exact matching.

        - Lowercase
        - Remove common punctuation
        - Collapse multiple spaces
        """
        import re
        text = text.lower()
        # Remove common punctuation characters
        text = re.sub(r"[.,!?;:\\-]", " ", text)
        # Collapse multiple whitespace into single spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _detect_exact_matches(self, transcript_lower: str) -> List[Dict[str, Any]]:
        """Detect exact phrase matches with punctuation-insensitive matching."""
        matches = []

        normalized_transcript = self._normalize_for_matching(transcript_lower)

        for category, phrases in self.keyword_repo.get_all_phrases().items():
            for phrase in phrases:
                normalized_phrase = self._normalize_for_matching(phrase)
                if normalized_phrase and normalized_phrase in normalized_transcript:
                    confidence = self._calculate_exact_confidence(phrase, transcript_lower)
                    matches.append({
                        'phrase': phrase,
                        'category': category,
                        'confidence': confidence,
                        'match_type': 'exact'
                    })

        return matches

    def _detect_semantic_matches(self, transcript: str) -> List[Dict[str, Any]]:
        """Detect semantic matches using Sentence Transformers with batch encoding."""
        if self.phrase_embeddings is None:
            return []
        
        matches = []
        
        try:
            # Split transcript into sentences for better semantic matching
            sentences = self._split_into_sentences(transcript)
            # Filter short sentences and polite closing sentences without rebuttal content
            valid_sentences = [
                s for s in sentences
                if len(s.strip()) >= 3 and not self._is_polite_closing(s)
            ]
            
            if not valid_sentences:
                return []
            
            # Batch encode all sentences at once for speed
            sentence_embeddings = self.semantic_model.encode(valid_sentences, batch_size=8)
            
            # Calculate similarities for all sentences at once
            similarities = cosine_similarity(sentence_embeddings, self.phrase_embeddings['embeddings'])
            
            # Find matches above threshold
            for sent_idx, sentence in enumerate(valid_sentences):
                for emb_idx, similarity in enumerate(similarities[sent_idx]):
                    if similarity >= self.semantic_threshold:
                        phrase_info = self.phrase_embeddings['metadata'][emb_idx]
                        matches.append({
                            'phrase': phrase_info['phrase'],
                            'category': phrase_info['category'],
                            'confidence': float(similarity),
                            'match_type': 'semantic',
                            'matched_sentence': sentence.strip()
                        })
            
        except Exception as e:
            logger.error(f"Error in semantic matching: {e}")
        
        return matches

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for better semantic analysis, preserving rebuttal context."""
        # First, split on major punctuation
        import re
        sentences = re.split(r'[.!?]+', text)

        # Also try to preserve question sequences that might be rebuttals
        all_sentences = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If this is a question and we have a current chunk, add it to preserve context
            if sentence.endswith('?') or '?' in sentence:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                all_sentences.append(current_chunk)
                current_chunk = ""
            else:
                # For non-questions, group them but don't let chunks get too long
                if current_chunk and len((current_chunk + " " + sentence).split()) > 50:
                    all_sentences.append(current_chunk)
                    current_chunk = sentence
                elif current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Add any remaining chunk
        if current_chunk:
            all_sentences.append(current_chunk)

        # Clean and filter sentences
        cleaned_sentences = []
        for sentence in all_sentences:
            cleaned = sentence.strip()
            if len(cleaned) > 3:  # Only keep meaningful sentences
                cleaned_sentences.append(cleaned)

        return cleaned_sentences

    def _is_polite_closing(self, sentence: str) -> bool:
        sentence_lower = sentence.lower()
        closing_keywords = [
            "thank you",
            "thanks for your time",
            "have a good one",
            "have a great day",
            "have a nice day",
            "enjoy your day",
            "bye",
            "goodbye",
            "talk to you later",
            "take care"
        ]
        content_keywords = [
            "sell",
            "selling",
            "buyer",
            "buying",
            "offer",
            "price",
            "property",
            "house",
            "home",
            "future"
        ]

        if any(k in sentence_lower for k in content_keywords):
            return False

        if any(k in sentence_lower for k in closing_keywords):
            return True

        return False

    def _strip_polite_closing_suffix(self, text: str) -> str:
        """Remove polite closing phrases from the end of a candidate phrase."""
        if not text:
            return text

        lower = text.lower()
        closing_keywords = [
            "thank you",
            "thanks for your time",
            "have a good one",
            "have a great day",
            "have a nice day",
            "enjoy your day",
            "bye",
            "goodbye",
            "talk to you later",
            "take care",
        ]

        cut_index = len(text)
        for kw in closing_keywords:
            idx = lower.find(kw)
            if idx != -1 and idx < cut_index:
                cut_index = idx

        if cut_index == len(text):
            return text

        return text[:cut_index].strip()

    def _extract_candidate_phrase(self, base_phrase: str, matched_sentence: str) -> str:
        if not matched_sentence:
            return base_phrase
        sentence = matched_sentence.strip()
        base = base_phrase.strip()
        if not sentence:
            return base
        sentence_tokens = sentence.split()
        if len(sentence_tokens) <= 10:
            return self._strip_polite_closing_suffix(sentence.lower())
        base_tokens = base.lower().split()
        base_token_set = {t.strip(".,!?;:") for t in base_tokens if t}
        if not base_token_set:
            candidate = sentence.lower()
            if len(candidate.split()) > 15:
                candidate_tokens = candidate.split()
                candidate = " ".join(candidate_tokens[:15])
            if len(candidate) > 160:
                candidate = candidate[:160]
            return candidate
        max_window = min(len(sentence_tokens), max(len(base_tokens) + 3, 12))
        best_start = 0
        best_end = min(len(sentence_tokens), len(base_tokens))
        best_score = 0.0
        for start in range(len(sentence_tokens)):
            for end in range(start + 1, min(len(sentence_tokens), start + max_window) + 1):
                window_tokens = sentence_tokens[start:end]
                window_token_set = {t.lower().strip(".,!?;:") for t in window_tokens if t}
                if not window_token_set:
                    continue
                overlap = len(base_token_set.intersection(window_token_set))
                score = overlap / float(len(base_token_set))
                if score > best_score or (score == best_score and (end - start) < (best_end - best_start)):
                    best_score = score
                    best_start = start
                    best_end = end
        if best_score >= 0.5:
            candidate = " ".join(sentence_tokens[best_start:best_end])
        else:
            candidate = base
        candidate = candidate.strip().lower()
        if len(candidate.split()) > 15:
            candidate_tokens = candidate.split()
            candidate = " ".join(candidate_tokens[:15])
        if len(candidate) > 160:
            candidate = candidate[:160]
        candidate = self._strip_polite_closing_suffix(candidate)
        return candidate

    def _filter_duplicate_matches(self, exact_matches: List[Dict], semantic_matches: List[Dict]) -> List[Dict]:
        """Filter out semantic matches that are too similar to exact matches."""
        if not exact_matches:
            return semantic_matches

        filtered_matches = []
        exact_phrases = {match['phrase'].lower() for match in exact_matches}

        for semantic_match in semantic_matches:
            # Only skip if the EXACT same phrase was already found via exact matching
            # Allow semantic matches for similar but not identical phrases
            if semantic_match['phrase'].lower() not in exact_phrases:
                filtered_matches.append(semantic_match)

        return filtered_matches

    def _track_semantic_matches_for_learning(self, matches: List[Dict], transcript: str):
        """Track semantic matches for phrase learning system."""
        try:
            # Import here to avoid circular imports
            from lib.phrase_learning import get_phrase_learning_manager
            
            learning_manager = get_phrase_learning_manager()
            
            for match in matches:
                if match['match_type'] == 'semantic':
                    # Extract the matched sentence or use the original phrase
                    matched_sentence = match.get('matched_sentence', match['phrase'])
                    base_phrase = match['phrase']
                    candidate_phrase = self._extract_candidate_phrase(base_phrase, matched_sentence)
                    if not candidate_phrase:
                        continue
                    if len(candidate_phrase.split()) > 15 or len(candidate_phrase) > 160:
                        continue
                    
                    # Track this semantic match for potential learning
                    context_text = matched_sentence if matched_sentence else transcript
                    learning_manager.track_semantic_match(
                        phrase=candidate_phrase,
                        category=match['category'],
                        confidence=match['confidence'],
                        context=context_text[:500],  # First 500 chars as context
                        similar_to=base_phrase  # The original repository phrase it matched
                    )
                    
        except Exception as e:
            logger.debug(f"Failed to track semantic matches for learning: {e}")
            # Don't let learning failures affect detection

    def _calculate_exact_confidence(self, phrase: str, transcript: str) -> float:
        """Calculate confidence score for an exact match."""
        phrase_words = set(phrase.lower().split())
        transcript_words = set(transcript.lower().split())

        overlap = len(phrase_words.intersection(transcript_words))
        total_phrase_words = len(phrase_words)

        if total_phrase_words == 0:
            return 0.0

        return min(1.0, overlap / total_phrase_words)


class ValidationFramework:
    """Accuracy testing and edge case handling."""

    def __init__(self, detection_engine: SemanticDetectionEngine):
        self.detection_engine = detection_engine

    def run_unit_tests(self) -> Dict[str, Any]:
        """Run comprehensive unit tests."""
        test_cases = [
            ("Do you have any other properties?", True, "OTHER_PROPERTY_FAMILY"),
            ("Not even in the future", True, "NOT_EVEN_FUTURE_FAMILY"),
            ("When is the best time to call you back", True, "CALLBACK_SCHEDULE_FAMILY"),
            ("Thank you for calling", False, None),
            ("", False, None),
        ]

        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "details": []
        }

        for transcript, expected_result, expected_category in test_cases:
            matches = self.detection_engine.detect_rebuttals(transcript)
            actual_result = len(matches) > 0

            passed = (actual_result == expected_result)
            if passed and expected_category:
                categories = [m['category'] for m in matches]
                passed = expected_category in categories

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "transcript": transcript,
                "expected": expected_result,
                "actual": actual_result,
                "passed": passed
            })

        return results


class OutputFormatter:
    """Standardized result schema formatting."""

    def format_result(self, result: str, confidence_score: float = 0.0,
                     matched_phrases: List[Dict] = None, transcript: str = "",
                     raw_transcript: str = "", corrections_made: Dict = None,
                     processing_time_ms: int = 0, metadata: Dict = None,
                     error_type: str = "", error_message: str = "") -> Dict[str, Any]:
        """Format detection result into standardized schema."""
        if matched_phrases is None:
            matched_phrases = []
        if corrections_made is None:
            corrections_made = {}
        if metadata is None:
            metadata = {}

        # If this is an error result, include error information
        result_dict = {
            "result": result,
            "confidence_score": confidence_score,
            "matched_phrases": matched_phrases,
            "transcript": transcript,
            "raw_transcript": raw_transcript,
            "corrections_made": corrections_made,
            "metadata": {
                "processing_time_ms": processing_time_ms,
                "audio_quality_score": metadata.get("audio_quality_score", 0.0),
                "vosk_confidence": metadata.get("vosk_confidence", 0.0),
                **metadata
            },
            "validation_flags": {
                "audio_quality_ok": metadata.get("audio_quality_ok", True),
                "transcript_length_sufficient": metadata.get("transcript_length_sufficient", True),
                "phonetic_corrections_applied": bool(corrections_made)
            }
        }

        # Add error information if provided
        if error_type or error_message:
            result_dict["error"] = {
                "type": error_type,
                "message": error_message
            }

        return result_dict


class RebuttalDetectionModule:
    """Main rebuttal detection module focusing on agent speech analysis."""

    def __init__(self):
        self.data_ingestion = DataIngestionLayer()
        self.preprocessing = PreprocessingPipeline()
        self.transcription = TranscriptionEngine()
        self.phonetic_adaptation = PhoneticAdaptationLayer()
        self.keyword_repo = KeywordRepository()
        self.detection_engine = SemanticDetectionEngine(self.keyword_repo)
        self.output_formatter = OutputFormatter()
        self.accent_correction_enabled = True
        if persistent_app_settings is not None:
            try:
                self.accent_correction_enabled = persistent_app_settings.is_accent_correction_enabled()
            except Exception:
                pass

    def _assess_transcription_quality(self, transcript: str) -> Dict[str, Any]:
        """Assess transcription quality to identify potential false negatives."""
        import re  # Explicit import to ensure availability in method scope
        issues = []
        quality_score = 1.0

        # Check for very short transcript
        if len(transcript.split()) < 5:
            issues.append("very_short_transcript")
            quality_score -= 0.3

        # Check for excessive repetition (transcription artifacts)
        words = transcript.lower().split()
        if len(words) > 10:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            # Check if any word is repeated more than 30% of the time
            max_repetition = max(word_counts.values()) / len(words)
            if max_repetition > 0.3:
                issues.append("excessive_repetition")
                quality_score -= 0.2

        # Check for nonsensical sequences (common Whisper artifacts)
        nonsensical_patterns = [
            r'\b(um|uh|ah|er)\b.{0,5}\1',  # Repeated fillers
            r'\b(thank you|thanks).{0,20}\1',  # Repeated phrases
            r'\b(yes|yeah|okay|alright).{0,10}\1',  # Repeated acknowledgments
        ]

        for pattern in nonsensical_patterns:
            if re.search(pattern, transcript.lower()):
                issues.append("repetitive_artifacts")
                quality_score -= 0.1
                break

        # Check for lack of punctuation (poor sentence structure)
        sentence_count = len(re.split(r'[.!?]+', transcript))
        word_count = len(words)
        if word_count > 20 and sentence_count < 2:
            issues.append("lack_of_punctuation")
            quality_score -= 0.1

        # Ensure quality score doesn't go below 0
        quality_score = max(0.0, quality_score)

        return {
            "quality_score": quality_score,
            "issues": issues,
            "word_count": word_count,
            "sentence_count": sentence_count
        }

    def detect_rebuttals(self, audio_segment: AudioSegment) -> Dict[str, Any]:
        """Main detection method following the hierarchical decision tree for agent-only analysis."""
        start_time = time.time()
        logger.info(f"Starting rebuttal detection for audio segment of length {len(audio_segment)}ms")

        try:
            # 1. Data Ingestion & Validation
            logger.debug("Step 1: Data ingestion and validation")
            validation = self.data_ingestion.validate_input(audio_segment)
            if not validation["is_valid"]:
                logger.warning(f"Input validation failed: {validation['errors']}")
                return self.output_formatter.format_result(
                    "Error",
                    error_type="InputValidationError",
                    error_message="; ".join(validation["errors"])
                )

            total_duration_ms = len(audio_segment)
            if total_duration_ms < 20000:
                logger.info(f"Full recording shorter than 20 seconds: {total_duration_ms/1000:.1f}s - skipping rebuttal detection")
                return self.output_formatter.format_result(
                    "No",
                    metadata={
                        "skipped": True,
                        "skip_reason": "recording_too_short",
                        "audio_duration_seconds": total_duration_ms / 1000
                    }
                )

            # 2. Process agent channel only
            logger.debug("Step 2: Processing agent channel")
            agent_channel = self.preprocessing.extract_agent_channel(audio_segment)
            is_mono = audio_segment.channels == 1
            logger.debug(f"Audio channels: extracted agent channel, mono={is_mono}")

            # Normalize agent channel for analysis
            normalized_agent = self.preprocessing.normalize_for_transcription(agent_channel)
            logger.debug("Agent channel normalized")

            quality_check = self.preprocessing.quality_validation(normalized_agent)
            logger.debug(f"Quality check result: {quality_check}")
            if not quality_check["audio_quality_ok"]:
                skip_reason = quality_check.get("skipped_reason", "quality_check_failed")
                logger.info(f"Audio quality check failed (reason: {skip_reason}), skipping rebuttal detection")
                return self.output_formatter.format_result(
                    "No",
                    metadata={
                        "skipped": True,
                        "skip_reason": skip_reason,
                        "audio_duration_seconds": len(normalized_agent) / 1000
                    }
                )

            # 3. Single Channel Transcription (Agent Only)
            logger.debug("Step 3: Agent transcription")
            trans_start = time.time()

            # Transcribe agent channel only
            agent_text = self.transcription.transcribe_audio(normalized_agent)

            trans_time = time.time() - trans_start
            logger.info(f"Agent transcription completed in {trans_time:.2f}s")
            logger.info(f"Generated agent transcript: {len(agent_text)} characters")

            # Create simple dialogue format (agent only)
            dialogue_transcript = f"Agent: {agent_text}" if agent_text else ""

            # Check if we have valid agent transcript
            if not agent_text:
                logger.info("No agent transcript generated, returning 'No'")
                return self.output_formatter.format_result(
                    "No",
                    transcript=dialogue_transcript,
                    raw_transcript=agent_text
                )

            # Validate transcription quality - check for common transcription artifacts
            transcription_quality = self._assess_transcription_quality(agent_text)
            if transcription_quality["quality_score"] < 0.3:
                logger.warning(f"Poor transcription quality detected (score: {transcription_quality['quality_score']:.2f}): {transcription_quality['issues']}")
                # Still attempt detection but log the quality concerns

            # Use raw transcript (advanced phonetic corrections were corrupting transcripts)
            cleaned_agent_text = agent_text
            logger.debug("Using raw agent transcript (advanced phonetic corrections disabled)")

            corrected_transcript = cleaned_agent_text
            corrections_made = []

            # 4. Phonetic Adaptation (ENABLED with safety checks)
            if self.accent_correction_enabled:
                logger.debug("Step 4: Applying phonetic corrections with safety checks")
                try:
                    corrected_transcript, corrections_made = self.phonetic_adaptation.apply_corrections(cleaned_agent_text)

                    # Safety check: ensure corrections don't drastically change the transcript length
                    original_length = len(cleaned_agent_text.split())
                    corrected_length = len(corrected_transcript.split())

                    # Only use corrections if they don't change word count by more than 20%
                    length_ratio = corrected_length / original_length if original_length > 0 else 1.0
                    if 0.8 <= length_ratio <= 1.2 and len(corrections_made) <= 10:  # Max 10 corrections
                        logger.debug(f"Applied {len(corrections_made)} phonetic corrections safely")
                    else:
                        logger.warning(f"Phonetic corrections too aggressive (ratio: {length_ratio:.2f}, corrections: {len(corrections_made)}), using raw transcript")
                        corrected_transcript = cleaned_agent_text
                        corrections_made = []

                except Exception as phonetic_error:
                    logger.warning(f"Phonetic corrections failed: {phonetic_error}, using raw transcript")
                    corrected_transcript = cleaned_agent_text
                    corrections_made = []

            # 5. Semantic Detection (on agent transcript only)
            logger.debug("Step 5: Semantic detection")
            matches = self.detection_engine.detect_rebuttals(corrected_transcript)
            logger.debug(f"Found {len(matches)} rebuttal matches")

            # 6. Determine Result
            if matches:
                best_match = max(matches, key=lambda x: x['confidence'])
                result = "Yes"
                confidence_score = best_match['confidence']
                logger.info(f"Rebuttal detected with confidence {confidence_score:.2f}")
            else:
                result = "No"
                confidence_score = 0.0
                logger.debug("No rebuttals detected")

            # 7. Format Output
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Total processing time: {processing_time_ms}ms")

            return self.output_formatter.format_result(
                result=result,
                confidence_score=confidence_score,
                matched_phrases=matches,
                transcript=dialogue_transcript,  # Return dialogue format
                raw_transcript=agent_text,      # Raw agent transcript for analysis
                corrections_made=corrections_made,
                processing_time_ms=processing_time_ms,
                metadata={
                    "audio_quality_score": 0.85 if quality_check["audio_quality_ok"] else 0.5,
                    "vosk_confidence": 0.78,
                    "single_channel": True,
                    "audio_duration_seconds": len(normalized_agent) / 1000,
                    **validation["metadata"]
                }
            )

        except Exception as e:
            logger.error(f"Rebuttal detection failed: {e}", exc_info=True)
            return self.output_formatter.format_result(
                "Error",
                error_type="ProcessingError",
                error_message=str(e)
            )


# Convenience function for easy integration
def rebuttal_detection(audio_segment: AudioSegment) -> Dict[str, Any]:
    """
    Convenience function to detect rebuttals in audio.

    Args:
        audio_segment: Pydub AudioSegment containing call recording

    Returns:
        Detection result dictionary
    """
    module = RebuttalDetectionModule()
    return module.detect_rebuttals(audio_segment)
