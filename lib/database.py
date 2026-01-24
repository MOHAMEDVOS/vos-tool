"""
Database connection and configuration for VOS Tool.
Supports both PostgreSQL and SQLite (for development).
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from urllib.parse import urlparse, parse_qs, unquote

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    try:
        load_dotenv()
    except ValueError as e:
        if "embedded null character" in str(e):
            # .env file is corrupted, try to read it safely or skip it
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("⚠️  .env file contains null characters, skipping environment file loading")
            # Continue without .env file
        else:
            raise
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


def retry_on_db_error(max_retries=3, backoff_factor=2):
    """
    Decorator to retry database operations on transient failures.
    
    Handles connection pool exhaustion, timeouts, and transient network errors.
    """
    import time
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    
                    # Check if retryable
                    is_retryable = ('pool' in error_str or 'exhausted' in error_str or 
                                   'timeout' in error_str or 'timed out' in error_str or
                                   ('connection' in error_str and ('refused' in error_str or 'reset' in error_str)))
                    
                    if is_retryable and attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"DB operation failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        if attempt == max_retries - 1:
                            logger.error(f"All {max_retries} retry attempts exhausted for {func.__name__}")
                        raise
            
            raise last_exception
        return wrapper
    return decorator


def _parse_database_url(database_url: str) -> Dict[str, Optional[str]]:
    try:
        if not database_url:
            return {}

        normalized = database_url.strip()
        if normalized.startswith('postgres://'):
            normalized = 'postgresql://' + normalized[len('postgres://'):]

        parsed = urlparse(normalized)
        if parsed.scheme not in {'postgresql', 'postgres'}:
            return {}

        query = parse_qs(parsed.query)
        sslmode = query.get('sslmode', [None])[0]

        return {
            'host': parsed.hostname,
            'port': str(parsed.port) if parsed.port else None,
            'database': parsed.path.lstrip('/') if parsed.path else None,
            'user': unquote(parsed.username) if parsed.username else None,
            'password': unquote(parsed.password) if parsed.password else None,
            'sslmode': sslmode,
        }
    except Exception:
        return {}


class DatabaseManager:
    """Manages database connections and provides unified interface."""

    def __init__(self):
        self.db_type = os.getenv('DB_TYPE', 'postgresql').lower()
        self.connection_pool = None
        self.db_path = None
        self.health_monitor = None  # Will be set by health monitor module

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
        # Get database components from environment or DATABASE_URL
        # Priority: parse from URL if available, else use specific env vars
        env_host = os.getenv('POSTGRES_HOST') or os.getenv('PGHOST')
        env_port = os.getenv('POSTGRES_PORT') or os.getenv('PGPORT')
        env_db = os.getenv('POSTGRES_DB') or os.getenv('PGDATABASE')
        env_user = os.getenv('POSTGRES_USER') or os.getenv('PGUSER')
        env_password = os.getenv('POSTGRES_PASSWORD') or os.getenv('PGPASSWORD')
        
        # We prioritize components parsed from DATABASE_URL if available
        host = db_url_parts.get('host') or env_host or 'localhost'
        port = db_url_parts.get('port') or env_port or '5432'
        database = db_url_parts.get('database') or env_db or 'vos_tool'
        user = db_url_parts.get('user') or env_user or 'vos_user'
        password = db_url_parts.get('password') or env_password or ''

        # If host is "postgres" (Docker service name) and we're running locally,
        # try localhost instead (for local development)
        if host == 'postgres' or host == 'localhost':
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

        # Prefer IPv4 for Supabase (Railway containers often have no IPv6 route)
        try:
            import socket
            force_ipv4 = os.getenv('POSTGRES_FORCE_IPV4', '0')  # Default to IPv4
            if force_ipv4 is None:
                force_ipv4 = '1' if 'supabase.co' in host else '0'
            if str(force_ipv4).lower() in {'1', 'true', 'yes', 'on'}:
                ipv4 = socket.gethostbyname(host)
                if ipv4 and ipv4 != host:
                    logger.info(f"Resolved IPv4 database host: {host} -> {ipv4}")
                    host = ipv4
            else:
                logger.info(f"Using IPv4 database host: {host}")
        except socket.gaierror:
            logger.error(f"Failed to resolve host: {host}")
            host = 'localhost'

        try:
            # Get pool size from environment or use default
            # Increased from 10 to 20 to support more concurrent users (P0 Fix #2)
            max_connections = int(os.getenv('DB_POOL_MAX_SIZE', '20'))
            connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))

            port = os.getenv('POSTGRES_PORT') or os.getenv('PGPORT') or db_url_parts.get('port') or '5432'
            database = os.getenv('POSTGRES_DB') or os.getenv('PGDATABASE') or db_url_parts.get('database') or 'vos_tool'
            user = os.getenv('POSTGRES_USER') or os.getenv('PGUSER') or db_url_parts.get('user') or 'vos_user'
            password = os.getenv('POSTGRES_PASSWORD') or os.getenv('PGPASSWORD') or db_url_parts.get('password') or ''

            sslmode = os.getenv('POSTGRES_SSLMODE') or db_url_parts.get('sslmode')
            if not sslmode:
                sslmode = 'require' if 'supabase.co' in host else 'prefer'

            def _create_pool(resolved_host: str):
                return psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=max_connections,
                    host=resolved_host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    connect_timeout=connect_timeout,
                    sslmode=sslmode,
                )

            try:
                self.connection_pool = _create_pool(host)
                logger.info(
                    f"✓ PostgreSQL connection pool created successfully (host: {host}, db: {database}, maxconn: {max_connections}, timeout: {connect_timeout}s)"
                )
            except Exception as e:
                message = str(e)
                if 'Network is unreachable' in message:
                    import socket

                    try:
                        addrinfo = socket.getaddrinfo(host, int(port), family=socket.AF_INET, type=socket.SOCK_STREAM)
                        ipv4 = addrinfo[0][4][0] if addrinfo else None
                    except Exception:
                        ipv4 = None

                    if ipv4:
                        self.connection_pool = _create_pool(ipv4)
                        logger.info(
                            f"✓ PostgreSQL connection pool created successfully (host: {ipv4}, db: {database}, maxconn: {max_connections}, timeout: {connect_timeout}s)"
                        )
                    else:
                        raise
                else:
                    raise
        except Exception as e:
            logger.error(f"✗ Failed to create PostgreSQL connection pool: {e}")
            raise
    
    def _init_sqlite(self):
        """Initialize SQLite connection (for development)."""
        db_path = Path("dashboard_data/vos_tool.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        logger.info(f"✓ SQLite database initialized at {db_path}")
    
    @retry_on_db_error(max_retries=3, backoff_factor=2)
    def get_connection(self):
        """Get a database connection with automatic retry on pool exhaustion."""
        if self.db_type == 'postgresql':
            if not self.connection_pool:
                raise RuntimeError("PostgreSQL connection pool not initialized")
            try:
                conn = self.connection_pool.getconn()
                logger.debug("Connection acquired from pool")
                return conn
            except Exception as e:
                logger.error(f"Failed to get connection from pool: {e}")
                raise
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
        start_time = time.time()  # Track query execution time
        
        while retry_count < max_retries:
            try:
                conn = self.get_connection()
                
                # Validate connection is still active
                if self.db_type == 'postgresql':
                    try:
                        # Test connection with a simple query
                        test_cursor = conn.cursor()
                        test_cursor.execute('SELECT 1')
                        test_cursor.close()
                    except Exception as conn_test_error:
                        # Connection is dead, close it and get a new one
                        try:
                            if conn:
                                conn.close()
                        except:
                            pass
                        conn = self.get_connection()
                    
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
                
                # Log pool exhaustion event
                if self.health_monitor:
                    self.health_monitor.log_pool_exhaustion()
                
                raise
            except Exception as e:
                if conn:
                    conn.rollback()
                logger.error(f"Database query failed: {e}")
                logger.error(f"Query: {query[:200]}...")
                if params:
                    logger.error(f"Params: {params}")
                
                # Log failed query
                duration = time.time() - start_time
                if self.health_monitor:
                    self.health_monitor.log_query(query, duration, success=False, error=str(e))
                
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
                
                # Log successful query (if we got here without exception)
                # Note: This will only run if no exception was raised
                if 'e' not in locals():  # No exception occurred
                    duration = time.time() - start_time
                    if self.health_monitor:
                        self.health_monitor.log_query(query, duration, success=True)
    
    def cleanup_idle_connections(self):
        """Clean up idle connections to prevent pool exhaustion."""
        if self.connection_pool and self.db_type == 'postgresql':
            try:
                # Get current pool status
                current_connections = getattr(self.connection_pool, '_pool', [])
                if len(current_connections) > 5:  # Keep minimum 5 connections
                    # Close excess idle connections
                    excess_count = len(current_connections) - 5
                    for _ in range(min(excess_count, 3)):  # Close max 3 at a time
                        try:
                            conn = self.connection_pool.getconn()
                            conn.close()
                            self.connection_pool.putconn(conn, close=True)
                        except:
                            pass
                    logger.info(f"Cleaned up {min(excess_count, 3)} idle connections")
            except Exception as e:
                logger.warning(f"Error during connection cleanup: {e}")
    
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
    
    def execute_many(self, query: str, params_list: List[tuple], fetch: bool = False, chunk_size: int = 100) -> int:
        """
        Execute a query multiple times with different parameters.
        Uses chunked inserts for large batches to prevent connection pool exhaustion.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            fetch: Whether to fetch results
            chunk_size: Number of records to insert per chunk (default: 100)
            
        Returns:
            Total number of rows affected
        """
        if not params_list:
            return 0
        
        total_rows = 0
        total_chunks = (len(params_list) + chunk_size - 1) // chunk_size
        
        # For large batches, process in chunks to avoid holding connection too long
        if len(params_list) > chunk_size:
            logger.info(f"Executing {len(params_list)} records in {total_chunks} chunks of {chunk_size}")
            for chunk_idx in range(0, len(params_list), chunk_size):
                chunk = params_list[chunk_idx:chunk_idx + chunk_size]
                chunk_num = (chunk_idx // chunk_size) + 1
                logger.debug(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} records)")
                total_rows += self._execute_many_chunk(query, chunk)
            logger.info(f"Completed {total_chunks} chunks, {total_rows} total rows inserted")
        else:
            # Small batches: execute directly
            total_rows = self._execute_many_chunk(query, params_list)
        
        return total_rows
    
    def _execute_many_chunk(self, query: str, params_list: List[tuple]) -> int:
        """Execute a single chunk of parameters with timeout protection."""
        import time
        conn = None
        cursor = None
        start_time = time.time()
        timeout_seconds = 30  # 30 second timeout per chunk
        
        try:
            conn = self.get_connection()
            
            # Set statement timeout for PostgreSQL
            if self.db_type == 'postgresql':
                cursor = conn.cursor()
                try:
                    cursor.execute("SET statement_timeout = %s", (timeout_seconds * 1000,))  # milliseconds
                except Exception:
                    pass  # Ignore if timeout setting fails
            else:
                cursor = conn.cursor()
                query = self._convert_query_for_sqlite(query)
                query = query.replace('%s', '?')
            
            if self.db_type == 'postgresql':
                cursor.executemany(query, params_list)
            else:
                cursor.executemany(query, params_list)
            
            conn.commit()
            elapsed = time.time() - start_time
            if elapsed > 10:
                logger.warning(f"execute_many chunk took {elapsed:.2f}s (slow, consider reducing chunk_size)")
            return cursor.rowcount
            
        except Exception as e:
            if conn:
                conn.rollback()
            elapsed = time.time() - start_time
            logger.error(f"Database executemany failed after {elapsed:.2f}s: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)
    
    def execute_values_batch(self, query: str, values_list: List[tuple], page_size: int = 100) -> int:
        """
        Execute batch insert using psycopg2.extras.execute_values for optimal performance.
        
        This is significantly faster than execute_many/executemany for PostgreSQL.
        Uses VALUES syntax for true batch inserts (50x faster than individual inserts).
        
        Args:
            query: SQL query with %s placeholder for VALUES (e.g., "INSERT INTO table (...) VALUES %s")
            values_list: List of tuples with values to insert
            page_size: Number of rows per batch (default: 100)
            
        Returns:
            Number of rows inserted
            
        Example:
            query = "INSERT INTO users (name, email) VALUES %s"
            values = [('Alice', 'alice@example.com'), ('Bob', 'bob@example.com')]
            count = db.execute_values_batch(query, values)
        """
        if not values_list:
            return 0
        
        if self.db_type != 'postgresql':
            # Fallback to execute_many for non-PostgreSQL databases
            logger.warning("execute_values_batch only optimized for PostgreSQL, falling back to execute_many")
            # Convert query format from VALUES %s to standard INSERT
            if values_list:
                placeholders = ','.join(['%s'] * len(values_list[0]))
                standard_query = query.replace(" VALUES %s", f" VALUES ({placeholders})")
                return self.execute_many(standard_query, values_list)
            return 0
        
        try:
            from psycopg2.extras import execute_values
        except ImportError:
            logger.error("psycopg2.extras not available, falling back to execute_many")
            if values_list:
                placeholders = ','.join(['%s'] * len(values_list[0]))
                standard_query = query.replace(" VALUES %s", f" VALUES ({placeholders})")
                return self.execute_many(standard_query, values_list)
            return 0
        
        conn = None
        total_rows = 0
        
        try:
            conn = self.get_connection()
            
            with conn.cursor() as cursor:
                # Use execute_values for optimal batch insert performance
                execute_values(
                    cursor,
                    query,
                    values_list,
                    page_size=page_size  # Insert page_size rows per round trip
                )
                total_rows = cursor.rowcount
                
            conn.commit()
            logger.info(f"✅ Batch inserted {total_rows} rows using execute_values (page_size={page_size})")
            
            # Record metrics if health monitor is available
            if self.health_monitor:
                try:
                    self.health_monitor.record_query_execution(
                        query[:100],  # Truncate query for logging
                        0.0,  # Duration tracked elsewhere
                        success=True
                    )
                except Exception:
                    pass
            
            return total_rows
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Batch insert failed: {e}")
            
            # Record error if health monitor is available
            if self.health_monitor:
                try:
                    self.health_monitor.record_query_execution(
                        query[:100],
                        0.0,
                        success=False
                    )
                except Exception:
                    pass
            
            raise
            
        finally:
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

