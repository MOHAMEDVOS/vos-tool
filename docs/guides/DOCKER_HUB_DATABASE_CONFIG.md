# Docker Hub Database Configuration Guide

## Overview

While Docker Hub doesn't store environment variables directly, we've created a **pre-configured setup** that makes database configuration easy for users pulling images from Docker Hub.

## How It Works

### 1. Pre-Configured Defaults

The `docker-compose.example.yml` and `.env.example` files include **sensible defaults** for database configuration:

```yaml
# In docker-compose.example.yml
POSTGRES_HOST=${POSTGRES_HOST:-postgres}              # Default for docker-compose PostgreSQL service
POSTGRES_PORT=${POSTGRES_PORT:-5432}                  # Default PostgreSQL port
POSTGRES_DB=${POSTGRES_DB:-vos_tool}                  # Default database name
POSTGRES_USER=${POSTGRES_USER:-vos_user}              # Default user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}                # From .env file
```

### 2. Simple Configuration Process

Users only need to:

1. **Copy `.env.example` to `.env`**
2. **Update 2-3 database settings** in `.env`:
   - `POSTGRES_HOST` (if using remote database)
   - `POSTGRES_PASSWORD` (their database password)
   - Optionally: `POSTGRES_DB`, `POSTGRES_USER` if different

3. **Run the application** - Everything else works with defaults!

## Configuration Files

### `.env.example`
- **Purpose**: Template with all database defaults pre-configured
- **Contains**: Your current database settings as defaults
- **Usage**: Users copy this to `.env` and update only what's needed

### `docker-compose.example.yml`
- **Purpose**: Docker Compose file using Docker Hub images
- **Contains**: All environment variables with defaults
- **Usage**: Users copy this to `docker-compose.yml` and it works!

### `QUICK_START_DOCKER_HUB.md`
- **Purpose**: Step-by-step guide for new users
- **Contains**: Simple 3-step setup instructions

### `setup-database-config.ps1`
- **Purpose**: Automated PowerShell script to configure database
- **Usage**: `.\setup-database-config.ps1 -PostgresPassword "your_password"`

## Current Database Defaults

Based on your current setup, the defaults are:

```env
POSTGRES_HOST=postgres               # For docker-compose PostgreSQL service
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=<your_password>
```

## For Users on Different PCs

### Scenario 1: Local PostgreSQL (Same Machine)
```env
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=their_password
```

### Scenario 2: Remote PostgreSQL Server
```env
POSTGRES_HOST=192.168.1.100          # Server IP
POSTGRES_PORT=5432
POSTGRES_PASSWORD=their_password
```

### Scenario 3: Cloud Database (AWS RDS, etc.)
```env
POSTGRES_HOST=your-db.region.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_PASSWORD=their_password
```

## Benefits

✅ **No Docker Hub variables needed** - Configuration is in `.env` file  
✅ **Easy setup** - Users only update 2-3 settings  
✅ **Pre-configured defaults** - Works out of the box for most setups  
✅ **Flexible** - Supports local, remote, and cloud databases  
✅ **Secure** - Each user has their own `.env` file with their credentials  

## Quick Setup Command

For users who want the fastest setup:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
# Then edit .env and update POSTGRES_PASSWORD
```

Or use the automated script:
```powershell
.\setup-database-config.ps1 -PostgresPassword "their_password"
```

## Summary

**You don't need to set variables in Docker Hub!** Instead:

1. ✅ **Pre-configured defaults** in `.env.example` and `docker-compose.example.yml`
2. ✅ **Users copy files** and update only their database password
3. ✅ **Works immediately** - No complex configuration needed

This approach is actually **better** than Docker Hub variables because:
- Each user can have different database settings
- More secure (credentials not in Docker Hub)
- More flexible (supports any database setup)

