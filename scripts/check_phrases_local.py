
import sys
project_root = r"c:\Users\vos\Desktop\save v.1"
sys.path.append(project_root)
from analyzer.rebuttal_detection import KeywordRepository
repo = KeywordRepository()
all_phrases = repo.get_all_phrases()
total = sum(len(p) for p in all_phrases.values())
print(f"TOTAL_PHRASES_COUNT:{total}")
for cat, phrases in all_phrases.items():
    print(f"Category: {cat}, Count: {len(phrases)}")
