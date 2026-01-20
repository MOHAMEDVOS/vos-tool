
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Set the environment variable BEFORE importing/initializing
os.environ["ASSEMBLYAI_MAX_WORKERS"] = "2"

try:
    from processing.batch_engine import get_batch_processor, FORCED_MAX_WORKERS
    
    print(f"FORCED_MAX_WORKERS constant is: {FORCED_MAX_WORKERS}")
    print(f"Environment variable ASSEMBLYAI_MAX_WORKERS is: {os.environ['ASSEMBLYAI_MAX_WORKERS']}")
    
    # Get the processor
    # passing a unique username to ensure we get a fresh instance
    processor = get_batch_processor("test_user_concurrency")
    
    print(f"Processor max_workers: {processor.max_workers}")
    
    if processor.max_workers == 2:
        print("✅ SUCCESS: Processor respected the environment variable limit of 2.")
    else:
        print(f"❌ FAILURE: Processor ignored the limit. Got {processor.max_workers}, expected 2.")
        sys.exit(1)

except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)
