"""
Backup script for JSON data before migration.
Creates timestamped backup of dashboard_data directory.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_backup():
    """Create backup of dashboard_data directory."""
    dashboard_data = Path("dashboard_data")
    if not dashboard_data.exists():
        logger.error("dashboard_data directory not found")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"dashboard_data_backup_{timestamp}"
    backup_path = Path(backup_name)
    
    try:
        logger.info(f"Creating backup: {backup_path}")
        shutil.copytree(dashboard_data, backup_path, ignore=shutil.ignore_patterns('*.db-shm', '*.db-wal'))
        logger.info(f"✅ Backup created successfully: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        return None


if __name__ == "__main__":
    backup_path = create_backup()
    if backup_path:
        print(f"\nBackup location: {backup_path.absolute()}")
        print("You can restore by copying this directory back to 'dashboard_data'")

