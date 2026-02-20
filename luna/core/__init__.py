"""Core engine components for Luna RPG v4."""
from __future__ import annotations

from luna.core.models import (
    GameState,
    PlayerState,
    NPCState,
    LLMResponse,
    StateUpdate,
    QuestDefinition,
    QuestInstance,
    PersonalityState,
    WorldDefinition,
    StoryBeat,
    NarrativeArc,
)
from luna.core.database import DatabaseManager, get_db_manager
from luna.core.state import StateManager
from luna.core.config import Settings, get_settings, get_user_prefs
from luna.core.story_director import StoryDirector
from luna.core.prompt_builder import PromptBuilder
from luna.core.engine import GameEngine, TurnResult

__all__ = [
    # Models
    "GameState",
    "PlayerState",
    "NPCState",
    "LLMResponse",
    "StateUpdate",
    "QuestDefinition",
    "QuestInstance",
    "PersonalityState",
    "WorldDefinition",
    "StoryBeat",
    "NarrativeArc",
    # Core
    "DatabaseManager",
    "get_db_manager",
    "StateManager",
    "Settings",
    "get_settings",
    "get_user_prefs",
    "StoryDirector",
    "PromptBuilder",
    "GameEngine",
    "TurnResult",
]
