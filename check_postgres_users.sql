-- Check all PostgreSQL users/roles
-- Run this in pgAdmin 4 Query Tool

-- Method 1: List all users with details
SELECT 
    usename AS username,
    usecreatedb AS can_create_db,
    usesuper AS is_superuser,
    valuntil AS password_expires
FROM pg_user 
ORDER BY usename;

-- Method 2: List all roles (includes users and groups)
SELECT 
    rolname AS role_name,
    rolsuper AS is_superuser,
    rolcreatedb AS can_create_db,
    rolcanlogin AS can_login
FROM pg_roles 
WHERE rolcanlogin = true
ORDER BY rolname;

-- Method 3: Check current connected user
SELECT current_user AS current_username, session_user AS session_username;

-- Method 4: Check if vos_tool exists specifically
SELECT 
    CASE 
        WHEN EXISTS(SELECT 1 FROM pg_user WHERE usename = 'vos_tool') 
        THEN 'vos_tool EXISTS' 
        ELSE 'vos_tool DOES NOT EXIST' 
    END AS user_status;

