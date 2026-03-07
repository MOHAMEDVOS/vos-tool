"""
LLM-Based Rebuttal Evaluator for VOS Tool
Uses GroqCloud API to intelligently evaluate rebuttals with human-level reasoning.
"""

import os
import time
import json
import logging
import hashlib
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GroqClient:
    """Handles communication with GroqCloud API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        """
        Initialize GroqCloud API client.
        
        Args:
            api_key: GroqCloud API key. If not provided, reads from environment.
            model: Model to use for inference (default: llama-3.1-8b-instant)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required. Set it in environment or pass to constructor.")
        
        self.model = model
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "300"))
        self.timeout = int(os.getenv("GROQ_TIMEOUT", "10"))
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        
        logger.info(f"GroqClient initialized with model: {self.model}")
    
    def create_completion(self, messages: List[Dict[str, str]], retry_attempts: int = 3) -> Dict[str, Any]:
        """
        Create a chat completion with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            retry_attempts: Number of retry attempts on failure
            
        Returns:
            Response dict with 'choices' containing the completion
        """
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"}  # Force JSON response
        }
        
        last_error = None
        
        for attempt in range(retry_attempts):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"GroqCloud API success (attempt {attempt + 1})")
                    return result
                elif response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = (2 ** attempt) * 1  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"GroqCloud API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    last_error = error_msg
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{retry_attempts})")
                last_error = "Request timeout"
                time.sleep(1)
            except Exception as e:
                logger.error(f"GroqCloud API request failed: {e}")
                last_error = str(e)
                time.sleep(1)
        
        raise Exception(f"GroqCloud API failed after {retry_attempts} attempts. Last error: {last_error}")


class RebuttalPromptBuilder:
    """Constructs context-aware prompts for LLM evaluation."""
    
    # Objection category to human-readable mapping
    OBJECTION_MAP = {
        "not_interested": "customer said they are not interested",
        "busy_time": "customer said they are busy or it's a bad time",
        "already_sold": "customer said they already sold the property",
        "already_listed": "customer said property is already listed with an agent",
        "not_selling": "customer said they don't want to sell",
        "callback_request": "customer asked to be called back later",
        "remove_list": "customer asked to be removed from the call list",
        "price_too_low": "customer thinks the offer price is too low",
        "needs_time": "customer needs more time to think or decide",
        "spouse_decision": "customer needs to consult with spouse/partner",
        "wrong_number": "customer said they are not the person the agent asked for / wrong number"
    }
    
    SYSTEM_PROMPT = """You are an expert quality assurance evaluator for outbound real estate cold calls. Your task is to determine whether a sales agent attempted to handle or overcome a customer's objection during a phone call.

CONTEXT:
- These are Egyptian real estate agents calling US property owners
- Agents speak English with varying accent levels and informal phrasing
- Focus on INTENT and MEANING, not perfect grammar or wording
- The conversation format uses "Agent:" and "Owner:" labels to identify speakers

THE 8 REBUTTAL STRATEGIES (from most to least common):

1. PIVOT TO OTHER PROPERTIES (most common)
   The agent accepts the rejection but immediately asks about OTHER properties the owner might have.
   Examples: "Do you have any other property?", "Since I have you, any other property you might sell?", "Do you know anyone who might be selling?"

2. FUTURE SELLING INQUIRY
   The agent asks if the owner would consider selling in the future.
   Examples: "Would you be open to selling in the future?", "Even in the near future?", "Maybe next year?"

3. MIXED PIVOT (Future + Other Property)
   The agent combines multiple strategies in one response.
   Examples: "Not even in the future? But do you have any other property?", "Not this one, but maybe another property?"

4. VALUE PROPOSITION / WE-BUY OFFER
   The agent pitches their buying service with concrete benefits.
   Examples: "We buy houses all cash", "No commission, no fees", "We close in 7 days", "Would that be negotiable?"

5. CALLBACK SCHEDULING
   The agent tries to secure a follow-up call.
   Examples: "When is the best time to call you back?", "Can I follow up with you later?"

6. WOULD-YOU-CONSIDER OFFER
   The agent frames a direct offer.
   Examples: "Would you consider a cash offer?", "Would you be interested in selling?"

7. FLEXIBILITY / CONVENIENCE PITCH
   The agent highlights their process flexibility.
   Examples: "We're very flexible with timing", "Flexible closing, 30 days to 6 months"

8. REFERRAL ASK
   The agent asks if the owner knows someone else who might sell.
   Examples: "Do you know someone who might be selling?", "Know anyone looking to sell?"

HOW TO EVALUATE:
- Read the FULL conversation between Agent and Owner
- Identify the Owner's objection (e.g., "not interested", "wrong number", "already sold")
- Look at what the Agent says AFTER the objection
- A rebuttal is ANY genuine attempt from the agent to keep the conversation going or redirect the opportunity

WHAT COUNTS AS A REBUTTAL:
✅ Any of the 8 strategies above, even if poorly worded
✅ Asking about other properties after rejection (this is the #1 strategy)
✅ Asking about future selling plans
✅ Pitching the cash offer or benefits
✅ Asking for a callback time
✅ Asking for referrals ("know anyone selling?")
✅ Combining multiple strategies ("not even in the future? any other property?")
✅ Indirect or imperfect attempts ("before I let you go, do you have any property?")
✅ Broken English or garbled attempts where the agent clearly TRIED to say something beyond "okay bye" — even if the words are hard to understand (e.g., "you have like, any" = attempted pivot to other properties)

WHAT DOES NOT COUNT:
❌ Simply saying "okay" or "alright" and ending the call
❌ Only repeating the same pitch without addressing the objection
❌ Ending the call immediately after the objection
❌ Generic pleasantries without substance ("okay have a good day bye")
❌ Just confirming the wrong number without pivoting

CRITICAL RULES:
1. If the agent asks about OTHER properties, future selling, or referrals AFTER rejection, that IS a rebuttal — even if the owner says no to that too. The agent TRIED.
2. BROKEN ENGLISH RULE: These agents are Egyptian and speak English as a second language. Their sentences may be grammatically broken, garbled, or hard to understand. If you can detect ANY intent to rebut (even fragments like "you have any" or "do you have like property"), count it as a rebuttal. The goal is to distinguish agents who TRY from agents who simply give up and say goodbye.

RESPONSE FORMAT (valid JSON only):
{
  "rebuttal_detected": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "1-2 sentence explanation referencing which strategy the agent used",
  "matched_phrase": "the exact agent phrase that constitutes the rebuttal, or null"
}"""
    
    def __init__(self, learned_phrases: Optional[Dict[str, List[str]]] = None):
        """
        Initialize prompt builder.
        
        Args:
            learned_phrases: Dict of category -> list of successful rebuttals from database
        """
        self.learned_phrases = learned_phrases or {}
    
    def build_user_prompt(
        self,
        transcript: str,
        objection_category: str,
        semantic_hints: Optional[List[str]] = None,
        dialogue: Optional[str] = None
    ) -> str:
        """
        Build the user prompt for a specific evaluation.
        
        Args:
            transcript: Agent transcript (for backward compatibility)
            objection_category: Category of detected objection
            semantic_hints: Optional list of phrases that had low semantic match scores
            dialogue: Full conversation dialogue (Agent + Owner) for context
            
        Returns:
            Formatted user prompt string
        """
        objection_text = self.OBJECTION_MAP.get(
            objection_category,
            f"customer objection: {objection_category}"
        )
        
        # Use dialogue if available for full context, otherwise fallback to transcript
        conversation_text = dialogue if dialogue else transcript
        
        prompt = f"""FULL CONVERSATION:
{conversation_text}

OWNER'S OBJECTION: {objection_text}

TASK: After the owner raised this objection, did the agent use ANY of the 8 rebuttal strategies?

Pay special attention to:
- Does the agent ask about OTHER properties? (Strategy 1 — most common)
- Does the agent ask about FUTURE selling? (Strategy 2)
- Does the agent pitch their offer or benefits? (Strategy 4)
- Does the agent ask for a callback or referral? (Strategy 5, 8)

"""
        
        # Add learned phrases as examples if available
        if objection_category in self.learned_phrases:
            category_phrases = self.learned_phrases[objection_category]
            if category_phrases and len(category_phrases) > 0:
                # Limit to top 5 to keep prompt concise
                sample_phrases = category_phrases[:5]
                prompt += f"""KNOWN SUCCESSFUL REBUTTALS FOR THIS OBJECTION:
{chr(10).join(f'- "{phrase}"' for phrase in sample_phrases)}

"""
        
        # Add semantic hints if provided
        if semantic_hints:
            prompt += f"""POSSIBLE REBUTTAL CANDIDATES (low confidence — need your judgment):
{chr(10).join(f'- "{hint}"' for hint in semantic_hints[:3])}

"""
        
        prompt += """Return your evaluation as JSON:
{
  "rebuttal_detected": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "which strategy was used and why",
  "matched_phrase": "exact agent phrase or null"
}"""
        
        return prompt
    
    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return self.SYSTEM_PROMPT


class LLMRebuttalEvaluator:
    """Main orchestrator for LLM-based rebuttal evaluation."""
    
    # Class-level cache to share across instances (P0 FIX)
    _learned_phrases_cache = None
    _learned_phrases_loaded_at = 0
    _cache_lock = threading.Lock()
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        """
        Initialize LLM evaluator.
        
        Args:
            api_key: GroqCloud API key
            model: Model to use for inference
        """
        try:
            self.client = GroqClient(api_key=api_key, model=model)
            self.cache = {}  # In-memory cache: {hash(transcript+category): result}
            self.cache_ttl = timedelta(minutes=5)
            self.cache_timestamps = {}
            
            # Load learned phrases using class-level cache (P0 FIX)
            self.learned_phrases = self._get_cached_learned_phrases()
            self.prompt_builder = RebuttalPromptBuilder(learned_phrases=self.learned_phrases)
            
            logger.info(f"LLMRebuttalEvaluator initialized with {sum(len(p) for p in self.learned_phrases.values())} learned phrases")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLMRebuttalEvaluator: {e}")
            raise
    
    def _get_cached_learned_phrases(self) -> Dict[str, List[str]]:
        """Get learned phrases from class-level cache or load if expired."""
        with self._cache_lock:
            now = time.time()
            # 5-minute cache TTL for learned phrases
            if self._learned_phrases_cache is not None and (now - self._learned_phrases_loaded_at) < 300:
                logger.debug("Using class-level cache for learned phrases")
                return self._learned_phrases_cache
            
            # Cache expired or not loaded, load from DB
            logger.info("Class-level cache empty or expired, loading learned phrases from DB")
            self._learned_phrases_cache = self._load_learned_phrases_from_db()
            self._learned_phrases_loaded_at = now
            return self._learned_phrases_cache

    def _load_learned_phrases_from_db(self) -> Dict[str, List[str]]:
        """
        Load learned phrases from PostgreSQL database.
        Returns dict of category -> list of phrases.
        """
        try:
            from lib.database import get_db_manager
            
            db = get_db_manager()
            if not db:
                logger.warning("Database not available, LLM will not have learned phrase examples")
                return {}
            
            # Query repository_phrases table for approved learned phrases
            query = """
                SELECT category, phrase, usage_count, effectiveness_score
                FROM repository_phrases
                WHERE source IN ('auto_learned', 'manual', 'auto_approved')
                ORDER BY category, 
                         COALESCE(effectiveness_score, 0) DESC,
                         usage_count DESC,
                         added_date DESC
            """
            
            results = db.execute_query(query, fetch=True)
            
            if not results:
                logger.info("No learned phrases found in database")
                return {}
            
            # Organize by category
            learned_phrases = {}
            for row in results:
                category = row['category']
                phrase = row['phrase']
                
                if category not in learned_phrases:
                    learned_phrases[category] = []
                
                learned_phrases[category].append(phrase)
            
            logger.info(f"Loaded {sum(len(p) for p in learned_phrases.values())} learned phrases for LLM context")
            return learned_phrases
            
        except Exception as e:
            logger.warning(f"Could not load learned phrases from database: {e}")
            return {}
    
    def _get_cache_key(self, transcript: str, objection_category: str) -> str:
        """Generate cache key from transcript and category."""
        content = f"{transcript}|{objection_category}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if result exists in cache and is still valid."""
        if cache_key in self.cache:
            timestamp = self.cache_timestamps.get(cache_key)
            if timestamp and (datetime.now() - timestamp) < self.cache_ttl:
                logger.debug(f"Cache hit for key: {cache_key[:8]}...")
                return self.cache[cache_key]
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
        
        return None
    
    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]):
        """Save result to cache."""
        self.cache[cache_key] = result
        self.cache_timestamps[cache_key] = datetime.now()
    
    def evaluate_rebuttal(
        self,
        transcript: str,
        objection_category: str,
        semantic_candidates: Optional[List[Dict[str, Any]]] = None,
        dialogue: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate whether agent addressed objection using LLM.
        
        Args:
            transcript: Agent transcript (for backward compatibility)
            objection_category: Category of detected objection
            semantic_candidates: Optional list of semantic match results with low confidence
            dialogue: Full conversation dialogue (Agent + Owner) for enhanced context
            
        Returns:
            Dict with:
                - rebuttal_detected (bool)
                - confidence (float)
                - reasoning (str)
                - matched_phrase (str or None)
                - source (str): 'llm_evaluation'
        """
        # Check cache first (use dialogue if available for cache key)
        cache_text = dialogue if dialogue else transcript
        cache_key = self._get_cache_key(cache_text, objection_category)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Extract semantic hints if provided
            semantic_hints = None
            if semantic_candidates:
                semantic_hints = [
                    match.get('phrase', '')
                    for match in semantic_candidates[:3]
                    if match.get('phrase')
                ]
            
            # Build prompt with dialogue context
            system_prompt = self.prompt_builder.get_system_prompt()
            user_prompt = self.prompt_builder.build_user_prompt(
                transcript=transcript,
                objection_category=objection_category,
                semantic_hints=semantic_hints,
                dialogue=dialogue  # Pass full conversation for context
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call GroqCloud API
            logger.debug(f"Calling GroqCloud API for objection: {objection_category}")
            start_time = time.time()
            
            response = self.client.create_completion(messages)
            
            elapsed = time.time() - start_time
            logger.debug(f"GroqCloud API completed in {elapsed:.2f}s")
            
            # Parse response
            content = response['choices'][0]['message']['content']
            result = json.loads(content)
            
            # Validate response format
            if not self._validate_response(result):
                logger.error(f"Invalid LLM response format: {result}")
                return self._fallback_response()
            
            # Add metadata
            result['source'] = 'llm_evaluation'
            result['api_latency'] = elapsed
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            logger.info(f"LLM evaluation: {objection_category} -> {result['rebuttal_detected']} (confidence: {result['confidence']:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            return self._fallback_response()
    
    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate LLM response has required fields."""
        required_keys = ["rebuttal_detected", "confidence", "reasoning", "matched_phrase"]
        
        if not all(key in response for key in required_keys):
            return False
        
        if not isinstance(response["rebuttal_detected"], bool):
            return False
        
        try:
            confidence = float(response["confidence"])
            if not (0.0 <= confidence <= 1.0):
                return False
        except (ValueError, TypeError):
            return False
        
        return True
    
    def _fallback_response(self) -> Dict[str, Any]:
        """Return a safe fallback response when LLM fails."""
        return {
            "rebuttal_detected": False,
            "confidence": 0.0,
            "reasoning": "LLM evaluation failed, unable to determine",
            "matched_phrase": None,
            "source": "llm_evaluation_failed"
        }
