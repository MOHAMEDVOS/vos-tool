-- Verification Query: Check if all tables were created successfully
-- Run this in Supabase SQL Editor after schema initialization

-- Count total tables
SELECT COUNT(*) as total_tables 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- List all tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Check key tables exist
SELECT 
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN '✓' ELSE '✗' END as users_table,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_audit_results') THEN '✓' ELSE '✗' END as agent_audit_table,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rebuttal_phrases') THEN '✓' ELSE '✗' END as rebuttal_phrases_table,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pending_phrases') THEN '✓' ELSE '✗' END as pending_phrases_table,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_sessions') THEN '✓' ELSE '✗' END as sessions_table;

-- Check extensions
SELECT extname, extversion 
FROM pg_extension 
WHERE extname IN ('uuid-ossp', 'pg_trgm');

