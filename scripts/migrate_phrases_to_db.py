
import os
import sys
import logging
from typing import Dict, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.rebuttal_detection import KeywordRepository
from lib.database import get_db_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_phrases():
    """Migrate hardcoded phrases to database."""
    logger.info("Starting phrase migration...")
    
    # Initialize DB manager
    db = get_db_manager()
    if not db:
        logger.error("Could not connect to database")
        return

    # Get hardcoded phrases
    repo = KeywordRepository(skip_database=True)
    hardcoded_phrases: Dict[str, List[str]] = repo.REBUTTAL_PHRASES

    total_inserted = 0
    total_skipped = 0
    
    for category, phrases in hardcoded_phrases.items():
        logger.info(f"Processing category: {category} ({len(phrases)} phrases)")
        
        for phrase in phrases:
            phrase = phrase.strip().lower()
            if not phrase:
                continue

            try:
                # Upsert phrase (insert if not exists)
                # We use ON CONFLICT DO NOTHING to skip duplicates
                query = """
                INSERT INTO rebuttal_phrases (category, phrase, source, created_at, updated_at)
                VALUES (%s, %s, 'hardcoded_migration', NOW(), NOW())
                ON CONFLICT (category, phrase) DO NOTHING
                RETURNING id;
                """
                result = db.execute_query(query, (category, phrase), fetch=True)
                
                if result:
                    total_inserted += 1
                else:
                    total_skipped += 1
                    
            except Exception as e:
                logger.error(f"Failed to insert phrase '{phrase}': {e}")

    logger.info("="*50)
    logger.info(f"Migration Complete")
    logger.info(f"Total Inserted: {total_inserted}")
    logger.info(f"Total Skipped (Already Existed): {total_skipped}")
    logger.info("="*50)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    migrate_phrases()
