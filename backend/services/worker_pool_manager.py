"""
Worker Pool Manager for Multi-User Concurrency
Manages per-user worker allocation to prevent resource exhaustion.
"""

import os
import logging
import threading
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkerPoolManager:
    """
    Manages worker pool allocation per user to ensure fair resource distribution.
    
    Prevents worker pool exhaustion when multiple users process files simultaneously.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._user_workers: Dict[str, int] = defaultdict(int)  # username -> active workers
        self._max_total_workers = self._calculate_max_workers()
        self._max_workers_per_user = self._calculate_max_workers_per_user()
        self._active_users: set = set()
        
        logger.info(f"WorkerPoolManager initialized: max_total={self._max_total_workers}, max_per_user={self._max_workers_per_user}")
    
    def _calculate_max_workers(self) -> int:
        """Calculate maximum total workers based on system and account type."""
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        
        # Check environment override
        if os.getenv("ASSEMBLYAI_MAX_WORKERS"):
            try:
                return int(os.getenv("ASSEMBLYAI_MAX_WORKERS"))
            except ValueError:
                pass
        
        # Default based on account type
        account_type = os.getenv("ASSEMBLYAI_ACCOUNT_TYPE", "free").lower()
        if account_type == "paid":
            return min(cpu_count, 20)  # Paid: up to 20 workers
        else:
            return min(cpu_count, 5)  # Free: max 5 workers
    
    def _calculate_max_workers_per_user(self) -> int:
        """Calculate max workers per user based on expected concurrent users."""
        # Assume max 4 concurrent users, allocate workers fairly
        max_concurrent_users = int(os.getenv("MAX_CONCURRENT_USERS", "4"))
        return max(1, self._max_total_workers // max_concurrent_users)
    
    def get_workers_for_user(self, username: str) -> int:
        """
        Get allocated workers for a user.
        
        Args:
            username: Username requesting workers
            
        Returns:
            Number of workers allocated to this user
        """
        with self._lock:
            self._active_users.add(username)
            
            # Calculate available workers
            total_used = sum(self._user_workers.values())
            available = self._max_total_workers - total_used
            
            # Allocate workers for this user
            if username in self._user_workers:
                # User already has workers, return current allocation
                return self._user_workers[username]
            
            # New user - allocate workers
            if available >= self._max_workers_per_user:
                allocated = self._max_workers_per_user
            elif available > 0:
                allocated = available
            else:
                # No workers available - allocate minimum
                allocated = 1
                logger.warning(f"No workers available for {username}, allocating minimum (1)")
            
            self._user_workers[username] = allocated
            logger.info(f"Allocated {allocated} workers to user {username} (total used: {sum(self._user_workers.values())}/{self._max_total_workers})")
            
            return allocated
    
    def release_user_workers(self, username: str):
        """Release workers when user finishes processing."""
        with self._lock:
            if username in self._user_workers:
                released = self._user_workers.pop(username)
                self._active_users.discard(username)
                logger.info(f"Released {released} workers from user {username} (total used: {sum(self._user_workers.values())}/{self._max_total_workers})")
    
    def get_pool_stats(self) -> Dict[str, any]:
        """Get current pool statistics."""
        with self._lock:
            return {
                "max_total_workers": self._max_total_workers,
                "max_workers_per_user": self._max_workers_per_user,
                "total_used": sum(self._user_workers.values()),
                "available": self._max_total_workers - sum(self._user_workers.values()),
                "active_users": len(self._active_users),
                "user_allocations": dict(self._user_workers)
            }


# Global worker pool manager instance
_worker_pool_manager = None
_worker_pool_lock = threading.Lock()


def get_worker_pool_manager() -> WorkerPoolManager:
    """Get or create the global worker pool manager instance."""
    global _worker_pool_manager
    
    if _worker_pool_manager is None:
        with _worker_pool_lock:
            if _worker_pool_manager is None:
                _worker_pool_manager = WorkerPoolManager()
    
    return _worker_pool_manager

