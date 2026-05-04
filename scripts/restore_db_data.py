import os
import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

import logging
from lib.database import get_db_manager
from backend.core.database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RestoreScript")

def restore_database():
    logger.info("Starting database restoration process...")
    
    # 1. Initialize DB and create tables if missing
    logger.info("Initializing database schema...")
    init_db()
    
    # 2. Add owner to whitelist
    db = get_db_manager()
    if db:
        logger.info("Adding primary owner to whitelist...")
        try:
            db.execute_query(
                """
                INSERT INTO whitelist (email, name, role) 
                VALUES ('mohamedibrahimpayonner@gmail.com', 'Mohamed Abdo', 'Owner')
                ON CONFLICT (email) DO UPDATE SET role = 'Owner'
                """,
                fetch=False
            )
            logger.info("Owner successfully added to whitelist.")
        except Exception as e:
            logger.error(f"Failed to insert owner into whitelist: {e}")
            
    # 3. Restore other tables from db_backup.json if it exists
    logger.info("Checking for full DB backup...")
    try:
        import json
        db_backup_file = root_dir / 'cloud-migration' / 'db_backup.json'
        if db_backup_file.exists() and db:
            with open(db_backup_file, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
            
            # Users
            users = db_data.get('users', [])
            for u in users:
                db.execute_query(
                    """
                    INSERT INTO users (id, username, app_pass_hash, readymode_user, readymode_pass_encrypted, role, created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (u['id'], u['username'], u.get('app_pass_hash',''), u.get('readymode_user'), u.get('readymode_pass_encrypted'), u.get('role', 'Auditor'), u.get('created_at'), u.get('updated_at')),
                    fetch=False
                )
            
            # Whitelist
            whitelist = db_data.get('whitelist', [])
            for w in whitelist:
                db.execute_query(
                    "INSERT INTO whitelist (email, role, created_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING",
                    (w['email'], w.get('role', 'Auditor'), w.get('created_at')),
                    fetch=False
                )
                
            # Audit Results
            for table in ['agent_audit_results', 'lite_audit_results', 'campaign_audit_results']:
                rows = db_data.get(table, [])
                for r in rows:
                    cols = list(r.keys())
                    if 'metadata' in cols and isinstance(r['metadata'], (dict, list)):
                        r['metadata'] = json.dumps(r['metadata'])
                    if 'detection_results' in cols and isinstance(r['detection_results'], (dict, list)):
                        r['detection_results'] = json.dumps(r['detection_results'])
                        
                    placeholders = ', '.join(['%s'] * len(cols))
                    col_names = ', '.join(cols)
                    values = tuple(r[c] for c in cols)
                    try:
                        db.execute_query(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING", values, fetch=False)
                    except Exception as err:
                        pass
            
            logger.info(f"Full DB backup restored! Loaded {len(users)} users, {len(whitelist)} whitelist entries.")
    except Exception as e:
        logger.error(f"Failed to restore full DB backup: {e}")

    # 4. Seed phrases from backup
    logger.info("Restoring phrases from backup file...")
    try:
        import json
        backup_file = root_dir / 'cloud-migration' / 'phrases_backup.json'
        
        if backup_file.exists():
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            repo_phrases = data.get('repository_phrases', [])
            rebuttal_phrases = data.get('rebuttal_phrases', [])
            
            logger.info(f"Found {len(repo_phrases)} repository phrases and {len(rebuttal_phrases)} rebuttal phrases in backup.")
            
            # Restore repository_phrases
            if repo_phrases and db:
                for p in repo_phrases:
                    db.execute_query(
                        """
                        INSERT INTO repository_phrases (phrase, category, source, usage_count, successful_detections) 
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (phrase, category) DO NOTHING
                        """,
                        (p['phrase'], p['category'], p.get('source', 'manual'), p.get('usage_count', 0), p.get('successful_detections', 0)),
                        fetch=False
                    )
                logger.info("repository_phrases restored successfully.")
                
            # Restore rebuttal_phrases
            if rebuttal_phrases and db:
                for p in rebuttal_phrases:
                    db.execute_query(
                        """
                        INSERT INTO rebuttal_phrases (category, phrase, source) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (category, phrase) DO NOTHING
                        """,
                        (p['category'], p['phrase'], p.get('source', 'manual')),
                        fetch=False
                    )
                logger.info("rebuttal_phrases restored successfully.")
                
            # Update phrase learning manager cache
            from lib.phrase_learning import PhraseLearningManager
            pm = PhraseLearningManager()
            pm.refresh_cache()
        else:
            logger.warning("phrases_backup.json not found! Falling back to KeywordRepository...")
            from lib.phrase_learning import PhraseLearningManager
            pm = PhraseLearningManager()
            pm.rebuild_repository_from_existing()
            
    except Exception as e:
        logger.error(f"Failed to restore phrases: {e}")
        
    logger.info("Database restoration complete! You can now log in.")

if __name__ == "__main__":
    restore_database()
