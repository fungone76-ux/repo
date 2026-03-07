"""State Updater - Handles game state updates after LLM response.

V4.3 REFACTOR: Extracted from engine.py
Handles: affinity changes, outfit updates, location changes, flag setting, quest updates.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UpdateSummary:
    """Summary of state updates applied."""
    affinity_changes: Dict[str, int]
    outfit_changed: bool
    location_changed: bool
    flags_set: List[str]
    quest_triggered: bool
    errors: List[str]


class StateUpdater:
    """Updates game state based on LLM response updates."""
    
    def __init__(
        self,
        state_manager: Any,
        affinity_calculator: Any,
        outfit_modifier: Any,
        quest_engine: Any,
        personality_engine: Any,
    ) -> None:
        """Initialize state updater.
        
        Args:
            state_manager: For state persistence
            affinity_calculator: For calculating affinity changes
            outfit_modifier: For outfit updates
            quest_engine: For quest progression
            personality_engine: For personality updates
        """
        self.state_manager = state_manager
        self.affinity_calculator = affinity_calculator
        self.outfit_modifier = outfit_modifier
        self.quest_engine = quest_engine
        self.personality_engine = personality_engine
    
    def apply_updates(
        self,
        game_state: Any,
        updates: Dict[str, Any],
        companion_name: str,
        user_input: str,
        llm_text: str,
    ) -> UpdateSummary:
        """Apply all updates from LLM response.
        
        Args:
            game_state: Current game state
            updates: Updates dict from LLM response
            companion_name: Active companion name
            user_input: Original user input
            llm_text: LLM response text
            
        Returns:
            UpdateSummary of all changes
        """
        summary = UpdateSummary(
            affinity_changes={},
            outfit_changed=False,
            location_changed=False,
            flags_set=[],
            quest_triggered=False,
            errors=[],
        )
        
        if not updates:
            return summary
        
        # 1. Update affinity
        try:
            affinity_change = self._update_affinity(
                game_state, companion_name, user_input, llm_text, updates
            )
            if affinity_change:
                summary.affinity_changes[companion_name] = affinity_change
        except Exception as e:
            summary.errors.append(f"Affinity update failed: {e}")
            logger.error(f"[StateUpdater] Affinity update error: {e}")
        
        # 2. Update outfit
        try:
            outfit_changed = self._update_outfit(
                game_state, companion_name, updates
            )
            summary.outfit_changed = outfit_changed
        except Exception as e:
            summary.errors.append(f"Outfit update failed: {e}")
            logger.error(f"[StateUpdater] Outfit update error: {e}")
        
        # 3. Update location
        try:
            location_changed = self._update_location(game_state, updates)
            summary.location_changed = location_changed
        except Exception as e:
            summary.errors.append(f"Location update failed: {e}")
            logger.error(f"[StateUpdater] Location update error: {e}")
        
        # 4. Set flags
        try:
            flags = self._set_flags(game_state, updates)
            summary.flags_set = flags
        except Exception as e:
            summary.errors.append(f"Flag update failed: {e}")
            logger.error(f"[StateUpdater] Flag update error: {e}")
        
        # 5. Update quests
        try:
            quest_triggered = self._update_quests(game_state, companion_name)
            summary.quest_triggered = quest_triggered
        except Exception as e:
            summary.errors.append(f"Quest update failed: {e}")
            logger.error(f"[StateUpdater] Quest update error: {e}")
        
        # 6. Update personality
        try:
            self._update_personality(
                game_state, companion_name, user_input, llm_text
            )
        except Exception as e:
            summary.errors.append(f"Personality update failed: {e}")
            logger.error(f"[StateUpdater] Personality update error: {e}")
        
        return summary
    
    def _update_affinity(
        self,
        game_state: Any,
        companion_name: str,
        user_input: str,
        llm_text: str,
        updates: Dict[str, Any],
    ) -> int:
        """Calculate and apply affinity change.
        
        Returns:
            Actual affinity change applied
        """
        # Get suggested change from LLM
        suggested_change = updates.get("affinity_change", {}).get(companion_name, 0)
        
        # Use calculator for deterministic calculation
        calculated_change = self.affinity_calculator.calculate(
            user_input=user_input,
            response_text=llm_text,
            current_affinity=game_state.affinity.get(companion_name, 0),
            suggested_change=suggested_change,
        )
        
        # Apply change
        old_affinity = game_state.affinity.get(companion_name, 0)
        new_affinity = max(0, min(100, old_affinity + calculated_change))
        game_state.affinity[companion_name] = new_affinity
        
        actual_change = new_affinity - old_affinity
        
        logger.debug(
            f"[StateUpdater] Affinity: {companion_name} {old_affinity} -> {new_affinity} "
            f"(change: {actual_change})"
        )
        
        return actual_change
    
    def _update_outfit(
        self,
        game_state: Any,
        companion_name: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Update outfit if changed.
        
        Returns:
            True if outfit was changed
        """
        outfit_update = updates.get("current_outfit")
        if not outfit_update:
            return False
        
        # Get current outfit
        current = game_state.companion_outfits.get(companion_name)
        if current:
            from luna.core.models import OutfitState
            
            if isinstance(outfit_update, str):
                # Simple string update
                if outfit_update != current.style:
                    current.style = outfit_update
                    current.description = outfit_update
                    logger.info(f"[StateUpdater] Outfit changed: {companion_name} -> {outfit_update}")
                    return True
            elif isinstance(outfit_update, dict):
                # Dict update
                if outfit_update.get("style") != current.style:
                    current.style = outfit_update.get("style", current.style)
                    current.description = outfit_update.get("description", current.description)
                    logger.info(f"[StateUpdater] Outfit changed: {companion_name} -> {current.style}")
                    return True
        
        return False
    
    def _update_location(
        self,
        game_state: Any,
        updates: Dict[str, Any],
    ) -> bool:
        """Update location if changed.
        
        Returns:
            True if location was changed
        """
        new_location = updates.get("location")
        if not new_location:
            return False
        
        if new_location != game_state.current_location:
            old_location = game_state.current_location
            game_state.current_location = new_location
            logger.info(f"[StateUpdater] Location: {old_location} -> {new_location}")
            return True
        
        return False
    
    def _set_flags(
        self,
        game_state: Any,
        updates: Dict[str, Any],
    ) -> List[str]:
        """Set flags from updates.
        
        Returns:
            List of flags that were set
        """
        flags = updates.get("set_flags", {})
        if not flags:
            return []
        
        set_flags = []
        for flag_name, flag_value in flags.items():
            game_state.flags[flag_name] = flag_value
            set_flags.append(flag_name)
            logger.debug(f"[StateUpdater] Flag set: {flag_name} = {flag_value}")
        
        return set_flags
    
    def _update_quests(
        self,
        game_state: Any,
        companion_name: str,
    ) -> bool:
        """Check and update quest progress.
        
        Returns:
            True if a quest was triggered or advanced
        """
        if not self.quest_engine:
            return False
        
        # Check for quest activation
        triggered = self.quest_engine.check_quest_triggers(
            game_state, companion_name
        )
        
        if triggered:
            logger.info(f"[StateUpdater] Quest triggered for {companion_name}")
            return True
        
        return False
    
    def _update_personality(
        self,
        game_state: Any,
        companion_name: str,
        user_input: str,
        llm_text: str,
    ) -> None:
        """Update personality based on interaction."""
        if not self.personality_engine:
            return
        
        # Skip for temporary NPCs
        companion = game_state.npc_states.get(companion_name)
        if companion and getattr(companion, 'is_temporary', False):
            return
        
        # Update personality (fire-and-forget for LLM analysis)
        self.personality_engine.update_from_interaction(
            companion_name,
            user_input,
            llm_text,
            game_state.turn_count,
        )
