"""
Unified analyzer module using optimized core components.
Provides clean interface for batch processing with proper channel separation.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from audio_pipeline.audio_processor import AudioProcessor, RESULT_KEYS
from audio_pipeline.detections import IntroductionClassifier


class BatchProcessor:
    """
    Optimized batch processor using unified audio processing logic.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        self.audio_processor = AudioProcessor()
        # Optimize workers based on CPU count for better performance
        # Keep 4 workers as it was working fine - focus on batch size and memory cleanup
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        default_workers = min(cpu_count, 4)  # Keep 4 threads as before
        self.max_workers = max_workers or default_workers
    
    def find_audio_files(self, folder_path: str) -> List[Path]:
        """
        Find all audio files in folder and subdirectories.
        
        Args:
            folder_path: Path to search
            
        Returns:
            List of audio file paths
        """
        folder = Path(folder_path)
        if not folder.exists():
            return []
        
        # Search for supported audio formats
        audio_files = []
        for pattern in ['*.mp3', '*.wav', '*.m4a', '*.mp4']:
            audio_files.extend(folder.rglob(pattern))
        
        return audio_files
    
    def process_folder_parallel(self, folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None) -> List[dict]:
        """
        Process all audio files in folder using parallel processing.
        
        Args:
            folder_path: Path to folder containing audio files
            progress_callback: Optional progress callback (done, total)
            additional_metadata: Optional metadata to add to each result
            
        Returns:
            List of processing results
        """
        import logging
        import time
        from concurrent.futures import TimeoutError
        
        logger = logging.getLogger(__name__)
        audio_files = self.find_audio_files(folder_path)
        
        if not audio_files:
            return []
        
        # PRE-LOAD MODELS BEFORE BATCH PROCESSING STARTS
        logger.info("Pre-loading models before batch processing...")
        try:
            from lib.model_preloader import get_model_preloader
            preloader = get_model_preloader()
            preload_success = preloader.preload_all_models()
            if preload_success:
                logger.info("✓ All models pre-loaded successfully")
            else:
                logger.warning("Some models failed to pre-load, will load on-demand")
        except Exception as e:
            logger.warning(f"Model pre-loading failed: {e}, will load on-demand")
        
        results = []
        total_files = len(audio_files)
        logger.info(f"Starting parallel processing of {total_files} audio files")
        completed_global = 0
        
        # Use adaptive batch sizing
        from lib.adaptive_batch_sizer import get_adaptive_batch_sizer
        batch_sizer = get_adaptive_batch_sizer()
        batch_sizer.reset()  # Reset history for new batch
        
        # Allow more time per file for local Whisper Medium on CPU (first run can be slow)
        timeout_per_file = 600  # 600 seconds (10 minutes) timeout per file
        
        i = 0
        batch_num = 0
        while i < total_files:
            # Calculate adaptive batch size for this batch
            remaining_files = audio_files[i:]
            batch_size = batch_sizer.calculate_batch_size(
                remaining_files,
                current_batch_index=batch_num,
                completed_files=completed_global,
                total_files=total_files
            )
            
            batch_files = audio_files[i:i + batch_size]
            batch_num += 1
            total_batches = (total_files + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num} (adaptive size: {len(batch_files)} files)")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit batch for processing
                futures = {}
                for file_path in batch_files:
                    future = executor.submit(self.audio_processor.process_single_file, file_path, additional_metadata, False)
                    futures[future] = file_path
                
                # Collect results with timeout protection (per-file only)
                start_time = time.time()
                completed_count = 0

                for future in as_completed(futures.keys()):
                    try:
                        file_path = futures[future]
                        file_start_time = time.time()
                        result = future.result(timeout=timeout_per_file)
                        file_processing_time = time.time() - file_start_time
                        
                        # Update batch sizer with processing time for adaptive sizing
                        batch_sizer.update_processing_time(file_processing_time)
                        
                        results.append(result)
                        completed_count += 1
                        completed_global += 1

                        # Log progress every 5 files (more frequent updates)
                        if completed_count % 5 == 0 or completed_count == len(batch_files):
                            elapsed = time.time() - start_time
                            avg_time = elapsed / completed_count if completed_count > 0 else 0
                            logger.info(f"Batch {batch_num}: completed {completed_count}/{len(batch_files)} files in {elapsed:.1f}s (avg: {avg_time:.1f}s/file)")
                            # Also log to console for visibility
                            print(f"Progress: {completed_count}/{len(batch_files)} files processed ({completed_count/len(batch_files)*100:.0f}%)")

                        # Update overall progress for UI after each file
                        if progress_callback:
                            progress_callback(completed_global, total_files)

                    except TimeoutError:
                        file_path = futures[future]
                        logger.error(f"Processing timeout for file: {file_path}")
                        print(f"Warning: Timeout processing: {file_path.name}")
                        results.append({
                            'agent_name': 'Timeout',
                            'phone_number': '',
                            'file_path': str(file_path),
                            'error': f"Processing timeout after {timeout_per_file}s",
                            'classification_success': False
                        })
                        completed_count += 1
                        completed_global += 1

                        # Update overall progress for UI after each file
                        if progress_callback:
                            progress_callback(completed_global, total_files)

                    except Exception as e:
                        file_path = futures[future]
                        logger.error(f"Processing failed for {file_path}: {e}", exc_info=True)
                        print(f"Error processing: {file_path.name}")
                        results.append({
                            'agent_name': 'Error',
                            'phone_number': '',
                            'file_path': str(file_path),
                            'error': f"Processing error: {str(e)}",
                            'classification_success': False
                        })
                        completed_count += 1
            
            batch_time = time.time() - start_time
            logger.info(f"Batch {batch_num} completed in {batch_time:.1f}s")
            
            # CRITICAL: Force memory cleanup after each batch to prevent accumulation
            import gc
            gc.collect()
            
            # Clear torch cache if available (for CPU memory management)
            try:
                import torch
                if hasattr(torch, 'cuda') and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as e:
                # Silently ignore torch cache clearing errors as it's optional
                pass
            
            # Update progress and move to next batch
            if progress_callback:
                progress_callback(completed_global, total_files)
            
            i += len(batch_files)  # Move to next batch
        
        logger.info(f"All {total_files} files processed, {len(results)} results collected")
        return results


def convert_to_dataframe_format(results: List[Dict]) -> List[Dict]:
    """
    Convert processing results to standardized DataFrame format.
    Only includes flagged calls (with detected issues).
    
    Args:
        results: List of processing results
        
    Returns:
        List of dictionaries ready for DataFrame conversion
    """
    flagged_calls = []
    
    for result in results:
        # Skip files with errors
        if not result.get('classification_success', False):
            continue
        
        # Check if any detection is flagged
        # Releasing = "Yes" (agent never speaks - BAD)
        releasing_flagged = result.get('releasing_detection') == "Yes"
        # Late Hello = "Yes" (agent speaks too late - BAD)
        late_hello_flagged = result.get('late_hello_detection') == "Yes"
        # Rebuttal = "No" (agent didn't use rebuttals - MISSED OPPORTUNITY - BAD)
        rebuttal_not_used = result.get('rebuttal_detection', {}).get('result') == "No" if isinstance(result.get('rebuttal_detection'), dict) else False
        
        # Only include flagged calls (calls with issues or missed opportunities)
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
            
            # Add dialer name if available in metadata
            if 'dialer_name' in result:
                flagged_call['Dialer Name'] = result['dialer_name']
            
            # Add introduction scoring
            agent_name = result.get('agent_name', '')
            transcription = result.get('transcription', '')
            
            # Get existing detection results
            rebuttal_detected = result.get('rebuttal_detection', {}).get('result', 'No') if isinstance(result.get('rebuttal_detection'), dict) else 'No'
            late_hello_detected = result.get('late_hello_detection', 'No')
            releasing_detected = result.get('releasing_detection', 'No')
            
            # Create classifier with agent name only (owner/property will be detected from transcript)
            classifier = IntroductionClassifier(agent_name, '', '')
            intro_scores = classifier.score(transcription, rebuttal_detected, late_hello_detected, releasing_detected)
            
            # Add new columns
            flagged_call['Agent Intro'] = intro_scores['agent_intro']['display']
            flagged_call['Owner Name'] = intro_scores['owner_name']['display']
            flagged_call['Reason for calling'] = intro_scores['property_ref']['display']
            
            # Calculate total intro score (all 6 metrics) - now as percentage
            all_scores = [
                intro_scores['agent_intro']['score'],
                intro_scores['owner_name']['score'], 
                intro_scores['property_ref']['score'],
                intro_scores['rebuttal']['score'],
                intro_scores['late_hello']['score'],
                intro_scores['releasing']['score']
            ]
            intro_score_value = sum(all_scores) / 6  # Average percentage
            intro_score_display = f"{intro_score_value:.0f}%"
            
            flagged_call['Intro Score'] = intro_score_display
            
            # Status based on intro score - percentage thresholds
            if intro_score_value >= 83:
                status = "Excellent"
            elif intro_score_value >= 50:
                status = "Good"
            elif intro_score_value >= 17:
                status = "Needs Training"
            else:
                status = "Critical"
            flagged_call['Status'] = status
            
            flagged_calls.append(flagged_call)
    
    return flagged_calls


def convert_all_to_dataframe_format(results: List[Dict]) -> pd.DataFrame:
    """
    Convert all processing results to standardized DataFrame format.
    Includes all files, not just flagged calls.
    
    Args:
        results: List of processing results
        
    Returns:
        pandas DataFrame with all results formatted with proper column names
    """
    formatted_results = []
    
    for result in results:
        # Skip files with errors
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
        
        # Add dialer name if available in metadata
        if 'dialer_name' in result:
            formatted_result['Dialer Name'] = result['dialer_name']
        
        # Add introduction scoring
        agent_name = result.get('agent_name', '')
        transcription = result.get('transcription', '')
        
        # Get existing detection results
        rebuttal_detected = result.get('rebuttal_detection', {}).get('result', 'No') if isinstance(result.get('rebuttal_detection'), dict) else 'No'
        late_hello_detected = result.get('late_hello_detection', 'No')
        releasing_detected = result.get('releasing_detection', 'No')
        
        # Create classifier with agent name only (owner/property will be detected from transcript)
        classifier = IntroductionClassifier(agent_name, '', '')
        intro_scores = classifier.score(transcription, rebuttal_detected, late_hello_detected, releasing_detected)
        
        # Add new columns
        formatted_result['Agent Intro'] = intro_scores['agent_intro']['display']
        formatted_result['Owner Name'] = intro_scores['owner_name']['display']
        formatted_result['Reason for calling'] = intro_scores['property_ref']['display']
        
        # Calculate total intro score (all 6 metrics) - now as percentage
        all_scores = [
            intro_scores['agent_intro']['score'],
            intro_scores['owner_name']['score'], 
            intro_scores['property_ref']['score'],
            intro_scores['rebuttal']['score'],
            intro_scores['late_hello']['score'],
            intro_scores['releasing']['score']
        ]
        intro_score_value = sum(all_scores) / 6  # Average percentage
        intro_score_display = f"{intro_score_value:.0f}%"
        
        formatted_result['Intro Score'] = intro_score_display
        
        # Status based on intro score - percentage thresholds
        if intro_score_value >= 83:
            status = "Excellent"
        elif intro_score_value >= 50:
            status = "Good"
        elif intro_score_value >= 17:
            status = "Needs Training"
        else:
            status = "Critical"
        formatted_result['Status'] = status
        
        formatted_results.append(formatted_result)
    
    return pd.DataFrame(formatted_results)


import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

def format_agent_name_with_spaces(agent_name: str) -> str:
    """
    Convert agent names from formats like 'AbdelrahmanAhmedIbrahimHassan' 
    to 'Abdelrahman Ahmed Ibrahim Hassan' by adding spaces before capital letters.
    """
    # If name already has spaces, return as-is
    if ' ' in agent_name:
        return agent_name
    
    # Add space before each capital letter (except the first one)
    spaced_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', agent_name)
    return spaced_name

def format_timestamp_for_display(timestamp: str) -> str:
    """
    Reformat timestamp from ReadyMode format to display format.
    """
    if not timestamp or timestamp.strip() == "":
        return timestamp
    
    # Replace underscore with colon in time portion
    time_pattern = r'(\d{1,2})_(\d{2})(AM|PM)'
    formatted = re.sub(time_pattern, r'\1:\2\3', timestamp)
    return formatted


def batch_analyze_folder_lite(folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None) -> pd.DataFrame:
    """
    Lite batch analysis with only basic detections (releasing and late hello).
    Uses batch processing and parallel execution for optimal performance.
    Much faster than full analysis as it skips transcription and rebuttal detection.

    Args:
        folder_path: Path to folder containing audio files
        progress_callback: Optional callback function for progress updates (done, total)
        additional_metadata: Optional metadata to add to each result

    Returns:
        pandas DataFrame with lite analysis results
    """
    from audio_pipeline.detections import releasing_detection, late_hello_detection
    import logging
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

    logger = logging.getLogger(__name__)

    folder = Path(folder_path)
    if not folder.exists():
        return pd.DataFrame()

    # Find all audio files
    audio_files = []
    for pattern in ['*.mp3', '*.wav', '*.m4a', '*.mp4']:
        audio_files.extend(folder.rglob(pattern))

    if not audio_files:
        return pd.DataFrame()

    results = []
    total_files = len(audio_files)
    logger.info(f"Starting lite parallel processing of {total_files} audio files")

    # Use adaptive batch sizing for lite processing too
    from lib.adaptive_batch_sizer import get_adaptive_batch_sizer
    batch_sizer = get_adaptive_batch_sizer()
    batch_sizer.reset()  # Reset history for new batch
    
    timeout_per_file = 30  # 30 seconds timeout per file (lite processing is much faster)

    # Use same worker calculation as BatchProcessor
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    max_workers = min(cpu_count * 2, 16)  # Up to 16 threads for lite processing

    i = 0
    batch_num = 0
    completed_global = 0
    while i < total_files:
        # Calculate adaptive batch size for this batch
        remaining_files = audio_files[i:]
        batch_size = batch_sizer.calculate_batch_size(
            remaining_files,
            current_batch_index=batch_num,
            completed_files=completed_global,
            total_files=total_files
        )
        
        batch_files = audio_files[i:i + batch_size]
        batch_num += 1
        total_batches = (total_files + batch_size - 1) // batch_size

        logger.info(f"Processing lite batch {batch_num}/{total_batches} ({len(batch_files)} files)")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit batch for lite processing
            futures = {}
            for file_path in batch_files:
                future = executor.submit(process_single_file_lite, file_path, additional_metadata)
                futures[future] = file_path

            # Collect results with timeout protection
            start_time = time.time()
            completed_count = 0

            try:
                for future in as_completed(futures.keys(), timeout=timeout_per_file * len(batch_files)):
                    try:
                        file_path = futures[future]
                        file_start_time = time.time()
                        result = future.result(timeout=timeout_per_file)
                        file_processing_time = time.time() - file_start_time
                        
                        # Update batch sizer with processing time for adaptive sizing
                        batch_sizer.update_processing_time(file_processing_time)
                        
                        results.append(result)
                        completed_count += 1
                        completed_global += 1

                        # Log progress every 10 files (lite processing is faster)
                        if completed_count % 10 == 0 or completed_count == len(batch_files):
                            elapsed = time.time() - start_time
                            avg_time = elapsed / completed_count if completed_count > 0 else 0
                            logger.info(f"Lite batch {batch_num}: completed {completed_count}/{len(batch_files)} files in {elapsed:.1f}s (avg: {avg_time:.1f}s/file)")
                            print(f"Lite Progress: {completed_count}/{len(batch_files)} files processed ({completed_count/len(batch_files)*100:.0f}%)")

                    except TimeoutError:
                        file_path = futures[future]
                        logger.error(f"Lite processing timeout for file: {file_path}")
                        print(f"Warning: Lite timeout processing: {file_path.name}")
                        # Try to extract structured info even for timeout errors
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
                        
                        results.append({
                            "Agent Name": agent_name,
                            "Phone Number": phone_number,
                            "Timestamp": timestamp,
                            "Disposition": disposition,
                            "Releasing Detection": "Error",
                            "Late Hello Detection": "Error",
                            "Rebuttal Detection": "N/A",
                            "Transcription": "N/A",
                            "Agent Intro": "N/A",
                            "Owner Name": "N/A",
                            "Reason for Calling": "N/A",
                            "Intro Score": "N/A",
                            "Status": f"Error: Processing timeout after {timeout_per_file}s"
                        })
                        completed_count += 1
                        completed_global += 1

                    except Exception as e:
                        file_path = futures[future]
                        logger.error(f"Lite processing failed for {file_path}: {e}", exc_info=True)
                        print(f"Error: Lite error processing: {file_path.name}")
                        # Try to extract structured info even for general errors
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
                        
                        results.append({
                            "Agent Name": agent_name,
                            "Phone Number": phone_number,
                            "Timestamp": timestamp,
                            "Disposition": disposition,
                            "Releasing Detection": "Error",
                            "Late Hello Detection": "Error",
                            "Rebuttal Detection": "N/A",
                            "Transcription": "N/A",
                            "Agent Intro": "N/A",
                            "Owner Name": "N/A",
                            "Reason for Calling": "N/A",
                            "Intro Score": "N/A",
                            "Status": f"Error: {str(e)}"
                        })
                        completed_count += 1
                        completed_global += 1

            except TimeoutError:
                # Entire batch timed out
                logger.error(f"Lite batch {batch_num} timed out after {timeout_per_file * len(batch_files)}s")
                print(f"Error: Lite batch {batch_num} timed out! Continuing with next batch...")
                # Add error results for remaining files
                for future, file_path in futures.items():
                    if not future.done():
                        # Try to extract structured info even for batch timeout
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
                        
                        results.append({
                            "Agent Name": agent_name,
                            "Phone Number": phone_number,
                            "Timestamp": timestamp,
                            "Disposition": disposition,
                            "Releasing Detection": "Error",
                            "Late Hello Detection": "Error",
                            "Rebuttal Detection": "N/A",
                            "Transcription": "N/A",
                            "Agent Intro": "N/A",
                            "Owner Name": "N/A",
                            "Reason for Calling": "N/A",
                            "Intro Score": "N/A",
                            "Status": "Error: Batch processing timeout"
                        })

        batch_time = time.time() - start_time
        logger.info(f"Lite batch {batch_num} completed in {batch_time:.1f}s")

        # Update progress and move to next batch
        if progress_callback:
            progress_callback(completed_global, total_files)
        
        i += len(batch_files)  # Move to next batch

    logger.info(f"All {total_files} files processed with lite analysis, {len(results)} results collected")
    return pd.DataFrame(results)


def process_single_file_lite(file_path: Path, additional_metadata: Optional[dict] = None) -> dict:
    """
    Process a single audio file with lite detection (releasing + late hello only).
    This is the worker function for parallel lite processing.
    Extracts structured information from filename to match heavy audit columns.

    Args:
        file_path: Path to the audio file
        additional_metadata: Optional metadata to add to result

    Returns:
        dict: Processing result with lite detections and structured columns
    """
    from audio_pipeline.detections import releasing_detection, late_hello_detection
    from pydub import AudioSegment

    try:
        # Extract metadata from filename (same logic as heavy audit)
        stem = file_path.stem
        parts = stem.split(" _ ")
        
        if len(parts) == 4:
            # New format: AgentName _ Timestamp _ Phone _ Disposition.mp3
            agent_name_raw, timestamp, phone_number, disposition = parts
        elif len(parts) == 2:
            # Old format: AgentName _ Phone.mp3
            agent_name_raw, phone_number = parts
            timestamp = ""
            disposition = ""
        else:
            # Fallback for other formats
            agent_name_raw = stem
            phone_number = ""
            timestamp = ""
            disposition = ""
        
        # Clean up agent name - remove special characters but keep the structure
        agent_name_raw = agent_name_raw.replace("-", "").replace(".", "")
        
        # Format agent name with proper spacing
        agent_name = format_agent_name_with_spaces(agent_name_raw)
        
        # Format timestamp for display
        timestamp = format_timestamp_for_display(timestamp)

        # Load audio file
        audio = AudioSegment.from_file(str(file_path))

        # Perform only lite detections
        releasing = releasing_detection(audio)
        late_hello = late_hello_detection(audio)

        # Create result dict with structured columns matching heavy audit
        result = {
            "Agent Name": agent_name,
            "Phone Number": phone_number,
            "Timestamp": timestamp,
            "Disposition": disposition,
            "Releasing Detection": releasing,
            "Late Hello Detection": late_hello,
            "Rebuttal Detection": "N/A",
            "Transcription": "N/A",
            "Agent Intro": "N/A",
            "Owner Name": "N/A",
            "Reason for Calling": "N/A",
            "Intro Score": "N/A",
            "Status": "Lite Completed"
        }

        # Add metadata if provided
        if additional_metadata:
            for key, value in additional_metadata.items():
                result[key] = value

        return result

    except Exception as e:
        # Even on error, try to extract filename info for structured columns
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

        return {
            "Agent Name": agent_name,
            "Phone Number": phone_number,
            "Timestamp": timestamp,
            "Disposition": disposition,
            "Releasing Detection": "Error",
            "Late Hello Detection": "Error",
            "Rebuttal Detection": "N/A",
            "Transcription": "N/A",
            "Agent Intro": "N/A",
            "Owner Name": "N/A",
            "Reason for Calling": "N/A",
            "Intro Score": "N/A",
            "Status": f"Error: {str(e)}"
        }


# Global batch processor instance
_batch_processor = BatchProcessor()
def batch_analyze_folder(folder_path: str) -> pd.DataFrame:
    """
    Analyze all audio files in a folder and return results as pandas DataFrame.
    Uses optimized core audio processing with proper channel separation.
    
    Args:
        folder_path: Path to folder containing audio files
        
    Returns:
        pandas DataFrame with analysis results for flagged calls only
    """
    results = _batch_processor.process_folder_parallel(folder_path)
    flagged_calls = convert_to_dataframe_format(results)
    return pd.DataFrame(flagged_calls)


def batch_analyze_folder_fast(folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None, show_all_results: bool = False) -> pd.DataFrame:
    """
    Fast batch analysis with progress tracking and proper channel separation.
    
    Args:
        folder_path: Path to folder containing audio files
        progress_callback: Optional callback function for progress updates (done, total)
        additional_metadata: Optional metadata to add to each result (e.g., dialer_name, date)
        show_all_results: If True, return all results instead of just flagged calls
        
    Returns:
        pandas DataFrame with analysis results
    """
    results = _batch_processor.process_folder_parallel(folder_path, progress_callback, additional_metadata)
    
    if show_all_results:
        # Return all results as DataFrame for debugging, but apply proper column formatting
        return convert_all_to_dataframe_format(results)
    else:
        # Return only flagged calls (default behavior)
        flagged_calls = convert_to_dataframe_format(results)
        return pd.DataFrame(flagged_calls)
