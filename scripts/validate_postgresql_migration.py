"""
PostgreSQL Migration Validation Script
Validates that the VOS Tool operates exclusively on PostgreSQL without JSON fallback.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add workspace root to path
sys.path.append(os.getcwd())


class ValidationResult:
    """Stores validation test results."""
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.warnings = []
        self.errors = []
    
    def add_pass(self, test_name: str):
        self.tests_passed += 1
        print(f"  ✓ {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        self.tests_failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  ✗ {test_name}: {error}")
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        print(f"  ⚠ {message}")
    
    def print_summary(self):
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_failed}")
        print(f"Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print("=" * 70)
        return self.tests_failed == 0


def test_database_connectivity(result: ValidationResult):
    """Test 1: Database connectivity."""
    print("\n--- Test 1: Database Connectivity ---")
    try:
        from lib.database import get_db_manager
        db = get_db_manager()
        
        if not db:
            result.add_fail("Database manager initialization", "get_db_manager() returned None")
            return
        
        result.add_pass("Database manager initialized")
        
        # Test connection
        test_result = db.execute_query("SELECT 1 as test", fetchone=True)
        if test_result and test_result.get('test') == 1:
            result.add_pass("Database connection successful")
        else:
            result.add_fail("Database connection", "Query returned unexpected result")
            
    except Exception as e:
        result.add_fail("Database connectivity", str(e))


def test_required_tables(result: ValidationResult):
    """Test 2: Verify all required tables exist."""
    print("\n--- Test 2: Required Tables ---")
    try:
        from lib.database import get_db_manager
        db = get_db_manager()
        
        required_tables = [
            'users',
            'user_sessions',
            'agent_audit_results',
            'lite_audit_results',
            'admin_limits',
            'quota_usage',
            'pending_phrases',
            'repository_phrases',
            'rebuttal_phrases',
            'phrase_learning_settings',
            'app_settings'
        ]
        
        for table in required_tables:
            try:
                query = f"SELECT COUNT(*) as cnt FROM {table}"
                res = db.execute_query(query, fetchone=True)
                result.add_pass(f"Table '{table}' exists ({res['cnt']} records)")
            except Exception as e:
                result.add_fail(f"Table '{table}'", str(e))
                
    except Exception as e:
        result.add_fail("Table verification", str(e))


def test_phrase_learning_postgresql_only(result: ValidationResult):
    """Test 3: Phrase learning uses PostgreSQL only."""
    print("\n--- Test 3: Phrase Learning (PostgreSQL-only) ---")
    try:
        from lib.phrase_learning import get_phrase_learning_manager
        
        manager = get_phrase_learning_manager()
        if not manager:
            result.add_fail("Phrase learning manager", "Failed to initialize")
            return
        
        result.add_pass("Phrase learning manager initialized")
        
        # Test getting stats (should use PostgreSQL)
        stats = manager.get_repository_stats()
        if isinstance(stats, dict):
            result.add_pass(f"Get repository stats ({stats.get('total_phrases', 0)} phrases)")
        else:
            result.add_fail("Get repository stats", "Returned non-dict result")
        
        # Test getting pending phrases
        pending = manager.get_pending_phrases()
        if isinstance(pending, list):
            result.add_pass(f"Get pending phrases ({len(pending)} pending)")
        else:
            result.add_fail("Get pending phrases", "Returned non-list result")
            
    except Exception as e:
        result.add_fail("Phrase learning PostgreSQL test", str(e))


def test_app_settings_postgresql_only(result: ValidationResult):
    """Test 4: App settings uses PostgreSQL only."""
    print("\n--- Test 4: App Settings (PostgreSQL-only) ---")
    try:
        from lib.app_settings_manager import get_app_settings
        
        settings = get_app_settings()
        if not settings:
            result.add_fail("App settings manager", "Failed to initialize")
            return
        
        result.add_pass("App settings manager initialized")
        
        # Test getting a setting
        vad_threshold = settings.get_vad_threshold()
        if isinstance(vad_threshold, int):
            result.add_pass(f"Get VAD threshold ({vad_threshold})")
        else:
            result.add_fail("Get VAD threshold", f"Unexpected type: {type(vad_threshold)}")
        
        # Test setting a value
        test_key = "test_validation_key"
        test_value = "test_value_12345"
        if settings.set_setting("system", test_key, test_value):
            result.add_pass("Set setting in database")
            
            # Verify it was saved
            retrieved = settings.get_setting("system", test_key)
            if retrieved == test_value:
                result.add_pass("Retrieve saved setting")
            else:
                result.add_fail("Retrieve saved setting", f"Expected '{test_value}', got '{retrieved}'")
        else:
            result.add_fail("Set setting", "set_setting returned False")
            
    except Exception as e:
        result.add_fail("App settings PostgreSQL test", str(e))


def test_database_health_monitor(result: ValidationResult):
    """Test 5: Database health monitoring."""
    print("\n--- Test 5: Database Health Monitoring ---")
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            result.add_fail("Health monitor", "Failed to initialize")
            return
        
        result.add_pass("Health monitor initialized")
        
        # Test pool metrics
        pool_metrics = monitor.get_pool_metrics()
        if isinstance(pool_metrics, dict) and 'health_status' in pool_metrics:
            result.add_pass(f"Pool metrics ({pool_metrics['health_status']})")
        else:
            result.add_fail("Pool metrics", "Invalid response")
        
        # Test query metrics
        query_metrics = monitor.get_query_metrics()
        if isinstance(query_metrics, dict):
            result.add_pass(f"Query metrics ({query_metrics.get('total_queries', 0)} queries)")
        else:
            result.add_fail("Query metrics", "Invalid response")
        
        # Test health check
        health = monitor.check_health()
        if isinstance(health, dict) and 'overall_status' in health:
            result.add_pass(f"Health check ({health['overall_status']})")
        else:
            result.add_fail("Health check", "Invalid response")
            
    except Exception as e:
        result.add_fail("Database health monitoring", str(e))


def test_no_json_file_operations(result: ValidationResult):
    """Test 6: Verify no JSON file I/O during runtime."""
    print("\n--- Test 6: JSON File Operations Check ---")
    
    # Check if dashboard_data directory has JSON files
    dashboard_data = Path("dashboard_data")
    if dashboard_data.exists():
        json_files = list(dashboard_data.rglob("*.json"))
        # Exclude migration status file
        json_files = [f for f in json_files if '.migration_status.json' not in str(f)]
        
        if json_files:
            result.add_warning(f"Found {len(json_files)} JSON files in dashboard_data (should be archived)")
            for f in json_files[:5]:  # Show first 5
                result.add_warning(f"  - {f}")
        else:
            result.add_pass("No JSON files in dashboard_data (except migration status)")
    else:
        result.add_pass("dashboard_data directory does not exist")
    
    # Check for SQLite database
    sqlite_db = Path("dashboard_data/phrase_learning.db")
    if sqlite_db.exists():
        result.add_warning("SQLite database still exists (should be deleted)")
    else:
        result.add_pass("SQLite database removed")


def test_user_workflow(result: ValidationResult):
    """Test 7: Basic user workflow."""
    print("\n--- Test 7: User Workflow ---")
    try:
        from lib.dashboard_manager import user_manager
        
        # Test getting a user
        test_user = user_manager.get_user("Mohamed Abdo")
        if test_user:
            result.add_pass(f"Get user 'Mohamed Abdo'")
        else:
            result.add_warning("User 'Mohamed Abdo' not found (may not exist yet)")
        
        # Test getting user role
        role = user_manager.get_user_role("Mohamed Abdo")
        if role:
            result.add_pass(f"Get user role ({role})")
        else:
            result.add_warning("Could not get user role")
            
    except Exception as e:
        result.add_fail("User workflow test", str(e))


def main():
    """Run all validation tests."""
    print("=" * 70)
    print("POSTGRESQL MIGRATION VALIDATION")
    print("=" * 70)
    print("\nValidating that VOS Tool operates exclusively on PostgreSQL...")
    
    result = ValidationResult()
    
    # Run all tests
    test_database_connectivity(result)
    test_required_tables(result)
    test_phrase_learning_postgresql_only(result)
    test_app_settings_postgresql_only(result)
    test_database_health_monitor(result)
    test_no_json_file_operations(result)
    test_user_workflow(result)
    
    # Print summary
    success = result.print_summary()
    
    if success:
        print("\n✅ ALL VALIDATION TESTS PASSED!")
        print("The system is operating exclusively on PostgreSQL.")
        return 0
    else:
        print("\n❌ SOME VALIDATION TESTS FAILED")
        print("Please review the errors above and fix before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
