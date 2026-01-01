"""
Audio processing module within audio_pipeline package.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from pydub import AudioSegment

from audio_pipeline.detections import debug_audio_analysis, late_hello_detection, releasing_detection

# Import agent_only_detector with fallback
try:
    from lib.agent_only_detector import AgentOnlyRebuttalDetector
except (ModuleNotFoundError, ImportError):
    try:
        from agent_only_detector import AgentOnlyRebuttalDetector
    except (ModuleNotFoundError, ImportError):
        import importlib.util

        possible_paths = [
            Path(__file__).parent.parent / "agent_only_detector.py",
            Path(__file__).parent.parent / "lib" / "agent_only_detector.py",
        ]

        agent_only_detector_path = None
        for path in possible_paths:
            if path.exists():
                agent_only_detector_path = path
                break

        if agent_only_detector_path is None:
            raise ModuleNotFoundError("Could not find agent_only_detector.py in expected locations")

        spec = importlib.util.spec_from_file_location(
            "agent_only_detector",
            agent_only_detector_path
        )
        agent_only_detector = importlib.util.module_from_spec(spec)
        sys.modules["agent_only_detector"] = agent_only_detector
        spec.loader.exec_module(agent_only_detector)
        AgentOnlyRebuttalDetector = agent_only_detector.AgentOnlyRebuttalDetector


logger = logging.getLogger(__name__)
_agent_detector = None


def get_agent_detector(user_api_key: Optional[str] = None):
    global _agent_detector
    # Create a new instance with user API key if different
    if _agent_detector is None or user_api_key is not None:
        _agent_detector = AgentOnlyRebuttalDetector(user_api_key=user_api_key)
    return _agent_detector


def format_agent_name_with_spaces(agent_name: str) -> str:
    if ' ' in agent_name:
        return agent_name
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', agent_name)


def format_timestamp_for_display(timestamp: str) -> str:
    if not timestamp or timestamp.strip() == "":
        return timestamp
    time_pattern = r'(\d{1,2})_(\d{2})(AM|PM)'
    return re.sub(time_pattern, r'\1:\2\3', timestamp)


class AudioProcessor:
    """
    Unified audio processor for VOS Tool.
    Handles file loading, channel separation, and call classification.
    """

    def __init__(self):
        self.supported_formats = ['.mp3', '.wav', '.m4a', '.mp4']

    def is_valid_audio_file(self, file_path: Path) -> bool:
        try:
            if not file_path.exists() or not file_path.is_file():
                return False
            file_size = file_path.stat().st_size
            if file_size < 1024:  # Skip files smaller than 1KB (likely empty/corrupt)
                return False
            if file_path.suffix.lower() not in self.supported_formats:
                return False
            return True
        except Exception:
            return False
    
    def _check_audio_duration(self, audio: AudioSegment) -> bool:
        """Check if audio meets minimum duration requirement (skip very short/silent files)."""
        duration_ms = len(audio)
        # Skip files shorter than 3 seconds (likely silent or corrupted)
        if duration_ms < 3000:
            logger.warning(f"Audio too short ({duration_ms}ms), skipping")
            return False
        return True

    def load_audio_file(self, file_path: Path) -> Optional[AudioSegment]:
        try:
            return AudioSegment.from_mp3(file_path)
        except Exception:
            for format_name in ['wav', 'mp4', 'm4a']:
                try:
                    return AudioSegment.from_file(str(file_path), format=format_name)
                except Exception:
                    continue
            return None

    def extract_agent_audio(self, audio: AudioSegment) -> AudioSegment:
        if audio.channels == 2:
            return audio.split_to_mono()[0]
        return audio

    def classify_call(self, agent_audio: AudioSegment, full_audio: AudioSegment, file_name: str = "", user_api_key: Optional[str] = None) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)

        logger.info(f"Starting classification for file: {file_name}")
        start_time = time.time()

        result = {
            'classification_success': False,
            'error': None,
            'releasing_detection': 'No',
            'late_hello_detection': 'No',
            'rebuttal_detection': {'result': 'No', 'transcript': ''}
        }

        try:
            # Fast-path: Skip very short audio files before processing
            if not self._check_audio_duration(agent_audio):
                result['error'] = 'Audio too short (<3 seconds)'
                result['rebuttal_detection'] = {'result': 'Skipped', 'transcript': '', 'reason': 'too_short'}
                return result
            
            # OPTIMIZATION: Prepare temp file for AssemblyAI early (before other detections)
            import tempfile
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    agent_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
                    temp_file = tmp.name
            except Exception as temp_error:
                logger.error(f"Failed to create temp file for transcription: {temp_error}")
                temp_file = None
            
            # OPTIMIZATION: Run all three detections in parallel for maximum speed
            # - Releasing detection (local, fast ~0.5-1s)
            # - Late hello detection (local, fast ~0.5-1s)
            # - Rebuttal detection (AssemblyAI API, slow ~30-60s) - starts immediately
            logger.debug(f"Starting parallel detections for {file_name}")
            overall_start = time.time()
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Submit releasing and late hello tasks (fast local detections)
                future_releasing = executor.submit(releasing_detection, agent_audio)
                future_late_hello = executor.submit(late_hello_detection, agent_audio, file_name)
                
                # Start rebuttal detection (AssemblyAI) early if temp file was created
                # This runs in parallel with releasing/late hello detections
                # Note: Using sync version here for ThreadPoolExecutor compatibility
                # Async version will be used in async batch processing
                future_rebuttal = None
                if temp_file:
                    agent_detector = get_agent_detector(user_api_key)
                    future_rebuttal = executor.submit(agent_detector.detect_rebuttals_in_audio, temp_file)
                
                # Collect results as they complete
                # Releasing detection (fast, completes first ~0.5-1s)
                rel_start = time.time()
                try:
                    result['releasing_detection'] = future_releasing.result()
                except Exception as rel_error:
                    logger.error(f"Releasing detection failed: {rel_error}")
                    result['releasing_detection'] = 'Error'
                rel_time = time.time() - rel_start
                logger.info(f"Releasing detection completed in {rel_time:.2f}s: {result['releasing_detection']}")
                
                # Late hello detection (fast, completes second ~0.5-1s)
                late_start = time.time()
                try:
                    result['late_hello_detection'] = future_late_hello.result()
                except Exception as late_error:
                    logger.error(f"Late hello detection failed: {late_error}")
                    result['late_hello_detection'] = 'Error'
                late_time = time.time() - late_start
                logger.info(f"Late hello detection completed in {late_time:.2f}s: {result['late_hello_detection']}")
                
                # Rebuttal detection (slow, completes last ~30-60s, but started in parallel)
                # Check if we need rebuttal detection (skip if releasing call)
                if result['releasing_detection'] == 'Yes':
                    logger.info(f"Skipping rebuttal detection for releasing call: {file_name}")
                    # Note: future_rebuttal may still be running, but we'll ignore the result
                    # This is acceptable - the API call will complete but we won't use it
                    if future_rebuttal:
                        # Try to cancel if not started yet (won't work if already running, but harmless)
                        future_rebuttal.cancel()
                        # If cancellation failed (already running), just ignore the result
                        try:
                            # Quick timeout check - if it's running, don't wait
                            if not future_rebuttal.done():
                                logger.debug("Rebuttal detection already started, will complete but result will be ignored")
                        except Exception:
                            pass
                elif future_rebuttal:
                    reb_start = time.time()
                    try:
                        detection_result = future_rebuttal.result()
                        result['rebuttal_detection'] = {
                            'result': detection_result['result'],
                            'confidence_score': detection_result.get('confidence_score'),
                            'transcript': detection_result.get('transcript', '')
                        }
                    except Exception as reb_error:
                        # Check if it's a timeout error
                        error_str = str(reb_error)
                        is_timeout = 'ReadTimeout' in error_str or 'timeout' in error_str.lower() or 'timed out' in error_str.lower()
                        
                        if is_timeout:
                            logger.warning(f"Agent-only rebuttal detection timed out: {reb_error}. Treating as 'No' rebuttal.")
                            result['rebuttal_detection'] = {'result': 'No', 'transcript': '', 'error': 'timeout'}
                        else:
                        logger.error(f"Agent-only rebuttal detection failed: {reb_error}")
                            result['rebuttal_detection'] = {'result': 'No', 'transcript': '', 'error': str(reb_error)}
                    reb_time = time.time() - reb_start
                    logger.info(f"Agent-only rebuttal detection completed in {reb_time:.2f}s: {result['rebuttal_detection'].get('result', 'Error')}")
                else:
                    logger.warning(f"Could not start rebuttal detection (temp file creation failed) for {file_name}")
                    result['rebuttal_detection'] = {'result': 'No', 'transcript': '', 'error': 'temp_file_failed'}
            
            # Clean up temp file
            if temp_file:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            
            overall_time = time.time() - overall_start
            logger.info(f"All parallel detections completed for {file_name} in {overall_time:.2f}s")

            result['classification_success'] = True
            total_time = time.time() - start_time
            logger.info(f"All classifications completed for {file_name} in {total_time:.2f}s")

        except Exception as e:
            logger.error(f"Classification failed for {file_name}: {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def process_single_file(self, file_path: Path, additional_metadata: Optional[dict] = None, include_debug: bool = False, username: Optional[str] = None, user_api_key: Optional[str] = None) -> Dict:
        logger = logging.getLogger(__name__)
        start_time = time.time()

        logger.info(f"Starting processing of file: {file_path}")

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
        agent_name = format_agent_name_with_spaces(agent_name_raw)
        timestamp = format_timestamp_for_display(timestamp)

        if not self.is_valid_audio_file(file_path):
            logger.warning(f"Invalid audio file: {file_path}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Invalid audio file: {file_path}",
                'processing_time': time.time() - start_time,
                'classification_success': False
            }

        load_start = time.time()
        try:
            audio = self.load_audio_file(file_path)
            load_time = time.time() - load_start
            logger.debug(f"Audio loaded in {load_time:.2f}s")
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
                'classification_success': False
            }

        if audio is None:
            logger.error(f"Audio loading returned None for {file_path}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Failed to load audio: {file_path}",
                'processing_time': time.time() - start_time,
                'classification_success': False
            }

        agent_audio = self.extract_agent_audio(audio)

        if len(agent_audio) < 1000:
            logger.warning(f"Audio too short: {len(agent_audio)}ms for {file_path}")
            return {
                'agent_name': agent_name,
                'phone_number': phone_number,
                'timestamp': timestamp,
                'disposition': disposition,
                'file_path': str(file_path),
                'error': f"Audio too short: {len(agent_audio)}ms",
                'processing_time': time.time() - start_time,
                'classification_success': False
            }

        try:
            classification = self.classify_call(agent_audio, audio, file_name=file_path.name, user_api_key=user_api_key)
        except Exception as e:
            logger.error(f"Classification failed for {file_path}: {e}", exc_info=True)
            classification = {
                'classification_success': False,
                'error': str(e),
                'releasing_detection': 'Error',
                'late_hello_detection': 'Error',
                'rebuttal_detection': 'Error'
            }

        # Extract transcription from rebuttal detection result
        # Ensure transcription is always included, matching Agent Audit and Campaign Audit behavior
        transcription = ''
        if isinstance(classification['rebuttal_detection'], dict):
            transcription = classification['rebuttal_detection'].get('transcript', '')
        elif isinstance(classification.get('rebuttal_detection'), str):
            # Fallback: if rebuttal_detection is a string (e.g., 'Error'), try to get transcript from classification
            transcription = classification.get('transcript', '')
        
        result = {
            'agent_name': agent_name,
            'phone_number': phone_number,
            'timestamp': timestamp,
            'disposition': disposition,
            'file_path': str(file_path),
            'processing_time': time.time() - start_time,
            'classification_success': classification['classification_success'],
            'releasing_detection': classification['releasing_detection'],
            'late_hello_detection': classification['late_hello_detection'],
            'rebuttal_detection': classification['rebuttal_detection'],
            'transcription': transcription
        }

        if additional_metadata:
            result.update(additional_metadata)

        if classification['error']:
            result['error'] = classification['error']

        if include_debug:
            try:
                debug_info = debug_audio_analysis(agent_audio, file_path.name)
                result['debug_info'] = debug_info
            except Exception as e:
                result['debug_error'] = str(e)

        total_time = time.time() - start_time
        logger.info(f"Completed processing of {file_path} in {total_time:.2f}s")

        import gc
        gc.collect()

        return result

    def process_batch(self, file_paths: List[Path], additional_metadata: Optional[dict] = None, include_debug: bool = False) -> List[Dict]:
        results = []
        for file_path in file_paths:
            result = self.process_single_file(file_path, additional_metadata, include_debug)
            results.append(result)
        return results


RESULT_KEYS = {
    "AGENT_NAME": "Agent Name",
    "PHONE_NUMBER": "Phone Number",
    "TIMESTAMP": "Timestamp",
    "DISPOSITION": "Disposition",
    "RELEASING": "Releasing Detection",
    "LATE_HELLO": "Late Hello Detection",
    "REBUTTAL": "Rebuttal Detection",
    "TRANSCRIPTION": "Transcription"
}


def convert_to_dataframe_format(results: List[Dict]) -> List[Dict]:
    flagged_calls = []

    for result in results:
        if not result.get('classification_success', False):
            continue

        releasing_flagged = result.get('releasing_detection') == "Yes"
        late_hello_flagged = result.get('late_hello_detection') == "Yes"
        rebuttal_not_used = result.get('rebuttal_detection', {}).get('result') == "No" if isinstance(result.get('rebuttal_detection'), dict) else False

        if releasing_flagged or late_hello_flagged or rebuttal_not_used:
            flagged_call = {
                RESULT_KEYS["AGENT_NAME"]: result.get('agent_name', ''),
                RESULT_KEYS["PHONE_NUMBER"]: result.get('phone_number', ''),
                RESULT_KEYS["TIMESTAMP"]: result.get('timestamp', ''),
                RESULT_KEYS["DISPOSITION"]: result.get('disposition', ''),
                RESULT_KEYS["RELEASING"]: result.get('releasing_detection', 'No'),
                RESULT_KEYS["LATE_HELLO"]: result.get('late_hello_detection', 'No'),
                RESULT_KEYS["REBUTTAL"]: result.get('rebuttal_detection', {}).get('result', 'No') if isinstance(result.get('rebuttal_detection'), dict) else 'No',
                RESULT_KEYS["TRANSCRIPTION"]: result.get('transcription', '')
            }

            if 'dialer_name' in result:
                flagged_call['Dialer Name'] = result['dialer_name']

            flagged_calls.append(flagged_call)

    return flagged_calls


def convert_all_to_dataframe_format(results: List[Dict]) -> List[Dict]:
    formatted_results = []

    for result in results:
        if not result.get('classification_success', False):
            continue

        formatted_result = {
            RESULT_KEYS["AGENT_NAME"]: result.get('agent_name', ''),
            RESULT_KEYS["PHONE_NUMBER"]: result.get('phone_number', ''),
            RESULT_KEYS["TIMESTAMP"]: result.get('timestamp', ''),
            RESULT_KEYS["DISPOSITION"]: result.get('disposition', ''),
            RESULT_KEYS["RELEASING"]: result.get('releasing_detection', 'No'),
            RESULT_KEYS["LATE_HELLO"]: result.get('late_hello_detection', 'No'),
            RESULT_KEYS["REBUTTAL"]: result.get('rebuttal_detection', {}).get('result', 'No') if isinstance(result.get('rebuttal_detection'), dict) else 'No',
            RESULT_KEYS["TRANSCRIPTION"]: result.get('transcription', '')
        }

        if 'dialer_name' in result:
            formatted_result['Dialer Name'] = result['dialer_name']

        formatted_results.append(formatted_result)

    return formatted_results

