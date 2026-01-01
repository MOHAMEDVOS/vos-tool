#!/bin/bash
# Bash Script: Migrate Local Database to Supabase
# Usage: ./scripts/migrate-to-supabase.sh -h db.xxxxx.supabase.co -u postgres -p your_password

set -e

# Default values
LOCAL_DB_NAME="vos_tool"
LOCAL_USER="vos_user"
SUPABASE_DB="postgres"
SUPABASE_PORT=5432

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            SUPABASE_HOST="$2"
            shift 2
            ;;
        -u|--user)
            SUPABASE_USER="$2"
            shift 2
            ;;
        -p|--password)
            SUPABASE_PASSWORD="$2"
            shift 2
            ;;
        -d|--database)
            SUPABASE_DB="$2"
            shift 2
            ;;
        --local-db)
            LOCAL_DB_NAME="$2"
            shift 2
            ;;
        --local-user)
            LOCAL_USER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 -h HOST -u USER -p PASSWORD [-d DATABASE] [--local-db DB] [--local-user USER]"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$SUPABASE_HOST" || -z "$SUPABASE_USER" || -z "$SUPABASE_PASSWORD" ]]; then
    echo "ERROR: Missing required parameters"
    echo "Usage: $0 -h HOST -u USER -p PASSWORD"
    exit 1
fi

echo "========================================"
echo "VOS TOOL - Supabase Migration Script"
echo "========================================"
echo ""

# Check if pg_dump and pg_restore are available
if ! command -v pg_dump &> /dev/null; then
    echo "ERROR: pg_dump not found. Please install PostgreSQL client tools."
    echo "Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "macOS: brew install postgresql"
    exit 1
fi

if ! command -v pg_restore &> /dev/null; then
    echo "ERROR: pg_restore not found. Please install PostgreSQL client tools."
    exit 1
fi

# Step 1: Create backup
echo "Step 1: Creating backup of local database..."
BACKUP_FILE="vos_tool_backup_$(date +%Y%m%d_%H%M%S).dump"

read -sp "Enter local database password for user '$LOCAL_USER': " LOCAL_PASSWORD
echo ""

export PGPASSWORD="$LOCAL_PASSWORD"
pg_dump -h localhost -U "$LOCAL_USER" -d "$LOCAL_DB_NAME" -F c -f "$BACKUP_FILE"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create backup"
    exit 1
fi

echo "✓ Backup created: $BACKUP_FILE"
echo ""

# Step 2: Test Supabase connection
echo "Step 2: Testing Supabase connection..."

export PGPASSWORD="$SUPABASE_PASSWORD"
psql -h "$SUPABASE_HOST" -U "$SUPABASE_USER" -d "$SUPABASE_DB" -p "$SUPABASE_PORT" -c "SELECT version();" > /dev/null

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to connect to Supabase"
    echo "Please verify:"
    echo "  - Supabase host is correct"
    echo "  - Username and password are correct"
    echo "  - Database is accessible from your IP"
    exit 1
fi

echo "✓ Supabase connection successful"
echo ""

# Step 3: Restore to Supabase
echo "Step 3: Restoring backup to Supabase..."
echo "WARNING: This will overwrite existing data in Supabase!"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Migration cancelled."
    exit 0
fi

export PGPASSWORD="$SUPABASE_PASSWORD"
pg_restore -h "$SUPABASE_HOST" -U "$SUPABASE_USER" -d "$SUPABASE_DB" -p "$SUPABASE_PORT" -c "$BACKUP_FILE"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to restore to Supabase"
    echo "You may need to run the schema initialization script first:"
    echo "  psql -h $SUPABASE_HOST -U $SUPABASE_USER -d $SUPABASE_DB -f cloud-migration/init.sql"
    exit 1
fi

echo "✓ Data restored to Supabase successfully"
echo ""

# Step 4: Verify migration
echo "Step 4: Verifying migration..."

TABLE_COUNT=$(psql -h "$SUPABASE_HOST" -U "$SUPABASE_USER" -d "$SUPABASE_DB" -p "$SUPABASE_PORT" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
USER_COUNT=$(psql -h "$SUPABASE_HOST" -U "$SUPABASE_USER" -d "$SUPABASE_DB" -p "$SUPABASE_PORT" -t -c "SELECT COUNT(*) FROM users;" | tr -d ' ')

echo "✓ Migration verification:"
echo "  - Tables found: $TABLE_COUNT"
echo "  - Users found: $USER_COUNT"
echo ""

echo "========================================"
echo "Migration Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update Railway environment variables with Supabase connection details"
echo "2. Verify application connects to Supabase database"
echo "3. Test application functionality"
echo ""
echo "Backup file saved: $BACKUP_FILE"
echo "You can delete it after verifying the migration."

