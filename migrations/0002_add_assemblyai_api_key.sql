-- Add assemblyai_api_key column to users table
-- This will store each user's personal AssemblyAI API key (encrypted)

ALTER TABLE users 
ADD COLUMN assemblyai_api_key_encrypted TEXT;

-- Create index for faster lookups (optional, since we'll query by username)
-- CREATE INDEX idx_users_assemblyai_api_key ON users(assemblyai_api_key_encrypted) WHERE assemblyai_api_key_encrypted IS NOT NULL;
