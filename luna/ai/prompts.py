"""Prompt builders for LLM requests.

Provides structured system prompts and JSON schemas for consistent LLM responses.
NOTE: This module is deprecated. Use PromptBuilder from core.prompt_builder instead.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def build_system_prompt(
    world_context: str,
    companion_context: str,
    game_state_context: str,
    quest_context: str = "",
    personality_context: str = "",
    story_beat_instruction: str = "",
) -> str:
    """Build complete system prompt for LLM.
    
    DEPRECATED: Use PromptBuilder.build_system_prompt() instead.
    
    Args:
        world_context: World lore, setting, genre
        companion_context: Active companion personality, backstory
        game_state_context: Current location, time, affinity, etc.
        quest_context: Active quest narrative prompts
        personality_context: Behavioral analysis and impressions
        story_beat_instruction: Optional forced narrative beat
        
    Returns:
        Complete system prompt
    """
    # Delegate to the main prompt builder logic
    # This ensures consistency across the codebase
    sections = [
        "=== LUNA RPG - SYSTEM INSTRUCTIONS ===",
        "",
        "You are the Game Master of a visual novel/RPG game.",
        "NARRATE in ITALIAN LANGUAGE (the game is in Italian).",
        "",
        "=== CRITICAL RULES (DO NOT BREAK) ===",
        "1. NEVER repeat or echo what the player just said.",
        "2. NEVER describe the player's actions - only describe NPC actions and reactions.",
        "3. NPC DIALOGUE goes in quotes: \"Cosa vuoi?\"",
        "4. NPC ACTIONS go in third person with asterisks: *Luna crosses her arms.*",
        "5. NEVER use first person (I/me/my) - you are the Game Master, not a character.",
        "6. NEVER write 'You see...' or 'You feel...' - that's god-moding the player.",
        "7. Player input = THEIR action. Your response = NPC reaction ONLY.",
        "",
        "=== WRONG vs RIGHT EXAMPLES ===",
        "",
        "Player: 'Vado in segreteria' (I go to the office)",
        "❌ WRONG: 'Vado verso la segreteria...' (You speak as the player!)",
        "❌ WRONG: 'Vedi che la porta è aperta...' (You describe what player sees!)",
        "❌ WRONG: 'Io mi chiamo Enrico...' (NPC speaking as player!)",
        "",
        "✅ RIGHT: \"Dove vai?\" *Maria crosses her arms blocking the way.* \"Non puoi entrare.\"",
        "✅ RIGHT: *Luna turns around.* \"Ah, the new student.\" *She looks you up and down.*",
        "",
        "=== WORLD CONTEXT ===",
        world_context,
        "",
        "=== COMPANION CONTEXT ===",
        companion_context,
        "",
        "=== CURRENT GAME STATE ===",
        game_state_context,
    ]
    
    if quest_context:
        sections.extend([
            "",
            "=== ACTIVE QUESTS ===",
            quest_context,
        ])
    
    if personality_context:
        sections.extend([
            "",
            "=== PSYCHOLOGICAL CONTEXT ===",
            personality_context,
        ])
    
    if story_beat_instruction:
        sections.extend([
            "",
            "=== MANDATORY NARRATIVE BEAT ===",
            story_beat_instruction,
            "",
            "You MUST include the above event in your response.",
        ])
    
    sections.extend([
        "",
        "=== OUTPUT FORMAT ===",
        "Respond with valid JSON matching this schema:",
        json.dumps(get_response_schema(), indent=2),
        "",
        "=== END INSTRUCTIONS ===",
    ])
    
    return "\n".join(sections)


def get_response_schema() -> Dict[str, Any]:
    """Get JSON schema for LLM response validation.
    
    Returns:
        JSON Schema object
    """
    return {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Narrative text in Italian (1-3 short sentences). NPC dialogue in quotes, actions in asterisks.",
                "minLength": 10,
            },
            "visual_en": {
                "type": "string",
                "description": "Visual description for Stable Diffusion (English, detailed, static pose)",
            },
            "tags_en": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Stable Diffusion tags (English, 5-15 tags)",
            },
            "body_focus": {
                "type": "string",
                "description": "Body part in focus (optional: face, hands, legs, etc.)",
            },
            "approach_used": {
                "type": "string",
                "enum": ["standard", "physical_action", "question", "choice"],
                "description": "Interaction approach used in this scene",
            },
            "composition": {
                "type": "string",
                "enum": ["close_up", "medium_shot", "cowboy_shot", "wide_shot", "from_below", "from_above", "group", "scene"],
                "description": "Camera framing for image generation",
            },
            "updates": {
                "type": "object",
                "properties": {
                    "affinity_change": {
                        "type": "object",
                        "description": "Character -> delta mapping (clamped -5/+5)",
                    },
                    "current_outfit": {
                        "type": "string",
                        "description": "New outfit for active companion",
                    },
                    "location": {
                        "type": "string",
                        "description": "New location ID",
                    },
                    "time_of_day": {
                        "type": "string",
                        "enum": ["Morning", "Afternoon", "Evening", "Night"],
                    },
                    "set_flags": {
                        "type": "object",
                        "description": "Flags to set (key: value)",
                    },
                    "npc_emotion": {
                        "type": "string",
                        "description": "New emotional state for NPC",
                    },
                },
            },
        },
        "required": ["text"],
    }


def build_world_context(
    world_name: str,
    genre: str,
    description: str,
    lore: str,
    locations: List[str],
) -> str:
    """Build world context section.
    
    Args:
        world_name: World identifier
        genre: Genre (Visual Novel, Fantasy, etc.)
        description: Short description
        lore: World background/lore
        locations: List of available locations
        
    Returns:
        Formatted world context
    """
    lines = [
        f"World: {world_name}",
        f"Genre: {genre}",
        f"Description: {description}",
        "",
        "Lore:",
        lore,
        "",
        "Available Locations:",
    ]
    for loc in locations:
        lines.append(f"  - {loc}")
    
    return "\n".join(lines)


def build_companion_context(
    name: str,
    role: str,
    age: int,
    personality: str,
    current_affinity: int,
    current_outfit: str,
    emotional_state: str,
    available_outfits: List[str],
) -> str:
    """Build companion context section.
    
    Args:
        name: Companion name
        role: Role in story
        age: Character age
        personality: Personality description
        current_affinity: Current affinity (0-100)
        current_outfit: Current outfit worn
        emotional_state: Current emotional state
        available_outfits: List of valid outfit IDs
        
    Returns:
        Formatted companion context
    """
    lines = [
        f"Name: {name}",
        f"Role: {role}",
        f"Age: {age}",
        f"Personality: {personality}",
        f"Current Affinity: {current_affinity}/100",
        f"Current Outfit: {current_outfit}",
        f"Emotional State: {emotional_state}",
        "",
        "Available Outfits:",
    ]
    for outfit in available_outfits:
        lines.append(f"  - {outfit}")
    
    return "\n".join(lines)


def build_game_state_context(
    location: str,
    time_of_day: str,
    turn_count: int,
    active_quests: List[str],
    recent_events: List[str],
) -> str:
    """Build game state context section.
    
    Args:
        location: Current location
        time_of_day: Time period
        turn_count: Turn number
        active_quests: List of active quest titles
        recent_events: Recent narrative events
        
    Returns:
        Formatted game state context
    """
    lines = [
        f"Location: {location}",
        f"Time: {time_of_day}",
        f"Turn: {turn_count}",
        "",
        "Active Quests:",
    ]
    
    if active_quests:
        for quest in active_quests:
            lines.append(f"  - {quest}")
    else:
        lines.append("  (none)")
    
    if recent_events:
        lines.extend([
            "",
            "Recent Events:",
        ])
        for event in recent_events[-3:]:  # Last 3 only
            lines.append(f"  - {event}")
    
    return "\n".join(lines)
