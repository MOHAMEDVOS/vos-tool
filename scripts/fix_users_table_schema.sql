-- Fix users table schema for user creation
-- This script adds missing columns required by the add_user method
-- Run this in pgAdmin 4 Query Tool on the vos_tool database

-- ============================================================================
-- 1. ADD MISSING COLUMNS
-- ============================================================================

-- Add assemblyai_api_key_encrypted column (stores encrypted AssemblyAI API keys per user)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS assemblyai_api_key_encrypted TEXT;

-- Add app_pass_salt column (required for secure password hashing)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS app_pass_salt VARCHAR(255);

-- Add created_by column (tracks which admin/owner created each user)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);

-- ============================================================================
-- 2. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index on created_by for faster lookups of users created by specific admins
CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);

-- ============================================================================
-- 3. VERIFY COLUMNS EXIST
-- ============================================================================

-- This query will show all columns in the users table
-- Verify that all required columns are present:
-- - username (VARCHAR)
-- - app_pass_hash (VARCHAR)
-- - app_pass_salt (VARCHAR) ← Should be added
-- - readymode_user (VARCHAR)
-- - readymode_pass_encrypted (TEXT)
-- - assemblyai_api_key_encrypted (TEXT) ← Should be added
-- - daily_limit (INTEGER)
-- - role (VARCHAR)
-- - created_by (VARCHAR) ← Should be added
-- - created_at (TIMESTAMP)
-- - updated_at (TIMESTAMP)

SELECT 
    column_name, 
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;

-- ============================================================================
-- 4. VERIFY INDEXES
-- ============================================================================

-- Verify that the created_by index exists
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'users' 
    AND indexname LIKE 'idx_users_created_by';

