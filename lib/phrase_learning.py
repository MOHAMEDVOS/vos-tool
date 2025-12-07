"""
Phrase Learning System for VOS Tool
Handles automatic learning and management of rebuttal phrases.
"""

import json
import sqlite3
import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class PhraseLearningManager:
    """Manages the self-learning phrase system."""
    
    def __init__(self):
        self.data_dir = Path("dashboard_data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.db_path = self.data_dir / "phrase_learning.db"
        self.repository_path = self.data_dir / "rebuttal_repository.json"
        self.settings_path = self.data_dir / "phrase_learning_settings.json"
        
        # Load settings from file or use defaults
        self._load_settings()
        
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
                        # Add to repository
                        success = self._add_to_repository(
                            phrase=phrase_text,
                            category=category or 'general',
                            source='auto_approved'  # Using auto_approved as the source for auto-approved phrases
                        )
                        
                        if success:
                            # Update status in pending_phrases
                            cursor.execute("""
                                UPDATE pending_phrases 
                                SET status = 'approved', 
                                    reviewed_at = CURRENT_TIMESTAMP,
                                    reviewed_by = 'auto_approve'
                                WHERE id = ?
                            """, (phrase_id,))
                            
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
    
    def _init_database(self):
        """Initialize the phrase learning database."""
        try:
            with self._get_db_connection() as conn:
                conn.execute("""
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
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS repository_phrases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phrase TEXT NOT NULL,
                        category TEXT NOT NULL,
                        source TEXT DEFAULT 'manual',
                        added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        UNIQUE(phrase, category)
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
                # Check if phrase already exists in pending
                cursor = conn.execute(
                    "SELECT id, detection_count FROM pending_phrases WHERE phrase = ? AND category = ?",
                    (clean_phrase, clean_category)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing entry
                    phrase_id, count = existing
                    new_count = count + 1
                    
                    conn.execute("""
                        UPDATE pending_phrases 
                        SET detection_count = ?, last_detected = CURRENT_TIMESTAMP,
                            confidence = MAX(confidence, ?), sample_contexts = ?
                        WHERE id = ?
                    """, (new_count, confidence, context[:500], phrase_id))
                    
                    # Check if it should be auto-approved
                    if (confidence >= self.auto_approve_threshold and 
                        new_count >= self.frequency_threshold):
                        self._auto_approve_phrase(phrase_id, clean_phrase, clean_category)
                        
                else:
                    # Insert new pending phrase
                    conn.execute("""
                        INSERT INTO pending_phrases 
                        (phrase, category, confidence, sample_contexts, similar_to)
                        VALUES (?, ?, ?, ?, ?)
                    """, (clean_phrase, clean_category, confidence, context[:500], similar_to))
                
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
                
                # Track in database
                with self._get_db_connection() as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO repository_phrases 
                        (phrase, category, source) VALUES (?, ?, ?)
                    """, (clean_phrase, category, source))
                
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
    
    def get_pending_phrases(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """Get pending phrases for review."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, phrase, category, confidence, detection_count,
                           first_detected, last_detected, sample_contexts, similar_to
                    FROM pending_phrases 
                    WHERE status = ?
                    ORDER BY confidence DESC, detection_count DESC
                """, (status,))
                
                phrases = []
                for row in cursor.fetchall():
                    phrases.append({
                        'id': row[0],
                        'phrase': row[1],
                        'category': row[2],
                        'confidence': row[3],
                        'detection_count': row[4],
                        'first_detected': row[5],
                        'last_detected': row[6],
                        'sample_contexts': row[7] or "",
                        'similar_to': row[8] or ""
                    })
                
                return phrases
                
        except Exception as e:
            logger.error(f"Failed to get pending phrases: {e}")
            return []
    
    def approve_phrase(self, phrase_id: int) -> bool:
        """Approve a pending phrase and add it to repository."""
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
                    "UPDATE pending_phrases SET status = 'approved' WHERE id = ?",
                    (phrase_id,)
                )
                
                # Add to repository
                self._add_to_repository(phrase, category, source='admin_approved')
                
                logger.info(f"Approved phrase: '{phrase}' in {category}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to approve phrase: {e}")
            return False
    
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
        try:
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            
            total_phrases = sum(len(phrases) for phrases in repository["phrases"].values())
            
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending'")
                pending_count = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM repository_phrases WHERE source = 'auto_learned'")
                auto_learned_count = cursor.fetchone()[0]
            
            return {
                'total_phrases': total_phrases,
                'pending_count': pending_count,
                'auto_learned_count': auto_learned_count,
                'categories': len(repository["phrases"]),
                'last_updated': repository.get("last_updated", "Unknown")
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}")
            return {
                'total_phrases': 0,
                'pending_count': 0,
                'auto_learned_count': 0,
                'categories': 0,
                'last_updated': "Unknown"
            }
    
    def get_repository_phrases(self) -> Dict[str, List[str]]:
        """Get all phrases from repository."""
        try:
            with open(self.repository_path, 'r') as f:
                repository = json.load(f)
            return repository.get("phrases", {})
        except Exception as e:
            logger.error(f"Failed to get repository phrases: {e}")
            return {}
    
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
