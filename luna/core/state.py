"""Game state management.

Handles serialization, persistence, and manipulation of game state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from luna.core.database import DatabaseManager, GameSessionModel
from luna.core.models import (
    GameState,
    NPCState,
    PlayerState,
    QuestInstance,
    QuestStatus,
    TimeOfDay,
)


class StateManager:
    """Manages game state persistence and operations.
    
    This class provides high-level operations for loading, saving,
    and manipulating game state, abstracting database details.
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize state manager.
        
        Args:
            db_manager: Database manager instance. Creates default if None.
        """
        self.db = db_manager
        self._current: Optional[GameState] = None
    
    @property
    def current(self) -> GameState:
        """Get current game state.
        
        Raises:
            RuntimeError: If no game is loaded
        """
        if self._current is None:
            raise RuntimeError("No game state loaded")
        return self._current
    
    @property
    def is_loaded(self) -> bool:
        """True if a game state is loaded."""
        return self._current is not None
    
    async def create_new(
        self,
        db: AsyncSession,
        world_id: str,
        companion: str,
        companions_list: List[str],
    ) -> GameState:
        """Create new game session.
        
        Args:
            db: Database session
            world_id: World identifier
            companion: Starting companion name
            companions_list: List of all available companions
            
        Returns:
            New game state
        """
        # Initialize affinity for all companions
        affinity = {name: 0 for name in companions_list}
        
        # Create database session
        session_model = await self.db.create_session(
            db=db,
            world_id=world_id,
            companion=companion,
            affinity=affinity,
        )
        
        # Create game state
        state = GameState(
            session_id=session_model.id,
            world_id=world_id,
            active_companion=companion,
            companion_outfit="default",
            player=PlayerState(),
            affinity=affinity,
            npc_states={},
            active_quests=[],
            completed_quests=[],
            quest_flags={},
        )
        
        self._current = state
        return state
    
    async def load(self, db: AsyncSession, session_id: int) -> Optional[GameState]:
        """Load existing game session.
        
        Args:
            db: Database session
            session_id: Session ID to load
            
        Returns:
            Game state or None if not found
        """
        session_model = await self.db.get_session(db, session_id)
        if not session_model:
            return None
        
        # Deserialize player state
        player_data = session_model.player_state or {}
        player = PlayerState(**player_data) if player_data else PlayerState()
        
        # Deserialize NPC states
        npc_states = {}
        npc_data = session_model.npc_states or {}
        for name, data in npc_data.items():
            if isinstance(data, dict):
                npc_states[name] = NPCState(name=name, **data)
        
        # Deserialize outfit states
        from luna.core.models import OutfitState
        outfit_states = {}
        outfit_data = getattr(session_model, 'outfit_states', None) or {}
        for name, data in outfit_data.items():
            if isinstance(data, dict):
                outfit_states[name] = OutfitState(**data)
        
        # Create game state
        state = GameState(
            session_id=session_model.id,
            world_id=session_model.world_id,
            turn_count=session_model.turn_count,
            time_of_day=TimeOfDay(session_model.time_of_day),
            current_location=session_model.current_location,
            active_companion=session_model.active_companion,
            companion_outfit=session_model.companion_outfit,
            companion_outfits=outfit_states,
            player=player,
            npc_states=npc_states,
            affinity=session_model.affinity or {},
            flags=session_model.flags or {},
        )
        
        # Load quest states
        quest_models = await self.db.get_all_quest_states(db, session_id)
        for qm in quest_models:
            if qm.status == QuestStatus.ACTIVE.value:
                state.active_quests.append(qm.quest_id)
            elif qm.status == QuestStatus.COMPLETED.value:
                state.completed_quests.append(qm.quest_id)
        
        self._current = state
        return state
    
    async def save(self, db: AsyncSession) -> bool:
        """Save current game state.
        
        Args:
            db: Database session
            
        Returns:
            True if saved successfully
        """
        if not self._current:
            return False
        
        state = self._current
        
        # Serialize NPC states
        npc_data = {
            name: npc.model_dump(exclude={"name"}) 
            for name, npc in state.npc_states.items()
        }
        
        # Serialize outfit states
        outfit_data = {
            name: outfit.model_dump() 
            for name, outfit in state.companion_outfits.items()
        }
        
        # Update database
        updated = await self.db.update_session(
            db=db,
            session_id=state.session_id,
            turn_count=state.turn_count,
            time_of_day=state.time_of_day.value,
            current_location=state.current_location,
            active_companion=state.active_companion,
            companion_outfit=state.companion_outfit,
            outfit_states=outfit_data,
            player_state=state.player.model_dump(),
            npc_states=npc_data,
            affinity=state.affinity,
            flags=state.flags,
        )
        
        return updated
    
    # =========================================================================
    # State Operations
    # =========================================================================
    
    def advance_turn(self) -> int:
        """Increment turn counter.
        
        Returns:
            New turn number
        """
        self.current.turn_count += 1
        return self.current.turn_count
    
    def set_time(self, time_of_day: TimeOfDay) -> None:
        """Set time of day.
        
        Args:
            time_of_day: New time period
        """
        self.current.time_of_day = time_of_day
    
    def advance_time(self) -> TimeOfDay:
        """Advance to next time period.
        
        Returns:
            New time of day
        """
        times = list(TimeOfDay)
        current_idx = times.index(self.current.time_of_day)
        next_idx = (current_idx + 1) % len(times)
        self.current.time_of_day = times[next_idx]
        return self.current.time_of_day
    
    def set_location(self, location: str) -> None:
        """Set current location.
        
        Args:
            location: Location identifier
        """
        self.current.current_location = location
    
    def switch_companion(self, companion: str, outfit: Optional[str] = None) -> bool:
        """Switch active companion.
        
        Args:
            companion: New companion name
            outfit: Optional outfit style to set (uses existing or default)
            
        Returns:
            True if switched (companion exists in affinity)
        """
        if companion not in self.current.affinity:
            return False
        
        self.current.active_companion = companion
        
        # Sincronizza il campo legacy per il database
        current_outfit = self.current.get_outfit()
        self.current.companion_outfit = current_outfit.style

        # If outfit specified, update it
        if outfit:
            self.set_outfit_style(outfit)

        return True

    def set_outfit(self, outfit: str) -> None:
        """Set outfit for active companion (redirects to modern style system).

        Args:
            outfit: Outfit style identifier
        """
        self.set_outfit_style(outfit)

    def set_outfit_full(
        self,
        style: str,
        description: str,
        components: Optional[Dict[str, str]] = None,
        is_special: bool = False,
    ) -> None:
        """Set complete outfit state for active companion.

        Args:
            style: Outfit style (casual, formal, etc)
            description: Full outfit description
            components: Structured components dict
            is_special: If this is a special state (towel, etc)
        """
        from luna.core.models import OutfitState

        outfit = OutfitState(
            style=style,
            description=description,
            components=components or {},
            last_updated_turn=self.current.turn_count,
            is_special=is_special,
        )
        self.current.set_outfit(outfit)
        self.current.companion_outfit = style  # Sincronizzazione per DB

    def set_outfit_style(self, style: str) -> None:
        """Set outfit style (triggers new outfit generation).

        Args:
            style: New outfit style
        """
        outfit = self.current.get_outfit()
        outfit.style = style
        outfit.last_updated_turn = self.current.turn_count
        # Sincronizza il campo legacy per non corrompere il salvataggio
        self.current.companion_outfit = style
        # Description will be regenerated by LLM

    def modify_outfit_component(self, component: str, value: str) -> None:
        """Modify a single outfit component.

        Args:
            component: Component type (shoes, top, etc)
            value: New value
        """
        outfit = self.current.get_outfit()
        outfit.set_component(component, value)
        outfit.last_updated_turn = self.current.turn_count

    def get_outfit(self, companion: Optional[str] = None) -> Any:
        """Get outfit state for a companion.

        Args:
            companion: Companion name (default: active)

        Returns:
            OutfitState for the companion
        """
        name = companion or self.current.active_companion
        return self.current.get_outfit(name)

    # =========================================================================
    # Affinity Operations
    # =========================================================================

    def get_affinity(self, companion: str) -> int:
        """Get affinity with companion.

        Args:
            companion: Companion name

        Returns:
            Affinity value (0-100)
        """
        return self.current.affinity.get(companion, 0)

    def change_affinity(
        self,
        companion: str,
        delta: int,
        clamp: bool = True,
    ) -> int:
        """Modify affinity with companion.

        Args:
            companion: Companion name
            delta: Change amount (positive or negative)
            clamp: If True, clamps to 0-100 range

        Returns:
            New affinity value
        """
        current = self.current.affinity.get(companion, 0)
        new_value = current + delta

        if clamp:
            new_value = max(0, min(100, new_value))

        self.current.affinity[companion] = new_value
        return new_value

    # =========================================================================
    # NPC State Operations
    # =========================================================================

    def get_npc_state(self, name: str) -> Optional[NPCState]:
        """Get NPC state.

        Args:
            name: NPC name

        Returns:
            NPC state or None
        """
        return self.current.npc_states.get(name)

    def ensure_npc_state(self, name: str) -> NPCState:
        """Get or create NPC state.

        Args:
            name: NPC name

        Returns:
            NPC state (existing or new)
        """
        if name not in self.current.npc_states:
            self.current.npc_states[name] = NPCState(name=name)
        return self.current.npc_states[name]

    def update_npc_location(self, name: str, location: str) -> None:
        """Update NPC location.

        Args:
            name: NPC name
            location: New location
        """
        npc = self.ensure_npc_state(name)
        npc.location = location

    def update_npc_outfit(self, name: str, outfit: str) -> None:
        """Update NPC outfit.

        Args:
            name: NPC name
            outfit: New outfit style
        """
        npc = self.ensure_npc_state(name)
        # BUG FIX: Usiamo la struttura a dizionario invece della stringa inesistente
        npc.outfit.style = outfit
        npc.outfit.last_updated_turn = self.current.turn_count

    def update_npc_emotion(self, name: str, emotion: str) -> None:
        """Update NPC emotional state.

        Args:
            name: NPC name
            emotion: Emotional state
        """
        npc = self.ensure_npc_state(name)
        npc.emotional_state = emotion

    # =========================================================================
    # Quest Operations
    # =========================================================================

    def start_quest(self, quest_id: str) -> bool:
        """Mark quest as active.

        Args:
            quest_id: Quest identifier

        Returns:
            True if started (wasn't already active)
        """
        if quest_id in self.current.active_quests:
            return False
        if quest_id in self.current.completed_quests:
            return False

        self.current.active_quests.append(quest_id)
        return True

    def complete_quest(self, quest_id: str) -> bool:
        """Mark quest as completed.

        Args:
            quest_id: Quest identifier

        Returns:
            True if completed (was active)
        """
        if quest_id not in self.current.active_quests:
            return False

        self.current.active_quests.remove(quest_id)
        self.current.completed_quests.append(quest_id)
        return True

    def fail_quest(self, quest_id: str) -> bool:
        """Mark quest as failed.

        Args:
            quest_id: Quest identifier

        Returns:
            True if failed (was active)
        """
        if quest_id not in self.current.active_quests:
            return False

        self.current.active_quests.remove(quest_id)
        return True

    def is_quest_active(self, quest_id: str) -> bool:
        """Check if quest is active.

        Args:
            quest_id: Quest identifier

        Returns:
            True if active
        """
        return quest_id in self.current.active_quests

    def is_quest_completed(self, quest_id: str) -> bool:
        """Check if quest is completed.

        Args:
            quest_id: Quest identifier

        Returns:
            True if completed
        """
        return quest_id in self.current.completed_quests

    def set_flag(self, key: str, value: Any = True) -> None:
        """Set quest/game flag.

        Args:
            key: Flag name
            value: Flag value
        """
        self.current.flags[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        """Get flag value.

        Args:
            key: Flag name
            default: Default value if not set

        Returns:
            Flag value or default
        """
        return self.current.flags.get(key, default)

    def has_flag(self, key: str) -> bool:
        """Check if flag exists and is truthy.

        Args:
            key: Flag name

        Returns:
            True if flag exists and is truthy
        """
        return bool(self.current.flags.get(key))