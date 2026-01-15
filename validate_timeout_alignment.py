#!/usr/bin/env python3
"""
Validate timeout alignment across all processing layers.
Ensures consistent timeout values from config through to execution.
"""

def validate_timeout_alignment():
    """Check that timeouts are properly aligned across the system."""
    
    print("⏱️  Validating Timeout Alignment")
    print("=" * 40)
    
    # Test 1: Configuration values
    print("\n1️⃣ Checking Configuration...")
    try:
        from backend.core.config import settings
        
        config_timeouts = {
            "ASSEMBLYAI_TRANSCRIPTION_TIMEOUT": settings.ASSEMBLYAI_TRANSCRIPTION_TIMEOUT,
            "PROCESSING_TIMEOUT_SINGLE_FILE": settings.PROCESSING_TIMEOUT_SINGLE_FILE,
            "PROCESSING_TIMEOUT_LITE_FILE": settings.PROCESSING_TIMEOUT_LITE_FILE
        }
        
        for name, value in config_timeouts.items():
            print(f"   {name}: {value}s")
        
        # Validate relationships
        assert settings.PROCESSING_TIMEOUT_SINGLE_FILE > settings.ASSEMBLYAI_TRANSCRIPTION_TIMEOUT
        assert settings.PROCESSING_TIMEOUT_LITE_FILE < settings.PROCESSING_TIMEOUT_SINGLE_FILE
        assert settings.PROCESSING_TIMEOUT_LITE_FILE > 30  # At least 30s for lite
        
        print("   ✅ Configuration timeouts are properly aligned")
        
    except Exception as e:
        print(f"   ❌ Configuration check failed: {e}")
        return False
    
    # Test 2: AssemblyAI engine timeout parameter
    print("\n2️⃣ Checking AssemblyAI Engine...")
    try:
        from lib.assemblyai_transcription import AssemblyAITranscriptionEngine
        import inspect
        
        sig = inspect.signature(AssemblyAITranscriptionEngine.transcribe_file)
        assert 'timeout' in sig.parameters
        
        # Check default timeout handling
        timeout_param = sig.parameters['timeout']
        print(f"   Timeout parameter: {timeout_param}")
        print(f"   Default value: {timeout_param.default}")
        
        print("   ✅ AssemblyAI engine supports timeout parameter")
        
    except Exception as e:
        print(f"   ❌ AssemblyAI engine check failed: {e}")
        return False
    
    # Test 3: Audio service timeout usage
    print("\n3️⃣ Checking Audio Service...")
    try:
        import backend.services.audio_service
        import inspect
        
        # Check if asyncio.wait_for is used in background processing
        source = inspect.getsource(backend.services.audio_service._process_audio_background)
        assert 'asyncio.wait_for' in source
        assert 'timeout=' in source
        
        print("   ✅ Audio service uses asyncio.wait_for with timeout")
        
    except Exception as e:
        print(f"   ❌ Audio service check failed: {e}")
        return False
    
    # Test 4: Batch engine timeout consistency
    print("\n4️⃣ Checking Batch Engine...")
    try:
        from processing.batch_engine import batch_analyze_folder, batch_analyze_folder_lite
        
        # Check if batch engines have reasonable timeouts
        import processing.batch_engine as batch_module
        source = inspect.getsource(batch_module)
        
        # Look for timeout values in batch processing
        if 'timeout_per_file' in source:
            print("   ✅ Batch engine has timeout_per_file configuration")
        
        # Check for timeout handling
        if 'TimeoutError' in source:
            print("   ✅ Batch engine handles TimeoutError")
        
    except Exception as e:
        print(f"   ❌ Batch engine check failed: {e}")
        return False
    
    # Test 5: Error handling consistency
    print("\n5️⃣ Checking Error Handling...")
    try:
        from backend.api.audio import _extract_transcription_status, _extract_transcription_error
        
        # Test timeout detection
        test_result = {"error": "Processing timeout after 600s"}
        status = _extract_transcription_status(test_result, None)
        assert status == "timeout"
        
        # Test transcription error detection
        test_result = {"transcription_error": "API timeout"}
        error = _extract_transcription_error(test_result, None)
        assert error == "API timeout"
        
        print("   ✅ Error handling detects timeouts correctly")
        
    except Exception as e:
        print(f"   ❌ Error handling check failed: {e}")
        return False
    
    print("\n✅ All timeout alignment checks passed!")
    
    # Summary
    print("\n📊 Timeout Summary:")
    print(f"   AssemblyAI Transcription: {config_timeouts['ASSEMBLYAI_TRANSCRIPTION_TIMEOUT']}s")
    print(f"   Single File Processing: {config_timeouts['PROCESSING_TIMEOUT_SINGLE_FILE']}s")
    print(f"   Lite File Processing: {config_timeouts['PROCESSING_TIMEOUT_LITE_FILE']}s")
    print(f"   Ratio (Single/AssemblyAI): {config_timeouts['PROCESSING_TIMEOUT_SINGLE_FILE'] / config_timeouts['ASSEMBLYAI_TRANSCRIPTION_TIMEOUT']:.1f}x")
    print(f"   Ratio (Lite/AssemblyAI): {config_timeouts['PROCESSING_TIMEOUT_LITE_FILE'] / config_timeouts['ASSEMBLYAI_TRANSCRIPTION_TIMEOUT']:.1f}x")
    
    return True

if __name__ == "__main__":
    validate_timeout_alignment()
