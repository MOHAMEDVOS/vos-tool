"""
Daily data cleanup utility for VOS Railway.
Automatically deletes audit records older than 1 day to minimize database size and RAM usage.
"""

import logging
from datetime import datetime, timedelta
from lib.database import get_db_manager

logger = logging.getLogger(__name__)


def cleanup_old_audit_data(days_to_keep: int = 1):
    """
    Delete audit records older than specified days.
    
    Args:
        days_to_keep: Number of days to keep (default: 1 = today only)
    """
    db_manager = get_db_manager()
    
    if not db_manager:
        logger.warning("Database manager not available, skipping cleanup")
        return
    
    try:
        # Calculate cutoff date (today at 00:00:00 minus days_to_keep)
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"🗑️ Starting cleanup: deleting audit data older than {cutoff_date}")
        
        # Delete old agent audit results
        agent_query = """
            DELETE FROM agent_audit_results 
            WHERE created_at < %s
        """
        agent_deleted = db_manager.execute_query(agent_query, (cutoff_date,), fetch=False)
        logger.info(f"✅ Deleted old agent audit records (cutoff: {cutoff_date})")
        
        # Delete old lite audit results
        lite_query = """
            DELETE FROM lite_audit_results 
            WHERE created_at < %s
        """
        lite_deleted = db_manager.execute_query(lite_query, (cutoff_date,), fetch=False)
        logger.info(f"✅ Deleted old lite audit records (cutoff: {cutoff_date})")
        
        # Delete old campaign audit results
        campaign_query = """
            DELETE FROM campaign_audit_results 
            WHERE created_at < %s
        """
        campaign_deleted = db_manager.execute_query(campaign_query, (cutoff_date,), fetch=False)
        logger.info(f"✅ Deleted old campaign audit records (cutoff: {cutoff_date})")
        
        # Vacuum database to reclaim space (PostgreSQL)
        try:
            db_manager.execute_query("VACUUM ANALYZE", (), fetch=False)
            logger.info("✅ Database vacuumed to reclaim space")
        except Exception as e:
            logger.warning(f"Could not vacuum database: {e}")
        
        logger.info(f"🎉 Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        raise


def schedule_daily_cleanup():
    """
    Schedule cleanup to run daily at midnight.
    This should be called when the app starts.
    """
    import schedule
    import time
    import threading
    
    def run_cleanup():
        """Run cleanup in background thread"""
        try:
            cleanup_old_audit_data(days_to_keep=1)
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}")
    
    # Schedule cleanup for midnight every day
    schedule.every().day.at("00:00").do(run_cleanup)
    
    def run_scheduler():
        """Run scheduler in background thread"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("📅 Daily cleanup scheduled for midnight")


if __name__ == "__main__":
    # For manual testing
    logging.basicConfig(level=logging.INFO)
    cleanup_old_audit_data(days_to_keep=1)
