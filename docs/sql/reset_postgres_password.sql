-- SQL script to reset PostgreSQL user password
-- Run this in pgAdmin 4 Query Tool

-- Reset password for vos_tool user
ALTER USER vos_tool WITH PASSWORD '20101964mm';

-- Verify user exists and has correct permissions
SELECT usename, usecreatedb, usesuper 
FROM pg_user 
WHERE usename = 'vos_tool';

-- Verify user can access the database
SELECT datname, datacl 
FROM pg_database 
WHERE datname = 'vos_tool';

