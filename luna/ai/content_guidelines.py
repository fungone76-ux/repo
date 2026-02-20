"""Content guidelines and tone settings for Luna RPG v4.

This module defines the base tone and content guidelines for the LLM,
especially for adult/mature content (18+).
"""
from __future__ import annotations

from typing import Dict, List


class ContentGuidelines:
    """Content guidelines for AI generation.
    
    Defines tone, style, and content boundaries for different
    maturity levels and genres.
    """
    
    # Base guidelines for all content
    BASE_GUIDELINES = """
=== CONTENT GUIDELINES ===

1. CHARACTER AGE & CONSENT
   - All characters depicted are consenting adults (18+)
   - All interactions are consensual
   - This is a fictional scenario for entertainment

2. TONE & STYLE
   - Write in Italian language
   - Use descriptive, atmospheric prose
   - Focus on emotions, sensations, and relationships
   - Maintain character voice consistency

3. CONTENT BOUNDARIES
   - No non-consensual content
   - No extreme violence or gore
   - No illegal activities
   - Keep within genre-appropriate boundaries

4. NARRATIVE QUALITY
   - Show, don't tell
   - Use sensory details (sight, sound, touch, smell)
   - Build tension and emotional connection
   - Respect story beats and world lore
"""
    
    # Adult/Mature content guidelines (18+)
    MATURE_GUIDELINES = """
=== MATURE CONTENT GUIDELINES (18+) ===

1. ROMANTIC/INTIMATE SCENES
   - Focus on emotional connection and intimacy
   - Use suggestive but tasteful descriptions
   - Emphasize feelings, sensations, and atmosphere
   - Build gradually based on relationship progression

2. LANGUAGE & DIALOGUE
   - Characters may use mature language when appropriate
   - Dialogue should reflect relationship intimacy level
   - Use euphemisms and poetic language for explicit content
   - Maintain emotional authenticity

3. PHYSICAL DESCRIPTIONS
   - Descriptions can be sensual and detailed
   - Focus on attraction, desire, and emotional states
   - Use artistic/poetic language
   - Balance physical and emotional elements

4. BOUNDARIES
   - All content must be consensual
   - Respect character agency and comfort levels
   - Fade to black when appropriate
   - Match content intensity to narrative context
"""
    
    # Genre-specific tones
    GENRE_TONES: Dict[str, str] = {
        "Slice of Life": """
TONE: Slice of Life
- Everyday situations and relationships
- Focus on character development
- Realistic dialogue and scenarios
- Gentle, heartwarming atmosphere
""",
        "Romance": """
TONE: Romance
- Emotional connection and intimacy
- Focus on relationship development
- Flirtatious and passionate when appropriate
- Build romantic tension gradually
""",
        "Drama": """
TONE: Drama
- Emotional intensity and conflict
- Complex character relationships
- Serious themes handled with care
- Atmospheric and moody
""",
        "Comedy": """
TONE: Comedy
- Light-hearted and fun
- Playful banter between characters
- Humorous situations
- Cheerful atmosphere
""",
        "Mystery": """
TONE: Mystery
- Suspenseful and intriguing
- Clues and revelations
- Atmospheric tension
- Methodical pacing
""",
    }
    
    @classmethod
    def get_guidelines(
        cls,
        mature_content: bool = True,
        genre: str = "Slice of Life",
    ) -> str:
        """Get complete content guidelines.
        
        Args:
            mature_content: If True, include 18+ guidelines
            genre: Genre for specific tone
            
        Returns:
            Complete guidelines string
        """
        sections = [cls.BASE_GUIDELINES]
        
        if mature_content:
            sections.append(cls.MATURE_GUIDELINES)
        
        if genre in cls.GENRE_TONES:
            sections.append(cls.GENRE_TONES[genre])
        
        return "\n".join(sections)
    
    @classmethod
    def get_safety_message(cls) -> str:
        """Get content safety disclaimer.
        
        Returns:
            Safety message for prompts
        """
        return """
SAFETY NOTICE:
This is a work of fiction. All characters are consenting adults (18+).
All scenarios are fictional and for entertainment purposes only.
Content is generated responsibly with appropriate boundaries.
"""
