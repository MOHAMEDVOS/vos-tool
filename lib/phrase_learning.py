"""
Phrase Learning System for VOS Tool
Handles automatic learning and management of rebuttal phrases.
PHASE 4: PostgreSQL-Only Implementation
"""

import logging
import os
import time
from decimal import Decimal
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from datetime import datetime, timedelta
import re
from pathlib import Path

# Import database manager
try:
    from lib.database import get_db_manager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    get_db_manager = None
    logging.error("Database manager not available - PhraseLearningManager requires PostgreSQL")

logger = logging.getLogger(__name__)

class PhraseLearningManager:
    """Manages the self-learning phrase system."""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PhraseLearningManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the phrase learning manager with PostgreSQL connection."""
        if self._initialized:
            return
            
        if not DB_AVAILABLE or get_db_manager is None:
            raise RuntimeError("PhraseLearningManager requires lib.database and PostgreSQL")

        self.db_manager = get_db_manager()
        if not self.db_manager:
             raise RuntimeError("Could not initialize database manager")

        # Phase 4: Always use PostgreSQL
        self.use_postgresql = True

        logger.info("Using PostgreSQL for phrase management")
        
        # Cache for settings and performance stats
        self._settings_cache = {}
        self._category_thresholds = {}
        self._last_threshold_update = None
        
        # Initialize database tables
        self._init_database()
        
        # Load settings from DB
        self._load_settings()
        
        # Cache for performance optimization
        self._quality_score_cache = {}
        self._canonical_form_cache = {}
        self._similarity_cache = {}
        self._category_thresholds_cache = {}
        
        # Deferred mode for batch processing (prevents mid-session embedding reloads)
        self.deferred_mode = False
        self._deferred_phrases = []  # Queue: [(phrase, category, source), ...]
        

        self._init_repository()
        
        self._initialized = True
    
    def _load_settings(self):
        """Load settings from database or use defaults."""
        default_settings = {
            'confidence_threshold': 0.85,  # Minimum confidence for auto-learning
            'frequency_threshold': 5,      # Minimum detections before consideration
            'auto_approve_threshold': 0.80 # Auto-approve above this confidence (Updated to 80%)
        }
        
        # Initialize with defaults first
        self.confidence_threshold = default_settings['confidence_threshold']
        self.frequency_threshold = default_settings['frequency_threshold']
        self.auto_approve_threshold = default_settings['auto_approve_threshold']
        
        try:
            with self._db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT setting_key, setting_value FROM phrase_learning_settings")
                rows = cursor.fetchall()
                
                if rows:
                    settings_map = {row[0]: row[1] for row in rows}
                    
                    if 'confidence_threshold' in settings_map:
                        self.confidence_threshold = float(settings_map['confidence_threshold'])
                    
                    if 'frequency_threshold' in settings_map:
                        self.frequency_threshold = int(float(settings_map['frequency_threshold']))
                        
                    if 'auto_approve_threshold' in settings_map:
                        self.auto_approve_threshold = float(settings_map['auto_approve_threshold'])
                    
                    logger.info(f"Loaded settings from DB: confidence={self.confidence_threshold}, "
                               f"frequency={self.frequency_threshold}, auto_approve={self.auto_approve_threshold}")
                else:
                    # Save defaults to DB if empty
                    self._save_settings()
                    logger.info("Initialized default settings in database")
                cursor.close()
                
        except Exception as e:
            logger.error(f"Failed to load settings from DB, using defaults: {e}")

    def _save_settings(self):
        """Save current settings to database."""
        try:
            with self._db_connection() as conn:
                cursor = conn.cursor()
                
                settings = {
                    'confidence_threshold': str(self.confidence_threshold),
                    'frequency_threshold': str(self.frequency_threshold),
                    'auto_approve_threshold': str(self.auto_approve_threshold)
                }
                
                for key, value in settings.items():
                    cursor.execute("""
                        INSERT INTO phrase_learning_settings (setting_key, setting_value, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (setting_key) 
                        DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP
                    """, (key, value))
                
                conn.commit()
                cursor.close()
                
            logger.info("Settings saved to database")
            
        except Exception as e:
            logger.error(f"Failed to save settings to DB: {e}")
            
    def auto_approve_high_confidence_phrases(self, min_confidence: float = 0.8) -> dict:
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
            with self._db_connection() as conn:
                # Get all pending phrases with confidence >= min_confidence
                cursor = conn.cursor()
                
                # First, get the count of phrases that will be auto-approved
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM pending_phrases 
                    WHERE confidence >= %s 
                    AND status = 'pending'
                """, (min_confidence,))
                total_to_approve = cursor.fetchone()[0]
                
                if total_to_approve == 0:
                    cursor.close()
                    return {
                        'success': True,
                        'message': 'No phrases found with confidence >= 80%',
                        'stats': stats
                    }
                
                # Check if source column exists (just in case schema update failed)
                # But in pure PG environment created by Init DB, it should exist.
                # Simplified to just try selecting it, catch error if needed? 
                # Better: Just select simplified columns for now, assuming standard schema.
                
                cursor.execute("""
                    SELECT id, phrase, confidence, category
                    FROM pending_phrases 
                    WHERE confidence >= %s 
                    AND status = 'pending'
                """, (min_confidence,))
                phrases = [(row[0], row[1], row[2], row[3], 'auto_approved') for row in cursor.fetchall()]
                
                # Process each phrase
                for phrase_id, phrase_text, confidence, category, source in phrases:
                    try:
                        # Add to repository (will skip if already exists, but that's OK)
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='auto_approved'
                        )
                        
                        # Update status to approved
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET status = 'approved'
                            WHERE id = %s
                        """, (phrase_id,))
                        
                        if success:
                            stats['total_approved'] += 1
                        else:
                            # It might have been skipped by _add_to_repository, but we still approve it in pending
                            stats['total_approved'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                cursor.close()
                
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
        """Get database connection from pool."""
        if self.db_manager:
            try:
                conn = self.db_manager.connection_pool.getconn()
                if conn:
                    return conn
            except Exception as e:
                logger.error(f"Failed to get PostgreSQL connection: {e}")
                raise
        
        raise RuntimeError("No database manager available for PhraseLearningManager")
    
    def _return_db_connection(self, conn):
        """Return database connection to pool."""
        try:
            if self.db_manager:
                self.db_manager.connection_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")

    @contextmanager
    def _db_connection(self, timeout: int = 30, retries: int = 3):
        conn = None
        try:
            conn = self._get_db_connection(timeout=timeout, retries=retries)
            yield conn
        except Exception:
            if conn and self.use_postgresql:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn:
                self._return_db_connection(conn)
    
    def _init_database(self):
        """Initialize the phrase learning database tables."""
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
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
            logger.info("Phrase learning database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize phrase learning database: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_db_connection(conn)
    
    def rebuild_repository_from_existing(self) -> bool:
        """Sync foundational phrases from KeywordRepository into the database."""
        try:
            from analyzer.rebuttal_detection import KeywordRepository
            keyword_repo = KeywordRepository()
            base_phrases = keyword_repo.get_all_phrases()
            
            count = 0
            with self._db_connection() as conn:
                cursor = conn.cursor()
                for category, phrases in base_phrases.items():
                    for phrase in phrases:
                        clean_phrase = phrase.lower().strip()
                        cursor.execute("""
                            INSERT INTO repository_phrases (phrase, category, source, usage_count)
                            VALUES (%s, %s, 'system_default', 1)
                            ON CONFLICT (phrase, category) DO NOTHING
                        """, (clean_phrase, category))
                        count += 1
                conn.commit()
                cursor.close()
            
            logger.info(f" synced {count} base phrases to repository database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync repository: {e}")
            return False
    
    def _init_repository(self):
        """Initialize the repository by syncing default phrases if empty."""
        try:
            with self._db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM repository_phrases")
                count = cursor.fetchone()[0]
                cursor.close()
                
            if count == 0:
                logger.info("Repository empty, importing default phrases...")
                self.rebuild_repository_from_existing()
        except Exception as e:
            logger.error(f"Failed to init repository: {e}")
    
    def track_semantic_match(self, phrase: str, category: str, confidence: float, 
                           context: str = "", similar_to: str = "", existing_conn=None):
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
            if self._is_blacklisted(clean_phrase, clean_category, existing_conn=existing_conn):
                return
            
            # Skip if phrase already exists in repository
            if self._phrase_exists_in_repository(clean_phrase, clean_category, existing_conn=existing_conn):
                return
            
            # Use provided connection or acquire a new one
            from contextlib import nullcontext
            db_ctx = self._db_connection() if existing_conn is None else nullcontext(existing_conn)
            
            with db_ctx as conn:
                # Check for duplicate by phrase text ONLY (normalized, case-insensitive) - not category
                normalized_phrase = clean_phrase.lower().strip()
                
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, detection_count, confidence, sample_contexts, category
                    FROM pending_phrases 
                    WHERE LOWER(TRIM(phrase)) = %s AND status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                    LIMIT 1
                """, (normalized_phrase,))
                existing = cursor.fetchone()
                
                if existing:
                    # Merge into existing entry (auto-prevent duplicate)
                    phrase_id, count, existing_conf, existing_ctx, existing_cat = existing

                    try:
                        if isinstance(count, Decimal):
                            count = int(count)
                    except Exception:
                        pass

                    try:
                        if isinstance(existing_conf, Decimal):
                            existing_conf = float(existing_conf)
                    except Exception:
                        pass

                    try:
                        if isinstance(confidence, Decimal):
                            confidence = float(confidence)
                    except Exception:
                        pass

                    new_count = int(count) + 1
                    new_confidence = max(float(existing_conf), float(confidence))
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
                    
                    cursor.execute("""
                        UPDATE pending_phrases 
                        SET detection_count = %s, confidence = %s, 
                            last_detected = CURRENT_TIMESTAMP,
                            sample_contexts = %s,
                            quality_score = %s,
                            canonical_form = %s
                        WHERE id = %s
                    """, (new_count, new_confidence, merged_context, quality_score, canonical_form, phrase_id))
                    
                    # Check if it should be auto-approved (use merged confidence)
                    # High Priority (confidence ≥ threshold): Auto-approve immediately, no frequency requirement
                    if quality_score >= self.auto_approve_threshold or confidence >= self.auto_approve_threshold:
                        self._auto_approve_phrase(phrase_id, clean_phrase, clean_category, existing_conn=conn)
                
                # Only commit if we opened the connection
                if existing_conn is None:
                    conn.commit()
                cursor.close()

                logger.debug(f"Tracked semantic match: '{clean_phrase}' in {clean_category} (confidence: {confidence:.3f})")
                
        except Exception as e:
            logger.error(f"Failed to track semantic match: {e}")
    
    def _auto_approve_phrase(self, phrase_id: int, phrase: str, category: str, existing_conn=None):
        """Automatically approve a high-confidence phrase."""
        try:
            from contextlib import nullcontext
            db_ctx = self._db_connection() if existing_conn is None else nullcontext(existing_conn)
            
            with db_ctx as conn:
                # Move to approved status
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE pending_phrases SET status = 'auto_approved' WHERE id = %s",
                    (phrase_id,),
                )
                
                # Only commit if we opened the connection
                if existing_conn is None:
                    conn.commit()
                cursor.close()
                
                # Add to repository
                self._add_to_repository(phrase, category, source='auto_learned', existing_conn=conn)
                
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

        # psycopg2 returns DECIMAL/NUMERIC as Decimal; normalize to python numeric types
        try:
            if isinstance(confidence, Decimal):
                confidence = float(confidence)
            else:
                confidence = float(confidence)
        except Exception:
            confidence = 0.0

        try:
            if isinstance(detection_count, Decimal):
                detection_count = int(detection_count)
            else:
                detection_count = int(detection_count)
        except Exception:
            detection_count = 1
        
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
            with self._db_connection() as conn:
                if self.use_postgresql:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT approval_rate, avg_quality_score FROM category_performance WHERE category = %s",
                        (category,),
                    )
                    result = cursor.fetchone()
                    cursor.close()
                else:
                    cursor = conn.execute(
                        "SELECT approval_rate, avg_quality_score FROM category_performance WHERE category = ?",
                        (category,)
                    )
                    result = cursor.fetchone()
                
                if result:
                    approval_rate, avg_quality = result

                    try:
                        if isinstance(approval_rate, Decimal):
                            approval_rate = float(approval_rate)
                    except Exception:
                        approval_rate = None

                    try:
                        if isinstance(avg_quality, Decimal):
                            avg_quality = float(avg_quality)
                    except Exception:
                        avg_quality = None

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
    
    def _is_blacklisted(self, phrase: str, category: str, existing_conn=None) -> bool:
        """Check if a phrase is blacklisted."""
        try:
            from contextlib import nullcontext
            db_ctx = self._db_connection() if existing_conn is None else nullcontext(existing_conn)
            
            with db_ctx as conn:
                if self.use_postgresql:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT 1 FROM phrase_blacklist WHERE phrase = %s AND category = %s",
                        (phrase.lower().strip(), category),
                    )
                    result = cursor.fetchone() is not None
                    cursor.close()
                    return result
                cursor = conn.execute(
                    "SELECT 1 FROM phrase_blacklist WHERE phrase = ? AND category = ?",
                    (phrase.lower().strip(), category)
                )
                return cursor.fetchone() is not None
        except:
            return False
    
    def _phrase_exists_in_repository(self, phrase: str, category: str, existing_conn=None) -> bool:
        """Check if phrase already exists in the repository."""
        try:
            if self.use_postgresql:
                from contextlib import nullcontext
                db_ctx = self._db_connection() if existing_conn is None else nullcontext(existing_conn)
                
                with db_ctx as conn:
                    clean_phrase = phrase.lower().strip()
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "SELECT 1 FROM repository_phrases WHERE phrase = %s AND category = %s LIMIT 1",
                            (clean_phrase, category),
                        )
                        return cursor.fetchone() is not None
                    except Exception:
                        cursor.execute(
                            "SELECT 1 FROM rebuttal_phrases WHERE phrase = %s AND category = %s LIMIT 1",
                            (clean_phrase, category),
                        )
                        return cursor.fetchone() is not None
                    finally:
                        cursor.close()
            
        except Exception as e:
            logger.error(f"Error checking phrase existence: {e}")
            return False
    
    def _add_to_repository(self, phrase: str, category: str, source: str = 'manual', existing_conn=None) -> bool:
        """Add a phrase to the repository database."""
        try:
            clean_phrase = phrase.lower().strip()
            
            # DEFERRED MODE: Queue phrase instead of immediate DB write
            if self.deferred_mode:
                self._deferred_phrases.append((clean_phrase, category, source))
                logger.debug(f"Queued phrase for deferred processing: '{clean_phrase}' in {category}")
                return True
            
            # NORMAL MODE: Immediate processing (backward compatible)
            from contextlib import nullcontext
            db_ctx = self._db_connection() if existing_conn is None else nullcontext(existing_conn)
            
            with db_ctx as conn:
                cursor = conn.cursor()
                try:
                    # Update repository_phrases
                    cursor.execute(
                        "SELECT id FROM repository_phrases WHERE phrase = %s AND category = %s",
                        (clean_phrase, category),
                    )
                    existing = cursor.fetchone()

                    if existing:
                        cursor.execute(
                            "UPDATE repository_phrases SET usage_count = usage_count + 1 WHERE id = %s",
                            (existing[0],),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO repository_phrases
                            (phrase, category, source, usage_count) VALUES (%s, %s, %s, 1)
                            """,
                            (clean_phrase, category, source),
                        )

                    # Update rebuttal_phrases (if table exists)
                    try:
                        cursor.execute(
                            """
                            INSERT INTO rebuttal_phrases (category, phrase, source)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (category, phrase) DO NOTHING
                            """,
                            (category, clean_phrase, source),
                        )
                    except Exception:
                        pass 

                    conn.commit()
                finally:
                    cursor.close()

            logger.info(f"Added phrase to repository: '{clean_phrase}' in {category}")

            # Reload semantic embeddings
            try:
                from models import reload_semantic_embeddings
                reload_semantic_embeddings()
            except Exception:
                pass
            return True

        except Exception as e:
            logger.error(f"Failed to add to repository: {e}")
            return False

    def enable_deferred_mode(self):
        """Enable deferred mode for batch processing."""
        self.deferred_mode = True
        self._deferred_phrases = []
        logger.info("📦 Deferred phrase learning enabled (batch mode)")

    def disable_deferred_mode(self, flush: bool = True):
        """
        Disable deferred mode and optionally flush queued phrases.
        
        Args:
            flush: If True, flush deferred phrases before disabling
        """
        if flush and self._deferred_phrases:
            result = self.flush_deferred_phrases()
            if result:
                logger.info(f"Flushed deferred phrases: {result.get('message', 'Unknown')}")
        
        self.deferred_mode = False
        self._deferred_phrases = []
        logger.info("📦 Deferred phrase learning disabled")

    def flush_deferred_phrases(self) -> dict:
        """
        Flush all deferred phrases to database and reload embeddings once.
        
        Returns:
            dict: Statistics about the flush operation
        """
        if not self.deferred_mode:
            logger.warning("flush_deferred_phrases called but deferred_mode is False")
            return {'success': False, 'message': 'Not in deferred mode'}
        
        if not self._deferred_phrases:
            logger.info("No deferred phrases to flush")
            return {'success': True, 'message': 'No phrases to flush', 'count': 0}
        
        stats = {
            'total_queued': len(self._deferred_phrases),
            'total_added': 0,
            'total_skipped': 0,
            'errors': []
        }
        
        try:
            with self._db_connection() as conn:
                cursor = conn.cursor()
                
                for clean_phrase, category, source in self._deferred_phrases:
                    try:
                        # Check if already exists
                        cursor.execute(
                            "SELECT id FROM repository_phrases WHERE phrase = %s AND category = %s",
                            (clean_phrase, category),
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            cursor.execute(
                                "UPDATE repository_phrases SET usage_count = usage_count + 1 WHERE id = %s",
                                (existing[0],),
                            )
                            stats['total_skipped'] += 1
                        else:
                            cursor.execute(
                                """
                                INSERT INTO repository_phrases
                                (phrase, category, source, usage_count) VALUES (%s, %s, %s, 1)
                                """,
                                (clean_phrase, category, source),
                            )
                            stats['total_added'] += 1
                        
                        # Update rebuttal_phrases table
                        try:
                            cursor.execute(
                                """
                                INSERT INTO rebuttal_phrases (category, phrase, source)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (category, phrase) DO NOTHING
                                """,
                                (category, clean_phrase, source),
                            )
                        except Exception:
                            pass
                        
                        logger.info(f"Added phrase to repository: '{clean_phrase}' in {category}")
                        
                    except Exception as e:
                        error_msg = f"Error adding phrase '{clean_phrase}': {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                cursor.close()
            
            # Single reload after all phrases added
            logger.info(f"🔄 Flushing {stats['total_queued']} deferred phrases with single reload...")
            try:
                from models import reload_semantic_embeddings
                reload_semantic_embeddings()
                logger.info(f"✅ Successfully flushed {stats['total_added']} new phrases (skipped {stats['total_skipped']} duplicates)")
            except Exception as e:
                error_msg = f"Failed to reload embeddings: {str(e)}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)
            
            # Clear queue
            self._deferred_phrases = []
            
            return {
                'success': True,
                'message': f"Flushed {stats['total_added']} phrases with single reload",
                'stats': stats
            }
            
        except Exception as e:
            error_msg = f"Error in flush_deferred_phrases: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'stats': stats
            }


    def flush_deferred_phrases_in_background(self):
        """
        Flush deferred phrases in a separate thread to avoid blocking the main flow.
        This allows the UI to return results immediately while learning happens in background.
        """
        import threading
        
        def _background_worker():
            try:
                # Capture phrases locally because disable_deferred_mode clears the list
                # Actually, flush_deferred_phrases handles the clearing
                logger.info("🚀 Starting background phrase flush...")
                result = self.flush_deferred_phrases()
                stats = result.get('stats', {})
                if stats.get('total_added', 0) > 0:
                    logger.info(f"✨ Background Flush Complete: Added {stats['total_added']} phrases")
                else:
                    logger.info("✨ Background Flush Complete: No new phrases added")
            except Exception as e:
                logger.error(f"Background flush failed: {e}")
                
        # Start daemon thread (won't block program exit)
        t = threading.Thread(target=_background_worker, daemon=True, name="PhraseFlushWorker")
        t.start()
        
        # Disable deferred mode immediately in main thread (reset state)
        # Note: We need to preserve the list for the worker before clearing,
        # but flush_deferred_phrases reads self._deferred_phrases.
        # So we DON'T clear it here if flushing; the worker does it.
        # But we DO need to set deferred_mode to False so new adds go to DB?
        # Actually, let's keep it simple: Just disable the mode flag, 
        # let the worker flush the queue.
        
        # Wait... if we set deferred_mode=False, flush_deferred_phrases checks this flag and returns error!
        # So we must keep deferred_mode=True until the worker runs?
        # OR we modify flush_deferred_phrases to not check the flag?
        # Better option: The worker calls 'flush_deferred_phrases', which clears the queue.
        # We just need to manage the flag.
        
        self.deferred_mode = False  # Disable mode for future calls
        logger.info("📦 Deferred mode disabled (flush running in background)")
    
    def _auto_cleanup_duplicates_lightweight(self):
        """Lightweight automatic duplicate cleanup - merges duplicates by phrase text only."""
        try:
            conn = self._get_db_connection()
            with conn: # Transaction context
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, confidence, detection_count, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY detection_count DESC
                """)
                phrases = cursor.fetchall()

                # Group by normalized phrase
                phrase_groups = {}
                for row in phrases:
                    # Normalized: lower case, stripped
                    norm_phrase = row[1].lower().strip()
                    if norm_phrase not in phrase_groups:
                        phrase_groups[norm_phrase] = []
                    
                    phrase_groups[norm_phrase].append({
                        'id': row[0],
                        'phrase': row[1],
                        'category': row[2],
                        'confidence': row[3],
                        'detection_count': row[4],
                        'contexts': row[5],
                        'similar_to': row[6]
                    })
                
                # Find duplicates
                duplicates_to_remove = []
                phrases_to_update = []
                
                for norm_phrase, duplicates in phrase_groups.items():
                    if len(duplicates) > 1:
                        # Sort by detection count (desc) then confidence (desc)
                        duplicates.sort(key=lambda x: (x['detection_count'], x['confidence']), reverse=True)
                        
                        best_phrase = duplicates[0]
                        total_detections = best_phrase['detection_count']
                        all_contexts = [best_phrase['contexts']] if best_phrase['contexts'] else []
                        
                        # Merge others
                        for dup in duplicates[1:]:
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
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET detection_count = %s, sample_contexts = %s
                            WHERE id = %s
                        """, (update_data['detection_count'], update_data['contexts'], update_data['id']))
                    except Exception as e:
                        logger.warning(f"Error updating phrase ID {update_data['id']} during auto-cleanup: {e}")
                
                # Delete duplicate phrases
                if duplicates_to_remove:
                    placeholders = ','.join(['%s'] * len(duplicates_to_remove))
                    cursor.execute(f"""
                        DELETE FROM pending_phrases 
                        WHERE id IN ({placeholders})
                    """, duplicates_to_remove)
                    logger.info(f"Auto-cleaned {len(duplicates_to_remove)} duplicate phrases")
                
                cursor.close()
                self._return_db_connection(conn)
        
        except Exception as e:
            logger.warning(f"Auto-cleanup duplicates failed (non-critical): {e}", exc_info=True)
            if 'conn' in locals() and conn:
                try:
                    if 'cursor' in locals() and cursor:
                        cursor.close()
                    self._return_db_connection(conn)
                except:
                    pass
    
    def get_pending_phrases(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """Get pending phrases for review. Automatically cleans duplicates before returning."""
        # Auto-cleanup duplicates before returning
        self._auto_cleanup_duplicates_lightweight()
        
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, phrase, category, confidence, detection_count,
                       first_detected, last_detected, sample_contexts, similar_to,
                       quality_score, canonical_form
                FROM pending_phrases 
                WHERE status = %s
                ORDER BY quality_score DESC NULLS LAST, confidence DESC, detection_count DESC
                """,
                (status,),
            )

            phrases = []
            for row in cursor.fetchall():
                row_len = len(row)
                quality_score = row[9] if row_len > 9 and row[9] is not None else None
                canonical_form = row[10] if row_len > 10 and row[10] else None

                # Convert UUID and Decimal to standard Python types to prevent Pydantic validation errors in the API layer.
                raw_id = row[0]
                str_id = str(raw_id) if raw_id is not None else ""

                raw_confidence = row[3]
                try:
                    conf_val = float(raw_confidence) if raw_confidence is not None else None
                except (ValueError, TypeError):
                    conf_val = None

                phrase_data = {
                    'id': str_id,
                    'phrase': row[1],
                    'category': row[2],
                    'confidence': conf_val,
                    'detection_count': int(row[4]) if row[4] is not None else None,
                    'first_detected': row[5],
                    'last_detected': row[6],
                    'sample_contexts': row[7] or "",
                    'similar_to': row[8] or "",
                }

                if quality_score is None:
                    quality_score = self.calculate_quality_score(phrase_data)
                else:
                    try:
                        quality_score = float(quality_score)
                    except (ValueError, TypeError):
                        quality_score = 0.0

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
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                self._return_db_connection(conn)
    
    def approve_phrase(self, phrase_id: Union[int, str]) -> bool:
        """Approve a pending phrase and add it to repository."""
        try:
            conn = self._get_db_connection()
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
            
            # Add to repository
            self._add_to_repository(phrase, category, source='admin_approved')
            
            logger.info(f"Approved phrase: '{phrase}' in {category}")
            return True
                
        except Exception as e:
            logger.error(f"Failed to approve phrase: {e}", exc_info=True)
            if 'conn' in locals() and conn:
                try:
                    if 'cursor' in locals() and cursor:
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
            with self._db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, quality_score
                    FROM pending_phrases 
                    WHERE status = 'pending' AND quality_score >= %s
                    ORDER BY quality_score DESC
                """, (min_quality_score,))
                phrases = cursor.fetchall()
                
                if not phrases:
                    cursor.close()
                    return {
                        'success': True,
                        'message': f'No phrases found with quality score >= {min_quality_score:.0%}',
                        'stats': stats
                    }
                
                for phrase_id, phrase_text, category, quality_score in phrases:
                    try:
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
                            WHERE id = %s
                        """, (phrase_id,))
                        
                        if success:
                            stats['total_approved'] += 1
                        else:
                            # Count as approved if we updated status, even if add to repo skipped (duplicate)
                            stats['total_approved'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                cursor.close()
                
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
            with self._db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, quality_score
                    FROM pending_phrases 
                    WHERE status = 'pending' AND category = %s AND quality_score >= %s
                    ORDER BY quality_score DESC
                """, (category, min_quality_score))
                phrases = cursor.fetchall()
                
                for phrase_id, phrase_text, cat, quality_score in phrases:
                    try:
                        success = self._add_to_repository(phrase_text, cat, source='auto_approved')
                        
                        cursor.execute("""
                            UPDATE pending_phrases SET status = 'approved' WHERE id = %s
                        """, (phrase_id,))
                        
                        if success:
                            stats['total_approved'] += 1
                        else:
                            stats['total_approved'] += 1
                    except Exception as e:
                        stats['errors'].append(f"Error processing phrase ID {phrase_id}: {str(e)}")
                
                conn.commit()
                cursor.close()
                
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
            with self._db_connection() as conn:
                # Get all pending phrases
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY id
                """)
                phrases = cursor.fetchall()
                
                if not phrases:
                    cursor.close()
                    return {
                        'success': True,
                        'message': 'No pending phrases to approve',
                        'stats': stats
                    }
                
                for phrase_id, phrase_text, category in phrases:
                    try:
                        # Add to repository (will skip if already exists)
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='admin_approved'
                        )
                        
                        # Update status to approved
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET status = 'approved'
                            WHERE id = %s
                        """, (phrase_id,))
                        
                        if success:
                            stats['total_approved'] += 1
                            logger.info(f"Approved phrase: '{phrase_text}' in {category or 'general'}")
                        else:
                            stats['total_approved'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing phrase ID {phrase_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                
                conn.commit()
                cursor.close()
                
                return {
                    'success': True,
                    'message': f"Approved {stats['total_approved']} pending phrases.",
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
            with self._db_connection() as conn:
                # Find phrase in repository
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, usage_count, successful_detections 
                    FROM repository_phrases 
                    WHERE phrase = %s AND category = %s
                """, (phrase.lower().strip(), category))
                result = cursor.fetchone()
                
                if result:
                    phrase_id, usage_count, successful = result
                    new_usage = usage_count + 1
                    new_successful = successful + (1 if was_successful else 0)
                    effectiveness = new_successful / new_usage if new_usage > 0 else 0.0
                    
                    cursor.execute("""
                        UPDATE repository_phrases 
                        SET usage_count = %s,
                            successful_detections = %s,
                            effectiveness_score = %s
                        WHERE id = %s
                    """, (new_usage, new_successful, effectiveness, phrase_id))
                    
                    conn.commit()
                cursor.close()
                
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
            with self._db_connection() as conn:
                # Get all pending phrases
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phrase, category, confidence, detection_count, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = 'pending'
                    ORDER BY confidence DESC, detection_count DESC
                """)
                phrases = cursor.fetchall()
                
                if not phrases:
                    cursor.close()
                    return {
                        'success': True,
                        'message': 'No pending phrases found',
                        'stats': stats
                    }
                
                # Group by normalized phrase
                phrase_groups = {}
                for row in phrases:
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
                
                for key, phrases in phrase_groups.items():
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
                        
                        stats['phrases_merged'] += len(duplicates)
                
                # Update phrases with merged data
                for update_data in phrases_to_update:
                    try:
                        cursor.execute("""
                            UPDATE pending_phrases 
                            SET detection_count = %s, sample_contexts = %s
                            WHERE id = %s
                        """, (update_data['detection_count'], update_data['contexts'], update_data['id']))
                    except Exception as e:
                        logger.warning(f"Error updating phrase ID {update_data['id']}: {e}")
                
                # Delete duplicate phrases
                if duplicates_to_remove:
                    placeholders = ','.join(['%s'] * len(duplicates_to_remove))
                    cursor.execute(f"""
                        DELETE FROM pending_phrases 
                        WHERE id IN ({placeholders})
                    """, duplicates_to_remove)
                    stats['total_duplicates_removed'] = len(duplicates_to_remove)
                
                conn.commit()
                cursor.close()
                
                return {
                    'success': True,
                    'message': f"Removed {stats['total_duplicates_removed']} duplicate phrases",
                    'stats': stats
                }
                
        except Exception as e:
            logger.error(f"Failed to remove duplicate phrases: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}",
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
    
    def reject_phrase(self, phrase_id: Union[int, str], reason: str = "") -> bool:
        """Reject a pending phrase and add to blacklist."""
        try:
            with self._db_connection() as conn:
                # Get phrase details
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT phrase, category FROM pending_phrases WHERE id = %s",
                    (phrase_id,),
                )
                result = cursor.fetchone()
                
                if not result:
                    cursor.close()
                    return False
                
                phrase, category = result
                
                # Update status
                cursor.execute(
                    "UPDATE pending_phrases SET status = 'rejected' WHERE id = %s",
                    (phrase_id,),
                )
                
                # Add to blacklist
                cursor.execute(
                    """
                    INSERT INTO phrase_blacklist (phrase, category, reason)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (phrase, category) DO NOTHING
                    """,
                    (phrase, category, reason),
                )
                conn.commit()
                cursor.close()
                
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
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM repository_phrases")
            total_phrases = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending'")
            pending_count = cursor.fetchone()[0]
            
            auto_learned_count = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                auto_learned_count = cursor.fetchone()[0]
            except Exception:
                try:
                    cursor.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                    auto_learned_count = cursor.fetchone()[0]
                except Exception:
                    auto_learned_count = 0
            
            cursor.execute("SELECT COUNT(DISTINCT category) FROM repository_phrases")
            categories = cursor.fetchone()[0]
            
            try:
                cursor.execute("SELECT COALESCE(MAX(added_date), MAX(created_at)) FROM repository_phrases")
                last_updated_row = cursor.fetchone()
                last_updated = last_updated_row[0].isoformat() if last_updated_row and last_updated_row[0] else "Unknown"
            except Exception:
                last_updated = "Unknown"
            
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
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                self._return_db_connection(conn)

    def get_repository_phrases(self) -> Dict[str, List[str]]:
        """Get all phrases from repository."""
        conn = None
        try:
            # Get phrases from PostgreSQL
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            try:
                debug_enabled = os.getenv("VOS_DEBUG_PHRASES_DB", "false").lower() in {"1", "true", "yes", "on"}
                if debug_enabled:
                    try:
                        cursor.execute("SELECT COUNT(*) FROM repository_phrases")
                        repo_count = cursor.fetchone()[0]
                    except Exception:
                        repo_count = None
                    try:
                        cursor.execute("SELECT COUNT(*) FROM rebuttal_phrases")
                        rebuttal_count = cursor.fetchone()[0]
                    except Exception:
                        rebuttal_count = None
                    logger.info(f"Phrase DB counts: repository_phrases={repo_count}, rebuttal_phrases={rebuttal_count}")

                results = []
                try:
                    cursor.execute("SELECT category, phrase FROM repository_phrases ORDER BY category, phrase")
                    results = cursor.fetchall()
                except Exception as e:
                    logger.warning(f"Failed to read repository_phrases, trying rebuttal_phrases: {e}")

                if not results:
                    try:
                        cursor.execute("SELECT category, phrase FROM rebuttal_phrases ORDER BY category, phrase")
                        results = cursor.fetchall()
                    except Exception:
                        results = []
                
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
        except Exception as e:
            logger.error(f"Failed to get repository phrases: {e}", exc_info=True)
            return {}
        finally:
            if conn:
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
            logger.info(
                f"Updated and saved learning settings: confidence={self.confidence_threshold}, "
                f"frequency={self.frequency_threshold}, auto_approve={self.auto_approve_threshold}"
            )
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
