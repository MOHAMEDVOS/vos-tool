-- Fix CHECK constraints on agent_audit_results table
-- The columns are VARCHAR (character varying), not BOOLEAN
-- This script updates the constraints to accept text values 'Yes', 'No', 'N/A', or NULL

-- Drop existing incorrect constraints
ALTER TABLE agent_audit_results 
    DROP CONSTRAINT IF EXISTS agent_audit_results_releasing_detection_check;

ALTER TABLE agent_audit_results 
    DROP CONSTRAINT IF EXISTS agent_audit_results_late_hello_detection_check;

ALTER TABLE agent_audit_results 
    DROP CONSTRAINT IF EXISTS agent_audit_results_rebuttal_detection_check;

-- Add correct constraints that accept text values 'Yes', 'No', 'N/A', or NULL
ALTER TABLE agent_audit_results 
    ADD CONSTRAINT agent_audit_results_releasing_detection_check 
    CHECK (releasing_detection IS NULL OR releasing_detection IN ('Yes', 'No', 'N/A'));

ALTER TABLE agent_audit_results 
    ADD CONSTRAINT agent_audit_results_late_hello_detection_check 
    CHECK (late_hello_detection IS NULL OR late_hello_detection IN ('Yes', 'No', 'N/A'));

ALTER TABLE agent_audit_results 
    ADD CONSTRAINT agent_audit_results_rebuttal_detection_check 
    CHECK (rebuttal_detection IS NULL OR rebuttal_detection IN ('Yes', 'No', 'N/A'));

-- Verify constraints
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conrelid = 'agent_audit_results'::regclass 
    AND contype = 'c'
    AND conname LIKE '%detection%'
ORDER BY conname;

