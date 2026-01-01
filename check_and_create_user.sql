-- Check existing users/roles in PostgreSQL
-- Run this in pgAdmin 4 Query Tool

-- Step 1: List all users/roles
SELECT usename, usecreatedb, usesuper, valuntil 
FROM pg_user 
ORDER BY usename;

-- Step 2: Check if vos_tool exists
SELECT EXISTS(
    SELECT 1 FROM pg_user WHERE usename = 'vos_tool'
) AS user_exists;

-- Step 3: If user doesn't exist, create it (uncomment and run):
-- CREATE USER vos_tool WITH PASSWORD '20101964mm';

-- Step 4: Grant privileges to vos_tool database
-- GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_tool;

-- Step 5: Grant schema privileges
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vos_tool;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vos_tool;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vos_tool;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vos_tool;

