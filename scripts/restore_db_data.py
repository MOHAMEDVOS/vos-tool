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
            
    # 3. Seed phrases
    logger.info("Restoring rebuttal phrases...")
    try:
        from lib.phrase_learning import PhraseLearningManager
        pm = PhraseLearningManager()
        # Force a rebuild just in case
        pm.rebuild_repository_from_existing()
        logger.info("Rebuttal phrases restored successfully.")
    except Exception as e:
        logger.error(f"Failed to restore phrases: {e}")
        
    logger.info("Database restoration complete! You can now log in.")

if __name__ == "__main__":
    restore_database()
