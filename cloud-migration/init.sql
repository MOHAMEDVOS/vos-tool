-- Database initialization script for VOS Tool
-- This script sets up the initial database schema and users

-- Create database if it doesn't exist
-- Note: This will be handled by the POSTGRES_DB environment variable in Docker

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    app_pass_hash VARCHAR(255) NOT NULL,
    readymode_user VARCHAR(255),
    readymode_pass_encrypted TEXT,
    daily_limit INTEGER DEFAULT 5000,
    role VARCHAR(50) DEFAULT 'Auditor',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    ip_address INET,
    user_agent TEXT
);

-- Create audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create call recordings metadata table
CREATE TABLE IF NOT EXISTS call_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_path TEXT NOT NULL,
    s3_key TEXT,
    file_size BIGINT,
    duration_seconds DECIMAL(10,2),
    uploaded_by VARCHAR(255) NOT NULL,
    campaign VARCHAR(255),
    agent_name VARCHAR(255),
    call_date DATE,
    analysis_status VARCHAR(50) DEFAULT 'pending',
    analysis_results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create analysis results table
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES call_recordings(id) ON DELETE CASCADE,
    analysis_type VARCHAR(100) NOT NULL, -- 'rebuttal', 'late_hello', 'releasing', etc.
    result JSONB NOT NULL,
    confidence_score DECIMAL(5,4),
    processing_time_ms INTEGER,
    model_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create quota tracking table
CREATE TABLE IF NOT EXISTS quota_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    downloads_count INTEGER DEFAULT 0,
    analysis_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, date)
);

-- Create agent audit results table
CREATE TABLE IF NOT EXISTS agent_audit_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255),
    file_name VARCHAR(255),
    file_path TEXT,
    releasing_detection VARCHAR(10) DEFAULT 'No',
    late_hello_detection VARCHAR(10) DEFAULT 'No',
    rebuttal_detection VARCHAR(10) DEFAULT 'No',
    timestamp TIMESTAMP WITH TIME ZONE,
    call_duration DECIMAL(10,2),
    transcript TEXT,
    confidence_score DECIMAL(5,4),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Add CHECK constraints to ensure only valid values
    CONSTRAINT agent_audit_results_releasing_detection_check 
        CHECK (releasing_detection IS NULL OR releasing_detection IN ('Yes', 'No', 'N/A')),
    CONSTRAINT agent_audit_results_late_hello_detection_check 
        CHECK (late_hello_detection IS NULL OR late_hello_detection IN ('Yes', 'No', 'N/A')),
    CONSTRAINT agent_audit_results_rebuttal_detection_check 
        CHECK (rebuttal_detection IS NULL OR rebuttal_detection IN ('Yes', 'No', 'N/A'))
);

-- Create lite audit results table
CREATE TABLE IF NOT EXISTS lite_audit_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255),
    file_name VARCHAR(255),
    file_path TEXT,
    detection_results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create campaign audit results table
CREATE TABLE IF NOT EXISTS campaign_audit_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_name VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE,
    record_count INTEGER DEFAULT 0,
    releasing_count INTEGER DEFAULT 0,
    late_hello_count INTEGER DEFAULT 0,
    rebuttal_count INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PHRASE MANAGEMENT TABLES
-- ============================================================================

-- Rebuttal phrases table (used by KeywordRepository for detection)
CREATE TABLE IF NOT EXISTS rebuttal_phrases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    phrase TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, phrase)
);

-- Pending phrases table (phrases awaiting review/approval)
CREATE TABLE IF NOT EXISTS pending_phrases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    detection_count INTEGER DEFAULT 1,
    first_detected TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_detected TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    sample_contexts TEXT,
    similar_to TEXT,
    quality_score DECIMAL(5,4),
    canonical_form TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phrase, category)
);

-- Repository phrases table (approved phrases with usage tracking)
CREATE TABLE IF NOT EXISTS repository_phrases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    added_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    successful_detections INTEGER DEFAULT 0,
    effectiveness_score DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phrase, category)
);

-- Phrase learning settings table
CREATE TABLE IF NOT EXISTS phrase_learning_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Phrase blacklist table
CREATE TABLE IF NOT EXISTS phrase_blacklist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    rejected_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    UNIQUE(phrase, category)
);

-- Category performance cache table
CREATE TABLE IF NOT EXISTS category_performance (
    category VARCHAR(100) PRIMARY KEY,
    approval_rate DECIMAL(5,4),
    avg_quality_score DECIMAL(5,4),
    total_phrases INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_sessions_username ON user_sessions(username);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_username ON audit_logs(username);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_call_recordings_uploaded_by ON call_recordings(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_call_recordings_call_date ON call_recordings(call_date);
CREATE INDEX IF NOT EXISTS idx_call_recordings_analysis_status ON call_recordings(analysis_status);
CREATE INDEX IF NOT EXISTS idx_analysis_results_recording_id ON analysis_results(recording_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_analysis_type ON analysis_results(analysis_type);
CREATE INDEX IF NOT EXISTS idx_quota_usage_username_date ON quota_usage(username, date);
CREATE INDEX IF NOT EXISTS idx_agent_audit_results_username ON agent_audit_results(username);
CREATE INDEX IF NOT EXISTS idx_agent_audit_results_created_at ON agent_audit_results(created_at);
CREATE INDEX IF NOT EXISTS idx_lite_audit_results_username ON lite_audit_results(username);
CREATE INDEX IF NOT EXISTS idx_lite_audit_results_created_at ON lite_audit_results(created_at);
CREATE INDEX IF NOT EXISTS idx_campaign_audit_results_username ON campaign_audit_results(username);
CREATE INDEX IF NOT EXISTS idx_campaign_audit_results_campaign ON campaign_audit_results(campaign_name);
CREATE INDEX IF NOT EXISTS idx_campaign_audit_results_created_at ON campaign_audit_results(created_at);

-- Indexes for phrase tables
CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_category ON rebuttal_phrases(category);
CREATE INDEX IF NOT EXISTS idx_rebuttal_phrases_source ON rebuttal_phrases(source);
CREATE INDEX IF NOT EXISTS idx_pending_phrases_status ON pending_phrases(status);
CREATE INDEX IF NOT EXISTS idx_pending_phrases_category ON pending_phrases(category);
CREATE INDEX IF NOT EXISTS idx_pending_phrases_quality_score ON pending_phrases(quality_score);
CREATE INDEX IF NOT EXISTS idx_repository_phrases_category ON repository_phrases(category);
CREATE INDEX IF NOT EXISTS idx_repository_phrases_source ON repository_phrases(source);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_call_recordings_updated_at ON call_recordings;
CREATE TRIGGER update_call_recordings_updated_at BEFORE UPDATE ON call_recordings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_quota_usage_updated_at ON quota_usage;
CREATE TRIGGER update_quota_usage_updated_at BEFORE UPDATE ON quota_usage FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_rebuttal_phrases_updated_at ON rebuttal_phrases;
CREATE TRIGGER update_rebuttal_phrases_updated_at BEFORE UPDATE ON rebuttal_phrases FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin user (password should be changed after deployment)
INSERT INTO users (username, app_pass_hash, role, daily_limit) 
VALUES ('Mohamed Abdo', '$2b$12$placeholder_hash_change_after_deployment', 'Owner', 999999)
ON CONFLICT (username) DO NOTHING;

-- Create function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to get user quota usage
CREATE OR REPLACE FUNCTION get_user_quota_usage(p_username VARCHAR, p_date DATE DEFAULT CURRENT_DATE)
RETURNS TABLE(downloads_count INTEGER, analysis_count INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(qu.downloads_count, 0) as downloads_count,
        COALESCE(qu.analysis_count, 0) as analysis_count
    FROM quota_usage qu
    WHERE qu.username = p_username AND qu.date = p_date
    UNION ALL
    SELECT 0, 0
    WHERE NOT EXISTS (
        SELECT 1 FROM quota_usage qu 
        WHERE qu.username = p_username AND qu.date = p_date
    )
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vos_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vos_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO vos_user;
