"""
Create only missing tables (skip ALTER statements that require owner permissions).
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'vos_tool'),
    'user': os.getenv('POSTGRES_USER', 'vos_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

def create_missing_tables():
    """Create only missing tables."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if update_updated_at_column function exists, create if not
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        print("Created update_updated_at_column function")
        
        # Create rebuttal_phrases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rebuttal_phrases (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                category VARCHAR(100) NOT NULL,
                phrase TEXT NOT NULL,
                source VARCHAR(50) DEFAULT 'manual',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, phrase)
            );
        """)
        print("Created rebuttal_phrases table")
        
        # Create app_settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                setting_key VARCHAR(255) UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                category VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Created app_settings table")
        
        # Create quota_system_config
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_system_config (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                quota_reset_time TIME DEFAULT '00:00',
                default_admin_user_limit INTEGER DEFAULT 10,
                default_admin_daily_quota INTEGER DEFAULT 5000,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Created quota_system_config table")
        
        # Create admin_limits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_limits (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                admin_username VARCHAR(255) NOT NULL,
                max_active_users INTEGER,
                per_user_daily_quota INTEGER,
                monthly_creation_limit INTEGER,
                cooldown_days INTEGER,
                enabled BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_username)
            );
        """)
        print("Created admin_limits table")
        
        # Create user_quota_assignments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_quota_assignments (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_username VARCHAR(255) NOT NULL,
                assigned_to_admin VARCHAR(255) NOT NULL,
                daily_quota INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_username)
            );
        """)
        print("Created user_quota_assignments table")
        
        # Create admin_usage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_usage (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                admin_username VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                total_used INTEGER DEFAULT 0,
                last_reset_date DATE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_username, date)
            );
        """)
        print("Created admin_usage table")
        
        # Create user_usage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_usage (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                admin_username VARCHAR(255) NOT NULL,
                user_username VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_username, user_username, date)
            );
        """)
        print("Created user_usage table")
        
        # Create daily_counters
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_counters (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                username VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                download_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, date)
            );
        """)
        print("Created daily_counters table")
        
        # Create subscription_plans
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                tier VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price_monthly DECIMAL(10,2),
                description TEXT,
                max_admin_users INTEGER,
                max_auditor_users INTEGER,
                daily_call_limit INTEGER,
                features JSONB,
                trial_days INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Created subscription_plans table")
        
        # Create subscription_data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_data (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                plan VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                start_date TIMESTAMP WITH TIME ZONE,
                end_date TIMESTAMP WITH TIME ZONE,
                created_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                payment_history JSONB,
                usage_stats JSONB,
                upgraded_by VARCHAR(255),
                upgraded_at TIMESTAMP WITH TIME ZONE
            );
        """)
        print("Created subscription_data table")
        
        # Create client_subscriptions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_subscriptions (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                client_id VARCHAR(255) UNIQUE NOT NULL,
                client_name VARCHAR(255),
                tier VARCHAR(50),
                start_date TIMESTAMP WITH TIME ZONE,
                end_date TIMESTAMP WITH TIME ZONE,
                is_trial BOOLEAN DEFAULT FALSE,
                trial_end_date TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
        """)
        print("Created client_subscriptions table")
        
        # Create dashboard_sharing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_sharing (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                username VARCHAR(255) NOT NULL,
                sharing_groups JSONB,
                dashboard_mode VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username)
            );
        """)
        print("Created dashboard_sharing table")
        
        # Create learned_rebuttals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_rebuttals (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                category VARCHAR(100) NOT NULL,
                phrase TEXT NOT NULL,
                learned_date TIMESTAMP WITH TIME ZONE,
                source VARCHAR(50),
                confidence DECIMAL(5,4),
                user_feedback VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, phrase)
            );
        """)
        print("Created learned_rebuttals table")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_app_settings_category ON app_settings(category);",
            "CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(setting_key);",
            "CREATE INDEX IF NOT EXISTS idx_admin_limits_admin ON admin_limits(admin_username);",
            "CREATE INDEX IF NOT EXISTS idx_user_assignments_user ON user_quota_assignments(user_username);",
            "CREATE INDEX IF NOT EXISTS idx_user_assignments_admin ON user_quota_assignments(assigned_to_admin);",
            "CREATE INDEX IF NOT EXISTS idx_admin_usage_admin_date ON admin_usage(admin_username, date);",
            "CREATE INDEX IF NOT EXISTS idx_user_usage_admin_user_date ON user_usage(admin_username, user_username, date);",
            "CREATE INDEX IF NOT EXISTS idx_daily_counters_user_date ON daily_counters(username, date);",
            "CREATE INDEX IF NOT EXISTS idx_client_subscriptions_active ON client_subscriptions(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_client_subscriptions_tier ON client_subscriptions(tier);",
            "CREATE INDEX IF NOT EXISTS idx_dashboard_sharing_username ON dashboard_sharing(username);",
            "CREATE INDEX IF NOT EXISTS idx_learned_rebuttals_category ON learned_rebuttals(category);",
            "CREATE INDEX IF NOT EXISTS idx_learned_rebuttals_source ON learned_rebuttals(source);",
            "CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_category ON rebuttal_phrases(category);",
            "CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_source ON rebuttal_phrases(source);"
        ]
        
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
            except Exception as e:
                print(f"Note: Index creation (may already exist): {e}")
        
        print("\nAll tables created successfully!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_missing_tables()
    sys.exit(0 if success else 1)

