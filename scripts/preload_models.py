"""
Model Preloader for Railway/Cloud Deployments
Downloads and caches HuggingFace models on container startup.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path for imports
sys.path.append(os.getcwd())
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Silence verbose third-party logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def setup_cache_directories():
    """Create cache directories for HuggingFace models."""
    cache_dir = os.getenv('HF_HOME', '/app/.cache/huggingface')
    hub_cache = os.getenv('HF_HUB_CACHE', f'{cache_dir}/hub')
    transformers_cache = os.getenv('TRANSFORMERS_CACHE', f'{cache_dir}/transformers')

    for directory in [cache_dir, hub_cache, transformers_cache]:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Cache directory ready: {directory}")

    return cache_dir


def preload_semantic_model():
    """
    Preload the semantic model for rebuttal detection.
    Downloads sentence-transformers/all-MiniLM-L6-v2 if not cached.
    """
    try:
        logger.info("=" * 60)
        logger.info("PRELOADING SEMANTIC MODEL FOR REBUTTAL DETECTION")
        logger.info("=" * 60)

        # Import dependencies
        from sentence_transformers import SentenceTransformer
        import torch

        # Model configuration
        model_id = 'sentence-transformers/all-MiniLM-L6-v2'
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

        logger.info(f"Model: {model_id}")
        logger.info(f"Device: {device}")
        logger.info(f"PyTorch version: {torch.__version__}")

        # Attempt to load model (will download if not cached)
        logger.info("Downloading/loading model... (this may take 1-2 minutes)")
        model = SentenceTransformer(model_id, device=device)

        # Test the model with a sample encoding
        logger.info("Testing model with sample encoding...")
        test_embedding = model.encode("test phrase", show_progress_bar=False)
        logger.info(f"✓ Model loaded successfully! Embedding dimension: {len(test_embedding)}")

        # Log model info
        logger.info(f"✓ Model ready on device: {device}")
        
        # Pre-compute embeddings for hardcoded phrases
        precompute_hardcoded_embeddings(model)
        
        logger.info("=" * 60)
        return True

    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("Install with: pip install sentence-transformers")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to preload semantic model: {e}")
        logger.error("The app will fallback to exact matching only")
        import traceback
        logger.error(traceback.format_exc())
        return False

def precompute_hardcoded_embeddings(model):
    """
    Compute embeddings for hardcoded phrases during build time.
    Saves them to 'hardcoded_embeddings.pkl' for instant loading.
    """
    try:
        logger.info("Pre-computing hardcoded phrase embeddings...")
        import pickle
        # We need to import the hardcoded phrases without triggering the full DB/App logic
        # So we import just the repository class/structure or define the path manually
        from analyzer.rebuttal_detection import KeywordRepository
        
        # Load ONLY hardcoded phrases (skip_database=True is critical here)
        repo = KeywordRepository(skip_database=True)
        hardcoded_phrases = repo.get_all_phrases()
        
        all_phrases = []
        phrase_metadata = []

        for category, phrases in hardcoded_phrases.items():
            for phrase in phrases:
                all_phrases.append(phrase)
                phrase_metadata.append({'phrase': phrase, 'category': category})
        
        logger.info(f"Encoding {len(all_phrases)} hardcoded phrases...")
        embeddings = model.encode(all_phrases, show_progress_bar=False, batch_size=32)
        
        output_data = {
            'embeddings': embeddings,
            'metadata': phrase_metadata,
            'count': len(all_phrases)
        }
        
        # Save to the same directory as the model/cache or app root
        output_path = '/app/hardcoded_embeddings.pkl'
        # Fallback for local testing (windows)
        if not os.path.exists('/app') and os.name == 'nt':
             output_path = 'hardcoded_embeddings.pkl'

        with open(output_path, 'wb') as f:
            pickle.dump(output_data, f)
            
        logger.info(f"✅ Saved pre-computed embeddings to {output_path}")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to pre-compute embeddings: {e}")
        import traceback
        logger.warning(traceback.format_exc())
        return False


def check_disk_space():
    """Check available disk space."""
    try:
        import shutil
        cache_dir = os.getenv('HF_HOME', '/app/.cache/huggingface')

        # Create directory if it doesn't exist
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        total, used, free = shutil.disk_usage(cache_dir)

        logger.info(f"Disk Space Check ({cache_dir}):")
        logger.info(f"  Total: {total / (1024**3):.2f} GB")
        logger.info(f"  Used:  {used / (1024**3):.2f} GB")
        logger.info(f"  Free:  {free / (1024**3):.2f} GB")

        # Warn if less than 500MB free
        if free < 500 * 1024 * 1024:
            logger.warning(f"⚠️ Low disk space: {free / (1024**2):.0f} MB remaining")
            logger.warning("Model download may fail due to insufficient space")
            return False

        return True

    except Exception as e:
        logger.error(f"Failed to check disk space: {e}")
        return False


def main():
    """Main preload function."""
    logger.info("Starting model preload for Railway deployment...")

    # 1. Check disk space
    logger.info("\n[1/3] Checking disk space...")
    check_disk_space()

    # 2. Setup cache directories
    logger.info("\n[2/3] Setting up cache directories...")
    cache_dir = setup_cache_directories()

    # 3. Preload semantic model
    logger.info("\n[3/3] Preloading semantic model...")
    success = preload_semantic_model()

    if success:
        logger.info("\n✅ Model preload completed successfully!")
        logger.info("Application ready for rebuttal detection with semantic matching")
        return 0
    else:
        logger.warning("\n⚠️ Model preload failed!")
        logger.warning("Application will use exact matching only (fallback mode)")
        # Don't fail the container startup - app can still work with exact matching
        return 0


if __name__ == "__main__":
    sys.exit(main())
