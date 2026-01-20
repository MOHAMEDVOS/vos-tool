
import os
import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Set concurrency for local test (simulating powerful machine)
os.environ["ASSEMBLYAI_MAX_WORKERS"] = "5"

from processing.batch_engine import batch_analyze_folder_fast

def run_benchmark():
    target_folder = r"C:\Users\vos\Desktop\save v.1\Recordings\Agent\Mohamed Abdo\All users-2026-01-16_004 resva"
    
    print(f"🚀 Starting Benchmark on: {target_folder}")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        # Run Heavy Audit (fast mode = async)
        # We use a dummy username to avoid polluting main user stats, or 'benchmark'
        results_df = batch_analyze_folder_fast(
            folder_path=target_folder,
            show_all_results=True,
            use_async=True,
            username="benchmark_test"
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "="*50)
        print(f"✅ Benchmark Complete")
        print(f"Total Time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"Total Files Processed: {len(results_df)}")
        if len(results_df) > 0:
            print(f"Average Time per File: {duration/len(results_df):.1f} seconds")
        print("="*50)
        
        # Verify no timeouts occurred
        timeouts = results_df[results_df['Status'].astype(str).str.contains("Timeout", case=False, na=False)]
        if not timeouts.empty:
            print(f"⚠️ WARNING: {len(timeouts)} files timed out!")
        else:
            print("🎉 Zero Timeouts detected.")

    except Exception as e:
        print(f"❌ Benchmark Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_benchmark()
