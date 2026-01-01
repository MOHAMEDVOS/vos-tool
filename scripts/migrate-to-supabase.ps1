# PowerShell Script: Migrate Local Database to Supabase
# Usage: .\scripts\migrate-to-supabase.ps1 -SupabaseHost "db.xxxxx.supabase.co" -SupabaseUser "postgres" -SupabasePassword "your_password" -LocalDbName "vos_tool" -LocalUser "vos_user"

param(
    [Parameter(Mandatory=$true)]
    [string]$SupabaseHost,
    
    [Parameter(Mandatory=$true)]
    [string]$SupabaseUser,
    
    [Parameter(Mandatory=$true)]
    [string]$SupabasePassword,
    
    [Parameter(Mandatory=$false)]
    [string]$LocalDbName = "vos_tool",
    
    [Parameter(Mandatory=$false)]
    [string]$LocalUser = "vos_user",
    
    [Parameter(Mandatory=$false)]
    [string]$SupabaseDb = "postgres",
    
    [Parameter(Mandatory=$false)]
    [int]$SupabasePort = 5432
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "VOS TOOL - Supabase Migration Script" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if pg_dump and pg_restore are available
$pgDumpPath = Get-Command pg_dump -ErrorAction SilentlyContinue
$pgRestorePath = Get-Command pg_restore -ErrorAction SilentlyContinue

if (-not $pgDumpPath) {
    Write-Host "ERROR: pg_dump not found. Please install PostgreSQL client tools." -ForegroundColor Red
    Write-Host "Windows: Install PostgreSQL from https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    exit 1
}

if (-not $pgRestorePath) {
    Write-Host "ERROR: pg_restore not found. Please install PostgreSQL client tools." -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Creating backup of local database..." -ForegroundColor Cyan
$backupFile = "vos_tool_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"

try {
    $env:PGPASSWORD = Read-Host "Enter local database password for user '$LocalUser'" -AsSecureString | ConvertFrom-SecureString -AsPlainText
    pg_dump -h localhost -U $LocalUser -d $LocalDbName -F c -f $backupFile
    
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "✓ Backup created: $backupFile" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to create backup: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2: Testing Supabase connection..." -ForegroundColor Cyan

$supabaseConnectionString = "postgresql://${SupabaseUser}:${SupabasePassword}@${SupabaseHost}:${SupabasePort}/${SupabaseDb}"

try {
    $testQuery = "SELECT version();"
    $env:PGPASSWORD = $SupabasePassword
    psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -c $testQuery | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        throw "Connection test failed"
    }
    
    Write-Host "✓ Supabase connection successful" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to connect to Supabase: $_" -ForegroundColor Red
    Write-Host "Please verify:" -ForegroundColor Yellow
    Write-Host "  - Supabase host is correct" -ForegroundColor Yellow
    Write-Host "  - Username and password are correct" -ForegroundColor Yellow
    Write-Host "  - Database is accessible from your IP" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Step 3: Restoring backup to Supabase..." -ForegroundColor Cyan
Write-Host "WARNING: This will overwrite existing data in Supabase!" -ForegroundColor Yellow
$confirm = Read-Host "Continue? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Migration cancelled." -ForegroundColor Yellow
    exit 0
}

try {
    $env:PGPASSWORD = $SupabasePassword
    pg_restore -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -c $backupFile
    
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "✓ Data restored to Supabase successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to restore to Supabase: $_" -ForegroundColor Red
    Write-Host "You may need to run the schema initialization script first:" -ForegroundColor Yellow
    Write-Host "  psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -f cloud-migration/init.sql" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Step 4: Verifying migration..." -ForegroundColor Cyan

try {
    $env:PGPASSWORD = $SupabasePassword
    $tableCount = psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
    $userCount = psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -t -c "SELECT COUNT(*) FROM users;"
    
    Write-Host "✓ Migration verification:" -ForegroundColor Green
    Write-Host "  - Tables found: $($tableCount.Trim())" -ForegroundColor White
    Write-Host "  - Users found: $($userCount.Trim())" -ForegroundColor White
} catch {
    Write-Host "WARNING: Could not verify migration: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Migration Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update Railway environment variables with Supabase connection details" -ForegroundColor White
Write-Host "2. Verify application connects to Supabase database" -ForegroundColor White
Write-Host "3. Test application functionality" -ForegroundColor White
Write-Host ""
Write-Host "Backup file saved: $backupFile" -ForegroundColor Yellow
Write-Host "You can delete it after verifying the migration." -ForegroundColor Yellow

