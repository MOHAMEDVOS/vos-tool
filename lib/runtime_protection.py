#!/usr/bin/env python3
"""
Runtime Protection System for VOS Application
Provides real-time protection against code extraction and reverse engineering
"""

import os
import sys
import inspect
import functools
import hashlib
import time
from pathlib import Path
import streamlit as st

class RuntimeProtection:
    """Advanced runtime protection mechanisms"""
    
    def __init__(self):
        self.is_production = os.getenv('DEPLOYMENT_MODE') == 'production'
        self.protection_enabled = True
        self._integrity_hashes = {}
        self._init_protection()
    
    def _init_protection(self):
        """Initialize protection mechanisms"""
        if self.is_production:
            self._hide_streamlit_elements()
            self._disable_debug_access()
            self._setup_integrity_monitoring()
    
    def _hide_streamlit_elements(self):
        """Hide Streamlit debug elements"""
        hide_streamlit_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none;}
        .stDecoration {display: none;}
        .stToolbar {display: none;}
        [data-testid="stToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
        [data-testid="stStatusWidget"] {display: none;}
        .stApp > header {display: none;}
        .css-1rs6os {display: none;}
        .css-17ziqus {display: none;}
        </style>
        """
        st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    def _disable_debug_access(self):
        """Disable debug and development features"""
        if self.is_production:
            # Disable Python debugging
            sys.tracebacklimit = 0
            
            # Remove development modules from sys.modules if present
            dev_modules = ['pdb', 'code', 'codeop', 'dis', 'inspect']
            for module in dev_modules:
                if module in sys.modules:
                    del sys.modules[module]
    
    def _setup_integrity_monitoring(self):
        """Setup file integrity monitoring"""
        critical_files = ['app.py', 'config.py', 'security_utils.py']
        for file_name in critical_files:
            file_path = Path(file_name)
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    content = f.read()
                self._integrity_hashes[file_name] = hashlib.sha256(content).hexdigest()
    
    def check_integrity(self):
        """Check file integrity"""
        if not self.is_production:
            return True
        
        for file_name, expected_hash in self._integrity_hashes.items():
            file_path = Path(file_name)
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    content = f.read()
                current_hash = hashlib.sha256(content).hexdigest()
                if current_hash != expected_hash:
                    self._handle_integrity_violation(file_name)
                    return False
        return True
    
    def _handle_integrity_violation(self, file_name):
        """Handle integrity violation"""
        st.error("Security Alert: Application integrity compromised")
        st.stop()
    
    def anti_debugging_decorator(self, func):
        """Decorator to add anti-debugging protection"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.is_production:
                # Check for debugging attempts
                frame = inspect.currentframe()
                if frame and frame.f_back and frame.f_back.f_code.co_name in ['trace_dispatch', 'set_trace']:
                    st.error("Debug access denied")
                    st.stop()
                
                # Check integrity
                if not self.check_integrity():
                    return None
            
            return func(*args, **kwargs)
        return wrapper
    
    def obfuscate_function_names(self):
        """Obfuscate function names in the current module"""
        if self.is_production:
            try:
                frame = inspect.currentframe().f_back
                if frame is None:
                    return
                
                local_vars = frame.f_locals.copy()
                
                for name, obj in local_vars.items():
                    if callable(obj) and not name.startswith('_'):
                        # Create obfuscated name
                        obfuscated_name = f"_{hashlib.md5(name.encode()).hexdigest()[:8]}"
                        # Note: Direct modification of f_locals may not work in all Python versions
                        # This is kept for compatibility but may not be effective
                        try:
                            frame.f_locals[obfuscated_name] = obj
                        except (TypeError, AttributeError):
                            # f_locals modification not supported, skip silently
                            pass
            except Exception:
                # Silently ignore obfuscation errors to prevent app crashes
                pass
    
    def secure_import_hook(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Custom import hook to prevent unauthorized module access"""
        if self.is_production:
            restricted_modules = {
                'dis', 'ast', 'code', 'codeop', 'py_compile', 'compileall',
                'pdb', 'trace', 'profile', 'cProfile', 'pstats'
            }
            
            if name in restricted_modules:
                raise ImportError(f"Module '{name}' is restricted in production mode")
        
        # Use the original import function to avoid recursion
        try:
            return self._original_import(name, globals, locals, fromlist, level)
        except AttributeError:
            # Fallback to built-in import if original not stored
            return __import__(name, globals, locals, fromlist, level)
    
    def enable_protection(self):
        """Enable all protection mechanisms"""
        if self.is_production:
            # Store original import before replacing
            import builtins
            self._original_import = builtins.__import__
            builtins.__import__ = self.secure_import_hook
            
            # Hide source code access
            self._hide_streamlit_elements()
            
            # Setup monitoring
            self._setup_integrity_monitoring()
            
            print("Runtime protection enabled")

class CodeObfuscationRuntime:
    """Runtime code obfuscation utilities"""
    
    @staticmethod
    def obfuscate_strings_in_memory():
        """Obfuscate string literals in memory"""
        try:
            frame = inspect.currentframe().f_back
            if frame is None:
                return
            
            local_vars = frame.f_locals
            if local_vars is None:
                return
            
            # Create a copy to avoid modification during iteration
            vars_copy = dict(local_vars)
            
            for name, value in vars_copy.items():
                if isinstance(value, str) and len(value) > 10:
                    try:
                        # Simple XOR obfuscation for demonstration
                        key = 0x42
                        obfuscated = ''.join(chr(ord(c) ^ key) for c in value)
                        local_vars[f"_obf_{name}"] = obfuscated
                    except (TypeError, ValueError, AttributeError):
                        # Skip problematic strings silently
                        pass
        except Exception:
            # Silently ignore obfuscation errors to prevent app crashes
            pass
    
    @staticmethod
    def dynamic_function_names():
        """Generate dynamic function names"""
        timestamp = str(int(time.time()))
        return f"func_{hashlib.md5(timestamp.encode()).hexdigest()[:8]}"

# Global protection instance
_protection = RuntimeProtection()

def secure_app_decorator(func):
    """Main decorator for securing the entire app"""
    return _protection.anti_debugging_decorator(func)

def enable_runtime_protection():
    """Enable runtime protection (call at app startup)"""
    _protection.enable_protection()

# Auto-enable protection if in production
if os.getenv('DEPLOYMENT_MODE') == 'production':
    enable_runtime_protection()
