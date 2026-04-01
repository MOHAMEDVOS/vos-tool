# Database Setup Guide for Docker Hub Users

This guide explains how to set up the PostgreSQL database required for VOS Tool when using Docker Hub images.

## 📋 Prerequisites

- PostgreSQL 15 or higher installed
- Access to create databases and users
- Basic knowledge of SQL

## 🗄️ Database Setup Steps

### Step 1: Install PostgreSQL

If PostgreSQL is not already installed:

**Windows:**
- Download from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)
- Run the installer and follow the setup wizard
- Remember the postgres superuser password you set

**macOS:**
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 2: Connect to PostgreSQL

Open a terminal/command prompt and connect to PostgreSQL:

**Windows:**
```bash
# Use psql from PostgreSQL installation directory
# Usually: C:\Program Files\PostgreSQL\15\bin\psql.exe
psql -U postgres
```

**macOS/Linux:**
```bash
# Connect as postgres user
sudo -u postgres psql

# Or if you have a postgres user account
psql -U postgres
```

### Step 3: Create Database and User

Once connected to PostgreSQL, run these SQL commands:

```sql
-- Create the database
CREATE DATABASE vos_tool;

-- Create the user
CREATE USER vos_user WITH PASSWORD 'your_secure_password_here';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_user;

-- Connect to the vos_tool database
\c vos_tool

-- Grant schema privileges (required for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO vos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vos_user;
```

**⚠️ Important:** Replace `'your_secure_password_here'` with a strong password. You'll need this password in your `.env` file.

### Step 4: Initialize Database Schema

You need to run the database initialization script. There are two methods:

#### Method A: Using psql (Recommended)

```bash
# From the project directory
psql -U vos_user -d vos_tool -f cloud-migration/init.sql
```

If prompted for a password, enter the password you set in Step 3.

#### Method B: Using psql Interactive Mode

```sql
-- Connect to vos_tool database
\c vos_tool

-- Run the script
\i cloud-migration/init.sql
```

### Step 5: Verify Installation

Check that tables were created:

```sql
-- Connect to vos_tool database
\c vos_tool

-- List all tables
\dt

-- You should see tables like:
-- - users
-- - user_sessions
-- - agent_audit_results
-- - rebuttal_phrases
-- - pending_phrases
-- - etc.
```

### Step 6: Configure PostgreSQL for Docker Access

#### For Local PostgreSQL

Ensure PostgreSQL is configured to accept connections from your Docker host:

- Check `pg_hba.conf` and add a rule that allows your Docker host/network
- Restart the PostgreSQL service after changes

#### For Remote PostgreSQL

1. **Configure `pg_hba.conf`** to allow connections from Docker network:
   ```
   # Add line for Docker network (adjust IP range as needed)
   host    all    all    172.17.0.0/16    md5
   ```

2. **Configure `postgresql.conf`**:
   ```conf
   listen_addresses = '*'  # Or specific IP addresses
   ```

3. **Restart PostgreSQL**:
   ```bash
   # Linux
   sudo systemctl restart postgresql
   
   # macOS
   brew services restart postgresql@15
   
   # Windows: Restart PostgreSQL service from Services
   ```

4. **Open firewall port** (if applicable):
   ```bash
   # Linux (ufw)
   sudo ufw allow 5432/tcp
   
   # Or use your firewall management tool
   ```

## 🔍 Troubleshooting

### Issue: "password authentication failed"

**Solution:**
1. Verify the password in `.env` matches the password set in Step 3
2. Check `pg_hba.conf` allows password authentication (md5 or scram-sha-256)
3. Ensure user exists: `\du` in psql

### Issue: "database does not exist"

**Solution:**
1. Verify database was created: `\l` in psql
2. Check database name in `.env` matches: `POSTGRES_DB=vos_tool`
3. Create database if missing: `CREATE DATABASE vos_tool;`

### Issue: "permission denied"

**Solution:**
1. Grant privileges: `GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_user;`
2. Grant schema privileges (PostgreSQL 15+):
   ```sql
   \c vos_tool
   GRANT ALL ON SCHEMA public TO vos_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vos_user;
   ```

### Issue: Cannot connect from Docker

**Solution:**
1. **For local PostgreSQL:**
   - Verify PostgreSQL is listening on the configured port
   - Verify `pg_hba.conf` allows connections from your Docker host/network

2. **For remote PostgreSQL:**
   - Verify PostgreSQL is listening: `netstat -an | grep 5432`
   - Check firewall rules
   - Verify `pg_hba.conf` allows connections from Docker network
   - Test connection: `psql -h your_host -U vos_user -d vos_tool`

### Issue: Schema initialization fails

**Solution:**
1. Ensure you're connected to the correct database: `\c vos_tool`
2. Check user has CREATE privileges
3. Verify extensions can be created:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pg_trgm";
   ```
4. Run script in sections if needed

## ✅ Verification Checklist

Before starting the Docker containers, verify:

- [ ] PostgreSQL is installed and running
- [ ] Database `vos_tool` exists
- [ ] User `vos_user` exists with correct password
- [ ] User has all privileges on `vos_tool` database
- [ ] Schema initialization script ran successfully
- [ ] Tables exist (check with `\dt`)
- [ ] `pg_hba.conf` allows connections from Docker
- [ ] Firewall allows port 5432 (if remote)
- [ ] `.env` file has correct database credentials

## 📚 Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostgreSQL Installation Guide](https://www.postgresql.org/download/)
- [Docker Network Configuration](https://docs.docker.com/network/)
- Main setup guide: [README-DOCKER-HUB.md](README-DOCKER-HUB.md)

---

**Last Updated**: 2024 | **Version**: 1.0.0

