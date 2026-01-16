
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

from lib.dashboard_manager import user_manager

print("UserManager methods:")
for method in dir(user_manager):
    if not method.startswith("__"):
        print(f"- {method}")
