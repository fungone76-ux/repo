"""Phase Manager - Handles time phase transitions and NPC movement.

V4.1 Phase System:
- 4 phases: Morning (8 turns) → Afternoon (8) → Evening (8) → Night (8)
- On phase change: NPCs move to their new schedule location
- Player stays in current location
- Auto-switch to solo if companion leaves
- Turn Freeze: Can pause turn counting for important scenes

Extracted to new file for clean architecture.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from luna.core.models import TimeOfDay, GameState


@dataclass
class PhaseConfig:
    """Configuration for phase system."""
    turns_per_phase: int = 8  # 8 turns = 1 phase
    phases_per_day: int = 4   # Morning, Afternoon, Evening, Night


class PhaseManager:
    """Manages phase transitions and their consequences.
    
    Key behaviors:
    - Tracks turns within current phase
    - Triggers phase change when threshold reached
    - Handles NPC movement on phase change
    - Supports turn freeze for important scenes
    """
    
    def __init__(
        self,
        game_state: GameState,
        schedule_manager: Optional['ScheduleManager'] = None,
        config: Optional[PhaseConfig] = None,
        on_phase_change: Optional[callable] = None,
    ):
        """Initialize phase manager.
        
        Args:
            game_state: Current game state
            schedule_manager: For NPC routine lookups
            config: Phase timing configuration
            on_phase_change: Callback when phase changes
        """
        self.game_state = game_state
        self.schedule_manager = schedule_manager
        self.config = config or PhaseConfig()
        self.on_phase_change = on_phase_change
        
        # Track turns in current phase
        self._turns_in_phase: int = 0
        
        # Freeze system
        self._frozen: bool = False
        self._freeze_reason: str = ""
        
        # Track if we need to handle phase change
        self._pending_phase_change: bool = False
    
    @property
    def is_frozen(self) -> bool:
        """Check if turn counting is frozen."""
        return self._frozen
    
    @property
    def turns_until_next_phase(self) -> int:
        """Get remaining turns in current phase."""
        if self._frozen:
            return -1  # Infinite while frozen
        return self.config.turns_per_phase - self._turns_in_phase
    
    def freeze(self, reason: str = "Scene importante") -> None:
        """Freeze turn counting.
        
        Args:
            reason: Why turns are frozen (shown to player)
        """
        self._frozen = True
        self._freeze_reason = reason
        print(f"[PhaseManager] PAUSE TURN FREEZE: {reason}")
    
    def unfreeze(self) -> None:
        """Resume turn counting."""
        if self._frozen:
            self._frozen = False
            print(f"[PhaseManager] RESUME TURN: {self._freeze_reason}")
            self._freeze_reason = ""
    
    def on_turn_end(self) -> Optional[PhaseChangeResult]:
        """Call at end of each turn to track phase progress.
        
        Returns:
            PhaseChangeResult if phase changed, None otherwise
        """
        if self._frozen:
            print(f"[PhaseManager] Turn frozen ({self._freeze_reason})")
            return None
        
        self._turns_in_phase += 1
        time_val = self.game_state.time_of_day
        time_str = time_val.value if hasattr(time_val, 'value') else str(time_val)
        print(f"[PhaseManager] Turn {self._turns_in_phase}/{self.config.turns_per_phase} in {time_str}")
        
        # Check if phase should change
        if self._turns_in_phase >= self.config.turns_per_phase:
            return self._execute_phase_change()
        
        return None
    
    def _execute_phase_change(self) -> PhaseChangeResult:
        """Execute phase transition and NPC movement.
        
        Returns:
            PhaseChangeResult with all changes
        """
        old_time = self.game_state.time_of_day
        
        # Advance time
        times = list(TimeOfDay)
        if isinstance(old_time, str):
            try:
                old_time = TimeOfDay(old_time)
            except ValueError:
                old_time = TimeOfDay.MORNING
        
        current_idx = times.index(old_time)
        next_idx = (current_idx + 1) % len(times)
        new_time = times[next_idx]
        
        self.game_state.time_of_day = new_time
        self._turns_in_phase = 0
        
        old_str = old_time.value if hasattr(old_time, 'value') else str(old_time)
        new_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        print(f"[PhaseManager] PHASE CHANGE: {old_str} -> {new_str}")
        
        # Handle NPC movements
        npc_movements = self._move_npcs_for_phase_change(old_time, new_time)
        
        # Check if player's companion left
        companion_left = False
        old_companion = None
        new_companion = None
        
        if self.schedule_manager:
            active_companion = self.game_state.active_companion
            if active_companion and active_companion != "_solo_":
                # Where should companion be now?
                companion_new_location = self.schedule_manager.get_npc_location(active_companion)
                player_location = self.game_state.current_location
                
                if companion_new_location != player_location:
                    # Companion left! Switch to solo
                    companion_left = True
                    old_companion = active_companion
                    new_companion = "_solo_"
                    print(f"[PhaseManager] {active_companion} left for {companion_new_location}, switching to solo")
        
        result = PhaseChangeResult(
            old_time=old_time,
            new_time=new_time,
            npc_movements=npc_movements,
            companion_left=companion_left,
            old_companion=old_companion,
            new_companion=new_companion,
        )
        
        if self.on_phase_change:
            self.on_phase_change(result)
        
        return result
    
    def _move_npcs_for_phase_change(
        self,
        old_time: TimeOfDay,
        new_time: TimeOfDay,
    ) -> Dict[str, Dict]:
        """Move all NPCs to their new schedule locations.
        
        V4.2: Generic - works with any world. Iterates over all scheduled NPCs
        instead of hardcoded names.
        
        Args:
            old_time: Previous time period
            new_time: New time period
            
        Returns:
            Dict of npc_name -> {old_location, new_location, activity}
        """
        movements = {}
        
        if not self.schedule_manager:
            return movements
        
        # V4.2: Get all NPCs that have schedules (generic, not hardcoded)
        # This works with any world
        npc_names = self.schedule_manager.get_all_scheduled_npcs()
        
        for npc_name in npc_names:
            # Skip solo/temporary NPCs
            if npc_name == "_solo_":
                continue
                
            old_location = self.schedule_manager.get_npc_location_at_time(npc_name, old_time)
            new_location = self.schedule_manager.get_npc_location(npc_name)  # Uses current (new) time
            activity = self.schedule_manager.get_npc_activity(npc_name)
            
            if old_location != new_location:
                movements[npc_name] = {
                    "old_location": old_location,
                    "new_location": new_location,
                    "activity": activity,
                }
                print(f"[PhaseManager] {npc_name} moved: {old_location} -> {new_location}")
        
        return movements
    
    def get_phase_status(self) -> str:
        """Get current phase status for display."""
        time_val = self.game_state.time_of_day
        time_str = time_val.value if hasattr(time_val, 'value') else str(time_val)
        
        if self._frozen:
            return f"⏸️ {time_str.upper()} (PAUSA)"
        
        remaining = self.turns_until_next_phase
        return f"⏰ {time_str.upper()} ({remaining} turni rimasti)"
    
    def should_auto_freeze(self, user_input: str, llm_response_text: str) -> Optional[str]:
        """Check if current situation warrants auto-freezing turns.
        
        V4.2: Automatically pause turn counting during important scenes
        to prevent NPCs from leaving mid-conversation.
        
        Args:
            user_input: Player's input
            llm_response_text: LLM's response
            
        Returns:
            Reason to freeze if auto-freeze triggered, None otherwise
        """
        if self._frozen:
            return None  # Already frozen
        
        text_combined = (user_input + " " + llm_response_text).lower()
        
        # Romantic/critical scene indicators
        romantic_triggers = [
            "ti amo", "ti adoro", "mi piaci", "baciami", "abbracciami",
            "mi manchi", "sei speciale", "sei importante", "confession",
            "promettimi", "giurami", "non lasciarmi", "resta con me",
        ]
        
        # Critical event indicators
        critical_triggers = [
            "muori", "morte", "incidente", "ferito", "sangue", "ospedale",
            "pericolo", "minaccia", "rapimento", "incendio", "esplosione",
            "non andare", "fermati", "ascoltami", "è importante",
        ]
        
        # Check romantic triggers
        for trigger in romantic_triggers:
            if trigger in text_combined:
                return f"Momento romantico ({trigger})"
        
        # Check critical triggers
        for trigger in critical_triggers:
            if trigger in text_combined:
                return f"Situazione critica ({trigger})"
        
        return None
    
    def auto_freeze_if_needed(self, user_input: str, llm_response_text: str) -> bool:
        """Auto-freeze turns if situation is important.
        
        Args:
            user_input: Player's input
            llm_response_text: LLM's response
            
        Returns:
            True if auto-froze, False otherwise
        """
        reason = self.should_auto_freeze(user_input, llm_response_text)
        if reason:
            self.freeze(f"⏸️ {reason}")
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Save phase manager state to dict."""
        return {
            "turns_in_phase": self._turns_in_phase,
            "frozen": self._frozen,
            "freeze_reason": self._freeze_reason,
            "pending_phase_change": self._pending_phase_change,
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load phase manager state from dict."""
        self._turns_in_phase = data.get("turns_in_phase", 0)
        self._frozen = data.get("frozen", False)
        self._freeze_reason = data.get("freeze_reason", "")
        self._pending_phase_change = data.get("pending_phase_change", False)
    
    def set_game_state(self, game_state: GameState) -> None:
        """Update game state reference (needed after loading)."""
        self.game_state = game_state


@dataclass
class PhaseChangeResult:
    """Result of a phase change."""
    old_time: TimeOfDay
    new_time: TimeOfDay
    npc_movements: Dict[str, Dict]
    companion_left: bool
    old_companion: Optional[str]
    new_companion: Optional[str]
    
    @property
    def time_message(self) -> str:
        """Get immersive time transition message."""
        transitions = {
            (TimeOfDay.MORNING, TimeOfDay.AFTERNOON): "🌅 Il sole sale più alto... è pomeriggio.",
            (TimeOfDay.AFTERNOON, TimeOfDay.EVENING): "🌆 Il sole inizia a calare... è sera.",
            (TimeOfDay.EVENING, TimeOfDay.NIGHT): "🌙 La notte cala sul paese...",
            (TimeOfDay.NIGHT, TimeOfDay.MORNING): "☀️ Una nuova alba... è mattino!",
        }
        # Handle both enum and string
        old_time = self.old_time
        new_time = self.new_time
        if isinstance(old_time, str):
            try:
                old_time = TimeOfDay(old_time)
            except ValueError:
                old_time = TimeOfDay.MORNING
        if isinstance(new_time, str):
            try:
                new_time = TimeOfDay(new_time)
            except ValueError:
                new_time = TimeOfDay.MORNING
        new_time_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        return transitions.get((old_time, new_time), f"⏰ Ora è {new_time_str}")
    
    @property
    def movement_message(self) -> str:
        """Get message about NPC movements."""
        if not self.npc_movements:
            return ""
        
        lines = ["\n📍 I personaggi si sono mossi:"]
        for npc, move in self.npc_movements.items():
            lines.append(f"  • {npc}: {move['activity']}")
        
        return "\n".join(lines)
    
    @property
    def companion_message(self) -> str:
        """Get message if companion left."""
        if not self.companion_left or not self.old_companion:
            return ""
        
        return f"\n👋 {self.old_companion} è andata via. Sei solo ora."
