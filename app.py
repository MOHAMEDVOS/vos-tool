import sys
import os
import subprocess
import time
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
# Import from frontend.app_ai (backend/frontend separation architecture)
from frontend.app_ai.css.custom_styles import apply_custom_styles, apply_login_styles, render_header_bar
from pathlib import Path
import importlib

# Add current directory to Python path to ensure all modules can be imported
sys.path.insert(0, str(Path(__file__).parent))

def reload_modules():
    """Reload all custom modules to pick up code changes without restarting"""
    modules_to_reload = [
        'config',
        'lib.dashboard_manager',
        'lib.ai_campaign_report',
        'lib.quota_manager',
        'tools.quota_redistribution',
        'audio_pipeline.detections',
        'analyzer.rebuttal_detection',
        'lib.agent_only_detector',
        'lib.optimized_pipeline',
        'lib.phrase_learning',
        'audio_pipeline.audio_processor'
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
                print(f"Reloaded: {module_name}")
            except Exception as e:
                print(f"Failed to reload {module_name}: {e}")
    
    # Clear Streamlit cache
    st.cache_data.clear()
    st.cache_resource.clear()
    print("Streamlit cache cleared")

import io
import tempfile
from datetime import date, datetime, timedelta
from typing import List
import logging
import threading
import time
import uuid
import warnings
import math

# Suppress Streamlit file watcher errors on Windows (different drive paths)
warnings.filterwarnings('ignore', message="Paths don't have the same drive")

# Configure logging for CMD output - Essential info only
logging.basicConfig(
    level=logging.WARNING,  # Reduce verbosity
    format='%(message)s',  # Simple format without timestamps
    handlers=[
        logging.StreamHandler(),  # This ensures logs appear in CMD
    ]
)

import pandas as pd
import streamlit as st

# Runtime Protection (must be imported early)
try:
    from lib.runtime_protection import secure_app_decorator, enable_runtime_protection
    PROTECTION_AVAILABLE = True
except ImportError:
    PROTECTION_AVAILABLE = False
    def secure_app_decorator(func):
        return func

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def generate_csv_data(df: pd.DataFrame, filename_prefix: str) -> tuple[bytes, str]:
    """
    Generate and cache CSV data to prevent hash changes in download buttons.

    Args:
        df: DataFrame to convert to CSV
        filename_prefix: Prefix for the filename

    Returns:
        tuple: (csv_bytes, filename)
    """
    if df.empty:
        return b"", f"{filename_prefix}_empty.csv"

    csv_data = df.to_csv(index=False).encode("utf-8")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.csv"

    return csv_data, filename

def generate_timestamped_folder_name(base_name: str = "All users") -> str:
    """
    Generate a unique folder name with timestamp to avoid duplicates.

    Args:
        base_name: Base name for the folder (default: "All users")

    Returns:
        Folder name with timestamp: "All users-2025-10-26_14-30-45"
    """
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{base_name}-{timestamp}"

from processing import batch_analyze_folder, batch_analyze_folder_fast, batch_analyze_folder_lite
from ui.batch import (
    show_batch_processing_section as ui_show_batch_processing_section,
    process_batch_files as ui_process_batch_files,
    show_batch_results_preview as ui_show_batch_results_preview,
    show_final_batch_results as ui_show_final_batch_results,
)
from config import READYMODE_URL, USERNAME, get_user_readymode_credentials, get_user_daily_limit, app_settings as runtime_app_settings
from lib.dashboard_manager import dashboard_manager, session_manager, user_manager
# Import from frontend.app_ai (backend/frontend separation architecture)
from frontend.app_ai.ui.components import (
    show_campaign_audit_dashboard,
    show_lite_audit_dashboard,
    show_actions_section,
)
from frontend.app_ai.ui.phrases import (
    show_phrase_management_section,
)
from frontend.app_ai.ui.audit import (
    show_audit_section,
)
from frontend.app_ai.ui.flagged import (
    show_flagged_calls_section,
)
from frontend.app_ai.auth.authentication import (
    check_authentication,
    is_user_authenticated,
    get_current_username,
    get_current_user_role,
    logout_current_user,
    logout_user_by_name,
)
import os

# Import API client for backend communication
try:
    import sys
    from pathlib import Path
    # Add frontend directory to path
    frontend_path = Path(__file__).parent / "frontend"
    if frontend_path.exists():
        sys.path.insert(0, str(Path(__file__).parent))
        from frontend.api_client import get_api_client
        API_CLIENT_AVAILABLE = True
    else:
        API_CLIENT_AVAILABLE = False
        logger.warning("Frontend directory not found - using direct function calls")
except ImportError as e:
    API_CLIENT_AVAILABLE = False
    logger.warning(f"API client not available - using direct function calls: {e}")

# Audio player removed for simplified interface

# Try to import ReadyMode automation, disable if not available (e.g., on Streamlit Cloud)
try:
    # Check deployment environment
    import os
    deployment_mode = os.getenv('DEPLOYMENT_MODE', 'auto')
    force_readymode = os.getenv('FORCE_READYMODE', 'false').lower() == 'true'
    
    if deployment_mode == 'enterprise' or force_readymode:
        # Force enable ReadyMode for enterprise deployments or when explicitly requested
        is_streamlit_cloud = False
    else:
        # Auto-detect Streamlit Cloud
        is_streamlit_cloud = (
            os.getenv('STREAMLIT_SHARING_MODE') == 'true' or 
            'streamlit.app' in os.getenv('HOSTNAME', '') or
            '/mount/src/' in os.getcwd()
        )
    
    if is_streamlit_cloud and not force_readymode:
        READYMODE_AVAILABLE = False
        st.info("**Running on Streamlit Cloud** - For security reasons, automated call downloading is disabled. Please use the **Upload & Analyze** tab to process your MP3 files directly.")
    else:
        from automation.download_readymode_calls import download_all_call_recordings, extract_dialer_name_from_url, ReadyModeLoginError, ReadyModeNoCallsError
        READYMODE_AVAILABLE = True
        if force_readymode and is_streamlit_cloud:
            st.info("**ReadyMode Automation Enabled** - Full call downloading functionality is available despite cloud deployment.")
except (ImportError, Exception) as e:
    READYMODE_AVAILABLE = False
    st.warning(f"ReadyMode automation not available: {str(e)}")

# Set page configuration with favicon
# Use the new Gemini-generated logo as favicon
favicon_path = "favicon.png"
if os.path.exists(favicon_path):
    st.set_page_config(
        page_title="VOS",
        page_icon=favicon_path,
        layout="wide"
    )
else:
    # Fallback to emoji if logo not found
    st.set_page_config(
        page_title="VOS",
        page_icon="🎤",
        layout="wide"
    )

# Helper function to extract dialer name from ReadyMode URL
def check_system_resources():
    """Check system resources and return detailed usage metrics."""
    try:
        import psutil

        # Get CPU usage percentage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Return detailed metrics
        return {
            "cpu": cpu_percent,
            "memory": memory_percent,
            "disk": disk_percent,
            "healthy": cpu_percent < 85 and memory_percent < 85 and disk_percent < 85
        }

    except Exception as e:
        logger.warning(f"Resource check failed: {e}")
        # Return default values if check fails
        return {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
            "healthy": True
        }

def load_custom_css():
    apply_custom_styles()
def show_login_page():
    """Display the professional login page."""
    apply_login_styles()
    
    # Login Header - Same as inside the app with wave animations
    st.markdown("""
    <div class="login-header-animated" style="text-align: center; padding: 1.25rem 1rem; margin-bottom: 1.25rem; background: rgba(2, 4, 18, 0.85); border-radius: 20px; border: 2px solid rgba(20, 20, 20, 0.8); position: relative; overflow: hidden; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), 0 0 40px rgba(37, 99, 235, 0.05);">
        <div class="wave-overlay-1"></div>
        <div class="wave-overlay-2"></div>
        <h1 class="vos-title login-title-animated">VOS</h1>
        <h2 class="vos-subtitle login-subtitle-animated">Voice Observation System</h2>
        <p class="vos-tagline login-tagline-animated">AI That Listens, Learns, and Elevates Quality</p>
    </div>
    """, unsafe_allow_html=True)

    # Add the wave animation CSS with classes
    st.markdown("""
    <style>
    .wave-overlay-1, .wave-overlay-2 {
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        animation: wave-slide 4s ease-in-out infinite;
        pointer-events: none;
        mix-blend-mode: screen;
        z-index: 1;
    }

    .wave-overlay-1 {
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(37, 99, 235, 0.15) 20%, 
            rgba(37, 99, 235, 0.35) 50%, 
            rgba(37, 99, 235, 0.15) 80%, 
            transparent 100%);
    }

    .wave-overlay-2 {
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(96, 165, 250, 0.12) 25%, 
            rgba(96, 165, 250, 0.28) 50%, 
            rgba(96, 165, 250, 0.12) 75%, 
            transparent 100%);
        animation-delay: 1s;
    }
    
    /* Ensure text stays above waves */
    .login-header-animated h1,
    .login-header-animated h2,
    .login-header-animated p {
        position: relative;
        z-index: 2;
    }

    /* Wave layer spanning the main app header (behind text and user pill) */
    .header-wave-container {
        position: fixed;
        top: 0;
        left: 260px; /* align with content area to the right of sidebar */
        right: 0;
        height: 64px;
        overflow: hidden;
        z-index: 1200; /* above header background (980), below header content (1000) */
    }

    .top-header-vos {
        position: fixed;
        top: 8px;
        left: calc(50% + 130px);
        transform: translateX(-50%);
        padding: 0.25rem 0.9rem;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(96, 165, 250, 0.35);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-width: 260px;
        overflow: hidden;
        z-index: 1000;
    }

    .top-header-vos .vos-title {
        font-size: 1.05rem;
        letter-spacing: 0.18em;
    }

    .top-header-vos .vos-subtitle {
        font-size: 0.75rem;
        letter-spacing: 0.14em;
        margin-top: 0.15rem;
    }

    .vos-title {
        font-size: 2.8rem;
        font-weight: bold;
        color: #e5e7eb;
        margin: 0;
        letter-spacing: 0.2em;
        animation: text-glow 2s ease-in-out infinite alternate;
    }

    .vos-subtitle {
        font-size: 1.5rem;
        color: #e2e8f0;
        margin: 0.5rem 0 0 0;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        animation: text-wave 3s ease-in-out infinite;
    }

    .vos-tagline {
        font-size: 1.1rem;
        color: #94a3b8;
        margin: 0.5rem 0 0 0;
        font-style: italic;
        animation: fade-in 2s ease-in-out infinite alternate;
    }

    .vos-divider {
        width: 100px;
        border: none;
        height: 3px;
        background: linear-gradient(90deg, #e5e7eb, #9ca3af);
        margin: 1.5rem auto 0;
        animation: gradient-shift 4s ease-in-out infinite;
    }

    @keyframes wave-slide {
        0% { left: -100%; }
        100% { left: 100%; }
    }

    @keyframes text-glow {
        0% { text-shadow: 0 0 5px rgba(37, 99, 235, 0.1); }
        100% { text-shadow: 0 0 20px rgba(37, 99, 235, 0.15), 0 0 30px rgba(37, 99, 235, 0.08); }
    }

    @keyframes text-wave {
        0%, 100% { transform: translateX(0px); }
        25% { transform: translateX(-2px); }
        75% { transform: translateX(2px); }
    }

    @keyframes fade-in {
        0% { opacity: 0.7; }
        100% { opacity: 1; }
    }

    @keyframes gradient-shift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }
    
    /* Enhanced login button - Glassy Bold Style (High Specificity) */
    .stForm button[data-testid*="stBaseButton"],
    .stForm button[kind="secondaryFormSubmit"],
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"],
    .stForm .stButton > button {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        color: #ffffff !important;
        border: 2px solid rgba(20, 20, 20, 0.9) !important;
        border-radius: 18px !important;
        padding: 1rem 2.5rem !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        width: 100% !important;
        cursor: pointer !important;
        text-transform: uppercase !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.05) !important;
        backdrop-filter: blur(16px) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    .stForm button[data-testid*="stBaseButton"] p,
    .stForm button[kind="secondaryFormSubmit"] p,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"] p,
    .stForm .stButton > button p {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        text-shadow: 0 0 10px rgba(37, 99, 235, 0.08) !important;
        margin: 0 !important;
    }
    
    .stForm button[data-testid*="stBaseButton"]:hover,
    .stForm button[kind="secondaryFormSubmit"]:hover,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"]:hover,
    .stForm .stButton > button:hover {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.12), 0 0 80px rgba(37, 99, 235, 0.08) !important;
    }
    
    .stForm button[data-testid*="stBaseButton"]:hover p,
    .stForm button[kind="secondaryFormSubmit"]:hover p,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"]:hover p,
    .stForm .stButton > button:hover p {
        text-shadow: 0 0 15px rgba(37, 99, 235, 0.12) !important;
    }
    
    .stForm button[data-testid*="stBaseButton"]:active,
    .stForm button[kind="secondaryFormSubmit"]:active,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"]:active,
    .stForm .stButton > button:active {
        transform: translateY(0) scale(0.98) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.05) !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Remove gap above VOS header card - target Streamlit's main container */
    [data-testid="stMainBlockContainer"],
    div[class*="st-emotion-cache"][data-testid="stMainBlockContainer"],
    .block-container[data-testid="stMainBlockContainer"] {
        padding-top: 0 !important;
        padding: 0 1rem 10rem !important;
    }
    
    /* More specific targeting for login page */
    .main .block-container {
        padding-top: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login card
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Create login form
        with st.form("login_form"):
            st.markdown('<div class="login-card-title">Authentication Required</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-card-description">Please enter your credentials to access the Auditing platform</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="login-input-group login-input-1">', unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter your username", key="login_username")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="login-input-group login-input-2">', unsafe_allow_html=True)
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="login-button-wrapper">', unsafe_allow_html=True)
            login_button = st.form_submit_button("LOGIN", width='stretch')
            st.markdown('</div>', unsafe_allow_html=True)
            
            if login_button:
                # Try to use API client first, fallback to direct calls
                if API_CLIENT_AVAILABLE:
                    try:
                        api_client = get_api_client()
                        # Login via API
                        result = api_client.login(username, password)
                        
                        # API login successful - session state already set by api_client.login()
                        st.success(f"Welcome, {username}! Loading platform...")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        error_msg = str(e)
                        if "401" in error_msg or "Invalid" in error_msg or "Unauthorized" in error_msg:
                            st.error("Invalid credentials. Please verify your username and password.")
                        else:
                            st.error(f"Login failed: {error_msg}")
                            logger.error(f"API login error: {e}", exc_info=True)
                        # Clear force login flag on failed authentication
                        if 'force_login_attempted' in st.session_state:
                            del st.session_state.force_login_attempted
                else:
                    # Fallback to direct function calls (legacy mode)
                    if user_manager.verify_user_password(username, password):
                        # Check for existing active session
                        existing_session_id = session_manager.check_existing_session(username)

                        if existing_session_id and not st.session_state.get('force_login_attempted', False):
                            # First attempt with existing session - block and offer force login option
                            st.error("This account is already logged in elsewhere. Continuing will log out the other session.")
                            st.session_state.force_login_attempted = True
                            return

                        # Either no existing session, or user clicked authenticate again (force login)
                        import uuid
                        new_session_id = str(uuid.uuid4())

                        # Create new session (this will invalidate any existing session)
                        if session_manager.create_session(username, new_session_id):
                            # Clear ALL previous session state to ensure clean login
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            
                            # Set fresh authentication state
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.session_id = new_session_id

                            # Show success message and force immediate redirect
                            st.success(f"Welcome, {username}! Loading platform...")
                            
                            # Brief delay to show success message before redirect
                            time.sleep(0.5)
                            
                            # Force complete page refresh to clear login page shadow
                            st.rerun()
                        else:
                            st.error("Session creation failed. Please try again.")
                            # Clear force login flag on session creation failure
                            if 'force_login_attempted' in st.session_state:
                                del st.session_state.force_login_attempted
                    else:
                        st.error("Invalid credentials. Please verify your username and password.")
                        # Clear force login flag on failed authentication
                        if 'force_login_attempted' in st.session_state:
                            del st.session_state.force_login_attempted
    
    # Login Footer
    st.markdown("""
    <div class="login-footer login-footer-animated">
        VOS Enterprise Platform • Developed by <a href="https://t.me/Mohmed_abdo" target="_blank" style="color: #1f77b4; text-decoration: none; font-weight: bold;">Mohamed Abdo</a>
    </div>
    """, unsafe_allow_html=True)

def show_logout_button():
    """Display logout button in sidebar with modern styling."""
    with st.sidebar:
        st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
        if st.button("Logout", key="logout_btn"):
            # Invalidate current session and clear core auth keys
            logout_current_user(clear_auth_state=True)

            # Clear session-specific data
            clear_agent_audit_data()

            # Clear all remaining session state (UI, filters, etc.)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Developer refresh button
        st.markdown("---")
        st.markdown('<div class="dev-refresh-btn">', unsafe_allow_html=True)
        if st.button("Refresh Code", key="dev_refresh_btn", help="Reload modules without restarting"):
            reload_modules()
            st.success("Modules reloaded! Changes should be visible now.")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def show_migration_section():
    """Owner-only migration runner with status display."""
    import os
    import sys
    import subprocess
    import threading
    
    try:
        from lib.migration_lock import (
            is_application_read_only,
            get_migration_status,
        )
    except Exception as e:
        st.error(f"Migration tools not available: {e}")
        return

    st.markdown("""
    <div class="settings-card">
        <h4>Data Migration</h4>
        <p>Move existing JSON data to PostgreSQL. The app enters read-only mode during migration.</p>
    </div>
    """, unsafe_allow_html=True)

    status = get_migration_status() or {}
    is_running = is_application_read_only()
    progress = status.get("progress", {}) if isinstance(status, dict) else {}
    stage = progress.get("stage", "idle")
    pct = progress.get("progress", 0)
    started_at = status.get("started_at") if isinstance(status, dict) else None

    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Status:** {'Running' if is_running else status.get('status', 'idle').title() if isinstance(status, dict) else 'idle'}")
        st.write(f"**Stage:** {stage}")
        st.write(f"**Progress:** {pct}%")
        if started_at:
            st.write(f"**Started:** {started_at}")
    with col_b:
        if is_running and pct:
            st.progress(min(max(int(pct), 0), 100) / 100, text=f"{pct}% - {stage}")
        elif is_running:
            st.info("Migration in progress...")

    if is_running:
        st.warning("App is in read-only mode while migration runs.")
        if st.button("Refresh Status", key="refresh_migration_status"):
            st.rerun()
        return

    st.info("Run this once to move existing JSON data into PostgreSQL. New data already goes to PostgreSQL automatically.")

    # Check if migration is already running in background
    if 'migration_running' in st.session_state and st.session_state.get('migration_running'):
        st.info("Migration is running in the background. Please wait...")
        if st.button("Refresh Status", key="refresh_migration_background"):
            st.rerun()
        return
    
    # Check if migration just finished
    if 'migration_finished' in st.session_state and st.session_state.get('migration_finished'):
        if 'migration_output' in st.session_state and st.session_state.get('migration_output'):
            output = st.session_state['migration_output']
            success = st.session_state.get('migration_success', False)
            
            if success:
                st.success("Migration completed successfully!")
            else:
                st.error("Migration failed. See details below.")
            
            with st.expander("Migration Output", expanded=not success):
                st.code(output.strip() or "No output")
            
            if st.button("Clear Output", key="clear_migration_output"):
                del st.session_state['migration_output']
                del st.session_state['migration_success']
                del st.session_state['migration_finished']
                st.rerun()
        else:
            # Migration finished but no output yet, clear the finished flag
            del st.session_state['migration_finished']
            st.rerun()

    if st.button("Run Migration Now", type="primary", key="run_migration_now"):
        st.session_state['migration_running'] = True
        st.session_state['migration_output'] = ""
        st.session_state['migration_success'] = False
        st.session_state['migration_finished'] = False
        
        def run_migration():
            """Run migration in background thread."""
            try:
                # Set environment variables
                env = os.environ.copy()
                env['POSTGRES_HOST'] = os.getenv('POSTGRES_HOST', 'localhost')
                env['POSTGRES_PORT'] = os.getenv('POSTGRES_PORT', '5432')
                env['POSTGRES_DB'] = os.getenv('POSTGRES_DB', 'vos_tool')
                env['POSTGRES_USER'] = os.getenv('POSTGRES_USER', 'vos_user')
                env['POSTGRES_PASSWORD'] = os.getenv('POSTGRES_PASSWORD', '')
                
                result = subprocess.run(
                    [sys.executable, "scripts/migrate_all_data_to_postgres_complete.py"],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                    cwd=os.getcwd(),
                )
                output = (result.stdout or "") + "\n" + (result.stderr or "")
                # Store results in session state (this is safe from background thread)
                st.session_state['migration_output'] = output
                st.session_state['migration_success'] = (result.returncode == 0)
            except Exception as e:
                st.session_state['migration_output'] = f"Error: {e}"
                st.session_state['migration_success'] = False
            finally:
                st.session_state['migration_running'] = False
                st.session_state['migration_finished'] = True
        
        # Start migration in background thread
        thread = threading.Thread(target=run_migration, daemon=True)
        thread.start()
        
        st.info("Migration started in the background. The app will enter read-only mode. Please refresh to see progress.")
        st.rerun()

def show_settings_section():
    """System Settings – Real-time user sessions and resource monitoring."""
    import json
    import os
    import pandas as pd
    from pathlib import Path
    # from streamlit_autorefresh import st_autorefresh  # Removed - using manual refresh instead

    # Restrict access to Owner and Admin roles only
    current_username = st.session_state.get("username")
    if not user_manager.has_settings_access(current_username):
        st.error("Access Denied: This section is restricted to administrators only.")
        return
    
    # Get current user's role for permission checks
    current_user_role = get_current_user_role(user_manager) or user_manager.get_user_role(current_username)

    # Main tabs - Role-based access
    if current_user_role == user_manager.ROLE_OWNER:
        main_tabs = st.tabs(["User Overview", "User Management", "Dashboard Sharing", "Quota Control", "User Sessions", "System Health", "App Configuration"])
        user_overview_tab, user_mgmt_tab, dashboard_sharing_tab, quota_tab, sessions_tab, health_tab, config_tab = main_tabs
    else:  # Admin role
        main_tabs = st.tabs(["Overview", "Quota Management", "Create User", "Manage Users"])
        user_overview_tab, quota_tab, create_user_tab, manage_users_tab = main_tabs

    # -------------------- TAB 1: USER OVERVIEW --------------------
    with user_overview_tab:
        # Modern header with clean styling

        # Get users based on role permissions
        all_users = user_manager.get_all_users()
        
        # Filter users based on current user's role
        if current_user_role == user_manager.ROLE_OWNER:
            # Owner sees all users
            visible_users = all_users
            table_title = "All Registered Users"
        elif current_user_role == user_manager.ROLE_ADMIN:
            # Admin sees only users they created + themselves
            try:
                from lib.quota_manager import quota_manager
                created_users = quota_manager.get_admin_created_users(current_username)
                visible_users = {username: config for username, config in all_users.items() 
                               if username in created_users or username == current_username}
                table_title = f"Your Created Users ({len(created_users)} users)"
            except ImportError:
                # Fallback if quota system not available
                visible_users = {current_username: all_users[current_username]} if current_username in all_users else {}
                table_title = "Your Account"
        else:
            # Auditor sees only themselves (shouldn't reach here in settings)
            visible_users = {current_username: all_users[current_username]} if current_username in all_users else {}
            table_title = "Your Account"

        # Display users table
        st.markdown(f"#### {table_title}")

        user_management_data = []
        for username, config in visible_users.items():
            session_id = session_manager.check_existing_session(username)
            is_online = session_id is not None
            
            # Role badge styling
            role = config.get('role', 'Auditor')
            if role == 'Owner':
                role_display = "Owner"
                role_color = "#ffd700"
            elif role == 'Admin':
                role_display = "Admin"
                role_color = "#ff6b6b"
            else:
                role_display = "Auditor"
                role_color = "#4ecdc4"
            
            # Check daily limit display based on user type
            daily_limit_display = "UNLIMITED"
            if config.get("daily_limit", 0) < 999999:
                daily_limit_display = str(config.get("daily_limit", 0))
            else:
                # Check if user is Admin with quota pool
                if role == 'Admin':
                    try:
                        from lib.quota_manager import quota_manager
                        if quota_manager:
                            admin_quota_info = quota_manager.get_admin_dashboard_info(username)
                            if "error" not in admin_quota_info:
                                # Show available quota for assignment (remaining pool)
                                daily_limit_display = f"{admin_quota_info['available_for_assignment']} (Available)"
                    except Exception as e:
                        logger.debug(f"Error getting admin quota info for {username}: {e}")
                else:
                    # Check if regular user has quota allocation
                    try:
                        from lib.quota_manager import quota_manager
                        if quota_manager:
                            user_quota_status = quota_manager.get_user_quota_status(username)
                            if user_quota_status.get("managed"):
                                daily_limit_display = f"{user_quota_status['daily_quota']} (Quota)"
                    except Exception as e:
                        logger.debug(f"Error getting user quota status for {username}: {e}")
            
            user_management_data.append({
                "Username": username,
                "Role": role_display,
                "Status": "🟢 Online" if is_online else "🔴 Offline",
                "Daily Limit": daily_limit_display,
                "App Account": "Active" if config.get("app_pass") else "Not Set",
                "ReadyMode": "Configured" if config.get("readymode_user") else "Not Set"
            })

        # Display enhanced user table
        df = pd.DataFrame(user_management_data)
        st.dataframe(
            df, 
            hide_index=True, 
            width='stretch',
            column_config={
                "Username": st.column_config.TextColumn("Username", width="medium"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Daily Limit": st.column_config.TextColumn("Daily Limit", width="small"),
                "App Account": st.column_config.TextColumn("App Account", width="small"),
                "ReadyMode": st.column_config.TextColumn("ReadyMode", width="small")
            }
        )

        # Quick stats
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if current_user_role == user_manager.ROLE_OWNER:
                st.metric("Total Users", len(all_users))
            else:
                st.metric("Visible Users", len(visible_users))
        with col2:
            try:
                # Debug: Check what keys are available
                if user_management_data:
                    available_keys = list(user_management_data[0].keys())
                    logger.debug(f"Available keys in user_management_data: {available_keys}")
                
                # Safe access with fallback
                online_count = 0
                for u in user_management_data:
                    if "Status" in u and "Online" in u["Status"]:
                        online_count += 1
                    elif "🟢 Status" in u and "Online" in u["🟢 Status"]:  # Fallback for old format
                        online_count += 1
                
                st.metric("Online Now", online_count)
            except Exception as e:
                logger.error(f"Error calculating online count: {e}")
                st.metric("Online Now", "Error")
        with col3:
            try:
                admin_count = sum(1 for u in user_management_data if "Role" in u and "Admin" in u["Role"])
                if current_user_role == user_manager.ROLE_OWNER:
                    st.metric("Admins", admin_count)
                else:
                    auditor_users = [u for u in user_management_data if "Role" in u and u["Role"] == "Auditor"]
                    st.metric("Your Users", len(auditor_users))
            except Exception as e:
                logger.error(f"Error calculating admin/user count: {e}")
                st.metric("Admins" if current_user_role == user_manager.ROLE_OWNER else "Your Users", "Error")
        with col4:
            if current_user_role == user_manager.ROLE_OWNER:
                try:
                    auditor_count = sum(1 for u in user_management_data if "Role" in u and "Auditor" in u["Role"])
                    st.metric("Auditors", auditor_count)
                except Exception as e:
                    logger.error(f"Error calculating auditor count: {e}")
                    st.metric("Auditors", "Error")
            elif current_user_role == user_manager.ROLE_ADMIN:
                # Show quota info for Admin
                try:
                    from lib.quota_manager import quota_manager
                    quota_info = quota_manager.get_admin_dashboard_info(current_username)
                    if "error" not in quota_info:
                        st.metric("Remaining Slots", quota_info.get('remaining_user_slots', 0))
                    else:
                        st.metric("Quota Status", "Not Set")
                except ImportError:
                    st.metric("Quota System", "N/A")
            # For Auditor role, don't show anything in col4

    # -------------------- TAB 2: USER MANAGEMENT (Owner only) --------------------
    if current_user_role == user_manager.ROLE_OWNER:
        with user_mgmt_tab:
            st.markdown("## User Management")
            st.caption("Create, edit, and delete user accounts")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Create tabs within User Management
            mgmt_tabs = st.tabs(["Create User", "Edit User", "Delete User", "Session Control"])
            create_tab, edit_tab, delete_tab, session_tab = mgmt_tabs
            
            # Create User Tab
            with create_tab:
                st.markdown("### Create New User")
                st.caption("Add a new user account with appropriate role and permissions")
                
                # Direct form without expander to reduce scrolling
                with st.form("add_user_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_username = st.text_input("Username", placeholder="Enter username")
                        
                        # Role selection - only Owner can assign Admin role
                        role_options = [user_manager.ROLE_AUDITOR, user_manager.ROLE_ADMIN]
                        selected_role = st.selectbox("Role", options=role_options, index=0,
                                                   help="Auditor: Basic access. Admin: Settings access + user management")
                        
                        app_password = st.text_input("App Password", type="password", placeholder="App login password")
                    
                    with col2:
                        rm_username = st.text_input("ReadyMode Username", placeholder="ReadyMode username")
                        rm_password = st.text_input("ReadyMode Password", type="password", placeholder="ReadyMode password")
                        daily_limit = st.number_input("Daily Limit", min_value=0, max_value=999999, value=5000,
                                                     help="Set to 999999 for unlimited, 0 to disable downloads")

                    submitted = st.form_submit_button("Create User", type="primary")
                    if submitted:
                        if not all([new_username, app_password, rm_username, rm_password]):
                            st.error("All fields are required: Username, App Password, ReadyMode Username, and ReadyMode Password")
                        elif user_manager.user_exists(new_username):
                            st.error(f"User '{new_username}' already exists!")
                        else:
                            user_data = {
                                'role': selected_role,
                                'app_pass': app_password,
                                'readymode_user': rm_username,
                                'readymode_pass': rm_password,
                                'daily_limit': daily_limit
                            }

                            # Use quota-aware user creation for proper integration
                            success, message = user_manager.create_user_with_quota(
                                new_username, user_data, current_username, daily_quota=None
                            )
                            if success:
                                # Show the message returned from the function
                                st.success(message)
                                # Add small delay to ensure message is visible before refresh
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Failed to create user '{new_username}': {message}")

            # Edit User Tab
            with edit_tab:
                st.markdown("### Edit User Settings")
                st.caption("Modify existing user accounts, roles, and permissions")
                
                # Direct content without expander
                # Filter users based on permissions
                editable_users = []
                for username in all_users.keys():
                    if user_manager.can_modify_user(current_username, username):
                        editable_users.append(username)

                if editable_users:
                    selected_user = st.selectbox("Select user to edit", editable_users, key="edit_user_select_main")

                    if selected_user:
                        user_config = all_users[selected_user]

                        st.markdown(f"#### Editing: **{selected_user}**")
                        st.markdown("---")

                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Current Settings:**")
                            st.write(f"**Role:** {user_config.get('role', 'Auditor')}")
                            st.write(f"**Daily Limit:** {user_config.get('daily_limit', 0)}")
                            st.write(f"**App Account:** {'Active' if user_config.get('app_pass') else 'Not Set'}")
                            st.write(f"**ReadyMode Account:** {'Configured' if user_config.get('readymode_user') else 'Not Set'}")

                        with col2:
                            st.markdown("**Update Settings:**")
                            
                            is_protected_owner = selected_user == "Mohamed Abdo"

                            if is_protected_owner:
                                st.caption("This protected Owner account can only update ReadyMode credentials.")

                                current_role = user_config.get('role', 'Auditor')
                                new_role = current_role
                                new_app_pass = ""

                                # ReadyMode credentials (only editable fields)
                                new_rm_user = st.text_input(
                                    "ReadyMode Username",
                                    value=user_config.get('readymode_user', ''),
                                    placeholder="ReadyMode username",
                                    key=f"rm_user_{selected_user}"
                                )

                                new_rm_pass = st.text_input(
                                    "ReadyMode Password",
                                    value=user_config.get('readymode_pass', ''),
                                    type="password",
                                    placeholder="ReadyMode password",
                                    key=f"rm_pass_{selected_user}"
                                )

                                # Preserve existing daily limit without offering edits
                                new_daily_limit = user_config.get('daily_limit', 5000)

                            else:
                                # Role editing - only Owner can change roles
                                current_role = user_config.get('role', 'Auditor')
                                role_options = [user_manager.ROLE_AUDITOR, user_manager.ROLE_ADMIN]
                                current_role_index = role_options.index(current_role) if current_role in role_options else 0
                                new_role = st.selectbox("Role", options=role_options, index=current_role_index,
                                                      help="Change user role", key=f"role_{selected_user}")

                                # App password update
                                new_app_pass = st.text_input(
                                    "New App Password",
                                    type="password",
                                    placeholder="Leave empty to keep current",
                                    key=f"app_pass_{selected_user}"
                                )

                                # ReadyMode credentials
                                new_rm_user = st.text_input(
                                    "ReadyMode Username",
                                    value=user_config.get('readymode_user', ''),
                                    placeholder="ReadyMode username",
                                    key=f"rm_user_{selected_user}"
                                )

                                new_rm_pass = st.text_input(
                                    "ReadyMode Password",
                                    value=user_config.get('readymode_pass', ''),
                                    type="password",
                                    placeholder="ReadyMode password",
                                    key=f"rm_pass_{selected_user}"
                                )

                                # Daily limit
                                new_daily_limit = st.number_input(
                                    "Daily Limit",
                                    min_value=0,
                                    max_value=999999,
                                    value=user_config.get('daily_limit', 5000),
                                    help="Set to 999999 for unlimited, 0 to disable downloads",
                                    key=f"daily_limit_{selected_user}"
                                )

                            if st.button(f"Update {selected_user}", key=f"update_user_{selected_user}", type="primary", width='stretch'):
                                updated_config = user_config.copy()

                                # Update password if provided (not allowed for protected Owner)
                                if new_app_pass and not is_protected_owner:
                                    updated_config['app_pass'] = new_app_pass

                                # Update ReadyMode credentials (allowed for all users)
                                updated_config['readymode_user'] = new_rm_user if new_rm_user else None
                                updated_config['readymode_pass'] = new_rm_pass if new_rm_pass else None

                                # Update role and daily limit only for non-protected users
                                if not is_protected_owner:
                                    updated_config['role'] = new_role
                                    updated_config['daily_limit'] = new_daily_limit

                                # Remove None values
                                updated_config = {k: v for k, v in updated_config.items() if v is not None}

                                if user_manager.update_user(selected_user, updated_config, updated_by=current_username):
                                    st.success(f"Settings updated for {selected_user}!")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to update settings for {selected_user}")
                else:
                    st.info("No users available for editing.")

            # Delete User Tab
            with delete_tab:
                st.markdown("### Delete User Account")
                st.caption("Permanently remove user accounts and all associated data")
                
                # Direct content without expander
                current_users = list(all_users.keys())
                # Filter users based on permissions - can't delete Owner, Admin can only delete Auditors
                removable_users = []
                for username in current_users:
                    if username == "Mohamed Abdo":
                        continue
                    if user_manager.can_modify_user(current_username, username):
                        removable_users.append(username)

                if removable_users:
                    user_to_delete = st.selectbox("Select user to delete", removable_users, key="delete_user_select")

                    if user_to_delete:
                        st.warning(f"**WARNING:** This will permanently delete user '{user_to_delete}' and all their data!")

                        if st.button(f"Permanently Delete {user_to_delete}", type="secondary", key="delete_button"):
                            if st.session_state.get(f'confirm_delete_{user_to_delete}', False):
                                if user_manager.remove_user(user_to_delete, removed_by=current_username):
                                    st.success(f"User '{user_to_delete}' deleted successfully!")
                                    del st.session_state[f'confirm_delete_{user_to_delete}']
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete user '{user_to_delete}'")
                            else:
                                st.session_state[f'confirm_delete_{user_to_delete}'] = True
                                st.error("**CONFIRM DELETION:** Click the button again to permanently delete this user!")
                else:
                    st.info("No users available for deletion.")

            # Session Control Tab
            with session_tab:
                st.markdown("### Active Session Management")
                st.caption("Monitor and terminate active user sessions")
                
                # Direct content without expander
                active_sessions = []
                for username in all_users.keys():
                    session_id = session_manager.check_existing_session(username)
                    if session_id and user_manager.can_end_sessions(current_username, username):
                        active_sessions.append((username, session_id))

                if active_sessions:
                    st.markdown("**Currently Active Sessions:**")
                    for username, session_id in active_sessions:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{username}** - Session active")
                        with col2:
                            if st.button(f"End Session", key=f"end_session_{username}_mgmt", type="secondary"):
                                if session_manager.invalidate_session(username, session_id):
                                    st.success(f"Session ended for {username}")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to end session for {username}")
                else:
                    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------- TAB 3: DASHBOARD SHARING (Owner only) --------------------
    if current_user_role == user_manager.ROLE_OWNER:
        with dashboard_sharing_tab:
            st.title("Dashboard Sharing Settings")
            st.caption("Manage who shares dashboards and who has isolated views")

            # Get dashboard sharing information
            try:
                from lib.dashboard_manager import dashboard_manager
                sharing_groups = dashboard_manager.get_sharing_groups()
                all_users = user_manager.get_all_users()

                tab_overview, tab_manage, tab_create = st.tabs(["Overview", "Manage Groups", "Create Group"])

                # -------------------- OVERVIEW TAB --------------------
                with tab_overview:
                    st.subheader("Current Groups")

                    if sharing_groups:
                        df_groups = pd.DataFrame([
                            {
                                "Group Name": name,
                                "Members": ", ".join(group["members"]),
                                "Created By": group["created_by"],
                                "Date": group["created_date"],
                            }
                            for name, group in sharing_groups.items()
                        ])
                        st.dataframe(df_groups, hide_index=True, width='stretch')
                    else:
                        st.info("No dashboard sharing groups found. All users are currently isolated.")

                    st.divider()
                    st.subheader("User Dashboard Status")

                    df_status = pd.DataFrame([
                        {
                            "Username": u,
                            "Role": cfg.get("role", "User"),
                            "Dashboard Mode": (
                                "Isolated"
                                if dashboard_manager.get_user_dashboard_mode(u) == "isolated"
                                else f"Shared ({dashboard_manager.get_user_dashboard_mode(u)})"
                            ),
                        }
                        for u, cfg in all_users.items()
                    ])
                    st.dataframe(df_status, hide_index=True, width='stretch')

                # -------------------- MANAGE GROUPS TAB --------------------
                with tab_manage:
                    if not sharing_groups:
                        st.info("No groups available to manage.")
                    else:
                        selected_group = st.selectbox("Select a group to manage", list(sharing_groups.keys()))
                        group_info = sharing_groups[selected_group]

                        st.markdown(f"**Members:** {', '.join(group_info['members'])}")
                        st.divider()

                        # Edit section
                        st.markdown("**Modify Group Members**")

                        col1, col2 = st.columns(2)
                        with col1:
                            to_add = st.multiselect(
                                "Add members",
                                [u for u in all_users if u not in group_info["members"]],
                            )
                            if st.button("Add Selected Users"):
                                updated = group_info["members"] + to_add
                                dashboard_manager.update_sharing_group(selected_group, updated)
                                st.success("Users added successfully.")
                                st.rerun()

                        with col2:
                            to_remove = st.multiselect(
                                "Remove members",
                                group_info["members"],
                            )
                            if st.button("Remove Selected Users"):
                                updated = [u for u in group_info["members"] if u not in to_remove]
                                dashboard_manager.update_sharing_group(selected_group, updated)
                                st.success("Users removed successfully.")
                                st.rerun()

                        st.divider()
                        if st.button(f"Delete Group '{selected_group}'", type="secondary"):
                            dashboard_manager.remove_sharing_group(selected_group)
                            st.success(f"Group '{selected_group}' deleted.")
                            st.rerun()

                # -------------------- CREATE GROUP TAB --------------------
                with tab_create:
                    st.subheader("Create a New Sharing Group")
                    with st.form("create_group_form"):
                        group_name = st.text_input("Group Name", placeholder="e.g., Sales Team")
                        available_users = [
                            u for u in all_users if user_manager.get_user_role(u) != user_manager.ROLE_OWNER
                        ]
                        members = st.multiselect("Select Users", available_users)

                        submitted = st.form_submit_button("Create Group")
                        if submitted:
                            if not group_name.strip():
                                st.error("Group name is required.")
                            elif len(members) < 2:
                                st.error("A sharing group must have at least two users.")
                            else:
                                if dashboard_manager.create_sharing_group(group_name, members, current_username):
                                    st.success(f"Group '{group_name}' created successfully.")
                                    st.rerun()
                                else:
                                    st.error("Failed to create group.")

            except ImportError:
                st.error("Dashboard manager not available")
            except Exception as e:
                st.error(f"Error loading dashboard sharing settings: {str(e)}")

    # -------------------- QUOTA MANAGEMENT TAB --------------------
    with quota_tab:
        
        # Import quota manager
        try:
            from lib.quota_manager import quota_manager
            quota_available = True
        except ImportError:
            quota_available = False
        
        if not quota_available:
            st.warning("Quota management system not available")
        else:
            # Create sub-tabs based on role
            if current_user_role == user_manager.ROLE_OWNER:
                # Direct admin limits content - no sub-tabs needed
                st.markdown("### Admin Quota Control")
                st.caption("Set user creation limits and daily quotas for Admin users")
                
                # Direct content without expander to reduce scrolling
                # Get all admin users
                admin_users = [username for username, data in all_users.items() 
                             if data.get('role') == user_manager.ROLE_ADMIN]
                
                if admin_users:
                    # Display current admin limits
                    st.markdown("#### Current Admin Limits")
                    admin_limits = user_manager.get_all_admin_limits_as_owner(current_username)
                    
                    if "error" not in admin_limits:
                        admin_data = []
                        for admin_username, info in admin_limits.items():
                            admin_data.append({
                                "Admin": admin_username,
                                "Max Users": info["limits"]["max_users"],
                                "Quota Pool": info["limits"]["daily_quota"],
                                "Users Created": info["users_created"],
                                "Remaining Slots": info["remaining_user_slots"],
                                "Pool Usage": info["current_usage"],
                                "Pool Remaining": info["remaining_quota"]
                            })
                        
                        if admin_data:
                            df_admin = pd.DataFrame(admin_data)
                            st.dataframe(df_admin, hide_index=True, width='stretch')
                    
                    # Set limits for admin
                    st.markdown("#### Set Admin Limits")
                    selected_admin = st.selectbox("Select Admin", admin_users, key="admin_limits_select")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        max_users = st.number_input("Maximum Users", min_value=1, max_value=100, value=10, 
                                                  help="Maximum number of users this admin can create")
                    with col2:
                        daily_quota = st.number_input("Daily Quota Pool", min_value=100, max_value=50000, value=5000,
                                                    help="Total daily quota pool - admin can use personally or distribute to users")
                    
                    if st.button("Set Admin Limits", key="set_admin_limits", type="primary"):
                        success, message = user_manager.set_admin_limits_as_owner(
                            selected_admin, max_users, daily_quota, current_username
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    
                    # Quota cleanup for orphan/ghost users
                    st.markdown("#### Quota Cleanup (Advanced)")
                    with st.expander("Remove orphan quota assignment by username"):
                        cleanup_username = st.text_input(
                            "Username to clean from quota assignments",
                            key="quota_cleanup_username",
                            help="Use this only if a username appears in Admin dashboards but not in the main user list."
                        )
                        if st.button("Remove Quota Assignment", key="quota_cleanup_button", type="secondary"):
                            if not cleanup_username:
                                st.error("Please enter a username.")
                            else:
                                success, msg = quota_manager.remove_quota_assignment(cleanup_username)
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                else:
                    st.info("No Admin users found. Create Admin users first to set their limits.")
            
            # Admin Panel - Quota Dashboard (no sub-tabs)
            elif current_user_role == user_manager.ROLE_ADMIN:
                st.markdown("### Your Quota Dashboard")
                st.caption("Monitor your quota usage and user creation limits")
                
                # Get admin quota info
                quota_info = user_manager.get_admin_quota_info(current_username)
                
                if "error" not in quota_info:
                    # Display quota status - DASHBOARD ONLY
                    st.markdown("#### Your Quota Status")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("User Slots", f"{quota_info['users_created']}/{quota_info['max_users']}")
                    with col2:
                        st.metric("Remaining Slots", quota_info['remaining_user_slots'])
                    with col3:
                        # Show committed quota (assigned to users + admin personal usage)
                        committed_quota = quota_info['quota_assigned_to_users'] + quota_info['admin_personal_usage']
                        st.metric("Daily Quota Pool", f"{committed_quota}/{quota_info['daily_quota_pool']}")
                        st.caption(f"Remaining: {quota_info['remaining_quota']}")
                    
                    # Detailed breakdown
                    st.markdown("#### Quota Pool Breakdown")
                    breakdown_col1, breakdown_col2, breakdown_col3 = st.columns(3)
                    with breakdown_col1:
                        st.metric("Your Personal Usage", quota_info['admin_personal_usage'])
                    with breakdown_col2:
                        st.metric("Users' Total Usage", quota_info['users_total_usage'])
                    with breakdown_col3:
                        st.metric("Assigned to Users", quota_info['quota_assigned_to_users'])
                else:
                    st.error(quota_info.get("error", "Unable to load quota information"))

    # -------------------- TAB 3: CREATE USER (Admin only) --------------------
    if current_user_role == user_manager.ROLE_ADMIN:
        with create_user_tab:
            st.markdown("### Create User with Quota")
            st.caption("Create new users under your admin limits with quota allocation")
            
            # Get fresh quota info for this tab
            quota_info = user_manager.get_admin_quota_info(current_username)
            
            if "error" not in quota_info:
                # Direct form without expander for better UX
                with st.form("admin_create_user"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_username = st.text_input("Username", placeholder="Enter username")
                        app_password = st.text_input("App Password", type="password")
                        # Ensure we have valid min/max/value for quota input
                        available_quota = quota_info['available_for_assignment']
                        min_quota = 10
                        max_quota = max(min_quota, available_quota)  # Ensure max is at least min
                        default_quota = max(min_quota, min(1000, available_quota))  # Ensure default is at least min
                        
                        user_daily_quota = st.number_input("User Daily Quota", 
                                                         min_value=min_quota, 
                                                         max_value=max_quota,
                                                         value=default_quota,
                                                         help=f"Available for assignment: {available_quota}")
                        
                        # Show warning if available quota is very low
                        if available_quota < 10:
                            st.warning(f"Low quota available ({available_quota}). Consider redistributing quota from existing users.")
                    
                    with col2:
                        rm_username = st.text_input("ReadyMode Username")
                        rm_password = st.text_input("ReadyMode Password", type="password")
                    
                    submitted = st.form_submit_button("Create User with Quota", type="primary")
                    
                    if submitted:
                        if not all([new_username, app_password, rm_username, rm_password]):
                            st.error("All fields are required: Username, App Password, ReadyMode Username, and ReadyMode Password")
                        elif quota_info['remaining_user_slots'] <= 0:
                            st.error("No remaining user slots available!")
                        elif user_daily_quota > quota_info['available_for_assignment']:
                            st.error("Insufficient quota available for assignment!")
                        else:
                            user_data = {
                                'role': user_manager.ROLE_AUDITOR,
                                'app_pass': app_password,
                                'readymode_user': rm_username,
                                'readymode_pass': rm_password,
                                'daily_limit': 999999  # Managed by quota system
                            }
                            
                            success, message = user_manager.create_user_with_quota(
                                new_username, user_data, current_username, user_daily_quota
                            )
                            
                            if success:
                                # Show the message returned from the function (includes quota assignment status)
                                st.success(message)
                                # Add small delay to ensure message is visible before refresh
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(message)
            else:
                # Show helpful setup message when limits not configured
                error_msg = quota_info.get("error", "Unable to load quota information")
                if "Admin limits not configured" in error_msg:
                    st.warning("**Quota System Not Set Up**")
                    st.info("""
                    **Your quota limits haven't been configured yet.**
                    
                    **To enable user creation:**
                    1. Ask the **Owner** (Mohamed Abdo) to set your limits
                    2. Owner needs to go to Settings → Quota Control → Admin Limits
                    3. Owner will set your maximum users and daily quota
                    """)
                    st.markdown("**Contact Owner:** Mohamed Abdo")
                    st.caption("Request quota limits to be set for your admin account")
                else:
                    st.error(error_msg)

    # -------------------- TAB 4: MANAGE USERS (Admin only) --------------------
    if current_user_role == user_manager.ROLE_ADMIN:
        with manage_users_tab:
            st.markdown("### Manage Your Users")
            st.caption("View and manage all users created under your admin account")
            
            # Get created users
            created_users = user_manager.get_admin_created_users(current_username)
            
            if created_users:
                st.markdown("#### Your Created Users")
                
                # Display user table
                user_quota_data = []
                for username in created_users:
                    user_quota_status = user_manager.get_user_quota_status(username)
                    if user_quota_status.get("managed"):
                        user_quota_data.append({
                            "Username": username,
                            "Daily Quota": user_quota_status["daily_quota"],
                            "Current Usage": user_quota_status["current_usage"],
                            "Remaining": user_quota_status["remaining"],
                            "Usage %": f"{user_quota_status['percentage_used']:.1f}%"
                        })
                
                if user_quota_data:
                    df_users = pd.DataFrame(user_quota_data)
                    st.dataframe(df_users, hide_index=True, width='stretch')
                    
                    # User management actions
                    st.markdown("#### User Actions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Individual User Management**")
                        selected_user = st.selectbox("Select User to Manage", created_users, key="manage_user_select")
                        
                        # Edit User button
                        if st.button("Edit Selected User", key="admin_edit_user", type="primary"):
                            st.session_state['show_edit_user'] = True
                            st.session_state['edit_user_target'] = selected_user
                            st.rerun()
                    
                    with col2:
                        st.markdown("**Quota Management**")
                        st.caption("Redistribute quota between all your users")
                        if st.button("Redistribute Quota", key="redistribute_quota", type="primary"):
                            st.session_state['show_redistribution'] = True
                            st.session_state['show_manual_redistribution'] = True
                            st.rerun()
                
                # Edit User Interface
                if st.session_state.get('show_edit_user', False):
                    st.markdown("---")
                    edit_username = st.session_state.get('edit_user_target')
                    st.markdown(f"#### Edit User: {edit_username}")
                    
                    # Get current user data
                    all_users = user_manager.get_all_users()
                    if edit_username in all_users:
                        current_user_data = all_users[edit_username]
                        
                        with st.form("admin_edit_user_form"):
                            st.markdown("**Update User Credentials**")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                new_app_password = st.text_input(
                                    "App Password", 
                                    value="",
                                    type="password",
                                    help="Leave empty to keep current password"
                                )
                                new_rm_username = st.text_input(
                                    "ReadyMode Username", 
                                    value=current_user_data.get('readymode_user', '') or '',
                                    help="ReadyMode account username"
                                )
                            
                            with col2:
                                new_rm_password = st.text_input(
                                    "ReadyMode Password", 
                                    value="",
                                    type="password",
                                    help="Leave empty to keep current password"
                                )
                                # Initialize quota variables
                                new_quota = None
                                user_quota_status = user_manager.get_user_quota_status(edit_username)
                                if user_quota_status.get("managed"):
                                    current_quota = user_quota_status['daily_quota']
                                    current_usage = user_quota_status['current_usage']
                                    
                                    # Get admin's available quota for assignment
                                    admin_quota_info = user_manager.get_admin_quota_info(current_username)
                                    available_for_assignment = admin_quota_info.get('available_for_assignment', 0)
                                    
                                    # Calculate maximum quota that can be assigned to this user
                                    # Include current quota allocation in available calculation
                                    max_quota = available_for_assignment + current_quota
                                    
                                    # Ensure value is never below min_value
                                    safe_value = max(current_usage, current_quota)
                                    safe_max = max(current_usage, max_quota)
                                    
                                    new_quota = st.number_input(
                                        f"Daily Quota (Current: {current_quota}, Used Today: {current_usage})",
                                        min_value=current_usage,  # Can't go below current usage
                                        max_value=safe_max,
                                        value=safe_value,
                                        step=10,
                                        help=f"Available quota range: {current_usage} to {safe_max}"
                                    )
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                save_changes = st.form_submit_button("Save Changes", type="primary")
                            with col_cancel:
                                cancel_edit = st.form_submit_button("Cancel", type="secondary")
                            
                            if save_changes:
                                # Prepare update data
                                update_data = {}
                                
                                # Only update fields that have values
                                if new_app_password:
                                    update_data['app_pass'] = new_app_password
                                
                                if new_rm_username != current_user_data.get('readymode_user', ''):
                                    update_data['readymode_user'] = new_rm_username if new_rm_username else None
                                
                                if new_rm_password:
                                    update_data['readymode_pass'] = new_rm_password
                                
                                # Handle quota adjustment
                                quota_updated = False
                                if new_quota is not None and user_quota_status.get("managed"):
                                    current_quota = user_quota_status['daily_quota']
                                    if new_quota != current_quota:
                                        # Update quota assignment
                                        try:
                                            from lib.quota_manager import quota_manager
                                            if quota_manager:
                                                # First, remove current quota allocation from admin's available
                                                # Then assign new quota
                                                success, message = quota_manager.adjust_user_quota(edit_username, current_username, new_quota)
                                                if success:
                                                    quota_updated = True
                                                    st.info(f"Quota updated to {new_quota} successfully!")
                                                else:
                                                    st.error(f"Failed to update quota: {message}")
                                        except Exception as e:
                                            st.error(f"Error updating quota: {str(e)}")
                                
                                if update_data or quota_updated:
                                    # Update user credentials
                                    if update_data:
                                        success = user_manager.update_user(edit_username, update_data, current_username)
                                        if success:
                                            st.success(f"User '{edit_username}' updated successfully!")
                                        else:
                                            st.error("Failed to update user. You may not have permission to modify this user.")
                                    
                                    if quota_updated or not update_data:
                                        st.session_state['show_edit_user'] = False
                                        st.session_state['edit_user_target'] = None
                                        st.rerun()
                                else:
                                    st.warning("No changes detected.")
                            
                            if cancel_edit:
                                st.session_state['show_edit_user'] = False
                                st.session_state['edit_user_target'] = None
                                st.rerun()
                    else:
                        st.error(f"User '{edit_username}' not found.")
                        st.session_state['show_edit_user'] = False
                        st.session_state['edit_user_target'] = None
                
                # Quota Redistribution Interface
                if st.session_state.get('show_redistribution', False):
                    st.markdown("---")
                    st.markdown("#### Quota Redistribution")
                    
                    try:
                        from tools.quota_redistribution import get_redistribution_manager
                        redistribution_manager = get_redistribution_manager(quota_manager)
                        
                        # Get current redistribution options
                        redist_options = redistribution_manager.get_redistribution_options(current_username)
                        
                        if "error" not in redist_options and redist_options.get("can_redistribute"):
                            # Manual redistribution form
                            if st.session_state.get('show_manual_redistribution', False):
                                st.markdown("##### Manual Quota Redistribution")
                                
                                with st.form("manual_redistribution_form"):
                                    st.caption(f"Total Available: {redist_options['admin_total_quota']} quota")
                                    
                                    new_allocations = {}
                                    total_manual = 0
                                    
                                    for user in redist_options["users"]:
                                        username = user["username"]
                                        current_quota = user["current_quota"]
                                        current_usage = user["current_usage"]
                                        
                                        # Ensure value is never below min_value
                                        safe_value = max(current_usage, current_quota)
                                        safe_max = max(current_usage, redist_options['admin_total_quota'])
                                        
                                        new_quota = st.number_input(
                                            f"{username} (currently using {current_usage})",
                                            min_value=current_usage,  # Can't go below current usage
                                            max_value=safe_max,
                                            value=safe_value,
                                            key=f"manual_{username}"
                                        )
                                        new_allocations[username] = new_quota
                                        total_manual += new_quota
                                    
                                    st.markdown(f"**Total Allocation:** {total_manual}/{redist_options['admin_total_quota']}")
                                    
                                    if total_manual > redist_options['admin_total_quota']:
                                        st.error("Total allocation exceeds your quota limit!")
                                    
                                    submitted = st.form_submit_button("Apply Manual Redistribution", type="primary")
                                    
                                    if submitted:
                                        if total_manual <= redist_options['admin_total_quota']:
                                            success, message = redistribution_manager.apply_redistribution(
                                                current_username, new_allocations
                                            )
                                            if success:
                                                st.success(f"{message}")
                                                st.session_state['show_redistribution'] = False
                                                st.session_state['show_manual_redistribution'] = False
                                                st.rerun()
                                            else:
                                                st.error(f"{message}")
                                        else:
                                            st.error("Cannot apply: Total exceeds quota limit")
                                    
                                
                                # Close redistribution interface (outside form)
                                if st.button("Cancel Redistribution", key="cancel_redistribution"):
                                    st.session_state['show_redistribution'] = False
                                    st.session_state['show_manual_redistribution'] = False
                                    st.rerun()
                                        
                        else:
                            if "error" in redist_options:
                                st.error(redist_options["error"])
                            else:
                                st.info("Need at least 2 users to redistribute quota")
                    except ImportError:
                        st.error("Quota redistribution system not available")
            else:
                st.info("No users created yet. Go to the 'Create User' tab to create your first user.")

    # -------------------- USER SESSIONS TAB (Owner only) --------------------
    if current_user_role == user_manager.ROLE_OWNER:
        with sessions_tab:
            st.markdown("### User Sessions")
            st.caption("Monitor active users and terminate sessions when needed.")

            # Manual refresh instead of auto-refresh to prevent footer flickering
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write("")  # Empty space
            with col2:
                if st.button("Refresh", help="Update session status", key="manual_session_refresh"):
                    st.rerun()

            all_users = user_manager.get_all_users()
            user_status_data = []
            for username, config in all_users.items():
                session_id = session_manager.check_existing_session(username)
                is_online = session_id is not None
                
                # Check daily limit display based on user type
                daily_limit_display = "UNLIMITED"
                if config.get("daily_limit", 0) < 999999:
                    daily_limit_display = str(config.get("daily_limit", 0))
                else:
                    # Check if user is Admin with quota pool
                    if config.get('role') == 'Admin':
                        try:
                            from lib.quota_manager import quota_manager
                            if quota_manager:
                                admin_quota_info = quota_manager.get_admin_dashboard_info(username)
                                if "error" not in admin_quota_info:
                                    # Show available quota for assignment (remaining pool)
                                    daily_limit_display = f"{admin_quota_info['available_for_assignment']} (Available)"
                        except Exception as e:
                            logger.debug(f"Error getting admin quota info in user sessions for {username}: {e}")
                    else:
                        # Check if regular user has quota allocation
                        try:
                            from lib.quota_manager import quota_manager
                            if quota_manager:
                                user_quota_status = quota_manager.get_user_quota_status(username)
                                if user_quota_status.get("managed"):
                                    daily_limit_display = f"{user_quota_status['daily_quota']} (Quota)"
                        except Exception as e:
                            logger.debug(f"Error getting user quota status in user sessions for {username}: {e}")
                
                user_status_data.append({
                    "Username": username,
                    "Role": config.get('role', 'Auditor'),
                    "Status": "Online" if is_online else "Offline",
                    "Daily Limit": daily_limit_display
                })

            df = pd.DataFrame(user_status_data)
            st.dataframe(df, hide_index=True, width='stretch')

            # Active session control
            st.markdown("#### Active Session Control")
            active_users = [u for u in user_status_data if u["Status"] == "Online" and user_manager.can_end_sessions(current_username, u["Username"])]

            if active_users:
                for user in active_users:
                    username = user["Username"]
                    session_id = session_manager.check_existing_session(username)
                    if session_id and st.button(f"End Session for {username}", key=f"end_{username}", type="secondary"):
                        if user_manager.invalidate_user_session(username, invalidated_by=current_username):
                            st.success(f"Session ended for {username}")
                            st.rerun()
                        else:
                            st.error(f"Failed to end session for {username}")
            else:
                st.info("No active user sessions available for management.")

    # -------------------- TAB 5: SYSTEM HEALTH (Owner only) --------------------
    if current_user_role == user_manager.ROLE_OWNER:
        with health_tab:
            st.markdown("### System Health")
            st.caption("Monitor CPU, memory, and disk usage in real time.")

            # Use manual refresh instead of auto-refresh to prevent footer flickering
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write("")  # Empty space
            with col2:
                if st.button("Refresh", help="Update system metrics", key="manual_system_refresh"):
                    st.rerun()

            system_usage = check_system_resources()
            cpu, mem, disk = system_usage.get("cpu", 0), system_usage.get("memory", 0), system_usage.get("disk", 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("CPU Usage", f"{cpu}%", delta_color="inverse")
            col2.metric("Memory Usage", f"{mem}%", delta_color="inverse")
            col3.metric("Disk Usage", f"{disk}%", delta_color="inverse")

            if max(cpu, mem, disk) > 85:
                st.warning("High system load detected. Consider closing idle sessions.")
            else:
                st.success("System resources are healthy and stable.")

        # -------------------- TAB 6: APP CONFIGURATION (Owner only) --------------------
        with config_tab:
            # Wrap content in a div to scope CSS styles
            st.markdown('<div class="app-config-wrapper">', unsafe_allow_html=True)
            
            # Import settings manager
            try:
                from lib.app_settings_manager import app_settings as persistent_app_settings
            except ImportError:
                st.error("Settings manager not available. Please check app_settings_manager.py")
                return
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Simple, clean layout with cards
            st.markdown("#### Quick Settings")
            
            # Most important settings in a clean grid
            col1, col2 = st.columns(2)
            
            with col1:
                # Audio Settings Card
                st.markdown("""
                <div class="settings-card">
                    <h4>Audio Processing</h4>
                    <p>Voice detection and audio quality</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Get current audio settings
                audio_settings = persistent_app_settings.get_category("audio")
                
                # Simple, clear controls
                vad_input = st.text_input(
                    "Voice Sensitivity (300 - 1000)",
                    value=str(audio_settings.get("vad_energy_threshold", 600)),
                    help="Lower = more sensitive to quiet speech; type an exact value between 300 and 1000"
                )
                try:
                    vad_threshold = int(vad_input)
                except ValueError:
                    st.warning("Invalid voice sensitivity; using the current setting.")
                    vad_threshold = audio_settings.get("vad_energy_threshold", 600)
                else:
                    vad_threshold = max(300, min(vad_threshold, 1000))
                
                quality_options = {"low": "Fast", "medium": "Balanced", "high": "Accurate"}
                current_quality = audio_settings.get("audio_quality", "medium")
                
                audio_quality = st.selectbox(
                    "Processing Speed",
                    options=list(quality_options.keys()),
                    index=list(quality_options.keys()).index(current_quality),
                    format_func=lambda x: quality_options[x]
                )
                
                if st.button("Save Audio Settings", key="save_audio_simple", type="primary"):
                    updates = {
                        "vad_energy_threshold": vad_threshold,
                        "audio_quality": audio_quality
                    }
                    if persistent_app_settings.update_category("audio", updates):
                        try:
                            runtime_app_settings.update_from_ui({
                                "vad_energy_threshold": vad_threshold
                            })
                        except Exception:
                            pass
                        st.success("Audio settings saved!")
        
            with col2:
                # Detection Settings Card
                st.markdown("""
                <div class="settings-card">
                    <h4>Detection Accuracy</h4>
                    <p>Rebuttal and intro detection</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Get current detection settings
                detection_settings = persistent_app_settings.get_category("detection")
                
                semantic_input = st.text_input(
                    "Semantic Threshold (0.50 - 0.90)",
                    value=f"{detection_settings.get('semantic_threshold', 0.68):.2f}",
                    help="Similarity cutoff for semantic rebuttal detection; higher = stricter matches"
                )
                try:
                    semantic_threshold = float(semantic_input)
                except ValueError:
                    st.warning("Invalid semantic threshold; using the current setting.")
                    semantic_threshold = detection_settings.get("semantic_threshold", 0.68)
                else:
                    semantic_threshold = max(0.5, min(semantic_threshold, 0.9))
                
                accent_correction = st.checkbox(
                    "Egyptian Accent Correction",
                    value=detection_settings.get("accent_correction_enabled", True)
                )
                
                if st.button("Save Detection Settings", key="save_detection_simple", type="primary"):
                    updates = {
                        "semantic_threshold": semantic_threshold,
                        "accent_correction_enabled": accent_correction
                    }
                    if persistent_app_settings.update_category("detection", updates):
                        st.success("Detection settings saved!")

                # --- AssemblyAI API key management (per-user) ---
                st.markdown("""<div class="settings-card"><h4>AssemblyAI API Key</h4>
                <p>Store a personal AssemblyAI API key for this account. This key is encrypted and
                used for transcription when available.</p></div>""", unsafe_allow_html=True)

                if API_CLIENT_AVAILABLE:
                    try:
                        api_client = get_api_client()
                        status = api_client.get_assemblyai_key_status()
                        has_key = bool(status.get("has_key"))
                    except Exception as e:
                        logger.error(f"Error checking AssemblyAI key status from UI: {e}")
                        has_key = False

                    current_status = "Set" if has_key else "Not set"
                    st.write(f"Current status: **{current_status}**")

                    api_key_input = st.text_input(
                        "New AssemblyAI API key",
                        type="password",
                        placeholder="Enter new key or leave blank to clear",
                        key="assemblyai_api_key_input",
                    )

                    col_save, col_clear = st.columns(2)
                    with col_save:
                        if st.button("Save API key", key="save_assemblyai_api_key", type="primary"):
                            should_rerun = False
                            try:
                                api_client.update_assemblyai_key(api_key_input or "")
                                st.success("AssemblyAI API key updated.")
                                should_rerun = True
                            except Exception as e:
                                logger.error(f"Error updating AssemblyAI key from UI: {e}")
                                st.error("Failed to update API key. Please try again.")
                            if should_rerun:
                                st.rerun()

                    with col_clear:
                        if has_key and st.button("Clear API key", key="clear_assemblyai_api_key", type="secondary"):
                            should_rerun = False
                            try:
                                api_client.update_assemblyai_key("")
                                st.success("AssemblyAI API key cleared.")
                                should_rerun = True
                            except Exception as e:
                                logger.error(f"Error clearing AssemblyAI key from UI: {e}")
                                st.error("Failed to clear API key. Please try again.")
                            if should_rerun:
                                st.rerun()
                else:
                    st.info("API client is not available; AssemblyAI key management is disabled in this environment.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Data Migration (Owner only)
        if current_user_role == user_manager.ROLE_OWNER:
            st.markdown("<br>", unsafe_allow_html=True)
            show_migration_section()
        
        # Add custom CSS for better styling
        st.markdown("""
        <style>
        .app-config-wrapper .settings-card {
            background: linear-gradient(135deg, 
                rgba(2, 4, 18, 0.75) 0%, 
                rgba(2, 4, 18, 0.85) 100%);
            border: 1px solid rgba(20, 20, 20, 0.8);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            backdrop-filter: blur(16px);
            box-shadow: 
                0 4px 20px rgba(0, 0, 0, 0.4),
                0 0 0 1px rgba(37, 99, 235, 0.05),
                0 0 80px rgba(37, 99, 235, 0.05);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .settings-card:hover {
            transform: translateY(-2px);
            box-shadow: 
                0 8px 30px rgba(0, 0, 0, 0.5),
                0 0 0 1px rgba(37, 99, 235, 0.08),
                0 0 100px rgba(37, 99, 235, 0.08);
        }

        .settings-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(37, 99, 235, 0.03), 
                transparent);
            animation: subtleShimmer 4s ease-in-out infinite;
        }

        @keyframes subtleShimmer {
            0% { left: -100%; }
            50% { left: 100%; }
            100% { left: 100%; }
        }
        
        .app-config-wrapper .settings-card h4 {
            color: #ffffff;
            margin: 0 0 8px 0;
            font-size: 18px;
            font-weight: 600;
        }
        
        .app-config-wrapper .settings-card p {
            color: rgba(255, 255, 255, 0.7);
            margin: 0;
            font-size: 14px;
        }
        
        /* Better button styling */
        .app-config-wrapper .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
            border: 2px solid rgba(20, 20, 20, 0.9) !important;
            border-radius: 18px !important;
            color: white !important;
            font-weight: 600 !important;
            padding: 0.75rem 1.5rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
            backdrop-filter: blur(16px) !important;
        }
        
        .app-config-wrapper .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.08) !important;
        }
        
        .app-config-wrapper .stButton > button[kind="secondary"] {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.5) 0%, rgba(2, 4, 18, 0.65) 100%) !important;
            border: 2px solid rgba(20, 20, 20, 0.8) !important;
            border-radius: 18px !important;
            color: #b4bcc8 !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 30px rgba(37, 99, 235, 0.05) !important;
        }
        
        .app-config-wrapper .stButton > button[kind="secondary"]:hover {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
            border-color: rgba(20, 20, 20, 0.9) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.08) !important;
        }
        
        /* Enhanced form styling */
        .app-config-wrapper .stForm {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%);
            border: 1px solid rgba(20, 20, 20, 0.8);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05);
        }
        
        /* Expander styling */
        .app-config-wrapper .streamlit-expanderHeader {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%);
            border: 1px solid rgba(20, 20, 20, 0.8);
            border-radius: 8px;
            padding: 1rem;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05);
        }
        
        .app-config-wrapper .streamlit-expanderHeader:hover {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08);
        }
        
        /* Metric improvements */
        .app-config-wrapper .metric-container {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%);
            border-radius: 12px;
            padding: 16px;
            margin: 8px 0;
            border: 1px solid rgba(20, 20, 20, 0.8);
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05);
        }
        
        .app-config-wrapper .metric-container:hover {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.08);
        }
        
        /* Status indicators */
        .app-config-wrapper .status-online {
            color: #10b981;
            font-weight: bold;
        }
        
        .app-config-wrapper .status-offline {
            color: #6b7280;
        }
        
        /* Card animations */
        .app-config-wrapper .settings-card {
            animation: fadeIn 0.5s ease-in;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Better selectbox styling */
        .app-config-wrapper .stSelectbox > div > div {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%);
            border: 2px solid rgba(20, 20, 20, 0.8);
            border-radius: 16px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05);
        }
        
        /* Enhanced info/success/warning messages */
        .app-config-wrapper .stAlert {
            border-radius: 8px;
            border: none;
        }
        
        .app-config-wrapper .stAlert > div {
            padding: 1rem 1.5rem;
        }
        </style>
        """, unsafe_allow_html=True)

        # Close the wrapper div
        st.markdown('</div>', unsafe_allow_html=True)

def _maybe_set_ffmpeg_converter() -> bool:
    """Set FFmpeg path if available."""
    try:
        from pydub import AudioSegment
        # Check for bundled ffmpeg
        ffmpeg_bin = Path(__file__).parent / "ffmpeg" / "bin" / "ffmpeg.exe"
        if ffmpeg_bin.exists():
            AudioSegment.converter = str(ffmpeg_bin)
            return True
        # Check system ffmpeg
        import shutil
        if shutil.which("ffmpeg"):
            return True
    except Exception:
        return False
    return False

# Excel download function removed - Excel downloads removed from entire project per user request

def clear_agent_audit_data():
    """Clear agent audit data on logout."""
    # Note: Agent audit data now persists through logout with 9-hour expiry
    # This function is kept for compatibility but doesn't clear data anymore
    pass

def get_available_campaigns(username: str = None) -> List[str]:
    """Get list of campaigns with audit data."""
    return dashboard_manager.get_available_campaigns(username)

def load_campaign_audit_data(campaign_name: str, start_date: date, end_date: date, username: str = None) -> pd.DataFrame:
    """Load campaign audit data for dashboard."""
    return dashboard_manager.load_campaign_audit_data(campaign_name, start_date, end_date, username)

def get_actions_flagged_count(username: str) -> int:
    if not username:
        return 0

    agent_df = dashboard_manager.get_combined_agent_audit_data(username)
    lite_df = dashboard_manager.get_combined_lite_audit_data(username)

    combined_df = pd.concat([agent_df, lite_df], ignore_index=True) if not agent_df.empty and not lite_df.empty else (
        agent_df if not agent_df.empty else lite_df
    )

    if combined_df.empty:
        return 0

    quality_issues_mask = (
        (combined_df['Releasing Detection'] == 'Yes') |
        (combined_df['Late Hello Detection'] == 'Yes')
    )

    if 'Rebuttal Detection' in combined_df.columns:
        no_rebuttal_mask = (combined_df['Rebuttal Detection'].isin(['No', 'N/A']))
        rebuttal_issues_mask = (combined_df['Rebuttal Detection'] == 'No')
    else:
        no_rebuttal_mask = pd.Series([True] * len(combined_df), index=combined_df.index)
        rebuttal_issues_mask = pd.Series([False] * len(combined_df), index=combined_df.index)

    flagged_df = combined_df[
        ((quality_issues_mask & no_rebuttal_mask) | rebuttal_issues_mask)
    ]

    return len(flagged_df)

def show_batch_processing_section():
    """Wrapper that delegates to ui.batch helpers."""
    ui_show_batch_processing_section(reload_modules)

def process_batch_files(uploaded_files, parallel_workers, detection_types, enable_audio_optimization, save_results):
    """Process multiple files in parallel batches."""
    return ui_process_batch_files(
        reload_modules,
        uploaded_files,
        parallel_workers,
        detection_types,
        enable_audio_optimization,
        save_results,
    )


def show_batch_results_preview(results, container):
    ui_show_batch_results_preview(results, container)


def show_final_batch_results(results, total_time, preload_time, save_results):
    ui_show_final_batch_results(results, total_time, preload_time, save_results)


def _render_health_widget():
    health = check_system_resources()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("CPU Usage", f"{health['cpu']:.0f}%")
    col2.metric("Memory Usage", f"{health['memory']:.0f}%")
    col3.metric("Disk Usage", f"{health['disk']:.0f}%")
    status = "Healthy" if health.get('healthy', True) else "Under Load"
    col4.metric("Status", status)

def show_batch_results_preview(results, container):
    ui_show_batch_results_preview(results, container)

def show_final_batch_results(results, total_time, preload_time, save_results):
    ui_show_final_batch_results(results, total_time, preload_time, save_results)

def show_dashboard_section():
    """Display the main Dashboard section with tabs for different audit types."""
    
    # Add CSS to reduce gap between header and tabs
    st.markdown("""
    <style>
    /* Reduce gap between header and dashboard tabs */
    .main .block-container {
      padding-top: 0.25rem !important;
    }
    
    /* Position tabs right below the fixed header */
    .stTabs {
      margin-top: -0.5rem !important;
    }
    
    /* Container for tab list - visually attached to header */
    [data-baseweb="tab-list"] {
      margin-top: 0 !important;
      padding-top: 0.25rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Personal AssemblyAI API key management (available for all roles)
    if API_CLIENT_AVAILABLE:
        st.markdown("""<div class=\"settings-card\"><h4>My AssemblyAI API Key</h4>
        <p>Store a personal AssemblyAI API key for your account. This key is encrypted and
        used for transcription when available.</p></div>""", unsafe_allow_html=True)

        try:
            api_client = get_api_client()
            status = api_client.get_assemblyai_key_status()
            has_key = bool(status.get("has_key"))
        except Exception as e:
            logger.error(f"Error checking AssemblyAI key status from dashboard UI: {e}")
            has_key = False

        current_status = "Set" if has_key else "Not set"
        st.write(f"Your AssemblyAI API key status: **{current_status}**")

        api_key_input = st.text_input(
            "Update your AssemblyAI API key",
            type="password",
            placeholder="Enter new key or leave blank to clear",
            key="dashboard_assemblyai_api_key_input",
        )

        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("Save My API key", key="dashboard_save_assemblyai_api_key", type="primary"):
                should_rerun = False
                try:
                    api_client.update_assemblyai_key(api_key_input or "")
                    st.success("Your AssemblyAI API key has been updated.")
                    should_rerun = True
                except Exception as e:
                    logger.error(f"Error updating AssemblyAI key from dashboard UI: {e}")
                    st.error("Failed to update API key. Please try again.")
                if should_rerun:
                    st.rerun()

        with col_clear:
            if has_key and st.button("Clear My API key", key="dashboard_clear_assemblyai_api_key", type="secondary"):
                should_rerun = False
                try:
                    api_client.update_assemblyai_key("")
                    st.success("Your AssemblyAI API key has been cleared.")
                    should_rerun = True
                except Exception as e:
                    logger.error(f"Error clearing AssemblyAI key from dashboard UI: {e}")
                    st.error("Failed to clear API key. Please try again.")
                if should_rerun:
                    st.rerun()
    
    # Main dashboard tabs
    tab_agent, tab_lite, tab_campaign = st.tabs(["Agent Audit Dashboard", "Lite Audit Dashboard", "Campaign Audit Dashboard"])
    
    # --- Agent Audit Dashboard Tab ---
    with tab_agent:
        show_agent_audit_dashboard()
    
    # --- Lite Audit Dashboard Tab ---
    with tab_lite:
        show_lite_audit_dashboard(dashboard_manager, generate_csv_data)
    
    # --- Campaign Audit Dashboard Tab ---
    with tab_campaign:
        show_campaign_audit_dashboard(dashboard_manager, generate_csv_data)
 
def show_agent_audit_dashboard():
    """Display Agent Audit Dashboard with persistent data storage."""
    
    st.markdown("### Agent Audit Dashboard")
    
    # Add refresh button at the top
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("")  # Empty space
    with col2:
        if st.button("Refresh Data", help="Reload data from storage", key="agent_refresh_btn"):
            # Clear any cached data and force reload
            if 'dashboard_cache_timestamp' in st.session_state:
                del st.session_state.dashboard_cache_timestamp
            st.rerun()
    
    # Get combined data from current user's audits
    df = dashboard_manager.get_combined_agent_audit_data(st.session_state.get('username'))
    
    if df.empty:
        st.info("No agent audit data available. Run Agent Audits to see cumulative results here.")
        return
    
    if 'Agent Name' in df.columns:
        df = df.sort_values('Agent Name', ascending=True, key=lambda col: col.str.lower()).reset_index(drop=True)
    
    # Count flagged samples per agent for warning system
    flagged_counts = {}
    if 'Agent Name' in df.columns and ('Releasing Detection' in df.columns or 'Late Hello Detection' in df.columns or 'Rebuttal Detection' in df.columns):
        for _, row in df.iterrows():
            agent_name = row.get('Agent Name', 'Unknown')
            # Count as flagged if releasing, late hello, or rebuttal not used
            releasing_flagged = row.get('Releasing Detection', 'No') == 'Yes'
            late_hello_flagged = row.get('Late Hello Detection', 'No') == 'Yes'
            rebuttal_not_used = row.get('Rebuttal Detection', 'No') == 'No'  # "No" means rebuttal not detected
            
            is_flagged = releasing_flagged or late_hello_flagged or rebuttal_not_used
            if is_flagged:
                flagged_counts[agent_name] = flagged_counts.get(agent_name, 0) + 1
    
    # Get metrics using the new method
    metrics = dashboard_manager.get_audit_metrics(df)
    
    # Add rebuttal calls count manually (dashboard manager doesn't include it)
    metrics['rebuttal_calls'] = (df['Rebuttal Detection'] == 'No').sum() if 'Rebuttal Detection' in df.columns else 0
    
    # Display summary statistics (Agent Audit now includes Rebuttal detection)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Calls", metrics['total_calls'])
    with col2:
        st.metric("Releasing Calls", metrics['releasing_calls'])
    with col3:
        st.metric("Late Hello Calls", metrics['late_hello_calls'])
    with col4:
        st.metric("Missing Rebuttals", metrics['rebuttal_calls'])
    
    # Agent Warning System
    problematic_agents = {agent: count for agent, count in flagged_counts.items() if count > 5}
    
    if problematic_agents:
        st.markdown("### Agents Needing Attention")
        warning_cols = st.columns(min(len(problematic_agents), 3))
        
        for i, (agent, count) in enumerate(problematic_agents.items()):
            col_idx = i % 3
            with warning_cols[col_idx]:
                st.error(f"**{agent}**: {count} flagged samples")
        
        st.markdown("---")
    
    # Display the data table with conditional styling
    st.markdown("#### Detailed Results")
    
    # Remove unwanted columns from display (keep in data for CSV export)
    # Note: 'username' is kept and will be displayed as "Auditor"
    columns_to_hide = ['File Name', 'File Path', 'Call Duration', 'Confidence Score', 'audit_timestamp']
    display_df = df.copy()
    for col in columns_to_hide:
        if col in display_df.columns:
            display_df = display_df.drop(columns=[col])
    
    # Rename 'username' to 'Auditor' for display if it exists
    if 'username' in display_df.columns:
        display_df = display_df.rename(columns={'username': 'Auditor'})
    
    # Rename 'audit_type' to 'Audit Type' if it exists
    if 'audit_type' in display_df.columns:
        display_df = display_df.rename(columns={'audit_type': 'Audit Type'})
    
    # Standard column order (matching the image)
    standard_column_order = [
        'Agent Name',
        'Phone Number',
        'Timestamp',
        'Disposition',
        'Releasing Detection',
        'Late Hello Detection',
        'Rebuttal Detection',
        'Transcription',
        'Owner Name',
        'Agent Intro',
        'Reason for calling',
        'Intro Score',
        'Status',
        'Dialer Name',
        'Audit Type',
        'Auditor'
    ]
    
    # Handle column name variations - check all possible variations
    column_name_mapping = {}
    
    # Check for "Reason for calling" variations
    if 'Reason for Calling' in display_df.columns:
        column_name_mapping['Reason for Calling'] = 'Reason for calling'
    elif 'Reason for calling' not in display_df.columns:
        # Check for other possible variations
        for col in display_df.columns:
            if 'reason' in col.lower() and 'calling' in col.lower():
                column_name_mapping[col] = 'Reason for calling'
                break
    
    # Check for "Dialer Name" variations
    if 'dialer_name' in display_df.columns:
        column_name_mapping['dialer_name'] = 'Dialer Name'
    elif 'Dialer Name' not in display_df.columns:
        # Check for other possible variations
        for col in display_df.columns:
            if 'dialer' in col.lower():
                column_name_mapping[col] = 'Dialer Name'
                break
    
    # Apply column name mappings
    if column_name_mapping:
        display_df = display_df.rename(columns=column_name_mapping)
    
    # Add missing columns with default values - ensure ALL standard columns exist
    for col in standard_column_order:
        if col not in display_df.columns:
            if col in ['Rebuttal Detection', 'Transcription', 'Agent Intro', 'Owner Name', 'Intro Score', 'Status', 'Audit Type']:
                display_df[col] = 'N/A'
            else:
                display_df[col] = ''
    
    # Reorder columns to match standard order - ALL standard columns should be present now
    # Force include all standard columns in the correct order
    ordered_cols = []
    for col in standard_column_order:
        if col in display_df.columns:
            ordered_cols.append(col)
    
    # Add any remaining columns that aren't in the standard order
    remaining_cols = [col for col in display_df.columns if col not in standard_column_order]
    
    # Final column order: standard columns first (in correct order), then any remaining columns
    display_df = display_df[ordered_cols + remaining_cols]
    
    # Apply conditional styling to the filtered dataframe
    styled_df = display_df.copy()
    
    def highlight_problematic_agents(row):
        agent_name = row.get('Agent Name', '')
        flagged_count = flagged_counts.get(agent_name, 0)

        base_style = 'background-color: #000000; color: #ffffff'
        if flagged_count > 5:
            return [f'{base_style}; border: 1px solid #8b1a1a'] * len(row)
        return [f'{base_style}; border: 1px solid rgba(255,255,255,0.08)'] * len(row)
    
    if not display_df.empty:
        styled_df = display_df.style.apply(highlight_problematic_agents, axis=1)
        st.dataframe(styled_df, width='stretch')
    else:
        st.dataframe(display_df, width='stretch')
    
    # Download options - CSV only (Excel removed per user request)
    csv_data, filename = generate_csv_data(df, "agent_audit_dashboard")
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )
    
    # Clear agent audit data option
    st.markdown("---")
    if st.button("Clear All Agent Audit Data", type="secondary"):
        if st.session_state.get('confirm_clear_agent', False):
            dashboard_manager.clear_agent_audit_data(st.session_state.get('username'))
            st.success("Agent audit data cleared successfully!")
            # Clear any loaded data from session state
            if 'agent_audit_data' in st.session_state:
                del st.session_state.agent_audit_data
            st.rerun()
        else:
            st.session_state['confirm_clear_agent'] = True
            st.warning("Click again to confirm clearing all agent audit data.")

@secure_app_decorator
def main():
    """Main application function."""
    
    # Enable runtime protection for production
    if PROTECTION_AVAILABLE and os.getenv('DEPLOYMENT_MODE') == 'production':
        enable_runtime_protection()
    
    # Suppress Streamlit ScriptRunContext warnings immediately
    import warnings
    warnings.filterwarnings("ignore", message="missing ScriptRunContext")
    
    # Note: Page configuration (including favicon) is set at module level (line ~196)
    # to ensure it runs before any other Streamlit commands

# Removed background jobs cleanup (no longer needed)
    
    load_custom_css()
    
    # ✅ PERFORMANCE FIX: Load CSS from external cached files
    # Before: 273 lines of CSS parsed on EVERY rerun (200-300ms penalty)
    # After: CSS loaded once per session and cached (0ms on subsequent loads)
    from lib.css_loader import apply_cached_css
    apply_cached_css()
    
    # Add smooth section transition animations (lightweight and performant)
    if 'section_animations_loaded' not in st.session_state:
        st.markdown("""
        <style>
        /* Lightweight section transition animations */
        @keyframes sectionTransition {
            from {
                opacity: 0;
                transform: translateY(12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Apply smooth fade-in to main content blocks */
        .main .block-container {
            animation: sectionTransition 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        
        /* Smooth transitions for vertical blocks */
        .main [data-testid="stVerticalBlock"]:not(:first-child) {
            animation: sectionTransition 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            animation-fill-mode: both;
        }
        
        /* Stagger animation for multiple elements */
        .main [data-testid="stVerticalBlock"]:nth-child(1) { animation-delay: 0.05s; }
        .main [data-testid="stVerticalBlock"]:nth-child(2) { animation-delay: 0.1s; }
        .main [data-testid="stVerticalBlock"]:nth-child(3) { animation-delay: 0.15s; }
        
        /* Ensure animations don't block interactions */
        .main * {
            will-change: auto;
        }
        </style>
        """, unsafe_allow_html=True)
        st.session_state.section_animations_loaded = True

    # Handle header logout icon via query parameter
    try:
        params = st.query_params
    except Exception:
        params = {}
    if params.get("header_logout", ["0"])[0] == "1":
        username = st.session_state.get('username') or params.get("header_logout_user", [None])[0]

        # Use centralized helper to invalidate any active session for this username
        if username:
            logout_user_by_name(username)

        clear_agent_audit_data()

        # Clear only authentication-related keys and mark next login as forced
        for key in ["authenticated", "username", "session_id"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.force_login_attempted = True

        # Clear the query params so we don't loop
        try:
            if hasattr(st, "query_params"):
                st.query_params.clear()
        except Exception:
            pass

        st.rerun()

    # Check authentication first
    if not check_authentication():
        # Check if user was just logged out due to session invalidation
        if st.session_state.get('session_invalidated', False):
            st.warning("Your session was terminated because you logged in from another location/device. Only one active session per account is allowed.")
            del st.session_state.session_invalidated
        show_login_page()
        return
    
    # Initialize agent audit storage for authenticated users
    dashboard_manager.initialize_agent_audit_storage(st.session_state.get('username'))
    
    ffmpeg_ok = _maybe_set_ffmpeg_converter()

    # Top header content (auth only): section title + user pill (no center VOS text now)
    username = get_current_username('Guest')
    is_authenticated = is_user_authenticated()
    if is_authenticated:
        display_name = username
        avatar_letter = display_name[0].upper() if display_name else "?"
        role_label = get_current_user_role(user_manager) or "User"

        active_section = st.session_state.get('active_nav_tab', 'Dashboard')
        render_header_bar(
            active_section=active_section,
            display_name=display_name,
            avatar_letter=avatar_letter,
            role_label=role_label,
            username=username,
        )

    # ✅ PERFORMANCE FIX: Wave animations now loaded from cached CSS file
    # No need to inject duplicate CSS - already in animations.css

    # Main navigation sections with modern sidebar design
    with st.sidebar:
        # VOS Branding CSS and Sidebar Button Styling
        st.markdown("""
        <style>
        /* VOS BRANDING */
        .sidebar-brand-vos .vos-title {
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.8), rgba(37, 99, 235, 0.6));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: 0.2em;
            filter: drop-shadow(0 0 15px rgba(37, 99, 235, 0.15));
            animation: pulse-glow 2s ease-in-out infinite;
        }
        
        .sidebar-brand-vos .vos-subtitle {
            color: #94a3b8;
            font-size: 0.75rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }
        
        @keyframes pulse-glow {
            0%, 100% { filter: drop-shadow(0 0 10px rgba(37, 99, 235, 0.1)); }
            50% { filter: drop-shadow(0 0 20px rgba(37, 99, 235, 0.15)); }
        }
        
        /* SIDEBAR BUTTONS - Dark theme with subtle blue */
        [data-testid="stSidebar"] button,
        section[data-testid="stSidebar"] button {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
            border: 2px solid rgba(20, 20, 20, 0.8) !important;
            color: #e2e8f0 !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            cursor: pointer !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 30px rgba(37, 99, 235, 0.05) !important;
        }
        
        [data-testid="stSidebar"] button:hover,
        section[data-testid="stSidebar"] button:hover {
            background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
            border-color: rgba(20, 20, 20, 0.9) !important;
            color: #ffffff !important;
            transform: translateX(5px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.08) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Sidebar VOS brand at the top
        st.markdown('''
        <div class="sidebar-brand-vos">
            <div class="vos-title">VOS</div>
            <div class="vos-subtitle">Voice Observation System</div>
        </div>
        ''', unsafe_allow_html=True)

        # Navigation Section
        st.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)
        
        # Create tab-style navigation buttons in sidebar (vertical stack)
        # Order: Audit, Actions, Call Review, Dashboard
        base_nav_options = ["Audit", "Actions", "Call Review", "Dashboard"]
        
        # Add Phrase Management for Owner only (above Settings)
        if get_current_user_role(user_manager) == "Owner":
            nav_options = base_nav_options + ["Phrase Management"]
        else:
            nav_options = base_nav_options
            
        # Add Settings for Owner and Admin roles only
        if user_manager.has_settings_access(username):
            nav_options = nav_options + ["Settings"]
        
        # Get current active tab from session state, default to first
        if 'active_nav_tab' not in st.session_state:
            st.session_state.active_nav_tab = nav_options[0]

        actions_badge_count = 0
        total_flagged_actions = 0
        current_username = st.session_state.get('username')
        if current_username:
            try:
                total_flagged_actions = get_actions_flagged_count(current_username)
            except Exception:
                total_flagged_actions = 0
            last_seen = st.session_state.get('actions_last_seen_total_flagged')
            if last_seen is None:
                st.session_state['actions_last_seen_total_flagged'] = total_flagged_actions
                last_seen = total_flagged_actions
            if total_flagged_actions < last_seen:
                st.session_state['actions_last_seen_total_flagged'] = total_flagged_actions
                last_seen = total_flagged_actions
            actions_badge_count = max(total_flagged_actions - last_seen, 0)
            st.session_state['actions_badge_count'] = actions_badge_count

        if actions_badge_count > 0:
            st.markdown(
                f"""
                <style>
                .st-key-nav_actions button {{
                    position: relative;
                }}
                .st-key-nav_actions button::after {{
                    content: "{actions_badge_count}";
                    position: absolute;
                    top: 4px;
                    right: 8px;
                    min-width: 18px;
                    height: 18px;
                    padding: 0 6px;
                    border-radius: 999px;
                    background: #ef4444;
                    color: #ffffff;
                    font-size: 0.65rem;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 0 0 1px #111827;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
        
        # Create vertical stack of tab buttons with Lucide-style icons + labels
        for i, option in enumerate(nav_options):
            # Check if this tab is active
            is_active = st.session_state.active_nav_tab == option

            # Choose Lucide-style icon SVG per option (kept for reference; actual icons are injected via CSS)
            if option == "Dashboard":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M3 13h8V3H3z'/>
                  <path d='M13 21h8V11h-8z'/>
                  <path d='M13 3h8v4h-8z'/>
                  <path d='M3 17h8v4H3z'/>
                </svg>
                """
            elif option == "Actions":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M12 5v14'/>
                  <path d='M5 12h14'/>
                </svg>
                """
            elif option == "Audit":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M9 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4'/>
                  <path d='M9 3h6v4H9z'/>
                  <path d='M9 17v-6h4'/>
                  <path d='M21 3l-6 6'/>
                </svg>
                """
            elif option == "Call Review":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M22 16.92V19a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2 5.18 2 2 0 0 1 4 3h2.09a2 2 0 0 1 2 1.72 12.44 12.44 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 11.09a16 16 0 0 0 6 6l1.45-1.45a2 2 0 0 1 2.11-.45 12.44 12.44 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'/>
                </svg>
                """
            elif option == "Phrase Management":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M7 8h10'/>
                  <path d='M7 12h6'/>
                  <path d='M7 16h4'/>
                  <path d='M4 4h16v16H4z'/>
                </svg>
                """
            elif option == "Settings":
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <circle cx='12' cy='12' r='3'/>
                  <path d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 8 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 3.6 15a1.65 1.65 0 0 0-1.51-1H2a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 3.6 8a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 8 3.6a1.65 1.65 0 0 0 1-1.51V2a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 16 3.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 8a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z'/>
                </svg>
                """
            else:
                # Fallback icon
                icon_svg = """
                <svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>
                  <circle cx='12' cy='12' r='10'/>
                </svg>
                """

            # Build label text (active tab can be styled via CSS; keep text simple here)
            button_label = option

            # Use a stable key per option
            nav_key = f"nav_{option.lower().replace(' ', '_')}"

            # Render a single flat button; icons are added with CSS using the container key
            if st.button(
                button_label,
                key=nav_key,
                help=None,
                type="secondary",
                width="stretch"
            ):
                st.session_state.active_nav_tab = option
                st.rerun()
        
        # Set nav_option based on active tab
        nav_option = st.session_state.active_nav_tab
        
        # Track section changes for animations
        if 'previous_nav_option' not in st.session_state:
            st.session_state.previous_nav_option = nav_option
        section_changed = st.session_state.previous_nav_option != nav_option
        if section_changed:
            st.session_state.previous_nav_option = nav_option
        
        if nav_option == "Actions" and current_username:
            st.session_state['actions_last_seen_total_flagged'] = total_flagged_actions
            st.session_state['actions_badge_count'] = 0
        job_manager = st.session_state.get('job_manager')
        if job_manager and 'background_jobs' in st.session_state and st.session_state.background_jobs:
            active_jobs = []
            for job_id, job_meta in st.session_state.background_jobs.items():
                job_status = job_manager.get_job_status(job_id)
                if job_status and job_status['status'] in ['running', 'completed', 'error']:
                    active_jobs.append((job_id, job_status, job_meta))
            
            if active_jobs:
                running_jobs = [job for job in active_jobs if job[1]['status'] == 'running']
                if running_jobs:
                    # SIMPLE CLEAN PROGRESS DISPLAY
                    st.markdown("---")
                    st.markdown("**Processing Status**")
                    
                    for job_id, job_status, job_meta in running_jobs:
                        job_type_display = "Agent Audit" if job_meta['type'] == 'agent_audit' else "Campaign Audit"
                        agent_name = job_meta.get('agent_name', 'Unknown')
                        campaign_name = job_meta.get('campaign_name', 'Unknown')
                        display_name = agent_name if job_meta['type'] == 'agent_audit' else campaign_name
                        
                        # SIMPLE PROGRESS DISPLAY
                        st.markdown(f"**{job_type_display}: {display_name}**")
                        st.markdown(f"{job_status['message']}")
                        st.progress(job_status['progress'] / 100)
                        st.markdown(f"{job_status['progress']:.0f}%")
                        
                    st.markdown("---")
                    st.info("Processing continues in background. You can switch tabs or continue working.")
        
        # Usage Metrics Section - At the bottom of sidebar (glass-style card)
        if st.session_state.get('authenticated', False):
            current_username = st.session_state.get('username', 'Unknown')
            usage_info = dashboard_manager.get_daily_usage_info(current_username)

            if usage_info['daily_limit'] > 0:
                usage_percent = usage_info['usage_percent']

                # Check if unlimited (high limit) or quota managed
                is_unlimited = usage_info['daily_limit'] >= 999999
                quota_managed = False
                quota_info = None

                if is_unlimited:
                    # Check if user is Admin with quota pool
                    current_user_role = user_manager.get_user_role(st.session_state.username)
                    if current_user_role == user_manager.ROLE_ADMIN:
                        try:
                            from lib.quota_manager import quota_manager
                            if quota_manager:
                                admin_quota_info = quota_manager.get_admin_dashboard_info(st.session_state.username)
                                if "error" not in admin_quota_info:
                                    quota_managed = True
                                    quota_info = {
                                        'daily_quota': admin_quota_info['daily_quota_pool'],
                                        'current_usage': admin_quota_info['total_usage'],
                                        'remaining': admin_quota_info['remaining_quota']
                                    }
                        except:
                            pass
                    else:
                        # Check if regular user has quota allocation
                        try:
                            from lib.quota_manager import quota_manager
                            if quota_manager:
                                user_quota_status = quota_manager.get_user_quota_status(st.session_state.username)
                                if user_quota_status.get("managed"):
                                    quota_managed = True
                                    quota_info = user_quota_status
                        except:
                            pass

                # Build display strings and ring values for the Daily Credits widget
                center_text = ""      # e.g. "15/100" (used/total)
                progress_text = ""    # e.g. "15" (used)
                remaining_text = ""   # e.g. "85" (remaining)
                resets_text = "Daily"
                ring_percent = 0.0

                if quota_managed and quota_info:
                    current_user_role = user_manager.get_user_role(st.session_state.username)
                    label = "Available" if current_user_role == user_manager.ROLE_ADMIN else "Quota"

                    current_usage = max(0, quota_info.get('current_usage', 0))
                    daily_quota = max(1, quota_info.get('daily_quota', 1))
                    remaining = max(0, quota_info.get('remaining', 0))

                    used = current_usage
                    total = daily_quota

                    center_text = f"{used}/{total}"
                    progress_text = f"{used}"
                    remaining_text = f"{remaining}"

                    ring_percent = used / total if total > 0 else 0.0
                    ring_percent = min(max(ring_percent, 0.0), 1.0)

                elif is_unlimited:
                    center_text = "∞"
                    progress_text = "UNLIMITED"
                    remaining_text = "UNLIMITED"
                    ring_percent = 0.0
                else:
                    # Fallback: limited accounts using raw usage_info
                    used = max(0, usage_info['current_count'])
                    total = max(1, usage_info['daily_limit'])
                    remaining_raw = usage_info['remaining']
                    remaining = max(0, remaining_raw)

                    center_text = f"{used}/{total}"
                    progress_text = f"{used}"
                    remaining_text = f"{remaining}"

                    ring_percent = used / total if total > 0 else 0.0
                    ring_percent = min(max(ring_percent, 0.0), 1.0)

                # Compute stroke offset for circular ring (approximate circumference)
                ring_circumference = 289
                ring_offset = ring_circumference * (1 - ring_percent)

                # Render compact glass-style usage card with circular ring
                st.markdown(f"""
                <div class="sidebar-usage">
                    <div class="usage-header-modern">DAILY CREDITS</div>
                    <div class="credits-ring">
                        <svg class="credits-ring-svg" viewBox="0 0 120 120">
                            <circle class="credits-ring-bg" cx="60" cy="60" r="46" />
                            <circle class="credits-ring-progress" cx="60" cy="60" r="46" stroke-dashoffset="{ring_offset}" />
                        </svg>
                        <div class="credits-ring-center">
                            <div class="credits-ring-number">{center_text}</div>
                        </div>
                    </div>
                    <div class="usage-metric-modern">
                        <div class="usage-label-modern">Progress</div>
                        <div class="usage-value-modern">{progress_text}</div>
                    </div>
                    <div class="usage-metric-modern">
                        <div class="usage-label-modern">Remaining</div>
                        <div class="usage-value-modern">{remaining_text}</div>
                    </div>
                    <div class="usage-metric-modern">
                        <div class="usage-label-modern">Resets</div>
                        <div class="usage-value-modern">{resets_text}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("**Status:** No limit")
        
        # Fixed bottom footer for authenticated users - Render before navigation to prevent flickering
        authenticated = st.session_state.get('authenticated', False)
        username = st.session_state.get('username')
        session_id = st.session_state.get('session_id')

    if authenticated and username and session_id:
        st.markdown("""
        <div class="app-footer">
            &copy; 2025 VOS-Voice Observation System. All rights reserved •
            <a href="https://t.me/Mohmed_abdo" target="_blank">Developed by Mohamed Abdo</a>
        </div>
        """, unsafe_allow_html=True)

    # Restore original conditional navigation logic
    if nav_option == "Audit":
        show_audit_section(
            _maybe_set_ffmpeg_converter,
            check_system_resources,
            READYMODE_AVAILABLE,
            get_user_readymode_credentials,
            get_user_daily_limit,
        )
    elif nav_option == "Actions":
        show_actions_section(dashboard_manager)
    elif nav_option == "Call Review":
        from call_review import show_call_review_page
        show_call_review_page()
    elif nav_option == "Phrase Management":
        show_phrase_management_section()
    elif nav_option == "Settings":
        show_settings_section()
    else:
        show_dashboard_section()

if __name__ == "__main__":
    main()
