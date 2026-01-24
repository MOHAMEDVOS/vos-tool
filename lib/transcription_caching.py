"""
Transcription Caching Module.
Handles caching of transcription results to avoid redundant API calls and processing.
"""

import logging
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime

# Import database manager
try:
    from lib.database import get_db_manager
    _DB_IMPORT_SUCCESS = True
except ImportError:
    # Fallback/mock for standalone testing
    _DB_IMPORT_SUCCESS = False
    get_db_manager = lambda: None

logger = logging.getLogger(__name__)

class TranscriptionCacheManager:
    """Manages caching of transcription results."""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranscriptionCacheManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the transcription cache manager."""
        if self._initialized:
            return
            
        if not _DB_IMPORT_SUCCESS:
            logger.warning("Database module unavailable, transcription caching disabled")
            self.enabled = False
            return

        self.db_manager = get_db_manager()
        if not self.db_manager:
            logger.warning("Could not initialize database manager, caching disabled")
            self.enabled = False
            return
            
        self.enabled = True
        self._init_database()
        self._initialized = True
        
    def _init_database(self):
        """Initialize the transcription cache table."""
        if not self.enabled:
            return
            
        try:
            # Create table if it doesn't exist
            # Using JSONB for raw_response to store flexible provider data
            create_table_query = """
            CREATE TABLE IF NOT EXISTS transcription_cache (
                file_hash TEXT PRIMARY KEY,
                file_size BIGINT,
                transcript_text TEXT,
                raw_response JSONB,
                provider TEXT DEFAULT 'assemblyai',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_transcription_cache_created ON transcription_cache(created_at);
            """
            
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_query)
                conn.commit()
                
            logger.info("Transcription cache database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize transcription cache database: {e}")
            self.enabled = False

    def calculate_file_hash(self, file_path: Union[str, Path]) -> Optional[str]:
        """Calculate MD5 hash of a file for caching keys."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            hash_md5 = hashlib.md5()
            # Read in chunks to handle large files efficiently
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    def get_cached_transcript(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached transcript by file hash.
        
        Args:
            file_hash: The content hash of the audio file
            
        Returns:
            Dictionary with transcript data or None if not found
        """
        if not self.enabled or not file_hash:
            return None
            
        try:
            query = """
            SELECT transcript_text, raw_response, provider, created_at 
            FROM transcription_cache 
            WHERE file_hash = %s
            """
            
            result = self.db_manager.execute_query(query, (file_hash,), fetchone=True)
            
            if result:
                # Update last accessed time asynchronously/fire-and-forget? 
                # For now, let's skip the update to keep reads super fast (0 writes)
                # Or maybe update occasionally? Let's keep it simple.
                
                # Parse JSON if it's stored as a string (sqlite fallback)
                raw_response = result.get('raw_response')
                if isinstance(raw_response, str):
                    try:
                        raw_response = json.loads(raw_response)
                    except:
                        pass
                
                return {
                    'text': result.get('transcript_text'),
                    'raw_response': raw_response,
                    'provider': result.get('provider'),
                    'cached': True
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached transcript: {e}")
            return None

    def cache_transcript(self, file_hash: str, file_size: int, transcript_text: str, raw_response: Dict, provider: str = 'assemblyai') -> bool:
        """
        Store transcription result in cache.
        
        Args:
            file_hash: Content hash
            file_size: Size in bytes
            transcript_text: Full transcript string
            raw_response: Full API response dictionary
            provider: Service provider name
            
        Returns:
            True if successful
        """
        if not self.enabled or not file_hash:
            return False
            
        try:
            query = """
            INSERT INTO transcription_cache 
            (file_hash, file_size, transcript_text, raw_response, provider)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_hash) 
            DO UPDATE SET 
                last_accessed_at = CURRENT_TIMESTAMP,
                transcript_text = EXCLUDED.transcript_text,
                raw_response = EXCLUDED.raw_response
            """
            
            # Ensure raw_response is JSON serializable
            json_response = json.dumps(raw_response) if raw_response else '{}'
            
            self.db_manager.execute_query(
                query, 
                (file_hash, file_size, transcript_text, json_response, provider), 
                fetch=False
            )
            
            logger.debug(f"Cached transcript for hash {file_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error caching transcript: {e}")
            return False
