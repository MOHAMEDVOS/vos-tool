#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to set up or reset PostgreSQL password for vos_user.
This script helps fix "password authentication failed" errors.
"""

import os
import sys
import getpass
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path to import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


def get_postgres_connection(host='localhost', port=5432, user='postgres', database='postgres'):
    """Connect to PostgreSQL as superuser."""
    print(f"\n🔐 Connecting to PostgreSQL as '{user}'...")
    print("   (You'll be prompted for the postgres superuser password)")
    
    password = getpass.getpass(f"Enter password for '{user}': ")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5
        )
        print("✅ Connected to PostgreSQL successfully!")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Failed to connect: {e}")
        print("\n💡 Tips:")
        print("   - Make sure PostgreSQL is running")
        print("   - Check if the postgres user password is correct")
        print("   - Try connecting with: psql -U postgres")
        return None


def check_user_exists(conn, username):
    """Check if a PostgreSQL user exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            (username,)
        )
        return cur.fetchone() is not None


def create_or_reset_user(conn, username, password, database):
    """Create user if it doesn't exist, or reset password if it does."""
    user_exists = check_user_exists(conn, username)
    
    with conn.cursor() as cur:
        if user_exists:
            print(f"📝 User '{username}' exists. Resetting password...")
            cur.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                    sql.Identifier(username)
                ),
                (password,)
            )
            print(f"✅ Password reset for user '{username}'")
        else:
            print(f"➕ Creating user '{username}'...")
            cur.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(username)
                ),
                (password,)
            )
            print(f"✅ User '{username}' created")
        
        # Grant privileges
        print(f"🔑 Granting privileges on database '{database}'...")
        cur.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(database),
                sql.Identifier(username)
            )
        )
        
        # Check if database exists
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (database,)
        )
        db_exists = cur.fetchone() is not None
        
        if db_exists:
            # Grant schema privileges (required for PostgreSQL 15+)
            conn.commit()
            # Connect to the target database to grant schema privileges
            conn.close()
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                user='postgres',
                password=getpass.getpass("Re-enter postgres password: "),
                database=database,
                connect_timeout=5
            )
            with conn.cursor() as schema_cur:
                schema_cur.execute(
                    sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(
                        sql.Identifier(username)
                    )
                )
                schema_cur.execute(
                    sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}").format(
                        sql.Identifier(username)
                    )
                )
            print(f"✅ Schema privileges granted")
        else:
            print(f"⚠️  Database '{database}' doesn't exist yet. Creating it...")
            conn.rollback()
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(database)
                )
            )
            print(f"✅ Database '{database}' created")
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(database),
                    sql.Identifier(username)
                )
            )
        
        conn.commit()
        print(f"✅ All privileges granted successfully!")


def update_env_file(env_path, password):
    """Update POSTGRES_PASSWORD in .env file."""
    env_path = Path(env_path)
    
    if not env_path.exists():
        print(f"⚠️  .env file not found at {env_path}")
        return False
    
    print(f"\n📝 Updating .env file...")
    
    # Read current content
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Update POSTGRES_PASSWORD
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('POSTGRES_PASSWORD='):
            lines[i] = f'POSTGRES_PASSWORD={password}\n'
            updated = True
            break
    
    if not updated:
        # Add if not found
        lines.append(f'POSTGRES_PASSWORD={password}\n')
    
    # Write back
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"✅ Updated POSTGRES_PASSWORD in {env_path}")
    return True


def test_connection(username, password, database, host='localhost', port=5432):
    """Test the connection with new credentials."""
    print(f"\n🧪 Testing connection with new credentials...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database,
            connect_timeout=5
        )
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✅ Connection successful!")
            print(f"   PostgreSQL version: {version.split(',')[0]}")
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"❌ Connection test failed: {e}")
        return False


def main():
    """Main function."""
    print("=" * 60)
    print("PostgreSQL Password Setup for VOS Tool")
    print("=" * 60)
    
    # Get configuration from environment or defaults
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = int(os.getenv('POSTGRES_PORT', '5432'))
    database = os.getenv('POSTGRES_DB', 'vos_tool')
    username = os.getenv('POSTGRES_USER', 'vos_user')
    
    print(f"\n📋 Configuration:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Database: {database}")
    print(f"   User: {username}")
    
    # Connect as postgres superuser
    conn = get_postgres_connection(host=host, port=port)
    if not conn:
        sys.exit(1)
    
    # Get new password
    print(f"\n🔐 Set password for '{username}':")
    password = getpass.getpass("Enter new password: ")
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        print("❌ Passwords don't match!")
        conn.close()
        sys.exit(1)
    
    if not password:
        print("❌ Password cannot be empty!")
        conn.close()
        sys.exit(1)
    
    # Create or reset user
    try:
        create_or_reset_user(conn, username, password, database)
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        conn.close()
        sys.exit(1)
    finally:
        conn.close()
    
    # Test connection
    if not test_connection(username, password, database, host, port):
        print("\n⚠️  Connection test failed, but user was created/reset.")
        print("   Please check your configuration and try again.")
        sys.exit(1)
    
    # Update .env file
    env_path = Path(__file__).parent.parent / '.env'
    if update_env_file(env_path, password):
        print(f"\n✅ Setup complete!")
        print(f"\n📌 Next steps:")
        print(f"   1. Restart your backend: The .env file has been updated")
        print(f"   2. Check logs to verify connection")
        print(f"   3. Test the application")
    else:
        print(f"\n⚠️  User setup complete, but .env file update failed.")
        print(f"   Please manually update POSTGRES_PASSWORD in .env file with:")
        print(f"   POSTGRES_PASSWORD={password}")


if __name__ == '__main__':
    main()
