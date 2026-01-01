"""
Unified analyzer module using optimized core components.
Provides clean interface for batch processing with proper channel separation.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import logging
import asyncio

from audio_pipeline.audio_processor import AudioProcessor, RESULT_KEYS

logger = logging.getLogger(__name__)
from audio_pipeline.detections import IntroductionClassifier


class BatchProcessor:
    """
    Optimized batch processor using unified audio processing logic.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        self.audio_processor = AudioProcessor()
        # Optimize workers for fast AssemblyAI processing (30-60s files)
        # Limit concurrent API calls to avoid rate limits and optimize throughput
        import multiprocessing
        import os
        cpu_count = multiprocessing.cpu_count()
        
        # Check for manual override via environment variable
        if max_workers is None and os.getenv("ASSEMBLYAI_MAX_WORKERS"):
            try:
                max_workers = int(os.getenv("ASSEMBLYAI_MAX_WORKERS"))
                logger.info(f"Using ASSEMBLYAI_MAX_WORKERS={max_workers} from environment")
            except ValueError:
                logger.warning(f"Invalid ASSEMBLYAI_MAX_WORKERS value, using default")
                max_workers = None
        
        # Default worker count based on AssemblyAI account limits
        # Free accounts: 5 concurrent jobs max
        # Paid accounts: 200 concurrent jobs max (but use reasonable limit like 20)
        if max_workers is None:
            account_type = os.getenv("ASSEMBLYAI_ACCOUNT_TYPE", "free").lower()
            if account_type == "paid":
                # Paid accounts: Use more workers (up to 20 for optimal performance)
                default_workers = min(cpu_count, 20)
                logger.info(f"Paid AssemblyAI account detected, using {default_workers} workers")
            else:
                # Free accounts: Use 5 workers (max allowed for free accounts)
                default_workers = min(cpu_count, 5)
                logger.info(f"Free AssemblyAI account (default), using {default_workers} workers (max 5 for free accounts)")
            max_workers = default_workers
        
        self.max_workers = max_workers
        logger.info(f"Batch processor initialized with {self.max_workers} workers (optimized for AssemblyAI API)")
    
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
    
    def process_folder_parallel(self, folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None, username: Optional[str] = None, user_api_key: Optional[str] = None) -> List[dict]:
        """
        Process all audio files in folder using parallel processing.
        
        Args:
            folder_path: Path to folder containing audio files
            progress_callback: Optional progress callback (done, total)
            additional_metadata: Optional metadata to add to each result
            username: Optional username for user-specific API key
            user_api_key: Optional user-specific AssemblyAI API key
            
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
            from processing.model_preloader import get_model_preloader
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
        from processing.adaptive_batch_sizer import get_adaptive_batch_sizer
        batch_sizer = get_adaptive_batch_sizer(username)
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
                    future = executor.submit(self.audio_processor.process_single_file, file_path, additional_metadata, False, username, user_api_key)
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
                        error_msg = str(e)
                        logger.error(f"Error processing file {file_path.name} for user {username or 'default'}: {e}", exc_info=True)
                        print(f"Error processing: {file_path.name}")
                        
                        # Check for specific concurrency-related errors
                        if "connection pool exhausted" in error_msg.lower() or "rate limit" in error_msg.lower():
                            logger.error(f"⚠️ CONCURRENCY ISSUE: {error_msg} - This may indicate resource exhaustion")
                        
                        results.append({
                            'agent_name': 'Error',
                            'phone_number': '',
                            'file_path': str(file_path),
                            'error': f"Processing error: {str(e)}",
                            'classification_success': False
                        })
                        completed_count += 1
                        completed_global += 1
            
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
        
        logger.info(f"Completed processing {total_files} files for user {username or 'default'}. Total results: {len(results)}")
        
        # Log if processing stopped early (potential issue)
        if completed_global < total_files:
            logger.warning(f"⚠️ EARLY STOP DETECTED: User {username or 'default'} processed {completed_global}/{total_files} files. Missing {total_files - completed_global} files!")
            logger.warning(f"This may indicate worker pool exhaustion, resource contention, or API rate limits.")
        
        return results
    
    async def process_folder_async(self, folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None, username: Optional[str] = None, user_api_key: Optional[str] = None) -> List[dict]:
        """
        Process all audio files in folder using async/await for optimal AssemblyAI concurrency.
        This method uses asyncio to manage concurrent API calls more efficiently than ThreadPoolExecutor.
        
        Args:
            folder_path: Path to folder containing audio files
            progress_callback: Optional progress callback (done, total)
            additional_metadata: Optional metadata to add to each result
            
        Returns:
            List of processing results
        """
        import time
        from concurrent.futures import TimeoutError
        
        logger.info("Starting ASYNC batch processing (Phase 2 optimization)")
        audio_files = self.find_audio_files(folder_path)
        
        if not audio_files:
            return []
        
        # PRE-LOAD MODELS BEFORE BATCH PROCESSING STARTS
        logger.info("Pre-loading models before async batch processing...")
        try:
            from processing.model_preloader import get_model_preloader
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
        logger.info(f"Starting async processing of {total_files} audio files with {self.max_workers} concurrent workers")
        completed_global = 0
        
        # Use adaptive batch sizing
        from processing.adaptive_batch_sizer import get_adaptive_batch_sizer
        batch_sizer = get_adaptive_batch_sizer(username)
        batch_sizer.reset()  # Reset history for new batch
        
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
            
            logger.info(f"Processing async batch {batch_num}/{total_batches} (size: {len(batch_files)} files)")
            
            # Create semaphore to limit concurrent AssemblyAI API calls
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def process_single_file_async(file_path: Path) -> dict:
                """Process a single file with async transcription."""
                async with semaphore:
                    try:
                        # Run the synchronous process_single_file in executor
                        # This allows us to use async for AssemblyAI calls while keeping other processing sync
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            self.audio_processor.process_single_file,
                            file_path,
                            additional_metadata,
                            False,
                            username,
                            user_api_key,
                        )
                        return result
                    except Exception as e:
                        logger.error(f"Async processing failed for {file_path}: {e}", exc_info=True)
                        return {
                            'agent_name': 'Error',
                            'phone_number': '',
                            'file_path': str(file_path),
                            'error': f"Processing error: {str(e)}",
                            'classification_success': False
                        }
            
            # Process batch with async concurrency control
            start_time = time.time()
            tasks = [process_single_file_async(file_path) for file_path in batch_files]
            
            # Use as_completed equivalent for async - gather results as they complete
            completed_count = 0
            for coro in asyncio.as_completed(tasks):
                try:
                    file_start_time = time.time()
                    result = await asyncio.wait_for(coro, timeout=timeout_per_file)
                    file_processing_time = time.time() - file_start_time
                    
                    # Update batch sizer with processing time for adaptive sizing
                    batch_sizer.update_processing_time(file_processing_time)
                    
                    results.append(result)
                    completed_count += 1
                    completed_global += 1
                    
                    # Log progress every 5 files
                    if completed_count % 5 == 0 or completed_count == len(batch_files):
                        elapsed = time.time() - start_time
                        avg_time = elapsed / completed_count if completed_count > 0 else 0
                        logger.info(f"Async batch {batch_num}: completed {completed_count}/{len(batch_files)} files in {elapsed:.1f}s (avg: {avg_time:.1f}s/file)")
                        print(f"Async Progress: {completed_count}/{len(batch_files)} files processed ({completed_count/len(batch_files)*100:.0f}%)")
                    
                    # Update overall progress for UI after each file
                    if progress_callback:
                        progress_callback(completed_global, total_files)
                        
                except asyncio.TimeoutError:
                    logger.error(f"Async processing timeout for file in batch {batch_num}")
                    print(f"Warning: Async timeout processing file in batch {batch_num}")
                    results.append({
                        'agent_name': 'Timeout',
                        'phone_number': '',
                        'file_path': 'Unknown',
                        'error': f"Processing timeout after {timeout_per_file}s",
                        'classification_success': False
                    })
                    completed_count += 1
                    completed_global += 1
                    
                    if progress_callback:
                        progress_callback(completed_global, total_files)
                        
                except Exception as e:
                    logger.error(f"Async batch processing error: {e}", exc_info=True)
                    results.append({
                        'agent_name': 'Error',
                        'phone_number': '',
                        'file_path': 'Unknown',
                        'error': f"Processing error: {str(e)}",
                        'classification_success': False
                    })
                    completed_count += 1
                    completed_global += 1
                    
                    if progress_callback:
                        progress_callback(completed_global, total_files)
            
            batch_time = time.time() - start_time
            logger.info(f"Async batch {batch_num} completed in {batch_time:.1f}s")
            
            # CRITICAL: Force memory cleanup after each batch
            import gc
            gc.collect()
            
            # Clear torch cache if available
            try:
                import torch
                if hasattr(torch, 'cuda') and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            
            # Update progress and move to next batch
            if progress_callback:
                progress_callback(completed_global, total_files)
            
            i += len(batch_files)  # Move to next batch
        
        logger.info(f"All {total_files} files processed with async method, {len(results)} results collected")
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

            if 'API Key Source' in result:
                flagged_call['API Key Source'] = result['API Key Source']
            elif 'api_key_source' in result:
                flagged_call['API Key Source'] = result['api_key_source']
            
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

        if 'API Key Source' in result:
            formatted_result['API Key Source'] = result['API Key Source']
        elif 'api_key_source' in result:
            formatted_result['API Key Source'] = result['api_key_source']
        
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

def extract_dialer_name_from_path(file_path: Path) -> str:
    """
    Extract dialer name from file path folder structure.
    Pattern: Recordings/Agent/{username}/{agent}-{date}_{counter} {dialer_name}/filename.mp3
    or: Recordings/Campaign/{username}/{campaign}-{date}_{counter} {dialer_name}/filename.mp3
    
    Examples:
    - "users-2025-12-12_005 resva3" -> "resva3"
    - "AgentName-2025-12-12_001 dialer1" -> "dialer1"
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dialer name if found (only the part after the last space), empty string otherwise
    """
    try:
        # Get parent directory (folder containing the file)
        parent_dir = file_path.parent.name
        
        # Pattern: {agent}-{date}_{counter} {dialer_name}
        # Look for space in folder name - dialer name is after the LAST space
        # This handles cases like "users-2025-12-12_005 resva3" -> "resva3"
        if ' ' in parent_dir:
            # Split on all spaces and take the last part (dialer name)
            parts = parent_dir.rsplit(' ', 1)  # Split on last space only
            if len(parts) == 2:
                dialer_name = parts[1].strip()
                # Remove any trailing path separators or special characters
                dialer_name = dialer_name.rstrip('/\\')
                if dialer_name:
                    return dialer_name
    except Exception as e:
        logger.debug(f"Error extracting dialer name from path {file_path}: {e}")
    
    return ""


def batch_analyze_folder_lite(folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None, username: Optional[str] = None, user_api_key: Optional[str] = None) -> pd.DataFrame:
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
    from processing.adaptive_batch_sizer import get_adaptive_batch_sizer
    batch_sizer = get_adaptive_batch_sizer()
    batch_sizer.reset()  # Reset history for new batch
    
    timeout_per_file = 30  # 30 seconds timeout per file (lite processing is much faster)

    # Optimize workers based on GPU availability
    import multiprocessing
    import torch
    cpu_count = multiprocessing.cpu_count()
    
    # GPU-optimized: More workers since GPU handles inference
    if torch.cuda.is_available():
        max_workers = min(cpu_count, 8)  # More workers with GPU
    else:
        max_workers = min(cpu_count * 2, 16)  # Up to 16 threads for CPU lite processing

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
                future = executor.submit(process_single_file_lite, file_path, additional_metadata, user_api_key)
                futures[future] = file_path

            # Collect results with timeout protection
            start_time = time.time()
            completed_count = 0
            batch_timeout = timeout_per_file * len(batch_files) + 60  # Add 60s buffer for batch timeout

            try:
                for future in as_completed(futures.keys(), timeout=batch_timeout):
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

                        # Log progress every 10 files (lite processing is faster) - show TOTAL progress
                        if completed_global % 10 == 0 or completed_global == total_files or completed_count == len(batch_files):
                            elapsed = time.time() - start_time
                            avg_time = elapsed / completed_global if completed_global > 0 else 0
                            logger.info(f"Lite batch {batch_num}: completed {completed_count}/{len(batch_files)} files in {elapsed:.1f}s (avg: {avg_time:.1f}s/file)")
                            print(f"Lite Progress: {completed_global}/{total_files} files processed ({completed_global/total_files*100:.0f}%)")

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
                # Entire batch timed out - handle remaining stuck files
                logger.error(f"Lite batch {batch_num} timed out after {batch_timeout}s")
                print(f"Warning: Lite batch {batch_num} timed out! Processing remaining files...")
            
            # CRITICAL: Handle any remaining stuck/pending files that didn't complete
            pending_files = []
            for future, file_path in futures.items():
                if not future.done():
                    pending_files.append((future, file_path))
                    logger.warning(f"File still pending after batch timeout: {file_path.name}")
            
            if pending_files:
                print(f"Warning: {len(pending_files)} files are stuck. Forcing completion...")
                for future, file_path in pending_files:
                    try:
                        # Try to cancel the stuck future
                        future.cancel()
                        if not future.cancelled():
                            # If can't cancel, try one last quick result check
                            try:
                                result = future.result(timeout=2)  # Quick 2s check
                                results.append(result)
                                completed_count += 1
                                completed_global += 1
                                logger.info(f"Stuck file completed: {file_path.name}")
                                continue
                            except:
                                pass
                    except:
                        pass
                    
                    # Add error result for stuck file
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
                        "Status": "Error: File processing stuck/timeout"
                    })
                    completed_count += 1
                    completed_global += 1
                    print(f"Error: Marked stuck file as failed: {file_path.name}")
            
            # Ensure all files are accounted for
            if completed_count < len(batch_files):
                missing_count = len(batch_files) - completed_count
                logger.warning(f"Batch {batch_num}: Only {completed_count}/{len(batch_files)} files completed. {missing_count} files may be stuck.")
                print(f"Warning: {missing_count} files may not have completed properly")

        batch_time = time.time() - start_time
        logger.info(f"Lite batch {batch_num} completed in {batch_time:.1f}s")

        # Update progress and move to next batch
        if progress_callback:
            progress_callback(completed_global, total_files)
        
        i += len(batch_files)  # Move to next batch

    logger.info(f"All {total_files} files processed with lite analysis, {len(results)} results collected")
    return pd.DataFrame(results)


def process_single_file_lite(file_path: Path, additional_metadata: Optional[dict] = None, user_api_key: Optional[str] = None) -> dict:
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
        
        # Extract dialer name from file path folder structure
        dialer_name = extract_dialer_name_from_path(file_path)

        # Load audio file
        audio = AudioSegment.from_file(str(file_path))

        # Perform only lite detections
        releasing = releasing_detection(audio)
        late_hello = late_hello_detection(audio)

        # Derive a simple quality-based status for lite results
        # - If both detections are clean (No/No) -> Excellent
        # - If either detection is flagged (Yes)  -> Needs Training
        # - If both are flagged                    -> Critical
        if str(releasing).strip().lower() == "yes" and str(late_hello).strip().lower() == "yes":
            status = "Critical"
        elif str(releasing).strip().lower() == "yes" or str(late_hello).strip().lower() == "yes":
            status = "Needs Training"
        else:
            status = "Excellent"

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
            "Dialer Name": dialer_name,  # Extract from folder path
            "Agent Intro": "N/A",
            "Owner Name": "N/A",
            "Reason for Calling": "N/A",
            "Intro Score": "N/A",
            "Status": status,
            "File Name": file_path.name,
            "File Path": str(file_path)
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
        
        # Extract dialer name from file path even on error
        dialer_name = extract_dialer_name_from_path(file_path)

        return {
            "Agent Name": agent_name,
            "Phone Number": phone_number,
            "Timestamp": timestamp,
            "Disposition": disposition,
            "Releasing Detection": "Error",
            "Late Hello Detection": "Error",
            "Rebuttal Detection": "N/A",
            "Transcription": "N/A",
            "Dialer Name": dialer_name,  # Extract from folder path
            "Agent Intro": "N/A",
            "Owner Name": "N/A",
            "Reason for Calling": "N/A",
            "Intro Score": "N/A",
            "Status": f"Error: {str(e)}"
        }


# Per-user batch processor instances
_batch_processors: Dict[str, BatchProcessor] = {}
_batch_processor_lock = threading.Lock()

def get_batch_processor(username: Optional[str] = None) -> BatchProcessor:
    """
    Get or create a batch processor instance for a user.
    
    Args:
        username: Username for per-user isolation. If None, uses default instance.
        
    Returns:
        BatchProcessor instance for the user
    """
    global _batch_processors
    
    # Use default key if no username
    user_key = username or "__default__"
    
    if user_key not in _batch_processors:
        with _batch_processor_lock:
            if user_key not in _batch_processors:
                # Get worker allocation for this user
                if username:
                    try:
                        from backend.services.worker_pool_manager import get_worker_pool_manager
                        pool_manager = get_worker_pool_manager()
                        max_workers = pool_manager.get_workers_for_user(username)
                        logger.info(f"Creating BatchProcessor for user {username} with {max_workers} workers")
                    except Exception as e:
                        logger.warning(f"Could not get worker pool manager: {e}, using default workers")
                        max_workers = None
                else:
                    max_workers = None
                
                _batch_processors[user_key] = BatchProcessor(max_workers=max_workers)
                logger.info(f"Created BatchProcessor instance for {user_key}")
    
    return _batch_processors[user_key]

def batch_analyze_folder(folder_path: str, username: Optional[str] = None, user_api_key: Optional[str] = None, additional_metadata: Optional[dict] = None) -> pd.DataFrame:
    """
    Analyze all audio files in a folder and return results as pandas DataFrame.
    Uses optimized core audio processing with proper channel separation.
    
    Args:
        folder_path: Path to folder containing audio files
        username: Optional username for user-specific API key
        user_api_key: Optional user-specific AssemblyAI API key
    
    Returns:
        pandas.DataFrame: Analysis results with all detection columns
    """
    processor = get_batch_processor(username)
    results = processor.process_folder_parallel(folder_path, additional_metadata=additional_metadata, username=username, user_api_key=user_api_key)
    flagged_calls = convert_to_dataframe_format(results)
    return pd.DataFrame(flagged_calls)


def batch_analyze_folder_fast(folder_path: str, progress_callback: Optional[Callable] = None, additional_metadata: Optional[dict] = None, show_all_results: bool = False, use_async: bool = True, username: Optional[str] = None, user_api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Fast batch analysis with progress tracking and proper channel separation.
    Uses async processing (Phase 2 optimization) by default for better AssemblyAI concurrency.
    
    Args:
        folder_path: Path to folder containing audio files
        progress_callback: Optional callback function for progress updates (done, total)
        additional_metadata: Optional metadata to add to each result (e.g., dialer_name, date)
        show_all_results: If True, return all results instead of just flagged calls
        use_async: If True (default), use async processing for better concurrency. If False, use ThreadPoolExecutor.
        
    Returns:
        pandas DataFrame with analysis results
    """
    if use_async:
        # Use async processing (Phase 2 optimization)
        logger.info("Using async batch processing (Phase 2 optimization)")
        results = asyncio.run(_batch_processor.process_folder_async(folder_path, progress_callback, additional_metadata, username=username, user_api_key=user_api_key))
    else:
        # Use traditional ThreadPoolExecutor processing
        logger.info("Using ThreadPoolExecutor batch processing")
        results = _batch_processor.process_folder_parallel(folder_path, progress_callback, additional_metadata, username=username, user_api_key=user_api_key)
    
    if show_all_results:
        # Return all results as DataFrame for debugging, but apply proper column formatting
        return convert_all_to_dataframe_format(results)
    else:
        # Return only flagged calls (default behavior)
        flagged_calls = convert_to_dataframe_format(results)
        return pd.DataFrame(flagged_calls)
