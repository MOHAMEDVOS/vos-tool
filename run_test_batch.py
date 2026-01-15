#!/usr/bin/env python3
import time, sys
sys.path.append('.')
from processing.batch_engine import batch_analyze_folder_fast, get_batch_processor

folder = r'C:\Users\vos\Desktop\save v.1\Recordings\Agent\Mohamed Abdo\All users-2026-01-11_001 resva'
p = get_batch_processor('Mohamed Abdo')
print('max_workers =', p.max_workers)

t0 = time.time()
df = batch_analyze_folder_fast(folder, show_all_results=True, use_async=False, username='Mohamed Abdo')
wall = round(time.time() - t0, 2)
print(f'wall = {wall}s, rows = {len(df)}')
if len(df) > 0:
    print(df[['Agent Name', 'Phone Number', 'Rebuttal Detection']].head())
else:
    print(df.head())
