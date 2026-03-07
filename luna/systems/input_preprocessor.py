"""Input Preprocessor - Handles all input parsing and special commands.

V4.3 REFACTOR: Extracted from engine.py to reduce complexity.
Handles: movement detection, farewell, freeze/unfreeze, rest commands, schedule queries.
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class PreprocessResult:
    """Result of input preprocessing."""
    should_stop: bool = False
    stop_reason: str = ""
    turn_result: Optional[Any] = None  # TurnResult if stopping
    is_movement: bool = False
    movement_target: Optional[str] = None
    is_farewell: bool = False
    is_freeze_command: bool = False
    is_rest_command: bool = False
    rest_message: str = ""


class InputPreprocessor:
    """Preprocesses user input to detect special commands and intents."""
    
    # Freeze/Unfreeze commands
    FREEZE_COMMANDS = [
        "pausa", "freeze", "blocca turni", "blocca tempo",
        "ferma tempo", "pausa turni", "importante", "momento importante",
    ]
    UNFREEZE_COMMANDS = [
        "riprendi", "unfreeze", "sblocca turni", "sblocca tempo",
        "riparti", "vai", "continua",
    ]
    
    # Rest commands that advance time
    REST_PATTERNS = [
        r"\bvado a dormire\b",
        r"\bmi addormento\b",
        r"\bdormo\b",
        r"\briposo\b",
        r"\bmi riposo\b",
        r"\bpausa pranzo\b",
        r"\bvado a casa\b",
        r"\btorno a casa\b",
    ]
    
    def __init__(self, world: Any, state_manager: Any) -> None:
        """Initialize preprocessor.
        
        Args:
            world: WorldDefinition
            state_manager: StateManager
        """
        self.world = world
        self.state_manager = state_manager
    
    async def preprocess(
        self,
        user_input: str,
        game_state: Any,
        movement_system: Any,
        time_manager: Any,
        phase_manager: Any,
    ) -> PreprocessResult:
        """Main preprocessing entry point.
        
        Checks (in order):
        1. Movement intent
        2. Farewell
        3. Rest/Sleep commands
        4. Freeze/Unfreeze
        5. Schedule queries
        
        Returns:
            PreprocessResult with detection flags
        """
        result = PreprocessResult()
        
        # 1. Check movement
        movement_result = await self._check_movement(
            user_input, game_state, movement_system
        )
        if movement_result:
            return movement_result
        
        # 2. Check farewell
        if self._check_farewell(user_input, game_state):
            result.is_farewell = True
            # Note: farewell handling returns its own result
            return result
        
        # 3. Check rest commands
        rest_msg = self._check_rest_command(user_input, time_manager)
        if rest_msg:
            result.is_rest_command = True
            result.rest_message = rest_msg
            # Rest commands don't stop - they just set a flag
        
        # 4. Check freeze/unfreeze
        freeze_result = self._check_freeze_unfreeze(user_input, phase_manager)
        if freeze_result:
            return freeze_result
        
        # 5. Check schedule queries (e.g., "dove è Luna?")
        schedule_result = self._check_schedule_query(user_input)
        if schedule_result:
            return schedule_result
        
        return result
    
    async def _check_movement(
        self,
        user_input: str,
        game_state: Any,
        movement_system: Any,
    ) -> Optional[PreprocessResult]:
        """Check if user wants to move to a location."""
        if not movement_system:
            return None
        
        from luna.core.models import TurnResult
        
        movement_result = await movement_system.handle_movement(
            user_input, game_state, self.world
        )
        
        if not movement_result:
            return None
        
        result = PreprocessResult()
        result.is_movement = True
        result.movement_target = movement_result.target_location_id
        
        if not movement_result.success:
            # Movement failed
            result.should_stop = True
            result.stop_reason = "movement_failed"
            result.turn_result = TurnResult(
                text=movement_result.error_message or "Non puoi andare lì.",
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
            )
            return result
        
        # Movement successful
        if movement_result.companion_left_behind:
            # Solo mode
            old_char = game_state.active_companion
            self.state_manager.switch_to_solo(game_state)
            
            result.should_stop = True
            result.stop_reason = "movement_success_solo"
            result.turn_result = TurnResult(
                text=f"{movement_result.transition_text}\n\n{movement_result.companion_message}",
                user_input=user_input,
                turn_number=game_state.turn_count,
                switched_character=True,
                previous_character=old_char,
                current_character="_solo_",
                new_location_id=movement_result.target_location_id,
                provider_used="system",
            )
            return result
        
        return None
    
    def _check_farewell(self, user_input: str, game_state: Any) -> bool:
        """Check if user is saying goodbye to current companion."""
        # Simple pattern matching for farewell
        farewell_patterns = [
            r"\bciao\b.*\b(a presto|arrivederci|ci vediamo)\b",
            r"\barrivederci\b",
            r"\bdevo andare\b",
            r"\bmi devo muovere\b",
        ]
        
        text_lower = user_input.lower()
        for pattern in farewell_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _check_rest_command(self, user_input: str, time_manager: Any) -> str:
        """Check for rest/sleep commands that advance time.
        
        Returns:
            Message to display if rest command detected, empty string otherwise
        """
        if not time_manager:
            return ""
        
        text_lower = user_input.lower()
        
        for pattern in self.REST_PATTERNS:
            if re.search(pattern, text_lower):
                # Determine rest type and duration
                if "dormi" in text_lower or "addorment" in text_lower:
                    return time_manager.advance_time("sleep")
                elif "pausa" in text_lower:
                    return time_manager.advance_time("rest")
                else:
                    return time_manager.advance_time("travel")
        
        return ""
    
    def _check_freeze_unfreeze(
        self,
        user_input: str,
        phase_manager: Any,
    ) -> Optional[PreprocessResult]:
        """Check for freeze/unfreeze commands."""
        if not phase_manager:
            return None
        
        from luna.core.models import TurnResult
        
        text_lower = user_input.lower()
        
        # Check freeze
        for cmd in self.FREEZE_COMMANDS:
            if cmd in text_lower:
                phase_manager.freeze_turns("manual")
                
                result = PreprocessResult()
                result.should_stop = True
                result.stop_reason = "freeze_command"
                result.is_freeze_command = True
                result.turn_result = TurnResult(
                    text="⏸️ Turni bloccati. Il tempo non avanza finché non dici 'riprendi'.",
                    user_input=user_input,
                    turn_number=0,  # Will be set by caller
                    provider_used="system",
                )
                return result
        
        # Check unfreeze
        for cmd in self.UNFREEZE_COMMANDS:
            if cmd in text_lower:
                phase_manager.unfreeze_turns()
                remaining = phase_manager.get_remaining_turns()
                
                result = PreprocessResult()
                result.should_stop = True
                result.stop_reason = "unfreeze_command"
                result.turn_result = TurnResult(
                    text=f"▶️ **Turni ripresi!**\n\nIl tempo riprende a scorrere.\nTurni rimanenti in questa fase: {remaining}",
                    user_input=user_input,
                    turn_number=0,
                    provider_used="system",
                )
                return result
        
        return None
    
    def _check_schedule_query(self, user_input: str) -> Optional[PreprocessResult]:
        """Check for schedule queries (e.g., 'dove è Luna?')."""
        # Pattern: "dove è [nome]?" or "routine di [nome]"
        patterns = [
            r"\bdov['eè]\s+(\w+)\b",
            r"\bdove\s+(?:si trova|è)\s+(\w+)\b",
            r"\broutine\s+(?:di|del|della)\s+(\w+)\b",
        ]
        
        text_lower = user_input.lower()
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                npc_name = match.group(1).capitalize()
                # Check if valid NPC
                if npc_name in self.world.companions:
                    # Would need schedule_manager to get actual location
                    # For now, just return a placeholder
                    from luna.core.models import TurnResult
                    
                    result = PreprocessResult()
                    result.should_stop = True
                    result.stop_reason = "schedule_query"
                    result.turn_result = TurnResult(
                        text=f"📍 {npc_name} dovrebbe essere nella sua location abituale per quest'ora.",
                        user_input=user_input,
                        turn_number=0,
                        provider_used="system",
                    )
                    return result
        
        return None
