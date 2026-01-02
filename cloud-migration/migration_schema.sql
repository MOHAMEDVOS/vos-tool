-- Additional Schema for Complete Data Migration
-- This script creates all missing tables required for full JSON to PostgreSQL migration
-- Run this AFTER init.sql to ensure all tables exist

-- ============================================================================
-- 1. ALTER EXISTING TABLES
-- ============================================================================

-- Add missing columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS app_pass_salt VARCHAR(255),
ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);

-- ============================================================================
-- 2. APP SETTINGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setting_key VARCHAR(255) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_settings_category ON app_settings(category);
CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(setting_key);

-- ============================================================================
-- 3. QUOTA SYSTEM TABLES
-- ============================================================================

-- Quota system configuration
CREATE TABLE IF NOT EXISTS quota_system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quota_reset_time TIME DEFAULT '00:00',
    default_admin_user_limit INTEGER DEFAULT 10,
    default_admin_daily_quota INTEGER DEFAULT 5000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Admin limits
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

CREATE INDEX IF NOT EXISTS idx_admin_limits_admin ON admin_limits(admin_username);

-- User quota assignments
CREATE TABLE IF NOT EXISTS user_quota_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_username VARCHAR(255) NOT NULL,
    assigned_to_admin VARCHAR(255) NOT NULL,
    daily_quota INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_username)
);

CREATE INDEX IF NOT EXISTS idx_user_assignments_user ON user_quota_assignments(user_username);
CREATE INDEX IF NOT EXISTS idx_user_assignments_admin ON user_quota_assignments(assigned_to_admin);

-- Admin usage tracking
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

CREATE INDEX IF NOT EXISTS idx_admin_usage_admin_date ON admin_usage(admin_username, date);

-- User usage tracking
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

CREATE INDEX IF NOT EXISTS idx_user_usage_admin_user_date ON user_usage(admin_username, user_username, date);

-- Daily counters (for download tracking)
CREATE TABLE IF NOT EXISTS daily_counters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    download_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_counters_user_date ON daily_counters(username, date);

-- ============================================================================
-- 4. SUBSCRIPTION TABLES
-- ============================================================================

-- Subscription plans (reference data)
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

-- Subscription data (current subscription)
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

-- Client subscriptions
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

CREATE INDEX IF NOT EXISTS idx_client_subscriptions_active ON client_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_client_subscriptions_tier ON client_subscriptions(tier);

-- ============================================================================
-- 5. DASHBOARD SHARING
-- ============================================================================

CREATE TABLE IF NOT EXISTS dashboard_sharing (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    sharing_groups JSONB,
    dashboard_mode VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username)
);

CREATE INDEX IF NOT EXISTS idx_dashboard_sharing_username ON dashboard_sharing(username);

CREATE TABLE IF NOT EXISTS admin_audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_username VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    target_username VARCHAR(255),
    details JSONB,
    ip_address INET,
    session_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_audits_admin_username ON admin_audits(admin_username);
CREATE INDEX IF NOT EXISTS idx_admin_audits_created_at ON admin_audits(created_at);

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_created_at ON subscriptions(created_at);

-- ============================================================================
-- 6. REBUTTAL PHRASES
-- ============================================================================

CREATE TABLE IF NOT EXISTS rebuttal_phrases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    phrase TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, phrase)
);

CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_category ON rebuttal_phrases(category);
CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_source ON rebuttal_phrases(source);

CREATE TRIGGER update_rebuttal_phrases_updated_at 
    BEFORE UPDATE ON rebuttal_phrases 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 7. LEARNED REBUTTALS
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_learned_rebuttals_category ON learned_rebuttals(category);
CREATE INDEX IF NOT EXISTS idx_learned_rebuttals_source ON learned_rebuttals(source);

-- ============================================================================
-- 8. TRIGGERS FOR UPDATED_AT
-- ============================================================================

-- Apply updated_at triggers to new tables
CREATE TRIGGER update_app_settings_updated_at 
    BEFORE UPDATE ON app_settings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quota_system_config_updated_at 
    BEFORE UPDATE ON quota_system_config 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_limits_updated_at 
    BEFORE UPDATE ON admin_limits 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_quota_assignments_updated_at 
    BEFORE UPDATE ON user_quota_assignments 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_usage_updated_at 
    BEFORE UPDATE ON admin_usage 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_usage_updated_at 
    BEFORE UPDATE ON user_usage 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_counters_updated_at 
    BEFORE UPDATE ON daily_counters 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscription_plans_updated_at 
    BEFORE UPDATE ON subscription_plans 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscription_data_updated_at 
    BEFORE UPDATE ON subscription_data 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_subscriptions_updated_at 
    BEFORE UPDATE ON client_subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dashboard_sharing_updated_at 
    BEFORE UPDATE ON dashboard_sharing 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at 
    BEFORE UPDATE ON subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 9. GRANT PERMISSIONS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vos_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vos_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO vos_user;

