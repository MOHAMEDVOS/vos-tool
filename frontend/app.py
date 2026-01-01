"""
Frontend Streamlit application entry point.
This is a wrapper that imports from the root app.py for backward compatibility.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the main app
from app import main

if __name__ == "__main__":
    main()

