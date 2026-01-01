# Implementation Guide: Optimize 500 Calls Processing

## Overview

This guide explains step-by-step how to implement the performance optimizations to process 500 calls faster.

**Current estimate**: ~78 minutes for 500 calls  
**Target estimate**: ~60-65 minutes (20-25% improvement)

---

## Phase 1: Quick Wins (Start Here - ~30 minutes)

### Step 1.1: Parallelize Releasing + Late Hello Detections

**File**: `audio_pipeline/audio_processor.py`  
**Location**: `classify_call()` method, lines 143-161

**Current Code** (Sequential - slow):
```python
# Step 1: Releasing detection (~0.5-1s)
rel_start = time.time()
result['releasing_detection'] = releasing_detection(agent_audio)
rel_time = time.time() - rel_start

# Step 2: Late hello detection (~0.5-1s) - WAITS for step 1
late_start = time.time()
result['late_hello_detection'] = late_hello_detection(agent_audio, file_name)
late_time = time.time() - late_start

# Step 3: Rebuttal detection (~30-60s) - WAITS for steps 1-2
detection_result = agent_detector.detect_rebuttals_in_audio(temp_file)
```

**Optimized Code** (Parallel - faster):
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# Run releasing and late hello in parallel (they don't depend on each other)
rel_start = time.time()
late_start = time.time()

with ThreadPoolExecutor(max_workers=2) as executor:
    future_releasing = executor.submit(releasing_detection, agent_audio)
    future_late_hello = executor.submit(late_hello_detection, agent_audio, file_name)
    
    # Get results (both complete in ~max(0.5s, 0.5s) = ~0.5-1s instead of ~1-2s)
    try:
        result['releasing_detection'] = future_releasing.result()
    except Exception as rel_error:
        logger.error(f"Releasing detection failed: {rel_error}")
        result['releasing_detection'] = 'Error'
    
    try:
        result['late_hello_detection'] = future_late_hello.result()
    except Exception as late_error:
        logger.error(f"Late hello detection failed: {late_error}")
        result['late_hello_detection'] = 'Error'

rel_time = time.time() - rel_start
late_time = time.time() - late_start
logger.info(f"Releasing detection completed in {rel_time:.2f}s: {result['releasing_detection']}")
logger.info(f"Late hello detection completed in {late_time:.2f}s: {result['late_hello_detection']}")
```

**Expected improvement**: Save ~1-2 seconds per file = **~8-17 minutes for 500 files**

---

### Step 1.2: Start AssemblyAI Transcription Earlier

**File**: `audio_pipeline/audio_processor.py`  
**Location**: `classify_call()` method, lines 163-192

**Current Flow**:
1. Releasing detection (0.5s)
2. Late hello detection (0.5s)
3. **THEN** start AssemblyAI transcription (30-60s)

**Problem**: AssemblyAI API call waits for local detections to finish

**Optimized Flow**:
1. Start AssemblyAI transcription **immediately** (non-blocking)
2. Run releasing + late hello in parallel **while** AssemblyAI processes
3. AssemblyAI completes around the same time as local detections

**Implementation**:
```python
# Prepare temp file for AssemblyAI early
import tempfile
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
    agent_audio.export(tmp.name, format="wav", parameters=["-ac", "1", "-ar", "16000"])
    temp_file = tmp.name

# Start ALL three operations in parallel
with ThreadPoolExecutor(max_workers=3) as executor:
    # Submit all three tasks simultaneously
    future_releasing = executor.submit(releasing_detection, agent_audio)
    future_late_hello = executor.submit(late_hello_detection, agent_audio, file_name)
    future_rebuttal = executor.submit(agent_detector.detect_rebuttals_in_audio, temp_file)
    
    # Collect results as they complete
    try:
        result['releasing_detection'] = future_releasing.result()
    except Exception as rel_error:
        logger.error(f"Releasing detection failed: {rel_error}")
        result['releasing_detection'] = 'Error'
    
    try:
        result['late_hello_detection'] = future_late_hello.result()
    except Exception as late_error:
        logger.error(f"Late hello detection failed: {late_error}")
        result['late_hello_detection'] = 'Error'
    
    # Rebuttal detection (includes AssemblyAI transcription)
    try:
        detection_result = future_rebuttal.result()
        result['rebuttal_detection'] = {
            'result': detection_result['result'],
            'confidence_score': detection_result['confidence_score'],
            'transcript': detection_result['transcript']
        }
    except Exception as reb_error:
        logger.error(f"Agent-only rebuttal detection failed: {reb_error}")
        result['rebuttal_detection'] = {'result': 'Error', 'transcript': ''}
    finally:
        try:
            os.unlink(temp_file)
        except Exception:
            pass
```

**Expected improvement**: Save ~2-3 seconds per file = **~17-25 minutes for 500 files**

**Total Phase 1 improvement**: ~25-42 minutes saved (32-54% faster)

---

## Phase 2: Async Optimization (If More Speed Needed)

### Step 2.1: Check AssemblyAI SDK for Async Support

**Action**: Review AssemblyAI Python SDK documentation
- Check if `assemblyai` package has async methods
- Look for `transcribe_async()` or similar

**If async available**:
```python
# In lib/assemblyai_transcription.py
async def transcribe_file_async(self, audio_file_path: str, ...):
    transcript = await self.transcriber.transcribe_async(audio_file_path, config=config)
    return result
```

**If async NOT available** (wrap in executor):
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def transcribe_file_async(self, audio_file_path: str, ...):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        transcript = await loop.run_in_executor(
            executor,
            self.transcriber.transcribe,
            audio_file_path,
            config
        )
    return result
```

### Step 2.2: Convert Batch Processing to Async

**File**: `processing/batch_engine.py`

**Create new async method**:
```python
import asyncio

async def process_folder_async(
    self, 
    folder_path: str, 
    progress_callback: Optional[Callable] = None,
    additional_metadata: Optional[dict] = None
) -> List[dict]:
    """Async version of process_folder_parallel."""
    audio_files = self.find_audio_files(folder_path)
    
    if not audio_files:
        return []
    
    # Semaphore to limit concurrent AssemblyAI calls (5 for free account)
    semaphore = asyncio.Semaphore(self.max_workers)
    
    async def process_with_limit(file_path):
        async with semaphore:
            # Process file asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default executor
                self.audio_processor.process_single_file,
                file_path,
                additional_metadata,
                False
            )
            return result
    
    # Process all files concurrently (respecting semaphore)
    tasks = [process_with_limit(f) for f in audio_files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions
    valid_results = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Processing failed: {r}")
        else:
            valid_results.append(r)
    
    return valid_results
```

**Expected improvement**: ~10-15% faster = **~8-12 minutes saved**

---

## Testing Steps

### 1. Baseline Measurement
```python
# Process 10 files, measure time
import time
start = time.time()
results = batch_analyze_folder_fast("test_folder_with_10_files")
elapsed = time.time() - start
print(f"Baseline: {elapsed/10:.2f} seconds per file")
```

### 2. After Phase 1 Optimization
```python
# Process same 10 files, compare
start = time.time()
results = batch_analyze_folder_fast("test_folder_with_10_files")
elapsed = time.time() - start
print(f"Optimized: {elapsed/10:.2f} seconds per file")
print(f"Improvement: {baseline_time - elapsed:.2f} seconds total")
```

### 3. Scale Test (50 files)
- Process 50 files
- Monitor for errors
- Check for rate limit issues
- Verify all files complete successfully

### 4. Full Test (500 files)
- Process 500 files
- Monitor performance metrics
- Check for any bottlenecks
- Verify final time matches estimate

---

## Expected Results

### Current Performance
- **500 files**: ~78 minutes
- **Per file**: ~47 seconds average

### After Phase 1 (Quick Wins)
- **500 files**: ~50-55 minutes
- **Per file**: ~36-40 seconds average
- **Improvement**: ~25-30 minutes faster (32-38% improvement)

### After Phase 2 (Async - if implemented)
- **500 files**: ~45-50 minutes
- **Per file**: ~32-36 seconds average
- **Improvement**: ~30-35 minutes faster (38-45% improvement)

---

## Implementation Checklist

### Phase 1: Quick Wins
- [ ] Step 1.1: Parallelize releasing + late hello detections
- [ ] Step 1.2: Start AssemblyAI transcription earlier
- [ ] Test with 10 files
- [ ] Test with 50 files
- [ ] Test with 500 files

### Phase 2: Async (Optional)
- [ ] Check AssemblyAI SDK for async support
- [ ] Create async transcription wrapper
- [ ] Convert batch processing to async
- [ ] Test with 10 files
- [ ] Test with 50 files
- [ ] Test with 500 files

---

## Important Notes

1. **AssemblyAI Free Account Limit**: Never exceed 5 concurrent jobs
2. **Error Handling**: Keep robust error handling for API failures
3. **Timeouts**: Keep 600s timeout per file (safety margin)
4. **Testing**: Always test with small batches before full 500-file run
5. **Monitoring**: Watch for rate limit errors (429 status codes)

---

## Quick Start

**To implement Phase 1 (recommended first step)**:

1. Open `audio_pipeline/audio_processor.py`
2. Find `classify_call()` method (line 122)
3. Replace sequential detection code (lines 143-192) with parallel version
4. Test with 10 files
5. Compare times before/after

**Estimated time**: 30 minutes to implement and test

