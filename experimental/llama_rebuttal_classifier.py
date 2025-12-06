"""
LLaMA-based Rebuttal Classifier for VOS Tool
Advanced AI-powered rebuttal detection using local LLaMA model
Used as a smart fallback for complex cases when exact + semantic matching have low confidence
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Global singleton for LLaMA model
_LLAMA_MODEL = None
_LLAMA_MODEL_FAILED = False


def get_llama_model():
    """
    Load LLaMA model (singleton pattern for efficiency).
    
    Returns:
        Llama model instance or None if loading fails
    """
    global _LLAMA_MODEL, _LLAMA_MODEL_FAILED
    
    # If we already tried and failed, don't try again
    if _LLAMA_MODEL_FAILED:
        return None
    
    # Return cached model if available
    if _LLAMA_MODEL is not None:
        return _LLAMA_MODEL
    
    try:
        logger.info("🔄 Loading local LLaMA model for complex case detection...")
        from llama_cpp import Llama
        
        # Path to your model
        model_path = Path(__file__).parent.parent / "models" / "local-campaign-model.gguf"
        
        if not model_path.exists():
            logger.warning(f"LLaMA model not found at: {model_path}")
            _LLAMA_MODEL_FAILED = True
            return None
        
        # Auto-detect GPU and configure layers
        # RTX 4090 has 24GB VRAM - can handle full model on GPU
        import os
        n_gpu_layers = 0
        n_threads = 4
        
        # Check for CUDA availability
        try:
            # Try to detect if CUDA is available via environment or direct check
            cuda_available = os.environ.get('CUDA_VISIBLE_DEVICES') is not None
            if not cuda_available:
                # Try importing torch to check CUDA
                try:
                    import torch
                    cuda_available = torch.cuda.is_available()
                except ImportError:
                    pass
            
            if cuda_available:
                # RTX 4090: Use 35+ layers on GPU (full model offloading)
                # This will use GPU for inference acceleration
                n_gpu_layers = 35  # Offload all layers to GPU for RTX 4090
                logger.info("🚀 GPU detected - using GPU acceleration for LLaMA model")
            else:
                # CPU fallback - use all available CPU threads
                import multiprocessing
                n_threads = multiprocessing.cpu_count()
                logger.info(f"CPU mode - using {n_threads} threads")
        except Exception as e:
            logger.warning(f"GPU detection failed, using CPU: {e}")
        
        # Load model with optimized settings for RTX 4090
        # Use larger context on GPU, smaller on CPU
        n_ctx = 4096 if n_gpu_layers > 0 else 2048
        
        _LLAMA_MODEL = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,        # Context window (4K on GPU, 2K on CPU)
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,  # GPU layers for RTX 4090
            n_batch=512,       # Batch size for prompt processing
            verbose=False,     # Disable verbose output
            use_mlock=True,    # Keep model in RAM
            use_mmap=True      # Use memory mapping for faster loading
        )
        
        logger.info("✅ LLaMA model loaded successfully (ready for complex cases)")
        return _LLAMA_MODEL
        
    except ImportError:
        # Silently handle missing llama_cpp - it's an optional dependency
        # Only log at debug level to avoid cluttering console
        logger.debug("llama-cpp-python not installed (optional dependency)")
        _LLAMA_MODEL_FAILED = True
        return None
    except Exception as e:
        logger.error(f"❌ Failed to load LLaMA model: {e}")
        _LLAMA_MODEL_FAILED = True
        return None


def llama_rebuttal_detection(transcript: str, max_tokens: int = 150) -> Optional[Dict[str, Any]]:
    """
    Detect rebuttals using LLaMA model inference.
    
    This is used as a FALLBACK for complex cases when:
    - Exact matching finds no matches
    - Semantic matching has low confidence (<0.70)
    
    Args:
        transcript: Call transcript to analyze
        max_tokens: Maximum tokens for LLaMA response
        
    Returns:
        dict with 'result', 'confidence_score', 'reasoning', 'method'
        Returns None if model unavailable or inference fails
    """
    model = get_llama_model()
    if model is None:
        return None
    
    try:
        # Truncate transcript if too long (keep first 500 words for performance)
        words = transcript.split()
        if len(words) > 500:
            truncated_transcript = ' '.join(words[:500]) + "..."
            logger.debug(f"Truncated transcript from {len(words)} to 500 words for LLaMA inference")
        else:
            truncated_transcript = transcript
        
        # Create optimized prompt for rebuttal detection
        prompt = f"""You are an expert call quality analyst specializing in sales conversations.

TASK: Analyze if the sales agent used rebuttals (objection-handling techniques) in this call.

REBUTTAL DEFINITION:
A rebuttal is when an agent responds to owner resistance by:
- Asking about other/alternative properties after rejection
- Suggesting future consideration when owner says "not now"
- Addressing price/value concerns with explanations
- Scheduling a callback after owner shows disinterest
- Pivoting to different offerings when initial pitch fails
- Acknowledging concerns then presenting alternatives

TRANSCRIPT:
{truncated_transcript}

INSTRUCTIONS:
1. Determine if agent used ANY rebuttal technique
2. Provide confidence (0-100)
3. Explain briefly WHY

FORMAT (MUST FOLLOW EXACTLY):
Result: [Yes/No]
Confidence: [0-100]
Reason: [Brief explanation in one sentence]

ANALYSIS:"""

        logger.debug("Running LLaMA inference for complex case analysis...")
        
        # Run inference with optimized parameters
        response = model(
            prompt,
            max_tokens=max_tokens,
            temperature=0.1,      # Low temperature for consistent, factual answers
            top_p=0.9,            # Nucleus sampling
            top_k=40,             # Top-k sampling
            repeat_penalty=1.1,   # Penalize repetition
            stop=["\n\n", "TRANSCRIPT:", "TASK:", "---"],  # Stop tokens
            echo=False            # Don't echo the prompt
        )
        
        # Extract response text
        answer = response['choices'][0]['text'].strip()
        logger.debug(f"LLaMA raw response: {answer[:200]}...")
        
        # Parse the structured response
        result, confidence, reasoning = _parse_llama_response(answer)
        
        if result is None:
            logger.warning("Failed to parse LLaMA response, falling back")
            return None
        
        logger.info(f"✅ LLaMA analysis: {result} (confidence: {confidence:.2f}) - {reasoning}")
        
        return {
            'result': result,
            'confidence_score': confidence,
            'reasoning': reasoning,
            'method': 'llama_inference',
            'model': 'local-campaign-model'
        }
        
    except Exception as e:
        logger.error(f"LLaMA inference failed: {e}", exc_info=True)
        return None


def _parse_llama_response(response: str) -> tuple:
    """
    Parse LLaMA's structured response.
    
    Expected format:
        Result: Yes
        Confidence: 85
        Reason: Agent asked about other properties after rejection
    
    Returns:
        (result, confidence, reasoning) or (None, None, None) if parsing fails
    """
    try:
        lines = response.strip().split('\n')
        result = None
        confidence = None
        reasoning = None
        
        for line in lines:
            line = line.strip()
            
            # Parse Result
            if line.lower().startswith('result:'):
                result_text = line.split(':', 1)[1].strip().lower()
                if 'yes' in result_text:
                    result = 'Yes'
                elif 'no' in result_text:
                    result = 'No'
            
            # Parse Confidence
            elif line.lower().startswith('confidence:'):
                confidence_text = line.split(':', 1)[1].strip()
                # Extract number (handles formats like "85", "85%", "85/100")
                import re
                numbers = re.findall(r'\d+', confidence_text)
                if numbers:
                    confidence = int(numbers[0]) / 100.0
                    # Clamp to valid range
                    confidence = max(0.0, min(1.0, confidence))
            
            # Parse Reason
            elif line.lower().startswith('reason:'):
                reasoning = line.split(':', 1)[1].strip()
        
        # Validation
        if result and confidence is not None:
            if not reasoning:
                reasoning = "LLaMA detected pattern" if result == 'Yes' else "No rebuttal pattern found"
            return result, confidence, reasoning
        
        # Fallback: Try to extract from free-form response
        logger.debug("Structured parsing failed, trying free-form extraction")
        return _parse_freeform_response(response)
        
    except Exception as e:
        logger.warning(f"Failed to parse LLaMA response: {e}")
        return None, None, None


def _parse_freeform_response(response: str) -> tuple:
    """
    Fallback parser for free-form LLaMA responses.
    
    Handles cases where LLaMA doesn't follow the exact format.
    """
    import re
    
    response_lower = response.lower()
    
    # Detect result (Yes/No)
    result = None
    if 'yes' in response_lower[:100]:  # Check first 100 chars
        result = 'Yes'
    elif 'no' in response_lower[:100]:
        result = 'No'
    
    # Extract confidence if present
    confidence = None
    confidence_patterns = [
        r'confidence[:\s]+(\d+)',
        r'(\d+)%',
        r'(\d+)/100',
        r'score[:\s]+(\d+)'
    ]
    
    for pattern in confidence_patterns:
        match = re.search(pattern, response_lower)
        if match:
            confidence = int(match.group(1)) / 100.0
            confidence = max(0.0, min(1.0, confidence))
            break
    
    # Default confidence if not found
    if confidence is None:
        confidence = 0.75 if result == 'Yes' else 0.25
    
    # Extract reasoning (use first sentence)
    sentences = re.split(r'[.!?]+', response)
    reasoning = sentences[0].strip() if sentences else "LLaMA analysis"
    
    # Truncate long reasoning
    if len(reasoning) > 150:
        reasoning = reasoning[:147] + "..."
    
    return result, confidence, reasoning


def test_llama_model() -> bool:
    """
    Test if LLaMA model is working correctly.
    
    Returns:
        True if model works, False otherwise
    """
    logger.info("Testing LLaMA model...")
    
    test_transcript = """
    Owner: I'm not interested in selling right now.
    Agent: I understand. But do you have any other property you might consider selling?
    """
    
    result = llama_rebuttal_detection(test_transcript)
    
    if result:
        logger.info(f"✅ LLaMA test passed: {result['result']} (confidence: {result['confidence_score']:.2f})")
        return True
    else:
        logger.warning("❌ LLaMA test failed")
        return False


# Test on import (optional - comment out if you don't want auto-test)
if __name__ == "__main__":
    # Only test when run directly
    logging.basicConfig(level=logging.INFO)
    test_llama_model()
