"""System prompt builder for LLM requests.

Builds structured prompts combining world, character, and game state context.
"""
from __future__ import annotations

from typing import List, Optional

from luna.core.models import CompanionDefinition, GameState, WorldDefinition
from luna.ai.content_guidelines import ContentGuidelines
from luna.systems.personality import PersonalityEngine
from luna.systems.location import LocationManager


class PromptBuilder:
    """Builds system prompts for LLM generation.
    
    Combines multiple context sources into a cohesive prompt.
    """
    
    def __init__(self, world: WorldDefinition) -> None:
        """Initialize prompt builder.
        
        Args:
            world: World definition for context
        """
        self.world = world
    
    def build_system_prompt(
        self,
        game_state: GameState,
        personality_engine: Optional[PersonalityEngine] = None,
        story_context: str = "",
        quest_context: str = "",
        memory_context: str = "",
        location_manager: Optional[Any] = None,
    ) -> str:
        """Build complete system prompt.
        
        Args:
            game_state: Current game state
            personality_engine: For psychological context
            story_context: StoryDirector beat instruction
            quest_context: Active quest narrative context
            memory_context: Memory context for recall
            location_manager: For location context and navigation
            
        Returns:
            Complete system prompt
        """
        sections: List[str] = []
        
        # Header
        sections.extend([
            "=== LUNA RPG - SYSTEM INSTRUCTIONS ===",
            "",
            f"Genre: {self.world.genre}",
            f"World: {self.world.name}",
            "",
            "You are a narrative AI for a visual novel/RPG game.",
            "Write engaging, atmospheric scenes in Italian.",
            "Focus on character emotions, sensory details, and immersion.",
            "",
        ])
        
        # Content Guidelines (Adult 18+)
        guidelines = ContentGuidelines.get_guidelines(
            mature_content=True,
            genre=self.world.genre,
        )
        sections.extend([
            guidelines,
            "",
        ])
        
        # World context
        sections.extend([
            "=== WORLD ===",
            self.world.lore or self.world.description,
            "",
        ])
        
        # Active companion
        companion = self._get_companion(game_state.active_companion)
        if companion:
            sections.extend([
                "=== ACTIVE COMPANION ===",
                self._build_companion_context(companion, game_state),
                "",
            ])
        
        # Location context (if available)
        if location_manager:
            sections.extend([
                location_manager.get_location_context(),
                "",
            ])
        else:
            # Basic location info
            outfit_desc = game_state.get_active_outfit_description()
            sections.extend([
                "=== CURRENT SITUATION ===",
                f"Location: {game_state.current_location}",
                f"Time: {game_state.time_of_day.value}",
                f"Turn: {game_state.turn_count}",
                f"Outfit: {outfit_desc}",
                "",
            ])
        
        # Psychological context
        if personality_engine:
            psych_context = personality_engine.get_psychological_context(
                game_state.active_companion,
                include_behavioral=True,
                include_impressions=True,
                include_links=False,
            )
            if psych_context:
                sections.extend([
                    "=== PSYCHOLOGICAL CONTEXT ===",
                    psych_context,
                    "",
                ])
        
        # Story beat (mandatory)
        if story_context:
            sections.extend([
                "=== MANDATORY NARRATIVE BEAT ===",
                story_context,
                "",
                "CRITICAL: Include this event in your response.",
                "",
            ])
        
        # Quest context
        if quest_context:
            sections.extend([
                "=== ACTIVE QUESTS ===",
                quest_context,
                "",
            ])
        
        # Memory context (important facts)
        if memory_context:
            sections.extend([
                memory_context,
                "",
            ])
        
        # Output format
        sections.extend([
            "=== OUTPUT FORMAT ===",
            "Respond with valid JSON:",
            "{",
            '  "text": "Narrative in Italian (2-4 paragraphs, immersive)",',
            '  "visual_en": "Visual description for image generation (English, detailed)",',
            '  "tags_en": ["tag1", "tag2", "tag3"],',
            '  "body_focus": "face|hands|legs|etc (optional)",',
            '  "approach_used": "standard|physical_action|question|choice",',
            '  "composition": "close_up|medium_shot|wide_shot|group|scene",',
            '  "updates": {',
            '    "affinity_change": {"CompanionName": 3},',
            '    "current_outfit": "outfit_id (must exist in wardrobe)",',
            '    "location": "location_id (must be valid)",',
            '    "set_flags": {"flag_name": true}',
            '  }',
            "}",
            "",
            "=== IMAGE GENERATION GUIDE (SD EXPERT MODE) ===",
            "",
            "VISUAL_EN (English description for Stable Diffusion):",
            "- Write detailed English description (not tags)",
            "- Include: pose, expression, clothing details, lighting, background",
            "- Use quality boosters: masterpiece, best quality, detailed",
            "- Describe body parts if relevant: 'cleavage', 'exposed shoulders'",
            "- Lighting: soft lighting, cinematic lighting, sunlight, moonlight",
            "- NEVER include: parentheses (), brackets [], weights :1.3",
            "",
            "TAGS_EN (SD tags - array format):",
            "- Use standard booru-style tags: 1girl, solo, classroom, etc.",
            "- Include: location, time of day, clothing, pose, quality tags",
            "- Quality tags: score_9, score_8_up, masterpiece, photorealistic",
            "- Avoid: conflicting tags (don't mix 'solo' with multiple chars)",
            "- Use specific tags: 'looking_at_viewer', 'smile', 'standing'",
            "",
            "BODY_FOCUS (optional):",
            "- If focusing on specific body part: 'face', 'breasts', 'legs', 'feet'",
            "- Leave empty for full scene focus",
            "",
            "COMPOSITION:",
            "- close_up: Face focus, intimate",
            "- medium_shot: Upper body, waist up",
            "- wide_shot: Full body, environmental",
            "- group: Multiple characters",
            "",
            "=== EXAMPLE OUTPUT ===",
            '{',
            '  "text": "Luna si avvicina alla finestra...",',
            '  "visual_en": "Luna standing by classroom window, afternoon sunlight illuminating her face, gentle smile, hands resting on windowsill, looking outside, profile view, soft lighting, detailed face, mature woman",',
            '  "tags_en": ["score_9", "score_8_up", "1girl", "solo", "luna", "classroom", "window", "afternoon", "sunlight", "looking_away", "smile", "standing", "masterpiece", "photorealistic"],',
            '  "body_focus": "face",',
            '  "composition": "medium_shot"',
            "}",
            "",
            "=== RULES ===",
            "1. text: Write in Italian, 2-4 paragraphs, immersive style",
            "2. visual_en: MUST be English, detailed, SD-optimized description",
            "3. tags_en: MUST be array of SD tags (booru style)",
            "4. updates.affinity_change: Suggest changes (-5 to +5 per turn max)",
            "5. updates.current_outfit: Must exist in character wardrobe",
            "6. updates.location: Must be a valid world location",
            "7. Be consistent with character personality and psychological context",
            "8. All characters are consenting adults in a fictional scenario",
            "",
            "=== END INSTRUCTIONS ===",
        ])
        
        return "\n".join(sections)
    
    def build_analysis_prompt(
        self,
        user_input: str,
        analysis_type: str = "intent",
    ) -> str:
        """Build prompt for predictive scene analysis.
        
        Args:
            user_input: User's input
            analysis_type: Type of analysis ('intent' or 'scene')
            
        Returns:
            Analysis prompt
        """
        if analysis_type == "intent":
            return f"""Analyze the player's intent in this input:
"{user_input}"

Predict:
1. Primary subject (who is focused on)
2. Expected location change
3. Expected action type (talk, move, physical, etc.)
4. Emotional tone

Respond in JSON format."""
        
        return ""
    
    def _get_companion(self, name: str) -> Optional[CompanionDefinition]:
        """Get companion definition by name.
        
        Args:
            name: Companion name
            
        Returns:
            Companion definition or None
        """
        return self.world.companions.get(name)
    
    def _build_companion_context(
        self,
        companion: CompanionDefinition,
        game_state: GameState,
    ) -> str:
        """Build companion context.
        
        Args:
            companion: Companion definition
            game_state: Current game state
            
        Returns:
            Formatted context
        """
        lines = [
            f"Name: {companion.name}",
            f"Role: {companion.role}",
            f"Age: {companion.age}",
            f"Personality: {companion.base_personality}",
            f"Current Affinity: {game_state.affinity.get(companion.name, 0)}/100",
        ]
        
        # Emotional state
        npc_state = game_state.npc_states.get(companion.name)
        if npc_state:
            lines.append(f"Emotional State: {npc_state.emotional_state}")
        
        # Wardrobe
        if companion.wardrobe:
            lines.append(f"Available Outfits: {', '.join(companion.wardrobe.keys())}")
        
        # Dialogue tone based on affinity
        affinity = game_state.affinity.get(companion.name, 0)
        tone = self._get_tone_for_affinity(companion, affinity)
        if tone:
            lines.append(f"Dialogue Tone: {tone}")
        
        return "\n".join(lines)
    
    def _get_tone_for_affinity(
        self,
        companion: CompanionDefinition,
        affinity: int,
    ) -> str:
        """Get dialogue tone for current affinity tier.
        
        Args:
            companion: Companion definition
            affinity: Current affinity value
            
        Returns:
            Tone description or empty
        """
        if not companion.dialogue_tone:
            return ""
        
        tiers = companion.dialogue_tone.get("affinity_tiers", {})
        
        # Find matching tier
        current_tone = ""
        for threshold_str, data in sorted(tiers.items(), key=lambda x: int(x[0])):
            threshold = int(threshold_str)
            if affinity >= threshold:
                current_tone = data.get("tone", "")
        
        return current_tone
