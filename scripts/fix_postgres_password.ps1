# PowerShell script to fix PostgreSQL password authentication
# Usage: .\scripts\fix_postgres_password.ps1 -Password "your_password"

param(
    [Parameter(Mandatory=$false)]
    [string]$Password,
    
    [Parameter(Mandatory=$false)]
    [string]$PostgresUser = "postgres",
    
    [Parameter(Mandatory=$false)]
    [string]$TargetUser = "vos_user",
    
    [Parameter(Mandatory=$false)]
    [string]$Database = "vos_tool"
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Password Setup for VOS Tool" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check if password was provided
if (-not $Password) {
    Write-Host "`nPlease provide the password for the PostgreSQL user '$TargetUser'" -ForegroundColor Yellow
    Write-Host "Usage: .\scripts\fix_postgres_password.ps1 -Password 'your_password'" -ForegroundColor Yellow
    Write-Host "`nOr you can set it interactively:" -ForegroundColor Yellow
    $Password = Read-Host "Enter password for '$TargetUser'" -AsSecureString
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    )
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    Write-Host "Error: Password cannot be empty!" -ForegroundColor Red
    exit 1
}

Write-Host "`nConfiguration:" -ForegroundColor Green
Write-Host "  Target User: $TargetUser" -ForegroundColor White
Write-Host "  Database: $Database" -ForegroundColor White
Write-Host "  Postgres Admin: $PostgresUser" -ForegroundColor White

# Check if psql is available
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    # Try common PostgreSQL installation paths
    $commonPaths = @(
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files\PostgreSQL\13\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\14\bin\psql.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            $psqlPath = $path
            break
        }
    }
}

if (-not $psqlPath) {
    Write-Host "`nError: psql not found. Please install PostgreSQL or add it to PATH." -ForegroundColor Red
    Write-Host "Alternatively, you can use pgAdmin 4 to reset the password manually." -ForegroundColor Yellow
    Write-Host "`nManual Steps:" -ForegroundColor Cyan
    Write-Host "1. Open pgAdmin 4" -ForegroundColor White
    Write-Host "2. Connect to your PostgreSQL server" -ForegroundColor White
    Write-Host "3. Navigate to: Servers > [Your Server] > Login/Group Roles" -ForegroundColor White
    Write-Host "4. Right-click on '$TargetUser' > Properties" -ForegroundColor White
    Write-Host "5. Go to 'Definition' tab and set password: $Password" -ForegroundColor White
    Write-Host "6. Click Save" -ForegroundColor White
    exit 1
}

Write-Host "`nFound psql at: $psqlPath" -ForegroundColor Green

# Prompt for postgres superuser password
Write-Host "`nYou'll need to enter the '$PostgresUser' superuser password to reset '$TargetUser' password" -ForegroundColor Yellow
$postgresPassword = Read-Host "Enter password for '$PostgresUser' user" -AsSecureString
$postgresPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($postgresPassword)
)

# Create SQL commands
$sqlCommands = @"
-- Check if user exists, create if not, or reset password
DO `$`$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '$TargetUser') THEN
        ALTER USER $TargetUser WITH PASSWORD '$Password';
        RAISE NOTICE 'Password reset for user $TargetUser';
    ELSE
        CREATE USER $TargetUser WITH PASSWORD '$Password';
        RAISE NOTICE 'User $TargetUser created';
    END IF;
END
`$`$;

-- Grant database privileges
GRANT ALL PRIVILEGES ON DATABASE $Database TO $TargetUser;

-- Connect to target database and grant schema privileges
\c $Database

GRANT ALL ON SCHEMA public TO $TargetUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $TargetUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $TargetUser;
"@

# Write SQL to temp file
$tempSqlFile = [System.IO.Path]::GetTempFileName() + ".sql"
$sqlCommands | Out-File -FilePath $tempSqlFile -Encoding UTF8

Write-Host "`nExecuting SQL commands..." -ForegroundColor Green

# Set password as environment variable for psql
$env:PGPASSWORD = $postgresPasswordPlain

try {
    # Execute SQL
    $result = & $psqlPath -U $PostgresUser -d postgres -f $tempSqlFile 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nSuccess! Password has been set for '$TargetUser'" -ForegroundColor Green
        
        # Update .env file
        $envFile = Join-Path $PSScriptRoot "..\.env"
        if (Test-Path $envFile) {
            Write-Host "`nUpdating .env file..." -ForegroundColor Green
            $content = Get-Content $envFile -Raw
            $content = $content -replace "POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$Password"
            $content | Set-Content $envFile -NoNewline
            Write-Host "Updated POSTGRES_PASSWORD in .env file" -ForegroundColor Green
        } else {
            Write-Host "Warning: .env file not found at $envFile" -ForegroundColor Yellow
        }
        
        Write-Host "`nNext steps:" -ForegroundColor Cyan
        Write-Host "1. Restart your backend server" -ForegroundColor White
        Write-Host "2. Check logs to verify connection" -ForegroundColor White
        Write-Host "3. Test the application" -ForegroundColor White
    } else {
        Write-Host "`nError executing SQL commands:" -ForegroundColor Red
        Write-Host $result -ForegroundColor Red
        Write-Host "`nPlease check:" -ForegroundColor Yellow
        Write-Host "- PostgreSQL is running" -ForegroundColor White
        Write-Host "- The '$PostgresUser' password is correct" -ForegroundColor White
        Write-Host "- You have permissions to create/modify users" -ForegroundColor White
    }
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
} finally {
    # Clean up
    Remove-Item $tempSqlFile -ErrorAction SilentlyContinue
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
