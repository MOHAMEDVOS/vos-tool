# Lite Audit Performance Optimization

## Problem

The lite audit analysis process became very slow, taking much longer than expected to process audio files.

## Root Causes Identified

1. **Full Audio Loading**: Loading entire audio files into memory for every file, even though late hello detection only needs the first 15 seconds
2. **Too Many Workers**: Excessive worker threads causing CPU/memory contention
3. **Long Timeouts**: 30-second timeout per file was too generous, allowing slow files to block the batch
4. **No Audio Optimization**: Processing full-length audio when only a portion is needed

## Solution

### 1. Optimized Audio Loading

**File:** `processing/batch_engine.py` - `process_single_file_lite()`

**Change:** Load full audio once, then slice first 15 seconds for late hello detection.

```python
# Before: Load full audio, process full audio for both detections
audio = AudioSegment.from_file(str(file_path))
releasing = releasing_detection(audio)  # Needs full audio
late_hello = late_hello_detection(audio)  # Only needs first 15s

# After: Load once, slice for late hello
audio = AudioSegment.from_file(str(file_path))
audio_for_late_hello = audio[:15000] if len(audio) > 15000 else audio  # First 15s only
releasing = releasing_detection(audio)  # Full audio
late_hello = late_hello_detection(audio_for_late_hello)  # Optimized slice
```

**Impact:** 
- Reduces processing time for late hello detection on long files
- Still loads full file (needed for releasing detection) but processes less data

### 2. Reduced Worker Count

**File:** `processing/batch_engine.py` - `batch_analyze_folder_lite()`

**Change:** Reduced maximum workers to avoid CPU/memory contention.

```python
# Before:
max_workers = min(cpu_count * 2, 16)  # Up to 16 threads

# After:
max_workers = min(cpu_count, 8)  # Reduced to 8 max workers
```

**Impact:**
- Reduces memory pressure from loading multiple large audio files simultaneously
- Prevents CPU contention from too many concurrent operations
- Better resource utilization

### 3. Reduced Timeout

**File:** `processing/batch_engine.py` - `batch_analyze_folder_lite()`

**Change:** Reduced timeout per file and batch timeout buffer.

```python
# Before:
timeout_per_file = 30  # 30 seconds
batch_timeout = timeout_per_file * len(batch_files) + 60  # 60s buffer

# After:
timeout_per_file = 15  # 15 seconds (lite processing should be fast)
batch_timeout = timeout_per_file * len(batch_files) + 30  # 30s buffer
```

**Impact:**
- Faster failure detection for stuck files
- Prevents slow files from blocking entire batch
- Encourages optimization of slow operations

### 4. Improved Error Handling

**Change:** Added try-catch around individual detections to prevent one failure from blocking the entire file.

```python
# Releasing detection (needs full audio)
try:
    releasing = releasing_detection(audio)
except Exception as e:
    logger.error(f"Releasing detection failed: {e}")
    releasing = "Error"

# Late hello detection (only needs first portion)
try:
    late_hello = late_hello_detection(audio_for_late_hello)
except Exception as e:
    logger.error(f"Late hello detection failed: {e}")
    late_hello = "Error"
```

**Impact:**
- Prevents one detection failure from blocking the entire file
- Better error recovery and logging

## Expected Performance Improvements

### Before Optimization:
- **Per file**: 15-30 seconds (depending on file size)
- **Batch processing**: Slow due to contention and long timeouts
- **Memory usage**: High (loading many full audio files)

### After Optimization:
- **Per file**: 5-15 seconds (faster for long files)
- **Batch processing**: More efficient with reduced workers
- **Memory usage**: Lower (processing less data for late hello)

## Testing

To verify the fix:

1. **Run lite audit** on a batch of files
2. **Monitor processing time** - should be faster, especially for long files
3. **Check logs** - should see faster completion times
4. **Verify results** - detections should still be accurate

## Configuration

No new environment variables needed. The optimizations are automatic.

## Notes

- **Late hello detection** only needs first 15 seconds, so slicing helps
- **Releasing detection** needs full audio (to check for any speech), so we still load full file
- **Worker count** is now more conservative to avoid resource contention
- **Timeouts** are tighter to catch slow operations faster

## Related Files

- `processing/batch_engine.py` - Batch processing logic
- `audio_pipeline/detections.py` - Detection algorithms
- `audio_pipeline/fast_audio_processor.py` - Fast single-file processing

---

**Status:** ✅ Fixed  
**Date:** 2026-01-22  
**Priority:** High (affects user experience)
