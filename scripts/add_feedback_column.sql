-- Migration: Add feedback column to agent_audit_results
-- Run this on Railway database to add the feedback column

ALTER TABLE agent_audit_results 
ADD COLUMN IF NOT EXISTS feedback TEXT DEFAULT NULL;

-- Verify the column was added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'agent_audit_results' 
AND column_name = 'feedback';
