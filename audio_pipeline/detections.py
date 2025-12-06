"""
Unified detection module for audio pipeline.
Combines voice activity detection, releasing/late hello logic, debug helpers,
and the introduction classifier.
"""

import logging
import re
from typing import Dict

import numpy as np
from pydub import AudioSegment
from thefuzz import fuzz

from config import app_settings
from scipy import signal
from scipy.fft import rfft, rfftfreq

logger = logging.getLogger(__name__)

# VAD Constants
ADAPTIVE_NOISE_MARGIN = 0.3  # 30% above noise floor
MIN_THRESHOLD_RATIO = 0.7    # At least 70% of config threshold

# Speech Detection Constants
ZCR_MIN = 0.01               # Minimum zero-crossing rate for speech
ZCR_MAX = 0.3                # Maximum zero-crossing rate for speech
SPEECH_FREQ_MIN = 300        # Minimum speech frequency (Hz)
SPEECH_FREQ_MAX = 3500       # Maximum speech frequency (Hz)
SPEECH_BANDWIDTH_MIN = 200   # Minimum bandwidth for speech (not pure tone)
SPEECH_ROLLOFF_MAX = 4000    # Maximum rolloff frequency (Hz)
MIN_SPECTRAL_CHECKS = 2      # Minimum spectral features required


def extract_left_channel(audio_segment):
    """
    Extract left channel (agent) from stereo audio.
    If mono, return the original segment.
    """
    if audio_segment.channels == 2:
        left_channel = audio_segment.split_to_mono()[0]
        return left_channel
    return audio_segment


def estimate_noise_floor(audio_array, frame_rate, percentile=10):
    """
    Estimate adaptive noise floor from audio signal.
    Uses the lower percentile of frame energies to determine baseline noise.
    """
    frame_length = int(0.05 * frame_rate)  # 50ms frames
    hop_length = int(0.025 * frame_rate)   # 25ms hop

    frame_energies = []
    for i in range(0, len(audio_array) - frame_length, hop_length):
        frame = audio_array[i:i + frame_length]
        rms = np.sqrt(np.mean(frame**2)) * 32767
        frame_energies.append(rms)

    if len(frame_energies) == 0:
        return 0

    return np.percentile(frame_energies, percentile)


def calculate_spectral_features(frame, frame_rate):
    """
    Calculate spectral features to distinguish speech from noise.
    """
    try:
        fft_vals = np.abs(rfft(frame))
        fft_freqs = rfftfreq(len(frame), 1.0 / frame_rate)

        if np.sum(fft_vals) == 0:
            return {'centroid': 0, 'bandwidth': 0, 'rolloff': 0}

        centroid = np.sum(fft_freqs * fft_vals) / np.sum(fft_vals)
        bandwidth = np.sqrt(np.sum(((fft_freqs - centroid) ** 2) * fft_vals) / np.sum(fft_vals))
        cumsum = np.cumsum(fft_vals)
        rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0]
        rolloff = fft_freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

        return {'centroid': centroid, 'bandwidth': bandwidth, 'rolloff': rolloff}
    except Exception as e:
        logger.debug(f"Spectral feature calculation failed: {e}")
        return {'centroid': 0, 'bandwidth': 0, 'rolloff': 0}


def voice_activity_detection(audio_segment, energy_threshold=None, min_speech_duration=None, use_adaptive=True):
    """
    Enhanced Voice Activity Detection (VAD) with adaptive noise floor and spectral analysis.
    """
    energy_threshold = energy_threshold or app_settings.vad_energy_threshold
    min_speech_duration = min_speech_duration or app_settings.vad_min_speech_duration

    try:
        try:
            audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
        except Exception as array_error:
            logger.warning(f"Failed to convert audio to array: {array_error}")
            return simple_energy_vad(audio_segment, energy_threshold)

        if len(audio_array) == 0:
            return []

        max_val = np.max(np.abs(audio_array))
        if max_val == 0:
            return []
        audio_array = audio_array / max_val

        if use_adaptive:
            noise_floor = estimate_noise_floor(audio_array, audio_segment.frame_rate)
            adaptive_threshold = noise_floor + (energy_threshold * ADAPTIVE_NOISE_MARGIN)
            effective_threshold = max(adaptive_threshold, energy_threshold * MIN_THRESHOLD_RATIO)
        else:
            effective_threshold = energy_threshold

        frame_length = int(0.05 * audio_segment.frame_rate)
        hop_length = int(0.025 * audio_segment.frame_rate)

        speech_frames = []
        for i in range(0, len(audio_array) - frame_length, hop_length):
            frame = audio_array[i:i + frame_length]
            rms_energy = np.sqrt(np.mean(frame**2)) * 32767
            zcr = np.sum(np.diff(np.sign(frame)) != 0) / len(frame)
            spectral = calculate_spectral_features(frame, audio_segment.frame_rate)

            energy_check = rms_energy > effective_threshold
            zcr_check = ZCR_MIN < zcr < ZCR_MAX
            centroid_check = SPEECH_FREQ_MIN < spectral['centroid'] < SPEECH_FREQ_MAX
            bandwidth_check = spectral['bandwidth'] > SPEECH_BANDWIDTH_MIN
            rolloff_check = spectral['rolloff'] < SPEECH_ROLLOFF_MAX
            spectral_score = sum([centroid_check, bandwidth_check, rolloff_check])

            is_speech = energy_check and zcr_check and spectral_score >= MIN_SPECTRAL_CHECKS
            speech_frames.append(is_speech)

        speech_segments = []
        in_speech = False
        speech_start = 0

        for i, is_speech in enumerate(speech_frames):
            time_ms = i * hop_length / audio_segment.frame_rate * 1000

            if is_speech and not in_speech:
                speech_start = time_ms
                in_speech = True
            elif not is_speech and in_speech:
                speech_duration = time_ms - speech_start
                if speech_duration >= min_speech_duration:
                    speech_segments.append((speech_start, time_ms))
                in_speech = False

        if in_speech:
            final_time = len(audio_array) / audio_segment.frame_rate * 1000
            speech_duration = final_time - speech_start
            if speech_duration >= min_speech_duration:
                speech_segments.append((speech_start, final_time))

        return speech_segments

    except Exception:
        return simple_energy_vad(audio_segment, energy_threshold)


def simple_energy_vad(audio_segment, energy_threshold=None):
    """
    Fallback VAD using simple energy thresholding.
    """
    if energy_threshold is None:
        energy_threshold = app_settings.vad_energy_threshold
    try:
        from pydub.silence import detect_nonsilent

        speech_segments = detect_nonsilent(
            audio_segment,
            min_silence_len=200,
            silence_thresh=-40
        )

        return [
            (start, end) for start, end in speech_segments
            if (end - start) >= 100
        ]
    except Exception as e:
        logger.warning(f"Fallback VAD failed: {str(e)}")
        return []


def releasing_detection(agent_segment):
    """
    Returns 'Yes' if agent channel contains no speech events for entire call duration.
    """
    agent_channel = extract_left_channel(agent_segment)
    call_duration_s = len(agent_channel) / 1000.0
    min_duration = app_settings.late_hello_time

    if call_duration_s < min_duration:
        return "No"

    speech_segments = voice_activity_detection(
        agent_channel,
        energy_threshold=app_settings.vad_energy_threshold,
        min_speech_duration=app_settings.vad_min_speech_duration,
        use_adaptive=True
    )

    return "Yes" if len(speech_segments) == 0 else "No"


def late_hello_detection(agent_segment, customer_segment=None, debug=False):
    """
    Returns 'Yes' if first speech onset in agent channel occurs after 5.0 seconds from call start.
    """
    agent_channel = extract_left_channel(agent_segment)
    speech_segments = voice_activity_detection(
        agent_channel,
        energy_threshold=400,
        min_speech_duration=50,
        use_adaptive=False
    )

    if len(speech_segments) == 0:
        if debug:
            logger.debug("No speech detected at all (falls under Releasing)")
        return "No"

    first_speech_start_ms = speech_segments[0][0]
    late_hello_threshold_ms = app_settings.late_hello_time * 1000.0
    is_late_hello = first_speech_start_ms > late_hello_threshold_ms

    if debug:
        first_speech_start_s = first_speech_start_ms / 1000.0
        logger.debug(f"Late Hello Detection Debug:")
        logger.debug(f"First speech detected at: {first_speech_start_s:.2f}s ({first_speech_start_ms:.0f}ms)")
        logger.debug(f"Late hello threshold: {app_settings.late_hello_time:.1f}s ({late_hello_threshold_ms:.0f}ms)")
        logger.debug(f"Total speech segments found: {len(speech_segments)}")
        logger.debug(f"First 3 segments: {[(round(s/1000, 2), round(e/1000, 2)) for s, e in speech_segments[:3]]}")
        logger.debug(f"Result: {'LATE HELLO' if is_late_hello else 'NORMAL (on time)'}")

    return "Yes" if is_late_hello else "No"


def debug_audio_analysis(agent_segment, file_name="Unknown"):
    """
    Analyze audio segment and return detailed information for debugging.
    """
    try:
        agent_channel = extract_left_channel(agent_segment)
        duration_ms = len(agent_channel)
        duration_s = duration_ms / 1000.0
        channels = agent_segment.channels
        dbfs = agent_channel.dBFS

        speech_segments = voice_activity_detection(
            agent_channel,
            energy_threshold=app_settings.vad_energy_threshold,
            min_speech_duration=app_settings.vad_min_speech_duration,
            use_adaptive=True
        )

        total_speech_duration = sum([end - start for start, end in speech_segments])
        speech_percentage = (total_speech_duration / duration_ms) if duration_ms > 0 else 0

        first_speech_onset = speech_segments[0][0] if speech_segments else None
        first_speech_onset_s = first_speech_onset / 1000.0 if first_speech_onset is not None else None

        audio_array = np.array(agent_channel.get_array_of_samples())
        if len(audio_array) > 0:
            rms_energy = np.sqrt(np.mean(audio_array**2))
            peak_energy = np.max(np.abs(audio_array))
        else:
            rms_energy = peak_energy = 0

        releasing_result = releasing_detection(agent_segment)
        late_hello_result = late_hello_detection(agent_segment)

        return {
            "file_name": file_name,
            "duration_seconds": round(duration_s, 2),
            "channels": channels,
            "dbfs": round(dbfs, 2) if dbfs != float('-inf') else "Silent",
            "rms_energy": round(rms_energy, 2),
            "peak_energy": round(peak_energy, 2),
            "speech_segments_count": len(speech_segments),
            "total_speech_duration_ms": round(total_speech_duration, 1),
            "speech_percentage": round(speech_percentage * 100, 1),
            "first_speech_onset_ms": round(first_speech_onset, 1) if first_speech_onset else "None",
            "first_speech_onset_s": round(first_speech_onset_s, 3) if first_speech_onset_s else "None",
            "releasing_detection": releasing_result,
            "late_hello_detection": late_hello_result,
            "speech_segments": [(round(start, 1), round(end, 1)) for start, end in speech_segments[:5]]
        }
    except Exception as e:
        return {
            "file_name": file_name,
            "error": str(e),
            "releasing_detection": "Error",
            "late_hello_detection": "Error"
        }


def run_audit(audio_segment, mode="heavy", file_name="Unknown"):
    """
    Run either Heavy or Lite audit based on selected mode.
    """
    releasing = releasing_detection(audio_segment)
    late_hello = late_hello_detection(audio_segment)

    result = {
        "File Name": file_name,
        "Releasing Detection": releasing,
        "Late Hello Detection": late_hello,
        "Rebuttal Detection": "N/A",
        "Transcription": "N/A",
        "Agent Intro": "N/A",
        "Owner Name": "N/A",
        "Reason for Calling": "N/A",
        "Intro Score": "N/A",
        "Status": "N/A"
    }

    if mode == "lite":
        result["Status"] = "Lite Completed"

    return result


class IntroductionClassifier:
    """
    Lightweight classifier for call introduction quality.
    """

    def __init__(self, agent_name: str, owner_name: str, property_street: str):
        self.agent_name = agent_name.lower()
        self.owner_name = owner_name.lower()
        self.property_street = property_street.lower()

    def score(self, transcript: str, rebuttal_detected: str = "No", late_hello_detected: str = "No", releasing_detected: str = "No") -> dict:
        transcript_lower = transcript.lower()

        return {
            "agent_intro": self._check_agent_intro(transcript_lower),
            "owner_name": self._check_owner_name_from_transcript(transcript_lower),
            "property_ref": self._check_property_ref_from_transcript(transcript_lower),
            "rebuttal": self._calculate_rebuttal_score(rebuttal_detected),
            "late_hello": self._calculate_late_hello_score(late_hello_detected),
            "releasing": self._calculate_releasing_score(releasing_detected)
        }

    def _check_agent_intro(self, transcript: str) -> Dict[str, int | str]:
        if not self.agent_name:
            return {"display": "N/A", "score": 0}

        intro_section = transcript[:450]

        exact_patterns = [
            f"this is {self.agent_name}",
            f"my name is {self.agent_name}",
            f"i'm {self.agent_name}",
            f"i am {self.agent_name}",
            f"it's {self.agent_name}",
            f"it is {self.agent_name}"
        ]

        for pattern in exact_patterns:
            if pattern in intro_section:
                return {"display": "Yes", "score": 100}

        intro_phrases = [
            r"\bthis\s+is\s+(\w+(?:\s+\w+)?)",
            r"\bmy\s+name\s+is\s+(\w+(?:\s+\w+)?)",
            r"\bi'?m\s+(\w+(?:\s+\w+)?)",
            r"\bit'?s\s+(\w+(?:\s+\w+)?)",
            r"\bthis\s+(\w+(?:\s+\w+)?)(?:\s+and|\s+calling|\s+from|\s+with)",
            r"\byeah\s+this\s+(\w+(?:\s+\w+)?)",
            r"\bhello\s+this\s+(\w+(?:\s+\w+)?)",
        ]

        for pattern in intro_phrases:
            matches = re.findall(pattern, intro_section, re.IGNORECASE)
            for match in matches:
                similarity = fuzz.ratio(match.lower(), self.agent_name.lower())
                if similarity >= 75:
                    return {"display": "Yes", "score": 100}

        generic_patterns = [
            r"\bthis\s+is\s+\w{2,}",
            r"\bmy\s+name\s+is\s+\w{2,}",
            r"\bi'?m\s+\w{2,}\b",
            r"\bit'?s\s+\w{2,}\b"
        ]

        for pattern in generic_patterns:
            if re.search(pattern, intro_section, re.IGNORECASE):
                match = re.search(pattern, intro_section, re.IGNORECASE)
                if match:
                    matched_text = match.group(0).lower()
                    name_candidate = matched_text.split()[-1]
                    non_names = {
                        'calling', 'reaching', 'contacting', 'trying', 'looking',
                        'speaking', 'talking', 'here', 'there', 'just', 'now',
                        'sorry', 'hello', 'good', 'morning', 'afternoon', 'evening'
                    }
                    if name_candidate not in non_names and len(name_candidate) >= 3:
                        return {"display": "Yes", "score": 100}

        return {"display": "No", "score": 0}

    def _check_owner_name_from_transcript(self, transcript: str) -> Dict[str, int | str]:
        intro_section = transcript[:450]
        respectful_addresses = ['ma\'am', 'sir', 'madam', 'miss', 'mister']
        for address in respectful_addresses:
            pattern = rf'\b{re.escape(address)}\b[\s,?.!]*'
            if re.search(pattern, intro_section, re.IGNORECASE):
                return {"display": "Yes", "score": 100}

        greeting_patterns = [
            r'\bhello\s*[,.]?\s+(\w+)(?!\s+(?:this|there|how|what|when|where|why))',
            r'\bhi\s*[,.]?\s+(\w+)(?!\s+(?:this|there|how|what|when|where|why))',
            r'\bhey\s*[,.]?\s+(\w+)(?!\s+(?:this|there|how|what|when|where|why))',
            r'\bgood\s+(?:morning|afternoon|evening)\s*[,.]?\s+(\w+)',
            r'\bms\.?\s+(\w+)',
            r'\bmr\.?\s+(\w+)',
            r'\bmrs\.?\s+(\w+)',
            r'\bmiss\s+(\w+)',
            r'\breaching?\s+(?:out\s+to\s+)?(?:the\s+)?(?:homeowner|owner)?\s*[,.]?\s+(\w+(?:\s+\w+)?)',
            r'\btrying\s+to\s+reach\s+(?:the\s+)?(?:homeowner|owner)?\s*[,.]?\s+(\w+(?:\s+\w+)?)',
            r'\blooking\s+for\s+(?:the\s+)?(?:homeowner|owner)?\s*[,.]?\s+(\w+(?:\s+\w+)?)',
            r'\bspeaking\s+with\s+(\w+(?:\s+\w+)?)',
            r'\bspeaking\s+to\s+(\w+(?:\s+\w+)?)',
            r'\bi\'?m\s+speaking\s+(?:to|with)\s+(\w+(?:\s+\w+)?)',
            r'\bcan\s+i\s+speak\s+(?:to|with)\s+(\w+(?:\s+\w+)?)',
            r'\bmay\s+i\s+speak\s+(?:to|with)\s+(\w+(?:\s+\w+)?)',
            r'\bam\s+i\s+speaking\s+(?:to|with)\s+(\w+(?:\s+\w+)?)',
            r'\bis\s+(\w+(?:\s+\w+)?)\s+(?:there|available)',
            r'\b(?:great|perfect|wonderful|excellent)\s*[,.]?\s+(\w+)',
            r'\bthank\s+you\s*[,.]?\s+(\w+)',
            r'\bnice\s+to\s+(?:meet|speak\s+with)\s+you\s*[,.]?\s+(\w+)',
            r'\bconfirming\s+(?:this\s+is\s+)?(\w+\s+\w+)',
            r'\b(?:so|okay)\s*[,.]?\s+(?:you\'re|you\s+are)\s+(\w+\s+\w+)',
        ]

        for pattern in greeting_patterns:
            matches = re.findall(pattern, intro_section, re.IGNORECASE)
            if matches:
                flattened_matches = []
                for match in matches:
                    if isinstance(match, tuple):
                        flattened_matches.extend([m for m in match if m])
                    else:
                        flattened_matches.append(match)

                non_names = {
                    'there', 'sir', 'maam', 'miss', 'mrs', 'mr', 'ms', 'hello', 'hi', 'hey',
                    'the', 'and', 'but', 'for', 'are', 'you', 'this', 'that', 'with', 'from',
                    'have', 'had', 'has', 'was', 'were', 'will', 'can', 'could', 'would', 'should',
                    'what', 'when', 'where', 'how', 'why', 'who', 'which', 'whose',
                    'yes', 'no', 'not', 'now', 'here', 'there', 'then', 'than',
                    'ma', 'am', 'pm', 'th', 'nd', 'rd', 'st', 'ing', 'ed', 'er', 'ly', 'tion',
                    'i', 'a', 'an', 'as', 'at', 'by', 'do', 'go', 'if', 'in', 'is', 'it', 'me', 'my', 'of', 'on', 'or', 'so', 'to', 'up', 'us', 'we',
                    'out', 'about', 'over', 'under', 'again', 'further', 'once',
                    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
                    'only', 'own', 'same', 'too', 'very', 'dont', 'don',
                    'property', 'house', 'home', 'address', 'street', 'avenue', 'road', 'place'
                }

                valid_names = []
                for name in flattened_matches:
                    name_clean = name.strip().lower()
                    if (
                        name_clean not in non_names
                        and len(name_clean) >= 3
                        and not name.isdigit()
                        and not any(char.isdigit() for char in name)
                        and any(vowel in name_clean for vowel in 'aeiou')
                    ):
                        valid_names.append(name)

                if valid_names:
                    return {"display": "Yes", "score": 100}

        return {"display": "No", "score": 0}

    def _check_property_ref_from_transcript(self, transcript: str) -> Dict[str, int | str]:
        property_patterns = [
            r'\bproperty\b', r'\bhouse\b', r'\bhome\b', r'\bapartment\b', r'\bcondo\b',
            r'\bland\b', r'\baddress\b', r'\bstreet\b', r'\bavenue\b', r'\broad\b', r'\bdrive\b',
            r'\blane\b', r'\bway\b', r'\bplace\b', r'\bcourt\b', r'\bcircl\b', r'\bboulevard\b',
            r'\bparkway\b', r'\bhighway\b', r'\broute\b',
            r'\d+\s+(?:street|avenue|road|drive|lane|way|place|court|circle|boulevard|parkway)',
            r'\d+(?:st|nd|rd|th)\s+(?:street|avenue|road|drive|lane|way|place|court|circle|boulevard|parkway)',
            r'\b(?:street|avenue|road|drive|lane|way|place|court|circle|boulevard|parkway)\s+\d+'
        ]

        for pattern in property_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                return {"display": "Yes", "score": 100}

        return {"display": "No", "score": 0}

    def _calculate_rebuttal_score(self, detected: str) -> Dict[str, int | str]:
        if detected == "Yes":
            return {"display": "Yes", "score": 100}
        if detected == "No":
            return {"display": "No", "score": 0}
        return {"display": "N/A", "score": 0}

    def _calculate_late_hello_score(self, detected: str) -> Dict[str, int | str]:
        if detected == "No":
            return {"display": "No", "score": 100}
        if detected == "Yes":
            return {"display": "Yes", "score": 0}
        return {"display": "N/A", "score": 0}

    def _calculate_releasing_score(self, detected: str) -> Dict[str, int | str]:
        if detected == "No":
            return {"display": "No", "score": 100}
        if detected == "Yes":
            return {"display": "Yes", "score": 0}
        return {"display": "N/A", "score": 0}

