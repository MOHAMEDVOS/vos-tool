"""
Database Health Monitoring Module for VOS Tool
Tracks connection pool metrics, query performance, and system health.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class QueryLog:
    """Log entry for a database query."""
    timestamp: str
    query: str
    duration: float
    success: bool
    error: Optional[str] = None


@dataclass
class HealthAlert:
    """Health alert for monitoring thresholds."""
    level: str  # 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message: str
    timestamp: str
    metric: str
    value: Any


class DatabaseHealthMonitor:
    """Monitors database health and performance metrics."""
    
    def __init__(self, db_manager, slow_query_threshold: float = 1.0, max_slow_queries: int = 100):
        """
        Initialize the health monitor.
        
        Args:
            db_manager: DatabaseManager instance to monitor
            slow_query_threshold: Threshold in seconds for slow query detection (default: 1.0s)
            max_slow_queries: Maximum number of slow queries to keep in memory (default: 100)
        """
        self.db_manager = db_manager
        self.slow_query_threshold = slow_query_threshold
        self.max_slow_queries = max_slow_queries
        
        # Metrics
        self.metrics = {
            'queries_total': 0,
            'queries_success': 0,
            'queries_failed': 0,
            'slow_queries_count': 0,
            'pool_exhaustion_events': 0,
            'total_query_time': 0.0,
            'last_reset': datetime.now().isoformat()
        }
        
        # Slow queries log (thread-safe deque)
        self.slow_queries = deque(maxlen=max_slow_queries)
        self._lock = threading.Lock()
        
        # Alert thresholds
        self.alert_thresholds = {
            'pool_usage_warning': 80.0,  # %
            'pool_usage_critical': 95.0,  # %
            'error_rate_warning': 5.0,  # %
            'error_rate_critical': 10.0,  # %
            'slow_query_warning': 10,  # count per minute
            'avg_query_time_warning': 500.0,  # ms
        }
        
        logger.info(f"DatabaseHealthMonitor initialized (slow query threshold: {slow_query_threshold}s)")
    
    def log_query(self, query: str, duration: float, success: bool, error: Optional[str] = None):
        """
        Log a query execution for metrics tracking.
        
        Args:
            query: SQL query string (will be truncated for storage)
            duration: Query execution time in seconds
            success: Whether the query succeeded
            error: Error message if query failed
        """
        with self._lock:
            self.metrics['queries_total'] += 1
            self.metrics['total_query_time'] += duration
            
            if success:
                self.metrics['queries_success'] += 1
            else:
                self.metrics['queries_failed'] += 1
            
            # Log slow queries
            if duration >= self.slow_query_threshold:
                self.metrics['slow_queries_count'] += 1
                
                # Truncate query for storage (keep first 200 chars)
                truncated_query = query[:200] + "..." if len(query) > 200 else query
                
                query_log = QueryLog(
                    timestamp=datetime.now().isoformat(),
                    query=truncated_query,
                    duration=duration,
                    success=success,
                    error=error
                )
                self.slow_queries.append(query_log)
    
    def log_pool_exhaustion(self):
        """Log a connection pool exhaustion event."""
        with self._lock:
            self.metrics['pool_exhaustion_events'] += 1
        logger.warning("Connection pool exhaustion event logged")
    
    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Get current connection pool statistics.
        
        Returns:
            Dictionary with pool metrics including usage, available connections, etc.
        """
        try:
            stats = self.db_manager.get_pool_stats()
            
            # Add calculated metrics
            if stats.get('max_connections', 0) > 0:
                stats['health_status'] = self._get_pool_health_status(stats['usage_percent'])
            else:
                stats['health_status'] = 'UNKNOWN'
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get pool metrics: {e}")
            return {
                'error': str(e),
                'health_status': 'ERROR'
            }
    
    def _get_pool_health_status(self, usage_percent: float) -> str:
        """Determine pool health status based on usage percentage."""
        if usage_percent >= self.alert_thresholds['pool_usage_critical']:
            return 'CRITICAL'
        elif usage_percent >= self.alert_thresholds['pool_usage_warning']:
            return 'WARNING'
        else:
            return 'HEALTHY'
    
    def get_query_metrics(self) -> Dict[str, Any]:
        """
        Get query performance metrics.
        
        Returns:
            Dictionary with query statistics
        """
        with self._lock:
            total = self.metrics['queries_total']
            
            metrics = {
                'total_queries': total,
                'successful_queries': self.metrics['queries_success'],
                'failed_queries': self.metrics['queries_failed'],
                'slow_queries': self.metrics['slow_queries_count'],
                'error_rate': (self.metrics['queries_failed'] / total * 100) if total > 0 else 0.0,
                'success_rate': (self.metrics['queries_success'] / total * 100) if total > 0 else 0.0,
                'avg_query_time_ms': (self.metrics['total_query_time'] / total * 1000) if total > 0 else 0.0,
                'last_reset': self.metrics['last_reset']
            }
            
            return metrics
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent slow queries.
        
        Args:
            limit: Maximum number of slow queries to return
            
        Returns:
            List of slow query log entries
        """
        with self._lock:
            # Get the most recent slow queries
            recent_queries = list(self.slow_queries)[-limit:]
            return [asdict(q) for q in reversed(recent_queries)]
    
    def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'checks': {}
        }
        
        # 1. Database connectivity test
        try:
            connectivity_ok = self.db_manager.test_connection()
            health_status['checks']['database_connectivity'] = {
                'status': 'PASS' if connectivity_ok else 'FAIL',
                'message': 'Database is reachable' if connectivity_ok else 'Database connection failed'
            }
            if not connectivity_ok:
                health_status['overall_status'] = 'CRITICAL'
        except Exception as e:
            health_status['checks']['database_connectivity'] = {
                'status': 'FAIL',
                'message': f'Connection test error: {str(e)}'
            }
            health_status['overall_status'] = 'CRITICAL'
        
        # 2. Connection pool health
        try:
            pool_metrics = self.get_pool_metrics()
            pool_status = pool_metrics.get('health_status', 'UNKNOWN')
            
            health_status['checks']['connection_pool'] = {
                'status': pool_status,
                'usage_percent': pool_metrics.get('usage_percent', 0.0),
                'used_connections': pool_metrics.get('used_connections', 0),
                'max_connections': pool_metrics.get('max_connections', 0)
            }
            
            if pool_status in ['CRITICAL', 'ERROR']:
                health_status['overall_status'] = 'CRITICAL'
            elif pool_status == 'WARNING' and health_status['overall_status'] == 'HEALTHY':
                health_status['overall_status'] = 'WARNING'
        except Exception as e:
            health_status['checks']['connection_pool'] = {
                'status': 'ERROR',
                'message': f'Pool check error: {str(e)}'
            }
            if health_status['overall_status'] == 'HEALTHY':
                health_status['overall_status'] = 'WARNING'
        
        # 3. Query performance check
        try:
            query_metrics = self.get_query_metrics()
            error_rate = query_metrics['error_rate']
            avg_query_time = query_metrics['avg_query_time_ms']
            
            query_status = 'HEALTHY'
            if error_rate >= self.alert_thresholds['error_rate_critical']:
                query_status = 'CRITICAL'
            elif error_rate >= self.alert_thresholds['error_rate_warning']:
                query_status = 'WARNING'
            elif avg_query_time >= self.alert_thresholds['avg_query_time_warning']:
                query_status = 'WARNING'
            
            health_status['checks']['query_performance'] = {
                'status': query_status,
                'error_rate': error_rate,
                'avg_query_time_ms': avg_query_time,
                'slow_queries': query_metrics['slow_queries']
            }
            
            if query_status == 'CRITICAL':
                health_status['overall_status'] = 'CRITICAL'
            elif query_status == 'WARNING' and health_status['overall_status'] == 'HEALTHY':
                health_status['overall_status'] = 'WARNING'
        except Exception as e:
            health_status['checks']['query_performance'] = {
                'status': 'ERROR',
                'message': f'Query metrics error: {str(e)}'
            }
        
        return health_status
    
    def get_alerts(self) -> List[HealthAlert]:
        """
        Check for active alerts based on current metrics.
        
        Returns:
            List of active health alerts
        """
        alerts = []
        timestamp = datetime.now().isoformat()
        
        # Pool usage alerts
        try:
            pool_metrics = self.get_pool_metrics()
            usage_percent = pool_metrics.get('usage_percent', 0.0)
            
            if usage_percent >= self.alert_thresholds['pool_usage_critical']:
                alerts.append(HealthAlert(
                    level='CRITICAL',
                    message=f'Connection pool critically high: {usage_percent:.1f}%',
                    timestamp=timestamp,
                    metric='pool_usage',
                    value=usage_percent
                ))
            elif usage_percent >= self.alert_thresholds['pool_usage_warning']:
                alerts.append(HealthAlert(
                    level='WARNING',
                    message=f'Connection pool usage high: {usage_percent:.1f}%',
                    timestamp=timestamp,
                    metric='pool_usage',
                    value=usage_percent
                ))
        except Exception as e:
            logger.error(f"Error checking pool alerts: {e}")
        
        # Query error rate alerts
        try:
            query_metrics = self.get_query_metrics()
            error_rate = query_metrics['error_rate']
            
            if error_rate >= self.alert_thresholds['error_rate_critical']:
                alerts.append(HealthAlert(
                    level='CRITICAL',
                    message=f'Query error rate critically high: {error_rate:.1f}%',
                    timestamp=timestamp,
                    metric='error_rate',
                    value=error_rate
                ))
            elif error_rate >= self.alert_thresholds['error_rate_warning']:
                alerts.append(HealthAlert(
                    level='WARNING',
                    message=f'Query error rate elevated: {error_rate:.1f}%',
                    timestamp=timestamp,
                    metric='error_rate',
                    value=error_rate
                ))
        except Exception as e:
            logger.error(f"Error checking query alerts: {e}")
        
        # Slow query alerts
        with self._lock:
            slow_query_count = self.metrics['slow_queries_count']
            if slow_query_count >= self.alert_thresholds['slow_query_warning']:
                alerts.append(HealthAlert(
                    level='WARNING',
                    message=f'High number of slow queries: {slow_query_count}',
                    timestamp=timestamp,
                    metric='slow_queries',
                    value=slow_query_count
                ))
        
        # Pool exhaustion alerts
        with self._lock:
            exhaustion_events = self.metrics['pool_exhaustion_events']
            if exhaustion_events > 0:
                alerts.append(HealthAlert(
                    level='WARNING',
                    message=f'Connection pool exhaustion events: {exhaustion_events}',
                    timestamp=timestamp,
                    metric='pool_exhaustion',
                    value=exhaustion_events
                ))
        
        return alerts
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive health summary including all metrics and alerts.
        
        Returns:
            Dictionary with complete health status
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'health_check': self.check_health(),
            'pool_metrics': self.get_pool_metrics(),
            'query_metrics': self.get_query_metrics(),
            'slow_queries': self.get_slow_queries(limit=5),
            'alerts': [asdict(alert) for alert in self.get_alerts()],
            'monitoring_config': {
                'slow_query_threshold_seconds': self.slow_query_threshold,
                'max_slow_queries_stored': self.max_slow_queries,
                'alert_thresholds': self.alert_thresholds
            }
        }
        
        return summary
    
    def reset_metrics(self):
        """Reset all metrics counters (useful for testing or periodic resets)."""
        with self._lock:
            self.metrics = {
                'queries_total': 0,
                'queries_success': 0,
                'queries_failed': 0,
                'slow_queries_count': 0,
                'pool_exhaustion_events': 0,
                'total_query_time': 0.0,
                'last_reset': datetime.now().isoformat()
            }
            self.slow_queries.clear()
        logger.info("Health monitor metrics reset")


# Global health monitor instance
_health_monitor: Optional[DatabaseHealthMonitor] = None


def get_health_monitor() -> Optional[DatabaseHealthMonitor]:
    """
    Get or create the global health monitor instance.
    
    Returns:
        DatabaseHealthMonitor instance or None if database manager not available
    """
    global _health_monitor
    
    if _health_monitor is None:
        try:
            from lib.database import get_db_manager
            db_manager = get_db_manager()
            
            if db_manager:
                _health_monitor = DatabaseHealthMonitor(db_manager)
                # Attach monitor to database manager for automatic logging
                db_manager.health_monitor = _health_monitor
                logger.info("Global DatabaseHealthMonitor initialized and attached to DatabaseManager")
            else:
                logger.warning("Database manager not available, health monitor disabled")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize health monitor: {e}")
            return None
    
    return _health_monitor
