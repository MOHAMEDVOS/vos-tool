"""
Singleton model manager for Whisper and semantic encoders.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_WHISPER_MODEL = None
_SEMANTIC_MODEL = None
_SEMANTIC_MODEL_LOCK = threading.RLock()
_SEMANTIC_EMBEDDINGS = None


def get_semantic_model():
    """Get or create the global semantic model instance (thread-safe singleton)."""
    global _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    if _SEMANTIC_MODEL is not None:
        return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    print("[SINGLETON] Waiting for semantic model lock...")
    with _SEMANTIC_MODEL_LOCK:
        print("[SINGLETON] Acquired semantic model lock.")
        if _SEMANTIC_MODEL is not None:
            return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

        try:
            print("[SINGLETON] Loading Sentence Transformer model (all-mpnet-base-v2)...")
            from sentence_transformers import SentenceTransformer
            from analyzer.rebuttal_detection import KeywordRepository
            from huggingface_hub import snapshot_download
            import os

            # Auto-detect GPU for Sentence Transformers
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"[SINGLETON] Device: {device}")
            
            # Prefer local cache to avoid hanging on slow network connections
            model_id = 'sentence-transformers/all-mpnet-base-v2'
            try:
                # Check for existing local snapshot
                print(f"[SINGLETON] Checking for local model snapshot: {model_id}")
                local_path = snapshot_download(
                    model_id, 
                    local_files_only=True,
                )
                print(f"[SINGLETON] Using cached model from: {local_path}")
                _SEMANTIC_MODEL = SentenceTransformer(local_path, device=device)
            except Exception as e:
                print(f"[SINGLETON] Model not in cache or cache error: {e}")
                print(f"[SINGLETON] Attempting download/load: {model_id}")
                try:
                    # Download if not found locally
                    _SEMANTIC_MODEL = SentenceTransformer('all-mpnet-base-v2', device=device)
                except Exception as download_error:
                    print(f"[SINGLETON] Failed heavy model load: {download_error}")
                    print("[SINGLETON] ⚠️ Falling back to LIGHTER model (all-MiniLM-L6-v2) for resource optimization...")
                    try:
                        _SEMANTIC_MODEL = SentenceTransformer('all-MiniLM-L6-v2', device=device)
                        print("[SINGLETON] ✅ Lighter model (all-MiniLM-L6-v2) loaded successfully")
                    except Exception as fallback_error:
                        print(f"[SINGLETON] CRITICAL: Lighter model fallback also failed: {fallback_error}")
                        raise fallback_error
            
            logger.info(f"[SINGLETON] Sentence Transformer model ready ({_SEMANTIC_MODEL.get_parameter_device() if hasattr(_SEMANTIC_MODEL, 'get_parameter_device') else device})")

            logger.info("[SINGLETON] Precomputing phrase embeddings...")
            repo = KeywordRepository()
            all_phrases = []
            phrase_metadata = []

            for category, phrases in repo.get_all_phrases().items():
                for phrase in phrases:
                    all_phrases.append(phrase)
                    phrase_metadata.append({'phrase': phrase, 'category': category})

            embeddings = _SEMANTIC_MODEL.encode(all_phrases, show_progress_bar=False)
            _SEMANTIC_EMBEDDINGS = {
                'embeddings': embeddings,
                'metadata': phrase_metadata
            }

            logger.info(f"[SINGLETON] Computed embeddings for {len(all_phrases)} phrases")
            return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

        except Exception as e:
            import traceback
            logger.error(f"[SINGLETON] Failed to load semantic model: {e}")
            logger.error(traceback.format_exc())
            logger.warning("[SINGLETON] Semantic matching will be unavailable")
            _SEMANTIC_MODEL = None
            _SEMANTIC_EMBEDDINGS = None
            return None, None
        finally:
            print("[SINGLETON] Released semantic model lock.")


def reload_semantic_embeddings():
    """Reload semantic embeddings to include newly learned phrases."""
    global _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    if _SEMANTIC_MODEL is None:
        return

    with _SEMANTIC_MODEL_LOCK:
        try:
            logger.info("🔄 [RELOAD] Reloading phrase embeddings with new learned phrases...")
            from analyzer.rebuttal_detection import KeywordRepository
            repo = KeywordRepository()
            all_phrases = []
            phrase_metadata = []

            for category, phrases in repo.get_all_phrases().items():
                for phrase in phrases:
                    all_phrases.append(phrase)
                    phrase_metadata.append({'phrase': phrase, 'category': category})

            embeddings = _SEMANTIC_MODEL.encode(all_phrases, show_progress_bar=False)
            _SEMANTIC_EMBEDDINGS = {
                'embeddings': embeddings,
                'metadata': phrase_metadata
            }

            logger.info(f"✅ [RELOAD] Reloaded embeddings for {len(all_phrases)} phrases (includes learned phrases)")

        except Exception as e:
            logger.error(f"❌ [RELOAD] Failed to reload embeddings: {e}")


def get_whisper_model():
    """
    DEPRECATED: This function is no longer used.
    The app uses AssemblyAI for transcription instead of local Whisper models.
    
    Returns None to indicate Whisper is not used.
    """
    logger.warning("get_whisper_model() called but app uses AssemblyAI for transcription. Returning None.")
    return None
    
    # Original Whisper loading code below (kept for reference but never executed)
    global _WHISPER_MODEL

    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    if not hasattr(get_whisper_model, 'lock'):
        get_whisper_model.lock = threading.Lock()

    with get_whisper_model.lock:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL

        try:
            from transformers import pipeline
            import torch

            # GPU optimization for RTX 4090
            if torch.cuda.is_available():
                device = 0
                dtype = torch.float16  # Use FP16 for faster inference on RTX 4090
                logger.info(f"[SINGLETON] Loading Whisper model on GPU (CUDA device {device}) with FP16...")
                logger.info(f"[SINGLETON] GPU: {torch.cuda.get_device_name(0)}, VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
            else:
                device = -1
                dtype = torch.float32
                logger.info("[SINGLETON] Loading Whisper model on CPU...")
            
            logger.info("[SINGLETON] Loading Whisper medium model (default)...")
            
            # Try Flash Attention 2 on GPU, fallback to eager if not available
            attn_implementation = "eager"
            if device >= 0:  # Only try Flash Attention on GPU
                try:
                    from flash_attn import flash_attn_interface  # noqa: F401
                    attn_implementation = "flash_attention_2"
                    logger.info("[SINGLETON] Using Flash Attention 2 for faster inference")
                except ImportError:
                    logger.info("[SINGLETON] Flash Attention 2 not available, using eager attention")
                    attn_implementation = "eager"
            
            # Import config to get batch size settings
            try:
                from runpod_config import BATCH_CONFIG
                batch_size = BATCH_CONFIG['gpu_batch_size'] if device >= 0 else BATCH_CONFIG['cpu_batch_size']
            except ImportError:
                batch_size = 6 if device >= 0 else 1  # Default fallback
                
            _WHISPER_MODEL = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-medium",
                device=device,
                batch_size=batch_size,  # Added batch processing
                model_kwargs={
                    "attn_implementation": attn_implementation,
                    "dtype": dtype,  # Updated: torch_dtype -> dtype
                    "use_safetensors": True,
                    "low_cpu_mem_usage": True
                }
            )
            logger.info(f"[SINGLETON] Whisper medium model loaded successfully on {'GPU' if device >= 0 else 'CPU'}")
            return _WHISPER_MODEL
        except Exception as e:
            logger.error(f"Failed to load Whisper medium model: {e}", exc_info=True)
            try:
                logger.info("[SINGLETON] Trying Whisper small model as fallback...")
                device = 0 if torch.cuda.is_available() else -1
                dtype = torch.float16 if torch.cuda.is_available() else torch.float32
                
                attn_implementation = "eager"
                if device >= 0:  # Only try Flash Attention on GPU
                    try:
                        from flash_attn import flash_attn_interface  # noqa: F401
                        attn_implementation = "flash_attention_2"
                        logger.info("[SINGLETON] Using Flash Attention 2 for fallback model")
                    except ImportError:
                        attn_implementation = "eager"
                
                _WHISPER_MODEL = pipeline(
                    "automatic-speech-recognition",
                    model="openai/whisper-small",
                    device=device,
                    model_kwargs={
                        "attn_implementation": attn_implementation,
                        "dtype": dtype,  # Updated: torch_dtype -> dtype
                        "use_safetensors": True,
                        "low_cpu_mem_usage": True
                    }
                )
                logger.info(f"[SINGLETON] Whisper small model loaded successfully (fallback) on {'GPU' if device >= 0 else 'CPU'}")
                return _WHISPER_MODEL
            except Exception as fallback_error:
                logger.error(f"Fallback Whisper small model also failed: {fallback_error}")
                _WHISPER_MODEL = None
                return None
