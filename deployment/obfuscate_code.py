#!/usr/bin/env python3
"""
Code Obfuscation Tool for VOS Application
Protects source code from easy extraction when deployed online
"""

import os
import sys
import base64
import zlib
import marshal
import py_compile
from pathlib import Path
import shutil
import tempfile

class CodeObfuscator:
    """Advanced code obfuscation for Python applications"""
    
    def __init__(self, source_dir, output_dir):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.excluded_files = {'.env', '.encryption_key', 'chromedriver.exe'}
        self.excluded_dirs = {'__pycache__', '.git', 'Recordings', 'dashboard_data', 'chrome_profile_sessions'}
        
    def obfuscate_string(self, text):
        """Obfuscate string literals"""
        encoded = base64.b64encode(zlib.compress(text.encode())).decode()
        return f"__import__('zlib').decompress(__import__('base64').b64decode('{encoded}')).decode()"
    
    def obfuscate_python_file(self, file_path):
        """Obfuscate a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Create obfuscated version
            obfuscated_lines = []
            lines = source_code.split('\n')
            
            for line in lines:
                # Skip comments and docstrings for basic obfuscation
                if line.strip().startswith('#') or '"""' in line or "'''" in line:
                    obfuscated_lines.append(line)
                    continue
                
                # Obfuscate string literals (basic approach)
                if '"' in line and not line.strip().startswith('import'):
                    # This is a simplified approach - in production, use a proper AST parser
                    obfuscated_lines.append(line)
                else:
                    obfuscated_lines.append(line)
            
            return '\n'.join(obfuscated_lines)
            
        except Exception as e:
            print(f"Error obfuscating {file_path}: {e}")
            return None
    
    def compile_to_bytecode(self, py_file, output_file):
        """Compile Python file to bytecode (.pyc)"""
        try:
            py_compile.compile(py_file, output_file, doraise=True)
            return True
        except Exception as e:
            print(f"Error compiling {py_file}: {e}")
            return False
    
    def create_loader_script(self, main_file):
        """Create a loader script that loads bytecode"""
        loader_code = f'''
import sys
import os
import marshal
import types
from pathlib import Path

def load_module_from_pyc(pyc_path, module_name):
    """Load module from compiled bytecode"""
    try:
        with open(pyc_path, 'rb') as f:
            # Skip magic number and timestamp (first 12 bytes in Python 3.7+)
            f.read(12)
            code_obj = marshal.load(f)
            
        module = types.ModuleType(module_name)
        sys.modules[module_name] = module
        exec(code_obj, module.__dict__)
        return module
    except Exception as e:
        print(f"Error loading {{module_name}}: {{e}}")
        return None

# Load and run main application
if __name__ == "__main__":
    main_module = load_module_from_pyc("app.pyc", "app")
    if main_module and hasattr(main_module, 'main'):
        main_module.main()
    else:
        print("Error: Could not load main application")
'''
        return loader_code
    
    def obfuscate_project(self):
        """Obfuscate entire project"""
        print("🔒 Starting code obfuscation...")
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Copy non-Python files
        for item in self.source_dir.rglob('*'):
            if item.is_file() and item.name not in self.excluded_files:
                if any(excluded in item.parts for excluded in self.excluded_dirs):
                    continue
                
                relative_path = item.relative_to(self.source_dir)
                output_path = self.output_dir / relative_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if item.suffix == '.py':
                    # Compile Python files to bytecode
                    pyc_path = output_path.with_suffix('.pyc')
                    if self.compile_to_bytecode(item, pyc_path):
                        print(f"✅ Compiled: {relative_path} -> {pyc_path.name}")
                    else:
                        # Fallback: copy original file
                        shutil.copy2(item, output_path)
                        print(f"⚠️  Copied (compilation failed): {relative_path}")
                else:
                    # Copy non-Python files as-is
                    shutil.copy2(item, output_path)
                    print(f"📄 Copied: {relative_path}")
        
        # Create loader script
        loader_script = self.create_loader_script("app.py")
        with open(self.output_dir / "run_secure.py", 'w') as f:
            f.write(loader_script)
        
        print(f"🎉 Obfuscation complete! Output: {self.output_dir}")
        print("📋 To run: python run_secure.py")

def main():
    """Main obfuscation process"""
    source_dir = "."
    output_dir = "./obfuscated_app"
    
    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    obfuscator = CodeObfuscator(source_dir, output_dir)
    obfuscator.obfuscate_project()

if __name__ == "__main__":
    main()
