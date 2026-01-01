"""
Call Review Module - Audio playback for flagged calls
Displays flagged calls from Actions section with easy audio playback and jump-to-rebuttal markers
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import os
from lib.dashboard_manager import dashboard_manager
from streamlit.runtime.media_file_storage import MediaFileStorageError

def show_call_review_page():
    """Display Call Review page with flagged calls and audio player."""
    
    st.markdown("### Call Review - Flagged Calls")
    st.caption("Listen to calls flagged in Actions section with audio playback and rebuttal markers")
    
    # Get current user
    current_username = st.session_state.get('username')
    if not current_username:
        st.error("Please log in to view call review.")
        return
    
    # Get flagged calls data (same logic as Actions section)
    agent_df = dashboard_manager.get_combined_agent_audit_data(current_username)
    lite_df = dashboard_manager.get_combined_lite_audit_data(current_username)
    
    # Combine both dataframes
    combined_df = pd.concat([agent_df, lite_df], ignore_index=True) if not agent_df.empty and not lite_df.empty else (
        agent_df if not agent_df.empty else lite_df
    )
    
    if combined_df.empty:
        st.info("No audit data available. Run audits to see flagged calls.")
        return
    
    # Apply same filtering as Actions section
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
    
    # Get flagged calls
    flagged_df = combined_df[
        ((quality_issues_mask & no_rebuttal_mask) | rebuttal_issues_mask)
    ].copy()
    
    if flagged_df.empty:
        st.info("No flagged calls found. Calls with issues will appear here after running audits.")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Flagged", len(flagged_df))
    with col2:
        releasing_count = len(flagged_df[flagged_df['Releasing Detection'] == 'Yes'])
        st.metric("Releasing", releasing_count)
    with col3:
        late_hello_count = len(flagged_df[flagged_df['Late Hello Detection'] == 'Yes'])
        st.metric("Late Hello", late_hello_count)
    with col4:
        if 'Rebuttal Detection' in flagged_df.columns:
            rebuttal_issues = len(flagged_df[flagged_df['Rebuttal Detection'] == 'No'])
            st.metric("No Rebuttals", rebuttal_issues)
    
    st.markdown("---")
    
    # Filter options
    st.markdown("#### Filter Calls")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_type = st.selectbox(
            "Issue Type",
            ["All Issues", "Releasing Only", "Late Hello Only", "No Rebuttals Only"]
        )
    
    with col2:
        if 'Agent Name' in flagged_df.columns:
            agents = ['All Agents'] + sorted(flagged_df['Agent Name'].dropna().unique().tolist())
            selected_agent = st.selectbox("Agent", agents)
        else:
            selected_agent = 'All Agents'
    
    with col3:
        search_term = st.text_input("Search Phone/Filename", "")
    
    # Apply filters
    filtered_df = flagged_df.copy()
    
    if filter_type == "Releasing Only":
        filtered_df = filtered_df[filtered_df['Releasing Detection'] == 'Yes']
    elif filter_type == "Late Hello Only":
        filtered_df = filtered_df[filtered_df['Late Hello Detection'] == 'Yes']
    elif filter_type == "No Rebuttals Only":
        if 'Rebuttal Detection' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Rebuttal Detection'] == 'No']
    
    if selected_agent != 'All Agents' and 'Agent Name' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Agent Name'] == selected_agent]
    
    if search_term:
        mask = filtered_df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
        filtered_df = filtered_df[mask]
    
    st.markdown(f"#### Showing {len(filtered_df)} of {len(flagged_df)} Flagged Calls")
    
    if filtered_df.empty:
        st.info("No calls match the selected filters.")
        return
    
    # Display calls with direct audio players (no expand/play toggle)
    # Use enumerate to ensure unique sequential indices
    for enum_idx, (df_idx, row) in enumerate(filtered_df.iterrows()):
        try:
            with st.container():
                phone = str(row.get('Phone Number', 'Unknown'))
                agent = str(row.get('Agent Name', 'Unknown'))

                # Try multiple column names for filename
                filename = (
                    row.get('File Name') or 
                    row.get('filename') or 
                    row.get('Filename') or
                    row.get('file_name') or
                    row.get('Audio File') or
                    'Unknown'
                )
                filename = str(filename)

                # Determine issues
                issues = []
                if row.get('Releasing Detection') == 'Yes':
                    issues.append("Releasing")
                if row.get('Late Hello Detection') == 'Yes':
                    issues.append("Late Hello")
                if row.get('Rebuttal Detection') == 'No':
                    issues.append("No Rebuttals")

                issues_str = " | ".join(issues) if issues else "Issue"

                # Always show audio player directly for this call (no header above)
                show_audio_player(row, enum_idx)

                st.markdown("---")
        except Exception as e:
            st.error(f"Error displaying call {enum_idx}: {str(e)}")
            continue

def show_audio_player(call_data, idx):
    """Display audio player with rebuttal markers for a specific call."""
    
    # Ensure idx is a valid integer for string formatting
    try:
        idx = int(idx)
    except (ValueError, TypeError):
        idx = 0
    
    st.markdown("##### Audio Player")
    
    # Initialize audio_path variable
    audio_path = None
    method_used = None  # Track which method found the file for debugging
    
    # PRIORITY 1: Check for "File Path" column first (full path to file)
    # This is the most reliable method since it contains the exact path
    file_path_str = (
        call_data.get('File Path') or 
        call_data.get('file_path') or 
        call_data.get('file_path_str') or
        None
    )
    
    if file_path_str:
        try:
            audio_path = Path(file_path_str)
            if audio_path.exists() and audio_path.is_file():
                method_used = "File Path column"
            else:
                # Path doesn't exist, continue to fallback
                audio_path = None
        except Exception as e:
            # Invalid path format, continue to fallback
            audio_path = None
    
    # PRIORITY 2: If no File Path, try to get filename and search recursively
    if audio_path is None:
        filename = (
            call_data.get('File Name') or 
            call_data.get('filename') or 
            call_data.get('Filename') or
            call_data.get('file_name') or
            call_data.get('Audio File') or
            None
        )
        
        # If we have a filename, search recursively in Recordings folder
        if filename and filename != 'Unknown':
            recordings_dir = Path("Recordings")
            if recordings_dir.exists() and recordings_dir.is_dir():
                try:
                    # Search recursively for the file
                    for file in recordings_dir.rglob(filename):
                        if file.is_file() and file.name == filename:
                            audio_path = file
                            method_used = "File Name (recursive search)"
                            break
                except Exception as e:
                    pass  # Silently continue if search fails
    
    # PRIORITY 3: If still no file, try to find by phone number
    if audio_path is None:
        phone = call_data.get('Phone Number', '')
        if phone:
            # Try to find file by phone number in Recordings folder and ALL subfolders
            recordings_dir = Path("Recordings")
            
            if recordings_dir.exists() and recordings_dir.is_dir():
                try:
                    # Search RECURSIVELY for files containing the exact phone number format
                    # Phone format in filename: "(631) 671-0097" or similar
                    for file in recordings_dir.rglob("*.mp3"):  # rglob searches recursively!
                        if file.is_file():
                            # Check if phone number appears in filename (with formatting)
                            if phone in file.name:
                                audio_path = file  # Store the full path
                                method_used = "Phone number search (formatted)"
                                break
                    
                    # If not found with formatting, try digits only
                    if not audio_path:
                        clean_phone = ''.join(filter(str.isdigit, str(phone)))
                        for file in recordings_dir.rglob("*.mp3"):  # rglob searches recursively!
                            if file.is_file():
                                file_digits = ''.join(filter(str.isdigit, file.name))
                                if clean_phone in file_digits:
                                    audio_path = file  # Store the full path
                                    method_used = "Phone number search (digits only)"
                                    break
                except Exception as e:
                    pass  # Silently continue if search fails
    
    # Final check - if we still don't have a valid path, show error with details
    if audio_path is None:
        st.error("Audio file not found for this call")
        st.caption(f"Phone number: {call_data.get('Phone Number', 'N/A')}")
        st.caption(f"File Path: {file_path_str or 'Not available'}")
        st.caption(f"File Name: {call_data.get('File Name', 'Not available')}")
        return
    
    # Verify the path exists and is a file
    if not audio_path.exists():
        st.error(f"Audio file not found at: {audio_path}")
        if method_used:
            st.caption(f"Found via: {method_used}")
        return
    
    if not audio_path.is_file():
        st.error(f"Invalid audio file path: {audio_path}")
        if method_used:
            st.caption(f"Found via: {method_used}")
        return
    
    try:
        # Load and play audio
        with open(str(audio_path), 'rb') as audio_file:
            audio_bytes = audio_file.read()
            try:
                st.audio(audio_bytes, format='audio/mp3')
            except MediaFileStorageError:
                # Streamlit lost the file reference - retry by re-reading the file
                # This happens when Streamlit's media storage clears between app reruns
                with open(str(audio_path), 'rb') as retry_audio_file:
                    retry_audio_bytes = retry_audio_file.read()
                    st.audio(retry_audio_bytes, format='audio/mp3')
        
        # Show debug info in development (optional - can be removed in production)
        if method_used:
            st.caption(f"✓ Loaded via: {method_used}")
    except MediaFileStorageError as e:
        # If retry also fails, show error but don't crash
        st.warning(f"Audio playback temporarily unavailable. Please refresh the page.")
        st.caption(f"Path: {audio_path}")
        if method_used:
            st.caption(f"Found via: {method_used}")
    except Exception as e:
        st.error(f"Unable to play audio file: {str(e)}")
        st.caption(f"Path: {audio_path}")
        if method_used:
            st.caption(f"Found via: {method_used}")
        return
    
    # Display call details and rebuttal markers
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Call Details**")
        if 'Agent Name' in call_data and pd.notna(call_data['Agent Name']):
            st.write(f"**Agent:** {call_data['Agent Name']}")
        if 'Phone Number' in call_data and pd.notna(call_data['Phone Number']):
            st.write(f"**Phone:** {call_data['Phone Number']}")
        # Dialer/source of the call, if available
        if 'Dialer Name' in call_data and pd.notna(call_data['Dialer Name']):
            st.write(f"**Dialer:** {call_data['Dialer Name']}")
        elif 'dialer_name' in call_data and pd.notna(call_data['dialer_name']):
            st.write(f"**Dialer:** {call_data['dialer_name']}")
    
    with col2:
        st.markdown("**Issues Detected**")
        if call_data.get('Releasing Detection') == 'Yes':
            st.write("**Releasing** - Agent didn't speak")
        if call_data.get('Late Hello Detection') == 'Yes':
            st.write("**Late Hello** - Intro >5 seconds")
        if call_data.get('Rebuttal Detection') == 'No':
            st.write("**No Rebuttals** - Missing rebuttals")
        # Move disposition and date here to keep left column shorter
        if 'Disposition' in call_data and pd.notna(call_data['Disposition']):
            st.write(f"**Disposition:** {call_data['Disposition']}")
        if 'Timestamp' in call_data and pd.notna(call_data['Timestamp']):
            st.write(f"**Date:** {call_data['Timestamp']}")

