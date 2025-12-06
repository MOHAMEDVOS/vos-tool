"""
Enhanced Rebuttal Detection - Agent-Only Version
Works with agent-only transcription using VAD and audio features
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class CallTerminationDetector:
    """Detect when owner ends the call (hangs up)."""
    
    def detect_call_termination(self, owner_channel: AudioSegment, 
                               total_duration: float) -> Dict[str, Any]:
        """
        Detect when owner ends the call by analyzing owner channel silence.
        
        Returns:
            Dict with termination info: {'terminated': bool, 'termination_time': float, 'reason': str}
        """
        try:
            from audio_pipeline.detections import voice_activity_detection
            
            # Use VAD to detect owner speech segments
            speech_segments = voice_activity_detection(
                owner_channel,
                energy_threshold=None,
                min_speech_duration=0.3
            )
            
            if not speech_segments:
                # No owner speech detected at all
                return {
                    'terminated': False,
                    'termination_time': None,
                    'reason': 'no_owner_speech'
                }
            
            # Find the last owner speech segment
            last_speech_end = max(end_ms for _, end_ms in speech_segments) / 1000.0  # Convert to seconds
            call_end_time = total_duration
            
            # If owner stopped speaking more than 2 seconds before call end, they likely hung up
            silence_before_end = call_end_time - last_speech_end
            
            if silence_before_end > 2.0:
                # Owner likely hung up
                return {
                    'terminated': True,
                    'termination_time': last_speech_end,
                    'silence_duration': silence_before_end,
                    'reason': 'owner_silence_before_call_end'
                }
            
            # Check if owner channel goes completely silent (no energy)
            # Analyze last 3 seconds of owner channel
            if len(owner_channel) > 3000:
                last_3_seconds = owner_channel[-3000:]
                audio_array = np.array(last_3_seconds.get_array_of_samples())
                max_amplitude = np.max(np.abs(audio_array))
                
                # Very low energy = call ended
                if max_amplitude < 1000:  # Threshold for silence
                    return {
                        'terminated': True,
                        'termination_time': call_end_time - 3.0,
                        'silence_duration': 3.0,
                        'reason': 'low_energy_at_end'
                    }
            
            return {
                'terminated': False,
                'termination_time': None,
                'reason': 'call_active'
            }
            
        except Exception as e:
            logger.warning(f"Call termination detection failed: {e}")
            return {
                'terminated': False,
                'termination_time': None,
                'reason': 'detection_failed'
            }


class VADBasedOwnerDetection:
    """Detect owner speech using Voice Activity Detection (VAD) without transcription."""
    
    def __init__(self):
        # Keywords that indicate owner objections (detected from agent responses)
        self.objection_indicators_in_agent_speech = [
            "i understand", "i see", "i hear you", "i know",  # Agent acknowledging
            "but", "however", "though",  # Agent countering
            "what if", "consider", "think about",  # Agent suggesting
        ]
        self.termination_detector = CallTerminationDetector()
    
    def detect_owner_speech_segments(self, audio_segment: AudioSegment) -> List[Dict]:
        """
        Use VAD to detect owner speech segments without transcription.
        For stereo audio, analyze the owner channel (right channel).
        """
        try:
            from audio_pipeline.detections import voice_activity_detection
            
            # Extract owner channel if stereo
            if audio_segment.channels == 2:
                owner_channel = audio_segment.split_to_mono()[1]  # Right channel
            else:
                # Mono audio - can't separate, return empty
                return []
            
            # Use VAD to detect speech segments
            speech_segments = voice_activity_detection(
                owner_channel,
                energy_threshold=None,  # Use adaptive
                min_speech_duration=0.3  # 300ms minimum
            )
            
            # Convert to our format
            owner_segments = []
            for start_ms, end_ms in speech_segments:
                owner_segments.append({
                    'start': start_ms / 1000.0,  # Convert to seconds
                    'end': end_ms / 1000.0,
                    'text': '',  # No transcription
                    'has_speech': True,
                    'duration': (end_ms - start_ms) / 1000.0
                })
            
            return owner_segments
            
        except Exception as e:
            logger.warning(f"VAD-based owner detection failed: {e}")
            return []


class AgentResponsePatternAnalyzer:
    """Analyze agent speech patterns to infer owner objections."""
    
    def __init__(self):
        # Patterns where agent responses indicate owner objections
        self.objection_response_patterns = {
            "acknowledgment_then_rebuttal": {
                "triggers": ["i understand", "i see", "i hear you", "i know"],
                "followed_by": ["but", "however", "what if", "consider", "do you have"],
                "time_window": 3.0  # seconds
            },
            "pivot_after_pause": {
                "triggers": ["pause"],  # Detected from audio
                "followed_by": ["do you have", "any other", "what about", "consider"],
                "time_window": 2.0
            },
            "future_consideration": {
                "triggers": ["not now", "not ready", "maybe later"],  # Inferred from agent
                "followed_by": ["future", "down the road", "next year", "consider"],
                "time_window": 5.0
            }
        }
    
    def infer_objections_from_agent_responses(self, agent_segments: List[Dict]) -> List[Dict]:
        """
        Infer owner objections by analyzing agent response patterns.
        When agent says "I understand, but..." it implies owner just objected.
        """
        inferred_objections = []
        
        for i, segment in enumerate(agent_segments):
            text = segment.get('text', '').lower()
            
            # Pattern 1: Acknowledgment followed by rebuttal
            if any(trigger in text for trigger in self.objection_response_patterns["acknowledgment_then_rebuttal"]["triggers"]):
                # Check if next segment has rebuttal
                if i + 1 < len(agent_segments):
                    next_segment = agent_segments[i + 1]
                    next_text = next_segment.get('text', '').lower()
                    time_diff = next_segment.get('start', 0) - segment.get('end', 0)
                    
                    if time_diff < 3.0:  # Within 3 seconds
                        has_rebuttal = any(
                            phrase in next_text 
                            for phrase in self.objection_response_patterns["acknowledgment_then_rebuttal"]["followed_by"]
                        )
                        
                        if has_rebuttal:
                            # Infer: Owner objected, agent acknowledged, then rebutted
                            inferred_objections.append({
                                'start': segment.get('start', 0) - 2.0,  # Estimate objection before acknowledgment
                                'end': segment.get('start', 0),
                                'text': '[inferred: owner objection]',
                                'confidence': 0.7,
                                'pattern': 'acknowledgment_then_rebuttal'
                            })
        
        return inferred_objections


class RebuttalCompletionAnalyzer:
    """Analyze if rebuttal was completed before call termination."""
    
    def check_rebuttal_completion(self, agent_segments: List[Dict],
                                 rebuttal_text: str,
                                 call_termination: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if rebuttal was completed before owner ended the call.
        
        Returns:
            Dict with completion status, confidence penalty, and hangup detection
        """
        if not call_termination.get('terminated', False):
            # Call didn't end early, rebuttal was completed
            return {
                'completed': True,
                'confidence_penalty': 0.0,
                'reason': 'call_not_terminated',
                'owner_hangup': False
            }
        
        termination_time = call_termination.get('termination_time')
        if termination_time is None:
            return {
                'completed': True,
                'confidence_penalty': 0.0,
                'reason': 'termination_time_unknown'
            }
        
        # Find the segment containing the rebuttal
        rebuttal_lower = rebuttal_text.lower()
        rebuttal_segment = None
        
        for segment in agent_segments:
            segment_text = segment.get('text', '').lower()
            if any(phrase in segment_text for phrase in rebuttal_lower.split()[:3]):  # Check first few words
                rebuttal_segment = segment
                break
        
        if not rebuttal_segment:
            # Can't find rebuttal segment, assume completed
            return {
                'completed': True,
                'confidence_penalty': 0.0,
                'reason': 'rebuttal_segment_not_found'
            }
        
        rebuttal_start = rebuttal_segment.get('start', 0)
        rebuttal_end = rebuttal_segment.get('end', 0)
        
        # Check if rebuttal started after call termination
        if rebuttal_start > termination_time:
            # Rebuttal started AFTER owner hung up - definitely incomplete
            return {
                'completed': False,
                'confidence_penalty': -0.5,  # Large penalty
                'reason': 'rebuttal_started_after_call_end',
                'time_after_termination': rebuttal_start - termination_time,
                'owner_hangup': True,
                'hangup_type': 'owner_hung_up_before_rebuttal_started'
            }
        
        # Check if rebuttal was cut off (started before but ended after termination)
        if rebuttal_end > termination_time:
            # Rebuttal was in progress when call ended - OWNER HUNG UP
            completion_ratio = (termination_time - rebuttal_start) / (rebuttal_end - rebuttal_start) if rebuttal_end > rebuttal_start else 0
            
            if completion_ratio < 0.5:
                # Less than 50% complete - Owner hung up mid-rebuttal
                return {
                    'completed': False,
                    'confidence_penalty': -0.4,
                    'reason': 'rebuttal_cut_off_early',
                    'completion_ratio': completion_ratio,
                    'owner_hangup': True,
                    'hangup_type': 'owner_hung_up_during_rebuttal',
                    'rebuttal_progress': f'{completion_ratio*100:.0f}%'
                }
            elif completion_ratio < 0.8:
                # 50-80% complete - Owner hung up near end of rebuttal
                return {
                    'completed': False,
                    'confidence_penalty': -0.2,
                    'reason': 'rebuttal_partially_complete',
                    'completion_ratio': completion_ratio,
                    'owner_hangup': True,
                    'hangup_type': 'owner_hung_up_near_end_of_rebuttal',
                    'rebuttal_progress': f'{completion_ratio*100:.0f}%'
                }
            else:
                # 80%+ complete - Owner hung up but rebuttal mostly done
                return {
                    'completed': True,
                    'confidence_penalty': -0.05,
                    'reason': 'rebuttal_mostly_complete',
                    'completion_ratio': completion_ratio,
                    'owner_hangup': True,
                    'hangup_type': 'owner_hung_up_after_mostly_complete',
                    'rebuttal_progress': f'{completion_ratio*100:.0f}%'
                }
        
        # Rebuttal completed before call termination
        return {
            'completed': True,
            'confidence_penalty': 0.0,
            'reason': 'rebuttal_completed_before_call_end',
            'owner_hangup': False
        }


class TemporalAnalyzerAgentOnly:
    """Temporal analysis using only agent segments."""
    
    def analyze_temporal_features(self, agent_segments: List[Dict], 
                                  total_duration: float,
                                  owner_speech_segments: List[Dict] = None,
                                  call_termination: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze when rebuttals occur - works with agent-only data.
        Uses owner speech timing from VAD if available.
        """
        if not agent_segments:
            return {}
        
        features = {
            "rebuttal_windows": [],
            "early_rebuttal": False,
            "late_rebuttal": False,
            "mid_conversation_rebuttal": False,
            "response_to_owner_speech": False
        }
        
        for segment in agent_segments:
            start_time = segment.get('start', 0)
            position_ratio = start_time / total_duration if total_duration > 0 else 0
            
            # Classify temporal position
            if position_ratio < 0.2:
                features["early_rebuttal"] = True
            elif position_ratio > 0.8:
                features["late_rebuttal"] = True
            else:
                features["mid_conversation_rebuttal"] = True
            
            # Check if agent is responding to owner speech (using VAD)
            if owner_speech_segments:
                for owner_seg in owner_speech_segments:
                    owner_end = owner_seg.get('end', 0)
                    time_since_owner = start_time - owner_end
                    
                    # If agent speaks within 3 seconds of owner, likely a response
                    if 0 < time_since_owner < 3.0:
                        features["response_to_owner_speech"] = True
                        break
            
            # Check if rebuttal occurred after call termination
            if call_termination and call_termination.get('terminated', False):
                termination_time = call_termination.get('termination_time', float('inf'))
                if start_time > termination_time:
                    features["rebuttal_after_call_end"] = True
                    features["time_after_termination"] = start_time - termination_time
            
            features["rebuttal_windows"].append({
                "start": start_time,
                "position_ratio": position_ratio,
                "text": segment.get('text', '')[:50]
            })
        
        return features


class AudioProsodyAnalyzerAgentOnly:
    """Audio prosody analysis using only agent channel."""
    
    def analyze_prosody(self, agent_audio: AudioSegment, 
                       agent_segments: List[Dict]) -> Dict[str, Any]:
        """
        Analyze prosody from agent audio only.
        Detects pauses, emphasis, and pace.
        """
        try:
            audio_array = np.array(agent_audio.get_array_of_samples())
            
            features = {
                "pause_patterns": [],
                "emphasis_detected": False,
                "pace_analysis": {},
                "pre_rebuttal_pauses": []
            }
            
            # Analyze pauses between agent segments
            for i in range(len(agent_segments) - 1):
                current_end = agent_segments[i].get('end', 0)
                next_start = agent_segments[i + 1].get('start', 0)
                pause_duration = next_start - current_end
                
                if pause_duration > 0.5:  # Pause > 500ms
                    next_text = agent_segments[i + 1].get('text', '').lower()
                    # Check if next segment is a rebuttal
                    is_rebuttal = any(phrase in next_text for phrase in [
                        "do you have", "any other", "consider", "what if", "but"
                    ])
                    
                    if is_rebuttal:
                        features["pre_rebuttal_pauses"].append({
                            "duration": pause_duration,
                            "before_rebuttal": next_text[:30]
                        })
                    
                    features["pause_patterns"].append({
                        "duration": pause_duration,
                        "before_segment": next_text[:30]
                    })
            
            # Detect emphasis (volume spikes) in agent speech
            for segment in agent_segments:
                start_ms = int(segment.get('start', 0) * 1000)
                end_ms = int(segment.get('end', 0) * 1000)
                
                if 0 <= start_ms < len(audio_array) and 0 <= end_ms < len(audio_array):
                    segment_audio = audio_array[start_ms:end_ms]
                    if len(segment_audio) > 0:
                        max_amplitude = np.max(np.abs(segment_audio))
                        mean_amplitude = np.mean(np.abs(segment_audio))
                        
                        # Emphasis = amplitude spike > 1.5x mean
                        if mean_amplitude > 0 and max_amplitude / mean_amplitude > 1.5:
                            features["emphasis_detected"] = True
                            break
            
            # Analyze speaking pace
            if agent_segments:
                total_words = sum(len(seg.get('text', '').split()) for seg in agent_segments)
                total_duration = agent_segments[-1].get('end', 0) - agent_segments[0].get('start', 0)
                if total_duration > 0:
                    words_per_second = total_words / total_duration
                    features["pace_analysis"] = {
                        "words_per_second": words_per_second,
                        "is_fast_pace": words_per_second > 3.0,
                        "is_deliberate": words_per_second < 1.5
                    }
            
            return features
            
        except Exception as e:
            logger.warning(f"Prosody analysis failed: {e}")
            return {}


class PatternRecognizerAgentOnly:
    """Pattern recognition using only agent speech."""
    
    def __init__(self):
        self.patterns = {
            "pivot_after_acknowledgment": {
                "sequence": [
                    {"contains": ["i understand", "i see", "i hear"], "role": "acknowledgment"},
                    {"contains": ["but", "however", "do you have", "any other"], "role": "rebuttal", "max_gap": 3.0}
                ]
            },
            "future_consideration_offer": {
                "sequence": [
                    {"contains": ["not now", "not ready", "maybe later"], "role": "acknowledgment"},
                    {"contains": ["future", "down the road", "next year", "consider"], "role": "rebuttal", "max_gap": 5.0}
                ]
            },
            "callback_request": {
                "sequence": [
                    {"contains": ["busy", "not a good time"], "role": "acknowledgment"},
                    {"contains": ["best time", "when", "schedule", "callback"], "role": "rebuttal", "max_gap": 3.0}
                ]
            }
        }
    
    def detect_patterns(self, agent_segments: List[Dict]) -> List[Dict]:
        """
        Detect patterns in agent speech that indicate objection-rebuttal sequences.
        Works by detecting acknowledgment→rebuttal patterns.
        """
        detected_patterns = []
        
        for pattern_name, pattern_config in self.patterns.items():
            sequence = pattern_config.get("sequence", [])
            if len(sequence) < 2:
                continue
            
            # Look for the sequence in agent segments
            for i in range(len(agent_segments) - 1):
                first_seg = agent_segments[i]
                first_text = first_seg.get('text', '').lower()
                
                # Check if first segment matches first part of pattern
                first_pattern = sequence[0]
                if any(phrase in first_text for phrase in first_pattern.get("contains", [])):
                    # Look for second part
                    for j in range(i + 1, len(agent_segments)):
                        second_seg = agent_segments[j]
                        second_text = second_seg.get('text', '').lower()
                        time_diff = second_seg.get('start', 0) - first_seg.get('end', 0)
                        
                        second_pattern = sequence[1]
                        max_gap = second_pattern.get("max_gap", 5.0)
                        
                        if time_diff <= max_gap:
                            if any(phrase in second_text for phrase in second_pattern.get("contains", [])):
                                detected_patterns.append({
                                    "pattern": pattern_name,
                                    "confidence": 0.85,
                                    "acknowledgment": first_text[:50],
                                    "rebuttal": second_text[:50],
                                    "time_diff": time_diff
                                })
                                break
        
        return detected_patterns


class MultiSignalFusionAgentOnly:
    """Multi-signal fusion for agent-only transcription."""
    
    def __init__(self):
        self.vad_owner_detector = VADBasedOwnerDetection()
        self.response_pattern_analyzer = AgentResponsePatternAnalyzer()
        self.temporal_analyzer = TemporalAnalyzerAgentOnly()
        self.prosody_analyzer = AudioProsodyAnalyzerAgentOnly()
        self.pattern_recognizer = PatternRecognizerAgentOnly()
        self.completion_analyzer = RebuttalCompletionAnalyzer()
    
    def fuse_signals(self, 
                    transcript_matches: List[Dict],
                    agent_segments: List[Dict],
                    audio_segment: AudioSegment) -> Dict[str, Any]:
        """
        Fuse signals using only agent transcription + VAD + audio features.
        """
        # 1. Detect call termination (owner hung up)
        owner_channel = None
        if audio_segment.channels == 2:
            owner_channel = audio_segment.split_to_mono()[1]
        else:
            owner_channel = AudioSegment.empty()
        
        total_duration = len(audio_segment) / 1000.0
        call_termination = self.vad_owner_detector.termination_detector.detect_call_termination(
            owner_channel, total_duration
        )
        
        # 2. Detect owner speech using VAD (no transcription needed)
        owner_speech_segments = self.vad_owner_detector.detect_owner_speech_segments(audio_segment)
        
        # 3. Infer objections from agent response patterns
        inferred_objections = self.response_pattern_analyzer.infer_objections_from_agent_responses(agent_segments)
        
        # 4. Temporal Analysis (includes call termination check)
        temporal_features = self.temporal_analyzer.analyze_temporal_features(
            agent_segments, total_duration, owner_speech_segments, call_termination
        )
        
        # 4. Prosody Analysis (agent audio only)
        agent_audio = audio_segment.split_to_mono()[0] if audio_segment.channels == 2 else audio_segment
        prosody_features = self.prosody_analyzer.analyze_prosody(agent_audio, agent_segments)
        
        # 5. Pattern Recognition (agent speech only)
        detected_patterns = self.pattern_recognizer.detect_patterns(agent_segments)
        
        # 6. Check rebuttal completion (if call terminated early)
        completion_penalty = 0.0
        completion_status = None
        
        if transcript_matches and call_termination.get('terminated', False):
            best_match = transcript_matches[0] if transcript_matches else None
            if best_match:
                rebuttal_text = best_match.get('phrase', '')
                completion_status = self.completion_analyzer.check_rebuttal_completion(
                    agent_segments, rebuttal_text, call_termination
                )
                completion_penalty = completion_status.get('confidence_penalty', 0.0)
        
        # 7. Calculate confidence boost
        confidence_boost = 0.0
        boost_reasons = []
        
        # Apply completion penalty first (if rebuttal was incomplete)
        if completion_penalty < 0:
            boost_reasons.append(f"incomplete_rebuttal_penalty: {completion_status.get('reason', 'unknown')}")
        
        # Boost from inferred objection-rebuttal sequences
        if len(inferred_objections) > 0:
            confidence_boost += 0.12
            boost_reasons.append(f"{len(inferred_objections)}_inferred_objection_rebuttal_sequences")
        
        # Boost from VAD-detected owner speech (agent responding)
        if temporal_features.get("response_to_owner_speech", False):
            confidence_boost += 0.10
            boost_reasons.append("response_to_owner_speech_detected")
        
        # Boost from temporal position (but NOT if after call end)
        if temporal_features.get("mid_conversation_rebuttal", False):
            if not temporal_features.get("rebuttal_after_call_end", False):
                confidence_boost += 0.08
                boost_reasons.append("mid_conversation_timing")
        
        # Boost from prosody (emphasis, pauses)
        if prosody_features.get("emphasis_detected", False):
            confidence_boost += 0.07
            boost_reasons.append("audio_emphasis_detected")
        
        if len(prosody_features.get("pre_rebuttal_pauses", [])) > 0:
            confidence_boost += 0.06
            boost_reasons.append(f"{len(prosody_features['pre_rebuttal_pauses'])}_pre_rebuttal_pauses")
        
        # Boost from pattern recognition
        if len(detected_patterns) > 0:
            confidence_boost += 0.10
            boost_reasons.append(f"{len(detected_patterns)}_patterns_detected")
        
        # Apply completion penalty
        confidence_boost += completion_penalty
        
        # Cap boost at 0.25 (25% max boost for agent-only)
        # But allow negative values for penalties
        if confidence_boost > 0:
            confidence_boost = min(confidence_boost, 0.25)
        
        # Determine if this is an owner hangup scenario
        owner_hangup_detected = (
            call_termination.get("terminated", False) and 
            completion_status and 
            completion_status.get("owner_hangup", False)
        )
        
        return {
            "confidence_boost": confidence_boost,
            "boost_reasons": boost_reasons,
            "owner_speech_segments": len(owner_speech_segments),
            "inferred_objections": len(inferred_objections),
            "temporal_features": temporal_features,
            "prosody_features": prosody_features,
            "detected_patterns": detected_patterns,
            "call_termination": call_termination,
            "rebuttal_completion": completion_status,
            "owner_hangup_detected": owner_hangup_detected,
            "multi_signal_analysis": True,
            "agent_only_mode": True
        }


def enhance_detection_agent_only(
    base_result: Dict[str, Any],
    audio_segment: AudioSegment,
    agent_segments: List[Dict]
) -> Dict[str, Any]:
    """
    Enhance detection using agent-only transcription + VAD + audio features.
    
    Args:
        base_result: Base detection result from transcript matching
        audio_segment: Full audio segment
        agent_segments: Timestamped agent segments (from transcript)
    
    Returns:
        Enhanced result with multi-signal confidence boost
    """
    fusion = MultiSignalFusionAgentOnly()
    
    # Get base matches from transcript
    transcript_matches = base_result.get("matched_phrases", [])
    
    # Fuse all signals (agent-only mode)
    fusion_result = fusion.fuse_signals(
        transcript_matches,
        agent_segments,
        audio_segment
    )
    
    # Apply confidence boost to base result
    base_confidence = base_result.get("confidence_score", 0.0)
    enhanced_confidence = min(1.0, base_confidence + fusion_result["confidence_boost"])
    
    # Update result
    enhanced_result = base_result.copy()
    enhanced_result["confidence_score"] = enhanced_confidence
    enhanced_result["multi_signal_features"] = fusion_result
    
    # Check if rebuttal was incomplete (call ended early)
    call_termination = fusion_result.get("call_termination", {})
    completion_status = fusion_result.get("rebuttal_completion", {})
    
    # Mark owner hangup in result metadata
    if completion_status.get("owner_hangup", False):
        enhanced_result["owner_hangup"] = True
        enhanced_result["hangup_type"] = completion_status.get("hangup_type", "owner_hung_up")
        enhanced_result["rebuttal_progress"] = completion_status.get("rebuttal_progress", "unknown")
        enhanced_result["termination_time"] = call_termination.get("termination_time")
        logger.info(f"Owner hangup detected: {completion_status.get('hangup_type')} - Rebuttal {completion_status.get('rebuttal_progress', 'incomplete')}")
    
    if call_termination.get("terminated", False) and not completion_status.get("completed", True):
        # Call ended before rebuttal was completed - downgrade result
        if enhanced_result.get("result") == "Yes":
            enhanced_result["result"] = "No"
            enhanced_result["downgraded_due_to_incomplete"] = True
            enhanced_result["downgrade_reason"] = "owner_hung_up_before_rebuttal_completed"
            logger.info(f"Result downgraded from Yes to No: owner hung up before rebuttal completed ({completion_status.get('hangup_type', 'unknown')})")
        enhanced_confidence = max(0.0, enhanced_confidence)  # Ensure non-negative
        enhanced_result["confidence_score"] = enhanced_confidence
    
    # Update result if confidence crosses threshold (but only if rebuttal was completed)
    elif base_result.get("result") == "No" and enhanced_confidence >= 0.65:
        if completion_status.get("completed", True):  # Only upgrade if completed
            enhanced_result["result"] = "Yes"
            enhanced_result["upgraded_by_multi_signal"] = True
            logger.info(f"Result upgraded from No to Yes by multi-signal analysis (confidence: {enhanced_confidence:.2f})")
    
    return enhanced_result

