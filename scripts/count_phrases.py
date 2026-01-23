
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.database import get_db_manager

def count():
    db = get_db_manager()
    res = db.execute_query("SELECT COUNT(*) as count FROM rebuttal_phrases", fetch=True)
    print(f"Total Phrases: {res[0]['count']}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    count()
