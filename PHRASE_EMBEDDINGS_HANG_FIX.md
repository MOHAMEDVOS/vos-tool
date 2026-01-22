# Fix: Phrase Embeddings Hang Issue

## Problem

The semantic model loads successfully but hangs on "Precomputing phrase embeddings" during initialization. This occurs when `KeywordRepository()` tries to query the database for learned phrases, which can hang due to:

1. **Connection pool exhaustion** - All database connections are in use
2. **Database connection timeout** - Slow or unresponsive database connection
3. **Deadlock** - Database query waiting indefinitely
4. **Missing database** - Database not yet initialized or unavailable

## Root Cause

In `models/manager.py` line 96, `KeywordRepository()` is created without `skip_database=True`, which causes it to immediately try to load learned phrases from the database via `_load_learned_phrases()`. This database query can hang during model initialization, blocking the entire startup process.

## Solution

### 1. Non-Blocking Learned Phrase Loading with Timeout

**File:** `models/manager.py`

**Change:** Implement a two-phase loading strategy:
1. Load hardcoded phrases immediately (fast, no DB dependency)
2. Try to load learned phrases with a timeout (5 seconds default)
3. If timeout/failure, proceed with hardcoded phrases and schedule background reload

```python
# Strategy: Load hardcoded phrases immediately, then try learned phrases with timeout
# Step 1: Load hardcoded phrases (fast, no DB)
repo_hardcoded = KeywordRepository(skip_database=True)
hardcoded_phrases = repo_hardcoded.get_all_phrases()

# Step 2: Try to load learned phrases with timeout (non-blocking)
learned_thread = threading.Thread(target=load_learned_phrases, daemon=True)
learned_thread.start()
learned_thread.join(timeout=5)  # 5 second timeout

# Step 3: Merge and compute embeddings
all_phrase_data = merge(hardcoded_phrases, learned_phrases)
```

**Why:** This ensures:
- ✅ **No hangs** - Hardcoded phrases load immediately, learned phrases have timeout
- ✅ **Learned phrases work** - If DB is available, learned phrases are included
- ✅ **Graceful fallback** - If DB is slow/unavailable, we still have working embeddings
- ✅ **Background reload** - If learned phrases timeout, they're loaded in background

### 2. Improved Error Handling

**File:** `analyzer/rebuttal_detection.py`

**Change:** Simplified the database query in `_load_learned_phrases()` to rely on the database manager's built-in timeout mechanism (30 seconds default, configurable via `DB_QUERY_TIMEOUT` environment variable).

**Why:** The database manager already has timeout support, so we don't need complex timeout logic. The key fix is using `skip_database=True` during initialization.

### 3. Reload Functionality

**File:** `models/manager.py`

**Change:** In `reload_semantic_embeddings()`, explicitly use `skip_database=False` to ensure newly learned phrases are included when reloading.

```python
# Don't skip database on reload - we want to include newly learned phrases
repo = KeywordRepository(skip_database=False)
```

**Why:** When reloading embeddings (after new phrases are learned), we want to include them, so we don't skip the database.

## Impact

### Before Fix:
- Model initialization hangs on "Precomputing phrase embeddings"
- Application startup blocked indefinitely
- No fallback mechanism
- Learned phrases may not be included if DB is slow

### After Fix:
- ✅ **No hangs** - Model initialization completes quickly (max 5s wait for learned phrases)
- ✅ **Learned phrases always work** - Included when DB is available, loaded in background if timeout
- ✅ **Graceful fallback** - Works with hardcoded phrases even if DB is unavailable
- ✅ **Background reload** - Learned phrases loaded automatically after startup if they timed out
- ✅ **Non-blocking** - Startup never blocked by database issues

## Testing

To verify the fix:

1. **Start the application** - Should complete initialization without hanging
2. **Check logs** - Should see:
   ```
   [SINGLETON] Precomputing phrase embeddings...
   [SINGLETON] Fetching phrases from library...
   [SINGLETON] Fetched phrases in X.XXs
   [SINGLETON] Encoding X phrases...
   [SINGLETON] Encoding finished in X.XXs
   ```

3. **Verify learned phrases are still loaded** - When detection runs, learned phrases should be available (loaded on-demand, not during initialization)

## Configuration

### Environment Variables

- `LEARNED_PHRASES_LOAD_TIMEOUT` - Timeout for loading learned phrases during initialization (default: 5 seconds)
- `REBUTTAL_DB_CACHE_SECONDS` - Cache duration for learned phrases (default: 300 seconds)
- `DB_QUERY_TIMEOUT` - Database query timeout in milliseconds (default: 30000 = 30 seconds)

## Notes

- **Hardcoded phrases** are always available immediately (loaded from `REBUTTAL_PHRASES` dictionary)
- **Learned phrases** are loaded with a 5-second timeout during initialization
- **If timeout occurs**: Learned phrases are loaded in background after startup completes
- **Caching** prevents repeated database queries (5-minute cache by default)
- **Fallback** to JSON file if database is unavailable
- **Learned phrases always work** - Either loaded during init (if fast) or in background (if slow)

## Related Files

- `models/manager.py` - Semantic model initialization
- `analyzer/rebuttal_detection.py` - KeywordRepository and phrase loading
- `lib/database.py` - Database connection and query execution

## Future Improvements

1. Consider async database queries for non-blocking phrase loading
2. Add metrics/monitoring for phrase loading performance
3. Implement progressive loading (hardcoded first, learned phrases in background)

---

**Status:** ✅ Fixed  
**Date:** 2026-01-21  
**Priority:** High (blocks application startup)
