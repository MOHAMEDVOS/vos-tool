"""
Phrase Learning System for VOS Tool
Handles automatic learning and management of rebuttal phrases.
"""

import json
import sqlite3
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

# Try to import database manager for PostgreSQL support
try:
    from lib.database import get_db_manager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    get_db_manager = None
    logging.warning("Database manager not available - will use SQLite only")

logger = logging.getLogger(__name__)

class PhraseLearningManager:
    """Manages the self-learning phrase system."""
    
    def __init__(self):
        self.data_dir = Path("dashboard_data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.db_path = self.data_dir / "phrase_learning.db"
        self.repository_path = self.data_dir / "rebuttal_repository.json"
        self.settings_path = self.data_dir / "phrase_learning_settings.json"
        
        # Check if PostgreSQL is available and should be used
        self.use_postgresql = False
        self.db_manager = None
        if DB_AVAILABLE:
            try:
                db_type = os.getenv('DB_TYPE', '').lower()
                if db_type == 'postgresql':
                    self.db_manager = get_db_manager()
                    if self.db_manager:
                        self.use_postgresql = True
                        logger.info("Using PostgreSQL for phrase management")
            except Exception as e:
                logger.warning(f"Could not initialize PostgreSQL, falling back to SQLite: {e}")
        
        if not self.use_postgresql:
            logger.info("Using SQLite for phrase management")
        
        # Load settings from file or use defaults
        self._load_settings()
        
        # Cache for performance optimization
        self._quality_score_cache = {}
        self._canonical_form_cache = {}
        self._similarity_cache = {}
        self._category_thresholds_cache = {}
        
        self._init_database()
        self._init_repository()
    
    def _load_settings(self):
        """Load settings from file or use defaults."""
        default_settings = {
            'confidence_threshold': 0.85,  # Minimum confidence for auto-learning
            'frequency_threshold': 5,      # Minimum detections before consideration
            'auto_approve_threshold': 0.95 # Auto-approve above this confidence
        }
        
        try:
            if self.settings_path.exists():
                with open(self.settings_path, 'r') as f:
                    saved_settings = json.load(f)
                
                # Use saved settings with fallback to defaults
                self.confidence_threshold = saved_settings.get('confidence_threshold', default_settings['confidence_threshold'])
                self.frequency_threshold = saved_settings.get('frequency_threshold', default_settings['frequency_threshold'])
                self.auto_approve_threshold = saved_settings.get('auto_approve_threshold', default_settings['auto_approve_threshold'])
                
                logger.info(f"Loaded settings from file: confidence={self.confidence_threshold}, "
                           f"frequency={self.frequency_threshold}, auto_approve={self.auto_approve_threshold}")
            else:
                # Use defaults and save them
                self.confidence_threshold = default_settings['confidence_threshold']
                self.frequency_threshold = default_settings['frequency_threshold']
                self.auto_approve_threshold = default_settings['auto_approve_threshold']
                
                self._save_settings()
                logger.info("Created default settings file")
                
        except Exception as e:
            logger.error(f"Failed to load settings, using defaults: {e}")
            self.confidence_threshold = default_settings['confidence_threshold']
            self.frequency_threshold = default_settings['frequency_threshold']
            self.auto_approve_threshold = default_settings['auto_approve_threshold']
    
    def _save_settings(self):
        """Save current settings to file."""
        try:
            settings = {
                'confidence_threshold': self.confidence_threshold,
                'frequency_threshold': self.frequency_threshold,
                'auto_approve_threshold': self.auto_approve_threshold,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            
            logger.info(f"Settings saved to file: {self.settings_path}")
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            
    def auto_approve_high_confidence_phrases(self, min_confidence: float = 0.9) -> dict:
        """
        Automatically approve phrases with confidence >= min_confidence.
        Returns dict with stats about the operation.
        """
        stats = {
            'total_approved': 0,
            'total_skipped': 0,
            'errors': []
        }
        
        try:
            with self._get_db_connection() as conn:
                # Get all pending phrases with confidence >= min_confidence
                cursor = conn.cursor()
                
                # First, get the count of phrases that will be auto-approved
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM pending_phrases 
                    WHERE confidence >= ? 
                    AND status = 'pending'
                """, (min_confidence,))
                total_to_approve = cursor.fetchone()[0]
                
                if total_to_approve == 0:
                    return {
                        'success': True,
                        'message': 'No phrases found with confidence >= 90%',
                        'stats': stats
                    }
                
                # Check if source column exists
                cursor.execute("PRAGMA table_info(pending_phrases)")
                columns = [column[1] for column in cursor.fetchall()]
                has_source = 'source' in columns
                
                # Build query based on available columns
                if has_source:
                    cursor.execute("""
                        SELECT id, phrase, confidence, category, source
                        FROM pending_phrases 
                        WHERE confidence >= ? 
                        AND status = 'pending'
                    """, (min_confidence,))
                    phrases = [(row[0], row[1], row[2], row[3], row[4]) for row in cursor.fetchall()]
                else:
                    cursor.execute("""
                        SELECT id, phrase, confidence, category
                        FROM pending_phrases 
                        WHERE confidence >= ? 
                        AND status = 'pending'
                    """, (min_confidence,))
                    phrases = [(row[0], row[1], row[2], row[3], 'auto_approved') for row in cursor.fetchall()]
                
                # Process each phrase
                for phrase_id, phrase_text, confidence, category, source in phrases:
                    try:
                        # Check if phrase already exists in repository
                        already_in_repo = self._phrase_exists_in_repository(phrase_text, category or 'general')
                        
                        # Add to repository (will skip if already exists, but that's OK)
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='auto_approved'  # Using auto_approved as the source for auto-approved phrases
                        )
                        
                        # Update status to approved regardless of whether it was already in repository
                        # (if it's already in repo, we still want to mark it as approved in pending)
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET status = 'approved'
                            WHERE id = ?
                        """, (phrase_id,))
                        
                        if success:
                            stats['total_approved'] += 1
                        elif already_in_repo:
                            # Already in repository, but we marked it as approved
                            stats['total_approved'] += 1
                        else:
                            stats['total_skipped'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': f"Auto-approved {stats['total_approved']} phrases with confidence >= {min_confidence*100:.0f}%",
                    'stats': stats
                }
                
        except Exception as e:
            error_msg = f"Error in auto-approval process: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'stats': stats
            }
    
    def _get_db_connection(self, timeout: int = 30, retries: int = 3):
        """Get database connection with retry logic and proper timeout."""
        if self.use_postgresql and self.db_manager:
            # Return PostgreSQL connection from pool
            try:
                conn = self.db_manager.connection_pool.getconn()
                if conn:
                    return conn
            except Exception as e:
                logger.error(f"Failed to get PostgreSQL connection: {e}")
                raise
        
        # Fallback to SQLite
        for attempt in range(retries):
            try:
                conn = sqlite3.connect(
                    self.db_path, 
                    timeout=timeout,
                    isolation_level=None  # Autocommit mode
                )
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=268435456")  # 256MB
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retries - 1:
                    logger.warning(f"Database locked, retrying in {0.1 * (attempt + 1)}s (attempt {attempt + 1}/{retries})")
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise
        raise sqlite3.OperationalError("Failed to acquire database lock after retries")
    
    def _return_db_connection(self, conn):
        """Return database connection to pool (PostgreSQL) or close (SQLite)."""
        if self.use_postgresql and self.db_manager and hasattr(self.db_manager, 'connection_pool'):
            try:
                self.db_manager.connection_pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error returning PostgreSQL connection: {e}")
        else:
            # SQLite - close connection
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing SQLite connection: {e}")
    
    def _init_database(self):
        """Initialize the phrase learning database."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
            
            if self.use_postgresql:
                # PostgreSQL table creation
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_phrases (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        phrase TEXT NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        confidence DECIMAL(5,4) NOT NULL,
                        detection_count INTEGER DEFAULT 1,
                        first_detected TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        last_detected TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(50) DEFAULT 'pending',
                        sample_contexts TEXT,
                        similar_to TEXT,
                        quality_score DECIMAL(5,4),
                        canonical_form TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(phrase, category)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS repository_phrases (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        phrase TEXT NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        source VARCHAR(50) DEFAULT 'manual',
                        added_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        successful_detections INTEGER DEFAULT 0,
                        effectiveness_score DECIMAL(5,4),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(phrase, category)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS phrase_learning_settings (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        setting_key VARCHAR(100) UNIQUE NOT NULL,
                        setting_value TEXT,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS phrase_blacklist (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        phrase TEXT NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        rejected_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        reason TEXT,
                        UNIQUE(phrase, category)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_performance (
                        category VARCHAR(100) PRIMARY KEY,
                        approval_rate DECIMAL(5,4),
                        avg_quality_score DECIMAL(5,4),
                        total_phrases INTEGER DEFAULT 0,
                        last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
            else:
                # SQLite table creation (original code)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_phrases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phrase TEXT NOT NULL,
                        category TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        detection_count INTEGER DEFAULT 1,
                        first_detected DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_detected DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        sample_contexts TEXT,
                        similar_to TEXT,
                        UNIQUE(phrase, category)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS repository_phrases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phrase TEXT NOT NULL,
                        category TEXT NOT NULL,
                        source TEXT DEFAULT 'manual',
                        added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        successful_detections INTEGER DEFAULT 0,
                        effectiveness_score REAL,
                        UNIQUE(phrase, category)
                    )
                """)
                
                # Add columns if they don't exist (for existing databases)
                try:
                    conn.execute("ALTER TABLE repository_phrases ADD COLUMN successful_detections INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    conn.execute("ALTER TABLE repository_phrases ADD COLUMN effectiveness_score REAL")
                except sqlite3.OperationalError:
                    pass
                
                # Create category performance cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS category_performance (
                        category TEXT PRIMARY KEY,
                        approval_rate REAL,
                        avg_quality_score REAL,
                        total_phrases INTEGER DEFAULT 0,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS phrase_blacklist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phrase TEXT NOT NULL,
                        category TEXT NOT NULL,
                        rejected_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        reason TEXT,
                        UNIQUE(phrase, category)
                    )
                """)
                
                # Add new columns if they don't exist (for existing databases)
                try:
                    conn.execute("ALTER TABLE pending_phrases ADD COLUMN quality_score REAL")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                try:
                    conn.execute("ALTER TABLE pending_phrases ADD COLUMN canonical_form TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                try:
                    conn.execute("ALTER TABLE repository_phrases ADD COLUMN successful_detections INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                try:
                    conn.execute("ALTER TABLE repository_phrases ADD COLUMN effectiveness_score REAL")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                # Create indexes for performance
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_quality_score ON pending_phrases(quality_score)")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_canonical_form ON pending_phrases(canonical_form)")
                except sqlite3.OperationalError:
                    pass
                
                # Create category performance cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS category_performance (
                        category TEXT PRIMARY KEY,
                        approval_rate REAL,
                        avg_quality_score REAL,
                        total_phrases INTEGER DEFAULT 0,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                logger.info("Phrase learning database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize phrase learning database: {e}")
    
    def rebuild_repository_from_existing(self) -> bool:
        """Rebuild repository by merging existing KeywordRepository with approved phrases."""
        try:
            from analyzer.rebuttal_detection import KeywordRepository
            keyword_repo = KeywordRepository()
            base_phrases = keyword_repo.get_all_phrases()
            
            # Get current repository to preserve approved phrases
            current_repository = {}
            if self.repository_path.exists():
                try:
                    with open(self.repository_path, 'r') as f:
                        current_repository = json.load(f)
                except:
                    current_repository = {}
            
            # Merge base phrases with current approved phrases
            merged_phrases = {}
            
            # Start with base KeywordRepository phrases
            for category, phrases in base_phrases.items():
                merged_phrases[category] = list(phrases)  # Copy base phrases
            
            # Add any approved phrases from current repository
            current_phrases = current_repository.get("phrases", {})
            for category, phrases in current_phrases.items():
                if category not in merged_phrases:
                    merged_phrases[category] = []
                
                # Add phrases that aren't already in the base repository
                for phrase in phrases:
                    if phrase not in merged_phrases[category]:
                        merged_phrases[category].append(phrase)
                        logger.info(f"Preserved approved phrase: '{phrase}' in {category}")
            
            # Create updated repository
            updated_repository = {
                "version": "2.0.0",
                "last_updated": datetime.now().isoformat(),
                "auto_added_count": current_repository.get("auto_added_count", 0),  # Preserve count
                "phrases": merged_phrases
            }
            
            # Save to file
            with open(self.repository_path, 'w') as f:
                json.dump(updated_repository, f, indent=2)
            
            total_phrases = sum(len(phrases) for phrases in merged_phrases.values())
            base_count = sum(len(phrases) for phrases in base_phrases.values())
            approved_count = total_phrases - base_count
            
            logger.info(f"Repository rebuilt: {base_count} base + {approved_count} approved = {total_phrases} total phrases")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rebuild repository: {e}")
            return False
    
    def _init_repository(self):
        """Initialize the rebuttal repository file if it doesn't exist."""
        if not self.repository_path.exists():
            logger.info("Repository file doesn't exist, creating with all existing phrases...")
            # Force rebuild with all existing phrases
            if not self.rebuild_repository_from_existing():
                logger.warning("Failed to import existing phrases, creating minimal repository")
                # Fallback to minimal set if import fails
                default_repository = {
                    "version": "1.0.0",
                    "last_updated": datetime.now().isoformat(),
                    "auto_added_count": 0,
                    "phrases": {
                        "OTHER_PROPERTY_FAMILY": [
                            "do you have any other property",
                            "any other properties",
                            "do you have another house",
                            "any other houses to sell"
                        ],
                        "NOT_EVEN_FUTURE_FAMILY": [
                            "not even in the future",
                            "not even in the near future",
                            "never in the future",
                            "maybe next year"
                        ],
                        "MIXED_FUTURE_OTHER_FAMILY": [
                            "maybe other properties in the future",
                            "different houses later"
                        ],
                        "CALLBACK_SCHEDULE_FAMILY": [
                            "when should I call you back",
                            "what's the best time to call",
                            "when would be better"
                        ]
                    }
                }
                
                with open(self.repository_path, 'w') as f:
                    json.dump(default_repository, f, indent=2)
                
                logger.info("Created minimal rebuttal repository")
    
    def track_semantic_match(self, phrase: str, category: str, confidence: float, 
                           context: str = "", similar_to: str = ""):
        """Track a semantic match for potential learning."""
        try:
            # Skip if confidence is too low
            if confidence < self.confidence_threshold:
                return

            clean_phrase = (phrase or "").lower().strip()
            clean_category = (category or "").strip()

            # Basic validation: non-empty and minimum length
            if not clean_phrase or len(clean_phrase) < 3:
                return

            # Skip phrases that are just polite closings with no sales content
            lower = clean_phrase
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
                "future",
            ]

            if any(k in lower for k in closing_keywords) and not any(k in lower for k in content_keywords):
                return

            # Enforce maximum length for auto-learned phrases
            words = clean_phrase.split()
            if len(words) > 20 or len(clean_phrase) > 200:
                words = words[:20]
                clean_phrase = " ".join(words)[:200].strip()

            # Skip if phrase is blacklisted
            if self._is_blacklisted(clean_phrase, clean_category):
                return
            
            # Skip if phrase already exists in repository
            if self._phrase_exists_in_repository(clean_phrase, clean_category):
                return
            
            with self._get_db_connection() as conn:
                # Check for duplicate by phrase text ONLY (normalized, case-insensitive) - not category
                normalized_phrase = clean_phrase.lower().strip()
                cursor = conn.execute("""
                    SELECT id, detection_count, confidence, sample_contexts, category
                    FROM pending_phrases 
                    WHERE LOWER(TRIM(phrase)) = ? AND status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                    LIMIT 1
                """, (normalized_phrase,))
                existing = cursor.fetchone()
                
                if existing:
                    # Merge into existing entry (auto-prevent duplicate)
                    phrase_id, count, existing_conf, existing_ctx, existing_cat = existing
                    new_count = count + 1
                    new_confidence = max(existing_conf, confidence)
                    # Merge contexts
                    existing_context = existing_ctx or ""
                    new_context = context[:500] or ""
                    if existing_context and new_context:
                        merged_context = existing_context + " | " + new_context
                    elif existing_context:
                        merged_context = existing_context
                    else:
                        merged_context = new_context
                    merged_context = merged_context[:500]  # Limit to 500 chars
                    
                    # Calculate quality score for merged phrase
                    merged_phrase_data = {
                        'id': phrase_id,
                        'confidence': new_confidence,
                        'detection_count': new_count,
                        'last_detected': datetime.now().isoformat(),
                        'sample_contexts': merged_context
                    }
                    quality_score = self.calculate_quality_score(merged_phrase_data)
                    canonical_form = self.normalize_to_canonical(clean_phrase)
                    
                    conn.execute("""
                        UPDATE pending_phrases 
                        SET detection_count = ?, confidence = ?, 
                            last_detected = CURRENT_TIMESTAMP,
                            sample_contexts = ?,
                            quality_score = ?,
                            canonical_form = ?
                        WHERE id = ?
                    """, (new_count, new_confidence, merged_context, quality_score, canonical_form, phrase_id))
                    
                    # Check if it should be auto-approved (use merged confidence)
                    # High Priority (confidence ≥ 90%): Auto-approve immediately, no frequency requirement
                    if new_confidence >= 0.90:
                        self._auto_approve_phrase(phrase_id, clean_phrase, existing_cat)
                    elif (new_confidence >= self.auto_approve_threshold and 
                          new_count >= self.frequency_threshold):
                        # Lower confidence: Use existing threshold and frequency requirements
                        self._auto_approve_phrase(phrase_id, clean_phrase, existing_cat)
                        
                else:
                    # Calculate quality score and canonical form for new phrase
                    new_phrase_data = {
                        'confidence': confidence,
                        'detection_count': 1,
                        'last_detected': datetime.now().isoformat(),
                        'sample_contexts': context[:500]
                    }
                    quality_score = self.calculate_quality_score(new_phrase_data)
                    canonical_form = self.normalize_to_canonical(clean_phrase)
                    
                    # Insert new pending phrase
                    phrase_id = None
                    cursor = conn.execute("""
                        INSERT INTO pending_phrases 
                        (phrase, category, confidence, sample_contexts, similar_to, quality_score, canonical_form)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (clean_phrase, clean_category, confidence, context[:500], similar_to, quality_score, canonical_form))
                    phrase_id = cursor.lastrowid
                    
                    # Auto-approve High Priority phrases (quality score ≥ 0.90 or confidence ≥ 90%) immediately
                    if quality_score >= 0.90 or confidence >= 0.90:
                        self._auto_approve_phrase(phrase_id, clean_phrase, clean_category)
                
                logger.debug(f"Tracked semantic match: '{clean_phrase}' in {clean_category} (confidence: {confidence:.3f})")
                
        except Exception as e:
            logger.error(f"Failed to track semantic match: {e}")
    
    def _auto_approve_phrase(self, phrase_id: int, phrase: str, category: str):
        """Automatically approve a high-confidence phrase."""
        try:
            with self._get_db_connection() as conn:
                # Move to approved status
                conn.execute(
                    "UPDATE pending_phrases SET status = 'auto_approved' WHERE id = ?",
                    (phrase_id,)
                )
                
                # Add to repository
                self._add_to_repository(phrase, category, source='auto_learned')
                
                logger.info(f"Auto-approved phrase: '{phrase}' in {category}")
                
        except Exception as e:
            logger.error(f"Failed to auto-approve phrase: {e}")
    
    def normalize_to_canonical(self, phrase: str) -> str:
        """
        Create canonical form by removing filler words.
        Performance: ~1-2ms, cached for reuse.
        """
        # Check cache first
        cache_key = phrase.lower().strip()
        if cache_key in self._canonical_form_cache:
            return self._canonical_form_cache[cache_key]
        
        # Remove common fillers (be careful not to remove important words)
        # Only remove standalone filler words, not words that are part of meaningful phrases
        filler_words = {'okay', 'ok', 'well', 'so', 'um', 'uh', 'like', 'actually', 
                       'basically', 'literally', 'really', 'very', 'just'}
        # Handle filler phrases (remove these complete phrases)
        filler_phrases = ['you know', 'i mean']
        
        # First remove multi-word filler phrases
        text = phrase.lower().strip()
        for filler_phrase in filler_phrases:
            # Replace with space to maintain word boundaries
            text = text.replace(filler_phrase, ' ')
        
        # Then remove single-word fillers (only if standalone, not part of phrase)
        words = text.split()
        canonical = []
        for i, word in enumerate(words):
            # Remove punctuation for comparison
            clean_word = word.strip('.,!?;:')
            # Only skip if it's a filler word
            if clean_word not in filler_words:
                canonical.append(word)
        
        canonical_form = ' '.join(canonical).strip()
        # Clean up extra spaces
        canonical_form = ' '.join(canonical_form.split())
        
        # Cache result
        self._canonical_form_cache[cache_key] = canonical_form
        return canonical_form
    
    def calculate_quality_score(self, phrase_data: Dict[str, Any]) -> float:
        """
        Calculate multi-factor quality score (0-1 scale).
        Performance: ~2ms, uses simple weighted formula (no ML).
        
        Factors:
        - Confidence (50%): Semantic match strength
        - Frequency (25%): Detection count (normalized)
        - Recency (15%): Time since last detection
        - Context Quality (10%): Richness of sample contexts
        """
        # Check cache first (TTL: 1 hour)
        cache_key = f"{phrase_data.get('id', 'new')}_{phrase_data.get('confidence', 0)}"
        if cache_key in self._quality_score_cache:
            cached_score, cached_time = self._quality_score_cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < 3600:  # 1 hour TTL
                return cached_score
        
        # Extract factors
        confidence = phrase_data.get('confidence', 0.0)
        detection_count = phrase_data.get('detection_count', 1)
        last_detected = phrase_data.get('last_detected')
        sample_contexts = phrase_data.get('sample_contexts', '')
        
        # Normalize frequency (0-1 scale, max at 10 detections)
        frequency_score = min(detection_count / 10.0, 1.0)
        
        # Calculate recency score (0-1 scale)
        recency_score = 1.0
        if last_detected:
            try:
                if isinstance(last_detected, str):
                    # Handle ISO format strings
                    last_detected_str = last_detected.replace('Z', '+00:00')
                    try:
                        last_detected_dt = datetime.fromisoformat(last_detected_str)
                    except:
                        # Fallback for different formats
                        last_detected_dt = datetime.strptime(last_detected.split('.')[0], '%Y-%m-%d %H:%M:%S')
                else:
                    last_detected_dt = last_detected
                
                # Remove timezone for comparison
                if hasattr(last_detected_dt, 'replace'):
                    last_detected_dt = last_detected_dt.replace(tzinfo=None)
                
                days_ago = (datetime.now() - last_detected_dt).days
                # Fresher = better (decay over 30 days)
                recency_score = max(0.0, 1.0 - (days_ago / 30.0))
            except Exception as e:
                logger.debug(f"Recency calculation failed: {e}")
                recency_score = 1.0  # Default to fresh if parsing fails
        
        # Context quality (0-1 scale, based on length)
        context_quality = min(len(sample_contexts) / 500.0, 1.0) if sample_contexts else 0.0
        
        # Weighted formula (no ML, just smart weights)
        quality_score = (
            confidence * 0.50 +        # Most important: semantic match strength
            frequency_score * 0.25 +   # More detections = more reliable
            recency_score * 0.15 +     # Fresher = more relevant
            context_quality * 0.10    # Rich context = better understanding
        )
        
        quality_score = min(quality_score, 1.0)  # Cap at 1.0
        
        # Cache result
        self._quality_score_cache[cache_key] = (quality_score, datetime.now())
        
        return quality_score
    
    def get_quality_tier(self, quality_score: float) -> str:
        """
        Get priority tier based on quality score.
        Performance: ~0.1ms (simple comparison)
        """
        if quality_score >= 0.90:
            return "auto_approve"  # Tier 1: Auto-Approve
        elif quality_score >= 0.80:
            return "high_value"    # Tier 2: High Value
        elif quality_score >= 0.65:
            return "medium_value" # Tier 3: Medium Value
        else:
            return "low_value"    # Tier 4: Low Value
    
    def get_adaptive_threshold(self, category: str) -> float:
        """
        Get adaptive threshold for category based on historical performance.
        Performance: ~0.1ms (cached lookup)
        """
        # Check cache first (TTL: 1 week)
        if category in self._category_thresholds_cache:
            cached_threshold, cached_time = self._category_thresholds_cache[category]
            if (datetime.now() - cached_time).total_seconds() < 604800:  # 1 week
                return cached_threshold
        
        # Base thresholds per category (rule-based, no ML)
        base_thresholds = {
            'OTHER_PROPERTY_FAMILY': 0.88,
            'MIXED_FUTURE_OTHER_FAMILY': 0.85,
            'GENERAL': 0.80,
        }
        
        base_threshold = base_thresholds.get(category, 0.85)
        
        # Adjust based on historical performance (if available)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT approval_rate, avg_quality_score FROM category_performance WHERE category = ?",
                    (category,)
                )
                result = cursor.fetchone()
                
                if result:
                    approval_rate, avg_quality = result
                    # Adjust threshold based on performance
                    if approval_rate and approval_rate > 0.95:
                        base_threshold -= 0.02  # Lower threshold (high accuracy)
                    elif approval_rate and approval_rate < 0.80:
                        base_threshold += 0.02  # Raise threshold (low accuracy)
        except Exception as e:
            logger.debug(f"Adaptive threshold lookup failed: {e}")
            pass  # Use base threshold if lookup fails
        
        # Cache result
        self._category_thresholds_cache[category] = (base_threshold, datetime.now())
        
        return base_threshold
    
    def _is_blacklisted(self, phrase: str, category: str) -> bool:
        """Check if a phrase is blacklisted."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM phrase_blacklist WHERE phrase = ? AND category = ?",
                    (phrase.lower().strip(), category)
                )
                return cursor.fetchone() is not None
        except:
            return False
    
    def _phrase_exists_in_repository(self, phrase: str, category: str) -> bool:
        """Check if phrase already exists in the repository."""
        try:
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            
            category_phrases = repository.get("phrases", {}).get(category, [])
            return phrase.lower().strip() in [p.lower().strip() for p in category_phrases]
            
        except:
            return False
    
    def _add_to_repository(self, phrase: str, category: str, source: str = 'manual'):
        """Add a phrase to the repository file."""
        try:
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            
            # Add phrase to category
            if category not in repository["phrases"]:
                repository["phrases"][category] = []
            
            clean_phrase = phrase.lower().strip()
            if clean_phrase not in repository["phrases"][category]:
                repository["phrases"][category].append(clean_phrase)
                
                # Update metadata
                repository["last_updated"] = datetime.now().isoformat()
                if source == 'auto_learned':
                    repository["auto_added_count"] = repository.get("auto_added_count", 0) + 1
                
                # Save back to file
                with open(self.repository_path, 'w') as f:
                    json.dump(repository, f, indent=2)
                
                # Track in database (SQLite or PostgreSQL)
                conn = None
                cursor = None
                try:
                    conn = self._get_db_connection()
                    
                    # Handle both SQLite and PostgreSQL
                    if self.use_postgresql:
                        cursor = conn.cursor()
                        # Check if phrase exists
                        cursor.execute("""
                            SELECT id, usage_count FROM repository_phrases 
                            WHERE phrase = %s AND category = %s
                        """, (clean_phrase, category))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update usage count
                            cursor.execute("""
                                UPDATE repository_phrases 
                                SET usage_count = usage_count + 1
                                WHERE id = %s
                            """, (existing[0],))
                        else:
                            # Insert new phrase
                            cursor.execute("""
                                INSERT INTO repository_phrases 
                                (phrase, category, source, usage_count) VALUES (%s, %s, %s, 1)
                            """, (clean_phrase, category, source))
                        conn.commit()
                        if cursor:
                            cursor.close()
                    else:
                        # SQLite - use direct execute
                    cursor = conn.execute("""
                        SELECT id, usage_count FROM repository_phrases 
                        WHERE phrase = ? AND category = ?
                    """, (clean_phrase, category))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update usage count
                        conn.execute("""
                            UPDATE repository_phrases 
                            SET usage_count = usage_count + 1
                            WHERE id = ?
                        """, (existing[0],))
                    else:
                        # Insert new phrase
                        conn.execute("""
                            INSERT INTO repository_phrases 
                            (phrase, category, source, usage_count) VALUES (?, ?, ?, 1)
                        """, (clean_phrase, category, source))
                except Exception as e:
                    logger.warning(f"Failed to track phrase in repository_phrases table: {e}")
                finally:
                    if cursor and self.use_postgresql:
                        try:
                            cursor.close()
                        except:
                            pass
                    if conn:
                        self._return_db_connection(conn)
                
                # ALSO save to PostgreSQL if configured (PRIMARY SOURCE for semantic matching)
                try:
                    from lib.database import get_db_manager
                    db = get_db_manager()
                    
                    if db and hasattr(db, 'db_type') and db.db_type == 'postgresql':
                        # Ensure table exists (PostgreSQL syntax)
                        try:
                            db.execute_query("""
                                CREATE TABLE IF NOT EXISTS rebuttal_phrases (
                                    id SERIAL PRIMARY KEY,
                                    category VARCHAR(255) NOT NULL,
                                    phrase TEXT NOT NULL,
                                    source VARCHAR(100) DEFAULT 'manual',
                                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    UNIQUE(category, phrase)
                                )
                            """, fetch=False)
                        except Exception as create_error:
                            # Table might already exist - that's fine
                            logger.debug(f"Table creation (may already exist): {create_error}")
                        
                        # Insert or update in PostgreSQL (ON CONFLICT DO NOTHING for duplicates)
                        # Try with source column first, fallback to without source if column doesn't exist
                        inserted = False
                        try:
                            db.execute_query("""
                                INSERT INTO rebuttal_phrases (category, phrase, source)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (category, phrase) DO NOTHING
                            """, (category, clean_phrase, source), fetch=False)
                            inserted = True
                            logger.debug(f"✅ Saved phrase to PostgreSQL: '{clean_phrase}' in {category}")
                        except Exception as insert_error:
                            # If source column doesn't exist or permission denied, try without it
                            error_str = str(insert_error).lower()
                            if 'column "source" does not exist' in error_str or 'must be owner' in error_str:
                                try:
                                    db.execute_query("""
                                        INSERT INTO rebuttal_phrases (category, phrase)
                                        VALUES (%s, %s)
                                        ON CONFLICT (category, phrase) DO NOTHING
                                    """, (category, clean_phrase), fetch=False)
                                    inserted = True
                                    logger.debug(f"✅ Saved phrase to PostgreSQL (without source): '{clean_phrase}' in {category}")
                                except Exception as fallback_error:
                                    # Only log if it's not a duplicate conflict (which is expected)
                                    if 'duplicate key' not in str(fallback_error).lower() and 'unique constraint' not in str(fallback_error).lower():
                                        logger.debug(f"PostgreSQL insert error (fallback): {fallback_error}")
                            else:
                                # Only log if it's not a duplicate conflict (which is expected)
                                if 'duplicate key' not in error_str and 'unique constraint' not in error_str:
                                    logger.debug(f"PostgreSQL insert error (phrase may already exist): {insert_error}")
                except Exception as e:
                    # PostgreSQL not configured or not available - that's OK, JSON/SQLite are fallbacks
                    logger.debug(f"PostgreSQL not available for phrase storage: {e}")
                
                logger.info(f"Added phrase to repository: '{clean_phrase}' in {category}")
                
                # Reload semantic embeddings to include the new phrase
                try:
                    from models import reload_semantic_embeddings
                    reload_semantic_embeddings()
                    logger.info("✅ Reloaded semantic embeddings to include new phrase")
                except Exception as e:
                    logger.warning(f"Failed to reload semantic embeddings: {e}")
                    # Don't fail the entire operation if embedding reload fails
                
        except Exception as e:
            logger.error(f"Failed to add phrase to repository: {e}")
    
    def _auto_cleanup_duplicates_lightweight(self):
        """Lightweight automatic duplicate cleanup - merges duplicates by phrase text only."""
        try:
            conn = self._get_db_connection()
            if self.use_postgresql:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, confidence, detection_count, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                """)
            else:
                cursor = conn.execute("""
                    SELECT id, phrase, category, confidence, detection_count, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                """)
                
                all_phrases = cursor.fetchall()
                if not all_phrases:
                if self.use_postgresql:
                    cursor.close()
                    self._return_db_connection(conn)
                    return
                
                # Group by normalized phrase text ONLY (not category)
                phrase_groups = {}
                for row in all_phrases:
                    phrase_id, phrase, category, confidence, detection_count, contexts, similar_to = row
                    normalized_phrase = phrase.lower().strip() if phrase else ""
                    if normalized_phrase:
                        if normalized_phrase not in phrase_groups:
                            phrase_groups[normalized_phrase] = []
                        phrase_groups[normalized_phrase].append({
                            'id': phrase_id,
                            'phrase': phrase,
                            'category': category,
                            'confidence': confidence,
                            'detection_count': detection_count,
                            'contexts': contexts or "",
                            'similar_to': similar_to or ""
                        })
                
                # Process groups with duplicates
                duplicates_to_remove = []
                phrases_to_update = []
                
                for normalized, phrases in phrase_groups.items():
                    if len(phrases) > 1:
                        # Sort by confidence (desc) then detection_count (desc)
                        phrases.sort(key=lambda x: (x['confidence'], x['detection_count']), reverse=True)
                        
                        # Keep the best one (first after sorting)
                        best_phrase = phrases[0]
                        duplicates = phrases[1:]
                        
                        # Merge data: sum detection counts, combine contexts
                        total_detections = best_phrase['detection_count']
                        all_contexts = [best_phrase['contexts']] if best_phrase['contexts'] else []
                        
                        for dup in duplicates:
                            total_detections += dup['detection_count']
                            if dup['contexts']:
                                all_contexts.append(dup['contexts'])
                            duplicates_to_remove.append(dup['id'])
                        
                        # Update the best phrase with merged data
                        merged_contexts = " | ".join([c for c in all_contexts if c])[:500]
                        phrases_to_update.append({
                            'id': best_phrase['id'],
                            'detection_count': total_detections,
                            'contexts': merged_contexts
                        })
                
                # Update phrases with merged data
                for update_data in phrases_to_update:
                    try:
                        if self.use_postgresql:
                            cursor.execute("""
                                UPDATE pending_phrases 
                                SET detection_count = %s, sample_contexts = %s
                                WHERE id = %s
                            """, (update_data['detection_count'], update_data['contexts'], update_data['id']))
                        else:
                        conn.execute("""
                            UPDATE pending_phrases 
                            SET detection_count = ?, sample_contexts = ?
                            WHERE id = ?
                        """, (update_data['detection_count'], update_data['contexts'], update_data['id']))
                    except Exception as e:
                        logger.warning(f"Error updating phrase ID {update_data['id']} during auto-cleanup: {e}")
                
                # Delete duplicate phrases
                if duplicates_to_remove:
                    if self.use_postgresql:
                        placeholders = ','.join(['%s'] * len(duplicates_to_remove))
                        cursor.execute(f"""
                            DELETE FROM pending_phrases 
                            WHERE id IN ({placeholders})
                        """, duplicates_to_remove)
                    else:
                    placeholders = ','.join(['?'] * len(duplicates_to_remove))
                    conn.execute(f"""
                        DELETE FROM pending_phrases 
                        WHERE id IN ({placeholders})
                    """, duplicates_to_remove)
                    logger.info(f"Auto-cleaned {len(duplicates_to_remove)} duplicate phrases")
                
                if self.use_postgresql:
                    conn.commit()
                    cursor.close()
                    self._return_db_connection(conn)
                else:
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Auto-cleanup duplicates failed (non-critical): {e}", exc_info=True)
            if self.use_postgresql and 'conn' in locals():
                try:
                    if 'cursor' in locals():
                        cursor.close()
                    self._return_db_connection(conn)
                except:
                    pass
            # Don't fail the entire operation if cleanup fails
    
    def get_pending_phrases(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """Get pending phrases for review. Automatically cleans duplicates before returning."""
        # Auto-cleanup duplicates before returning
        self._auto_cleanup_duplicates_lightweight()
        
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            if self.use_postgresql:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, confidence, detection_count,
                           first_detected, last_detected, sample_contexts, similar_to,
                           quality_score, canonical_form
                    FROM pending_phrases 
                    WHERE status = %s
                    ORDER BY quality_score DESC NULLS LAST, confidence DESC, detection_count DESC
                """, (status,))
            else:
                cursor = conn.execute("""
                    SELECT id, phrase, category, confidence, detection_count,
                           first_detected, last_detected, sample_contexts, similar_to,
                           quality_score, canonical_form
                    FROM pending_phrases 
                    WHERE status = ?
                    ORDER BY quality_score DESC NULLS LAST, confidence DESC, detection_count DESC
                """, (status,))
                
                phrases = []
                for row in cursor.fetchall():
                    # Handle rows with or without new columns (backward compatibility)
                    row_len = len(row)
                    quality_score = row[9] if row_len > 9 and row[9] is not None else None
                    canonical_form = row[10] if row_len > 10 and row[10] else None
                    
                    phrase_data = {
                        'id': row[0],
                        'phrase': row[1],
                        'category': row[2],
                        'confidence': row[3],
                        'detection_count': row[4],
                        'first_detected': row[5],
                        'last_detected': row[6],
                        'sample_contexts': row[7] or "",
                        'similar_to': row[8] or ""
                    }
                    
                    # Calculate quality score if not present
                    if quality_score is None:
                        quality_score = self.calculate_quality_score(phrase_data)
                    
                    # Calculate canonical form if not present
                    if canonical_form is None:
                        canonical_form = self.normalize_to_canonical(row[1])
                    
                    phrase_data['quality_score'] = quality_score
                    phrase_data['canonical_form'] = canonical_form
                    phrase_data['quality_tier'] = self.get_quality_tier(quality_score)
                    
                    phrases.append(phrase_data)
                
                return phrases
                
        except Exception as e:
            logger.error(f"Failed to get pending phrases: {e}", exc_info=True)
            return []
        finally:
            if cursor and self.use_postgresql:
                try:
                    cursor.close()
                except:
                    pass
            if conn and self.use_postgresql:
                self._return_db_connection(conn)
    
    def approve_phrase(self, phrase_id: int) -> bool:
        """Approve a pending phrase and add it to repository."""
        try:
            conn = self._get_db_connection()
            if self.use_postgresql:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT phrase, category FROM pending_phrases WHERE id = %s",
                    (phrase_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    cursor.close()
                    self._return_db_connection(conn)
                    return False
                
                phrase, category = result
                
                # Update status
                cursor.execute(
                    "UPDATE pending_phrases SET status = 'approved' WHERE id = %s",
                    (phrase_id,)
                )
                conn.commit()
                cursor.close()
                self._return_db_connection(conn)
            else:
                cursor = conn.execute(
                    "SELECT phrase, category FROM pending_phrases WHERE id = ?",
                    (phrase_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                phrase, category = result
                
                # Update status
                conn.execute(
                    "UPDATE pending_phrases SET status = 'approved' WHERE id = ?",
                    (phrase_id,)
                )
                
                # Add to repository
                self._add_to_repository(phrase, category, source='admin_approved')
                
                logger.info(f"Approved phrase: '{phrase}' in {category}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to approve phrase: {e}", exc_info=True)
            if self.use_postgresql and 'conn' in locals():
                try:
                    if 'cursor' in locals():
                        cursor.close()
                    self._return_db_connection(conn)
                except:
                    pass
            return False
    
    def approve_all_high_priority_phrases(self, min_confidence: float = 0.90) -> dict:
        """
        Approve all pending phrases with confidence >= min_confidence.
        This is a batch operation for existing pending phrases.
        """
        return self.auto_approve_high_confidence_phrases(min_confidence=min_confidence)
    
    def approve_by_quality_score(self, min_quality_score: float = 0.90) -> dict:
        """
        Approve all pending phrases with quality score >= min_quality_score.
        Performance optimized batch operation.
        """
        stats = {
            'total_approved': 0,
            'total_skipped': 0,
            'errors': []
        }
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, phrase, category, quality_score
                    FROM pending_phrases 
                    WHERE status = 'pending' AND quality_score >= ?
                    ORDER BY quality_score DESC
                """, (min_quality_score,))
                
                phrases = cursor.fetchall()
                
                if not phrases:
                    return {
                        'success': True,
                        'message': f'No phrases found with quality score >= {min_quality_score:.0%}',
                        'stats': stats
                    }
                
                for phrase_id, phrase_text, category, quality_score in phrases:
                    try:
                        # Check if already in repository
                        already_in_repo = self._phrase_exists_in_repository(phrase_text, category or 'general')
                        
                        # Add to repository (will skip if already exists)
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='auto_approved'
                        )
                        
                        # Update status to approved regardless
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET status = 'approved'
                            WHERE id = ?
                        """, (phrase_id,))
                        
                        if success or already_in_repo:
                            stats['total_approved'] += 1
                        else:
                            stats['total_skipped'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': f"Approved {stats['total_approved']} phrases with quality score >= {min_quality_score:.0%}",
                    'stats': stats
                }
                
        except Exception as e:
            logger.error(f"Failed to approve by quality score: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'stats': stats
            }
    
    def approve_by_category(self, category: str, min_quality_score: float = 0.80) -> dict:
        """
        Approve all pending phrases in a specific category with quality score >= min_quality_score.
        """
        stats = {
            'total_approved': 0,
            'total_skipped': 0,
            'errors': []
        }
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, phrase, category, quality_score
                    FROM pending_phrases 
                    WHERE status = 'pending' AND category = ? AND quality_score >= ?
                    ORDER BY quality_score DESC
                """, (category, min_quality_score))
                
                phrases = cursor.fetchall()
                
                for phrase_id, phrase_text, cat, quality_score in phrases:
                    try:
                        already_in_repo = self._phrase_exists_in_repository(phrase_text, cat)
                        success = self._add_to_repository(phrase_text, cat, source='auto_approved')
                        
                        cursor.execute("""
                            UPDATE pending_phrases SET status = 'approved' WHERE id = ?
                        """, (phrase_id,))
                        
                        if success or already_in_repo:
                            stats['total_approved'] += 1
                        else:
                            stats['total_skipped'] += 1
                    except Exception as e:
                        stats['errors'].append(f"Error processing phrase ID {phrase_id}: {str(e)}")
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': f"Approved {stats['total_approved']} phrases in category '{category}'",
                    'stats': stats
                }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'stats': stats
            }
    
    def approve_all_pending_phrases(self) -> dict:
        """
        Approve all pending phrases regardless of quality score or confidence.
        This is a batch operation that approves every phrase in pending status.
        """
        stats = {
            'total_approved': 0,
            'total_skipped': 0,
            'errors': []
        }
        
        try:
            with self._get_db_connection() as conn:
                # Get all pending phrases
                cursor = conn.execute("""
                    SELECT id, phrase, category
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY id
                """)
                
                phrases = cursor.fetchall()
                
                if not phrases:
                    return {
                        'success': True,
                        'message': 'No pending phrases to approve',
                        'stats': stats
                    }
                
                for phrase_id, phrase_text, category in phrases:
                    try:
                        # Check if already in repository
                        already_in_repo = self._phrase_exists_in_repository(
                            phrase_text, 
                            category or 'general'
                        )
                        
                        # Add to repository (will skip if already exists)
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='admin_approved'
                        )
                        
                        # Update status to approved
                        conn.execute("""
                            UPDATE pending_phrases 
                            SET status = 'approved'
                            WHERE id = ?
                        """, (phrase_id,))
                        
                        if success or already_in_repo:
                            stats['total_approved'] += 1
                            logger.info(f"Approved phrase: '{phrase_text}' in {category or 'general'}")
                        else:
                            stats['total_skipped'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': f"Approved {stats['total_approved']} pending phrases. {stats['total_skipped']} skipped (already in repository).",
                    'stats': stats
                }
                
        except Exception as e:
            logger.error(f"Failed to approve all pending phrases: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'stats': stats
            }
    
    def track_phrase_effectiveness(self, phrase: str, category: str, was_successful: bool):
        """
        Track phrase effectiveness when used in detection.
        Performance: ~0.5ms (simple DB update)
        """
        try:
            with self._get_db_connection() as conn:
                # Find phrase in repository
                cursor = conn.execute("""
                    SELECT id, usage_count, successful_detections 
                    FROM repository_phrases 
                    WHERE phrase = ? AND category = ?
                """, (phrase.lower().strip(), category))
                
                result = cursor.fetchone()
                if result:
                    phrase_id, usage_count, successful = result
                    new_usage = usage_count + 1
                    new_successful = successful + (1 if was_successful else 0)
                    effectiveness = new_successful / new_usage if new_usage > 0 else 0.0
                    
                    conn.execute("""
                        UPDATE repository_phrases 
                        SET usage_count = ?,
                            successful_detections = ?,
                            effectiveness_score = ?
                        WHERE id = ?
                    """, (new_usage, new_successful, effectiveness, phrase_id))
                    conn.commit()
        except Exception as e:
            logger.debug(f"Failed to track effectiveness: {e}")
    
    def remove_duplicate_phrases(self) -> dict:
        """
        Remove duplicate phrases from pending review.
        Keeps the phrase with highest confidence, merges detection counts and contexts.
        """
        stats = {
            'total_duplicates_removed': 0,
            'phrases_merged': 0,
            'errors': []
        }
        
        try:
            with self._get_db_connection() as conn:
                # Get all pending phrases
                cursor = conn.execute("""
                    SELECT id, phrase, category, confidence, detection_count, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                """)
                
                all_phrases = cursor.fetchall()
                
                if not all_phrases:
                    return {
                        'success': True,
                        'message': 'No pending phrases found',
                        'stats': stats
                    }
                
                # Group by normalized phrase text ONLY (not category) - same phrase text = duplicate
                phrase_groups = {}
                for row in all_phrases:
                    phrase_id, phrase, category, confidence, detection_count, contexts, similar_to = row
                    # Normalize phrase for comparison - use phrase text only as key
                    normalized_phrase = phrase.lower().strip() if phrase else ""
                    key = normalized_phrase  # Remove category from key - duplicates by text only
                    
                    if key not in phrase_groups:
                        phrase_groups[key] = []
                    phrase_groups[key].append({
                        'id': phrase_id,
                        'phrase': phrase,
                        'category': category,
                        'confidence': confidence,
                        'detection_count': detection_count,
                        'contexts': contexts or "",
                        'similar_to': similar_to or ""
                    })
                
                # Find duplicates (groups with more than one phrase)
                duplicates_to_remove = []
                phrases_to_update = []
                
                for key, phrases in phrase_groups.items():
                    if len(phrases) > 1:
                        # Sort by confidence (desc) then detection_count (desc)
                        phrases.sort(key=lambda x: (x['confidence'], x['detection_count']), reverse=True)
                        
                        # Keep the best one (first after sorting)
                        best_phrase = phrases[0]
                        duplicates = phrases[1:]
                        
                        # Merge data: sum detection counts, combine contexts
                        total_detections = best_phrase['detection_count']
                        all_contexts = [best_phrase['contexts']]
                        
                        for dup in duplicates:
                            total_detections += dup['detection_count']
                            if dup['contexts']:
                                all_contexts.append(dup['contexts'])
                            duplicates_to_remove.append(dup['id'])
                        
                        # Update the best phrase with merged data
                        merged_contexts = " | ".join([c for c in all_contexts if c])[:500]
                        phrases_to_update.append({
                            'id': best_phrase['id'],
                            'detection_count': total_detections,
                            'contexts': merged_contexts
                        })
                        
                        stats['phrases_merged'] += len(duplicates)
                
                # Update phrases with merged data
                for update_data in phrases_to_update:
                    try:
                        conn.execute("""
                            UPDATE pending_phrases 
                            SET detection_count = ?, sample_contexts = ?
                            WHERE id = ?
                        """, (update_data['detection_count'], update_data['contexts'], update_data['id']))
                    except Exception as e:
                        error_msg = f"Error updating phrase ID {update_data['id']}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                # Delete duplicate phrases
                if duplicates_to_remove:
                    placeholders = ','.join(['?'] * len(duplicates_to_remove))
                    conn.execute(f"""
                        DELETE FROM pending_phrases 
                        WHERE id IN ({placeholders})
                    """, duplicates_to_remove)
                    stats['total_duplicates_removed'] = len(duplicates_to_remove)
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': f"Removed {stats['total_duplicates_removed']} duplicate phrases, merged {stats['phrases_merged']} entries",
                    'stats': stats
                }
                
        except Exception as e:
            logger.error(f"Failed to remove duplicate phrases: {e}")
            return {
                'success': False,
                'message': f"Error removing duplicates: {str(e)}",
                'stats': stats
            }
    
    def add_phrase_manually(self, phrase: str, category: str) -> dict:
        """Add a phrase manually to the repository with validation."""
        try:
            # Clean and validate input
            clean_phrase = phrase.lower().strip()
            clean_category = category.strip().upper()
            
            if not clean_phrase:
                return {"success": False, "message": "Phrase cannot be empty"}
            
            if not clean_category:
                return {"success": False, "message": "Category cannot be empty"}
            
            if len(clean_phrase) < 3:
                return {"success": False, "message": "Phrase must be at least 3 characters long"}
            
            # Check if phrase already exists in repository
            current_phrases = self.get_repository_phrases()
            for cat, phrases in current_phrases.items():
                if clean_phrase in phrases:
                    return {"success": False, "message": f"Phrase already exists in category '{cat}'"}
            
            # Add to repository
            self._add_to_repository(clean_phrase, clean_category, source='manual_admin')
            
            logger.info(f"Manually added phrase: '{clean_phrase}' to {clean_category}")
            return {
                "success": True, 
                "message": f"Successfully added '{clean_phrase}' to {clean_category}",
                "phrase": clean_phrase,
                "category": clean_category
            }
            
        except Exception as e:
            logger.error(f"Failed to add phrase manually: {e}")
            return {"success": False, "message": f"Error adding phrase: {str(e)}"}
    
    def reject_phrase(self, phrase_id: int, reason: str = "") -> bool:
        """Reject a pending phrase and add to blacklist."""
        try:
            with self._get_db_connection() as conn:
                # Get phrase details
                cursor = conn.execute(
                    "SELECT phrase, category FROM pending_phrases WHERE id = ?",
                    (phrase_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                phrase, category = result
                
                # Update status
                conn.execute(
                    "UPDATE pending_phrases SET status = 'rejected' WHERE id = ?",
                    (phrase_id,)
                )
                
                # Add to blacklist
                conn.execute("""
                    INSERT OR IGNORE INTO phrase_blacklist 
                    (phrase, category, reason) VALUES (?, ?, ?)
                """, (phrase, category, reason))
                
                logger.info(f"Rejected phrase: '{phrase}' in {category}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reject phrase: {e}")
            return False
    
    def get_repository_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        conn = None
        cursor = None
        try:
            if self.use_postgresql:
                # Get stats from PostgreSQL
                conn = self._get_db_connection()
                cursor = conn.cursor()
                
                # Total phrases from rebuttal_phrases (main table)
                cursor.execute("SELECT COUNT(*) FROM rebuttal_phrases")
                total_phrases = cursor.fetchone()[0]
                
                # Pending phrases
                cursor.execute("SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending'")
                pending_count = cursor.fetchone()[0]
                
                # Auto-learned count - check if source column exists in rebuttal_phrases first
                auto_learned_count = 0
                try:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'rebuttal_phrases' AND column_name = 'source'
                    """)
                    has_source_column = cursor.fetchone() is not None
                    
                    if has_source_column:
                        # Use rebuttal_phrases with source column
                        cursor.execute("SELECT COUNT(*) FROM rebuttal_phrases WHERE source = 'auto_learned'")
                        auto_learned_count = cursor.fetchone()[0]
                    else:
                        # Column doesn't exist - use repository_phrases table as fallback
                        logger.debug("'source' column missing in rebuttal_phrases. Using repository_phrases for auto-learned count.")
                        try:
                            cursor.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                            auto_learned_count = cursor.fetchone()[0]
                        except Exception as repo_error:
                            logger.warning(f"Could not get auto-learned count from repository_phrases: {repo_error}")
                            auto_learned_count = 0
                except Exception as col_check_error:
                    # If we can't check for column, try repository_phrases directly
                    logger.debug(f"Could not check for source column: {col_check_error}. Using repository_phrases.")
                    try:
                        cursor.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                        auto_learned_count = cursor.fetchone()[0]
                    except Exception:
                        auto_learned_count = 0
                
                # Categories count
                cursor.execute("SELECT COUNT(DISTINCT category) FROM rebuttal_phrases")
                categories = cursor.fetchone()[0]
                
                # Last updated timestamp
                cursor.execute("SELECT MAX(created_at) FROM rebuttal_phrases")
                last_updated_row = cursor.fetchone()
                last_updated = last_updated_row[0].isoformat() if last_updated_row and last_updated_row[0] else "Unknown"
                
                return {
                    'total_phrases': total_phrases,
                    'pending_count': pending_count,
                    'auto_learned_count': auto_learned_count,
                    'categories': categories,
                    'last_updated': last_updated
                }
            else:
                # Get stats from SQLite + JSON (original code)
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            
            total_phrases = sum(len(phrases) for phrases in repository["phrases"].values())
            
                conn = self._get_db_connection()
                cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
                
                cursor.execute("SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending'")
                pending_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                auto_learned_count = cursor.fetchone()[0]
            
                categories = len(repository["phrases"])
                last_updated = repository.get("last_updated", "Unknown")
                
            return {
                'total_phrases': total_phrases,
                'pending_count': pending_count,
                'auto_learned_count': auto_learned_count,
                    'categories': categories,
                    'last_updated': last_updated
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}", exc_info=True)
            return {
                'total_phrases': 0,
                'pending_count': 0,
                'auto_learned_count': 0,
                'categories': 0,
                'last_updated': "Unknown"
            }
        finally:
            if cursor and self.use_postgresql:
                try:
                    cursor.close()
                except:
                    pass
            if conn and self.use_postgresql:
                self._return_db_connection(conn)
    
    def get_repository_phrases(self) -> Dict[str, List[str]]:
        """Get all phrases from repository."""
        conn = None
        try:
            if self.use_postgresql:
                # Get phrases from PostgreSQL
                conn = self._get_db_connection()
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT category, phrase FROM rebuttal_phrases ORDER BY category, phrase")
                    results = cursor.fetchall()
                    
                    phrases_dict = {}
                    for row in results:
                        category = row[0]
                        phrase = row[1]
                        if category not in phrases_dict:
                            phrases_dict[category] = []
                        phrases_dict[category].append(phrase)
                    
                    return phrases_dict
                finally:
                    cursor.close()
            else:
                # Get phrases from JSON (original code)
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            return repository.get("phrases", {})
        except Exception as e:
            logger.error(f"Failed to get repository phrases: {e}", exc_info=True)
            return {}
        finally:
            if conn and self.use_postgresql:
                self._return_db_connection(conn)
    
    def update_settings(self, confidence_threshold: float = None, 
                       frequency_threshold: int = None,
                       auto_approve_threshold: float = None):
        """Update learning settings and save them persistently."""
        settings_changed = False
        
        if confidence_threshold is not None:
            new_value = max(0.5, min(1.0, confidence_threshold))
            if abs(self.confidence_threshold - new_value) > 0.001:
                self.confidence_threshold = new_value
                settings_changed = True
                
        if frequency_threshold is not None:
            new_value = max(1, frequency_threshold)
            if self.frequency_threshold != new_value:
                self.frequency_threshold = new_value
                settings_changed = True
                
        if auto_approve_threshold is not None:
            new_value = max(0.8, min(1.0, auto_approve_threshold))
            if abs(self.auto_approve_threshold - new_value) > 0.001:
                self.auto_approve_threshold = new_value
                settings_changed = True
        
        if settings_changed:
            # Save settings to file for persistence
            self._save_settings()
            logger.info(f"Updated and saved learning settings: confidence={self.confidence_threshold}, "
                       f"frequency={self.frequency_threshold}, auto_approve={self.auto_approve_threshold}")
        else:
            logger.debug("No settings changes detected")


# Global instance
_phrase_learning_manager = None

def get_phrase_learning_manager() -> PhraseLearningManager:
    """Get the global phrase learning manager instance."""
    global _phrase_learning_manager
    if _phrase_learning_manager is None:
        _phrase_learning_manager = PhraseLearningManager()
    return _phrase_learning_manager
