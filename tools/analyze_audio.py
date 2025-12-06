import os
import sys
from pydub import AudioSegment
import numpy as np
from audio_pipeline.detections import voice_activity_detection, releasing_detection

def analyze_audio(filepath):
    print(f"Analyzing: {os.path.basename(filepath)}")
    
    # Load audio file
    try:
        audio = AudioSegment.from_file(filepath)
        print(f"Duration: {len(audio)/1000:.2f} seconds")
        print(f"Channels: {audio.channels}")
        print(f"Sample width: {audio.sample_width} bytes")
        print(f"Frame rate: {audio.frame_rate} Hz")
        
        # Convert to mono for analysis
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Run VAD
        print("\nRunning Voice Activity Detection...")
        speech_segments = voice_activity_detection(audio)
        print(f"Detected {len(speech_segments)} speech segments:")
        for i, (start, end) in enumerate(speech_segments, 1):
            print(f"  {i}. {start/1000:.2f}s - {end/1000:.2f}s (duration: {(end-start)/1000:.2f}s)")
        
        # Check releasing detection
        print("\nRunning Releasing Detection...")
        is_releasing = releasing_detection(audio)
        print(f"\nReleasing Detection Result: {is_releasing}")
        
    except Exception as e:
        print(f"Error analyzing audio: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_audio(sys.argv[1])
    else:
        print("Please provide an audio file path as an argument")
