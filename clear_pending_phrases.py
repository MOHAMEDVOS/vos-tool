"""
Script to clear all pending phrases from the database.
Run this script to start fresh with an empty pending phrases list.
"""
import logging
from lib.phrase_learning import get_phrase_learning_manager

def main():
    """Clear all pending phrases from the database."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting to clear all pending phrases...")
    
    try:
        # Get the phrase learning manager
        manager = get_phrase_learning_manager()
        
        # Clear all pending phrases
        with manager._get_db_connection() as conn:
            # First get count for reporting
            cursor = conn.execute("SELECT COUNT(*) FROM pending_phrases WHERE status = 'pending'")
            count = cursor.fetchone()[0]
            
            if count == 0:
                print("\nNo pending phrases found to clear.")
                return
            
            # Delete all pending phrases
            conn.execute("DELETE FROM pending_phrases WHERE status = 'pending'")
            conn.commit()
            
            print(f"\n✅ Successfully removed {count} pending phrases")
            logger.info(f"Removed {count} pending phrases")
            
    except Exception as e:
        error_msg = f"Failed to clear pending phrases: {str(e)}"
        logger.error(error_msg)
        print(f"\n❌ {error_msg}")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()