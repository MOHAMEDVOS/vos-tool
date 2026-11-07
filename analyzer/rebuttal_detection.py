"""
Rebuttal Detection Module for VOS Tool
Handles detection of sales rebuttals in call recordings with Egyptian accent support.
"""

import time
import logging
import os
import json
import re
import threading
from typing import Dict, List, Any, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity

from models import (
    get_semantic_model as _model_get_semantic_model,
    # get_whisper_model removed - using AssemblyAI only
)


def _get_semantic_model():
    return _model_get_semantic_model()


# _get_whisper_model removed - using AssemblyAI only

try:
    from lib.app_settings_manager import app_settings as persistent_app_settings
except ImportError:
    persistent_app_settings = None

logger = logging.getLogger(__name__)

# LLaMA classifier removed - experimental feature causing hangs
# The experimental/llama_rebuttal_classifier module doesn't exist
# and llama-cpp-python is not installed (not in requirements.txt)
LLAMA_AVAILABLE = False
llama_rebuttal_detection = None
logger.info("🚫 LLaMA classifier disabled (removed - experimental feature)")


class KeywordRepository:
    """Repository of rebuttal phrases organized by category."""
    
    # Class-level cache to share across instances (P0 FIX)
    _learned_phrases_cache = None
    _learned_phrases_timestamp = None
    _learned_phrases_loaded_at = None
    _cache_is_full_db_load = False
    _cache_lock = threading.Lock()
    
    def __init__(self, skip_database: bool = False):
        """Initialize repository and load learned phrases.
        
        Args:
            skip_database: If True, skip database queries and use only hardcoded + JSON phrases.
                          Useful for batch processing to avoid connection pool exhaustion.
        """
        self._skip_database = skip_database

    REBUTTAL_PHRASES = {
        "OTHER_PROPERTY_FAMILY": [
            "do you have any other property",
            "do you have another property",
            "any other property",
            "any other properties",
            "any other properties you might consider",
            "any other property you might consider",
            "any other property you want to sell",
            "any other property you might want to sell",
            "any other property that you might want to sell",
            "any property",  # NEW: Direct "any property" detection
            "do you have any other houses",
            "do you have any other houses you want to sell",
            "do you have another house",
            "any other houses to sell",
            "any other houses you might consider selling",
            "any property you might be interested in selling",
            "any property you might be interested in selling soon",
            "do you happen to have any property that you might be interested in selling soon",
            "any property that you might be interested in selling soon",
            "do you have any other property you might be interested in selling",
            "you don't have any other property to sell",
            "you don't have another property to sell",
            "you don't own any other property",
            "you don't have any properties in general",
            "don't have any properties in general",
            "you have another property you'd like to sell",
            "do you own any other property you'd like to sell",
            # NEGATIVE PHRASING VARIATIONS (Added for better recall)
            "you don't have a property that you may sell",
            "you don't have a property that you might sell",
            "you don't have any property that you may sell",
            "you don't have any other property",
            "do you happen to have any other property",
            
            # OPPORTUNISTIC PIVOTS (Transitional phrases)
            "since i've got you",
            "since i got you",
            "since i have you",
            "while i have you",
            "before i let you go",
            "before i let you go do you have",
            "before we hang up",
            "just before you go",
            
            # INDIRECT/OPPORTUNISTIC QUESTIONS
            "do you have a piece of property",
            "piece of property for sale",
            "know someone who might be selling",
            "know anyone selling",
            "know someone by any chance", 
            "know someone by eating",  # Common transcription error for "by any chance"
            "we buy properties",
            "we are buying properties",
            "we buy houses",
            
            "any other properties besides this one",
            "any other properties aside from this one",
            "any other houses who failed",
            "any other houses to fill",
            "do you haf any ozer broperty",
            "do you haf any uzzer proberty",
            "got any other property",
            "any other properties available",
            # EGYPTIAN ENGLISH VARIATIONS
            "do you haf any uzzer broperty", "haf any uzzer broperty", "haf any ozer proberty", "haf any uzzer proberty",
            "do you haf any ozer broperty", "haf ozer broperty", "haf uzzer proberty", "haf ozer proberty",
            "got any uzzer broperty", "got any ozer broperty", "haf any uzzer bropertiz", "haf any ozer bropertiz",
            "haf any uzzer hows", "haf any ozer hows", "haf any uzzer howsiz", "haf any ozer howsiz",
            "haf any uzzer hows to sel", "haf any ozer hows to sel", "haf any uzzer hows for sale", "haf any ozer hows for sale",
            "haf any uzzer broperty you want to sel", "haf any ozer broperty you want to sel",
            "haf any uzzer broperty you'd like to sel", "haf any ozer broperty you'd like to sel",
            # NEW EXPANSIONS
            "are there any other homes you own",
            "do you own multiple properties",
            "any additional properties",
            "other real estate you might have",
            "different properties you own",
            "any other real estate assets",
            "other investment properties",
            "any commercial properties",
            "other residential properties",
            "additional homes or apartments",
            "other pieces of real estate",
            "any other land or property",
            "secondary properties",
            "backup properties",
            "other properties in your portfolio",
            "any other holdings",
            "additional real estate",
            "other owned properties",
            "any other assets you want to sell",
            "different properties you might consider",
            "other homes you might want to liquidate",
            "any other real estate you might sell",
            "additional properties you might consider",
            "other houses you might want to sell",
            "any different properties you own",
            "other real estate you might have",
            "any additional homes you have",
            "other properties you manage",
            "any other real estate you own",
            "additional pieces of property",
            "other lots or land you own",
            "any other buildings you own",
            "different structures you have",
            "other pieces of land",
            "any additional acreage",
            "other property holdings",
            "additional real estate you own",
            "other assets in real estate",
            "any other property investments",
            "different property types",
            "other real estate ventures",
            "any additional homes or land",
            "other properties you might liquidate",
            "any other real estate you might sell",
            "additional properties you might consider",
            "other homes you might want to sell",
            "any different properties you own",
            "other real estate you might have",
            "any additional properties you control",
            "do you own any properties that you might consider selling for the next few months",
            "do you own any properties that you might consider selling",
            "any properties you might consider selling",
            # NEW PATTERN: Agent qualification question about properties for sale
            "but you don't have any properties for sale?",
            # ADDITIONAL PROPERTY EXTENSIONS
            "do you have any other property you own",
            "any other property you might have",
            "do you happen to have other property",
            "any other property you could sell",
            "do you have other property available",
            "any other property you control",
            "do you own other property somewhere",
            "any other property in your name",
            "do you have property elsewhere",
            "any other property you're sitting on",
            "do you have any rental property",
            "any other property you inherited",
            "do you own any other real estate",
            "any other property you manage",
            "do you have other property investments",
            "any other property in the family",
            "do you have any vacant property",
            "any other property you're holding",
            "do you own any other homes",
            "any other property you bought",
            "do you have property in other areas",
            "any other property you acquired",
            "do you own any other buildings",
            "any other property you possess",
            "do you have any other assets",
            "any other property you maintain",
            "do you own any other lots",
            "any other property you purchased",
            "do you have any other units",
            "any other property under your name",
            "do you own any other places",
            "any other property you hold title to",
            "do you have any other addresses",
            "any other property you're responsible for",
            "do you own any other structures",
            "any other property you have interest in",
            "do you have any other locations",
            "any other property you have rights to",
            "do you own any other parcels",
            "any other property you have access to",
            # --- Added 2026-09-02 from measured false-negative analysis.
            # The agents' actual script lines, taken from 61 real rebuttals the
            # detector missed. Measured over 198 labelled calls: 38 recovered,
            # zero correctly-flagged calls lost. docs/REBUTTAL_FALSE_FLAGS.md
            "do you have another one",
            "do you have any other one",
            "have another one",
            "any other one",
        ],
        "NOT_EVEN_FUTURE_FAMILY": [
            # Agent questions/rebuttals about future selling (what agents should say)
            "would you be open to selling in the future",
            "would you be open to sell in the future", 
            "would you be open to sell maybe next year",
            "would you be open to selling maybe next year",
            "would you be interested in selling in the future",
            "would you be interested in selling maybe next year", 
            "would you be interested in selling later",
            "any chance you might sell in the future",
            "any chance you might sell later",
            "any chance you might sell next year",
            "i'm checking if there is a chance for selling in the near future",
            "checking if there is a chance for selling in the near future",
            "is there a chance for selling in the near future",
            "chance for selling in the near future",
            "i'm checking if there is a chance for sellling in the near future",  # Handle typo
            "checking if there is a chance for sellling in the near future",  # Handle typo
            "i'm checking if there is a chance for selling",
            "checking if there is a chance for selling",
            "what about in the future",
            "even in the near future?",
            "even in the near future",
            "now or even in the near future",
            "even in the future?",
            "maybe down the road?",
            "not even possible in the future?",
            # Agent negotiation/agreement phrases for future selling
            "you think you could possibly sell the next year or so",
            "think you could possibly sell in the next year",
            "could you possibly sell the next year or so",
            "you think you might sell the next year or so",
            "could we come to an agreement next year",
            "think we could come to an agreement in the future",
            "you think you could sell maybe next year",
            "could you possibly consider selling next year",
            # --- Added 2026-09-02 from measured false-negative analysis.
            # The agents' actual script lines, taken from 61 real rebuttals the
            # detector missed. Measured over 198 labelled calls: 38 recovered,
            # zero correctly-flagged calls lost. docs/REBUTTAL_FALSE_FLAGS.md
            "not even down the road",
            "not even a possibility down the road",
            "not even anytime soon",
            "not even in the future",
            "not even in the near future",
            "not even a possibility",
            "even down the road",
            "not even like in the next few months",
            "not even sometime",
            "not even in your future",
        ],
        "CALLBACK_SCHEDULE_FAMILY": [
            "when is the best time to call you back", "what's a good time to reach you",
            "can i call you back later", "let me take down your details",
            # ADDITIONAL CALLBACK EXTENSIONS
            "when would be a good time to call back",
            "what time works best for you",
            "when should I follow up with you",
            "what's the best time to reach you",
            "when can I call you again",
            "what time is convenient for you",
            "when would you prefer I call",
            "what's a good callback time",
            "when is it okay to call back",
            "what time should I try again",
            "when would be better to talk",
            "what's your preferred call time",
            "when can we talk again",
            "what time works for your schedule",
            "when should I check back with you"
        ],
        "WOULD_CONSIDER_FAMILY": [
            "would you consider selling", "would you be interested in an offer",
            "could we make you an offer",
            # ADDITIONAL WOULD_CONSIDER EXTENSIONS
            "would you consider an offer",
            "would you be interested in selling",
            "would you think about an offer",
            "would you entertain an offer",
            "would you be open to an offer",
            "would you consider a cash offer",
            "would you be willing to sell",
            "would you be interested in a deal",
            "would you consider our offer",
            "would you be open to selling",
            # --- Added 2026-09-02 from measured false-negative analysis.
            # The agents' actual script lines, taken from 61 real rebuttals the
            # detector missed. Measured over 198 labelled calls: 38 recovered,
            # zero correctly-flagged calls lost. docs/REBUTTAL_FALSE_FLAGS.md
            "thinking about selling",
            "open to selling",
            "you would be open to selling",
            "open to selling at all",
            "considering selling in the future",
        ],
        "WE_BUY_OFFER_FAMILY": [
            "we buy houses all cash", "no commission, no fees",
            "we pay all closing costs", "as-is, no repairs",
            "buying properties all over the state",
            # ADDITIONAL WE_BUY EXTENSIONS
            "we buy houses for cash",
            "we purchase properties quickly",
            "we buy in any condition",
            "we close fast with cash",
            "we buy houses as-is",
            "we purchase homes directly",
            "we buy properties all cash",
            "we close in days not months",
            "we buy without inspections",
            "we purchase without repairs",
            # Price negotiation and offer discussion rebuttals
            "would that be negotiable",
            "is that price negotiable",
            "would you consider a lower offer",
            "how did you come up with this number",
            "how did you arrive at that price",
            "what's your best price",
            "would you take less",
            "is there room for negotiation",
            "can we work on the price",
            "would you entertain an offer",
            "what would you accept",
            "is that your final price"
        ],
        "FLEXIBLE_CONVENIENT_FAMILY": [
            "we're very flexible with timing", "very simple process",
            "fast closing, your convenience",
            "we have flexible closing time to six months",
            "flexible closing time to six months",
            "we have flexible closing time",
            "flexible closing time"
        ],
        "DISCOVERED_FROM_TRAINING_FAMILY": [
            "any other property you have"
        ],
        "MIXED_FUTURE_OTHER_FAMILY": [
            "not even in the near future but do you have any other property",
            "not even in the future but do you have any other property",
            "no plans to sell but do you have any other property",
            "not interested in selling but do you have any other property",
            "not now maybe later do you have any other property",
            "not now maybe next year do you have any other property",
            "not selling now but do you have any other property",
            "not for sale right now but do you have any other property",
            "not for sale now but any other property you might want to sell",
            "not ready to sell this one but do you have any other property",
            "not selling this one but maybe another property",
            "not this property but maybe another one",
            "not this property but maybe another house",
            "not this one but another one",
            "not this one but maybe another property",
            "not this house but maybe another one",
            "do you have any other properties besides this",
            "do you have something else you might sell",
            "do you have another property instead",
            "any other property instead of this one",
            "do you own another property instead",
            "do you happen to own another property",
            # NEW ADDITIONS
            "do you have another property that you're considering selling",
            "do you have other properties that might be available",
            "do you have any additional properties",
            "do you have other homes or properties",
            "do you have another piece of property",
            # NEW PATTERN: General qualification question
            "do you have any",
            # NEW PATTERN: Agent asking about additional properties to sell
            "do you have another one you think about sellling it sometime soon?",
            "do you have another one",
            "do you have another one?",
            "do you guys have another one",
            "do you guys have another one that might be up for sales",
            "do you have another one that might be up for sales",
            "another one that might be up for sales",
            "do you have another one that might be up for sale",
            "do you have different properties",
            "do you have other real estate holdings",
            "do you have alternative properties",
            "do you have secondary properties",
            "do you have backup properties",
            "do you have other investment properties",
            # "DO YOU HAVE ANY OTHER" VARIATIONS
            "do you have any other property",
            "do you have any other properties",
            "do you have any other home",
            "do you have any other homes",
            "do you have any other house",
            "do you have any other houses",
            "do you have any other real estate",
            "do you have any other investment",
            "do you have any other asset",
            "do you have any other assets",
            # EXACT PHRASE REQUESTED
            "do you have any other",
            # AGENT QUALIFICATION AFTER REJECTION (Business Rule)
            "do you have a property that you might be interested in selling",
            "do you have any property that you might be interested in selling",
            "do you have property that you might be interested in selling",
            # VARIATIONS MATCHING USER'S TRANSCRIPT
            "did you happen to have any other",
            "do you happen to have any other",
            "do you have any other for sale",
            "did you happen to have any other for sale",
            # ADDITIONAL COMMON VARIATIONS
            "do you have any other properties for sale",
            "do you have anything else for sale",
            "do you happen to own any other",
            "do you happen to have other",
            # ADDITIONAL MIXED_FUTURE_OTHER_FAMILY EXTENSIONS
            "not selling this but do you have any other property",
            "not this one but any other property you own",
            "not interested in this but other property maybe",
            "not this house but other houses you have",
            "not ready for this but other property perhaps",
            "not this place but any other places you own",
            "not selling here but elsewhere maybe",
            "not this location but other locations you have",
            "not this address but other addresses you own",
            "not this building but other buildings maybe",
            "not this home but other homes you have",
            "not this unit but other units you own",
            "not this lot but other lots maybe",
            "not this parcel but other parcels you have",
            "not this asset but other assets you own",
            "not this investment but other investments maybe",
            "not this structure but other structures you have",
            "not ready here but ready elsewhere maybe",
            "not selling now but other property later",
            "not this property but different property maybe",
            "not interested here but interested elsewhere",
            "not this time but other property anytime",
            "not this deal but other deals maybe",
            "not this opportunity but other opportunities",
            "not this situation but other situations maybe",
            # --- Added 2026-09-02 from measured false-negative analysis.
            # The agents' actual script lines, taken from 61 real rebuttals the
            # detector missed. Measured over 198 labelled calls: 38 recovered,
            # zero correctly-flagged calls lost. docs/REBUTTAL_FALSE_FLAGS.md
            "maybe in the next few months",
            "maybe in the next year",
            "maybe sometime in",
            "maybe later on this year",
            "in the near future",
            "sell in the near future",
            "anytime soon",
            "down the road",
            "by the end of the year",
        ]
    }

    REBUTTAL_REGEX_PATTERNS = {
        # Pattern 1: Direct "other properties" questions
        "OTHER_PROPERTY_FAMILY": [
            r'\bany\s+other\s+propert(?:y|ies)\b',
            r'\banother\s+propert(?:y|ies)\b',
            r'\bother\s+propert(?:y|ies)\b',
            r'\badditional\s+propert(?:y|ies)\b',
            r'\bother\s+house\b',
            r'\banother\s+house\b',
        ],
        
        # Pattern 2: General property inquiries
        "GENERAL_INQUIRY": [
            r'\bpropert(?:y|ies).*sell\b',
            r'\bsell.*propert(?:y|ies)\b',
            r'\bpropert(?:y|ies)\s+for\s+sale\b',
            r'\bpropert(?:y|ies)\s+to\s+sell\b',
            r'\bfor\s+sale\b',
            r'\bselling.*propert(?:y|ies)\b',
        ],
        
        # Pattern 3: Ownership expansion questions
        "OWNERSHIP_EXPANSION": [
            r'\bdo\s+you\s+own.*propert(?:y|ies)\b',
            r'\bdo\s+you\s+have.*propert(?:y|ies)\b',
            r'\bown\s+any\s+propert(?:y|ies)\b',
            r'\bhave\s+any\s+propert(?:y|ies)\b',
            r'\bany\s+propert(?:y|ies).*own\b',
            r'\bany\s+propert(?:y|ies).*have\b',
        ],
        
        # Pattern 4: Business declaration + invitation
        "BUSINESS_DECLARATION": [
            r'\bwe\s+buy\s+propert(?:y|ies)\b',
            r'\bi\s+buy\s+propert(?:y|ies)\b',
            r'\bbuying\s+propert(?:y|ies)\b',
            r'\binvest.*propert(?:y|ies)\b',
            r'\bpurchas.*propert(?:y|ies)\b',
        ],
        
        # Pattern 5: Pivot phrases
        "PIVOT_PHRASE": [
            r'\bsince.*phone\b',
            r'\bbefore.*let.*go\b',
            r'\bby\s+the\s+way\b',
            r'\bwhile.*have.*you\b',
            r'\bapolog.*but.*since\b',
        ],
        
        # Pattern 6: Location-based inquiries
        "LOCATION_BASED": [
            r'\bpropert(?:y|ies).*in\s+(utah|colorado|kentucky|new jersey|new york|pennsylvania|texas|california|nevada|idaho)\b',
            r'\bin\s+(utah|colorado|kentucky|new jersey|new york|pennsylvania|texas|california|nevada|idaho).*propert(?:y|ies)\b',
        ],
        
        # Pattern 7: Referral questions
        "REFERRAL": [
            r'\bknow\s+someone\b',
            r'\bknow\s+anyone\b',
            r'\bknow.*selling\b',
            r'\brefer.*propert(?:y|ies)\b',
            r'\brecommend.*propert(?:y|ies)\b',
        ],
        
        # Pattern 8: Alternative property questions
        "ALTERNATIVE_PROPERTY": [
            r'\bany.*propert(?:y|ies).*consider\b',
            r'\bpropert(?:y|ies).*consider.*selling\b',
            r'\bwould\s+you\s+consider.*propert(?:y|ies)\b',
            r'\bmight\s+consider.*propert(?:y|ies)\b',
        ],
    }

    @classmethod
    def get_compiled_regex_patterns(cls) -> Dict[str, List[re.Pattern]]:
        """Return compiled regex patterns for efficiency."""
        compiled_patterns = {}
        for category, patterns in cls.REBUTTAL_REGEX_PATTERNS.items():
            compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                for pattern in patterns
            ]
        return compiled_patterns

    def _load_learned_phrases(self) -> Dict[str, List[str]]:
        """Load learned phrases from PostgreSQL database or JSON file."""
        try:
            db_cache_seconds = int(os.getenv("REBUTTAL_DB_CACHE_SECONDS", "300"))
            
            # Check cache with lock (P0 FIX)
            with self._cache_lock:
                # Only return cache if it matches the request type (DB vs No-DB)
                # If we need DB (skip_database=False) but cache is partial (JSON-only), we MUST reload
                cache_is_valid_type = (self._skip_database) or (self._cache_is_full_db_load)
                
                if (
                    self._learned_phrases_cache is not None
                    and self._learned_phrases_loaded_at is not None
                    and (time.time() - self._learned_phrases_loaded_at) < db_cache_seconds
                    and cache_is_valid_type
                ):
                    return self._learned_phrases_cache

            if not self._skip_database:
                try:
                    logger.info("Attempting to load phrases from database...")
                    from lib.database import get_db_manager
                    
                    db = get_db_manager()
                    
                    if db:
                        # Database manager has built-in timeout (default 30s, configurable via DB_QUERY_TIMEOUT)
                        # For faster fallback, we can set a shorter timeout for this specific query
                        # But the main fix is using skip_database=True during model initialization
                        query = "SELECT category, phrase FROM rebuttal_phrases ORDER BY category, phrase"
                        logger.debug("Executing DB query for learned phrases...")
                        query_start = time.time()
                        results = db.execute_query(query, fetch=True)
                        logger.debug(f"DB query finished in {time.time()-query_start:.2f}s, rows: {len(results) if results else 0}")
                        
                        if results:
                            learned_phrases = {}
                            for row in results:
                                category = row['category']
                                phrase = row['phrase']
                                if category not in learned_phrases:
                                    learned_phrases[category] = []
                                learned_phrases[category].append(phrase)
                            
                            with self._cache_lock:
                                self._learned_phrases_cache = learned_phrases
                                self._learned_phrases_timestamp = None  # Database doesn't have mtime
                                self._learned_phrases_loaded_at = time.time()
                                self._cache_is_full_db_load = True # Mark as full DB load
                            
                            logger.info(f"Loaded {sum(len(p) for p in learned_phrases.values())} learned phrases from database")
                            return learned_phrases
                                
                                
                except Exception as e:
                    logger.debug(f"Could not load from database: {e}, falling back to JSON")
                    # Fallback to JSON - this ensures we can still load hardcoded phrases even if DB fails
                    pass
            
            from pathlib import Path

            repository_path = Path("dashboard_data") / "rebuttal_repository.json"

            if not repository_path.exists():
                return {}

            current_mtime = os.path.getmtime(repository_path)
            
            # Check cache again before file read (P0 FIX)
            with self._cache_lock:
                if (self._learned_phrases_cache is not None and 
                    self._learned_phrases_timestamp == current_mtime):
                    return self._learned_phrases_cache
            
            with open(repository_path, 'r', encoding='utf-8') as f:
                repository_data = json.load(f)

            learned_phrases = repository_data.get("categories", {})

            with self._cache_lock:
                self._learned_phrases_cache = learned_phrases
                self._learned_phrases_timestamp = current_mtime
                self._learned_phrases_loaded_at = time.time()
                self._cache_is_full_db_load = False
            
            logger.debug(f"Loaded {sum(len(p) for p in learned_phrases.values())} learned phrases from repository")
            return learned_phrases
            
        except Exception as e:
            logger.warning(f"Failed to load learned phrases from repository: {e}")
            return {}

    def get_all_phrases(self) -> Dict[str, List[str]]:
        """Get all rebuttal phrases organized by category, merging hardcoded with learned phrases."""
        merged_phrases = {}
        
        # Copy hardcoded phrases (deep copy to avoid modifying original)
        for category, phrases in self.REBUTTAL_PHRASES.items():
            merged_phrases[category] = list(phrases)
        
        learned_phrases = self._load_learned_phrases()

        for category, phrases in learned_phrases.items():
            if category not in merged_phrases:
                merged_phrases[category] = []

            # Use lowercase comparison to avoid duplicates
            existing_lower = {p.lower().strip() for p in merged_phrases[category]}
            for phrase in phrases:
                phrase_lower = phrase.lower().strip()
                if phrase_lower not in existing_lower:
                    merged_phrases[category].append(phrase)
                    existing_lower.add(phrase_lower)
                    # logger.debug(f"Added learned phrase: '{phrase}' to {category}")
        
        return merged_phrases

    def get_all_regex_patterns(self) -> Dict[str, List[str]]:
        """Get all rebuttal regex patterns organized by category."""
        return self.REBUTTAL_REGEX_PATTERNS

    def get_phrases_by_category(self, category: str) -> List[str]:
        """Get phrases for a specific category (includes learned phrases)."""
        all_phrases = self.get_all_phrases()
        return all_phrases.get(category, [])

    def expand_phrases(self) -> Dict[str, List[str]]:
        """Apply expansion rules to generate more variations."""
        return self.REBUTTAL_PHRASES


class SemanticDetectionEngine:
    """Phrase matching and categorization with confidence scoring using both exact and semantic matching."""

    def __init__(self, keyword_repo: KeywordRepository):
        self.keyword_repo = keyword_repo
        self.semantic_model = None
        self.phrase_embeddings = None
        self.semantic_threshold = 0.68
        self._initialization_attempted = False
        if persistent_app_settings is not None:
            try:
                configured_threshold = persistent_app_settings.get_semantic_threshold()
                self.semantic_threshold = float(configured_threshold)
            except Exception:
                logger.warning("Failed to load semantic threshold from settings; using default 0.68")
        self.semantic_threshold = max(0.5, min(self.semantic_threshold, 0.9))
        
        self.regex_patterns = self.keyword_repo.get_compiled_regex_patterns()

        self.llm_evaluator = None
        self.llm_fallback_enabled = os.getenv("LLM_FALLBACK_ENABLED", "true").lower() == "true"
        self.llm_confidence_threshold = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.70"))
        
        if self.llm_fallback_enabled:
            try:
                from analyzer.llm_rebuttal_evaluator import LLMRebuttalEvaluator
                groq_api_key = os.getenv("GROQ_API_KEY", "")
                if groq_api_key:
                    self.llm_evaluator = LLMRebuttalEvaluator(api_key=groq_api_key)
                    logger.info(f"🤖 LLM fallback evaluator initialized (threshold: {self.llm_confidence_threshold:.2f})")
                else:
                    logger.warning(
                        "GROQ_API_KEY not set - LLM rebuttal stage DISABLED. Rebuttals that "
                        "the phrase library does not match will be recorded as 'No Rebuttal', "
                        "which flags the agent. See docs/REBUTTAL_FALSE_FLAGS.md"
                    )
                    self.llm_fallback_enabled = False
            except Exception as e:
                logger.warning(f"Failed to initialize LLM evaluator: {e}, continuing without fallback")
                self.llm_fallback_enabled = False

        # We no longer load models eagerly in __init__ to prevent OOM stalls on startup
        logger.info("Semantic detection engine created (Lazy Loading enabled)")

    def _lazy_initialize_models(self):
        """Load models only when needed (on first detection call).
        
        IMPORTANT: If the singleton model is still loading in another thread,
        this will return None but we should retry on next call.
        """
        if self.semantic_model is not None:
            return  # Already have the model

        if not self._initialization_attempted:
            logger.info("Lazily initializing semantic detection engine with singleton model...")
            self._initialization_attempted = True

        try:
            self.semantic_model, self.phrase_embeddings = _get_semantic_model()

            if self.semantic_model is None:
                tid = threading.get_ident()
                logger.debug(f"Semantic model not yet available from singleton (TID={tid}), will retry next call")
            else:
                logger.info("✅ Semantic detection engine lazy-initialized successfully")
        except Exception as e:
            import traceback
            tid = threading.get_ident()
            logger.error(f"Failed to lazy-load semantic model (TID={tid}): {e}")
            logger.error(f"Exception traceback:\n{traceback.format_exc()}")
            logger.warning("Semantic matching will be unavailable, falling back to exact matching only")
            self.semantic_model = None
            self.phrase_embeddings = None

    def detect_rebuttals(self, transcript: str, dialogue: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Detect all matching rebuttal phrases using exact and semantic matching (Lazy Load enabled)."""
        # Lazy initialization: Try to get model if we don't have it yet
        # This allows retries if the model was still loading on previous calls
        if self.semantic_model is None and transcript and len(transcript.strip()) > 0:
            self._lazy_initialize_models()
            
        logger.debug(f"🔍 Starting rebuttal detection on transcript: '{transcript[:100]}...'")
        matches = []
        feedback_metadata = {}
        transcript_lower = transcript.lower()

        # 1. Primary: Exact matching (fastest)
        logger.debug("Running exact phrase matching...")
        exact_matches = self._detect_exact_matches(transcript_lower)
        matches.extend(exact_matches)

        best_confidence = max([m['confidence'] for m in matches], default=0.0)
        
        # 1.5 NEW: Regex matching (flexible patterns with Context Awareness)
        # Only run regex if we don't have a high-confidence exact match
        if best_confidence < 0.95:
            logger.debug("Running regex pattern matching with context awareness...")
            
            # Context Awareness: Extract relevant segments (post-denial)
            # This reduces false positives by only looking at what the Agent says AFTER an objection
            analysis_segments = self._extract_post_denial_agent_segments(transcript, dialogue)
            
            regex_matches = self._detect_regex_matches(analysis_segments)
            matches.extend(regex_matches)
            best_confidence = max([m['confidence'] for m in matches], default=0.0)

        # 2. Secondary: Semantic matching (AI-powered)
        # SHORT-CIRCUIT: Skip semantic matching if we have a high-confidence exact/regex match (efficiency fix)
        if best_confidence >= 0.95:
            logger.info(f"✨ High confidence exact match found ({best_confidence:.2f}), skipping semantic and LLM matching to save time")
        elif self.semantic_model is not None:
            logger.debug("Running semantic AI matching...")
            semantic_matches = self._detect_semantic_matches(transcript)
            filtered_semantic_matches = self._filter_duplicate_matches(exact_matches, semantic_matches)
            matches.extend(filtered_semantic_matches)

            self._track_semantic_matches_for_learning(filtered_semantic_matches, transcript)

            best_confidence = max([m['confidence'] for m in matches], default=0.0)
        else:
            logger.warning("❌ Semantic model not available, using exact matching only")


        # 3. NEW: LLM Fallback for low-confidence cases
        # Only run LLM if best confidence is still below threshold (saves API usage)
        if self.llm_fallback_enabled and self.llm_evaluator and best_confidence < self.llm_confidence_threshold:
            logger.info(f"🤖 LLM fallback triggered (confidence: {best_confidence:.2f} < {self.llm_confidence_threshold:.2f})")
            
            objection_category = 'not_interested'  # Default
            if matches:
                temp_matches = sorted(matches, key=lambda x: x['confidence'], reverse=True)
                objection_category = temp_matches[0].get('category', 'not_interested')

            try:
                llm_result = self.llm_evaluator.evaluate_rebuttal(
                    transcript=transcript,
                    objection_category=objection_category,
                    semantic_candidates=matches if matches else None,
                    dialogue=dialogue
                )

                if llm_result.get('source') == 'llm_evaluation_failed':
                    # Infrastructure failure (Groq error, timeout, bad JSON) - not a real
                    # "no rebuttal" verdict. Keep whatever semantic candidates we already had
                    # instead of letting an API failure veto them.
                    logger.warning(
                        f"⚠️ LLM evaluation unavailable ({llm_result.get('reasoning', 'unknown error')}); "
                        f"keeping {len(matches)} existing semantic candidate(s) instead of vetoing"
                    )
                elif llm_result.get('rebuttal_detected', False):
                    llm_match = {
                        'phrase': llm_result.get('matched_phrase', transcript[:100]),
                        'category': objection_category,
                        'confidence': float(llm_result.get('confidence', 0.75)),
                        'match_type': 'llm_evaluation',
                        'reasoning': llm_result.get('reasoning', ''),
                        'api_latency': llm_result.get('api_latency', 0.0)
                    }
                    matches.append(llm_match)
                    logger.info(f"✅ LLM detected rebuttal: '{llm_match['phrase'][:50]}...' (confidence: {llm_match['confidence']:.2f})")
                else:
                    # LLM explicitly said no rebuttal
                    reason = llm_result.get('reasoning', 'No reason provided')
                    logger.info(f"❌ LLM did not detect rebuttal: {reason}")

                    feedback_metadata['feedback'] = reason
                    feedback_metadata['llm_reasoning'] = reason # Keep for compatibility
                    feedback_metadata['llm_confidence'] = llm_result.get('confidence', 0.0)
                    
                    # IMPORTANT: Clear any low-confidence candidates that triggered this check
                    # LLM has the "Final Say" or "Veto Power"
                    if matches:
                        logger.info(f"🗑️ Clearing {len(matches)} low-confidence semantic candidates based on LLM veto")
                        matches = []
                    
            except Exception as e:
                logger.error(f"LLM fallback evaluation failed: {e}")
        elif best_confidence >= self.llm_confidence_threshold:
            logger.debug(f"⏭️ Skipping LLM fallback (confidence {best_confidence:.2f} >= {self.llm_confidence_threshold:.2f})")

        best_confidence_final = max([m['confidence'] for m in matches], default=0.0)
        if len(matches) == 0 or best_confidence_final < 0.70:
            logger.debug(f"ℹ️ Final confidence: {best_confidence_final:.2f}")

        matches.sort(key=lambda x: x['confidence'], reverse=True)

        if matches:
            best_match = matches[0]
            logger.debug(f"✅ Best match: '{best_match['phrase']}' ({best_match['match_type']}) confidence: {best_match['confidence']:.3f}")
            
            # Populate feedback even for non-LLM matches so user knows WHY it was flagged
            if 'feedback' not in feedback_metadata:
                match_type = best_match.get('match_type', 'unknown')
                phrase = best_match.get('phrase', 'unknown')
                if match_type == 'regex':
                    feedback_metadata['feedback'] = f"Detected via regex pattern matching: {phrase}"
                elif match_type == 'exact':
                    feedback_metadata['feedback'] = f"Detected exact keyword match: '{phrase}'"
                elif match_type == 'semantic':
                    feedback_metadata['feedback'] = f"Detected semantic similarity to: '{phrase}' (score: {best_match.get('confidence', 0):.2f})"
                elif match_type == 'llm_evaluation':
                    # Bug found 2026-09-03: this branch was missing entirely, so
                    # feedback_metadata['feedback'] stayed unset and the
                    # unconditional copy below raised KeyError -- meaning every
                    # call where the LLM stage actually FOUND a rebuttal crashed
                    # and got silently swallowed by the except in the caller,
                    # logged as "LLM evaluation failed" even though the LLM had
                    # succeeded. Never observed before because GROQ_API_KEY was
                    # unset in every environment until now.
                    feedback_metadata['feedback'] = best_match.get(
                        'reasoning') or f"LLM identified a rebuttal attempt: '{phrase}'"
                else:
                    feedback_metadata['feedback'] = f"Detected via {match_type}: '{phrase}'"

                # Copy to compatibility key
                feedback_metadata['llm_reasoning'] = feedback_metadata['feedback']
        else:
            logger.debug("❌ No rebuttals detected by any method")
            if 'feedback' not in feedback_metadata:
                feedback_metadata['feedback'] = "No rebuttal detected. No matching keywords or LLM-identified objections found."
                feedback_metadata['llm_reasoning'] = feedback_metadata['feedback']

        return matches, feedback_metadata


    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for robust exact matching.

        - Lowercase
        - Remove common punctuation
        - Collapse multiple spaces
        """
        text = text.lower()
        # Remove common punctuation characters
        text = re.sub(r"[.,!?;:\\-]", " ", text)
        # Collapse multiple whitespace into single spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _detect_exact_matches(self, transcript_lower: str) -> List[Dict[str, Any]]:
        """Detect exact phrase matches with punctuation-insensitive matching."""
        matches = []

        normalized_transcript = self._normalize_for_matching(transcript_lower)

        for category, phrases in self.keyword_repo.get_all_phrases().items():
            for phrase in phrases:
                normalized_phrase = self._normalize_for_matching(phrase)
                if normalized_phrase and normalized_phrase in normalized_transcript:
                    confidence = self._calculate_exact_confidence(phrase, transcript_lower)
                    matches.append({
                        'phrase': phrase,
                        'category': category,
                        'confidence': confidence,
                        'match_type': 'exact'
                    })

        return matches

    def _detect_semantic_matches(self, transcript: str) -> List[Dict[str, Any]]:
        """Detect semantic matches using Sentence Transformers with batch encoding."""
        if self.phrase_embeddings is None:
            logger.warning("⚠️ Semantic embeddings not available, skipping semantic matching")
            return []
        
        if self.semantic_model is None:
            logger.warning("⚠️ Semantic model not available, skipping semantic matching")
            return []
        
        matches = []
        
        try:
            # Strategy 1: Split transcript into sentences for better semantic matching
            sentences = self._split_into_sentences(transcript)
            # Filter short sentences and polite closing sentences without rebuttal content
            valid_sentences = [
                s for s in sentences
                if len(s.strip()) >= 3 and not self._is_polite_closing(s)
            ]
            
            # Strategy 2: Also try matching longer context windows (2-3 sentences together)
            # This helps catch rebuttals that span multiple sentences
            context_windows = []
            if len(valid_sentences) >= 2:
                for i in range(len(valid_sentences) - 1):
                    window = valid_sentences[i] + " " + valid_sentences[i + 1]
                    if len(window.strip()) >= 10:  # Only meaningful windows
                        context_windows.append(window)
                # Also try 3-sentence windows for longer rebuttals
                if len(valid_sentences) >= 3:
                    for i in range(len(valid_sentences) - 2):
                        window = valid_sentences[i] + " " + valid_sentences[i + 1] + " " + valid_sentences[i + 2]
                        if len(window.strip()) >= 15:
                            context_windows.append(window)
            
            # Strategy 3: Also try the full transcript (for very short transcripts)
            all_texts_to_match = list(valid_sentences)
            if context_windows:
                all_texts_to_match.extend(context_windows)
            if len(transcript.strip()) < 500 and len(transcript.strip()) > 10:
                all_texts_to_match.append(transcript.strip())
            
            if not all_texts_to_match:
                logger.debug("No valid text segments for semantic matching")
                return []
            
            logger.debug(f"Semantic matching on {len(all_texts_to_match)} text segments (sentences + context windows)")
            
            # Batch encode all texts at once for speed
            logger.debug(f"Encoding {len(all_texts_to_match)} segments with semantic model...")
            text_embeddings = self.semantic_model.encode(all_texts_to_match, batch_size=8, show_progress_bar=False)
            logger.debug("Encoding completed")
            
            similarities = cosine_similarity(text_embeddings, self.phrase_embeddings['embeddings'])

            best_similarities = {}  # Track best match per phrase to avoid duplicates
            for text_idx, text_segment in enumerate(all_texts_to_match):
                for emb_idx, similarity in enumerate(similarities[text_idx]):
                    if similarity >= self.semantic_threshold:
                        phrase_info = self.phrase_embeddings['metadata'][emb_idx]
                        phrase_key = (phrase_info['phrase'], phrase_info['category'])

                        if phrase_key not in best_similarities or similarity > best_similarities[phrase_key]['confidence']:
                            best_similarities[phrase_key] = {
                                'phrase': phrase_info['phrase'],
                                'category': phrase_info['category'],
                                'confidence': float(similarity),
                                'match_type': 'semantic',
                                'matched_sentence': text_segment.strip()
                            }
            
            matches = list(best_similarities.values())
            if matches:
                logger.debug(f"✅ Semantic matching found {len(matches)} matches (threshold: {self.semantic_threshold:.2f})")
                for match in matches[:3]:
                    logger.debug(f"  - '{match['phrase']}' (confidence: {match['confidence']:.3f})")
            else:
                logger.debug(f"ℹ️ No semantic matches above threshold {self.semantic_threshold:.2f}")
                if similarities.size > 0:
                    max_sim = similarities.max()
                    if max_sim > 0.5:
                        logger.debug(f"Highest similarity found: {max_sim:.3f} (below threshold {self.semantic_threshold:.2f})")
            
        except Exception as e:
            logger.error(f"Error in semantic matching: {e}", exc_info=True)
        
        return matches

    def _extract_post_denial_agent_segments(self, transcript: str, dialogue: Optional[str] = None) -> List[str]:
        """
        Extract agent segments that occur after initial denial or rejection.
        Uses formatted dialogue (Agent:/Owner:) if available, otherwise falls back to raw transcript analysis.
        """
        segments = []
        source_text = dialogue if dialogue else transcript

        if not dialogue and "Agent:" not in source_text:
            return [transcript]

        # Regex to split dialogue into identifying speaker turns
        # Matches "Agent: text" or "Owner: text"
        # Handles potential newlines and spacing
        speaker_pattern = r'(Agent|Owner):\s*(.*?)(?=(?:\n(?:Agent|Owner):|\Z))'
        matches = re.findall(speaker_pattern, source_text, re.DOTALL | re.IGNORECASE)
        
        if not matches:
             return [transcript]

        # Find the first denial/rejection point from OWNER
        denial_found = False
        denial_patterns = [
            r'\bno\b',
            r'\bnot\s+the\s+owner\b',
            r'\bnot\s+interested\b',
            r'\bwrong\s+number\b',
            r'\bdon\'t\s+own\b',
            r'\bdoesn\'t\s+lives\b',
            r'\bdoesn\'t\s+live\b',
            r'\bnot\s+for\s+sale\b',
            r'\bstop\s+calling\b',
            r'\btake\s+me\s+off\b',
            r'\bremove\s+me\b',
            r'\brent\b',
            r'\brenter\b',
            r'\brenting\b',
            r'\brented\b',
        ]
        
        compiled_denials = [re.compile(p, re.IGNORECASE) for p in denial_patterns]

        for speaker, text in matches:
            text = text.strip()
            speaker = speaker.strip().capitalize()
            
            if speaker == "Owner" and not denial_found:
                for pattern in compiled_denials:
                    if pattern.search(text):
                        denial_found = True
                        break

            elif speaker == "Agent" and denial_found and text:
                segments.append(text)
        
        # If no denial found but we have dialogue, maybe return all agent segments?
        # Or return empty? For now, if no denial is found, we might want to be conservative 
        # and distinct from "no rebuttal".
        # But if the user wants to find "rebuttal pattern", it implies a rebuttal to SOMETHING.
        # If explicit denial isn't found, maybe the pattern itself is enough (e.g. "Do you have any other property").
        # So providing ALL agent segments is safer fallback if strict denial isn't detected.
        if not segments and matches:
             return [m[1].strip() for m in matches if m[0].strip().capitalize() == "Agent"]
             
        return segments

    def _detect_regex_matches(self, segments_or_text: Any) -> List[Dict[str, Any]]:
        """
        Detect rebuttal using robust regex patterns from KeywordRepository.
        Args:
            segments_or_text: List of strings (segments) or single string (transcript)
        """
        matches = []

        if isinstance(segments_or_text, str):
            segments = [segments_or_text]
        else:
            segments = segments_or_text
            
        for segment in segments:
            if not segment or not segment.strip():
                continue
                
            segment_lower = segment.lower()

            for category, patterns in self.regex_patterns.items():
                for pattern in patterns:
                     match = pattern.search(segment_lower)
                     if match:
                         matches.append({
                             "phrase": match.group(0),
                             "confidence": 0.95,  # High confidence for regex
                             "category": category,
                             "match_type": "regex",
                             "context": segment.strip()
                         })
                         # Optimization: We can return early or keep finding detailed matches.
                         # Finding all matches is better for debugging.
        
        return matches

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for better semantic analysis, preserving rebuttal context."""
        sentences = re.split(r'[.!?]+', text)

        # Also try to preserve question sequences that might be rebuttals
        all_sentences = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if sentence.endswith('?') or '?' in sentence:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                all_sentences.append(current_chunk)
                current_chunk = ""
            else:
                if current_chunk and len((current_chunk + " " + sentence).split()) > 50:
                    all_sentences.append(current_chunk)
                    current_chunk = sentence
                elif current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            all_sentences.append(current_chunk)

        cleaned_sentences = []
        for sentence in all_sentences:
            cleaned = sentence.strip()
            if len(cleaned) > 3:
                cleaned_sentences.append(cleaned)

        return cleaned_sentences

    def _is_polite_closing(self, sentence: str) -> bool:
        sentence_lower = sentence.lower()
        closing_keywords = [
            "thank you",
            "thanks for your time",
            "have a good one",
            "have a great day",
            "have a nice day",
            "enjoy your day",
            "bye",
            "goodbye",
            "talk to you later",
            "take care"
        ]
        content_keywords = [
            "sell",
            "selling",
            "buyer",
            "buying",
            "offer",
            "price",
            "property",
            "house",
            "home",
            "future"
        ]

        if any(k in sentence_lower for k in content_keywords):
            return False

        if any(k in sentence_lower for k in closing_keywords):
            return True

        return False

    def _strip_polite_closing_suffix(self, text: str) -> str:
        """Remove polite closing phrases from the end of a candidate phrase."""
        if not text:
            return text

        lower = text.lower()
        closing_keywords = [
            "thank you",
            "thanks for your time",
            "have a good one",
            "have a great day",
            "have a nice day",
            "enjoy your day",
            "bye",
            "goodbye",
            "talk to you later",
            "take care",
        ]

        cut_index = len(text)
        for kw in closing_keywords:
            idx = lower.find(kw)
            if idx != -1 and idx < cut_index:
                cut_index = idx

        if cut_index == len(text):
            return text

        return text[:cut_index].strip()

    def _extract_candidate_phrase(self, base_phrase: str, matched_sentence: str) -> str:
        if not matched_sentence:
            return base_phrase
        sentence = matched_sentence.strip()
        base = base_phrase.strip()
        if not sentence:
            return base
        sentence_tokens = sentence.split()
        if len(sentence_tokens) <= 10:
            return self._strip_polite_closing_suffix(sentence.lower())
        base_tokens = base.lower().split()
        base_token_set = {t.strip(".,!?;:") for t in base_tokens if t}
        if not base_token_set:
            candidate = sentence.lower()
            if len(candidate.split()) > 15:
                candidate_tokens = candidate.split()
                candidate = " ".join(candidate_tokens[:15])
            if len(candidate) > 160:
                candidate = candidate[:160]
            return candidate
        max_window = min(len(sentence_tokens), max(len(base_tokens) + 3, 12))
        best_start = 0
        best_end = min(len(sentence_tokens), len(base_tokens))
        best_score = 0.0
        for start in range(len(sentence_tokens)):
            for end in range(start + 1, min(len(sentence_tokens), start + max_window) + 1):
                window_tokens = sentence_tokens[start:end]
                window_token_set = {t.lower().strip(".,!?;:") for t in window_tokens if t}
                if not window_token_set:
                    continue
                overlap = len(base_token_set.intersection(window_token_set))
                score = overlap / float(len(base_token_set))
                if score > best_score or (score == best_score and (end - start) < (best_end - best_start)):
                    best_score = score
                    best_start = start
                    best_end = end
        if best_score >= 0.5:
            candidate = " ".join(sentence_tokens[best_start:best_end])
        else:
            candidate = base
        candidate = candidate.strip().lower()
        if len(candidate.split()) > 15:
            candidate_tokens = candidate.split()
            candidate = " ".join(candidate_tokens[:15])
        if len(candidate) > 160:
            candidate = candidate[:160]
        candidate = self._strip_polite_closing_suffix(candidate)
        return candidate

    def _filter_duplicate_matches(self, exact_matches: List[Dict], semantic_matches: List[Dict]) -> List[Dict]:
        """Filter out semantic matches that are too similar to exact matches."""
        if not exact_matches:
            return semantic_matches

        filtered_matches = []
        exact_phrases = {match['phrase'].lower() for match in exact_matches}

        for semantic_match in semantic_matches:
            # Only skip if the EXACT same phrase was already found via exact matching
            # Allow semantic matches for similar but not identical phrases
            if semantic_match['phrase'].lower() not in exact_phrases:
                filtered_matches.append(semantic_match)

        return filtered_matches

    def _track_semantic_matches_for_learning(self, matches: List[Dict], transcript: str):
        """Track semantic matches for phrase learning system."""
        try:
            # Import here to avoid circular imports
            from lib.phrase_learning import get_phrase_learning_manager

            learning_manager = get_phrase_learning_manager()

            for match in matches:
                if match['match_type'] == 'semantic':
                    matched_sentence = match.get('matched_sentence', match['phrase'])
                    base_phrase = match['phrase']
                    candidate_phrase = self._extract_candidate_phrase(base_phrase, matched_sentence)
                    if not candidate_phrase:
                        continue
                    if len(candidate_phrase.split()) > 15 or len(candidate_phrase) > 160:
                        continue

                    context_text = matched_sentence if matched_sentence else transcript
                    learning_manager.track_semantic_match(
                        phrase=candidate_phrase,
                        category=match['category'],
                        confidence=match['confidence'],
                        context=context_text[:500],
                        similar_to=base_phrase  # The original repository phrase it matched
                    )

        except Exception as e:
            logger.debug(f"Failed to track semantic matches for learning: {e}")
            # Don't let learning failures affect detection

    def _calculate_exact_confidence(self, phrase: str, transcript: str) -> float:
        """Calculate confidence score for an exact match."""
        phrase_words = set(phrase.lower().split())
        transcript_words = set(transcript.lower().split())

        overlap = len(phrase_words.intersection(transcript_words))
        total_phrase_words = len(phrase_words)

        if total_phrase_words == 0:
            return 0.0

        return min(1.0, overlap / total_phrase_words)


class OutputFormatter:
    """Standardized result schema formatting."""

    def format_result(self, result: str, confidence_score: float = 0.0,
                     matched_phrases: List[Dict] = None, transcript: str = "",
                     raw_transcript: str = "", corrections_made: Dict = None,
                     processing_time_ms: int = 0, metadata: Dict = None,
                     error_type: str = "", error_message: str = "") -> Dict[str, Any]:
        """Format detection result into standardized schema."""
        if matched_phrases is None:
            matched_phrases = []
        if corrections_made is None:
            corrections_made = {}
        if metadata is None:
            metadata = {}

        result_dict = {
            "result": result,
            "confidence_score": confidence_score,
            "matched_phrases": matched_phrases,
            "transcript": transcript,
            "raw_transcript": raw_transcript,
            "corrections_made": corrections_made,
            "metadata": {
                "processing_time_ms": processing_time_ms,
                "audio_quality_score": metadata.get("audio_quality_score", 0.0),
                "vosk_confidence": metadata.get("vosk_confidence", 0.0),
                "feedback": metadata.get("feedback", None),
                **metadata
            },
            "validation_flags": {
                "audio_quality_ok": metadata.get("audio_quality_ok", True),
                "transcript_length_sufficient": metadata.get("transcript_length_sufficient", True),
                "phonetic_corrections_applied": bool(corrections_made)
            }
        }

        if error_type or error_message:
            result_dict["error"] = {
                "type": error_type,
                "message": error_message
            }

        return result_dict
