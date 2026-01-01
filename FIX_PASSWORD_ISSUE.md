# Fix: Password Authentication Failed

## Problem Identified

**Root Cause:** The password in `.env` file (`20101964mm`) does not match the actual password for PostgreSQL user `vos_tool`.

**Evidence:**
- ✅ Network connectivity works (host.docker.internal resolves to 192.168.65.254)
- ✅ PostgreSQL is reachable on port 5432
- ❌ Password authentication fails: "FATAL: password authentication failed for user 'vos_tool'"

## Solution Options

### Option 1: Update Password in PostgreSQL (Recommended)

If you know the correct password:

1. **Open pgAdmin 4**
2. **Connect to your PostgreSQL server**
3. **Navigate to**: Servers → [Your Server] → Login/Group Roles
4. **Right-click on `vos_tool`** → **Properties**
5. **Go to "Definition" tab**
6. **Enter the correct password** in the "Password" field
7. **Click "Save"**

Then update `.env` file with the correct password.

### Option 2: Reset Password in PostgreSQL

If you want to set a new password:

1. **Open pgAdmin 4**
2. **Connect to your PostgreSQL server**
3. **Open Query Tool** (Tools → Query Tool)
4. **Run this SQL command**:
   ```sql
   ALTER USER vos_tool WITH PASSWORD '20101964mm';
   ```
5. **Click Execute** (F5)
6. **Verify** the password is updated

### Option 3: Check Current Password

To verify what password is currently set:

1. **Open pgAdmin 4**
2. **Connect to your PostgreSQL server**
3. **Right-click on `vos_tool` user** → **Properties**
4. **Check if password is set** (you can't see the actual password, but you can reset it)

## After Fixing Password

1. **Update `.env` file** with the correct password
2. **Restart Docker containers**:
   ```bash
   docker-compose restart backend
   ```
3. **Check logs** to verify connection:
   ```bash
   docker-compose logs backend | Select-String -Pattern "PostgreSQL|connection"
   ```
4. **Test login** at http://localhost:8501

## Quick Fix Script

If you want to test with a different password, update `.env`:

```bash
# Edit .env file and update this line:
POSTGRES_PASSWORD=your_actual_password_here
```

Then restart:
```bash
docker-compose restart backend frontend
```

