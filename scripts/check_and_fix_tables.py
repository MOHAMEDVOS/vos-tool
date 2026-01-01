"""Check which tables exist and create missing ones."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'vos_tool'),
    'user': os.getenv('POSTGRES_USER', 'vos_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

def check_and_create_tables():
    """Check tables and create missing ones."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if audit_logs exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'audit_logs'
            );
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    username VARCHAR(255) NOT NULL,
                    action VARCHAR(255) NOT NULL,
                    details JSONB,
                    ip_address INET,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("Created audit_logs table")
        else:
            print("audit_logs table already exists")
        
        # Check if rebuttal_phrases has source column
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rebuttal_phrases' AND column_name = 'source';
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE rebuttal_phrases ADD COLUMN source VARCHAR(50) DEFAULT 'manual';")
                print("Added source column to rebuttal_phrases")
            except Exception as e:
                print(f"Could not add source column (may need owner permissions): {e}")
        else:
            print("rebuttal_phrases.source column exists")
        
        conn.close()
        print("\nTable check complete!")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_and_create_tables()
    sys.exit(0 if success else 1)

