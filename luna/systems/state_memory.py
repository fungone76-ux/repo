"""State and Memory Management System - Unified persistence layer.

V4 Refactor: Extracted from engine.py to centralize all state and memory operations.

Handles:
- Game state persistence (location, outfit, affinity, etc.)
- Quest states
- Global event states  
- StoryDirector state
- Personality states
- Short-term memory (conversation history)
- Long-term memory (semantic facts)
- Coordinated save/load operations
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from luna.core.database import DatabaseManager
    from luna.core.state import StateManager
    from luna.systems.memory import MemoryManager
    from luna.systems.quests import QuestEngine
    from luna.systems.global_events import GlobalEventManager
    from luna.core.story_director import StoryDirector
    from luna.systems.personality import PersonalityEngine


class StateMemoryManager:
    """Unified manager for game state and memory persistence.
    
    Centralizes all save/load operations that were previously scattered
    throughout the GameEngine, making the code cleaner and more maintainable.
    """
    
    def __init__(
        self,
        db: "DatabaseManager",
        session_id: int,
        state_manager: "StateManager",
        memory_manager: Optional["MemoryManager"] = None,
        quest_engine: Optional["QuestEngine"] = None,
        event_manager: Optional["GlobalEventManager"] = None,
        story_director: Optional["StoryDirector"] = None,
        personality_engine: Optional["PersonalityEngine"] = None,
    ):
        """Initialize state-memory manager.
        
        Args:
            db: Database manager
            session_id: Current session ID
            state_manager: State manager for game state
            memory_manager: Optional memory manager for conversation history
            quest_engine: Optional quest engine for quest states
            event_manager: Optional event manager for global events
            story_director: Optional story director for narrative state
            personality_engine: Optional personality engine for character states
        """
        self.db = db
        self.session_id = session_id
        self.state_manager = state_manager
        self.memory_manager = memory_manager
        self.quest_engine = quest_engine
        self.event_manager = event_manager
        self.story_director = story_director
        self.personality_engine = personality_engine
    
    async def save_all(self) -> None:
        """Save all game state and memory in a single transaction.
        
        This replaces the scattered save operations in engine.py
        with a single coordinated save operation.
        """
        async with self.db.session() as db_session:
            # 1. Core game state
            await self.state_manager.save(db_session)
            
            # 2. Quest states
            if self.quest_engine:
                for quest_state in self.quest_engine.get_all_states():
                    await self.db.save_quest_state(
                        db_session,
                        self.session_id,
                        quest_state.quest_id,
                        quest_state.status.value,
                        quest_state.current_stage_id,
                    )
            
            # 3. Global event states
            if self.event_manager:
                event_states_data = list(self.event_manager.to_dict()["active_events"].values())
                await self.db.save_global_event_states(
                    db_session,
                    self.session_id,
                    event_states_data,
                )
            
            # 4. StoryDirector state
            if self.story_director:
                sd_data = self.story_director.to_dict()
                await self.db.save_story_director_state(
                    db_session,
                    self.session_id,
                    sd_data.get("current_chapter", ""),
                    sd_data.get("current_beat_index", 0),
                    sd_data.get("completed_beats", []),
                    sd_data.get("beat_history", []),
                )
            
            # 5. Personality states
            if self.personality_engine:
                personality_states = self.personality_engine.get_all_states()
                personality_data = {
                    "states": [state.model_dump() for state in personality_states]
                }
                await self.db.update_session(
                    db_session,
                    self.session_id,
                    personality_state=personality_data,
                )
    
    async def load_memory(self) -> bool:
        """Load short-term memory (conversation history).
        
        Returns:
            True if memory was loaded successfully
        """
        if not self.memory_manager:
            return False
        
        try:
            await self.memory_manager.load()
            return True
        except Exception as e:
            print(f"[StateMemoryManager] Failed to load memory: {e}")
            return False
    
    def get_memory_context(
        self,
        query: str,
        limit: int = 5,
        max_facts: int = 3,
        min_importance: int = 4,
        use_semantic: bool = True,
    ) -> str:
        """Get relevant memory context for a query.
        
        Combines short-term recent history with long-term semantic facts.
        
        Args:
            query: Query text to find relevant memories
            limit: Maximum number of memories to return
            max_facts: Maximum facts to include (for compatibility)
            min_importance: Minimum importance threshold (for compatibility)
            use_semantic: Whether to use semantic search
            
        Returns:
            Formatted memory context string
        """
        if not self.memory_manager:
            return ""
        
        return self.memory_manager.get_memory_context(
            query=query,
            max_facts=max_facts,
            min_importance=min_importance,
        )
    
    def get_recent_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent conversation history.
        
        Args:
            limit: Number of recent messages to return
            
        Returns:
            List of recent messages
        """
        if not self.memory_manager:
            return []
        
        return self.memory_manager.get_recent_history(limit=limit)
    
    async def add_message(
        self,
        role: str,
        content: str,
        turn_number: int,
        visual_en: str = "",
        tags_en: Optional[List[str]] = None,
    ) -> None:
        """Add a message to short-term memory.
        
        Args:
            role: Message role (user/assistant)
            content: Message text
            turn_number: Current turn number
            visual_en: Optional visual description
            tags_en: Optional SD tags
        """
        if not self.memory_manager:
            return
        
        await self.memory_manager.add_message(
            role=role,
            content=content,
            turn_number=turn_number,
            visual_en=visual_en,
            tags_en=tags_en,
        )
    
    async def add_fact(
        self,
        text: str,
        importance: int = 5,
        source: str = "extraction",
    ) -> bool:
        """Add a fact to long-term semantic memory.
        
        Args:
            text: Fact text to store
            importance: Importance score (1-10)
            source: Source of the fact
            
        Returns:
            True if fact was added successfully
        """
        if not self.memory_manager:
            return False
        
        try:
            await self.memory_manager.add_fact(
                text=text,
                importance=importance,
                source=source,
            )
            return True
        except Exception as e:
            print(f"[StateMemoryManager] Failed to add fact: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about state and memory.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "session_id": self.session_id,
            "has_memory_manager": self.memory_manager is not None,
        }
        
        if self.memory_manager:
            stats["messages"] = len(self.memory_manager.messages)
            stats["facts"] = len(self.memory_manager.facts)
            if self.memory_manager.semantic_memory:
                stats["semantic_enabled"] = True
        
        return stats
