
import asyncio
import time
import os
import logging
import sys
from unittest.mock import patch, MagicMock

# Mock database before any imports that might use it
mock_db = MagicMock()
mock_db.execute_query.return_value = []
mock_db.test_connection.return_value = True

# Patch get_db_manager global BEFORE importing other modules
with patch('lib.database.get_db_manager', return_value=None):
    from processing.batch_engine import BatchProcessor
    from audio_pipeline.audio_processor import AudioProcessor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_benchmark():
    # Configuration
    folder_path = r"C:\Users\vos\Desktop\save v.1\Recordings\Agent\Mohamed Abdo\All users-2026-01-16_004 resva"
    user_api_key = os.getenv("ASSEMBLYAI_API_KEY") # Pass directly to avoid DB lookup
    username = "Mohamed Abdo"
    
    if not user_api_key:
        print("ERROR: ASSEMBLYAI_API_KEY environment variable not set")
        return

    print(f"Starting DB-LESS benchmark for 50 files in: {folder_path}")
    
    # Initialize processor with 5 workers (limit for free accounts)
    processor = BatchProcessor(max_workers=5)
    
    # Get files (limit to exactly 50 for consistent benchmark)
    all_files = processor.find_audio_files(folder_path)
    batch_files = all_files[:50]
    
    if len(batch_files) < 50:
        print(f"WARNING: Only found {len(batch_files)} files, benchmark might be less accurate.")
    
    start_time = time.time()
    
    # Mock database manager inside modules that might have already imported it
    with patch('lib.dashboard_manager.user_manager.get_user_assemblyai_key', return_value=user_api_key), \
         patch('lib.app_settings_manager.get_app_settings', return_value=MagicMock()), \
         patch('lib.database.get_db_manager', return_value=None):
        
        results = await processor.process_folder_async(
            folder_path=folder_path,
            username=username,
            user_api_key=user_api_key
        )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Analyze results
    total_files = len(results)
    completed_files = [r for r in results if r.get('Status') != 'Error']
    success_rate = (len(completed_files) / total_files) * 100 if total_files > 0 else 0
    avg_time = duration / total_files if total_files > 0 else 0
    
    # Write to results file
    with open("benchmark_results_final.txt", "w") as f:
        f.write("=" * 50 + "\n")
        f.write("BENCHMARK RESULTS (DB-LESS)\n")
        f.write("=" * 50 + "\n")
        f.write(f"Total Files: {total_files}\n")
        f.write(f"Successfully Processed: {len(completed_files)}\n")
        f.write(f"Success Rate: {success_rate:.1f}%\n")
        f.write(f"Total Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)\n")
        f.write(f"Average Time per File: {avg_time:.2f} seconds\n")
        f.write("=" * 50 + "\n")

    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS (DB-LESS)")
    print("=" * 50)
    print(f"Total Files: {total_files}")
    print(f"Successfully Processed: {len(completed_files)}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Total Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"Average Time per File: {avg_time:.2f} seconds")
    print("=" * 50)
    print("Summary written to benchmark_results_final.txt")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_benchmark())
