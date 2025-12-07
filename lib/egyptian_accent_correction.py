from typing import Dict, List, Tuple
import re

class EgyptianAccentCorrection:
    """Egyptian accent correction system that removes common accent patterns and artifacts."""

    def __init__(self):
        # Define corrections dictionary as class attribute for efficiency and reusability
        self.corrections = {
            # Double letter patterns to remove
            'hhello': 'hello',
            'hhi': 'hi',
            'hhurt': 'hurt',
            'yyou': 'you',
            'yyeah': 'yeah',
            'rruiz': 'ruiz',
            'rroad': 'road',
            'pproperty': 'property',
            'rright': 'right',
            'iit': 'it',
            'sso': 'so',
            'ssir': 'sir',
            'iinterested': 'interested',
            'dday': 'day',
            'ggoodbye': 'goodbye',
            'wwhite': 'white',
            'yyours': 'yours',
            'sspeaking': 'speaking',
            'mmike': 'mike',
            'lleah': 'leah',
            'wwaren': 'waren',
            'ccalling': 'calling',
            'iinvestors': 'investors',
            'wwith': 'with',
            'bbad': 'bad',
            'ssory': 'sorry',
            'ookay': 'okay',
            'ggo': 'go',
            'wwork': 'work',
            'oorder': 'order',
            'ssell': 'sell',
            'ggot': 'got',
            'ttime': 'time',
            'oone': 'one',
            'bbaba': 'baba',
            'eedmond': 'edmond',
            'hharison': 'harrison',
            'fflorida': 'florida',
            'sstoon': 'stoon',
            'wwater': 'water',
            'ccourt': 'court',
            'bbatesta': 'batesta',
            'ffuture': 'future',
            'ssomething': 'something',
            'mmuch': 'much',
            'wwatching': 'watching',
            # Additional patterns
            'proberty': 'property',
            'seling': 'selling',
            'baying': 'buying',
            'uzzer': 'other',
            'anuzzer': 'another',
            'fuchure': 'future',
            'efen': 'even',
            'imbertan': 'important',
            'interes': 'interest',
            'becuz': 'because',
            'meybi': 'maybe',
            'somting': 'something',
            'everyting': 'everything',
            'anyting': 'anything',
            'abot': 'about',
            'nid': 'need',
            'tek': 'take',
            'giv': 'give',
            'sel': 'sell',
            'ofer': 'offer',
            'belif': 'believe',
            'anderstand': 'understand',
            'rimember': 'remember',
            'rebresent': 'represent',
            'perfict': 'perfect',
            'broblem': 'problem'
        }

    def apply_corrections(self, text: str) -> Tuple[str, List[str]]:
        """
        Apply Egyptian accent corrections to text.
        Removes common Egyptian accent patterns and artifacts.
        """
        if not text:
            return text, []

        corrections_made = []
        original_text = text

        # Apply corrections using class attribute
        for egyptian_pattern, english_word in self.corrections.items():
            if egyptian_pattern in text:
                text = text.replace(egyptian_pattern, english_word)
                corrections_made.append(f"{egyptian_pattern}→{english_word}")

        # Handle numbers with extra digits (like 44913 → 4913)
        # Remove duplicate digits that are likely transcription errors
        text = re.sub(r'(\d)\1+', r'\1', text)

        if text != original_text:
            corrections_made.insert(0, "egyptian_accent_corrections_applied")

        return text, corrections_made

    def get_correction_stats(self) -> Dict[str, int]:
        """Get statistics about available corrections."""
        return {
            "total_corrections": len(self.corrections),
            "consonant_corrections": len([k for k in self.corrections.keys() if len(k) <= 4]),
            "word_corrections": len([k for k in self.corrections.keys() if len(k) > 4])
        }
