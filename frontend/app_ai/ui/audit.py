import streamlit as st
import tempfile
import time
import threading
import traceback
import logging
from pathlib import Path
from datetime import date, datetime

# Set up logger
logger = logging.getLogger(__name__)

# Import auto-refresh for real-time progress updates
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False
    def st_autorefresh(interval, key=None, limit=None):
        """Fallback if autorefresh not available."""
        pass

from config import READYMODE_URL
from processing import batch_analyze_folder_fast, batch_analyze_folder_lite
from lib.dashboard_manager import dashboard_manager, user_manager
# Import from frontend.app_ai (backend/frontend separation architecture)
from frontend.app_ai.auth.authentication import get_current_username, get_current_user_role
from lib.security_utils import security_manager
from automation.download_readymode_calls import (
    download_all_call_recordings,
    extract_dialer_name_from_url,
    ReadyModeLoginError,
    ReadyModeNoCallsError,
)
from .components import (
    show_campaign_audit_dashboard,
    show_lite_audit_dashboard,
    show_actions_section,
)


# NOTE: This module is an extraction of the Audit wrapper UI from app.py.
# Logic is kept identical; only the location changed.
def show_audit_section(
    _maybe_set_ffmpeg_converter,
    check_system_resources,
    READYMODE_AVAILABLE,
    get_user_readymode_credentials,
    get_user_daily_limit,
):
    """Display the Audit section with modern card-based layout.

    This is extracted from app.py; behavior is kept identical.
    External helpers and flags are passed in from app.py to avoid
    duplicating environment and auth logic here.
    """

    # Get current user role for access control
    current_username = get_current_username("Unknown")
    current_user_role = (
        get_current_user_role(user_manager)
        or user_manager.get_user_role(current_username)
    )

    def _get_user_assemblyai_api_key(username: str):
        user_data = user_manager.get_user(username) or {}
        encrypted_key = user_data.get("assemblyai_api_key_encrypted")
        if not encrypted_key:
            return None, "global"
        try:
            decrypted_key = security_manager.decrypt_string(encrypted_key)
        except Exception:
            decrypted_key = None
        return decrypted_key or None, "user" if decrypted_key else "global"

    ffmpeg_ok = _maybe_set_ffmpeg_converter()

    # Initialize worker state for Agent Audit (if not present)
    if "agent_worker_state" not in st.session_state:
        st.session_state.agent_worker_state = {
            "status": "idle",
            "phase": None,
            "downloaded": 0,
            "total": 0,
            "message": "",
            "start_time": None,
            "elapsed_time": 0,
        }
    if "agent_cancel_event" not in st.session_state:
        st.session_state.agent_cancel_event = threading.Event()
    if "agent_worker_thread" not in st.session_state:
        st.session_state.agent_worker_thread = None

    # Initialize worker state for Upload Audit (if not present)
    if "upload_worker_state" not in st.session_state:
        st.session_state.upload_worker_state = {
            "status": "idle",
            "message": "",
            "downloaded": 0,
            "total": 0,
            "df": None
        }
    if "upload_cancel_event" not in st.session_state:
        st.session_state.upload_cancel_event = threading.Event()
    if "upload_worker_thread" not in st.session_state:
        st.session_state.upload_worker_thread = None

    def _run_upload_audit_worker(
        temp_path_str,
        campaign_name,
        current_username,
        user_api_key,
        api_key_source,
        worker_state,
        cancel_event,
        show_flagged_only=False
    ):
        import traceback
        import time as time_module
        import shutil
        from pathlib import Path

        try:
            start_time = time_module.time()
            worker_state["status"] = "running"
            worker_state["message"] = "Initializing analysis..."
            worker_state["downloaded"] = 0
            worker_state["total"] = 0
            
            metadata = {
                "dialer_name": "upload",
                "API Key Source": api_key_source,
            }

            def analyze_progress(done, total, message=None):
                worker_state["downloaded"] = int(done)
                worker_state["total"] = int(total)
                worker_state["message"] = message if message else f"Analyzing: {done}/{total}"
                worker_state["elapsed_time"] = time_module.time() - start_time
                if cancel_event.is_set():
                    raise KeyboardInterrupt("cancelled")

            df = batch_analyze_folder_fast(
                temp_path_str,
                progress_callback=analyze_progress,
                additional_metadata=metadata,
                show_all_results=True,
                username=current_username,
                user_api_key=user_api_key,
            )

            # Filter to flagged calls only if requested (after getting all results with transcription)
            if show_flagged_only and not df.empty:
                # Build mask for flagged calls (calls with detected issues)
                masks = []
                if 'Releasing Detection' in df.columns:
                    masks.append(df['Releasing Detection'] == 'Yes')
                if 'Late Hello Detection' in df.columns:
                    masks.append(df['Late Hello Detection'] == 'Yes')
                if 'Rebuttal Detection' in df.columns:
                    masks.append(df['Rebuttal Detection'] == 'No')
                
                # Combine all masks with OR logic
                if masks:
                    flagged_mask = masks[0]
                    for mask in masks[1:]:
                        flagged_mask = flagged_mask | mask
                    df = df[flagged_mask].copy()

            # Tag results for clarity
            if not df.empty:
                df["Audit Type"] = "Upload Audit"
                if campaign_name:
                    df["Campaign"] = campaign_name
                
                # Save results to dashboard
                worker_state["message"] = "Saving results..."
                if campaign_name and campaign_name.strip():
                    dashboard_manager.save_campaign_audit_results(
                        df, campaign_name.strip(), current_username
                    )
                else:
                    dashboard_manager.save_agent_audit_results(
                        df, current_username
                    )

            worker_state["df"] = df
            worker_state["status"] = "completed"
            
            # Clean up temp files
            try:
                shutil.rmtree(temp_path_str, ignore_errors=True)
            except:
                pass

        except KeyboardInterrupt:
            worker_state["status"] = "cancelled"
            try:
                shutil.rmtree(temp_path_str, ignore_errors=True)
            except:
                pass
        except Exception as e:
            worker_state["status"] = "error"
            worker_state["error_message"] = str(e)
            worker_state["traceback"] = traceback.format_exc()
            try:
                shutil.rmtree(temp_path_str, ignore_errors=True)
            except:
                pass

    def _run_agent_audit_worker(
        ready_url,
        agent_name,
        start_date,
        end_date,
        selected_dispositions,
        min_duration,
        max_duration,
        max_samples,
        audit_mode,
        current_username_local,
        rm_user,
        rm_pass,
        worker_state,
        cancel_event,
        driver_storage,
        user_api_key,
        api_key_source
    ):
        import traceback
        import time as time_module
        from pathlib import Path

        try:
            start_time = time_module.time()
            worker_state["status"] = "running"
            worker_state["phase"] = "download"
            worker_state["downloaded"] = 0
            worker_state["total"] = max_samples
            worker_state["start_time"] = start_time
            worker_state["message"] = "Starting download..."

            effective_min_duration = min_duration
            effective_max_duration = max_duration
            if audit_mode == "heavy":
                if effective_min_duration is None or effective_min_duration < 20:
                    effective_min_duration = 20
                if effective_max_duration is not None and effective_max_duration < effective_min_duration:
                    effective_max_duration = None

            def check_cancellation():
                return cancel_event.is_set()

            def download_update(downloaded, total):
                worker_state["phase"] = "download"
                worker_state["downloaded"] = int(downloaded) if isinstance(downloaded, (int, float)) else 0
                worker_state["total"] = int(total) if isinstance(total, (int, float)) else max_samples
                worker_state["message"] = f"Downloading: {worker_state['downloaded']}/{worker_state['total']}"
                worker_state["elapsed_time"] = time_module.time() - start_time

            downloaded_path_str = download_all_call_recordings(
                ready_url,
                agent=agent_name,
                start_date=start_date,
                end_date=end_date,
                max_samples=max_samples,
                update_callback=download_update,
                disposition=selected_dispositions,
                min_duration=effective_min_duration,
                max_duration=effective_max_duration,
                username=current_username_local,
                readymode_user=rm_user,
                readymode_pass=rm_pass,
                cancellation_callback=check_cancellation,
                driver_storage=driver_storage,
            )

            if cancel_event.is_set():
                worker_state["status"] = "cancelled"
                return

            worker_state["phase"] = "analyze"
            worker_state["message"] = "Processing audio files..."
            
            dialer_name = extract_dialer_name_from_url(ready_url)
            from config import RECORDINGS_ROOT
            recordings_base = Path(RECORDINGS_ROOT)

            def _list_mp3_files(folder: Path):
                try:
                    return [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"]
                except Exception:
                    return []

            agent_name_lower = agent_name.lower()
            all_users_mode = agent_name_lower.strip() in ["all users", "all user", "all"]
            target_folder = None
            files = []

            # Priority 1: Use the explicit download path
            if downloaded_path_str:
                explicit_path = Path(downloaded_path_str)
                if explicit_path.exists() and explicit_path.is_dir():
                    target_folder = explicit_path
                    files = _list_mp3_files(target_folder)

            # Priority 2: Fallback search (simplified for worker)
            if not files and recordings_base.exists():
                auditor_dir = recordings_base / "Agent" / current_username_local
                if auditor_dir.exists():
                    subdirs = [d for d in auditor_dir.iterdir() if d.is_dir()]
                    matching_subdirs = []
                    formatted_agent = agent_name_lower.replace(" ", "")
                    for d in subdirs:
                        if all_users_mode or agent_name_lower in d.name.lower() or formatted_agent in d.name.lower().replace(" ", ""):
                            if _list_mp3_files(d):
                                matching_subdirs.append(d)
                    if matching_subdirs:
                        matching_subdirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        target_folder = matching_subdirs[0]
                        files = _list_mp3_files(target_folder)

            if not files:
                worker_state["status"] = "error"
                worker_state["error_type"] = "no_files"
                worker_state["error_message"] = f"No files found for agent '{agent_name}'"
                return

            metadata = {
                "dialer_name": dialer_name,
                "API Key Source": api_key_source,
            }

            def analyze_progress(done, total, message=None):
                worker_state["phase"] = "analyze"
                worker_state["downloaded"] = int(done)
                worker_state["total"] = int(total)
                worker_state["message"] = message if message else f"Analyzing: {done}/{total}"
                worker_state["elapsed_time"] = time_module.time() - start_time
                if cancel_event.is_set():
                    raise KeyboardInterrupt("cancelled")

            if audit_mode == "heavy":
                df = batch_analyze_folder_fast(
                    str(target_folder),
                    progress_callback=analyze_progress,
                    additional_metadata=metadata,
                    show_all_results=True,
                    username=current_username_local,
                    user_api_key=user_api_key,
                )
                if not df.empty:
                    df["Audit Type"] = "Heavy Audit"
            else:
                df = batch_analyze_folder_lite(
                    str(target_folder),
                    progress_callback=analyze_progress,
                    additional_metadata=metadata,
                    username=current_username_local,
                    user_api_key=user_api_key,
                )
                if not df.empty:
                    df["Audit Type"] = "Lite Audit"

            worker_state["message"] = "Saving results..."
            if not df.empty:
                if audit_mode == "heavy":
                    dashboard_manager.save_agent_audit_results(df, current_username_local)
                else:
                    dashboard_manager.save_lite_audit_results(df, current_username_local)
                dashboard_manager.increment_daily_download_count(current_username_local, len(df))
                worker_state["record_count"] = len(df)
            
            worker_state["status"] = "completed"
            worker_state["df_empty"] = bool(df.empty)

        except KeyboardInterrupt:
            worker_state["status"] = "cancelled"
        except Exception as e:
            worker_state["status"] = "error"
            worker_state["error_message"] = str(e)
            worker_state["traceback"] = traceback.format_exc()

    def _run_campaign_audit_worker(
        ready_url,
        campaign_name,
        start_date,
        end_date,
        selected_dispositions,
        min_duration,
        max_duration,
        max_samples,
        audit_type,
        current_username_local,
        rm_user,
        rm_pass,
        worker_state,
        cancel_event,
        driver_storage,
    ):
        import traceback
        import time as time_module

        try:
            start_time = time_module.time()
            
            worker_state["status"] = "running"
            worker_state["phase"] = "download"
            worker_state["downloaded"] = 0
            worker_state["total"] = max_samples
            worker_state["start_time"] = start_time

            effective_min_duration = min_duration
            effective_max_duration = max_duration
            if audit_type == "Heavy Audit":
                if effective_min_duration is None or effective_min_duration < 20:
                    effective_min_duration = 20
                if effective_max_duration is not None and effective_max_duration < effective_min_duration:
                    effective_max_duration = None

            def check_cancellation():
                return cancel_event.is_set()

            def download_update(downloaded, total):
                worker_state["phase"] = "download"
                worker_state["downloaded"] = int(downloaded) if isinstance(downloaded, (int, float)) else 0
                worker_state["total"] = int(total) if isinstance(total, (int, float)) else max_samples
                # Update elapsed time for ETA calculation
                worker_state["elapsed_time"] = time_module.time() - start_time

            worker_state["phase"] = "download"

            download_all_call_recordings(
                ready_url,
                agent="all users",
                campaign_name=campaign_name,
                start_date=start_date,
                end_date=end_date,
                max_samples=max_samples,
                update_callback=download_update,
                disposition=selected_dispositions,
                min_duration=effective_min_duration,
                max_duration=effective_max_duration,
                username=current_username_local,
                readymode_user=rm_user,
                readymode_pass=rm_pass,
                cancellation_callback=check_cancellation,
                driver_storage=driver_storage,
            )

            if cancel_event.is_set():
                worker_state["status"] = "cancelled"
                return

            worker_state["phase"] = "analyze"

            dialer_name = extract_dialer_name_from_url(ready_url)

            # Use absolute paths from config to ensure correct location
            from config import RECORDINGS_ROOT
            search_paths = [
                RECORDINGS_ROOT / "Campaign" / current_username_local,
                RECORDINGS_ROOT / "Campaign",
                RECORDINGS_ROOT,
            ]

            target_folder = None
            files = []

            candidate_dirs = []
            for base_path in search_paths:
                if not base_path.exists():
                    continue
                for entry in base_path.iterdir():
                    if not entry.is_dir():
                        continue
                    if campaign_name.lower() in entry.name.lower():
                        mp3_files = list(entry.rglob("*.mp3"))
                        if mp3_files:
                            candidate_dirs.append((entry.stat().st_mtime, entry, mp3_files))

            if candidate_dirs:
                candidate_dirs.sort(key=lambda x: x[0], reverse=True)
                _, target_folder, files = candidate_dirs[0]

            if not files:
                worker_state["status"] = "error"
                worker_state["error_type"] = "no_files"
                worker_state["error_message"] = f"No MP3 files found for campaign '{campaign_name}' in any search location"
                return

            metadata = {
                "dialer_name": dialer_name,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }

            df = None

            try:
                if audit_type == "Heavy Audit":
                    def analyze_progress(done, total, message=None):
                        worker_state["phase"] = "analyze"
                        worker_state["downloaded"] = int(done) if isinstance(done, (int, float)) else 0
                        worker_state["total"] = int(total) if isinstance(total, (int, float)) else len(files)
                        if message:
                            worker_state["message"] = message
                        else:
                            worker_state["message"] = f"Analyzing: {worker_state['downloaded']}/{worker_state['total']}"
                        # Update elapsed time for ETA calculation
                        worker_state["elapsed_time"] = time_module.time() - start_time
                        # Allow cancellation during analysis
                        if cancel_event.is_set():
                            raise KeyboardInterrupt("cancelled by user during analysis")

                    df = batch_analyze_folder_fast(
                        str(target_folder),
                        progress_callback=analyze_progress,
                        additional_metadata=metadata,
                        show_all_results=True,
                    )
                    if not df.empty:
                        df["Audit Type"] = "Heavy Audit"
                else:
                    processed_count = 0
                    total_files = len(files)

                    def lite_progress_callback(completed, total, message=None):
                        nonlocal processed_count
                        processed_count += 1
                        worker_state["phase"] = "analyze"
                        worker_state["downloaded"] = int(processed_count)
                        worker_state["total"] = int(total_files)
                        if message:
                            worker_state["message"] = message
                        else:
                            worker_state["message"] = f"Analyzing: {worker_state['downloaded']}/{worker_state['total']}"
                        # Update elapsed time for ETA calculation
                        worker_state["elapsed_time"] = time_module.time() - start_time
                        # Allow cancellation during lite analysis
                        if cancel_event.is_set():
                            raise KeyboardInterrupt("cancelled by user during analysis")

                    df = batch_analyze_folder_lite(
                        str(target_folder),
                        progress_callback=lite_progress_callback,
                        additional_metadata=metadata,
                    )
                    if not df.empty:
                        df["Audit Type"] = "Lite Audit"
            except Exception as e:
                error_msg = f"Error during {audit_type} processing: {str(e)}\n\n{traceback.format_exc()}"
                worker_state["status"] = "error"
                worker_state["error_type"] = "processing"
                worker_state["error_message"] = error_msg
                return

            if df is None:
                worker_state["status"] = "error"
                worker_state["error_type"] = "processing"
                worker_state["error_message"] = "No analysis results DataFrame created"
                return

            worker_state["record_count"] = int(len(df))

            if not df.empty:
                dashboard_manager.save_campaign_audit_results(
                    df, campaign_name, current_username_local
                )
                dashboard_manager.increment_daily_download_count(
                    current_username_local, len(df)
                )

            worker_state["status"] = "completed"
            worker_state["df_empty"] = bool(df.empty)
        except KeyboardInterrupt:
            worker_state["status"] = "cancelled"
        except ReadyModeLoginError as login_error:
            worker_state["status"] = "error"
            worker_state["error_type"] = "login"
            worker_state["error_message"] = str(login_error)
        except ReadyModeNoCallsError as no_calls_error:
            worker_state["status"] = "error"
            worker_state["error_type"] = "no_calls"
            worker_state["error_message"] = str(no_calls_error)
        except Exception as e:
            error_message = str(e)
            lower = error_message.lower()
            worker_state["status"] = "error"
            if "[!] campaign" in lower and "not found" in lower:
                worker_state["error_type"] = "campaign_not_found"
            elif "NO_AVAILABLE_ADMIN_LICENSES" in error_message:
                worker_state["error_type"] = "license"
            elif any(
                keyword in lower
                for keyword in [
                    "no such window",
                    "web view not found",
                    "chrome",
                    "webdriver",
                    "session info",
                    "stacktrace",
                    "gethandleverifier",
                ]
            ):
                worker_state["error_type"] = "browser"
            else:
                worker_state["error_type"] = "generic"
            worker_state["error_message"] = error_message
            worker_state["traceback"] = traceback.format_exc()
        finally:
            # Playwright handles browser cleanup automatically
            # No manual process management or driver.quit() needed
            logger.info("Download worker completed - Playwright handles cleanup")

    # Progress tracker helper
    def _create_progress_tracker():
        status_text = st.empty()
        progress_bar = st.progress(0)

        def update_progress(downloaded, total):
            try:
                ratio = downloaded / total if total else 0
            except Exception:
                ratio = float(downloaded)
            progress_bar.progress(min(max(ratio, 0.0), 1.0))
            if (
                isinstance(downloaded, (int, float))
                and isinstance(total, (int, float))
                and total
            ):
                status_text.text(
                    f"Processing: {int(min(downloaded, total))}/{int(total)}"
                )

        return status_text, progress_bar, update_progress

    # Create tabs - using default styling to avoid empty space

    # Create tabs based on user role - Upload & Analyze only for Owner
    if current_user_role == user_manager.ROLE_OWNER:
        tab_upload, tab_agent, tab_campaign = st.tabs(
            ["Upload & Analyze", "Agent Audit", "Campaign Audit"]
        )
    elif current_user_role == user_manager.ROLE_ADMIN:
        tab_agent, tab_campaign = st.tabs(["Agent Audit", "Campaign Audit"])
        tab_upload = None
    else:
        # Auditor and any other non-owner/admin roles: show Agent Audit without visible tabs
        # Use a simple container instead of st.tabs so no tab bar is rendered.
        tab_agent = st.container()
        tab_campaign = None
        tab_upload = None

    # --- Upload & Analyze Tab (Owner only) ---
    if current_user_role == user_manager.ROLE_OWNER and tab_upload is not None:
        with tab_upload:
            # Upload & Analyze card removed as requested

            # Detection Matrix
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    """
                <div class="modern-card" style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%); border-color: rgba(239, 68, 68, 0.3);">
                    <div style="color: #f87171; font-weight: 600; margin-bottom: 0.5rem;">Releasing Detection</div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">Identifies calls where agent speech is completely absent</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    """
                <div class="modern-card" style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.1) 100%); border-color: rgba(245, 158, 11, 0.3);">
                    <div style="color: #fbbf24; font-weight: 600; margin-bottom: 0.5rem;">Late Hello Detection</div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">Flags calls with agent response time > 4 seconds</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            # File Upload Section
            st.subheader("Audio File Input")
            uploaded_files = st.file_uploader(
                "Select MP3/WAV files for processing",
                type=["mp3", "wav"],
                accept_multiple_files=True,
                help="Supported formats: MP3, WAV. Maximum batch size: 1000 files",
            )

            # File Processing Status
            if uploaded_files:
                st.info(f"Files Queued: {len(uploaded_files)}")

            # Campaign Name Input (Optional)
            st.subheader("Save Options")
            campaign_name = st.text_input(
                "Campaign Name (optional)",
                key="upload_campaign_name",
                placeholder=(
                    "Enter campaign name to save as campaign audit data"
                ),
                help=(
                    "If provided, results will be saved under campaign audit. "
                    "Leave blank for agent audit."
                ),
            )

            # Processing Action
            analyze_button = st.button(
                "Analyze Files", disabled=not uploaded_files, key="upload_analyze_btn"
            )

            # Debug option to show only flagged calls
            show_flagged_only = st.checkbox(
                "Show only flagged calls",
                value=False,
                help="Only show calls with detected issues (hide clean calls)",
            )

            if analyze_button:
                # Check system resources before starting
                if not check_system_resources():
                    st.warning(
                        "System resources may be insufficient for transcription. "
                        "Results may be incomplete."
                    )
                
                # Create persistent temp directory
                from config import RECORDINGS_ROOT
                
                base_temp = RECORDINGS_ROOT if RECORDINGS_ROOT and Path(RECORDINGS_ROOT).exists() else tempfile.gettempdir()
                upload_dir = Path(base_temp) / "Uploads" / current_username / f"req_{int(time.time())}"
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                # Save uploaded files
                for f in uploaded_files:
                    (upload_dir / f.name).write_bytes(f.getbuffer())
                
                # Initialize worker state
                user_api_key, api_key_source = _get_user_assemblyai_api_key(current_username)
                st.session_state.upload_cancel_event.clear()
                st.session_state.upload_worker_state = {
                    "status": "running",
                    "message": "Starting analysis...",
                    "downloaded": 0,
                    "total": len(uploaded_files),
                    "df": None,
                    "start_time": time.time(),
                    "elapsed_time": 0,
                }
                
                # Start background thread
                worker_thread = threading.Thread(
                    target=_run_upload_audit_worker,
                    args=(
                        str(upload_dir),
                        campaign_name,
                        current_username,
                        user_api_key,
                        api_key_source,
                        st.session_state.upload_worker_state,
                        st.session_state.upload_cancel_event,
                        show_flagged_only,
                    ),
                    daemon=True
                )
                st.session_state.upload_worker_thread = worker_thread
                worker_thread.start()
                st.rerun()

                if "upload_results" in st.session_state:
                    df = st.session_state["upload_results"]

                    if not df.empty:
                        st.dataframe(df, width="stretch")
                    else:
                        st.dataframe(df, width="stretch")

                    # Download options - CSV only (Excel removed per user request)
                    st.download_button(
                        label="Download CSV",
                        data=df.to_csv(index=False).encode("utf-8"),
                        file_name="analysis_results.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("No files were processed successfully.")

    # --- Agent Audit Tab ---
    with tab_agent:
        # Configuration Sections
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Agent Configuration")
            ready_url = st.text_input(
                "ReadyMode URL", value=READYMODE_URL, key="agent_url"
            )
            agent_name = st.text_input(
                "Agent Identifier",
                value="All users",
                key="agent_name",
                placeholder="Enter exact agent name",
            )

        with col2:
            st.subheader("Date Parameters")
            start_date = st.date_input(
                "Start Date", value=date.today(), key="agent_start"
            )
            end_date = st.date_input("End Date", value=date.today(), key="agent_end")

        # Advanced Filters
        st.subheader("Advanced Filters")

        col3, col4 = st.columns(2)

        with col3:
            dispositions_options = [
                "Spanish Speaker",
                "DNC - Unknown",
                "Unknown",
                "DNC - Decision Maker",
                "Decision Maker - Lead",
                "Callback",
                "Wrong Number",
                "Voicemail",
                "Decision Maker - NYI",
                "Dead Call",
                "Not logged",
                "Do Not Call",
                "Not Available",
                "Not interested",
            ]
            selected_dispositions = st.multiselect(
                "Call Dispositions",
                options=dispositions_options,
                key="agent_dispositions",
            )

        with col4:
            duration_option = st.selectbox(
                "Duration Filter",
                [
                    "All durations",
                    "Less than 30 seconds",
                    "30 seconds - 1:00",
                    "1:00 to 10:00",
                    "Greater than...",
                    "Less than...",
                ],
                index=0,
                key="agent_duration_filter",
            )

        # Handle duration filter logic
        min_duration, max_duration = None, None
        if duration_option == "Less than 30 seconds":
            max_duration = 30
        elif duration_option == "30 seconds - 1:00":
            min_duration, max_duration = 30, 60
        elif duration_option == "1:00 to 10:00":
            min_duration, max_duration = 60, 600
        elif duration_option == "Greater than...":
            min_duration = st.number_input(
                "Greater than (seconds)",
                min_value=0,
                value=60,
                key="agent_min_duration",
            )
        elif duration_option == "Less than...":
            max_duration = st.number_input(
                "Less than (seconds)",
                min_value=1,
                value=30,
                key="agent_max_duration",
            )

        # Sample Configuration
        st.subheader("Processing Parameters")
        num_recordings = st.number_input(
            "Number of samples",
            min_value=1,
            max_value=2000,
            value=50,
            key="agent_num",
            help="Number of recordings to analyze for statistical significance",
        )

        max_samples = int(num_recordings) if num_recordings else 50

        # Create the buttons first
        col_heavy, col_lite = st.columns(2)
        with col_heavy:
            heavy_audit_button = st.button("Heavy Audit", key="heavy_audit_btn")
        with col_lite:
            lite_audit_button = st.button("Lite Audit", key="lite_audit_btn")

        # Add custom CSS after the buttons are created
        st.markdown(
            """
        <style>
            /* Target only the specific buttons by their parent containers */
            div[class*='stElementContainer'].st-key-heavy_audit_btn button,
            div[class*='stElementContainer'].st-key-lite_audit_btn button {
                border: none !important;
                border-radius: 12px !important;
                padding: 1rem 2rem !important;
                font-size: 0.95rem !important;
                font-weight: 600 !important;
                cursor: pointer !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                text-transform: uppercase !important;
                letter-spacing: 0.05em !important;
                position: relative !important;
                overflow: hidden !important;
                width: 100% !important;
            }

            /* Heavy Audit Button - Deep Crimson */
            div[class*='stElementContainer'].st-key-heavy_audit_btn button {
                background: linear-gradient(135deg, #B83227 0%, #8E1C13 100%) !important;
                color: white !important;
                box-shadow: 0 0 12px 0 rgba(184, 50, 39, 0.5) !important;
            }

            div[class*='stElementContainer'].st-key-heavy_audit_btn button:hover {
                background: linear-gradient(135deg, #A32018 0%, #6E0F0A 100%) !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 0 15px 0 rgba(184, 50, 39, 0.6) !important;
            }

            div[class*='stElementContainer'].st-key-heavy_audit_btn button:active {
                transform: translateY(0px) !important;
                box-shadow: 0 0 8px 0 rgba(184, 50, 39, 0.4) !important;
            }

            /* Lite Audit Button - Teal Gradient */
            div[class*='stElementContainer'].st-key-lite_audit_btn button {
                background: linear-gradient(135deg, #3498DB 0%, #2980B9 100%) !important;
                color: white !important;
                box-shadow: 0 4px 14px 0 rgba(52, 152, 219, 0.3) !important;
            }

            div[class*='stElementContainer'].st-key-lite_audit_btn button:hover {
                background: linear-gradient(135deg, #2980B9 0%, #2471A3 100%) !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 20px 0 rgba(52, 152, 219, 0.4) !important;
            }

            div[class*='stElementContainer'].st-key-lite_audit_btn button:active {
                transform: translateY(0px) !important;
                box-shadow: 0 2px 8px 0 rgba(52, 152, 219, 0.3) !important;
            }

            /* Shine effect for both buttons */
            div[class*='stElementContainer'].st-key-heavy_audit_btn button::before,
            div[class*='stElementContainer'].st-key-lite_audit_btn button::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
                transition: left 0.5s;
            }

            div[class*='stElementContainer'].st-key-heavy_audit_btn button:hover::before,
            div[class*='stElementContainer'].st-key-lite_audit_btn button:hover::before {
                left: 100%;
            }
        </style>
        <script>
        // Debug: Log button elements to console
        console.log('Heavy Audit Button:', document.querySelector('button[data-testid="baseButton-heavy_audit_btn"]'));
        console.log('Lite Audit Button:', document.querySelector('button[data-testid="baseButton-lite_audit_btn"]'));
        </script>
        """,
            unsafe_allow_html=True,
        )

        # Progress display for background worker
        worker_state = st.session_state.agent_worker_state
        if worker_state and worker_state.get("status") in ("running", "starting"):
            if AUTOREFRESH_AVAILABLE:
                st_autorefresh(interval=2000, key="agent_audit_autorefresh", limit=None)
            
            st.markdown("---")
            st.markdown(f"## AGENT AUDIT STATUS: {agent_name}")
            
            phase = worker_state.get("phase", "")
            message = worker_state.get("message", "")
            downloaded = worker_state.get("downloaded", 0)
            total = worker_state.get("total", 0)
            
            # Display phase information
            phase_display = "Downloading calls..." if phase == "download" else "Analyzing calls..."
            st.info(f"🔄 **{phase_display}** - {message}")
            
            # Display progress bar
            progress_value = 0.0
            if total and total > 0:
                progress_value = max(0.0, min(float(downloaded) / float(total), 1.0))
            st.progress(progress_value)
            
            # Cancel button
            if st.button("Cancel Audit", key="cancel_agent_audit_worker"):
                st.session_state.agent_cancel_event.set()
                st.warning("Stop signal sent. Finishing current file...")
            
            st.markdown("---")
            
        elif worker_state and worker_state.get("status") == "completed":
            st.success(f"Audit completed! Processed {worker_state.get('record_count', 0)} records.")
            if st.button("Clear and Restart", key="clear_agent_audit_success"):
                st.session_state.agent_worker_state["status"] = "idle"
                st.rerun()
                
        elif worker_state and worker_state.get("status") == "error":
            st.error(f"Audit failed: {worker_state.get('error_message')}")
            if st.button("Clear and Retry", key="clear_agent_audit_error"):
                st.session_state.agent_worker_state["status"] = "idle"
                st.rerun()

        # Progress display for Upload background worker
        upload_worker_state = st.session_state.upload_worker_state
        if upload_worker_state and upload_worker_state.get("status") in ("running", "starting"):
            if AUTOREFRESH_AVAILABLE:
                st_autorefresh(interval=2000, key="upload_audit_autorefresh", limit=None)
            
            st.markdown("---")
            st.markdown("## UPLOAD ANALYSIS STATUS")
            
            message = upload_worker_state.get("message", "")
            downloaded = upload_worker_state.get("downloaded", 0)
            total = upload_worker_state.get("total", 0)
            
            st.info(f"🔄 **Processing uploaded files...** - {message}")
            
            # Display progress bar
            progress_value = 0.0
            if total and total > 0:
                progress_value = max(0.0, min(float(downloaded) / float(total), 1.0))
            st.progress(progress_value)
            
            # Cancel button
            if st.button("Cancel Upload Analysis", key="cancel_upload_audit_worker"):
                st.session_state.upload_cancel_event.set()
                st.warning("Stop signal sent. Finishing current file...")
            
            st.markdown("---")
            
        elif upload_worker_state and upload_worker_state.get("status") == "completed":
            df = upload_worker_state.get("df")
            if df is not None:
                st.session_state["upload_results"] = df
                st.success(f"Analysis completed! Processed {len(df)} files.")
                # Automatically move results to session state and reset worker
                st.session_state.upload_worker_state["status"] = "idle"
                st.rerun()
                
        elif upload_worker_state and upload_worker_state.get("status") == "error":
            st.error(f"Analysis failed: {upload_worker_state.get('error_message')}")
            if st.button("Clear and Retry", key="clear_upload_audit_error"):
                st.session_state.upload_worker_state["status"] = "idle"
                st.rerun()

        # Check for stale cancelled state and clear it (runs on every page load, not just button clicks)
        if st.session_state.get("agent_audit_cancelled_status", False):
            # Clear cancelled state if it exists (user may have navigated away after cancelling)
            st.session_state.audit_in_progress = False
            st.session_state.agent_audit_driver_storage = {}
            st.session_state.agent_audit_cancelled = False
            st.session_state.agent_audit_cancelled_status = False
            # Clear any remaining state
            for key in [
                "audit_status_placeholder",
                "audit_progress_placeholder",
                "audit_progress_downloaded",
                "audit_progress_total",
                "audit_download_status",
                "audit_in_progress_state",
            ]:
                if key in st.session_state:
                    del st.session_state[key]
        
        # Also check for stale audit_in_progress flag (no driver but flag is set)
        if (
            st.session_state.get("audit_in_progress", False)
            and "driver" not in st.session_state.get("agent_audit_driver_storage", {})
            and not st.session_state.get("agent_audit_cancelled_status", False)
        ):
            # Stale flag exists - clear it
            st.session_state.audit_in_progress = False
            if "agent_audit_driver_storage" in st.session_state:
                st.session_state.agent_audit_driver_storage = {}
            # Clear progress placeholders
            for key in [
                "audit_status_placeholder",
                "audit_progress_placeholder",
                "audit_progress_downloaded",
                "audit_progress_total",
                "audit_download_status",
                "audit_in_progress_state",
            ]:
                if key in st.session_state:
                    del st.session_state[key]

        # Check which button was clicked
        audit_mode = None
        if heavy_audit_button:
            audit_mode = "heavy"
        elif lite_audit_button:
            audit_mode = "lite"

        # Handle button click - Start processing
        if audit_mode:
            # Check if audit was cancelled (clear state if cancelled status exists)
            if st.session_state.get("agent_audit_cancelled_status", False):
                st.session_state.audit_in_progress = False
                st.session_state.agent_audit_driver_storage = {}
                st.session_state.agent_audit_cancelled = False
                st.session_state.agent_audit_cancelled_status = False
                # Clear any remaining state
                for key in [
                    "audit_status_placeholder",
                    "audit_progress_placeholder",
                    "audit_progress_downloaded",
                    "audit_progress_total",
                    "audit_download_status",
                    "audit_in_progress_state",
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
            
            # Check if audit is actually running by verifying driver storage
            audit_really_running = (
                st.session_state.get("audit_in_progress", False)
                and "driver" in st.session_state.get("agent_audit_driver_storage", {})
            )

            if audit_really_running:
                st.warning(
                    "Another audit is already running. Please wait for it to finish "
                    "before starting a new one."
                )
            elif st.session_state.get("audit_in_progress", False):
                # Flag is set but no driver exists - clear the stale flag (likely from cancelled audit)
                st.session_state.audit_in_progress = False
                # Also clear any cancelled status and related state
                if "agent_audit_cancelled_status" in st.session_state:
                    del st.session_state.agent_audit_cancelled_status
                if "agent_audit_cancelled" in st.session_state:
                    st.session_state.agent_audit_cancelled = False
                if "agent_audit_driver_storage" in st.session_state:
                    st.session_state.agent_audit_driver_storage = {}
                # Clear progress placeholders
                for key in [
                    "audit_status_placeholder",
                    "audit_progress_placeholder",
                    "audit_progress_downloaded",
                    "audit_progress_total",
                    "audit_download_status",
                    "audit_in_progress_state",
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.info(
                    "Cleared stale audit flag. You can start a new audit now."
                )
            else:
                st.session_state.audit_in_progress = True
                # Show immediate feedback that audit is starting
                mode_name = "Heavy" if audit_mode == "heavy" else "Lite"
                # Only show the starting message for Heavy audits, not Lite
                if audit_mode == "heavy":
                    st.info(f"Starting {mode_name} Audit...")

                if not agent_name:
                    st.error("Please enter an agent name.")
                    # Reset flags if validation fails
                    st.session_state.audit_in_progress = False
                else:
                    if not READYMODE_AVAILABLE:
                        st.warning("**ReadyMode Automation Unavailable**")
                        st.markdown(
                            """
                        **Alternative Options:**
                        - **Upload & Analyze Tab**: Upload your MP3 files directly for analysis
                        - **Manual Export**: Export MP3s from ReadyMode and upload them here
                        - **Enterprise Setup**: Contact your administrator for full ReadyMode integration

                        The core audio analysis functionality is fully available via file upload!
                        """
                        )
                        # Reset flags if automation unavailable
                        st.session_state.audit_in_progress = False
                    else:
                        # Check daily download limit
                        current_username_local = st.session_state.get(
                            "username", "Auditor1"
                        )
                        can_download, limit_message = dashboard_manager.check_daily_download_limit(
                            current_username_local, max_samples
                        )

                        if not can_download:
                            st.error("Daily Download Limit Exceeded")
                            st.warning(limit_message)

                            # Show usage info
                            usage_info = dashboard_manager.get_daily_usage_info(
                                current_username_local
                            )
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric(
                                    "Used Today",
                                    f"{usage_info['current_count']}/{usage_info['daily_limit']}",
                                )
                            with col2:
                                st.metric("Remaining", usage_info["remaining"])
                            with col3:
                                st.metric(
                                    "Usage", f"{usage_info['usage_percent']:.1f}%"
                                )
                            # Reset flags if limit exceeded
                            st.session_state.audit_in_progress = False
                            return

                        # Get user-specific ReadyMode credentials
                        rm_user, rm_pass = get_user_readymode_credentials(
                            current_username_local
                        )

                    # OLD VERSION: Simple progress tracker
                    st.markdown("---")
                    st.markdown(f"## AGENT AUDIT: {agent_name}")

                    # Check if audit was cancelled (similar to Campaign Audit's status == "cancelled" check)
                    if st.session_state.get("agent_audit_cancelled_status", False):
                        st.warning("Agent Audit cancelled. Chrome browser closed.")
                        st.session_state.audit_in_progress = False
                        st.session_state.agent_audit_driver_storage = {}
                        st.session_state.agent_audit_cancelled = False
                        st.session_state.agent_audit_cancelled_status = False
                        # Clear any remaining state
                        for key in [
                            "audit_status_placeholder",
                            "audit_progress_placeholder",
                            "audit_progress_downloaded",
                            "audit_progress_total",
                            "audit_download_status",
                            "audit_in_progress_state",
                        ]:
                            if key in st.session_state:
                                del st.session_state[key]
                        return  # Exit early to return to initial screen

                    # Check if we're recovering from a rerun mid-operation
                    if (
                        "audit_in_progress_state" in st.session_state
                        and "audit_progress_downloaded" in st.session_state
                    ):
                        # Restore progress display after rerun
                        restored_progress = st.session_state.audit_progress_downloaded
                        restored_total = (
                            st.session_state.audit_progress_total
                            if "audit_progress_total" in st.session_state
                            else restored_progress
                        )
                        st.info(
                            f"🔄 Audit in progress: {restored_progress}/{restored_total if restored_total else '?'} files processed. Continuing..."
                        )

                        # Get user-specific ReadyMode credentials
                        rm_user, rm_pass = get_user_readymode_credentials(current_username_local)
                        
                        # Initialize and start background worker
                        st.session_state.agent_cancel_event.clear()
                        user_api_key, api_key_source = _get_user_assemblyai_api_key(current_username_local)
                        
                        st.session_state.agent_worker_state = {
                            "status": "running",
                            "phase": "download",
                            "downloaded": 0,
                            "total": max_samples,
                            "message": "Starting...",
                            "start_time": time.time(),
                            "elapsed_time": 0,
                        }

                        # Clear driver storage before starting fresh
                        st.session_state.agent_audit_driver_storage = {}

                        # Start background thread
                        worker_thread = threading.Thread(
                            target=_run_agent_audit_worker,
                            args=(
                                READYMODE_URL,
                                agent_name,
                                start_date,
                                end_date,
                                selected_dispositions,
                                min_duration,
                                max_duration,
                                max_samples,
                                audit_mode,
                                current_username_local,
                                rm_user,
                                rm_pass,
                                st.session_state.agent_worker_state,
                                st.session_state.agent_cancel_event,
                                st.session_state.agent_audit_driver_storage,
                                user_api_key,
                                api_key_source
                            ),
                            daemon=True
                        )
                        st.session_state.agent_worker_thread = worker_thread
                        worker_thread.start()
                        st.rerun()



    # --- Campaign Audit Tab ---
    if current_user_role in [user_manager.ROLE_OWNER, user_manager.ROLE_ADMIN]:
        with tab_campaign:
            # Campaign Audit section (heading and description removed as requested)

            # Configuration Sections
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Campaign Configuration")
                ready_url = st.text_input(
                    "ReadyMode URL", value=READYMODE_URL, key="camp_url"
                )
                campaign_name = st.text_input(
                    "Campaign Name",
                    key="camp_name",
                    placeholder="Enter exact campaign name",
                )

            with col2:
                st.subheader("Date Parameters")
                start_date = st.date_input(
                    "Start Date", value=date.today(), key="camp_start"
                )
                end_date = st.date_input(
                    "End Date", value=date.today(), key="camp_end"
                )

            # Advanced Filters
            st.subheader("Advanced Filters")

            col3, col4 = st.columns(2)

            with col3:
                dispositions_options = [
                    "Spanish Speaker",
                    "DNC - Unknown",
                    "Unknown",
                    "DNC - Decision Maker",
                    "Decision Maker - Lead",
                    "Callback",
                    "Wrong Number",
                    "Voicemail",
                    "Decision Maker - NYI",
                    "Dead Call",
                    "Not logged",
                    "Do Not Call",
                    "Not Available",
                    "Not interested",
                ]
                selected_dispositions = st.multiselect(
                    "Call Dispositions",
                    options=dispositions_options,
                    key="camp_dispositions",
                    placeholder="Choose all options",
                )

            with col4:
                duration_option = st.selectbox(
                    "Duration Filter",
                    [
                        "All durations",
                        "Less than 30 seconds",
                        "30 seconds - 1:00",
                        "1:00 to 10:00",
                        "Greater than...",
                        "Less than...",
                    ],
                    index=0,
                    key="camp_duration_filter",
                )

            # Handle duration filter logic
            min_duration, max_duration = None, None
            if duration_option == "Less than 30 seconds":
                max_duration = 30
            elif duration_option == "30 seconds - 1:00":
                min_duration, max_duration = 30, 60
            elif duration_option == "1:00 to 10:00":
                min_duration, max_duration = 60, 600
            elif duration_option == "Greater than...":
                min_duration = st.number_input(
                    "Greater than (seconds)",
                    min_value=0,
                    value=60,
                    key="camp_min_duration",
                )
            elif duration_option == "Less than...":
                max_duration = st.number_input(
                    "Less than (seconds)",
                    min_value=1,
                    value=30,
                    key="camp_max_duration",
                )

            # Sample Configuration
            st.subheader("Processing Parameters")
            num_recordings = st.number_input(
                "Number of samples",
                min_value=1,
                max_value=2000,
                value=50,
                key="camp_num",
                help=(
                    "Number of recordings to analyze for statistical significance"
                ),
            )

            max_samples = int(num_recordings) if num_recordings else 50

            # Create the buttons first (Heavy/Lite for Campaign)
            col_heavy, col_lite = st.columns(2)
            with col_heavy:
                heavy_campaign_button = st.button(
                    "Heavy Audit", key="heavy_campaign_btn"
                )
            with col_lite:
                lite_campaign_button = st.button("Lite Audit", key="lite_campaign_btn")

            # Add custom CSS for campaign buttons (match Agent Audit styling)
            st.markdown(
                """
            <style>
                /* Target campaign audit buttons - match Agent Audit */
                div[class*='stElementContainer'].st-key-heavy_campaign_btn button,
                div[class*='stElementContainer'].st-key-lite_campaign_btn button {
                    border: none !important;
                    border-radius: 12px !important;
                    padding: 1rem 2rem !important;
                    font-size: 0.95rem !important;
                    font-weight: 600 !important;
                    cursor: pointer !important;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                    text-transform: uppercase !important;
                    letter-spacing: 0.05em !important;
                    position: relative !important;
                    overflow: hidden !important;
                    width: 100% !important;
                }

                /* Heavy Audit Button - Deep Crimson */
                div[class*='stElementContainer'].st-key-heavy_campaign_btn button {
                    background: linear-gradient(135deg, #B83227 0%, #8E1C13 100%) !important;
                    color: white !important;
                    box-shadow: 0 0 12px 0 rgba(184, 50, 39, 0.5) !important;
                }

                div[class*='stElementContainer'].st-key-heavy_campaign_btn button:hover {
                    background: linear-gradient(135deg, #A32018 0%, #6E0F0A 100%) !important;
                    transform: translateY(-2px) !important;
                    box-shadow: 0 0 15px 0 rgba(184, 50, 39, 0.6) !important;
                }

                div[class*='stElementContainer'].st-key-heavy_campaign_btn button:active {
                    transform: translateY(0px) !important;
                    box-shadow: 0 0 8px 0 rgba(184, 50, 39, 0.4) !important;
                }

                /* Lite Audit Button - Teal Gradient */
                div[class*='stElementContainer'].st-key-lite_campaign_btn button {
                    background: linear-gradient(135deg, #3498DB 0%, #2980B9 100%) !important;
                    color: white !important;
                    box-shadow: 0 4px 14px 0 rgba(52, 152, 219, 0.3) !important;
                }

                div[class*='stElementContainer'].st-key-lite_campaign_btn button:hover {
                    background: linear-gradient(135deg, #2980B9 0%, #2471A3 100%) !important;
                    transform: translateY(-2px) !important;
                    box-shadow: 0 6px 20px 0 rgba(52, 152, 219, 0.4) !important;
                }

                div[class*='stElementContainer'].st-key-lite_campaign_btn button:active {
                    transform: translateY(0px) !important;
                    box-shadow: 0 2px 8px 0 rgba(52, 152, 219, 0.3) !important;
                }

                /* Shine effect for both buttons */
                div[class*='stElementContainer'].st-key-heavy_campaign_btn button::before,
                div[class*='stElementContainer'].st-key-lite_campaign_btn button::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: -100%;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                    transition: left 0.5s;
                }

                div[class*='stElementContainer'].st-key-heavy_campaign_btn button:hover::before,
                div[class*='stElementContainer'].st-key-lite_campaign_btn button:hover::before {
                    left: 100%;
                }
            </style>
            """,
                unsafe_allow_html=True,
            )

            # Initialize background worker state for Campaign Audit
            if "campaign_worker_state" not in st.session_state:
                st.session_state.campaign_worker_state = None
            if "campaign_cancel_event" not in st.session_state:
                st.session_state.campaign_cancel_event = None
            if "campaign_worker_thread" not in st.session_state:
                st.session_state.campaign_worker_thread = None
            if "campaign_audit_driver_storage" not in st.session_state:
                st.session_state.campaign_audit_driver_storage = {}

            worker_state = st.session_state.campaign_worker_state
            cancel_event = st.session_state.campaign_cancel_event

            # Progress tracker helper (simple, per-run) driven by worker_state
            if worker_state:
                status = worker_state.get("status", "")
                phase = worker_state.get("phase", "")
                downloaded = worker_state.get("downloaded", 0)
                total = worker_state.get("total", 0)

                progress_value = 0.0
                if isinstance(downloaded, (int, float)) and isinstance(total, (int, float)) and total:
                    try:
                        progress_value = max(0.0, min(float(downloaded) / float(total), 1.0))
                    except Exception:
                        progress_value = 0.0

                st.markdown("---")
                st.markdown("## CAMPAIGN AUDIT STATUS")

                # Only show progress bar while audit is actively running
                if status in ("running", "starting"):
                    # Enable auto-refresh every 2 seconds when worker is running
                    # This ensures the UI updates in real-time as the background worker progresses
                    # The autorefresh will automatically rerun the script, picking up updated worker_state values
                    # This is the key fix: without this, Streamlit doesn't know to rerun when session state
                    # changes from a background thread, so the progress bar stays frozen
                    if AUTOREFRESH_AVAILABLE:
                        st_autorefresh(interval=2000, key="campaign_audit_autorefresh", limit=None)
                    else:
                        # Fallback: Show message if autorefresh not available
                        st.warning("⚠️ Auto-refresh not available. Progress updates may be delayed. Install: `pip install streamlit-autorefresh`")
                    
                    # Display phase/message information
                    current_message = worker_state.get("message")
                    phase_display = "Downloading calls..." if phase == "download" else "Analyzing calls..."
                    display_text = current_message if current_message else phase_display
                    st.info(f"🔄 **{display_text}**")
                    
                    # Display progress bar with real-time updates
                    progress_bar = st.progress(progress_value)
                    
                    # Display detailed progress information
                    if isinstance(downloaded, (int, float)) and isinstance(total, (int, float)) and total:
                        percentage = (downloaded / total * 100) if total > 0 else 0
                        st.markdown(f"**Progress:** {int(downloaded)}/{int(total)} items processed ({percentage:.1f}%)")
                        
                        # Calculate and display ETA if we have progress
                        if downloaded > 0 and phase == "analyze":
                            # Estimate time remaining based on current progress
                            elapsed_time = worker_state.get("elapsed_time", 0)
                            if elapsed_time > 0:
                                avg_time_per_item = elapsed_time / downloaded
                                remaining_items = total - downloaded
                                eta_seconds = avg_time_per_item * remaining_items
                                eta_minutes = int(eta_seconds / 60)
                                eta_secs = int(eta_seconds % 60)
                                st.caption(f"⏱️ Estimated time remaining: {eta_minutes}m {eta_secs}s")
                    else:
                        st.markdown(f"**Progress:** {int(downloaded)} items processed")

                # Cancel button for Campaign Audit (affects background worker)
                if status in ("running", "starting"):
                    cancel_col, _ = st.columns([1, 5])
                    with cancel_col:
                        if st.button("Cancel", key="cancel_campaign_audit", type="secondary"):
                            # Signal background worker to stop
                            if cancel_event is not None:
                                cancel_event.set()
                            # Immediately reflect cancelled state in UI
                            worker_state["status"] = "cancelled"
                            # Force a rerun so UI reflects cancelled state right away
                            st.rerun()

                # Handle completion and errors
                if status == "completed":
                    record_count = worker_state.get("record_count", 0)
                    df_empty = worker_state.get("df_empty", False)
                    audit_type_display = worker_state.get("audit_type", "").upper() or "AUDIT"
                    st.success(
                        f"CAMPAIGN {audit_type_display} COMPLETE! Processed {record_count if not df_empty else 0} calls successfully!"
                    )
                    if not df_empty:
                        st.info(
                            f"Results saved to dashboard: {record_count} calls analyzed"
                        )
                    st.session_state.audit_in_progress = False
                    # Clear worker objects so UI returns to idle state
                    st.session_state.campaign_worker_state = None
                    st.session_state.campaign_cancel_event = None
                    st.session_state.campaign_worker_thread = None

                elif status == "cancelled":
                    st.warning("Campaign Audit cancelled. Chrome browser closed.")
                    st.session_state.audit_in_progress = False
                    st.session_state.campaign_worker_state = None
                    st.session_state.campaign_cancel_event = None
                    st.session_state.campaign_worker_thread = None

                elif status == "error":
                    error_type = worker_state.get("error_type", "generic")
                    error_message = worker_state.get("error_message", "Unknown error")
                    lower = error_message.lower()
                    if error_type == "campaign_not_found":
                        st.error(f"{error_message} please enter the exact campaign name")
                    elif error_type == "license":
                        st.error("**ADMIN LICENSE UNAVAILABLE**")
                        st.warning("**No available admin licenses at this time.**")
                        st.info(
                            "Please wait until another admin signs out before retrying the automation."
                        )
                    elif error_type == "browser":
                        st.warning(
                            "Processing was interrupted. This may be due to browser connectivity issues."
                        )
                        st.info(
                            "Please try again. If the problem persists, check your internet connection."
                        )
                    elif error_type == "login":
                        st.error(error_message)
                    elif error_type == "no_calls":
                        st.warning(error_message)
                    elif error_type == "no_files":
                        st.error(error_message)
                    else:
                        st.error(f"PROCESSING FAILED: {error_message}")
                        st.info(
                            "Check your ReadyMode connection and try again."
                        )
                    st.session_state.audit_in_progress = False
                    st.session_state.campaign_worker_state = None
                    st.session_state.campaign_cancel_event = None
                    st.session_state.campaign_worker_thread = None

            # Check which button was clicked
            campaign_audit_just_started = False
            audit_type = None

            if heavy_campaign_button:
                campaign_audit_just_started = True
                audit_type = "Heavy Audit"
            elif lite_campaign_button:
                campaign_audit_just_started = True
                audit_type = "Lite Audit"

            if campaign_audit_just_started:
                # Check if audit is actually running by verifying driver storage
                audit_really_running = (
                    st.session_state.get("audit_in_progress", False)
                    and "driver"
                    in st.session_state.get("campaign_audit_driver_storage", {})
                )

                if audit_really_running:
                    st.warning(
                        "Another audit is already running. Please wait for it to finish before starting a new campaign audit."
                    )
                elif st.session_state.get("audit_in_progress", False) and worker_state and worker_state.get("status") in ("running", "starting"):
                    st.warning(
                        "A campaign audit is already in progress. Please wait for it to finish before starting a new one."
                    )
                else:
                    st.session_state.audit_in_progress = True
                    # Show immediate feedback that audit is starting
                    st.info("Starting Campaign Audit...")

                    if not campaign_name:
                        st.error("Please enter a campaign name.")
                        # Reset flags if validation fails
                        st.session_state.audit_in_progress = False
                    else:
                        if not READYMODE_AVAILABLE:
                            st.warning("**ReadyMode Automation Unavailable**")
                            st.markdown(
                                """
                            **Alternative Options:**
                            - **Upload & Analyze Tab**: Upload your MP3 files directly for analysis
                            - **Manual Export**: Export MP3s from ReadyMode and upload them here
                            - **Enterprise Setup**: Contact your administrator for full ReadyMode integration

                            The core audio analysis functionality is fully available via file upload!
                            """
                            )
                            # Reset flags if automation unavailable
                            st.session_state.audit_in_progress = False
                        else:
                            # Check daily download limit
                            current_username_local = st.session_state.get(
                                "username", "Auditor1"
                            )
                            can_download, limit_message = (
                                dashboard_manager.check_daily_download_limit(
                                    current_username_local, max_samples
                                )
                            )

                            if not can_download:
                                st.error("Daily Download Limit Exceeded")
                                st.warning(limit_message)

                                # Show usage info
                                usage_info = (
                                    dashboard_manager.get_daily_usage_info(
                                        current_username_local
                                    )
                                )
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric(
                                        "Used Today",
                                        f"{usage_info['current_count']}/{usage_info['daily_limit']}",
                                    )
                                with col2:
                                    st.metric("Remaining", usage_info["remaining"])
                                with col3:
                                    st.metric(
                                        "Usage",
                                        f"{usage_info['usage_percent']:.1f}%",
                                    )
                                # Reset flags if limit exceeded
                                st.session_state.audit_in_progress = False
                                return

                            # Get user-specific ReadyMode credentials
                            rm_user, rm_pass = get_user_readymode_credentials(
                                current_username_local
                            )

                            # Start background worker thread for Campaign Audit
                            new_worker_state = {
                                "status": "starting",
                                "phase": "download",
                                "downloaded": 0,
                                "total": max_samples,
                                "audit_type": audit_type,
                                "campaign_name": campaign_name,
                            }
                            st.session_state.campaign_worker_state = new_worker_state

                            new_cancel_event = threading.Event()
                            st.session_state.campaign_cancel_event = new_cancel_event

                            driver_storage = st.session_state.campaign_audit_driver_storage

                            worker_thread = threading.Thread(
                                target=_run_campaign_audit_worker,
                                args=(
                                    ready_url,
                                    campaign_name,
                                    start_date,
                                    end_date,
                                    selected_dispositions,
                                    min_duration,
                                    max_duration,
                                    max_samples,
                                    audit_type,
                                    current_username_local,
                                    rm_user,
                                    rm_pass,
                                    new_worker_state,
                                    new_cancel_event,
                                    driver_storage,
                                ),
                                daemon=True,
                            )
                            worker_thread.start()
                            st.session_state.campaign_worker_thread = worker_thread

                            st.rerun()


                            st.session_state.campaign_worker_thread = worker_thread

                            st.rerun()

