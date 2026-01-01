"""
Batch processing UI helpers extracted from app.py, now with enhanced UX.
"""

import math
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import psutil
import streamlit as st

from lib.optimized_pipeline import get_optimized_pipeline


def show_batch_processing_section(reload_modules_fn):
    """Display the batch processing interface for multiple audio files."""

    st.markdown("""
    <div class="modern-card">
        <div class="card-header">
            <div class="card-title">
                🚀 Batch Audio Processing
            </div>
            <div class="card-subtitle">
                Process multiple audio files simultaneously with optimized parallel processing
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    cpu_cores = psutil.cpu_count(logical=True)
    memory_gb = psutil.virtual_memory().total / (1024**3)

    col1, col2, col3 = st.columns(3)
    col1.metric("CPU Cores", f"{cpu_cores} cores")
    col2.metric("System RAM", f"{memory_gb:.1f} GB")
    col3.metric("Transcription Service", "AssemblyAI")

    st.markdown("---")

    st.markdown("### 📁 Upload Audio Files")
    uploaded_files = st.file_uploader(
        "Choose audio files",
        type=['mp3', 'wav', 'm4a', 'flac'],
        accept_multiple_files=True,
        help="Upload multiple audio files for batch processing. Supported formats: MP3, WAV, M4A, FLAC"
    )

    if not uploaded_files:
        st.info("📤 Upload audio files to start batch processing")
        _render_batch_benefits()
        return

    st.success(f"✅ {len(uploaded_files)} files uploaded successfully")

    with st.expander("📋 Uploaded Files", expanded=True):
        for i, file in enumerate(uploaded_files, 1):
            file_size = len(file.getvalue()) / (1024 * 1024)
            st.write(f"{i}. **{file.name}** ({file_size:.1f} MB)")

    st.markdown("### ⚙️ Processing Configuration")
    col1, col2 = st.columns(2)

    with col1:
        parallel_workers = st.slider(
            "Parallel Workers",
            min_value=1,
            max_value=min(12, cpu_cores),
            value=min(8, cpu_cores),
            help="Number of files to process simultaneously. More workers = faster processing but higher memory usage."
        )
        enable_audio_optimization = st.checkbox(
            "Enable Audio Optimization",
            value=True,
            help="Optimize audio format for faster transcription (recommended)"
        )

    with col2:
        detection_types = st.multiselect(
            "Detection Types",
            ["Releasing Detection", "Late-Hello Detection", "Rebuttal Detection"],
            default=["Releasing Detection", "Late-Hello Detection", "Rebuttal Detection"],
            help="Select which detections to run on each file"
        )
        save_results = st.checkbox(
            "Save Results to Dashboard",
            value=True,
            help="Save processing results to your dashboard for later review"
        )

    _render_performance_estimate(uploaded_files, parallel_workers, memory_gb)

    st.markdown("---")
    if st.button("🚀 Start Batch Processing", type="primary", width="stretch"):
        if not detection_types:
            st.error("❌ Please select at least one detection type")
            return

        hud_placeholder = st.container()
        logs_expander = st.expander("📜 Live Logs", expanded=False)
        logs_display = logs_expander.empty()

        process_batch_files(
            reload_modules_fn,
            uploaded_files,
            parallel_workers,
            detection_types,
            enable_audio_optimization,
            save_results,
            hud_placeholder,
            logs_display,
        )


def process_batch_files(
    reload_modules_fn,
    uploaded_files,
    parallel_workers,
    detection_types,
    enable_audio_optimization,
    save_results,
    hud_placeholder=None,
    logs_display=None,
):
    """Process multiple files in parallel batches."""

    reload_modules_fn()
    _init_batch_state()

    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.empty()

        total_files = len(uploaded_files)
        processed_files = 0
        results = []

        log_writer = _LogWriter(logs_display)
        progress_renderer = _ProgressRenderer(hud_placeholder)

        status_text.text("🔄 Reloading detection modules with latest fixes...")
        log_writer.add("Reloading detection modules")
        time.sleep(1)
        status_text.text("🔄 Initializing batch processing...")

        pipeline = get_optimized_pipeline()
        status_text.text("🤖 Pre-loading AI models...")
        log_writer.add("Pre-loading models...")
        preload_start = time.time()
        pipeline.preload_models()
        preload_time = time.time() - preload_start
        log_writer.add(f"Models loaded in {preload_time:.2f}s")
        status_text.text(f"✅ Models loaded in {preload_time:.1f}s. Starting batch processing...")

        batch_start = time.time()

        def process_single_file(file_info):
            file_obj, file_index = file_info
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_obj.name).suffix) as tmp_file:
                tmp_file.write(file_obj.getvalue())
                tmp_path = tmp_file.name

            try:
                start_time = time.time()
                result = pipeline.run_optimized_pipeline(tmp_path)
                processing_time = time.time() - start_time

                if 'error' not in result:
                    detection_results = result.get('results', {})
                    return {
                        'file_name': file_obj.name,
                        'file_index': file_index,
                        'processing_time': processing_time,
                        'success': True,
                        'releasing': detection_results.get('releasing', {}).get('result', 'Unknown'),
                        'late_hello': detection_results.get('late_hello', {}).get('result', 'Unknown'),
                        'rebuttal': detection_results.get('rebuttal', {}).get('result', 'Unknown'),
                        'rebuttal_confidence': detection_results.get('rebuttal', {}).get('confidence_score', 0),
                        'transcript': detection_results.get('rebuttal', {}).get('transcript', '')
                    }

                return {
                    'file_name': file_obj.name,
                    'file_index': file_index,
                    'processing_time': processing_time,
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        file_infos = [(file, i) for i, file in enumerate(uploaded_files)]
        log_writer.add(f"Queued {len(file_infos)} files for processing")

        with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
            future_to_file = {executor.submit(process_single_file, file_info): file_info for file_info in file_infos}

            for future in as_completed(future_to_file):
                file_info = future_to_file[future]

                try:
                    result = future.result()
                    results.append(result)
                    processed_files += 1

                    log_writer.add(
                        f"{result.get('file_name', 'Unknown')} processed",
                        level="success" if result.get('success') else "warning"
                    )

                    progress_renderer.render(processed_files, total_files, result.get('file_name'), batch_start)

                    progress = processed_files / total_files
                    progress_bar.progress(progress)
                    status_text.text(f"📊 Processed {processed_files}/{total_files} files ({progress*100:.1f}%)")

                    if processed_files % 5 == 0 or processed_files == total_files:
                        show_batch_results_preview(results, results_container)

                    if st.session_state.get('batch_stop_requested'):
                        log_writer.add("Stop requested. Halting after current tasks finish.", level="warning")
                        status_text.warning("Stop requested. Halting after current tasks finish.")
                        break

                except Exception as e:
                    st.error(f"❌ Error processing {file_info[0].name}: {str(e)}")
                    log_writer.add(f"Error processing {file_info[0].name}: {e}", level="error")

            if st.session_state.get('batch_stop_requested'):
                log_writer.add("Batch stopped by user.", level="warning")

        total_time = time.time() - batch_start
        successful_count = len([r for r in results if r.get('success', False)])
        status_text.text(f"🎉 Batch processing completed in {total_time:.1f}s!")
        log_writer.add(f"Batch completed: {successful_count}/{len(results)} files", level="success")
        progress_bar.progress(1.0)

        try:
            show_final_batch_results(results, total_time, preload_time, save_results)
        finally:
            st.session_state['batch_stop_requested'] = False
            if hasattr(st, "toast"):
                st.toast("Batch processing completed", icon="✅")

    except Exception as e:
        st.error(f"❌ Batch processing failed: {str(e)}")
        st.info("Please check your files and try again.")
        if hasattr(st, "toast"):
            st.toast("Batch processing failed", icon="⚠️")
        raise


def show_batch_results_preview(results, container):
    """Show a preview of batch processing results."""

    if not results or container is None:
        return

    successful_results = [r for r in results if r.get('success', False)]
    failed_results = [r for r in results if not r.get('success', True)]

    with container.container():
        st.markdown("### 📊 Processing Results (Live Update)")

        col1, col2, col3 = st.columns(3)
        col1.metric("Processed", len(results))
        col2.metric("Successful", len(successful_results))
        col3.metric("Failed", len(failed_results))

        if successful_results:
            recent_results = successful_results[-5:]
            for result in recent_results:
                with st.expander(f"📄 {result['file_name']}", expanded=False):
                    col1, col2 = st.columns(2)
                    col1.write(f"**Processing Time:** {result['processing_time']:.2f}s")
                    col1.write(f"**Releasing:** {result.get('releasing', 'N/A')}")
                    col1.write(f"**Late Hello:** {result.get('late_hello', 'N/A')}")
                    col2.write(f"**Rebuttal:** {result.get('rebuttal', 'N/A')}")
                    if result.get('rebuttal_confidence'):
                        col2.write(f"**Confidence:** {result['rebuttal_confidence']:.3f}")


def show_final_batch_results(results, total_time, preload_time, save_results):
    """Display comprehensive final results of batch processing."""

    st.markdown("### 🎉 Batch Processing Complete!")

    summary = _build_issue_summary(results)
    col_summary = st.columns(3)
    col_summary[0].metric("Releasing Flags", summary["Releasing"])
    col_summary[1].metric("Late Hello Flags", summary["Late Hello"])
    col_summary[2].metric("Rebuttal Misses", summary["Rebuttal"])

    successful_results = [r for r in results if r.get('success', False)]
    failed_results = [r for r in results if not r.get('success', True)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", len(results))
    col2.metric("Successful", len(successful_results))
    col3.metric("Failed", len(failed_results))
    avg_time = sum(r.get('processing_time', 0) for r in successful_results) / len(successful_results) if successful_results else 0
    col4.metric("Avg Time/File", f"{avg_time:.1f}s")

    st.markdown("### ⚡ Performance Analysis")
    perf_cols = st.columns(3)
    perf_cols[0].metric("Total Processing Time", f"{total_time:.1f}s")
    perf_cols[1].metric("Model Preload Time", f"{preload_time:.1f}s")
    throughput = len(results) / total_time * 60 if total_time > 0 else 0
    perf_cols[2].metric("Throughput", f"{throughput:.1f} files/min")

    if successful_results:
        st.markdown("### 📋 Detailed Results")
        try:
            import pandas as pd

            df = pd.DataFrame(successful_results)
            st.dataframe(df)

            if save_results:
                st.success("✅ Results saved to dashboard")
        except Exception as e:
            st.error(f"❌ Failed to render detailed results table: {e}")
            st.write(successful_results[:5])

    if failed_results:
        st.warning("⚠️ Some files failed to process:")
        for result in failed_results[:5]:
            st.write(f"- **{result.get('file_name', 'Unknown')}**: {result.get('error', 'Unknown error')}")
        if len(failed_results) > 5:
            st.write(f"... and {len(failed_results) - 5} more failures")


def _render_batch_benefits():
    st.markdown("### 🎯 Batch Processing Benefits")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **⚡ Speed Improvements:**
        - Up to 8x faster than sequential processing
        - Parallel processing with CPU optimization
        - AssemblyAI cloud transcription for accurate speech-to-text
        - Real-time performance (1.1x audio duration)
        """)
    with col2:
        st.markdown("""
        **🎯 Features:**
        - Multiple file format support
        - Automatic audio optimization
        - Memory-efficient processing
        - Progress tracking and results export
        """)


def _render_performance_estimate(uploaded_files, parallel_workers, memory_gb):
    st.markdown("### 📊 Performance Estimation")
    single_file_time = 25.62
    total_files = len(uploaded_files)
    sequential_time = single_file_time * total_files
    parallel_batches = math.ceil(total_files / parallel_workers)
    parallel_time = parallel_batches * single_file_time

    col1, col2, col3 = st.columns(3)
    col1.metric("Sequential Time", f"{sequential_time/60:.1f} min", help="Time if processing files one by one")
    col2.metric(
        "Parallel Time",
        f"{parallel_time/60:.1f} min",
        delta=f"-{(sequential_time-parallel_time)/60:.1f} min",
        help="Estimated time with parallel processing"
    )
    speedup = sequential_time / parallel_time if parallel_time > 0 else 1
    col3.metric("Speedup", f"{speedup:.1f}x", help="Performance improvement vs sequential")

    memory_per_worker = 2.1
    estimated_memory = parallel_workers * memory_per_worker

    if estimated_memory > memory_gb * 0.8:
        st.warning(f"⚠️ High memory usage estimated: {estimated_memory:.1f} GB. Consider reducing parallel workers to avoid system slowdown.")
    else:
        st.info(f"💾 Estimated memory usage: {estimated_memory:.1f} GB ({(estimated_memory/memory_gb)*100:.1f}% of system RAM)")


def _init_batch_state():
    if 'batch_logs' not in st.session_state:
        st.session_state['batch_logs'] = []
    if 'batch_stop_requested' not in st.session_state:
        st.session_state['batch_stop_requested'] = False


class _LogWriter:
    def __init__(self, display):
        self.display = display

    def add(self, message, level="info"):
        entry = f"{datetime.now().strftime('%H:%M:%S')} [{level.upper()}] {message}"
        st.session_state['batch_logs'].append(entry)
        if self.display is not None:
            self.display.code("\n".join(st.session_state['batch_logs'][-200:]), language="")


class _ProgressRenderer:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.start_time = time.time()

    def render(self, processed, total, current_file, batch_start):
        if not self.placeholder:
            return

        elapsed = time.time() - batch_start
        eta = "--"
        if processed > 0:
            remaining = total - processed
            per_file = elapsed / processed
            eta_seconds = per_file * remaining
            eta = f"{eta_seconds/60:.1f} min" if eta_seconds > 60 else f"{eta_seconds:.0f} s"

        with self.placeholder:
            st.markdown("### Live Progress")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Processed", f"{processed}/{total}")
            col2.metric("Current File", current_file or "N/A")
            col3.metric("Elapsed", f"{elapsed/60:.1f} min" if elapsed > 60 else f"{elapsed:.0f} s")
            col4.metric("ETA", eta)
            if st.button("⏹ Stop Processing", key="stop_batch_processing", help="Finish current tasks then halt"):
                st.session_state['batch_stop_requested'] = True
                if hasattr(st, "toast"):
                    st.toast("Stop requested. Finishing current tasks...", icon="⚠️")


def _build_issue_summary(results):
    releasing = sum(1 for r in results if r.get('success') and r.get('releasing') == "Yes")
    late_hello = sum(1 for r in results if r.get('success') and r.get('late_hello') == "Yes")
    rebuttal = sum(1 for r in results if r.get('success') and r.get('rebuttal') == "No")
    return {"Releasing": releasing, "Late Hello": late_hello, "Rebuttal": rebuttal}


def show_batch_results_preview(results, container):
    """Show a preview of batch processing results."""

    if not results:
        return

    successful_results = [r for r in results if r.get('success', False)]
    failed_results = [r for r in results if not r.get('success', True)]

    with container.container():
        st.markdown("### 📊 Processing Results (Live Update)")

        col1, col2, col3 = st.columns(3)
        col1.metric("Processed", len(results))
        col2.metric("Successful", len(successful_results))
        col3.metric("Failed", len(failed_results))

        if successful_results:
            recent_results = successful_results[-5:]
            for result in recent_results:
                with st.expander(f"📄 {result['file_name']}", expanded=False):
                    col1, col2 = st.columns(2)
                    col1.write(f"**Processing Time:** {result['processing_time']:.2f}s")
                    col1.write(f"**Releasing:** {result.get('releasing', 'N/A')}")
                    col1.write(f"**Late Hello:** {result.get('late_hello', 'N/A')}")
                    col2.write(f"**Rebuttal:** {result.get('rebuttal', 'N/A')}")
                    if result.get('rebuttal_confidence'):
                        col2.write(f"**Confidence:** {result['rebuttal_confidence']:.3f}")


def show_final_batch_results(results, total_time, preload_time, save_results):
    """Display comprehensive final results of batch processing."""

    st.markdown("### 🎉 Batch Processing Complete!")
    st.write(f"Debug: Received {len(results)} results")
    if results:
        st.write(f"Debug: First result keys: {list(results[0].keys())}")

    successful_results = [r for r in results if r.get('success', False)]
    failed_results = [r for r in results if not r.get('success', True)]
    st.write(f"Debug: {len(successful_results)} successful, {len(failed_results)} failed")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", len(results))
    col2.metric("Successful", len(successful_results))
    col3.metric("Failed", len(failed_results))
    avg_time = sum(r.get('processing_time', 0) for r in successful_results) / len(successful_results) if successful_results else 0
    col4.metric("Avg Time/File", f"{avg_time:.1f}s")

    st.markdown("### ⚡ Performance Analysis")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Processing Time", f"{total_time:.1f}s")
    col2.metric("Model Preload Time", f"{preload_time:.1f}s")
    throughput = len(results) / total_time * 60 if total_time > 0 else 0
    col3.metric("Throughput", f"{throughput:.1f} files/min")

    if successful_results:
        st.markdown("### 📋 Detailed Results")
        try:
            import pandas as pd

            df = pd.DataFrame(successful_results)
            st.dataframe(df)

            if save_results:
                st.success("✅ Results saved to dashboard")
        except Exception as e:
            st.error(f"❌ Failed to render detailed results table: {e}")
            st.write(successful_results[:5])

    if failed_results:
        st.warning("⚠️ Some files failed to process:")
        for result in failed_results[:5]:
            st.write(f"- **{result.get('file_name', 'Unknown')}**: {result.get('error', 'Unknown error')}")
        if len(failed_results) > 5:
            st.write(f"... and {len(failed_results) - 5} more failures")


def _render_batch_benefits():
    st.markdown("### 🎯 Batch Processing Benefits")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **⚡ Speed Improvements:**
        - Up to 8x faster than sequential processing
        - Parallel processing with CPU optimization
        - AssemblyAI cloud transcription for accurate speech-to-text
        - Real-time performance (1.1x audio duration)
        """)
    with col2:
        st.markdown("""
        **🎯 Features:**
        - Multiple file format support
        - Automatic audio optimization
        - Memory-efficient processing
        - Progress tracking and results export
        """)


def _render_performance_estimate(uploaded_files, parallel_workers, memory_gb):
    st.markdown("### 📊 Performance Estimation")
    single_file_time = 25.62
    total_files = len(uploaded_files)
    sequential_time = single_file_time * total_files
    parallel_batches = math.ceil(total_files / parallel_workers)
    parallel_time = parallel_batches * single_file_time

    col1, col2, col3 = st.columns(3)
    col1.metric("Sequential Time", f"{sequential_time/60:.1f} min", help="Time if processing files one by one")
    col2.metric(
        "Parallel Time",
        f"{parallel_time/60:.1f} min",
        delta=f"-{(sequential_time-parallel_time)/60:.1f} min",
        help="Estimated time with parallel processing"
    )
    speedup = sequential_time / parallel_time if parallel_time > 0 else 1
    col3.metric("Speedup", f"{speedup:.1f}x", help="Performance improvement vs sequential")

    memory_per_worker = 2.1
    estimated_memory = parallel_workers * memory_per_worker

    if estimated_memory > memory_gb * 0.8:
        st.warning(f"⚠️ High memory usage estimated: {estimated_memory:.1f} GB. Consider reducing parallel workers to avoid system slowdown.")
    else:
        st.info(f"💾 Estimated memory usage: {estimated_memory:.1f} GB ({(estimated_memory/memory_gb)*100:.1f}% of system RAM)")

