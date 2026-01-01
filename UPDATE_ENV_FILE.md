# Update .env File - Change Username

## Issue Found

Your PostgreSQL has user `vos_user` but `.env` is configured for `vos_tool` (which doesn't exist).

## Solution: Update .env File

### Step 1: Open .env File

Navigate to: `C:\Users\vos\Desktop\save v.1\.env`

### Step 2: Find This Line

```
POSTGRES_USER=vos_tool
```

### Step 3: Change It To

```
POSTGRES_USER=vos_user
```

### Step 4: Save the File

### Step 5: Restart Backend

After saving, run:
```bash
docker-compose restart backend
```

## Alternative: Check vos_user Password

If `vos_user` has a different password, you may also need to update:
```
POSTGRES_PASSWORD=20101964mm
```

To find the correct password:
1. In pgAdmin 4, expand "Login/Group Roles (18)"
2. Right-click on `vos_user` → Properties
3. Check the password (or reset it to `20101964mm`)

## After Updating

1. Restart backend: `docker-compose restart backend`
2. Check logs: `docker-compose logs backend | Select-String -Pattern "PostgreSQL|successfully"`
3. Test login at http://localhost:8501

