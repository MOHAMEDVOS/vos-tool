
import os, sys, json
sys.path.insert(0, os.getcwd())
from lib.database import get_db_manager
import datetime as dt

db = get_db_manager()

def fix_table(table_name):
    print(f"Fixing {table_name} timestamps...")
    try:
        # Check if metadata column exists
        cols = db.execute_query(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}'", fetch=True)
        col_names = [c['column_name'] for c in cols]
        if 'metadata' not in col_names:
            print(f"Column 'metadata' not found in {table_name}. Skipping.")
            return

        results = db.execute_query(f"SELECT id, metadata, created_at FROM {table_name}", fetch=True)
        updated = 0
        for row in results:
            meta = row.get('metadata')
            if not meta: continue
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except: continue
            
            # Try both 'timestamp' and 'Timestamp' in metadata
            ts_str = meta.get('timestamp') or meta.get('Timestamp')
            if not ts_str or not isinstance(ts_str, str): continue
            
            ts_str = ts_str.strip()
            new_ts = None
            
            # Try full format: Jan 9, 7:28PM or Jan 9, 7_28PM
            try:
                clean_ts = ts_str.replace('_', ':')
                # Some formats might be "Jan 9, 7:28PM" (missing year)
                # strptime defaults to 1900 if year is missing
                timestamp_dt = dt.datetime.strptime(clean_ts, '%b %d, %I:%M%p')
                # Use year from created_at
                year = row.get('created_at').year if row.get('created_at') else dt.datetime.now().year
                timestamp_dt = timestamp_dt.replace(year=year)
                new_ts = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Try time-only: 7:28PM or 7_28PM
                try:
                    clean_time = ts_str.replace('_', ':').strip()
                    if ' AM' not in clean_time and ' PM' not in clean_time:
                        clean_time = clean_time.replace('AM', ' AM').replace('PM', ' PM')
                    time_dt = dt.datetime.strptime(clean_time, '%I:%M %p')
                    created_date = row.get('created_at').date() if row.get('created_at') else dt.datetime.now().date()
                    new_ts = dt.datetime.combine(created_date, time_dt.time()).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
            
            if new_ts:
                db.execute_query(f"UPDATE {table_name} SET timestamp = %s WHERE id = %s", (new_ts, row['id']), fetch=False)
                updated += 1
        
        print(f"Fixed {updated} rows in {table_name}")
    except Exception as e:
        print(f"Error fixing {table_name}: {e}")

fix_table('agent_audit_results')
fix_table('lite_audit_results')
