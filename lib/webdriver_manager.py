"""
WebDriver Manager Module
Ensures Chrome/Selenium WebDriver instances are always properly cleaned up.
Prevents memory leaks that cause server crashes.
"""

import atexit
import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import psutil for process management
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - process cleanup may be less reliable")


class ChromeProcessManager:
    """
    Manages Chrome process lifecycle to prevent memory leaks.
    
    Why This Is Critical:
    - Each Chrome instance = 100-200MB RAM
    - After 10 failed audits with leaks = 1-2GB leaked
    - Server runs out of memory and crashes
    - Requires manual restart
    
    This manager ensures:
    - All Chrome processes are tracked
    - Processes are killed even if driver.quit() fails
    - Temp profiles are cleaned up
    - No orphaned processes remain
    """
    
    def __init__(self):
        self.tracked_pids = set()
        self.tracked_profiles = set()
        
    def register_process(self, pid: int):
        """Register a Chrome process for tracking"""
        if pid:
            self.tracked_pids.add(pid)
            logger.info(f"Registered Chrome process: PID {pid}")
    
    def register_profile(self, profile_path: Path):
        """Register a temp profile for cleanup"""
        if profile_path and profile_path.exists():
            self.tracked_profiles.add(profile_path)
            logger.info(f"Registered temp profile: {profile_path}")
    
    def kill_process(self, pid: int):
        """Force kill a Chrome process"""
        if not pid or not PSUTIL_AVAILABLE:
            return False
        
        try:
            process = psutil.Process(pid)
            if 'chrome' in process.name().lower():
                process.terminate()
                process.wait(timeout=5)
                logger.info(f"Killed Chrome process: PID {pid}")
                return True
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
        
        return False
    
    def cleanup_profile(self, profile_path: Path):
        """Clean up a temp profile directory"""
        if not profile_path or not profile_path.exists():
            return False
        
        try:
            shutil.rmtree(profile_path, ignore_errors=True)
            logger.info(f"Cleaned up temp profile: {profile_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup profile {profile_path}: {e}")
            return False
    
    def cleanup_all(self):
        """
        Emergency cleanup: Kill all tracked processes and remove temp files.
        Called automatically on app exit via atexit.
        """
        logger.info(f"Cleaning up {len(self.tracked_pids)} Chrome processes and {len(self.tracked_profiles)} profiles")
        
        # Kill all tracked processes
        for pid in list(self.tracked_pids):
            self.kill_process(pid)
        
        # Clean all temp profiles
        for profile in list(self.tracked_profiles):
            self.cleanup_profile(profile)
        
        self.tracked_pids.clear()
        self.tracked_profiles.clear()
        logger.info("Chrome cleanup complete")


# Global instance
_chrome_manager = ChromeProcessManager()

# Register cleanup on app exit
atexit.register(_chrome_manager.cleanup_all)


def get_chrome_manager() -> ChromeProcessManager:
    """Get the global Chrome process manager"""
    return _chrome_manager


@contextmanager
def managed_chrome_driver(driver_init_func, *args, **kwargs):
    """
    Context manager for safe Chrome WebDriver usage.
    
    Guarantees cleanup even if:
    - Exception occurs
    - Early return
    - User cancels operation
    - driver.quit() fails
    
    Usage:
        with managed_chrome_driver(init_chrome_driver, options) as driver:
            # Use driver here
            driver.get("https://example.com")
            # Driver automatically closes when exiting context
    
    Args:
        driver_init_func: Function that creates and returns WebDriver
        *args, **kwargs: Arguments to pass to driver_init_func
        
    Yields:
        WebDriver instance
        
    Example:
        def my_automation():
            with managed_chrome_driver(init_chrome_driver) as driver:
                driver.get("https://readymode.com")
                # Do work...
                return results
            # Driver is guaranteed closed here
    """
    driver = None
    chrome_pid = None
    temp_profile = None
    manager = get_chrome_manager()
    
    try:
        # Initialize driver
        logger.info("Initializing Chrome WebDriver with managed context")
        driver = driver_init_func(*args, **kwargs)
        
        # Extract process ID if available
        if driver and hasattr(driver, 'service') and hasattr(driver.service, 'process'):
            chrome_pid = driver.service.process.pid
            manager.register_process(chrome_pid)
        
        # Extract temp profile path if available
        if driver and hasattr(driver, 'capabilities'):
            user_data_dir = driver.capabilities.get('chrome', {}).get('userDataDir')
            if user_data_dir:
                temp_profile = Path(user_data_dir)
                manager.register_profile(temp_profile)
        
        logger.info(f"Chrome WebDriver initialized (PID: {chrome_pid})")
        
        # Yield driver to caller
        yield driver
        
    except Exception as e:
        logger.error(f"Error in managed Chrome driver: {e}")
        raise
        
    finally:
        # ALWAYS executed, even on exception/return
        logger.info("Cleaning up Chrome WebDriver")
        
        # Step 1: Try graceful quit
        if driver:
            try:
                driver.quit()
                logger.info("Chrome WebDriver quit gracefully")
            except Exception as e:
                logger.warning(f"driver.quit() failed: {e}")
        
        # Step 2: Force kill process if it's still running
        if chrome_pid:
            manager.kill_process(chrome_pid)
        
        # Step 3: Clean up temp profile
        if temp_profile and temp_profile.exists():
            manager.cleanup_profile(temp_profile)
        
        logger.info("Chrome WebDriver cleanup complete")


def force_cleanup_chrome_processes():
    """
    Emergency cleanup function to kill all Chrome processes.
    Use this if you suspect leaked processes.
    """
    if not PSUTIL_AVAILABLE:
        logger.warning("psutil not available - cannot force cleanup")
        return 0
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                proc.terminate()
                proc.wait(timeout=5)
                killed_count += 1
                logger.info(f"Force killed Chrome process: PID {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass
        except Exception as e:
            logger.error(f"Error killing Chrome process: {e}")
    
    logger.info(f"Force cleanup complete: killed {killed_count} Chrome processes")
    return killed_count


def get_chrome_process_count() -> int:
    """
    Count running Chrome processes.
    Useful for monitoring memory leaks.
    """
    if not PSUTIL_AVAILABLE:
        return -1
    
    count = 0
    for proc in psutil.process_iter(['name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return count


# Diagnostic function
def diagnose_chrome_leaks():
    """
    Print diagnostic information about Chrome processes.
    Use for debugging memory issues.
    """
    if not PSUTIL_AVAILABLE:
        print("psutil not available - install with: pip install psutil")
        return
    
    print("\n" + "="*60)
    print("CHROME PROCESS DIAGNOSTIC")
    print("="*60)
    
    chrome_procs = []
    total_memory_mb = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
        try:
            if 'chrome' in proc.info['name'].lower():
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                total_memory_mb += memory_mb
                chrome_procs.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory_mb': memory_mb,
                    'create_time': proc.info['create_time']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if chrome_procs:
        print(f"\nFound {len(chrome_procs)} Chrome processes")
        print(f"Total Memory Usage: {total_memory_mb:.1f} MB")
        print(f"\nProcess Details:")
        print("-"*60)
        for proc in sorted(chrome_procs, key=lambda x: x['memory_mb'], reverse=True):
            print(f"PID {proc['pid']}: {proc['name']} - {proc['memory_mb']:.1f} MB")
    else:
        print("No Chrome processes found")
    
    print("="*60 + "\n")
    
    return len(chrome_procs), total_memory_mb





