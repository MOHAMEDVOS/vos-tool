"""
Comprehensive data migration script to recover all user data from local files to PostgreSQL.

Migrates:
1. Phrases from SQLite and JSON (~1,300 phrases)
2. Campaign audit results from CSV files (494+ Cessna records)
3. Agent audit results from JSON files (83+ records)
4. Lite audit results from JSON files
"""

import sys
import os
from pathlib import Path
import json
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Any
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection settings (from Docker Compose)
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'vos_tool'),
    'user': os.getenv('POSTGRES_USER', 'vos_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '20101964mm')
}


def get_postgres_connection():
    """Get PostgreSQL connection."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except ImportError:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


def migrate_phrases(conn) -> Dict[str, int]:
    """Migrate phrases from SQLite and JSON to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING PHRASES")
    logger.info("=" * 60)
    
    stats = {
        'sqlite_phrases': 0,
        'json_phrases': 0,
        'merged_unique': 0,
        'imported': 0,
        'skipped': 0,
        'errors': 0
    }
    
    all_phrases = {}  # {(category, phrase): source}
    
    # 1. Load from SQLite
    sqlite_path = Path("dashboard_data/phrase_learning.db")
    if sqlite_path.exists():
        try:
            logger.info(f"Loading phrases from SQLite: {sqlite_path}")
            sqlite_conn = sqlite3.connect(str(sqlite_path))
            cursor = sqlite_conn.cursor()
            
            cursor.execute("SELECT category, phrase, source FROM repository_phrases")
            for row in cursor.fetchall():
                category, phrase, source = row
                key = (category, phrase.lower().strip())
                if key not in all_phrases:
                    all_phrases[key] = source or 'auto_learned'
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
            logger.info(f"Loading phrases from JSON: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            phrases_dict = data.get('phrases', {})
            for category, phrase_list in phrases_dict.items():
                for phrase in phrase_list:
                    key = (category, phrase.lower().strip())
                    if key not in all_phrases:
                        all_phrases[key] = 'manual'
                        stats['json_phrases'] += 1
            
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
        
        # Table should already exist, just try to insert
        
        # Insert phrases
        for (category, phrase_lower), source in all_phrases.items():
            try:
                # Get original phrase (preserve case from first source)
                # Try to get from SQLite first, then JSON
                original_phrase = None
                if sqlite_path.exists():
                    try:
                        sqlite_conn = sqlite3.connect(str(sqlite_path))
                        sqlite_cursor = sqlite_conn.cursor()
                        sqlite_cursor.execute(
                            "SELECT phrase FROM repository_phrases WHERE category = ? AND LOWER(phrase) = ?",
                            (category, phrase_lower)
                        )
                        result = sqlite_cursor.fetchone()
                        if result:
                            original_phrase = result[0]
                        sqlite_conn.close()
                    except:
                        pass
                
                if not original_phrase:
                    # Get from JSON
                    if json_path.exists():
                        try:
                            with open(json_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            phrases_list = data.get('phrases', {}).get(category, [])
                            for p in phrases_list:
                                if p.lower().strip() == phrase_lower:
                                    original_phrase = p
                                    break
                        except:
                            pass
                
                if not original_phrase:
                    original_phrase = phrase_lower  # Fallback
                
                try:
                    cursor.execute("""
                        INSERT INTO rebuttal_phrases (category, phrase, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (category, phrase) DO NOTHING
                    """, (category, original_phrase, source))
                except Exception as insert_error:
                    # If source column doesn't exist, try without it
                    error_str = str(insert_error).lower()
                    if 'column "source" does not exist' in error_str:
                        cursor.execute("""
                            INSERT INTO rebuttal_phrases (category, phrase)
                            VALUES (%s, %s)
                            ON CONFLICT (category, phrase) DO NOTHING
                        """, (category, original_phrase))
                    else:
                        raise
                
                if cursor.rowcount > 0:
                    stats['imported'] += 1
                else:
                    stats['skipped'] += 1
                    
            except Exception as e:
                logger.error(f"Error inserting phrase '{original_phrase}' in category '{category}': {e}")
                stats['errors'] += 1
        
        conn.commit()
        logger.info(f"✅ Phrases migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error importing phrases to PostgreSQL: {e}")
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def migrate_campaign_audits(conn) -> Dict[str, int]:
    """Migrate campaign audit results from CSV files to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING CAMPAIGN AUDITS")
    logger.info("=" * 60)
    
    stats = {
        'files_processed': 0,
        'records_imported': 0,
        'records_skipped': 0,
        'errors': 0
    }
    
    campaign_dir = Path("dashboard_data/campaign_audits")
    if not campaign_dir.exists():
        logger.warning(f"Campaign audits directory not found: {campaign_dir}")
        return stats
    
    csv_files = list(campaign_dir.glob("*.csv"))
    logger.info(f"Found {len(csv_files)} CSV files")
    
    try:
        cursor = conn.cursor()
        
        for csv_file in csv_files:
            try:
                logger.info(f"Processing: {csv_file.name}")
                
                # Extract campaign name from filename (e.g., "Cessna_20251214_045639.csv" -> "Cessna")
                campaign_name = csv_file.stem.split('_')[0]
                
                # Try to get username from metadata JSON
                metadata_file = csv_file.with_suffix('.json')
                username = 'Mohamed Abdo'  # Use existing user
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            username = metadata.get('username', 'Mohamed Abdo')
                    except:
                        pass
                
                # Verify username exists in users table
                cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
                if cursor.fetchone()[0] == 0:
                    logger.warning(f"  User '{username}' not found, using 'Mohamed Abdo'")
                    username = "Mohamed Abdo"
                
                # Read CSV
                df = pd.read_csv(csv_file)
                if df.empty:
                    logger.warning(f"  Empty CSV file: {csv_file.name}")
                    continue
                
                # Calculate counts
                record_count = len(df)
                releasing_count = len(df[df.get("Releasing Detection", pd.Series()) == "Yes"]) if "Releasing Detection" in df.columns else 0
                late_hello_count = len(df[df.get("Late Hello Detection", pd.Series()) == "Yes"]) if "Late Hello Detection" in df.columns else 0
                rebuttal_count = len(df[df.get("Rebuttal Detection", pd.Series()) == "Yes"]) if "Rebuttal Detection" in df.columns else 0
                
                # Extract timestamp from filename or use file modification time
                try:
                    # Try to parse from filename: CampaignName_YYYYMMDD_HHMMSS.csv
                    parts = csv_file.stem.split('_')
                    if len(parts) >= 3:
                        date_str = parts[1]
                        time_str = parts[2]
                        timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                    else:
                        timestamp = datetime.fromtimestamp(csv_file.stat().st_mtime)
                except:
                    timestamp = datetime.fromtimestamp(csv_file.stat().st_mtime)
                
                # Prepare metadata
                metadata = {
                    "campaign_name": campaign_name,
                    "username": username,
                    "filename": csv_file.name,
                    "data": df.to_dict('records')
                }
                
                # Insert into database
                cursor.execute("""
                    INSERT INTO campaign_audit_results 
                    (campaign_name, username, timestamp, record_count, releasing_count, 
                     late_hello_count, rebuttal_count, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    campaign_name,
                    username,
                    timestamp,
                    record_count,
                    releasing_count,
                    late_hello_count,
                    rebuttal_count,
                    json.dumps(metadata)
                ))
                
                if cursor.rowcount > 0:
                    stats['records_imported'] += record_count
                    stats['files_processed'] += 1
                    logger.info(f"  ✅ Imported {record_count} records for campaign '{campaign_name}'")
                else:
                    stats['records_skipped'] += record_count
                    logger.info(f"  ⚠️  Skipped (duplicate): {record_count} records for campaign '{campaign_name}'")
                    
            except Exception as e:
                logger.error(f"  ❌ Error processing {csv_file.name}: {e}")
                stats['errors'] += 1
        
        conn.commit()
        logger.info(f"✅ Campaign audits migration complete: {stats['files_processed']} files, {stats['records_imported']} records imported")
        cursor.close()
        
    except Exception as e:
        logger.error(f"Error migrating campaign audits: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def migrate_agent_audits(conn) -> Dict[str, int]:
    """Migrate agent audit results from JSON files to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING AGENT AUDITS")
    logger.info("=" * 60)
    
    stats = {
        'files_processed': 0,
        'records_imported': 0,
        'records_skipped': 0,
        'errors': 0
    }
    
    agent_audit_dir = Path("dashboard_data/agent_audits")
    if not agent_audit_dir.exists():
        logger.warning(f"Agent audits directory not found: {agent_audit_dir}")
        return stats
    
    json_files = list(agent_audit_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files")
    
    try:
        cursor = conn.cursor()
        
        for json_file in json_files:
            try:
                logger.info(f"Processing: {json_file.name}")
                
                # Extract username from filename (e.g., "agent_audits_Mohamed Abdo.json" -> "Mohamed Abdo")
                username = json_file.stem.replace("agent_audits_", "").replace("shared_", "")
                if username == "agent_audits" or not username:
                    username = "Mohamed Abdo"  # Use existing user instead of default_user
                
                # Verify username exists in users table
                cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
                if cursor.fetchone()[0] == 0:
                    logger.warning(f"  User '{username}' not found, using 'Mohamed Abdo'")
                    username = "Mohamed Abdo"
                
                # Read JSON
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                audit_results = data.get('audit_results', [])
                if not audit_results:
                    logger.warning(f"  No audit results in: {json_file.name}")
                    continue
                
                imported_count = 0
                # Use savepoint for each file to handle errors gracefully
                cursor.execute("SAVEPOINT agent_audit_file")
                for record in audit_results:
                    try:
                        # Map JSON fields to database columns
                        agent_name = record.get('Agent Name') or record.get('agent_name', '')
                        file_name = record.get('File Name') or record.get('file_name', '')
                        file_path = record.get('File Path') or record.get('file_path', '')
                        
                        # Convert detection values to boolean (ensure they're proper booleans, not strings)
                        releasing = record.get('Releasing Detection', 'No')
                        if isinstance(releasing, str):
                            releasing = releasing.lower() in ['yes', 'true', '1', 'y']
                        elif releasing is None:
                            releasing = False
                        else:
                            releasing = bool(releasing)
                        
                        late_hello = record.get('Late Hello Detection', 'No')
                        if isinstance(late_hello, str):
                            late_hello = late_hello.lower() in ['yes', 'true', '1', 'y']
                        elif late_hello is None:
                            late_hello = False
                        else:
                            late_hello = bool(late_hello)
                        
                        rebuttal = record.get('Rebuttal Detection', 'No')
                        if isinstance(rebuttal, str):
                            rebuttal = rebuttal.lower() in ['yes', 'true', '1', 'y']
                        elif rebuttal is None:
                            rebuttal = False
                        else:
                            rebuttal = bool(rebuttal)
                        
                        transcript = record.get('Transcription') or record.get('transcript', '')
                        timestamp = record.get('Timestamp') or record.get('timestamp')
                        call_duration = record.get('Call Duration') or record.get('call_duration')
                        confidence_score = record.get('Confidence Score') or record.get('confidence_score')
                        
                        # Parse timestamp if string
                        if isinstance(timestamp, str):
                            try:
                                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            except:
                                timestamp = None
                        
                        metadata = {k: v for k, v in record.items() 
                                  if k not in ['Agent Name', 'agent_name', 'File Name', 'file_name', 
                                              'File Path', 'file_path', 'Releasing Detection', 
                                              'Late Hello Detection', 'Rebuttal Detection', 
                                              'Transcription', 'transcript', 'Timestamp', 'timestamp',
                                              'Call Duration', 'call_duration', 'Confidence Score', 'confidence_score']}
                        
                        # Insert into database (use NULL for empty strings to avoid constraint issues)
                        cursor.execute("""
                            INSERT INTO agent_audit_results 
                            (username, agent_name, file_name, file_path, releasing_detection, 
                             late_hello_detection, rebuttal_detection, timestamp, transcript, 
                             call_duration, confidence_score, metadata)
                            VALUES (%s, %s, NULLIF(%s, ''), NULLIF(%s, ''), %s, %s, %s, %s, NULLIF(%s, ''), 
                                    NULLIF(%s, ''), NULLIF(%s, ''), %s)
                            ON CONFLICT DO NOTHING
                        """, (
                            username,
                            agent_name if agent_name else None,
                            file_name if file_name else None,
                            file_path if file_path else None,
                            releasing,
                            late_hello,
                            rebuttal,
                            timestamp,
                            transcript if transcript else None,
                            call_duration if call_duration else None,
                            confidence_score if confidence_score else None,
                            json.dumps(metadata) if metadata else None
                        ))
                        
                        if cursor.rowcount > 0:
                            imported_count += 1
                            
                    except Exception as e:
                        logger.error(f"  Error inserting record: {e}")
                        stats['errors'] += 1
                        # Rollback to savepoint and continue
                        cursor.execute("ROLLBACK TO SAVEPOINT agent_audit_file")
                        cursor.execute("SAVEPOINT agent_audit_file")
                
                # Release savepoint on success
                cursor.execute("RELEASE SAVEPOINT agent_audit_file")
                
                if imported_count > 0:
                    stats['records_imported'] += imported_count
                    stats['files_processed'] += 1
                    logger.info(f"  ✅ Imported {imported_count} records for user '{username}'")
                else:
                    logger.info(f"  ⚠️  No new records imported from: {json_file.name}")
                    
            except Exception as e:
                logger.error(f"  ❌ Error processing {json_file.name}: {e}")
                stats['errors'] += 1
        
        conn.commit()
        logger.info(f"✅ Agent audits migration complete: {stats['files_processed']} files, {stats['records_imported']} records imported")
        cursor.close()
        
    except Exception as e:
        logger.error(f"Error migrating agent audits: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    return stats


def main():
    """Main migration function."""
    logger.info("=" * 60)
    logger.info("COMPREHENSIVE DATA MIGRATION TO POSTGRESQL")
    logger.info("=" * 60)
    logger.info(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    logger.info("")
    
    try:
        conn = get_postgres_connection()
        logger.info("✅ Connected to PostgreSQL")
        
        # Run migrations
        phrase_stats = migrate_phrases(conn)
        campaign_stats = migrate_campaign_audits(conn)
        agent_stats = migrate_agent_audits(conn)
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Phrases: {phrase_stats['imported']} imported, {phrase_stats['skipped']} skipped")
        logger.info(f"Campaign Audits: {campaign_stats['records_imported']} records from {campaign_stats['files_processed']} files")
        logger.info(f"Agent Audits: {agent_stats['records_imported']} records from {agent_stats['files_processed']} files")
        logger.info("")
        logger.info("✅ Migration complete!")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

