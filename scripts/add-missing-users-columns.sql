-- Add missing columns to users table for AssemblyAI API keys and user management
-- Run this in Supabase SQL Editor if you already initialized the schema

-- Add assemblyai_api_key_encrypted column (stores encrypted AssemblyAI API keys per user)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS assemblyai_api_key_encrypted TEXT;

-- Add app_pass_salt column (required for secure password hashing)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS app_pass_salt VARCHAR(255);

-- Add created_by column (tracks which admin/owner created each user)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);

-- Create index on created_by for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);

-- Verify columns were added
SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'users' 
    AND column_name IN ('assemblyai_api_key_encrypted', 'app_pass_salt', 'created_by')
ORDER BY column_name;

