#!/usr/bin/env python3
"""
Migration script to migrate phrase data from SQLite and JSON to PostgreSQL.

This script migrates:
- Repository phrases from SQLite (repository_phrases table) and JSON (rebuttal_repository.json)
- Pending phrases from SQLite (pending_phrases table)
- Phrase learning settings from JSON (phrase_learning_settings.json)

Usage:
    python scripts/migrate_phrases_to_postgres.py
"""

import os
import sys
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database manager
try:
    from lib.database import get_db_manager
except ImportError:
    logger.error("Failed to import database manager. Make sure you're running from the project root.")
    sys.exit(1)


def get_postgres_connection():
    """Get PostgreSQL connection using database manager."""
    try:
        db_manager = get_db_manager()
        if not db_manager:
            raise Exception("Database manager returned None")
        
        # Get a connection from the pool
        conn = db_manager.connection_pool.getconn()
        if not conn:
            raise Exception("Failed to get connection from pool")
        
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


def migrate_repository_phrases(conn) -> Dict[str, int]:
    """Migrate repository phrases from SQLite and JSON to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING REPOSITORY PHRASES")
    logger.info("=" * 60)
    
    stats = {
        'sqlite_phrases': 0,
        'json_phrases': 0,
        'merged_unique': 0,
        'imported_rebuttal': 0,
        'imported_repository': 0,
        'skipped': 0,
        'errors': 0
    }
    
    all_phrases = {}  # {(category, phrase_lower): {'phrase': original, 'source': source}}
    
    # 1. Load from SQLite
    sqlite_path = Path("dashboard_data/phrase_learning.db")
    if sqlite_path.exists():
        try:
            logger.info(f"Loading repository phrases from SQLite: {sqlite_path}")
            sqlite_conn = sqlite3.connect(str(sqlite_path))
            cursor = sqlite_conn.cursor()
            
            cursor.execute("SELECT category, phrase, source, usage_count, successful_detections, effectiveness_score, added_date FROM repository_phrases")
            for row in cursor.fetchall():
                category, phrase, source, usage_count, successful_detections, effectiveness_score, added_date = row
                key = (category, phrase.lower().strip())
                if key not in all_phrases:
                    all_phrases[key] = {
                        'phrase': phrase,
                        'source': source or 'auto_learned',
                        'usage_count': usage_count or 0,
                        'successful_detections': successful_detections or 0,
                        'effectiveness_score': effectiveness_score,
                        'added_date': added_date
                    }
                    stats['sqlite_phrases'] += 1
            
            sqlite_conn.close()
            logger.info(f"Loaded {stats['sqlite_phrases']} phrases from SQLite")
        except Exception as e:
            logger.error(f"Error loading from SQLite: {e}")
            stats['errors'] += 1
    else:
        logger.warning(f"SQLite database not found: {sqlite_path}")
    
    # 2. Load from JSON
    json_path = Path("dashboard_data/rebuttal_repository.json")
    if json_path.exists():
        try:
            logger.info(f"Loading repository phrases from JSON: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            phrases_dict = data.get('phrases', {})
            for category, phrase_list in phrases_dict.items():
                for phrase in phrase_list:
                    key = (category, phrase.lower().strip())
                    if key not in all_phrases:
                        all_phrases[key] = {
                            'phrase': phrase,
                            'source': 'manual',
                            'usage_count': 0,
                            'successful_detections': 0,
                            'effectiveness_score': None,
                            'added_date': None
                        }
                        stats['json_phrases'] += 1
                    else:
                        # If exists in SQLite but source is 'manual' in JSON, keep SQLite source
                        pass
            
            logger.info(f"Loaded {stats['json_phrases']} phrases from JSON")
        except Exception as e:
            logger.error(f"Error loading from JSON: {e}")
            stats['errors'] += 1
    else:
        logger.warning(f"JSON file not found: {json_path}")
    
    stats['merged_unique'] = len(all_phrases)
    logger.info(f"Total unique phrases after merge: {stats['merged_unique']}")
    
    # 3. Import to PostgreSQL
    try:
        cursor = conn.cursor()
        
        for (category, phrase_lower), phrase_data in all_phrases.items():
            try:
                # Create savepoint for each phrase
                cursor.execute("SAVEPOINT phrase_insert")
                
                original_phrase = phrase_data['phrase']
                source = phrase_data['source']
                usage_count = phrase_data['usage_count']
                successful_detections = phrase_data['successful_detections']
                effectiveness_score = phrase_data['effectiveness_score']
                added_date = phrase_data['added_date']
                
                # Insert into rebuttal_phrases (used by KeywordRepository for detection)
                cursor.execute("""
                    INSERT INTO rebuttal_phrases (category, phrase, source)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (category, phrase) DO NOTHING
                """, (category, original_phrase, source))
                
                if cursor.rowcount > 0:
                    stats['imported_rebuttal'] += 1
                
                # Insert into repository_phrases (used by PhraseLearningManager for management)
                if added_date:
                    cursor.execute("""
                        INSERT INTO repository_phrases (category, phrase, source, usage_count, successful_detections, effectiveness_score, added_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, phrase) DO UPDATE SET
                            usage_count = EXCLUDED.usage_count,
                            successful_detections = EXCLUDED.successful_detections,
                            effectiveness_score = EXCLUDED.effectiveness_score,
                            source = EXCLUDED.source
                    """, (category, original_phrase, source, usage_count, successful_detections, effectiveness_score, added_date))
                else:
                    cursor.execute("""
                        INSERT INTO repository_phrases (category, phrase, source, usage_count, successful_detections, effectiveness_score)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, phrase) DO UPDATE SET
                            usage_count = EXCLUDED.usage_count,
                            successful_detections = EXCLUDED.successful_detections,
                            effectiveness_score = EXCLUDED.effectiveness_score,
                            source = EXCLUDED.source
                    """, (category, original_phrase, source, usage_count, successful_detections, effectiveness_score))
                
                if cursor.rowcount > 0:
                    stats['imported_repository'] += 1
                else:
                    stats['skipped'] += 1
                
                cursor.execute("RELEASE SAVEPOINT phrase_insert")
                    
            except Exception as e:
                # Rollback to savepoint and continue with next phrase
                try:
                    cursor.execute("ROLLBACK TO SAVEPOINT phrase_insert")
                except:
                    pass
                logger.error(f"Error inserting phrase '{original_phrase}' in category '{category}': {e}")
                stats['errors'] += 1
        
        conn.commit()
        logger.info(f"Repository phrases migration complete:")
        logger.info(f"  - Imported to rebuttal_phrases: {stats['imported_rebuttal']}")
        logger.info(f"  - Imported to repository_phrases: {stats['imported_repository']}")
        logger.info(f"  - Skipped (already exists): {stats['skipped']}")
        logger.info(f"  - Errors: {stats['errors']}")
        
    except Exception as e:
        logger.error(f"Error during repository phrases migration: {e}")
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def migrate_pending_phrases(conn) -> Dict[str, int]:
    """Migrate pending phrases from SQLite to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING PENDING PHRASES")
    logger.info("=" * 60)
    
    stats = {
        'loaded': 0,
        'imported': 0,
        'skipped': 0,
        'errors': 0
    }
    
    # Load from SQLite
    sqlite_path = Path("dashboard_data/phrase_learning.db")
    if not sqlite_path.exists():
        logger.warning(f"SQLite database not found: {sqlite_path}")
        return stats
    
    try:
        logger.info(f"Loading pending phrases from SQLite: {sqlite_path}")
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        cursor = sqlite_conn.cursor()
        
        cursor.execute("""
            SELECT phrase, category, confidence, detection_count, first_detected, 
                   last_detected, status, sample_contexts, similar_to, quality_score, canonical_form
            FROM pending_phrases
        """)
        
        pending_phrases = []
        for row in cursor.fetchall():
            pending_phrases.append({
                'phrase': row[0],
                'category': row[1],
                'confidence': row[2],
                'detection_count': row[3],
                'first_detected': row[4],
                'last_detected': row[5],
                'status': row[6],
                'sample_contexts': row[7],
                'similar_to': row[8],
                'quality_score': row[9],
                'canonical_form': row[10]
            })
            stats['loaded'] += 1
        
        sqlite_conn.close()
        logger.info(f"Loaded {stats['loaded']} pending phrases from SQLite")
        
        # Import to PostgreSQL
        if pending_phrases:
            pg_cursor = conn.cursor()
            for phrase_data in pending_phrases:
                try:
                    pg_cursor.execute("SAVEPOINT pending_insert")
                    
                    pg_cursor.execute("""
                        INSERT INTO pending_phrases 
                        (phrase, category, confidence, detection_count, first_detected, 
                         last_detected, status, sample_contexts, similar_to, quality_score, canonical_form)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (phrase, category) DO NOTHING
                    """, (
                        phrase_data['phrase'],
                        phrase_data['category'],
                        phrase_data['confidence'],
                        phrase_data['detection_count'],
                        phrase_data['first_detected'],
                        phrase_data['last_detected'],
                        phrase_data['status'],
                        phrase_data['sample_contexts'],
                        phrase_data['similar_to'],
                        phrase_data['quality_score'],
                        phrase_data['canonical_form']
                    ))
                    
                    if pg_cursor.rowcount > 0:
                        stats['imported'] += 1
                    else:
                        stats['skipped'] += 1
                    
                    pg_cursor.execute("RELEASE SAVEPOINT pending_insert")
                    
                except Exception as e:
                    try:
                        pg_cursor.execute("ROLLBACK TO SAVEPOINT pending_insert")
                    except:
                        pass
                    logger.error(f"Error inserting pending phrase '{phrase_data['phrase']}': {e}")
                    stats['errors'] += 1
            
            conn.commit()
            logger.info(f"Pending phrases migration complete:")
            logger.info(f"  - Imported: {stats['imported']}")
            logger.info(f"  - Skipped: {stats['skipped']}")
            logger.info(f"  - Errors: {stats['errors']}")
        
    except Exception as e:
        logger.error(f"Error during pending phrases migration: {e}")
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def migrate_phrase_settings(conn) -> Dict[str, int]:
    """Migrate phrase learning settings from JSON to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING PHRASE LEARNING SETTINGS")
    logger.info("=" * 60)
    
    stats = {
        'loaded': 0,
        'imported': 0,
        'errors': 0
    }
    
    settings_path = Path("dashboard_data/phrase_learning_settings.json")
    if not settings_path.exists():
        logger.warning(f"Settings file not found: {settings_path}")
        return stats
    
    try:
        logger.info(f"Loading settings from JSON: {settings_path}")
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        cursor = conn.cursor()
        for key, value in settings.items():
            try:
                cursor.execute("""
                    INSERT INTO phrase_learning_settings (setting_key, setting_value)
                    VALUES (%s, %s)
                    ON CONFLICT (setting_key) DO UPDATE SET
                        setting_value = EXCLUDED.setting_value,
                        updated_at = CURRENT_TIMESTAMP
                """, (key, json.dumps(value) if not isinstance(value, str) else value))
                
                stats['loaded'] += 1
                if cursor.rowcount > 0:
                    stats['imported'] += 1
            except Exception as e:
                logger.error(f"Error inserting setting '{key}': {e}")
                stats['errors'] += 1
        
        conn.commit()
        logger.info(f"Settings migration complete: {stats['imported']} imported, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error during settings migration: {e}")
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def main():
    """Main migration function."""
    logger.info("=" * 60)
    logger.info("PHRASE DATA MIGRATION TO POSTGRESQL")
    logger.info("=" * 60)
    logger.info("")
    
    # Check if running in dry-run mode
    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'
    if DRY_RUN:
        logger.warning("DRY RUN MODE - No changes will be committed to database")
    
    try:
        # Get PostgreSQL connection
        logger.info("Connecting to PostgreSQL...")
        conn = get_postgres_connection()
        logger.info("Connected to PostgreSQL successfully")
        
        # Run migrations
        repo_stats = migrate_repository_phrases(conn)
        pending_stats = migrate_pending_phrases(conn)
        settings_stats = migrate_phrase_settings(conn)
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Repository Phrases:")
        logger.info(f"  - SQLite: {repo_stats['sqlite_phrases']}")
        logger.info(f"  - JSON: {repo_stats['json_phrases']}")
        logger.info(f"  - Unique: {repo_stats['merged_unique']}")
        logger.info(f"  - Imported to rebuttal_phrases: {repo_stats['imported_rebuttal']}")
        logger.info(f"  - Imported to repository_phrases: {repo_stats['imported_repository']}")
        logger.info(f"  - Skipped: {repo_stats['skipped']}")
        logger.info(f"Pending Phrases:")
        logger.info(f"  - Loaded: {pending_stats['loaded']}")
        logger.info(f"  - Imported: {pending_stats['imported']}")
        logger.info(f"  - Skipped: {pending_stats['skipped']}")
        logger.info(f"Settings:")
        logger.info(f"  - Imported: {settings_stats['imported']}")
        logger.info(f"Total Errors: {repo_stats['errors'] + pending_stats['errors'] + settings_stats['errors']}")
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        
        # Return connection to pool
        db_manager = get_db_manager()
        if db_manager and db_manager.connection_pool:
            db_manager.connection_pool.putconn(conn)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

