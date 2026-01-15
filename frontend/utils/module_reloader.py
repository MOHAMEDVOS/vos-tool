"""
Module reloading utilities for development.
"""
import sys
import importlib
import streamlit as st
from typing import List


def reload_modules() -> None:
    """
    Reload all custom modules to pick up code changes without restarting.
    
    Clears Streamlit cache after reloading modules.
    """
    modules_to_reload: List[str] = [
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
        'audio_pipeline.audio_processor',
        'audio_pipeline.fast_audio_processor',
        'audio_pipeline.semantic_audio_processor',
        'backend.services.audio_service'
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            try:
                module = sys.modules[module_name]
                if module is not None:
                    importlib.reload(module)
                    print(f"Reloaded: {module_name}")
            except Exception as e:
                print(f"Failed to reload {module_name}: {e}")
    
    # Clear Streamlit cache
    st.cache_data.clear()
    st.cache_resource.clear()
    print("Streamlit cache cleared")
