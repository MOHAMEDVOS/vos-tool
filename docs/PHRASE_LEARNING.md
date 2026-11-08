# Phrase Learning Mechanism - Railway Deployment Guide

## 📚 Overview

The **Phrase Learning System** is an intelligent, self-improving component of the VOS Tool that automatically discovers and learns new rebuttal phrases from audio transcriptions. It uses semantic matching to identify potential phrases that should be added to the detection repository.

---

## 🎯 Purpose

The system automatically:
- **Discovers** new rebuttal phrases from real call transcripts
- **Tracks** semantic matches with confidence scores
- **Evaluates** phrase quality using multi-factor scoring
- **Auto-approves** high-confidence phrases (≥90% confidence)
- **Manages** a pending review queue for manual approval
- **Maintains** a repository of approved phrases for detection

---

## 🔄 How It Works

### 1. **Detection Phase** (During Audio Processing)

When audio is processed and transcribed:

```python
# Location: analyzer/rebuttal_detection.py
# During semantic matching detection:
1. Semantic matches are found using embeddings
2. Each match includes:
   - Phrase text
   - Category (e.g., "OTHER_PROPERTY_FAMILY")
   - Confidence score (0.0 - 1.0)
   - Context (surrounding transcript text)
3. Matches are tracked via: track_semantic_match()
```

**Flow:**
```
Audio File → Transcription → Semantic Matching → 
Track Semantic Match → Phrase Learning Manager
```

### 2. **Tracking Phase** (`track_semantic_match`)

**Location:** `lib/phrase_learning.py` - `track_semantic_match()`

**Process:**
1. **Validation:**
   - Confidence must be ≥ `confidence_threshold` (default: 0.85)
   - Phrase must be ≥ 3 characters
   - Filters out polite closings without sales content
   - Maximum length: 20 words or 200 characters

2. **Duplicate Prevention:**
   - Checks if phrase already exists in repository
   - Checks if phrase is blacklisted
   - Merges with existing pending phrase if duplicate found

3. **Quality Scoring:**
   - Calculates multi-factor quality score (0-1 scale):
     - **Confidence** (50%): Semantic match strength
     - **Frequency** (25%): Detection count (normalized)
     - **Recency** (15%): Time since last detection
     - **Context Quality** (10%): Richness of sample contexts

4. **Auto-Approval:**
   - If confidence ≥ 90% OR quality_score ≥ 90%: **Auto-approve immediately**
   - Otherwise: Add to pending queue for review

### 3. **Repository Management**

**Two Main Tables:**

#### `pending_phrases`
- Stores candidate phrases awaiting review
- Fields:
  - `phrase`: The candidate phrase text
  - `category`: Rebuttal category
  - `confidence`: Semantic match confidence
  - `detection_count`: How many times detected
  - `quality_score`: Calculated quality (0-1)
  - `status`: 'pending', 'approved', 'rejected', 'auto_approved'
  - `sample_contexts`: Example transcript snippets
  - `canonical_form`: Normalized version (filler words removed)

#### `repository_phrases`
- Stores approved phrases used for detection
- Fields:
  - `phrase`: Approved phrase text
  - `category`: Rebuttal category
  - `source`: 'manual', 'auto_learned', 'admin_approved', 'system_default'
  - `usage_count`: Times used in detection
  - `successful_detections`: Successful matches
  - `effectiveness_score`: Success rate

---

## 🗄️ Database Structure (PostgreSQL)

### Tables Created Automatically

```sql
-- Pending phrases (candidates for review)
CREATE TABLE pending_phrases (
    id UUID PRIMARY KEY,
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    detection_count INTEGER DEFAULT 1,
    first_detected TIMESTAMP WITH TIME ZONE,
    last_detected TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'pending',
    sample_contexts TEXT,
    similar_to TEXT,
    quality_score DECIMAL(5,4),
    canonical_form TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(phrase, category)
);

-- Approved phrases (active detection repository)
CREATE TABLE repository_phrases (
    id UUID PRIMARY KEY,
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    added_date TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    successful_detections INTEGER DEFAULT 0,
    effectiveness_score DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(phrase, category)
);

-- Learning settings (configurable thresholds)
CREATE TABLE phrase_learning_settings (
    id UUID PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Blacklist (rejected phrases)
CREATE TABLE phrase_blacklist (
    id UUID PRIMARY KEY,
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    rejected_date TIMESTAMP WITH TIME ZONE,
    reason TEXT,
    UNIQUE(phrase, category)
);

-- Performance tracking
CREATE TABLE category_performance (
    category VARCHAR(100) PRIMARY KEY,
    approval_rate DECIMAL(5,4),
    avg_quality_score DECIMAL(5,4),
    total_phrases INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE
);
```

---

## ⚙️ Configuration Settings

**Location:** `phrase_learning_settings` table

**Default Values:**
- `confidence_threshold`: **0.85** (minimum confidence to track)
- `frequency_threshold`: **5** (minimum detections before consideration)
- `auto_approve_threshold`: **0.95** (auto-approve above this)

**Adjustable via:**
- Frontend UI: `frontend/app_ai/ui/phrases.py`
- API: `update_settings()` method
- Database: Direct SQL update

---

## 🚂 Railway Deployment Considerations

### 1. **Database Connection**

The phrase learning system uses the **same PostgreSQL database** as the main application:

```python
# Uses shared database manager
from lib.database import get_db_manager
db_manager = get_db_manager()
```

**Railway Configuration:**
- Database URL: Set via `DATABASE_URL` environment variable
- Connection pooling: Managed by `lib.database`
- SSL: Required (`POSTGRES_SSLMODE=require`)

### 2. **Initialization**

**On First Startup:**
1. `PhraseLearningManager` initializes
2. Creates tables if they don't exist (`_init_database()`)
3. Loads settings from database
4. Syncs default phrases from `KeywordRepository` if repository is empty

**Code Flow:**
```python
# backend/core/database.py - init_db()
create_tables_if_needed(db)  # Creates all tables including phrase learning

# lib/phrase_learning.py - __init__()
self._init_database()  # Ensures phrase learning tables exist
self._load_settings()  # Loads thresholds from DB
self._init_repository()  # Syncs default phrases if empty
```

### 3. **Session Management**

**Railway Deployment:**
- Each Railway service instance has its own `PhraseLearningManager` instance
- Uses **connection pooling** for database access
- Thread-safe: Multiple requests can track phrases simultaneously
- No file-based storage: Everything in PostgreSQL

### 4. **Performance Optimizations**

**Caching:**
- Quality scores cached (1-hour TTL)
- Canonical forms cached
- Category thresholds cached (1-week TTL)
- Similarity cache for duplicate detection

**Database Operations:**
- Uses connection pooling (no per-request connections)
- Batch operations for auto-approval
- Lightweight duplicate cleanup before retrieval

---

## 🔍 Key Features

### 1. **Auto-Approval**

Phrases with **confidence ≥ 90%** are automatically approved:
- No manual review required
- Immediately added to repository
- Status set to `auto_approved`

### 2. **Quality Tiers**

Phrases are categorized by quality score:
- **Tier 1 (≥0.90)**: Auto-Approve
- **Tier 2 (≥0.80)**: High Value
- **Tier 3 (≥0.65)**: Medium Value
- **Tier 4 (<0.65)**: Low Value

### 3. **Duplicate Management**

- Automatic duplicate detection (normalized phrase text)
- Merges duplicates: combines detection counts and contexts
- Keeps highest confidence version

### 4. **Blacklist System**

- Rejected phrases are blacklisted
- Prevents re-tracking of known bad phrases
- Includes rejection reason

### 5. **Effectiveness Tracking**

- Tracks usage count for each phrase
- Tracks successful detections
- Calculates effectiveness score (success rate)

---

## 📊 Usage in Railway

### During Normal Operation

1. **Audio Processing:**
   ```
   User uploads audio → Backend processes → 
   Semantic matching finds phrases → 
   track_semantic_match() called → 
   Phrase added to pending_phrases (or auto-approved)
   ```

2. **Admin Review:**
   ```
   Admin opens Phrases UI → 
   Views pending phrases → 
   Approves/rejects phrases → 
   Approved phrases added to repository_phrases
   ```

3. **Detection:**
   ```
   New audio processed → 
   Repository phrases used for matching → 
   Effectiveness tracked → 
   System learns which phrases work best
   ```

### API Endpoints (if exposed)

The phrase learning system is primarily used internally, but can be accessed via:
- Frontend UI: `frontend/app_ai/ui/phrases.py`
- Direct Python: `get_phrase_learning_manager()`

---

## 🔧 Maintenance Operations

### Auto-Approve High Confidence Phrases

```python
manager = get_phrase_learning_manager()
result = manager.auto_approve_high_confidence_phrases(min_confidence=0.90)
```

### Approve by Quality Score

```python
result = manager.approve_by_quality_score(min_quality_score=0.90)
```

### Remove Duplicates

```python
result = manager.remove_duplicate_phrases()
```

### Get Statistics

```python
stats = manager.get_repository_stats()
# Returns: total_phrases, pending_count, auto_learned_count, categories, last_updated
```

---

## 🐛 Troubleshooting

### Phrases Not Being Tracked

1. **Check confidence threshold:**
   ```sql
   SELECT * FROM phrase_learning_settings;
   ```
   Ensure `confidence_threshold` is not too high

2. **Check database connection:**
   - Verify `DATABASE_URL` is set correctly
   - Check Railway logs for connection errors

3. **Check logs:**
   - Look for "Failed to track semantic match" errors
   - Verify phrase learning manager initialized

### Auto-Approval Not Working

1. **Check confidence scores:**
   ```sql
   SELECT phrase, confidence, quality_score, status 
   FROM pending_phrases 
   WHERE confidence >= 0.90 AND status = 'pending';
   ```

2. **Verify settings:**
   ```sql
   SELECT * FROM phrase_learning_settings;
   ```

### Duplicate Phrases

Run cleanup:
```python
manager = get_phrase_learning_manager()
result = manager.remove_duplicate_phrases()
```

---

## 📈 Monitoring

### Key Metrics to Track

1. **Pending Queue Size:**
   ```sql
   SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending';
   ```

2. **Auto-Learned Count:**
   ```sql
   SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned';
   ```

3. **Average Quality Score:**
   ```sql
   SELECT AVG(quality_score) FROM pending_phrases WHERE status = 'pending';
   ```

4. **Category Performance:**
   ```sql
   SELECT * FROM category_performance ORDER BY approval_rate DESC;
   ```

---

## 🔐 Security Considerations

1. **Database Access:**
   - Uses connection pooling (prevents connection exhaustion)
   - All queries use parameterized statements (SQL injection protection)

2. **Data Validation:**
   - Input sanitization (phrase length, content filtering)
   - Blacklist checking before tracking

3. **Railway-Specific:**
   - Environment variables for sensitive config
   - SSL required for database connections
   - No file-based storage (all in PostgreSQL)

---

## 📝 Summary

The Phrase Learning Mechanism is a **self-improving system** that:

✅ **Automatically discovers** new rebuttal phrases from real call data  
✅ **Evaluates quality** using multi-factor scoring  
✅ **Auto-approves** high-confidence phrases (≥90%)  
✅ **Manages review queue** for manual approval  
✅ **Tracks effectiveness** of learned phrases  
✅ **Works seamlessly** in Railway deployment using PostgreSQL  
✅ **Scales** with connection pooling and caching  

The system continuously improves the detection accuracy by learning from real-world usage patterns, making the VOS Tool more effective over time.

---

**Last Updated:** Based on codebase analysis of `lib/phrase_learning.py` and Railway deployment configuration.
