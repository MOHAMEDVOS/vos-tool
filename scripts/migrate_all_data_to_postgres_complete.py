"""
Comprehensive data migration script to migrate ALL application data from local JSON files to PostgreSQL.

This script migrates:
1. Users (with ReadyMode credentials) - CRITICAL
2. Phrases (from SQLite + JSON)
3. Agent audit results
4. Campaign audit results
5. Lite audit results
6. Daily counters
7. Quota management data
8. Admin limits
9. Admin audit logs
10. Subscriptions
11. Dashboard sharing
12. Learned rebuttals
13. App settings
14. Active sessions (optional)

Features:
- Comprehensive validation
- Transaction-based rollback
- Error handling for edge cases
- Progress tracking
- Detailed reporting
"""

import sys
import os
from pathlib import Path
import json
import sqlite3
import pandas as pd
from datetime import datetime, date, time
from typing import Dict, List, Tuple, Any, Optional
import logging
import hashlib
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import migration lock system
try:
    from lib.migration_lock import MigrationLock
    LOCK_AVAILABLE = True
except ImportError:
    LOCK_AVAILABLE = False
    logger.warning("Migration lock system not available - concurrent access protection disabled")

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try to import dateutil (optional)
try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    date_parser = None
    logger.warning("python-dateutil not installed. Some date parsing may be limited. Install with: pip install python-dateutil")

# Database connection settings
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'vos_tool'),
    'user': os.getenv('POSTGRES_USER', 'vos_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

# Migration configuration
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'
MIGRATE_SESSIONS = os.getenv('MIGRATE_SESSIONS', 'false').lower() == 'true'  # Usually skip expired sessions

# Global migration statistics
MIGRATION_STATS = {
    'users': {'imported': 0, 'skipped': 0, 'errors': 0},
    'phrases': {'imported': 0, 'skipped': 0, 'errors': 0},
    'agent_audits': {'imported': 0, 'skipped': 0, 'errors': 0},
    'campaign_audits': {'imported': 0, 'skipped': 0, 'errors': 0},
    'lite_audits': {'imported': 0, 'skipped': 0, 'errors': 0},
    'daily_counters': {'imported': 0, 'skipped': 0, 'errors': 0},
    'quotas': {'imported': 0, 'skipped': 0, 'errors': 0},
    'admin_limits': {'imported': 0, 'skipped': 0, 'errors': 0},
    'admin_audit': {'imported': 0, 'skipped': 0, 'errors': 0},
    'subscriptions': {'imported': 0, 'skipped': 0, 'errors': 0},
    'dashboard_sharing': {'imported': 0, 'skipped': 0, 'errors': 0},
    'learned_rebuttals': {'imported': 0, 'skipped': 0, 'errors': 0},
    'app_settings': {'imported': 0, 'skipped': 0, 'errors': 0},
    'sessions': {'imported': 0, 'skipped': 0, 'errors': 0}
}


def get_postgres_connection():
    """Get PostgreSQL connection."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False  # Use transactions
        return conn
    except ImportError:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


def parse_datetime(dt_str: Any, default: Optional[datetime] = None) -> Optional[datetime]:
    """Parse datetime string with multiple format support."""
    if dt_str is None:
        return default
    if isinstance(dt_str, datetime):
        return dt_str
    if isinstance(dt_str, date):
        return datetime.combine(dt_str, time.min)
    
        try:
            # Try ISO format first
            return datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        except:
            try:
                # Try dateutil parser if available
                if DATEUTIL_AVAILABLE:
                    return date_parser.parse(str(dt_str))
            except:
                pass
            try:
                # Try common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%b %d, %I:%M%p']:
                    try:
                        return datetime.strptime(str(dt_str), fmt)
                    except:
                        continue
            except:
                pass
    
    return default


def parse_date(date_str: Any, default: Optional[date] = None) -> Optional[date]:
    """Parse date string."""
    if date_str is None:
        return default
    if isinstance(date_str, date):
        return date_str
    if isinstance(date_str, datetime):
        return date_str.date()
    
    try:
        return date.fromisoformat(str(date_str))
    except:
        dt = parse_datetime(date_str)
        return dt.date() if dt else default


def parse_time(time_str: Any, default: time = time(0, 0)) -> time:
    """Parse time string."""
    if time_str is None:
        return default
    if isinstance(time_str, time):
        return time_str
    
    try:
        return datetime.strptime(str(time_str), '%H:%M').time()
    except:
        return default


def safe_json_read(file_path: Path, default: Any = None) -> Any:
    """Safely read JSON file with error handling."""
    if not file_path.exists():
        return default if default is not None else {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return default if default is not None else {}
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return default if default is not None else {}


def validate_user_exists(cursor, username: str) -> bool:
    """Validate user exists in database."""
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
    return cursor.fetchone()[0] > 0


def migrate_users(conn) -> Dict[str, int]:
    """Migrate users from users.json to PostgreSQL. CRITICAL - must be first."""
    logger.info("=" * 60)
    logger.info("MIGRATING USERS (CRITICAL - Must be first)")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    users_file = Path("dashboard_data/users/users.json")
    if not users_file.exists():
        logger.warning(f"Users file not found: {users_file}")
        return stats
    
    try:
        users_data = safe_json_read(users_file, {})
        if not users_data:
            logger.warning("Users file is empty")
            return stats
        
        cursor = conn.cursor()
        
        for username, user_data in users_data.items():
            try:
                # Normalize username
                username = username.strip()
                if not username:
                    logger.warning("Skipping user with empty username")
                    continue
                
                # Extract fields
                app_pass_hash = user_data.get('app_pass_hash', '')
                app_pass_salt = user_data.get('app_pass_salt')
                readymode_user = user_data.get('readymode_user')
                readymode_pass_encrypted = user_data.get('readymode_pass_encrypted')  # CRITICAL - preserve encryption
                daily_limit = user_data.get('daily_limit', 5000)
                role = user_data.get('role', 'Auditor')
                created_by = user_data.get('created_by')
                # If created_by references a non-existent user, set to None to satisfy FK
                if created_by:
                    created_by = created_by.strip()
                    if created_by not in users_data:
                        created_by = None
                created_date = parse_datetime(user_data.get('created_date'))
                updated_at = parse_datetime(user_data.get('updated_at'))
                
                # Validate role
                if role not in ['Owner', 'Admin', 'Auditor']:
                    logger.warning(f"Invalid role '{role}' for user '{username}', defaulting to 'Auditor'")
                    role = 'Auditor'
                
                # Insert or update user
                cursor.execute("""
                    INSERT INTO users 
                    (username, app_pass_hash, app_pass_salt, readymode_user, readymode_pass_encrypted,
                     daily_limit, role, created_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                        app_pass_hash = EXCLUDED.app_pass_hash,
                        app_pass_salt = EXCLUDED.app_pass_salt,
                        readymode_user = EXCLUDED.readymode_user,
                        readymode_pass_encrypted = EXCLUDED.readymode_pass_encrypted,
                        daily_limit = EXCLUDED.daily_limit,
                        role = EXCLUDED.role,
                        created_by = EXCLUDED.created_by,
                        updated_at = EXCLUDED.updated_at
                """, (
                    username, app_pass_hash, app_pass_salt, readymode_user, readymode_pass_encrypted,
                    daily_limit, role, created_by, created_date, updated_at
                ))
                
                if cursor.rowcount > 0:
                    stats['imported'] += 1
                    logger.info(f"  [OK] Migrated user: {username} (role: {role})")
                else:
                    stats['skipped'] += 1
                    logger.debug(f"  [WARN] User already exists: {username}")
                
            except Exception as e:
                logger.error(f"  [ERROR] Error migrating user '{username}': {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
            logger.info("DRY RUN - Rolled back transaction")
        
        logger.info(f"[OK] Users migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating users: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['users'] = stats
    return stats


def migrate_lite_audits(conn) -> Dict[str, int]:
    """Migrate lite audit results from JSON files."""
    logger.info("=" * 60)
    logger.info("MIGRATING LITE AUDITS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    lite_audit_dir = Path("dashboard_data/lite_audits")
    if not lite_audit_dir.exists():
        logger.warning(f"Lite audits directory not found: {lite_audit_dir}")
        return stats
    
    json_files = list(lite_audit_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} lite audit files")
    
    try:
        cursor = conn.cursor()
        
        for json_file in json_files:
            try:
                logger.info(f"Processing: {json_file.name}")
                
                # Extract username from filename
                username = json_file.stem.replace("lite_audits_", "")
                if not username or username == "lite_audits":
                    username = "Mohamed Abdo"
                
                # Validate user exists
                if not validate_user_exists(cursor, username):
                    logger.warning(f"  User '{username}' not found, skipping file")
                    stats['skipped'] += 1
                    continue
                
                # Read JSON
                data = safe_json_read(json_file, {})
                audit_results = data.get('audit_results', [])
                
                if not audit_results:
                    logger.info(f"  No audit results in: {json_file.name}")
                    continue
                
                imported_count = 0
                cursor.execute("SAVEPOINT lite_audit_file")
                
                for record in audit_results:
                    try:
                        agent_name = record.get('Agent Name') or record.get('agent_name')
                        file_name = record.get('File Name') or record.get('file_name')
                        file_path = record.get('File Path') or record.get('file_path')
                        detection_results = {k: v for k, v in record.items() 
                                           if k not in ['Agent Name', 'agent_name', 'File Name', 'file_name', 
                                                       'File Path', 'file_path']}
                        
                        cursor.execute("""
                            INSERT INTO lite_audit_results 
                            (username, agent_name, file_name, file_path, detection_results)
                            VALUES (%s, NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''), %s)
                            ON CONFLICT DO NOTHING
                        """, (
                            username, agent_name, file_name, file_path, json.dumps(detection_results)
                        ))
                        
                        if cursor.rowcount > 0:
                            imported_count += 1
                            
                    except Exception as e:
                        logger.error(f"  Error inserting lite audit record: {e}")
                        stats['errors'] += 1
                        cursor.execute("ROLLBACK TO SAVEPOINT lite_audit_file")
                        cursor.execute("SAVEPOINT lite_audit_file")
                
                cursor.execute("RELEASE SAVEPOINT lite_audit_file")
                
                if imported_count > 0:
                    stats['imported'] += imported_count
                    logger.info(f"  [OK] Imported {imported_count} lite audit records for '{username}'")
                
            except Exception as e:
                logger.error(f"  [ERROR] Error processing {json_file.name}: {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Lite audits migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating lite audits: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['lite_audits'] = stats
    return stats


def migrate_daily_counters(conn) -> Dict[str, int]:
    """Migrate daily counters from JSON files."""
    logger.info("=" * 60)
    logger.info("MIGRATING DAILY COUNTERS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    counters_dir = Path("dashboard_data/daily_counters")
    if not counters_dir.exists():
        logger.warning(f"Daily counters directory not found: {counters_dir}")
        return stats
    
    json_files = list(counters_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} daily counter files")
    
    try:
        cursor = conn.cursor()
        
        for json_file in json_files:
            try:
                # Extract username and date from filename: {username}_{YYYY-MM-DD}.json
                parts = json_file.stem.split('_')
                if len(parts) < 2:
                    logger.warning(f"  Invalid filename format: {json_file.name}")
                    continue
                
                date_str = parts[-1]  # Last part is date
                username = '_'.join(parts[:-1])  # Everything else is username
                
                counter_date = parse_date(date_str)
                if not counter_date:
                    logger.warning(f"  Could not parse date from filename: {json_file.name}")
                    continue
                
                # Validate user exists
                if not validate_user_exists(cursor, username):
                    logger.warning(f"  User '{username}' not found, skipping")
                    stats['skipped'] += 1
                    continue
                
                # Read counter data
                data = safe_json_read(json_file, {})
                download_count = data.get('download_count', 0)
                last_updated = parse_datetime(data.get('last_updated'))
                
                cursor.execute("""
                    INSERT INTO daily_counters (username, date, download_count, last_updated)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username, date) DO UPDATE SET
                        download_count = EXCLUDED.download_count,
                        last_updated = EXCLUDED.last_updated
                """, (username, counter_date, download_count, last_updated))
                
                if cursor.rowcount > 0:
                    stats['imported'] += 1
                
            except Exception as e:
                logger.error(f"  [ERROR] Error processing {json_file.name}: {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Daily counters migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating daily counters: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['daily_counters'] = stats
    return stats


def migrate_quotas(conn) -> Dict[str, int]:
    """Migrate quota management and daily usage data."""
    logger.info("=" * 60)
    logger.info("MIGRATING QUOTA DATA")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    try:
        cursor = conn.cursor()
        
        # 1. Migrate quota system config
        quota_file = Path("dashboard_data/quota_management.json")
        if quota_file.exists():
            quota_data = safe_json_read(quota_file, {})
            system_config = quota_data.get('system_config', {})
            
            if system_config:
                try:
                    cursor.execute("""
                        INSERT INTO quota_system_config 
                        (quota_reset_time, default_admin_user_limit, default_admin_daily_quota)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        parse_time(system_config.get('quota_reset_time', '00:00')),
                        system_config.get('default_admin_user_limit', 10),
                        system_config.get('default_admin_daily_quota', 5000)
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                        logger.info("  [OK] Migrated quota system config")
                except Exception as e:
                    logger.error(f"  Error migrating quota system config: {e}")
                    stats['errors'] += 1
            
            # 2. Migrate admin limits
            admin_limits = quota_data.get('admin_limits', {})
            for admin_username, limits in admin_limits.items():
                try:
                    if not validate_user_exists(cursor, admin_username):
                        logger.warning(f"  Admin user '{admin_username}' not found, skipping limits")
                        continue
                    
                    cursor.execute("""
                        INSERT INTO admin_limits 
                        (admin_username, max_active_users, per_user_daily_quota, 
                         monthly_creation_limit, cooldown_days, enabled)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (admin_username) DO UPDATE SET
                            max_active_users = EXCLUDED.max_active_users,
                            per_user_daily_quota = EXCLUDED.per_user_daily_quota,
                            monthly_creation_limit = EXCLUDED.monthly_creation_limit,
                            cooldown_days = EXCLUDED.cooldown_days,
                            enabled = EXCLUDED.enabled
                    """, (
                        admin_username,
                        limits.get('max_active_users'),
                        limits.get('per_user_daily_quota'),
                        limits.get('monthly_creation_limit'),
                        limits.get('cooldown_days'),
                        limits.get('enabled', True)
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error migrating admin limits for '{admin_username}': {e}")
                    stats['errors'] += 1
            
            # 3. Migrate user quota assignments
            user_assignments = quota_data.get('user_assignments', {})
            for user_username, assignment in user_assignments.items():
                try:
                    if not validate_user_exists(cursor, user_username):
                        logger.warning(f"  User '{user_username}' not found, skipping assignment")
                        continue
                    
                    assigned_to_admin = assignment.get('assigned_to_admin')
                    if assigned_to_admin and not validate_user_exists(cursor, assigned_to_admin):
                        logger.warning(f"  Admin '{assigned_to_admin}' not found, skipping assignment")
                        continue
                    
                    cursor.execute("""
                        INSERT INTO user_quota_assignments 
                        (user_username, assigned_to_admin, daily_quota)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_username) DO UPDATE SET
                            assigned_to_admin = EXCLUDED.assigned_to_admin,
                            daily_quota = EXCLUDED.daily_quota
                    """, (
                        user_username,
                        assigned_to_admin,
                        assignment.get('daily_quota')
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error migrating user assignment for '{user_username}': {e}")
                    stats['errors'] += 1
        
        # 4. Migrate daily usage
        usage_file = Path("dashboard_data/daily_usage.json")
        if usage_file.exists():
            usage_data = safe_json_read(usage_file, {})
            last_reset_date = parse_date(usage_data.get('last_reset_date'))
            admin_usage = usage_data.get('admin_usage', {})
            
            today = date.today()
            for admin_username, admin_data in admin_usage.items():
                try:
                    if not validate_user_exists(cursor, admin_username):
                        continue
                    
                    # Insert admin usage
                    cursor.execute("""
                        INSERT INTO admin_usage 
                        (admin_username, date, total_used, last_reset_date)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (admin_username, date) DO UPDATE SET
                            total_used = EXCLUDED.total_used,
                            last_reset_date = EXCLUDED.last_reset_date
                    """, (admin_username, today, admin_data.get('total_used', 0), last_reset_date))
                    
                    # Insert user usage
                    users_usage = admin_data.get('users_usage', {})
                    for user_username, usage_count in users_usage.items():
                        cursor.execute("""
                            INSERT INTO user_usage 
                            (admin_username, user_username, date, usage_count)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (admin_username, user_username, date) DO UPDATE SET
                                usage_count = EXCLUDED.usage_count
                        """, (admin_username, user_username, today, usage_count))
                    
                    stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error migrating usage for admin '{admin_username}': {e}")
                    stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Quota data migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating quota data: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['quotas'] = stats
    return stats


def migrate_admin_audit(conn) -> Dict[str, int]:
    """Migrate admin audit logs."""
    logger.info("=" * 60)
    logger.info("MIGRATING ADMIN AUDIT LOGS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    audit_file = Path("dashboard_data/admin_audit/admin_audit.json")
    if not audit_file.exists():
        logger.warning(f"Admin audit file not found: {audit_file}")
        return stats
    
    try:
        data = safe_json_read(audit_file, {})
        logs = data.get('logs', [])
        
        if not logs:
            logger.info("No audit logs to migrate")
            return stats
        
        cursor = conn.cursor()
        
        for log_entry in logs:
            try:
                username = log_entry.get('admin_username', '')
                if not username or not validate_user_exists(cursor, username):
                    logger.warning(f"  Admin user '{username}' not found, skipping log entry")
                    stats['skipped'] += 1
                    continue
                
                action = log_entry.get('action', '')
                target_username = log_entry.get('target_username')
                details = log_entry.get('details', {})
                ip_address = log_entry.get('ip_address')
                # Sanitize IP for inet type
                if not ip_address or str(ip_address).lower() in ['unknown', 'none', 'null', '']:
                    ip_address = None
                timestamp = parse_datetime(log_entry.get('timestamp'))
                
                cursor.execute("""
                    INSERT INTO audit_logs 
                    (username, action, details, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    username, action, json.dumps(details), ip_address, timestamp
                ))
                
                if cursor.rowcount > 0:
                    stats['imported'] += 1
                
            except Exception as e:
                logger.error(f"  Error inserting audit log: {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Admin audit logs migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating admin audit logs: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['admin_audit'] = stats
    return stats


def migrate_subscriptions(conn) -> Dict[str, int]:
    """Migrate subscription data."""
    logger.info("=" * 60)
    logger.info("MIGRATING SUBSCRIPTIONS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    try:
        cursor = conn.cursor()
        
        # 1. Migrate subscription plans
        plans_file = Path("dashboard_data/subscriptions/subscription_plans.json")
        if plans_file.exists():
            plans_data = safe_json_read(plans_file, {})
            for tier, plan_data in plans_data.items():
                try:
                    cursor.execute("""
                        INSERT INTO subscription_plans 
                        (tier, name, price_monthly, description, max_admin_users, max_auditor_users,
                         daily_call_limit, features, trial_days)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tier) DO UPDATE SET
                            name = EXCLUDED.name,
                            price_monthly = EXCLUDED.price_monthly,
                            description = EXCLUDED.description,
                            max_admin_users = EXCLUDED.max_admin_users,
                            max_auditor_users = EXCLUDED.max_auditor_users,
                            daily_call_limit = EXCLUDED.daily_call_limit,
                            features = EXCLUDED.features,
                            trial_days = EXCLUDED.trial_days
                    """, (
                        tier,
                        plan_data.get('name'),
                        plan_data.get('price_monthly'),
                        plan_data.get('description'),
                        plan_data.get('max_admin_users'),
                        plan_data.get('max_auditor_users'),
                        plan_data.get('daily_call_limit'),
                        json.dumps(plan_data.get('features', [])),
                        plan_data.get('trial_days')
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error migrating subscription plan '{tier}': {e}")
                    stats['errors'] += 1
        
        # 2. Migrate subscription data
        sub_data_file = Path("dashboard_data/subscriptions/subscription_data.json")
        if sub_data_file.exists():
            sub_data = safe_json_read(sub_data_file, {})
            try:
                cursor.execute("""
                    INSERT INTO subscription_data 
                    (plan, status, start_date, end_date, created_by, created_at,
                     payment_history, usage_stats, upgraded_by, upgraded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    sub_data.get('plan'),
                    sub_data.get('status', 'active'),
                    parse_datetime(sub_data.get('start_date')),
                    parse_datetime(sub_data.get('end_date')),
                    sub_data.get('created_by'),
                    parse_datetime(sub_data.get('created_at')),
                    json.dumps(sub_data.get('payment_history', [])),
                    json.dumps(sub_data.get('usage_stats', {})),
                    sub_data.get('upgraded_by'),
                    parse_datetime(sub_data.get('upgraded_at'))
                ))
                if cursor.rowcount > 0:
                    stats['imported'] += 1
            except Exception as e:
                logger.error(f"  Error migrating subscription data: {e}")
                stats['errors'] += 1
        
        # 3. Migrate client subscriptions
        client_subs_file = Path("dashboard_data/subscriptions/client_subscriptions.json")
        if client_subs_file.exists():
            client_subs = safe_json_read(client_subs_file, {})
            for client_id, client_data in client_subs.items():
                try:
                    cursor.execute("""
                        INSERT INTO client_subscriptions 
                        (client_id, client_name, tier, start_date, end_date, is_trial,
                         trial_end_date, is_active, created_by, created_at, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (client_id) DO UPDATE SET
                            client_name = EXCLUDED.client_name,
                            tier = EXCLUDED.tier,
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date,
                            is_trial = EXCLUDED.is_trial,
                            trial_end_date = EXCLUDED.trial_end_date,
                            is_active = EXCLUDED.is_active,
                            notes = EXCLUDED.notes
                    """, (
                        client_id,
                        client_data.get('client_name'),
                        client_data.get('tier'),
                        parse_datetime(client_data.get('start_date')),
                        parse_datetime(client_data.get('end_date')),
                        client_data.get('is_trial', False),
                        parse_datetime(client_data.get('trial_end_date')),
                        client_data.get('is_active', True),
                        client_data.get('created_by'),
                        parse_datetime(client_data.get('created_at')),
                        client_data.get('notes', '')
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error migrating client subscription '{client_id}': {e}")
                    stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Subscriptions migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating subscriptions: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['subscriptions'] = stats
    return stats


def migrate_dashboard_sharing(conn) -> Dict[str, int]:
    """Migrate dashboard sharing configuration."""
    logger.info("=" * 60)
    logger.info("MIGRATING DASHBOARD SHARING")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    sharing_file = Path("dashboard_data/dashboard_sharing.json")
    if not sharing_file.exists():
        logger.warning(f"Dashboard sharing file not found: {sharing_file}")
        return stats
    
    try:
        data = safe_json_read(sharing_file, {})
        sharing_groups = data.get('sharing_groups', {})
        user_dashboard_mode = data.get('user_dashboard_mode', {})
        
        cursor = conn.cursor()
        
        # Migrate user dashboard modes
        for username, mode in user_dashboard_mode.items():
            try:
                if not validate_user_exists(cursor, username):
                    logger.warning(f"  User '{username}' not found, skipping")
                    stats['skipped'] += 1
                    continue
                
                cursor.execute("""
                    INSERT INTO dashboard_sharing 
                    (username, sharing_groups, dashboard_mode)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                        sharing_groups = EXCLUDED.sharing_groups,
                        dashboard_mode = EXCLUDED.dashboard_mode
                """, (
                    username,
                    json.dumps(sharing_groups.get(username, {})),
                    mode
                ))
                if cursor.rowcount > 0:
                    stats['imported'] += 1
            except Exception as e:
                logger.error(f"  Error migrating dashboard sharing for '{username}': {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Dashboard sharing migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating dashboard sharing: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['dashboard_sharing'] = stats
    return stats


def migrate_learned_rebuttals(conn) -> Dict[str, int]:
    """Migrate learned rebuttals from JSON."""
    logger.info("=" * 60)
    logger.info("MIGRATING LEARNED REBUTTALS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    learned_file = Path("dashboard_data/learned_rebuttals.json")
    if not learned_file.exists():
        logger.warning(f"Learned rebuttals file not found: {learned_file}")
        return stats
    
    try:
        data = safe_json_read(learned_file, {})
        learned_phrases = data.get('learned_phrases', {})
        
        cursor = conn.cursor()
        
        for category, phrases_list in learned_phrases.items():
            for phrase_data in phrases_list:
                try:
                    phrase = phrase_data.get('phrase', '')
                    if not phrase:
                        continue
                    
                    cursor.execute("""
                        INSERT INTO learned_rebuttals 
                        (category, phrase, learned_date, source, confidence, user_feedback)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, phrase) DO NOTHING
                    """, (
                        category,
                        phrase,
                        parse_datetime(phrase_data.get('learned_date')),
                        phrase_data.get('source'),
                        phrase_data.get('confidence'),
                        phrase_data.get('user_feedback')
                    ))
                    if cursor.rowcount > 0:
                        stats['imported'] += 1
                except Exception as e:
                    logger.error(f"  Error inserting learned rebuttal: {e}")
                    stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] Learned rebuttals migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating learned rebuttals: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['learned_rebuttals'] = stats
    return stats


def migrate_app_settings(conn) -> Dict[str, int]:
    """Migrate app settings from JSON."""
    logger.info("=" * 60)
    logger.info("MIGRATING APP SETTINGS")
    logger.info("=" * 60)
    
    stats = {'imported': 0, 'skipped': 0, 'errors': 0}
    
    settings_file = Path("dashboard_data/settings/app_settings.json")
    if not settings_file.exists():
        logger.info(f"App settings file not found: {settings_file} (this is OK if using defaults)")
        return stats
    
    try:
        data = safe_json_read(settings_file, {})
        cursor = conn.cursor()
        
        # Flatten nested settings structure
        def flatten_settings(settings_dict, prefix=''):
            for key, value in settings_dict.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_settings(value, full_key)
                else:
                    category = prefix.split('.')[0] if prefix else 'system'
                    try:
                        cursor.execute("""
                            INSERT INTO app_settings (setting_key, setting_value, category)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (setting_key) DO UPDATE SET
                                setting_value = EXCLUDED.setting_value,
                                category = EXCLUDED.category
                        """, (full_key, json.dumps(value) if not isinstance(value, (str, int, float, bool)) else str(value), category))
                        if cursor.rowcount > 0:
                            stats['imported'] += 1
                    except Exception as e:
                        logger.error(f"  Error inserting setting '{full_key}': {e}")
                        stats['errors'] += 1
        
        flatten_settings(data)
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        
        logger.info(f"[OK] App settings migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error migrating app settings: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['app_settings'] = stats
    return stats


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
        
        # Check if source column exists (do this once, not per phrase)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rebuttal_phrases' AND column_name = 'source';
        """)
        has_source_column = cursor.fetchone() is not None
        
        for (category, phrase_lower), source in all_phrases.items():
            try:
                # Create savepoint for each phrase
                cursor.execute("SAVEPOINT phrase_insert")
                
                # Get original phrase (preserve case from first source)
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
                    original_phrase = phrase_lower
                
                # Insert based on whether source column exists (checked above)
                if has_source_column:
                    cursor.execute("""
                        INSERT INTO rebuttal_phrases (category, phrase, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (category, phrase) DO NOTHING
                    """, (category, original_phrase, source))
                else:
                    cursor.execute("""
                        INSERT INTO rebuttal_phrases (category, phrase)
                        VALUES (%s, %s)
                        ON CONFLICT (category, phrase) DO NOTHING
                    """, (category, original_phrase))
                
                cursor.execute("RELEASE SAVEPOINT phrase_insert")
                
                if cursor.rowcount > 0:
                    stats['imported'] += 1
                else:
                    stats['skipped'] += 1
                    
            except Exception as e:
                # Rollback to savepoint and continue with next phrase
                try:
                    cursor.execute("ROLLBACK TO SAVEPOINT phrase_insert")
                except:
                    pass
                logger.error(f"Error inserting phrase '{original_phrase}' in category '{category}': {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        logger.info(f"[OK] Phrases migration complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error importing phrases to PostgreSQL: {e}")
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['phrases'] = stats
    return stats


def migrate_campaign_audits(conn) -> Dict[str, int]:
    """Migrate campaign audit results from CSV files to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING CAMPAIGN AUDITS")
    logger.info("=" * 60)
    
    stats = {'files_processed': 0, 'records_imported': 0, 'records_skipped': 0, 'errors': 0}
    
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
                
                campaign_name = csv_file.stem.split('_')[0]
                metadata_file = csv_file.with_suffix('.json')
                username = 'Mohamed Abdo'
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            username = metadata.get('username', 'Mohamed Abdo')
                    except:
                        pass
                
                if not validate_user_exists(cursor, username):
                    logger.warning(f"  User '{username}' not found, using 'Mohamed Abdo'")
                    username = "Mohamed Abdo"
                
                df = pd.read_csv(csv_file)
                if df.empty:
                    logger.warning(f"  Empty CSV file: {csv_file.name}")
                    continue
                
                record_count = len(df)
                releasing_count = len(df[df.get("Releasing Detection", pd.Series()) == "Yes"]) if "Releasing Detection" in df.columns else 0
                late_hello_count = len(df[df.get("Late Hello Detection", pd.Series()) == "Yes"]) if "Late Hello Detection" in df.columns else 0
                rebuttal_count = len(df[df.get("Rebuttal Detection", pd.Series()) == "Yes"]) if "Rebuttal Detection" in df.columns else 0
                
                try:
                    parts = csv_file.stem.split('_')
                    if len(parts) >= 3:
                        date_str = parts[1]
                        time_str = parts[2]
                        timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                    else:
                        timestamp = datetime.fromtimestamp(csv_file.stat().st_mtime)
                except:
                    timestamp = datetime.fromtimestamp(csv_file.stat().st_mtime)
                
                metadata = {
                    "campaign_name": campaign_name,
                    "username": username,
                    "filename": csv_file.name,
                    "data": df.to_dict('records')
                }
                
                cursor.execute("""
                    INSERT INTO campaign_audit_results 
                    (campaign_name, username, timestamp, record_count, releasing_count, 
                     late_hello_count, rebuttal_count, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    campaign_name, username, timestamp, record_count, releasing_count,
                    late_hello_count, rebuttal_count, json.dumps(metadata)
                ))
                
                if cursor.rowcount > 0:
                    stats['records_imported'] += record_count
                    stats['files_processed'] += 1
                    logger.info(f"  [OK] Imported {record_count} records for campaign '{campaign_name}'")
                else:
                    stats['records_skipped'] += record_count
                    logger.info(f"  [WARN] Skipped (duplicate): {record_count} records for campaign '{campaign_name}'")
                    
            except Exception as e:
                logger.error(f"  [ERROR] Error processing {csv_file.name}: {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        logger.info(f"[OK] Campaign audits migration complete: {stats['files_processed']} files, {stats['records_imported']} records imported")
        
    except Exception as e:
        logger.error(f"Error migrating campaign audits: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['campaign_audits'] = stats
    return stats


def migrate_agent_audits(conn) -> Dict[str, int]:
    """Migrate agent audit results from JSON files to PostgreSQL."""
    logger.info("=" * 60)
    logger.info("MIGRATING AGENT AUDITS")
    logger.info("=" * 60)
    
    stats = {'files_processed': 0, 'records_imported': 0, 'records_skipped': 0, 'errors': 0}
    
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
                
                username = json_file.stem.replace("agent_audits_", "").replace("shared_", "")
                if username == "agent_audits" or not username:
                    username = "Mohamed Abdo"
                
                if not validate_user_exists(cursor, username):
                    logger.warning(f"  User '{username}' not found, using 'Mohamed Abdo'")
                    username = "Mohamed Abdo"
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                audit_results = data.get('audit_results', [])
                if not audit_results:
                    logger.warning(f"  No audit results in: {json_file.name}")
                    continue
                
                imported_count = 0
                cursor.execute("SAVEPOINT agent_audit_file")
                for record in audit_results:
                    try:
                        agent_name = record.get('Agent Name') or record.get('agent_name', '')
                        file_name = record.get('File Name') or record.get('file_name', '')
                        file_path = record.get('File Path') or record.get('file_path', '')
                        
                        # Convert to proper boolean (must be True or False, not None)
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
                            # Handle special case: "Error" should be False
                            if rebuttal.lower() == 'error':
                                rebuttal = False
                            else:
                                rebuttal = rebuttal.lower() in ['yes', 'true', '1', 'y']
                        elif rebuttal is None:
                            rebuttal = False
                        else:
                            rebuttal = bool(rebuttal)
                        
                        # Convert to 'Yes'/'No' strings (database has CHECK constraint expecting text, not boolean)
                        releasing_str = 'Yes' if releasing else 'No'
                        late_hello_str = 'Yes' if late_hello else 'No'
                        rebuttal_str = 'Yes' if rebuttal else 'No'
                        
                        transcript = record.get('Transcription') or record.get('transcript', '')
                        timestamp = parse_datetime(record.get('Timestamp') or record.get('timestamp'))
                        call_duration = record.get('Call Duration') or record.get('call_duration')
                        confidence_score = record.get('Confidence Score') or record.get('confidence_score')
                        
                        metadata = {k: v for k, v in record.items() 
                                  if k not in ['Agent Name', 'agent_name', 'File Name', 'file_name', 
                                              'File Path', 'file_path', 'Releasing Detection', 
                                              'Late Hello Detection', 'Rebuttal Detection', 
                                              'Transcription', 'transcript', 'Timestamp', 'timestamp',
                                              'Call Duration', 'call_duration', 'Confidence Score', 'confidence_score']}
                        
                        # Convert call_duration to numeric if it's a string
                        call_duration_numeric = None
                        if call_duration is not None:
                            try:
                                call_duration_numeric = float(call_duration) if call_duration else None
                            except (ValueError, TypeError):
                                call_duration_numeric = None
                        
                        # Convert confidence_score to numeric if it's a string
                        confidence_numeric = None
                        if confidence_score is not None:
                            try:
                                confidence_numeric = float(confidence_score) if confidence_score else None
                            except (ValueError, TypeError):
                                confidence_numeric = None
                        
                        cursor.execute("""
                            INSERT INTO agent_audit_results 
                            (username, agent_name, file_name, file_path, releasing_detection, 
                             late_hello_detection, rebuttal_detection, timestamp, transcript, 
                             call_duration, confidence_score, metadata)
                            VALUES (%s, %s, NULLIF(%s, ''), NULLIF(%s, ''), %s, %s, %s, %s, NULLIF(%s, ''), 
                                    %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (
                            username, agent_name if agent_name else None, file_name if file_name else None,
                            file_path if file_path else None, releasing_str, late_hello_str, rebuttal_str, timestamp,
                            transcript if transcript else None, call_duration_numeric,
                            confidence_numeric, json.dumps(metadata) if metadata else None
                        ))
                        
                        if cursor.rowcount > 0:
                            imported_count += 1
                            
                    except Exception as e:
                        logger.error(f"  Error inserting record: {e}")
                        stats['errors'] += 1
                        cursor.execute("ROLLBACK TO SAVEPOINT agent_audit_file")
                        cursor.execute("SAVEPOINT agent_audit_file")
                
                cursor.execute("RELEASE SAVEPOINT agent_audit_file")
                
                if imported_count > 0:
                    stats['records_imported'] += imported_count
                    stats['files_processed'] += 1
                    logger.info(f"  [OK] Imported {imported_count} records for user '{username}'")
                else:
                    logger.info(f"  [WARN] No new records imported from: {json_file.name}")
                    
            except Exception as e:
                logger.error(f"  [ERROR] Error processing {json_file.name}: {e}")
                stats['errors'] += 1
        
        if not DRY_RUN:
            conn.commit()
        else:
            conn.rollback()
        logger.info(f"[OK] Agent audits migration complete: {stats['files_processed']} files, {stats['records_imported']} records imported")
        
    except Exception as e:
        logger.error(f"Error migrating agent audits: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        stats['errors'] += 1
    
    MIGRATION_STATS['agent_audits'] = stats
    return stats


def main():
    """Main migration function with proper dependency order."""
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE DATA MIGRATION TO POSTGRESQL")
    logger.info("=" * 80)
    logger.info(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    # Initialize migration lock
    migration_lock = None
    if LOCK_AVAILABLE:
        migration_lock = MigrationLock()
        
        # Check if migration is already in progress
        if migration_lock.is_migration_in_progress():
            status = migration_lock.get_migration_status()
            logger.error("=" * 80)
            logger.error("MIGRATION ALREADY IN PROGRESS")
            logger.error("=" * 80)
            if status:
                logger.error(f"Status: {status.get('status', 'unknown')}")
                logger.error(f"Started: {status.get('started_at', 'unknown')}")
            logger.error("")
            logger.error("Another migration process is currently running.")
            logger.error("If you believe this is an error, check for stale lock files:")
            logger.error(f"  - {migration_lock.lock_file}")
            logger.error("")
            logger.error("To force unlock (USE WITH CAUTION):")
            logger.error("  python scripts/force_unlock_migration.py")
            sys.exit(1)
    
    logger.info(f"Dry Run: {DRY_RUN}")
    logger.info("")
    
    if DRY_RUN:
        logger.warning("DRY RUN MODE - No data will be committed")
    
    # Get database connection
    conn = None
    migration_lock = None
    
    try:
        conn = get_postgres_connection()
        logger.info("Connected to PostgreSQL")
        
        # Acquire locks if available
        if LOCK_AVAILABLE:
            migration_lock = MigrationLock()
            
            # Check if migration is already in progress
            if migration_lock.is_migration_in_progress():
                status = migration_lock.get_migration_status()
                logger.error("=" * 80)
                logger.error("MIGRATION ALREADY IN PROGRESS")
                logger.error("=" * 80)
                if status:
                    logger.error(f"Status: {status.get('status', 'unknown')}")
                    logger.error(f"Started: {status.get('started_at', 'unknown')}")
                logger.error("")
                logger.error("Another migration process is currently running.")
                logger.error("If you believe this is an error, check for stale lock files:")
                logger.error(f"  - {migration_lock.lock_file}")
                logger.error("")
                logger.error("To force unlock (USE WITH CAUTION):")
                logger.error("  python scripts/force_unlock_migration.py")
                conn.close()
                sys.exit(1)
            
            # Acquire all locks
            if not migration_lock.acquire_all_locks(conn):
                logger.error("Failed to acquire migration locks")
                logger.error("Another migration may be running, or locks are held by another process")
                conn.close()
                sys.exit(1)
            logger.info("Migration locks acquired - application will be in read-only mode")
            migration_lock.update_status('running', {'stage': 'initializing', 'progress': 0})
        
        # Migration order (respecting dependencies)
        # 1. Users (MUST BE FIRST - referenced by everything)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_users', 'progress': 5})
        user_stats = migrate_users(conn)
        
        # 2. Quota system config (no dependencies)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_quotas', 'progress': 10})
        quota_stats = migrate_quotas(conn)
        
        # 3. App settings (no dependencies)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_app_settings', 'progress': 15})
        settings_stats = migrate_app_settings(conn)
        
        # 4. Subscriptions (no dependencies)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_subscriptions', 'progress': 20})
        sub_stats = migrate_subscriptions(conn)
        
        # 5. Daily counters (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_daily_counters', 'progress': 25})
        counter_stats = migrate_daily_counters(conn)
        
        # 6. Admin audit logs (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_admin_audit', 'progress': 30})
        admin_audit_stats = migrate_admin_audit(conn)
        
        # 7. Learned rebuttals (no dependencies)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_learned_rebuttals', 'progress': 35})
        learned_stats = migrate_learned_rebuttals(conn)
        
        # 8. Phrases (no dependencies)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_phrases', 'progress': 40})
        phrase_stats = migrate_phrases(conn)
        
        # 9. Agent audits (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_agent_audits', 'progress': 50})
        agent_stats = migrate_agent_audits(conn)
        
        # 10. Lite audits (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_lite_audits', 'progress': 70})
        lite_stats = migrate_lite_audits(conn)
        
        # 11. Campaign audits (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_campaign_audits', 'progress': 85})
        campaign_stats = migrate_campaign_audits(conn)
        
        # 12. Dashboard sharing (depends on users)
        if migration_lock:
            migration_lock.update_status('running', {'stage': 'migrating_dashboard_sharing', 'progress': 95})
        sharing_stats = migrate_dashboard_sharing(conn)
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Users: {user_stats['imported']} imported, {user_stats['skipped']} skipped, {user_stats['errors']} errors")
        logger.info(f"Quotas: {quota_stats['imported']} imported, {quota_stats['skipped']} skipped, {quota_stats['errors']} errors")
        logger.info(f"App Settings: {settings_stats['imported']} imported, {settings_stats['skipped']} skipped, {settings_stats['errors']} errors")
        logger.info(f"Subscriptions: {sub_stats['imported']} imported, {sub_stats['skipped']} skipped, {sub_stats['errors']} errors")
        logger.info(f"Daily Counters: {counter_stats['imported']} imported, {counter_stats['skipped']} skipped, {counter_stats['errors']} errors")
        logger.info(f"Admin Audit: {admin_audit_stats['imported']} imported, {admin_audit_stats['skipped']} skipped, {admin_audit_stats['errors']} errors")
        logger.info(f"Learned Rebuttals: {learned_stats['imported']} imported, {learned_stats['skipped']} skipped, {learned_stats['errors']} errors")
        logger.info(f"Phrases: {phrase_stats['imported']} imported, {phrase_stats['skipped']} skipped, {phrase_stats['errors']} errors")
        logger.info(f"Agent Audits: {agent_stats.get('records_imported', agent_stats.get('imported', 0))} imported, {agent_stats.get('records_skipped', agent_stats.get('skipped', 0))} skipped, {agent_stats.get('errors', 0)} errors")
        logger.info(f"Lite Audits: {lite_stats['imported']} imported, {lite_stats['skipped']} skipped, {lite_stats['errors']} errors")
        logger.info(f"Campaign Audits: {campaign_stats.get('records_imported', campaign_stats.get('imported', 0))} imported, {campaign_stats.get('records_skipped', campaign_stats.get('skipped', 0))} skipped, {campaign_stats.get('errors', 0)} errors")
        logger.info(f"Dashboard Sharing: {sharing_stats['imported']} imported, {sharing_stats['skipped']} skipped, {sharing_stats['errors']} errors")
        logger.info("")
        
        total_imported = sum(s.get('imported', s.get('records_imported', 0)) for s in MIGRATION_STATS.values())
        total_errors = sum(s.get('errors', 0) for s in MIGRATION_STATS.values())
        
        if total_errors == 0:
            logger.info("Migration complete with no errors!")
            if migration_lock:
                migration_lock.update_status('completed', {'progress': 100, 'total_imported': total_imported})
        else:
            logger.warning(f"Migration complete with {total_errors} errors. Please review the log.")
            if migration_lock:
                migration_lock.update_status('completed', {'progress': 100, 'total_imported': total_imported, 'total_errors': total_errors})
        
        # Release locks before closing connection
        if migration_lock:
            migration_lock.release_all_locks()
            logger.info("Migration locks released - application can resume normal operation")
        
        if conn:
            conn.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Release locks on error
        if migration_lock:
            migration_lock.update_status('failed', {'error': str(e)})
            migration_lock.release_all_locks()
            logger.info("Migration locks released due to error")
        
        if conn:
            conn.close()
        
        sys.exit(1)


if __name__ == "__main__":
    main()

