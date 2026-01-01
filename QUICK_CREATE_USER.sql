-- Quick script to create vos_tool user
-- Run this in pgAdmin 4 Query Tool (make sure you're connected as 'postgres' superuser)

-- Create user
CREATE USER vos_tool WITH PASSWORD '20101964mm';

-- Grant database access
GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_tool;

-- Note: After running this, you may need to:
-- 1. Right-click on 'vos_tool' database → Query Tool
-- 2. Run the schema privileges (see CREATE_USER_VOS_TOOL.sql for full script)

