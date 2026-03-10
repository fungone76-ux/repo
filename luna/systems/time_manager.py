"""Time Management System - Automatic time progression.

V4 Hybrid Adaptive Time System:
- Phase 1: Auto-advance every N turns
- Phase 2: Rest/Sleep commands for voluntary advancement
- Phase 3: Deadline system for quests

Extracted to new file to keep engine.py clean.
"""
from __future__ import annotations

from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from luna.core.models import TimeOfDay, GameState


@dataclass
class TimeConfig:
    """Configuration for time progression."""
    turns_per_period: int = 4  # Turns before auto-advancing time
    enable_auto_advance: bool = True
    enable_rest_commands: bool = True
    enable_deadlines: bool = True
    
    # Rest command triggers (Italian)
    # V4.4: Separated sleep (full night) from rest (short break)
    rest_triggers: List[str] = field(default_factory=lambda: [
        # Short rest - advance one period
        "riposo", "mi riposo", "faccio una pausa", "mi fermo a riposare",
    ])
    
    # Full sleep triggers - go to next morning
    sleep_triggers: List[str] = field(default_factory=lambda: [
        "dormo", "dormire", "vado a dormire", "finisco la giornata",
        "vado a casa", "end of day", "chiudo la giornata", 
        "a letto", "sonno", "buonanotte", "notte"
    ])


@dataclass  
class QuestDeadline:
    """Deadline tracker for a quest."""
    quest_id: str
    quest_title: str
    deadline_turn: int  # Absolute turn number
    warning_turns: List[int] = field(default_factory=list)  # Turns when to warn
    warned: bool = False
    
    @property
    def turns_remaining(self, current_turn: int) -> int:
        return max(0, self.deadline_turn - current_turn)
    
    @property
    def is_expired(self, current_turn: int) -> bool:
        return current_turn >= self.deadline_turn


class TimeManager:
    """Manages automatic and voluntary time progression.
    
    Replaces manual time button with immersive systems:
    1. Auto-advance every N turns
    2. Rest/sleep commands
    3. Quest deadlines
    """
    
    def __init__(
        self,
        game_state: GameState,
        config: Optional[TimeConfig] = None,
        on_time_change: Optional[Callable[[TimeOfDay, str], None]] = None,
    ):
        """Initialize time manager.
        
        Args:
            game_state: Current game state
            config: Time progression configuration
            on_time_change: Callback when time changes (new_time, message)
        """
        self.game_state = game_state
        self.config = config or TimeConfig()
        self.on_time_change = on_time_change
        
        # Track turns since last time change
        self._turns_since_last_advance: int = 0
        
        # Active deadlines
        self._deadlines: Dict[str, QuestDeadline] = {}
        
        # Time transition messages
        self._time_messages = {
            (TimeOfDay.MORNING, TimeOfDay.AFTERNOON): [
                "🌅 Il sole sale più alto... è pomeriggio.",
                "🌅 La mattina vola via... arriva il pomeriggio.",
                "🕐 Le ore passano. È ora di pranzo.",
            ],
            (TimeOfDay.AFTERNOON, TimeOfDay.EVENING): [
                "🌆 Il sole inizia a calare... è sera.",
                "🌆 La giornata volge al termine... cala il crepuscolo.",
                "🕐 L'ombra si allunga... è sera.",
            ],
            (TimeOfDay.EVENING, TimeOfDay.NIGHT): [
                "🌙 La notte cala sul paese...",
                "🌙 Le stelle si accendono... è notte fonda.",
                "🕐 Il silenzio della notte avvolge tutto...",
            ],
            (TimeOfDay.NIGHT, TimeOfDay.MORNING): [
                "☀️ Una nuova alba... è mattino.",
                "☀️ Il giorno nuovo inizia... buongiorno!",
                "🕐 Il sole sorge su un nuovo giorno...",
            ],
        }
        
        # Rest transition messages
        self._rest_messages = [
            "💤 Decidi di riposare... il tempo passa.",
            "🛏️ Chiudi gli occhi per un po'...",
            "💤 Una pausa ben meritata...",
        ]
    
    def on_turn_end(self) -> Optional[str]:
        """Call at end of each turn to handle auto-advance.
        
        Returns:
            Time change message or None
        """
        if not self.config.enable_auto_advance:
            return None
        
        self._turns_since_last_advance += 1
        
        # Check if it's time to advance
        if self._turns_since_last_advance >= self.config.turns_per_period:
            return self._advance_time(auto=True)
        
        return None
    
    def check_rest_command(self, user_input: str) -> Optional[str]:
        """Check if user wants to rest/sleep.
        
        V4.4: Distinguishes between short rest (one period) and full sleep (to next morning)
        
        Args:
            user_input: Player's input
            
        Returns:
            Time change message if rest triggered, None otherwise
        """
        if not self.config.enable_rest_commands:
            return None
        
        text_lower = user_input.lower()
        
        # Check for full sleep commands first (higher priority)
        for trigger in self.config.sleep_triggers:
            if trigger in text_lower:
                return self._advance_time(auto=False, is_rest=True, is_full_sleep=True)
        
        # Check for short rest commands
        for trigger in self.config.rest_triggers:
            if trigger in text_lower:
                return self._advance_time(auto=False, is_rest=True, is_full_sleep=False)
        
        return None
    
    def _advance_time(self, auto: bool = True, is_rest: bool = False, is_full_sleep: bool = False) -> str:
        """Advance time to next period.
        
        Args:
            auto: True if auto-advance, False if manual
            is_rest: True if triggered by rest command
            is_full_sleep: True if full sleep (go to next morning)
            
        Returns:
            Message describing time change
        """
        import random
        old_time = self.game_state.time_of_day
        
        # Handle string time
        if isinstance(old_time, str):
            try:
                old_time = TimeOfDay(old_time)
            except ValueError:
                old_time = TimeOfDay.MORNING
        
        # V4.4 FIX: Full sleep goes to next morning
        if is_full_sleep:
            # Always go to Morning (next day)
            new_time = TimeOfDay.MORNING
            
            # Update state
            self.game_state.time_of_day = new_time
            self._turns_since_last_advance = 0
            
            # Special sleep messages
            sleep_messages = [
                "🌙 Chiudi gli occhi e ti addormenti...",
                "💤 Una notte di riposo ben meritata...",
                "🛏️ Il sonno ti avvolge dolcemente...",
            ]
            message = random.choice(sleep_messages)
            message += " È un nuovo giorno. Ora è Morning."
            
            old_time_str = old_time.value if hasattr(old_time, 'value') else str(old_time)
            print(f"[TimeManager] Full sleep: {old_time_str} → Morning (next day)")
            
            # Callback
            if self.on_time_change:
                self.on_time_change(new_time, message)
            
            return message
        
        # Normal advancement (one period)
        times = list(TimeOfDay)
        current_idx = times.index(old_time)
        next_idx = (current_idx + 1) % len(times)
        new_time = times[next_idx]
        
        # Update state
        self.game_state.time_of_day = new_time
        self._turns_since_last_advance = 0
        
        # Generate message
        new_time_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        
        if is_rest:
            message = random.choice(self._rest_messages)
            message += f" Ora è {new_time_str}."
        else:
            message = self._get_time_message(old_time, new_time)
        
        # Callback
        if self.on_time_change:
            self.on_time_change(new_time, message)
        
        old_time_str = old_time.value if hasattr(old_time, 'value') else str(old_time)
        print(f"[TimeManager] Time advanced: {old_time_str} → {new_time_str} ({'auto' if auto else 'manual'})")
        
        return message
    
    def _get_time_message(self, old_time: TimeOfDay, new_time: TimeOfDay) -> str:
        """Get transition message for time change."""
        import random
        
        messages = self._time_messages.get((old_time, new_time), [])
        if messages:
            return random.choice(messages)
        
        new_time_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        return f"⏰ Il tempo passa... ora è {new_time_str}."
    
    # =========================================================================
    # Phase 3: Deadline System
    # =========================================================================
    
    def set_quest_deadline(
        self,
        quest_id: str,
        quest_title: str,
        turns_from_now: int,
        warning_thresholds: Optional[List[int]] = None,
    ) -> None:
        """Set a deadline for a quest.
        
        Args:
            quest_id: Quest identifier
            quest_title: Display name
            turns_from_now: How many turns until deadline
            warning_thresholds: Turn counts when to warn player
        """
        if not self.config.enable_deadlines:
            return
        
        current_turn = self.game_state.turn_count
        deadline_turn = current_turn + turns_from_now
        
        warnings = warning_thresholds or [turns_from_now // 2, 5, 2]
        warning_turns = [current_turn + w for w in warnings if w < turns_from_now]
        
        self._deadlines[quest_id] = QuestDeadline(
            quest_id=quest_id,
            quest_title=quest_title,
            deadline_turn=deadline_turn,
            warning_turns=warning_turns,
        )
        
        print(f"[TimeManager] Deadline set for '{quest_title}': {turns_from_now} turns")
    
    def remove_deadline(self, quest_id: str) -> None:
        """Remove a quest deadline (when completed)."""
        if quest_id in self._deadlines:
            del self._deadlines[quest_id]
            print(f"[TimeManager] Deadline removed for {quest_id}")
    
    def check_deadlines(self) -> List[str]:
        """Check all deadlines and return warnings/expirations.
        
        Returns:
            List of messages for player
        """
        if not self.config.enable_deadlines:
            return []
        
        current_turn = self.game_state.turn_count
        messages = []
        expired = []
        
        for quest_id, deadline in self._deadlines.items():
            # Check expiration
            if deadline.is_expired(current_turn):
                messages.append(
                    f"⏰ SCADENZA: '{deadline.quest_title}' è scaduta!"
                )
                expired.append(quest_id)
            # Check warnings
            elif current_turn in deadline.warning_turns and not deadline.warned:
                turns_left = deadline.deadline_turn - current_turn
                messages.append(
                    f"⏰ ATTENZIONE: '{deadline.quest_title}' scade in {turns_left} turni!"
                )
                deadline.warned = True
        
        # Remove expired
        for qid in expired:
            del self._deadlines[qid]
        
        return messages
    
    def get_time_status(self) -> str:
        """Get current time status for display."""
        time_val = self.game_state.time_of_day
        if isinstance(time_val, str):
            return time_val.upper()
        return time_val.value.upper()
    
    def get_next_advance_turns(self) -> int:
        """Get turns remaining until next auto-advance."""
        if not self.config.enable_auto_advance:
            return -1
        return self.config.turns_per_period - self._turns_since_last_advance
