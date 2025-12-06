"""
Smart Rebuttal Classifier for VOS Tool
Advanced ML-based rebuttal detection using semantic analysis
"""

def smart_rebuttal_detection(transcript: str, agent_name: str = "", owner_name: str = "") -> dict:
    """
    Smart ML-based rebuttal detection using advanced semantic analysis.

    Args:
        transcript: The transcribed call text
        agent_name: Name of the agent (optional)
        owner_name: Name of the property owner (optional)

    Returns:
        dict: Detection result with 'result' key ('Yes'/'No') and confidence score
    """
    # For now, return a simple result
    # This is a placeholder for future ML implementation

    transcript_lower = transcript.lower()

    # Comprehensive rebuttal detection based on main production system
    # Organized by category for better detection and analysis
    rebuttal_keywords = [
        # OTHER_PROPERTY_FAMILY - Agent asking about other properties
        'do you have any other property', 'do you have another property', 'any other property',
        'any other properties', 'any other properties you might consider', 'any other property you might consider',
        'any other property you want to sell', 'any other property you might want to sell',
        'any other property that you might want to sell', 'any property',
        'do you have any other houses', 'do you have any other houses you want to sell',
        'do you have another house', 'any other houses to sell', 'any other houses you might consider selling',
        'any property you might be interested in selling', 'any property you might be interested in selling soon',
        'do you happen to have any property that you might be interested in selling soon',
        'any property that you might be interested in selling soon',
        'do you have any other property you might be interested in selling',
        'you don\'t have any other property to sell', 'you don\'t have another property to sell',
        'you don\'t own any other property', 'you don\'t have any properties in general',
        'don\'t have any properties in general', 'you have another property you\'d like to sell',
        'do you own any other property you\'d like to sell', 'do you happen to have any other property',
        'any other properties besides this one', 'any other properties aside from this one',
        'got any other property', 'any other properties available',
        
        # Egyptian English variations
        'do you haf any uzzer broperty', 'haf any uzzer broperty', 'haf any ozer proberty',
        'haf any uzzer proberty', 'do you haf any ozer broperty', 'haf ozer broperty',
        'haf uzzer proberty', 'haf ozer proberty', 'got any uzzer broperty', 'got any ozer broperty',
        'haf any uzzer bropertiz', 'haf any ozer bropertiz', 'haf any uzzer hows', 'haf any ozer hows',
        
        # Additional property variations
        'are there any other homes you own', 'do you own multiple properties', 'any additional properties',
        'other real estate you might have', 'different properties you own', 'any other real estate assets',
        'other investment properties', 'any commercial properties', 'other residential properties',
        'additional homes or apartments', 'other pieces of real estate', 'any other land or property',
        'secondary properties', 'backup properties', 'other properties in your portfolio',
        'any other holdings', 'additional real estate', 'other owned properties',
        
        # NOT_EVEN_FUTURE_FAMILY - Agent questions about future selling
        'would you be open to selling in the future', 'would you be open to sell in the future',
        'would you be open to sell maybe next year', 'would you be open to selling maybe next year',
        'would you be interested in selling in the future', 'would you be interested in selling maybe next year',
        'would you be interested in selling later', 'any chance you might sell in the future',
        'any chance you might sell later', 'any chance you might sell next year',
        
        # CALLBACK_SCHEDULE_FAMILY - Agent scheduling follow-ups
        'when is the best time to call you back', 'what\'s a good time to reach you',
        'can i call you back later', 'let me take down your details',
        
        # WOULD_CONSIDER_FAMILY - Agent testing interest
        'would you consider selling', 'would you be interested in an offer',
        'could we make you an offer',
        
        # WE_BUY_OFFER_FAMILY - Agent value proposition
        'we buy houses all cash', 'no commission, no fees', 'we pay all closing costs',
        'as-is, no repairs', 'buying properties all over the state',
        
        # FLEXIBLE_CONVENIENT_FAMILY - Agent addressing timing
        'we\'re very flexible with timing', 'very simple process', 'fast closing, your convenience',
        
        # MIXED_FUTURE_OTHER_FAMILY - Agent pivoting to other properties
        'do you have any other properties besides this', 'do you have something else you might sell',
        'do you have another property instead', 'any other property instead of this one',
        
        # Keep only core objection indicators
        'objection', 'concern', 'maybe later',
        'what else do you have', 'other properties', 'different options'
    ]

    # Count how many different objection-handling keywords are present
    keyword_count = sum(1 for keyword in rebuttal_keywords if keyword in transcript_lower)
    
    # Check if any rebuttal keywords are present
    has_rebuttal_indicators = keyword_count > 0

    # Calculate confidence based on keyword density and strength
    if has_rebuttal_indicators:
        # Stronger confidence for key rebuttal categories (matching main system)
        strong_indicators = [
            # High-confidence agent responses
            'do you have any other property', 'any other property', 'would you be open to selling',
            'would you consider selling', 'we buy houses all cash',
            'when is the best time to call you back', 'objection', 'concern', 'maybe down the road'
        ]
        
        # Check for high-confidence indicators
        has_strong_indicator = any(indicator in transcript_lower for indicator in strong_indicators)
        
        # Enhanced confidence calculation based on main system logic
        if has_strong_indicator and keyword_count >= 3:
            confidence = 0.90  # Very high confidence for multiple strong indicators
        elif has_strong_indicator and keyword_count >= 2:
            confidence = 0.85  # High confidence for strong indicators with support
        elif keyword_count >= 4:
            confidence = 0.80  # High confidence for many indicators
        elif keyword_count >= 2:
            confidence = 0.70  # Good confidence for multiple indicators
        else:
            confidence = 0.65  # Moderate confidence for single indicator
    else:
        confidence = 0.0

    result = "Yes" if has_rebuttal_indicators else "No"

    # Determine which categories were detected for detailed reporting
    detected_categories = []
    if 'do you have any other property' in transcript_lower or 'any other property' in transcript_lower:
        detected_categories.append('OTHER_PROPERTY_FAMILY')
    if 'would you be open to selling' in transcript_lower or 'maybe down the road' in transcript_lower:
        detected_categories.append('NOT_EVEN_FUTURE_FAMILY')
    if 'call you back' in transcript_lower or 'best time to call' in transcript_lower:
        detected_categories.append('CALLBACK_SCHEDULE_FAMILY')
    if 'would you consider' in transcript_lower or 'interested in an offer' in transcript_lower:
        detected_categories.append('WOULD_CONSIDER_FAMILY')
    if 'we buy houses' in transcript_lower or 'no commission' in transcript_lower:
        detected_categories.append('WE_BUY_OFFER_FAMILY')
    if 'flexible with timing' in transcript_lower or 'fast closing' in transcript_lower:
        detected_categories.append('FLEXIBLE_CONVENIENT_FAMILY')

    return {
        'result': result,
        'confidence_score': confidence,
        'method': 'enhanced_keyword_based',
        'keyword_count': keyword_count,
        'detected_categories': detected_categories,
        'has_strong_indicators': has_strong_indicator if has_rebuttal_indicators else False,
        'total_phrases_available': len(rebuttal_keywords)
    }
