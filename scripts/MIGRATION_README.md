# Complete Data Migration Guide

This guide explains how to migrate all application data from local JSON files to PostgreSQL.

## Prerequisites

1. **PostgreSQL Database**: Ensure PostgreSQL is running and accessible
2. **Python Dependencies**: Install required packages
   ```bash
   pip install psycopg2-binary pandas python-dateutil
   ```
3. **Database Schema**: Run the schema creation script first
   ```bash
   psql -h localhost -U vos_user -d vos_tool -f cloud-migration/migration_schema.sql
   ```

## Migration Steps

### Step 1: Create Backup

**CRITICAL**: Always backup your data before migration!

```bash
python scripts/backup_data.py
```

This creates a timestamped backup of your `dashboard_data/` directory.

### Step 2: Verify Database Connection

Set environment variables:
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=vos_tool
export POSTGRES_USER=vos_user
export POSTGRES_PASSWORD=your_password
```

Or create a `.env` file in the project root.

### Step 3: Run Schema Migration

Ensure all required tables exist:
```bash
psql -h localhost -U vos_user -d vos_tool -f cloud-migration/migration_schema.sql
```

### Step 4: Test Migration (Dry Run)

Run migration in dry-run mode to verify without committing:
```bash
DRY_RUN=true python scripts/migrate_all_data_to_postgres_complete.py
```

Review the output and `migration.log` file for any issues.

### Step 5: Execute Migration

Run the actual migration:
```bash
python scripts/migrate_all_data_to_postgres_complete.py
```

The script will:
- Migrate users (with ReadyMode credentials) - **CRITICAL**
- Migrate all audit results (agent, campaign, lite)
- Migrate quota management data
- Migrate subscriptions
- Migrate settings and configurations
- Generate detailed migration report

### Step 6: Verify Migration

Check the migration log and verify data:
```bash
# Check migration log
cat migration.log

# Verify user count
psql -h localhost -U vos_user -d vos_tool -c "SELECT COUNT(*) FROM users;"

# Verify audit results
psql -h localhost -U vos_user -d vos_tool -c "SELECT COUNT(*) FROM agent_audit_results;"
```

## Migration Order

The script migrates data in dependency order:
1. **Users** (must be first - all other data references users)
2. Quota system config
3. App settings
4. Subscriptions
5. Daily counters
6. Admin audit logs
7. Learned rebuttals
8. Phrases
9. Agent audits
10. Lite audits
11. Campaign audits
12. Dashboard sharing

## Troubleshooting

### Connection Errors
- Verify PostgreSQL is running: `pg_isready -h localhost`
- Check credentials in environment variables
- Verify database exists: `psql -l`

### Missing Tables
- Run `cloud-migration/migration_schema.sql` to create all tables
- Check for errors in schema script execution

### Data Validation Errors
- Review `migration.log` for specific errors
- Check that all users exist before migrating audit data
- Verify JSON files are valid (not corrupted)

### Rollback

If migration fails:
1. The script uses transactions - failed migrations are automatically rolled back
2. Restore from backup:
   ```bash
   # Stop application
   # Remove current dashboard_data
   rm -rf dashboard_data
   # Restore backup
   cp -r dashboard_data_backup_TIMESTAMP dashboard_data
   ```

## Post-Migration

After successful migration:
1. **Test Application**: Verify all features work with PostgreSQL
2. **Monitor**: Watch for any errors in application logs
3. **Archive JSON**: Keep JSON files for 30 days as backup
4. **Update Configuration**: Ensure `DB_TYPE=postgresql` in application config

## Migration Statistics

The script provides detailed statistics:
- Records imported per data type
- Records skipped (duplicates)
- Errors encountered
- Total migration time

All statistics are logged to `migration.log` and displayed in console.

## Support

For issues:
1. Check `migration.log` for detailed error messages
2. Verify database schema matches expected structure
3. Ensure all JSON files are readable and valid
4. Check user permissions on PostgreSQL database

