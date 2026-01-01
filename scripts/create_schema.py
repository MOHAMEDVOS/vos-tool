"""
Execute migration schema SQL file to create missing tables.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Database connection settings
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'vos_tool'),
    'user': os.getenv('POSTGRES_USER', 'vos_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

def execute_schema():
    """Execute the migration schema SQL file."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True  # Auto-commit for DDL statements
        
        schema_file = Path("cloud-migration/migration_schema.sql")
        if not schema_file.exists():
            print(f"ERROR: Schema file not found: {schema_file}")
            return False
        
        print(f"Reading schema file: {schema_file}")
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by semicolons and execute each statement
        cursor = conn.cursor()
        
        # Execute the entire script
        try:
            cursor.execute(sql_content)
            print("Schema created successfully!")
            return True
        except Exception as e:
            # Some statements might fail if tables already exist, which is OK
            error_str = str(e).lower()
            if 'already exists' in error_str or 'duplicate' in error_str:
                print(f"Note: Some objects already exist (this is OK): {e}")
                return True
            else:
                print(f"Error executing schema: {e}")
                # Try executing statements one by one
                statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
                for stmt in statements:
                    if stmt:
                        try:
                            cursor.execute(stmt)
                        except Exception as stmt_error:
                            error_str = str(stmt_error).lower()
                            if 'already exists' not in error_str and 'duplicate' not in error_str:
                                print(f"Warning: {stmt_error}")
                return True
        
    except ImportError:
        print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"ERROR: Failed to create schema: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = execute_schema()
    sys.exit(0 if success else 1)

