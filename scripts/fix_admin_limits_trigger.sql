-- Fix admin_limits trigger error
-- The table has a trigger that tries to update 'updated_at' but the column doesn't exist
-- This script adds the missing column

-- Add updated_at column to admin_limits table
ALTER TABLE admin_limits 
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Update existing rows to set updated_at = last_modified (if last_modified exists)
UPDATE admin_limits 
    SET updated_at = last_modified 
    WHERE updated_at IS NULL AND last_modified IS NOT NULL;

-- Set default for any remaining NULL values
UPDATE admin_limits 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE updated_at IS NULL;

-- Verify the column was added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'admin_limits' 
ORDER BY ordinal_position;

