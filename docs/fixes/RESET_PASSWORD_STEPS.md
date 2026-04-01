# Step-by-Step: Reset Password in pgAdmin 4

## Quick Steps

### Step 1: Open Login/Group Roles
1. In the **Object Explorer** (left panel), expand **"Login/Group Roles (18)"**
2. Find **`vos_tool`** in the list
3. **Right-click** on `vos_tool`
4. Select **"Properties"**

### Step 2: Reset Password
1. In the Properties window, go to the **"Definition"** tab
2. In the **"Password"** field, enter: `<new_password>`
3. In the **"Password (again)"** field, enter the same: `<new_password>`
4. Click **"Save"** button

### Step 3: Verify (Optional)
1. Right-click on `vos_tool` again → **"Properties"**
2. Go to **"Privileges"** tab
3. Make sure **"Can login?"** is checked 

## Alternative: Using Query Tool

If you prefer SQL:

1. **Right-click** on `vos_tool` database → **"Query Tool"**
2. **Paste** this SQL:
   ```sql
   ALTER USER vos_tool WITH PASSWORD '<new_password>';
   ```
3. Click **"Execute"** button (or press F5)
4. You should see: "Query returned successfully"

## After Resetting Password

1. **Restart backend container**:
   ```bash
   docker-compose restart backend
   ```

2. **Check if connection works**:
   ```bash
   docker-compose logs backend | Select-String -Pattern "PostgreSQL|connection|successfully"
   ```

3. **Test login** at http://localhost:8501

## Troubleshooting

If you get "permission denied":
- Make sure you're connected as a superuser (usually `postgres` user)
- Or use the Query Tool method with a superuser account

