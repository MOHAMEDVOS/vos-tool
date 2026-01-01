"""
Database connection and configuration for VOS Tool.
Supports both PostgreSQL and SQLite (for development).
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, will use system environment variables
    pass

logger = logging.getLogger(__name__)

# Try to import PostgreSQL adapter
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
    logger.info(f"✓ psycopg2 {psycopg2.__version__} loaded successfully")
except ImportError as e:
    POSTGRESQL_AVAILABLE = False
    logger.warning(f"psycopg2 not available - PostgreSQL support disabled. Error: {e}")
    logger.warning("Install with: pip install psycopg2-binary")

# SQLite is always available
import sqlite3

class DatabaseManager:
    """Manages database connections and provides unified interface."""
    
    def __init__(self):
        self.db_type = os.getenv('DB_TYPE', 'postgresql').lower()
        self.connection_pool = None
        self.db_path = None
        
        if self.db_type == 'postgresql':
            if not POSTGRESQL_AVAILABLE:
                logger.error("PostgreSQL requested but psycopg2 not installed. Install with: pip install psycopg2-binary")
                raise ImportError("psycopg2 not available")
            self._init_postgresql()
        elif self.db_type == 'sqlite':
            self._init_sqlite()
        else:
            raise ValueError(f"Unsupported DB_TYPE: {self.db_type}. Use 'postgresql' or 'sqlite'")
    
    def _init_postgresql(self):
        """Initialize PostgreSQL connection pool."""
        # Get host from environment, default to localhost
        host = os.getenv('POSTGRES_HOST', 'localhost')
        
        # If host is "postgres" (Docker service name) and we're running locally,
        # try localhost instead (for local development)
        if host == 'postgres':
            import socket
            try:
                # Try to resolve "postgres" hostname
                socket.gethostbyname('postgres')
                # If it resolves, we're likely in Docker, use "postgres"
                logger.info("Detected Docker environment, using 'postgres' as database host")
            except socket.gaierror:
                # "postgres" doesn't resolve, we're running locally
                logger.info("Running locally, using 'localhost' instead of 'postgres'")
                host = 'localhost'
        
        try:
            # Get pool size from environment or use default (50 for better concurrency)
            max_connections = int(os.getenv('DB_POOL_MAX_SIZE', '50'))
            connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
            
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=max_connections,
                host=host,
                port=os.getenv('POSTGRES_PORT', '5432'),
                database=os.getenv('POSTGRES_DB', 'vos_tool'),
                user=os.getenv('POSTGRES_USER', 'vos_user'),
                password=os.getenv('POSTGRES_PASSWORD', ''),
                connect_timeout=connect_timeout,  # Connection timeout in seconds
            )
            logger.info(f"✓ PostgreSQL connection pool created successfully (host: {host}, maxconn: {max_connections}, timeout: {connect_timeout}s)")
        except Exception as e:
            logger.error(f"✗ Failed to create PostgreSQL connection pool: {e}")
            raise
    
    def _init_sqlite(self):
        """Initialize SQLite connection (for development)."""
        db_path = Path("dashboard_data/vos_tool.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        logger.info(f"✓ SQLite database initialized at {db_path}")
    
    def get_connection(self):
        """Get a database connection."""
        if self.db_type == 'postgresql':
            if not self.connection_pool:
                raise RuntimeError("PostgreSQL connection pool not initialized")
            return self.connection_pool.getconn()
        else:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
    
    def return_connection(self, conn):
        """Return connection to pool (PostgreSQL only) or close (SQLite)."""
        if self.db_type == 'postgresql':
            if self.connection_pool:
                self.connection_pool.putconn(conn)
        else:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True, fetchone: bool = False, max_retries: int = 3):
        """
        Execute a query with retry logic for connection pool exhaustion.
        
        Args:
            query: SQL query string
            params: Query parameters (for parameterized queries)
            fetch: Whether to fetch all results (True) or just execute (False)
            fetchone: Whether to fetch only one result (overrides fetch if True)
            max_retries: Maximum number of retry attempts for pool exhaustion (default: 3)
            
        Returns:
            - Single dictionary if fetchone=True
            - List of dictionaries (rows) if fetch=True and fetchone=False
            - rowcount if fetch=False
        """
        import time
        
        conn = None
        cursor = None
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                conn = self.get_connection()
                
                if self.db_type == 'postgresql':
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    # Set query timeout (30 seconds default, configurable via env)
                    query_timeout = int(os.getenv('DB_QUERY_TIMEOUT', '30000'))  # milliseconds
                    cursor.execute(f"SET statement_timeout = {query_timeout}")
                else:
                    cursor = conn.cursor()
                    # Convert PostgreSQL syntax to SQLite if needed
                    query = self._convert_query_for_sqlite(query)
                
                # Execute query
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetchone:
                    # Fetch single row
                    if self.db_type == 'postgresql':
                        result = cursor.fetchone()
                        return dict(result) if result else None
                    else:
                        # SQLite returns tuples, convert to dict
                        columns = [desc[0] for desc in cursor.description] if cursor.description else []
                        row = cursor.fetchone()
                        return dict(zip(columns, row)) if row else None
                elif fetch:
                    # Fetch all rows - but only if this is a SELECT query
                    # Check if cursor has results to avoid "no results to fetch" error
                    if cursor.description is None:
                        # No results (UPDATE/INSERT/DELETE), just commit
                        conn.commit()
                        return cursor.rowcount
                    # SELECT query with results
                    if self.db_type == 'postgresql':
                        results = cursor.fetchall()
                        return [dict(row) for row in results]
                    else:
                        # SQLite returns tuples, convert to dict
                        columns = [desc[0] for desc in cursor.description] if cursor.description else []
                        rows = cursor.fetchall()
                        return [dict(zip(columns, row)) for row in rows]
                else:
                    # Just execute, don't fetch
                    conn.commit()
                    return cursor.rowcount
                
            except psycopg2.pool.PoolError as e:
                # Handle connection pool exhaustion with retry
                if "connection pool exhausted" in str(e).lower() or "pool" in str(e).lower():
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        wait_time = 0.1 * (2 ** (retry_count - 1))  # Exponential backoff: 0.1s, 0.2s, 0.4s
                        logger.warning(f"Connection pool exhausted, retrying in {wait_time:.2f}s (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        # Clean up before retry
                        if cursor:
                            try:
                                cursor.close()
                            except:
                                pass
                        if conn:
                            try:
                                self.return_connection(conn)
                            except:
                                pass
                        conn = None
                        cursor = None
                        continue
                # Re-raise if max retries reached or different pool error
                if conn:
                    conn.rollback()
                logger.error(f"Database pool error: {e}")
                logger.error(f"Query: {query[:200]}...")
                raise
            except Exception as e:
                if conn:
                    conn.rollback()
                logger.error(f"Database query failed: {e}")
                logger.error(f"Query: {query[:200]}...")
                if params:
                    logger.error(f"Params: {params}")
                raise
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass
                if conn:
                    try:
                        self.return_connection(conn)
                    except:
                        pass
    
    def _convert_query_for_sqlite(self, query: str) -> str:
        """Convert PostgreSQL-specific syntax to SQLite."""
        # Replace gen_random_uuid() with SQLite equivalent
        query = query.replace('gen_random_uuid()', "(lower(hex(randomblob(16))))")
        # Replace TIMESTAMP WITH TIME ZONE with TIMESTAMP
        query = query.replace('TIMESTAMP WITH TIME ZONE', 'TIMESTAMP')
        # Replace INET with TEXT
        query = query.replace(' INET', ' TEXT')
        # Replace %s placeholders with ? for SQLite
        # Note: We'll handle this in execute_query instead
        return query
    
    def execute_many(self, query: str, params_list: List[tuple], fetch: bool = False) -> int:
        """
        Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            fetch: Whether to fetch results
            
        Returns:
            Total number of rows affected
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            
            if self.db_type == 'postgresql':
                cursor = conn.cursor()
            else:
                cursor = conn.cursor()
                query = self._convert_query_for_sqlite(query)
                # Convert %s to ? for SQLite
                query = query.replace('%s', '?')
            
            if self.db_type == 'postgresql':
                cursor.executemany(query, params_list)
            else:
                # SQLite uses ? instead of %s
                cursor.executemany(query, params_list)
            
            conn.commit()
            return cursor.rowcount
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database executemany failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            result = self.execute_query("SELECT 1 as test")
            return len(result) > 0 and result[0].get('test') == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dictionary with pool statistics including:
            - max_connections: Maximum pool size
            - used_connections: Currently used connections (if available)
            - available_connections: Available connections (if available)
            - usage_percent: Percentage of pool in use (if available)
        """
        stats = {
            'max_connections': 0,
            'used_connections': 0,
            'available_connections': 0,
            'usage_percent': 0.0,
            'pool_type': self.db_type
        }
        
        if self.db_type == 'postgresql' and self.connection_pool:
            try:
                stats['max_connections'] = self.connection_pool.maxconn
                # Try to get used connections (internal attribute)
                if hasattr(self.connection_pool, '_used'):
                    stats['used_connections'] = len(self.connection_pool._used)
                    stats['available_connections'] = stats['max_connections'] - stats['used_connections']
                    stats['usage_percent'] = (stats['used_connections'] / stats['max_connections']) * 100 if stats['max_connections'] > 0 else 0.0
            except Exception as e:
                logger.debug(f"Could not get detailed pool stats: {e}")
        
        return stats
    
    def is_pool_healthy(self, threshold: float = 0.9) -> bool:
        """
        Check if connection pool is healthy (not too full).
        
        Args:
            threshold: Maximum usage percentage before considered unhealthy (default: 0.9 = 90%)
            
        Returns:
            True if pool is healthy, False if pool is nearly exhausted
        """
        if self.db_type != 'postgresql' or not self.connection_pool:
            return True  # SQLite doesn't have pool issues
        
        try:
            stats = self.get_pool_stats()
            usage_percent = stats.get('usage_percent', 0.0)
            return usage_percent < (threshold * 100)
        except Exception as e:
            logger.debug(f"Could not check pool health: {e}")
            return True  # Assume healthy if we can't check

# Global database manager instance (will be initialized on first import)
db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> Optional[DatabaseManager]:
    """Get or create the global database manager instance.
    
    Returns None if database initialization fails, allowing fallback to JSON storage.
    """
    global db_manager
    if db_manager is None:
        try:
            db_manager = DatabaseManager()
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            logger.warning("Falling back to JSON file storage")
            return None
    return db_manager

# Initialize on import if DB_TYPE is set
if os.getenv('DB_TYPE'):
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        logger.warning(f"Database manager initialization deferred: {e}")

