"""
Enhanced Rebuttal Detection with Multi-Signal Intelligence
Adds dialogue context, temporal analysis, audio features, and pattern recognition
"""

import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from pydub import AudioSegment
from collections import deque

logger = logging.getLogger(__name__)


class DialogueAnalyzer:
    """Analyze conversation flow and turn-taking patterns."""
    
    def __init__(self):
        self.objection_keywords = [
            "not interested", "not now", "no thanks", "don't want", "can't",
            "too busy", "no money", "not selling", "not for sale", "not ready",
            "maybe later", "call back later", "not the right time"
        ]
        self.rebuttal_indicators = [
            "but", "however", "understand", "what if", "consider", "think about",
            "flexible", "work with", "maybe", "possibly", "could", "would"
        ]
    
    def analyze_dialogue_flow(self, agent_segments: List[Dict], owner_segments: List[Dict]) -> Dict[str, Any]:
        """
        Analyze dialogue flow to detect objection-rebuttal patterns.
        
        Returns:
            Dict with dialogue analysis features
        """
        # Merge and sort segments chronologically
        all_segments = []
        for seg in agent_segments:
            all_segments.append({**seg, 'speaker': 'agent'})
        for seg in owner_segments:
            all_segments.append({**seg, 'speaker': 'owner'})
        
        all_segments.sort(key=lambda x: x.get('start', 0))
        
        if not all_segments:
            return {"has_dialogue": False}
        
        # Analyze turn-taking
        turn_count = 0
        agent_turns = 0
        owner_turns = 0
        previous_speaker = None
        
        # Detect objection-rebuttal sequences
        objection_rebuttal_sequences = []
        current_objection = None
        
        for i, segment in enumerate(all_segments):
            speaker = segment['speaker']
            text = segment.get('text', '').lower()
            
            # Track turn-taking
            if speaker != previous_speaker:
                turn_count += 1
                if speaker == 'agent':
                    agent_turns += 1
                else:
                    owner_turns += 1
                previous_speaker = speaker
            
            # Detect owner objections
            if speaker == 'owner':
                has_objection = any(keyword in text for keyword in self.objection_keywords)
                if has_objection:
                    current_objection = {
                        'start': segment.get('start', 0),
                        'text': text,
                        'position': i / len(all_segments)  # Position in conversation (0-1)
                    }
            
            # Detect agent rebuttals following objections
            if speaker == 'agent' and current_objection:
                # Check if this agent turn is a rebuttal (within 10 seconds of objection)
                time_since_objection = segment.get('start', 0) - current_objection['start']
                has_rebuttal_indicators = any(indicator in text for indicator in self.rebuttal_indicators)
                
                if time_since_objection < 10.0 and has_rebuttal_indicators:
                    objection_rebuttal_sequences.append({
                        'objection': current_objection,
                        'rebuttal': {
                            'start': segment.get('start', 0),
                            'text': text,
                            'time_since_objection': time_since_objection
                        }
                    })
                    current_objection = None  # Reset after detecting rebuttal
        
        # Calculate conversation metrics
        total_duration = all_segments[-1].get('end', 0) - all_segments[0].get('start', 0)
        avg_turn_length = total_duration / turn_count if turn_count > 0 else 0
        
        return {
            "has_dialogue": True,
            "turn_count": turn_count,
            "agent_turns": agent_turns,
            "owner_turns": owner_turns,
            "objection_rebuttal_sequences": len(objection_rebuttal_sequences),
            "sequences": objection_rebuttal_sequences,
            "avg_turn_length": avg_turn_length,
            "conversation_duration": total_duration
        }


class TemporalAnalyzer:
    """Analyze temporal patterns in conversations."""
    
    def analyze_temporal_features(self, agent_segments: List[Dict], 
                                  total_duration: float) -> Dict[str, Any]:
        """
        Analyze when rebuttals occur in the conversation timeline.
        
        Rebuttals typically occur:
        - After the first 20% of conversation (past introduction)
        - Before the last 20% (before closing)
        - In response to objections (middle section)
        """
        if not agent_segments:
            return {}
        
        features = {
            "rebuttal_windows": [],
            "early_rebuttal": False,
            "late_rebuttal": False,
            "mid_conversation_rebuttal": False
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
            
            features["rebuttal_windows"].append({
                "start": start_time,
                "position_ratio": position_ratio,
                "text": segment.get('text', '')[:50]  # First 50 chars
            })
        
        return features


class AudioProsodyAnalyzer:
    """Extract prosodic features from audio (pauses, emphasis, pace)."""
    
    def analyze_prosody(self, audio_segment: AudioSegment, 
                       agent_segments: List[Dict]) -> Dict[str, Any]:
        """
        Analyze audio prosody features that indicate rebuttals:
        - Pauses before rebuttals (agent thinking)
        - Emphasis on key words (volume spikes)
        - Speaking pace (faster = more urgent rebuttal)
        """
        try:
            audio_array = np.array(audio_segment.get_array_of_samples())
            frame_rate = audio_segment.frame_rate
            
            features = {
                "pause_patterns": [],
                "emphasis_detected": False,
                "pace_analysis": {}
            }
            
            # Analyze pauses between segments
            for i in range(len(agent_segments) - 1):
                current_end = agent_segments[i].get('end', 0)
                next_start = agent_segments[i + 1].get('start', 0)
                pause_duration = next_start - current_end
                
                if pause_duration > 0.5:  # Pause > 500ms
                    features["pause_patterns"].append({
                        "duration": pause_duration,
                        "before_segment": agent_segments[i + 1].get('text', '')[:30]
                    })
            
            # Detect emphasis (volume spikes) in agent speech
            if len(agent_segments) > 0:
                for segment in agent_segments:
                    start_ms = int(segment.get('start', 0) * 1000)
                    end_ms = int(segment.get('end', 0) * 1000)
                    
                    if start_ms < len(audio_array) and end_ms < len(audio_array):
                        segment_audio = audio_array[start_ms:end_ms]
                        if len(segment_audio) > 0:
                            max_amplitude = np.max(np.abs(segment_audio))
                            mean_amplitude = np.mean(np.abs(segment_audio))
                            
                            # Emphasis = amplitude spike > 1.5x mean
                            if mean_amplitude > 0 and max_amplitude / mean_amplitude > 1.5:
                                features["emphasis_detected"] = True
                                break
            
            # Analyze speaking pace (words per second)
            if agent_segments:
                total_words = sum(len(seg.get('text', '').split()) for seg in agent_segments)
                total_duration = agent_segments[-1].get('end', 0) - agent_segments[0].get('start', 0)
                if total_duration > 0:
                    words_per_second = total_words / total_duration
                    features["pace_analysis"] = {
                        "words_per_second": words_per_second,
                        "is_fast_pace": words_per_second > 3.0,  # Fast speech indicator
                        "is_deliberate": words_per_second < 1.5  # Slow, deliberate speech
                    }
            
            return features
            
        except Exception as e:
            logger.warning(f"Prosody analysis failed: {e}")
            return {}


class PatternRecognizer:
    """Recognize common rebuttal patterns and sequences."""
    
    def __init__(self):
        self.patterns = {
            "pivot_to_other_property": {
                "trigger": ["not interested", "not selling", "not for sale"],
                "response": ["other property", "another property", "any other"],
                "time_window": 5.0  # seconds
            },
            "future_consideration": {
                "trigger": ["not now", "maybe later", "not ready"],
                "response": ["future", "down the road", "next year", "consider"],
                "time_window": 5.0
            },
            "callback_request": {
                "trigger": ["busy", "not a good time", "call back"],
                "response": ["best time", "when", "schedule", "callback"],
                "time_window": 3.0
            }
        }
    
    def detect_patterns(self, agent_segments: List[Dict], 
                        owner_segments: List[Dict]) -> List[Dict]:
        """
        Detect common objection-rebuttal patterns.
        """
        # Merge segments chronologically
        all_segments = []
        for seg in agent_segments:
            all_segments.append({**seg, 'speaker': 'agent'})
        for seg in owner_segments:
            all_segments.append({**seg, 'speaker': 'owner'})
        
        all_segments.sort(key=lambda x: x.get('start', 0))
        
        detected_patterns = []
        
        for pattern_name, pattern_config in self.patterns.items():
            # Look for trigger (owner) followed by response (agent) within time window
            for i, segment in enumerate(all_segments):
                if segment['speaker'] == 'owner':
                    text = segment.get('text', '').lower()
                    has_trigger = any(trigger in text for trigger in pattern_config['trigger'])
                    
                    if has_trigger:
                        trigger_time = segment.get('start', 0)
                        
                        # Look for response in subsequent segments
                        for j in range(i + 1, len(all_segments)):
                            next_segment = all_segments[j]
                            if next_segment['speaker'] == 'agent':
                                response_time = next_segment.get('start', 0)
                                time_diff = response_time - trigger_time
                                
                                if time_diff <= pattern_config['time_window']:
                                    response_text = next_segment.get('text', '').lower()
                                    has_response = any(
                                        response in response_text 
                                        for response in pattern_config['response']
                                    )
                                    
                                    if has_response:
                                        detected_patterns.append({
                                            "pattern": pattern_name,
                                            "confidence": 0.9,
                                            "trigger": segment.get('text', ''),
                                            "response": response_text,
                                            "time_diff": time_diff
                                        })
                                        break
        
        return detected_patterns


class MultiSignalFusion:
    """Fuse multiple signals for smarter detection."""
    
    def __init__(self):
        self.dialogue_analyzer = DialogueAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.prosody_analyzer = AudioProsodyAnalyzer()
        self.pattern_recognizer = PatternRecognizer()
    
    def fuse_signals(self, 
                    transcript_matches: List[Dict],
                    agent_segments: List[Dict],
                    owner_segments: List[Dict],
                    audio_segment: AudioSegment) -> Dict[str, Any]:
        """
        Fuse transcript matches with dialogue, temporal, prosody, and pattern signals.
        
        Returns:
            Enhanced detection result with confidence boost from multi-signal analysis
        """
        # 1. Dialogue Analysis
        dialogue_features = self.dialogue_analyzer.analyze_dialogue_flow(
            agent_segments, owner_segments
        )
        
        # 2. Temporal Analysis
        total_duration = len(audio_segment) / 1000.0
        temporal_features = self.temporal_analyzer.analyze_temporal_features(
            agent_segments, total_duration
        )
        
        # 3. Prosody Analysis
        prosody_features = self.prosody_analyzer.analyze_prosody(
            audio_segment, agent_segments
        )
        
        # 4. Pattern Recognition
        detected_patterns = self.pattern_recognizer.detect_patterns(
            agent_segments, owner_segments
        )
        
        # 5. Calculate confidence boost from multi-signal analysis
        confidence_boost = 0.0
        boost_reasons = []
        
        # Boost from dialogue context
        if dialogue_features.get("objection_rebuttal_sequences", 0) > 0:
            confidence_boost += 0.15
            boost_reasons.append("objection-rebuttal_sequence_detected")
        
        # Boost from temporal position
        if temporal_features.get("mid_conversation_rebuttal", False):
            confidence_boost += 0.10
            boost_reasons.append("mid_conversation_timing")
        
        # Boost from prosody (emphasis, pauses)
        if prosody_features.get("emphasis_detected", False):
            confidence_boost += 0.08
            boost_reasons.append("audio_emphasis_detected")
        
        if len(prosody_features.get("pause_patterns", [])) > 0:
            confidence_boost += 0.05
            boost_reasons.append("pauses_before_rebuttals")
        
        # Boost from pattern recognition
        if len(detected_patterns) > 0:
            confidence_boost += 0.12
            boost_reasons.append(f"{len(detected_patterns)}_patterns_detected")
        
        # Boost from dialogue turn-taking (active conversation)
        if dialogue_features.get("turn_count", 0) >= 4:
            confidence_boost += 0.05
            boost_reasons.append("active_dialogue")
        
        # Cap boost at 0.3 (30% max boost)
        confidence_boost = min(confidence_boost, 0.3)
        
        return {
            "confidence_boost": confidence_boost,
            "boost_reasons": boost_reasons,
            "dialogue_features": dialogue_features,
            "temporal_features": temporal_features,
            "prosody_features": prosody_features,
            "detected_patterns": detected_patterns,
            "multi_signal_analysis": True
        }


def enhance_detection_with_multi_signal(
    base_result: Dict[str, Any],
    audio_segment: AudioSegment,
    agent_segments: List[Dict],
    owner_segments: List[Dict]
) -> Dict[str, Any]:
    """
    Enhance base detection result with multi-signal intelligence.
    
    Args:
        base_result: Base detection result from transcript matching
        audio_segment: Full audio segment
        agent_segments: Timestamped agent segments
        owner_segments: Timestamped owner segments
    
    Returns:
        Enhanced result with multi-signal confidence boost
    """
    fusion = MultiSignalFusion()
    
    # Get base matches from transcript
    transcript_matches = base_result.get("matched_phrases", [])
    
    # Fuse all signals
    fusion_result = fusion.fuse_signals(
        transcript_matches,
        agent_segments,
        owner_segments,
        audio_segment
    )
    
    # Apply confidence boost to base result
    base_confidence = base_result.get("confidence_score", 0.0)
    enhanced_confidence = min(1.0, base_confidence + fusion_result["confidence_boost"])
    
    # Update result
    enhanced_result = base_result.copy()
    enhanced_result["confidence_score"] = enhanced_confidence
    enhanced_result["multi_signal_features"] = fusion_result
    
    # Update result if confidence crosses threshold
    if base_result.get("result") == "No" and enhanced_confidence >= 0.65:
        enhanced_result["result"] = "Yes"
        enhanced_result["upgraded_by_multi_signal"] = True
        logger.info(f"Result upgraded from No to Yes by multi-signal analysis (confidence: {enhanced_confidence:.2f})")
    
    return enhanced_result








