"""
Automated script to remove JSON fallback code from dashboard_manager.py
This script systematically removes all remaining JSON fallback patterns.
"""

import re
import sys
from pathlib import Path

def remove_json_fallbacks(file_path):
    """Remove JSON fallback code patterns from the file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # Pattern 1: Remove "# Fallback to JSON" followed by "pass" and JSON code blocks
    # This pattern catches the common structure:
    #   except Exception as e:
    #       logger.error(...)
    #       # Fallback to JSON
    #       pass
    #   
    #   # Fallback to JSON
    #   [JSON file operations]
    
    # Count occurrences before
    fallback_comments = len(re.findall(r'#\s*Fallback to JSON', content))
    print(f"Found {fallback_comments} '# Fallback to JSON' comments")
    
    # Replace pattern: exception handler with fallback comment and pass
    pattern1 = re.compile(
        r'(\s+)(except\s+\w+\s+as\s+\w+:\s*\n'
        r'\s+logger\.\w+\([^)]+\)\s*\n'
        r'\s+#\s*Fallback to JSON.*?\n'
        r'\s+pass\s*\n)',
        re.MULTILINE
    )
    
    def replace_exception_handler(match):
        indent = match.group(1)
        changes_made.append(f"Replaced exception handler at position {match.start()}")
        return f'{indent}except Exception as e:\n{indent}    logger.error(f"Database operation failed: {{e}}")\n{indent}    raise\n'
    
    content = pattern1.sub(replace_exception_handler, content)
    
    # Pattern 2: Remove standalone "# Fallback to JSON" blocks with file operations
    # This removes blocks like:
    #   # Fallback to JSON
    #   if not self.sessions_file.exists():
    #       return None
    #   sessions = safe_json_read(...)
    #   ...
    
    # We'll use a more conservative approach: just remove the comment and let manual cleanup handle complex blocks
    # For now, replace "# Fallback to JSON\n        pass" with "raise"
    
    pattern2 = re.compile(
        r'(\s+)#\s*Fallback to JSON.*?\n\s+pass\s*\n',
        re.MULTILINE
    )
    
    content = pattern2.sub(r'\1raise  # Database required\n', content)
    
    # Save if changes were made
    if content != original_content:
        # Create backup
        backup_path = file_path.with_suffix('.py.backup_phase7')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"Created backup: {backup_path}")
        
        # Write modified content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Count after
        fallback_comments_after = len(re.findall(r'#\s*Fallback to JSON', content))
        print(f"Removed {fallback_comments - fallback_comments_after} fallback comments")
        print(f"Remaining: {fallback_comments_after}")
        
        return True, changes_made
    else:
        print("No changes needed")
        return False, []

def main():
    file_path = Path("lib/dashboard_manager.py")
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return 1
    
    print(f"Processing {file_path}...")
    changed, changes = remove_json_fallbacks(file_path)
    
    if changed:
        print(f"\n✅ Successfully modified {file_path}")
        print(f"Made {len(changes)} changes")
        print("\nIMPORTANT: Review the changes and test thoroughly!")
        print("Backup saved as: lib/dashboard_manager.py.backup_phase7")
    else:
        print(f"\n✅ No changes needed for {file_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
