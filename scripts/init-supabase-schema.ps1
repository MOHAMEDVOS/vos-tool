# PowerShell Script: Initialize Supabase Database Schema
# Usage: .\scripts\init-supabase-schema.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$SupabaseHost,
    
    [Parameter(Mandatory=$true)]
    [string]$SupabaseUser,
    
    [Parameter(Mandatory=$true)]
    [string]$SupabasePassword,
    
    [Parameter(Mandatory=$false)]
    [string]$SupabaseDb = "postgres",
    
    [Parameter(Mandatory=$false)]
    [int]$SupabasePort = 5432,
    
    [Parameter(Mandatory=$false)]
    [string]$SchemaFile = "cloud-migration/init.sql"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "SUPABASE SCHEMA INITIALIZATION" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if schema file exists
if (-not (Test-Path $SchemaFile)) {
    Write-Host "ERROR: Schema file not found: $SchemaFile" -ForegroundColor Red
    exit 1
}

# Check if psql is available
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    Write-Host "ERROR: psql not found. Please install PostgreSQL client tools." -ForegroundColor Red
    Write-Host "Windows: Install PostgreSQL from https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Step 1: Testing Supabase connection..." -ForegroundColor Cyan

try {
    $env:PGPASSWORD = $SupabasePassword
    $testQuery = "SELECT version();"
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
Write-Host "Step 2: Initializing database schema..." -ForegroundColor Cyan
Write-Host "Schema file: $SchemaFile" -ForegroundColor White

try {
    $env:PGPASSWORD = $SupabasePassword
    Get-Content $SchemaFile | psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort
    
    if ($LASTEXITCODE -ne 0) {
        throw "Schema initialization failed"
    }
    
    Write-Host "✓ Schema initialized successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to initialize schema: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 3: Verifying tables created..." -ForegroundColor Cyan

try {
    $env:PGPASSWORD = $SupabasePassword
    $tableCount = psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | ForEach-Object { $_.Trim() }
    
    Write-Host "✓ Verification complete:" -ForegroundColor Green
    Write-Host "  - Tables created: $tableCount" -ForegroundColor White
    
    # List some key tables
    Write-Host ""
    Write-Host "Key tables:" -ForegroundColor Cyan
    psql -h $SupabaseHost -U $SupabaseUser -d $SupabaseDb -p $SupabasePort -t -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;" | ForEach-Object { 
        $table = $_.Trim()
        if ($table) {
            Write-Host "  - $table" -ForegroundColor White
        }
    }
} catch {
    Write-Host "WARNING: Could not verify tables: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Schema Initialization Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Create Railway project and services" -ForegroundColor White
Write-Host "2. Add environment variables from RAILWAY_ENV_VARIABLES.txt" -ForegroundColor White
Write-Host "3. Deploy and verify connection" -ForegroundColor White
Write-Host ""

