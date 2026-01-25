"""
Migration script to add feedback column to agent_audit_results table.
Run this script to manually add the feedback column to Railway database.

Usage:
    python scripts/migrate_add_feedback_column.py

Make sure DATABASE_URL is set in your .env file or environment variables.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def add_feedback_column():
    """Add feedback column to agent_audit_results table."""
    
    # Try to load from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not installed, using environment variables only")
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        print()
        print("Please add DATABASE_URL to your .env file:")
        print("  DATABASE_URL=postgresql://postgres:password@database-vos-vos.up.railway.app:port/railway")
        print()
        print("Get the full URL from Railway → Database VOS → Connect tab")
        return False
    
    try:
        import psycopg2
    except ImportError:
        print("❌ ERROR: psycopg2 not installed")
        print("Install it with: pip install psycopg2-binary")
        return False
    
    try:
        # Connect to database
        print("🔌 Connecting to Railway database...")
        print(f"   Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'unknown'}")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Check if column already exists
        print("🔍 Checking if feedback column exists...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'agent_audit_results' 
            AND column_name = 'feedback';
        """)
        
        if cursor.fetchone():
            print("✅ Feedback column already exists!")
            cursor.close()
            conn.close()
            return True
        
        # Add the column
        print("➕ Adding feedback column to agent_audit_results table...")
        cursor.execute("""
            ALTER TABLE agent_audit_results 
            ADD COLUMN feedback TEXT DEFAULT NULL;
        """)
        
        conn.commit()
        
        # Verify it was added
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'agent_audit_results' 
            AND column_name = 'feedback';
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"✅ SUCCESS! Feedback column added: {result[0]} ({result[1]})")
        else:
            print("⚠️  Column may not have been added correctly")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Railway Database Migration: Add Feedback Column")
    print("=" * 60)
    print()
    
    success = add_feedback_column()
    
    print()
    if success:
        print("✨ Migration completed successfully!")
        print("   You can now run audits and the feedback will be saved.")
    else:
        print("❌ Migration failed. Please check the error above.")
    print("=" * 60)
