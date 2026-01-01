-- Complete script to create vos_tool user and grant all privileges
-- Run this in pgAdmin 4 Query Tool (connected as postgres superuser)

-- Step 1: Create the user with password
CREATE USER vos_tool WITH PASSWORD '20101964mm';

-- Step 2: Grant database privileges
GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_tool;

-- Step 3: Connect to vos_tool database and grant schema privileges
\c vos_tool

-- Step 4: Grant all privileges on existing tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vos_tool;

-- Step 5: Grant all privileges on sequences
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vos_tool;

-- Step 6: Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vos_tool;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vos_tool;

-- Step 7: Grant usage on schema
GRANT USAGE ON SCHEMA public TO vos_tool;

-- Step 8: Verify user was created
SELECT usename, usecreatedb, usesuper 
FROM pg_user 
WHERE usename = 'vos_tool';

