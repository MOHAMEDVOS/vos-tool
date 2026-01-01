#!/usr/bin/env python3
"""
Fix CHECK constraints on agent_audit_results table.

The constraints were incorrectly checking for text 'Yes'/'No' but the columns are BOOLEAN.
This script updates the constraints to accept boolean TRUE/FALSE values.
"""

import sys
import os

# Add parent directory to path to import lib modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.database import get_db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_constraints():
    """Fix the CHECK constraints on agent_audit_results table."""
    try:
        db = get_db_manager()
        conn = db.connection_pool.getconn()
        cursor = conn.cursor()
        
        logger.info("Fixing CHECK constraints on agent_audit_results table...")
        
        # Drop existing incorrect constraints
        constraints_to_drop = [
            'agent_audit_results_releasing_detection_check',
            'agent_audit_results_late_hello_detection_check',
            'agent_audit_results_rebuttal_detection_check'
        ]
        
        for constraint_name in constraints_to_drop:
            try:
                cursor.execute(f"ALTER TABLE agent_audit_results DROP CONSTRAINT IF EXISTS {constraint_name}")
                logger.info(f"  Dropped constraint: {constraint_name}")
            except Exception as e:
                logger.warning(f"  Could not drop {constraint_name}: {e}")
        
        # Add correct constraints that accept boolean TRUE/FALSE/NULL
        cursor.execute("""
            ALTER TABLE agent_audit_results 
            ADD CONSTRAINT agent_audit_results_releasing_detection_check 
            CHECK (releasing_detection IS NULL OR releasing_detection IN (TRUE, FALSE))
        """)
        logger.info("  Added constraint: agent_audit_results_releasing_detection_check")
        
        cursor.execute("""
            ALTER TABLE agent_audit_results 
            ADD CONSTRAINT agent_audit_results_late_hello_detection_check 
            CHECK (late_hello_detection IS NULL OR late_hello_detection IN (TRUE, FALSE))
        """)
        logger.info("  Added constraint: agent_audit_results_late_hello_detection_check")
        
        cursor.execute("""
            ALTER TABLE agent_audit_results 
            ADD CONSTRAINT agent_audit_results_rebuttal_detection_check 
            CHECK (rebuttal_detection IS NULL OR rebuttal_detection IN (TRUE, FALSE))
        """)
        logger.info("  Added constraint: agent_audit_results_rebuttal_detection_check")
        
        # Commit changes
        conn.commit()
        logger.info("✓ Constraints fixed successfully!")
        
        # Verify constraints
        cursor.execute("""
            SELECT 
                conname as constraint_name,
                pg_get_constraintdef(oid) as definition
            FROM pg_constraint 
            WHERE conrelid = 'agent_audit_results'::regclass 
                AND contype = 'c'
                AND conname LIKE '%detection%'
            ORDER BY conname
        """)
        
        logger.info("\nCurrent constraints:")
        for row in cursor.fetchall():
            logger.info(f"  {row[0]}: {row[1]}")
        
        cursor.close()
        db.connection_pool.putconn(conn)
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to fix constraints: {e}", exc_info=True)
        if 'conn' in locals():
            try:
                conn.rollback()
            except:
                pass
        return False

if __name__ == "__main__":
    success = fix_constraints()
    sys.exit(0 if success else 1)

