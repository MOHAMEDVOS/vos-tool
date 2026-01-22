import sys
import os
import shutil
import platform
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Diagnostic")

def check_command(cmd, name, tip):
    """Check if a system command is available."""
    path = shutil.which(cmd)
    if path:
        logger.info(f"✅ {name} found: {path}")
        return True
    else:
        logger.error(f"❌ {name} NOT found.")
        logger.error(f"   💡 FIX: {tip}")
        return False

def check_python_dependencies():
    """Check for critical Python packages."""
    dependencies = ["playwright", "torch", "sentence_transformers", "pydub", "assemblyai"]
    missing = []
    
    for dep in dependencies:
        try:
            __import__(dep)
            logger.info(f"✅ Python package '{dep}' is installed.")
        except ImportError:
            logger.error(f"❌ Python package '{dep}' is MISSING.")
            missing.append(dep)
            
    if missing:
        logger.error(f"   💡 FIX: pip install {' '.join(missing)}")
        return False
    return True

def check_model_loading():
    """Attempt to load the critical model that might cause OOM."""
    try:
        logger.info("⚡ Attempting to load 'all-mpnet-base-v2' (this might crash if RAM is low)...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        logger.info("✅ Model loaded successfully! (RAM is likely sufficient locally)")
        return True
    except Exception as e:
        logger.error(f"❌ CRASHED loading model: {e}")
        return False
    except ImportError:
         logger.error("❌ skipped model check due to missing libraries")
         return False

def check_playwright_browsers():
    """Check if playwright browsers are installed."""
    try:
        # Dry-run playwright install check
        # This is a heuristic; running 'playwright install' is safer
        logger.info("🔍 Checking Playwright browsers...")
        # We'll just suggest the command regardless, but try to see if it runs
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                p.chromium.launch(headless=True)
                logger.info("✅ Playwright Chromium launched successfully.")
            except Exception as e:
                logger.error(f"❌ Playwright Chromium launch FAILED: {e}")
                logger.error("   💡 FIX: Run 'playwright install'")
                return False
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"❌ Playwright check failed: {e}")
        return False
    return True

def run_diagnostics():
    logger.info("=== STARTING DIAGNOSTICS ===")
    
    # 1. System Info
    logger.info(f"OS: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    
    # 2. Check FFmpeg (Critical for Audio)
    ffmpeg_ok = check_command("ffmpeg", "FFmpeg", "Download from gyan.dev (Windows) or 'apt install ffmpeg' (Linux/Docker)")
    
    # 3. Check Python Deps
    deps_ok = check_python_dependencies()
    
    # 4. Check Playwright Browsers
    playwright_ok = check_playwright_browsers()
    
    # 5. Check Model Loading (RAM/Crash Test)
    model_ok = check_model_loading()
    
    logger.info("\n=== SUMMARY ===")
    if ffmpeg_ok and deps_ok and playwright_ok and model_ok:
        logger.info("✅ All checks PASSED. The local environment seems healthy.")
        logger.info("If it still crashes, check the specific file processing log.")
    else:
        logger.error("❌ Issues FOUND. Please apply the fixes above.")

if __name__ == "__main__":
    run_diagnostics()
