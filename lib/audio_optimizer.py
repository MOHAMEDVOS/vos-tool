#!/usr/bin/env python3
"""
Audio Preprocessing Optimizer
Optimizes audio format and quality for faster, more accurate transcription.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import time

logger = logging.getLogger(__name__)

class AudioOptimizer:
    """Optimizes audio for transcription performance and accuracy."""
    
    def __init__(self):
        # Optimal settings for Whisper transcription
        self.target_sample_rate = 16000  # Whisper's native sample rate
        self.target_channels = 1  # Mono for efficiency
        self.target_bit_depth = 16  # 16-bit for balance of quality/size
        
        # Audio enhancement settings
        self.normalize_audio = True
        self.apply_compression = True
        self.noise_reduction = True
        
        logger.info("AudioOptimizer initialized with optimal Whisper settings")
    
    def optimize_for_transcription(self, audio: AudioSegment, 
                                 preserve_quality: bool = True) -> AudioSegment:
        """
        Optimize audio specifically for transcription accuracy and speed.
        
        Args:
            audio: Input audio segment
            preserve_quality: If True, applies quality enhancements
            
        Returns:
            Optimized audio segment
        """
        start_time = time.time()
        original_duration = len(audio)
        
        logger.info(f"Optimizing {original_duration}ms audio for transcription...")
        
        # Step 1: Convert to optimal sample rate (most important for Whisper)
        if audio.frame_rate != self.target_sample_rate:
            logger.debug(f"Resampling from {audio.frame_rate}Hz to {self.target_sample_rate}Hz")
            audio = audio.set_frame_rate(self.target_sample_rate)
        
        # Step 2: Convert to mono (reduces processing time significantly)
        if audio.channels > 1:
            logger.debug(f"Converting from {audio.channels} channels to mono")
            # Use left channel for agent audio, or mix if needed
            audio = audio.set_channels(1)
        
        # Step 3: Optimize bit depth
        if audio.sample_width != 2:  # 2 bytes = 16-bit
            logger.debug(f"Converting from {audio.sample_width*8}-bit to 16-bit")
            audio = audio.set_sample_width(2)
        
        if preserve_quality:
            # Step 4: Normalize audio levels for consistent transcription
            if self.normalize_audio:
                logger.debug("Normalizing audio levels")
                audio = normalize(audio)
            
            # Step 5: Apply light compression to even out volume levels
            if self.apply_compression:
                logger.debug("Applying dynamic range compression")
                audio = compress_dynamic_range(audio, threshold=-20.0, ratio=2.0)
            
            # Step 6: Noise reduction (simple high-pass filter)
            if self.noise_reduction:
                logger.debug("Applying noise reduction")
                audio = self._apply_noise_reduction(audio)
        
        processing_time = time.time() - start_time
        size_reduction = self._calculate_size_reduction(original_duration, len(audio), 
                                                       audio.frame_rate, audio.channels)
        
        logger.info(f"Audio optimization completed in {processing_time:.2f}s")
        logger.info(f"Size reduction: {size_reduction:.1f}% (faster processing)")
        
        return audio
    
    def _apply_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """Apply simple noise reduction using high-pass filter."""
        try:
            # Simple high-pass filter to remove low-frequency noise
            # This removes frequencies below 80Hz (typical phone line noise)
            audio = audio.high_pass_filter(80)
            return audio
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio
    
    def _calculate_size_reduction(self, original_duration: int, new_duration: int,
                                sample_rate: int, channels: int) -> float:
        """Calculate the size reduction percentage."""
        try:
            # Estimate original size (assuming 44.1kHz, stereo, 16-bit)
            original_size = original_duration * 44100 * 2 * 2 / 1000  # bytes
            
            # Calculate new size
            new_size = new_duration * sample_rate * channels * 2 / 1000  # bytes
            
            reduction = (1 - new_size / original_size) * 100
            return max(0, reduction)
        except:
            return 0
    
    def extract_agent_channel_optimized(self, audio: AudioSegment) -> AudioSegment:
        """Extract and optimize agent channel in one step."""
        logger.debug("Extracting and optimizing agent channel")
        
        # Extract left channel (typically agent) if stereo
        if audio.channels == 2:
            agent_audio = audio.split_to_mono()[0]
        else:
            agent_audio = audio
        
        # Apply optimization
        return self.optimize_for_transcription(agent_audio)
    
    def create_optimized_temp_file(self, audio: AudioSegment) -> str:
        """Create an optimized temporary file for transcription."""
        try:
            # Create temporary file with optimal format
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Export with optimal parameters for Whisper
            audio.export(
                temp_path,
                format="wav",
                parameters=[
                    "-ac", "1",  # Mono
                    "-ar", str(self.target_sample_rate),  # 16kHz
                    "-sample_fmt", "s16",  # 16-bit
                    "-acodec", "pcm_s16le"  # PCM encoding
                ]
            )
            
            logger.debug(f"Created optimized temp file: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to create optimized temp file: {e}")
            # Fallback to basic export
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()
            audio.export(temp_path, format="wav")
            return temp_path
    
    def preprocess_for_whisper(self, audio_file_path: str) -> Tuple[str, dict]:
        """
        Complete preprocessing pipeline for Whisper transcription.
        
        Args:
            audio_file_path: Path to input audio file
            
        Returns:
            Tuple of (optimized_temp_file_path, optimization_stats)
        """
        start_time = time.time()
        
        try:
            # Load audio
            logger.info(f"Loading audio file: {Path(audio_file_path).name}")
            audio = AudioSegment.from_file(audio_file_path)
            
            original_stats = {
                'duration_ms': len(audio),
                'sample_rate': audio.frame_rate,
                'channels': audio.channels,
                'sample_width': audio.sample_width
            }
            
            # Extract agent channel and optimize
            optimized_audio = self.extract_agent_channel_optimized(audio)
            
            # Create optimized temp file
            temp_file_path = self.create_optimized_temp_file(optimized_audio)
            
            optimization_stats = {
                'original': original_stats,
                'optimized': {
                    'duration_ms': len(optimized_audio),
                    'sample_rate': optimized_audio.frame_rate,
                    'channels': optimized_audio.channels,
                    'sample_width': optimized_audio.sample_width
                },
                'processing_time': time.time() - start_time,
                'temp_file': temp_file_path
            }
            
            logger.info(f"Audio preprocessing completed in {optimization_stats['processing_time']:.2f}s")
            
            return temp_file_path, optimization_stats
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            # Return original file as fallback
            return audio_file_path, {'error': str(e)}

# Global optimizer instance
_audio_optimizer = None

def get_audio_optimizer() -> AudioOptimizer:
    """Get the global audio optimizer instance."""
    global _audio_optimizer
    if _audio_optimizer is None:
        _audio_optimizer = AudioOptimizer()
    return _audio_optimizer
