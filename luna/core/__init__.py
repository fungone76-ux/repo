"""Core engine components for Luna RPG v4."""
from __future__ import annotations

# Models (safe, no circular imports)
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
    TimeOfDay,
)

# Database (safe)
from luna.core.database import DatabaseManager, get_db_manager

# State (safe, only uses models)
from luna.core.state import StateManager

# Config (safe)
from luna.core.config import Settings, get_settings, get_user_prefs

# These are NOT exported here to avoid circular imports:
# - GameEngine (imports from ai, systems)
# - TurnResult (defined in engine)
# Import them directly: from luna.core.engine import GameEngine, TurnResult

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
    "TimeOfDay",
    # Database
    "DatabaseManager",
    "get_db_manager",
    # State
    "StateManager",
    # Config
    "Settings",
    "get_settings",
    "get_user_prefs",
]
