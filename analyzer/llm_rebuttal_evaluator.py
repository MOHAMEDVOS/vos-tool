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
- Agents speak English as a second language — expect broken grammar, heavy accent, garbled words
- Focus entirely on INTENT and MEANING, never on grammar or pronunciation
- The conversation format uses "Agent:" and "Owner:" labels to identify speakers
- Your job is to catch agents who TRIED, not just agents who spoke perfectly

THE 20 REBUTTAL STRATEGIES:

1. PIVOT TO OTHER PROPERTIES (most common — look hard for this)
   Agent accepts rejection but immediately asks if the owner has OTHER properties to sell.
   Examples from real calls:
   - "do you have any other property you'd like to sell"
   - "do you happen to have any other property"
   - "by any chance, do you have any other property you want to sell"
   - "any other properties you might consider selling"
   - "any other property that you might be interested in selling"
   - "do you have another one that might be up for sales"
   - "do you guys have another one that might be up for sales"
   - "before i go, do you have any other property you want to sell"
   - "but do you have any other property"
   - "by the way, do you have any other property"
   - "any other property, would you be thinking about selling"
   - "any other house or land you may want to sell"
   - "any property or land that you want to sell"
   - "do you happen to have any other properties that you'd like to sell"
   - "consider selling that's okay but do you have any other property you may want to"
   - "any other property you want to sell or know anyone who want to sell"
   - "any interestt to sell it okay do you have okay do you have other"
   CRITICAL: Even broken/trailing phrases like these ARE this strategy — the agent TRIED.

2. FUTURE SELLING INQUIRY
   Agent asks if the owner might sell in the future.
   Examples: "Would you be open to selling in the future?", "Even in the near future?", "Maybe next year?", "Not even in the future?", "Maybe down the road?", "You think you could possibly sell next year or so?"

3. MIXED PIVOT (combines strategies 1 + 2 in one sentence)
   Agent asks about future AND other properties in same breath.
   Examples: "Not even in the future? But do you have any other property?", "Not this one but maybe another property?", "Not now but other property later?"

4. VALUE PROPOSITION / CASH OFFER PITCH
   Agent pitches their cash buying service and its benefits.
   Examples: "We buy houses all cash", "No commission no fees", "We close in 7 days", "We pay all closing costs", "As-is no repairs needed", "We buy in any condition"

5. PRICE NEGOTIATION REBUTTAL
   Agent challenges or negotiates the price after rejection.
   Examples: "Would that be negotiable?", "Is that price negotiable?", "How did you come up with that number?", "Would you take less?", "Is there room for negotiation?", "What's your best price?", "Would you consider a lower offer?"

6. CALLBACK SCHEDULING
   Agent tries to schedule a follow-up call instead of ending the conversation.
   Examples: "When is the best time to call you back?", "What's a good time to reach you?", "When should I follow up?", "Can I call you again later?", "When would be better to talk?"

7. WOULD-YOU-CONSIDER OFFER
   Agent directly asks if the owner would consider any kind of offer or deal.
   Examples: "Would you consider selling?", "Would you consider a cash offer?", "Would you be open to an offer?", "Would you entertain an offer?", "Would you be willing to sell?"

8. REFERRAL ASK
   Agent asks if the owner knows anyone else who might sell.
   Examples: "Do you know someone who might be selling?", "Know anyone looking to sell?", "Know anyone selling?", "Do you know someone by any chance?"

9. OPPORTUNISTIC TRANSITION PIVOT
   Agent uses a transitional phrase to pivot before hanging up — a very common Egyptian agent technique.
   Examples: "Since I have you...", "Since I got you on the phone...", "Before I let you go...", "While I have you...", "Just before you go...", "Before we hang up...", "By the way..."
   IMPORTANT: Any sentence that starts with these phrases and then asks about property IS a rebuttal.

10. SPECIFIC PROPERTY TYPE INQUIRY
    Agent asks about specific types of property the owner might have.
    Examples: "Do you have any rental properties?", "Any investment properties?", "Do you have any land?", "Any commercial properties?", "Do you have any vacant lots?", "Any foreclosure properties?", "Do you own any undeveloped land?"

11. FAMILY / INHERITED PROPERTY INQUIRY
    Agent asks about property within the owner's family or network.
    Examples: "Any other property in the family?", "Any property you inherited?", "Does anyone in your family have property to sell?", "Any property under a family member's name?"

12. FLEXIBILITY / CONVENIENCE PITCH
    Agent highlights how easy and flexible their process is.
    Examples: "We're very flexible with timing", "Flexible closing 30 days to 6 months", "Very simple process", "We make it easy for you", "No hassle process"

13. LOCATION-BASED PIVOT
    Agent asks about properties the owner might have in other locations.
    Examples: "Do you have property in other areas?", "Any property elsewhere?", "Property in another state?", "Any other addresses you own?"

14. BROKEN ENGLISH PROPERTY QUESTION (CRITICAL — do not miss these)
    Agent asks about property with heavy accent or broken grammar. These are real rebuttals even if hard to understand.
    Examples: "you haf any uzzer broperty", "haf any ozer hows", "you have like any other", "do you haf any ozer", "any uzzer bropertiz", "you don't have like any other"
    RULE: If you can see ANY attempt to ask about property even in broken/garbled English, it IS a rebuttal.

15. DOUBLE QUESTION PIVOT
    Agent asks two questions in rapid succession to maximize chances.
    Examples: "Not even in the future? Do you have any other property?", "Not this one? What about other houses?", "Not interested? Do you know anyone who might be?"

16. SOFT AGREEMENT + REDIRECT
    Agent agrees with the rejection but immediately redirects to a new angle.
    Examples: "I understand, but just quickly...", "I respect that, but do you happen to have...", "No problem, but before I go...", "That's fine, but do you know anyone..."

17. EXTENDED PROPERTY PORTFOLIO QUESTION
    Agent asks broad questions about the owner's real estate holdings.
    Examples: "Do you own multiple properties?", "Any other real estate you own?", "Do you have other properties in your portfolio?", "Any real estate assets?", "Other investment holdings?"

18. URGENCY / MARKET PITCH
    Agent creates urgency about the market or their offer timeline.
    Examples: "The market is really good right now", "We have buyers looking right now", "We're buying in your area right now", "Prices are high right now"

19. EMPATHY + REFRAME
    Agent acknowledges the owner's situation and reframes the opportunity.
    Examples: "I understand you're not ready, but what if...", "I know it's not the right time, but...", "I completely understand, however...", "That makes sense, but have you considered..."

20. FRAGMENTED / INCOMPLETE ATTEMPT (catch-all — very important)
    Agent starts a rebuttal but doesn't finish it cleanly — still counts as an attempt.
    Examples: "Do you have any...", "What about...", "Is there any chance...", "Would you ever...", "Do you happen to..."
    RULE: Any sentence fragment that clearly points toward asking about property, future selling, or referrals IS a rebuttal attempt. The agent TRIED.

HOW TO EVALUATE:
- Read the FULL conversation between Agent and Owner
- Identify the Owner's objection
- Look at EVERYTHING the Agent says AFTER the objection
- A rebuttal is ANY genuine attempt to keep the conversation going or redirect to a new opportunity

WHAT COUNTS AS A REBUTTAL:
✅ Any of the 20 strategies above, even if broken or incomplete
✅ Any question about other properties after rejection — this is #1, look very hard for it
✅ Any question about future selling
✅ Any pivot using transitional phrases (since I have you, before I let you go, etc.)
✅ Any price negotiation after rejection
✅ Any request for referrals
✅ Any attempt to schedule a callback
✅ Broken/garbled English where you can still detect the intent to ask about property
✅ Two or more strategies combined in one response
✅ Incomplete sentence fragments that clearly point toward a rebuttal

WHAT DOES NOT COUNT:
❌ Only saying "okay", "alright", "thank you", "have a good day", "bye" and ending
❌ Repeating the same opening pitch word-for-word after the objection (not addressing it)
❌ Ending the call immediately after the objection with no attempt
❌ Pure pleasantries with zero substance ("okay sorry to bother you goodbye")

REAL TRANSCRIPT PATTERNS (from actual recorded calls — study these carefully):
These are exactly how your agents speak. All of these ARE rebuttals:
- "and by any chance, do you have a property yourself you're thinking to sell thank you"
- "and do you have any other property you'd like to sell"
- "any other properties that you'd like to sell okay"
- "any other property you want to sell in the future okay thanks a lot sir"
- "before i go, really quick, don't you have like any other properties you might be"
- "do you happen to have any other property consider selling we can take anything okay"
- "do you happen to have any other property you consider selling okay ma'am"
- "any other properties you might be interested in selling"
- "did you happen to have any other for sale"
- "a real estate expert do you have any property you might consider selling okay"
- "any property you may want to sell though if if you happen to that's okay"

KEY PATTERNS TO RECOGNIZE:
- Phrases ending in "okay", "thank you", "sir", "ma'am", "all right" are NORMAL call endings added after a rebuttal — do not let them make you miss the rebuttal before them
- "do you happen to have any other" (even incomplete) = rebuttal
- "by any chance" before a property question = always a rebuttal
- "before i go" + any property question = always a rebuttal
- "but do you have any other property" = rebuttal (the "but" signals pivot)
- Repeated words like "okay do you have okay do you have other" = agent trying despite confusion = rebuttal
- Double "l" in "selll", "interestted", "sellling" = AssemblyAI transcription artifacts, NOT different words

CRITICAL RULES:
1. ATTEMPT = REBUTTAL: If the agent asks about OTHER properties, future selling, referrals, or uses any of the 20 strategies AFTER rejection — that IS a rebuttal, even if the owner says no again. The agent TRIED and that is what we measure.
2. BROKEN ENGLISH RULE: These are Egyptian agents speaking English as a second language. Grammar will be broken. Words will be mispronounced. Sentences will be fragmented. If you can detect ANY intent to rebut — even from fragments like "you have any", "do you have like", "haf any ozer" — count it as a rebuttal. Do NOT penalize them for imperfect English.
3. TRANSCRIPTION ARTIFACTS: AssemblyAI sometimes doubles letters ("selll", "interestted", "sellling") or repeats words. Treat these as the normal word they represent.
4. OPPORTUNISTIC PIVOTS: Phrases like "since I have you", "before I let you go", "while I have you", "by any chance", "by the way" followed by ANY property question are ALWAYS rebuttals. Never miss these.
5. BE GENEROUS: When in doubt, lean toward rebuttal_detected=true with lower confidence rather than missing a real attempt. A false negative (missing a real rebuttal) is worse than a false positive.

RESPONSE FORMAT (valid JSON only):
{
  "rebuttal_detected": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "1-2 sentence explanation referencing which strategy number and name the agent used",
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

TASK: After the owner raised this objection, did the agent use ANY of the 20 rebuttal strategies?

Pay special attention to (most commonly missed):
- Does the agent ask about OTHER properties? (Strategy 1 — most common, look very hard)
- Does the agent use a transition phrase like "since I have you" or "before I let you go"? (Strategy 9)
- Does the agent ask about FUTURE selling? (Strategy 2)
- Does the agent ask about specific property types like rental, land, commercial? (Strategy 10)
- Does the agent negotiate price? (Strategy 5)
- Does the agent ask for a callback or referral? (Strategy 6, 8)
- Is there ANY broken English attempt to ask about property? (Strategy 14 — do not miss these)
- Does the agent ask an incomplete question that points toward property? (Strategy 20)

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
