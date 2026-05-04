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
            
    # 3. Seed phrases from backup
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
