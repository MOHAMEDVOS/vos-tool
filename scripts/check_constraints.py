"""Check database constraints."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', '5432')),
    database=os.getenv('POSTGRES_DB', 'vos_tool'),
    user=os.getenv('POSTGRES_USER', 'vos_user'),
    password=os.getenv('POSTGRES_PASSWORD', '')
)

cur = conn.cursor()
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid) 
    FROM pg_constraint 
    WHERE conrelid = 'agent_audit_results'::regclass AND contype = 'c';
""")

print("Check constraints on agent_audit_results:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()

