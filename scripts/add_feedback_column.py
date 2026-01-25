"""
Database Migration: Add feedback column to agent_audit_results table

This migration adds a 'feedback' TEXT column to store LLM reasoning
when rebuttal detection = 'No'.
"""

ALTER_QUERY = """
ALTER TABLE agent_audit_results 
ADD COLUMN IF NOT EXISTS feedback TEXT DEFAULT NULL;
"""

# Run this migration
if __name__ == "__main__":
    from lib.database import get_db_manager
    
    db = get_db_manager()
    if db:
        try:
            db.execute_query(ALTER_QUERY, fetch=False)
            print("✅ Successfully added 'feedback' column to agent_audit_results table")
        except Exception as e:
            print(f"❌ Migration failed: {e}")
    else:
        print("❌ Database not available")
