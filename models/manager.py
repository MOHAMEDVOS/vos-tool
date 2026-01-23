"""
Singleton model manager for Whisper and semantic encoders.
"""

import logging
import threading
import time
import os

logger = logging.getLogger(__name__)

_WHISPER_MODEL = None
_SEMANTIC_MODEL = None
_SEMANTIC_MODEL_LOCK = threading.RLock()
_SEMANTIC_EMBEDDINGS = None


def get_semantic_model():
    """Get or create the global semantic model instance (thread-safe singleton)."""
    global _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    tid = threading.get_ident()

    if _SEMANTIC_MODEL is not None:
        # Avoid spamming logs for hits, but helpful for debugging race
        # print(f"[SINGLETON] [TID={tid}] Fast-path return of existing model.") 
        return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    logger.debug(f"[SINGLETON] [TID={tid}] Waiting for semantic model lock...")
    with _SEMANTIC_MODEL_LOCK:
        logger.debug(f"[SINGLETON] [TID={tid}] Acquired semantic model lock.")
        if _SEMANTIC_MODEL is not None:
            logger.debug(f"[SINGLETON] [TID={tid}] Returning existing semantic model (loaded by another thread).")
            return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

        try:
            logger.debug(f"[SINGLETON] [TID={tid}] Loading Sentence Transformer model (all-MiniLM-L6-v2)...")
            # Prevent deadlocks in multithreaded usage (e.g. batch processing)
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            from sentence_transformers import SentenceTransformer
            from analyzer.rebuttal_detection import KeywordRepository
            from huggingface_hub import snapshot_download
            
            # Auto-detect GPU for Sentence Transformers
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.debug(f"[SINGLETON] [TID={tid}] Device: {device}")
            
            # Prefer local cache to avoid hanging on slow network connections
            model_id = 'sentence-transformers/all-MiniLM-L6-v2'  # SWITCHED TO LIGHTER MODEL FOR RELIABILITY
            try:
                # Check for existing local snapshot
                logger.debug(f"[SINGLETON] [TID={tid}] Checking for local model snapshot: {model_id}")
                local_path = snapshot_download(
                    model_id, 
                    local_files_only=True,
                )
                logger.debug(f"[SINGLETON] [TID={tid}] Using cached model from: {local_path}")
                _SEMANTIC_MODEL = SentenceTransformer(local_path, device=device)
            except Exception as e:
                logger.debug(f"[SINGLETON] [TID={tid}] Model not in cache or cache error: {e}")
                logger.info(f"[SINGLETON] [TID={tid}] Attempting explicit download/load: {model_id}")

                # Retry with timeout handling (Railway may have slow network)
                max_retries = 2
                retry_delay = 5  # seconds

                for attempt in range(max_retries):
                    try:
                        logger.info(f"[SINGLETON] [TID={tid}] Download attempt {attempt + 1}/{max_retries}...")
                        # Download if not found locally
                        # Using the lightweight model (~80MB) avoids OOM and timeouts on Railway
                        _SEMANTIC_MODEL = SentenceTransformer(model_id, device=device)
                        logger.info(f"[SINGLETON] [TID={tid}] ✅ Light model (all-MiniLM-L6-v2) loaded successfully")
                        break  # Success, exit retry loop
                    except Exception as critical_error:
                        logger.error(f"[SINGLETON] [TID={tid}] Attempt {attempt + 1} failed: {critical_error}")

                        # Check for common Railway issues
                        if "No space left on device" in str(critical_error):
                            logger.error(f"[SINGLETON] [TID={tid}] 🛑 DISK FULL DETECTED. Cannot load model.")
                            raise critical_error  # Don't retry on disk full
                        elif "Connection" in str(critical_error) or "timeout" in str(critical_error).lower():
                            logger.error(f"[SINGLETON] [TID={tid}] 🛑 NETWORK ERROR DETECTED. Check HuggingFace connectivity.")
                            if attempt < max_retries - 1:
                                logger.info(f"[SINGLETON] [TID={tid}] Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                raise critical_error  # Final attempt failed
                        else:
                            raise critical_error  # Unknown error, don't retry
            
            logger.info(f"[SINGLETON] [TID={tid}] Sentence Transformer model ready ({_SEMANTIC_MODEL.get_parameter_device() if hasattr(_SEMANTIC_MODEL, 'get_parameter_device') else device})")

            logger.info(f"[SINGLETON] [TID={tid}] Precomputing phrase embeddings...")
            
            repo_start_time = time.time()
            
            # Strategy: Load hardcoded phrases immediately, then try to load learned phrases with timeout
            # This ensures we always have working embeddings, and learned phrases are included when available
            
            # Step 1: Load hardcoded phrases (fast, no DB dependency)
            logger.info(f"[SINGLETON] [TID={tid}] Loading hardcoded phrases...")
            repo_hardcoded = KeywordRepository(skip_database=True)
            hardcoded_phrases = repo_hardcoded.get_all_phrases()
            logger.info(f"[SINGLETON] [TID={tid}] Loaded {sum(len(p) for p in hardcoded_phrases.values())} hardcoded phrases")
            
            # Step 2: Try to load PRE-COMPUTED embeddings first (Fastest path)
            precomputed_loaded = False
            precomputed_path = '/app/hardcoded_embeddings.pkl'
            # Fallback for local
            if not os.path.exists(precomputed_path):
                 precomputed_path = 'hardcoded_embeddings.pkl'
            
            if os.path.exists(precomputed_path):
                try:
                    import pickle
                    logger.info(f"[SINGLETON] [TID={tid}] Found pre-computed embeddings at {precomputed_path}")
                    with open(precomputed_path, 'rb') as f:
                        data = pickle.load(f)
                        if 'embeddings' in data and 'metadata' in data:
                            _SEMANTIC_EMBEDDINGS = {
                                'embeddings': data['embeddings'],
                                'metadata': data['metadata']
                            }
                            precomputed_loaded = True
                            logger.info(f"[SINGLETON] [TID={tid}] ✅ Instantly loaded {len(data['metadata'])} pre-computed phrases!")
                except Exception as e:
                    logger.warning(f"[SINGLETON] [TID={tid}] Failed to load pre-computed embeddings: {e}")

            # Fallback: Encode hardcoded phrases runtime if precomputed missing
            if not precomputed_loaded:
                all_phrases = []
                phrase_metadata = []

                for category, phrases in hardcoded_phrases.items():
                    for phrase in phrases:
                        all_phrases.append(phrase)
                        phrase_metadata.append({'phrase': phrase, 'category': category})

                logger.info(f"[SINGLETON] [TID={tid}] Encoding {len(all_phrases)} hardcoded phrases (Runtime fallback)...")
                encode_start_time = time.time()
                embeddings = _SEMANTIC_MODEL.encode(all_phrases, show_progress_bar=False, batch_size=8)
                logger.info(f"[SINGLETON] [TID={tid}] Fast encoding finished in {time.time() - encode_start_time:.2f}s")
                
                _SEMANTIC_EMBEDDINGS = {
                    'embeddings': embeddings,
                    'metadata': phrase_metadata
                }
            
            # Step 3: Launch background thread to load and encode learned phrases
            # This ensures the first request returns instantly, and the model upgrades itself 
            # with learned phrases in the background a few seconds later.
            def background_full_load():
                """Load learned phrases and re-encode everything in background."""
                time.sleep(1)  # Yield CPU to let the main request finish
                try:
                    logger.info(f"[SINGLETON] [BACKGROUND] Starting full phrase load (hardcoded + learned)...")
                    reload_semantic_embeddings()
                except Exception as e:
                    logger.warning(f"[SINGLETON] [BACKGROUND] Background phrase loading failed: {e}")

            bg_thread = threading.Thread(target=background_full_load, daemon=True)
            bg_thread.start()
            logger.info(f"[SINGLETON] [TID={tid}] Scheduled background task to load learned phrases")

            return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS
            
            return _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

        except Exception as e:
            import traceback
            logger.error(f"[SINGLETON] [TID={tid}] Failed to load semantic model: {e}")
            logger.error(traceback.format_exc())
            logger.warning(f"[SINGLETON] [TID={tid}] Semantic matching will be unavailable")
            _SEMANTIC_MODEL = None
            _SEMANTIC_EMBEDDINGS = None
            return None, None
        finally:
            logger.debug(f"[SINGLETON] [TID={tid}] Released semantic model lock.")


def reload_semantic_embeddings():
    """Reload semantic embeddings to include newly learned phrases."""
    global _SEMANTIC_MODEL, _SEMANTIC_EMBEDDINGS

    if _SEMANTIC_MODEL is None:
        return

    with _SEMANTIC_MODEL_LOCK:
        try:
            logger.info("🔄 [RELOAD] Reloading phrase embeddings with new learned phrases...")
            from analyzer.rebuttal_detection import KeywordRepository
            # Don't skip database on reload - we want to include newly learned phrases
            repo = KeywordRepository(skip_database=False)
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
