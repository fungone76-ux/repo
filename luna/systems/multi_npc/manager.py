"""Multi-NPC Manager - Main coordinator for multi-NPC interactions.

This is the main entry point for the multi-NPC dialogue system.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from luna.core.models import WorldDefinition
    from luna.systems.personality import PersonalityEngine

from luna.systems.multi_npc.interaction_rules import (
    InteractionRuleset,
    InteractionType,
    InteractionRule,
)
from luna.systems.multi_npc.dialogue_sequence import (
    DialogueSequence,
    DialogueTurn,
    SpeakerType,
)


class MultiNPCManager:
    """Manages multi-NPC dialogue interactions.
    
    Coordinates when and how secondary NPCs intervene in conversations,
    respecting relationship dynamics and configuration settings.
    
    CRITICAL: Multi-NPC triggers are now CONSERVATIVE:
    - Player must have affinity >= 20 with secondary NPC
    - NPC relationship must be extreme (strong friends or enemies)
    - Cooldown between interventions (same NPC can't interrupt twice in a row)
    - Player must mention NPC or have strong bond
    
    Attributes:
        world: World definition for NPC data
        personality_engine: For accessing NPC relationships
        enabled: Global toggle for the system
        ruleset: Rules for determining interactions
    """
    
    # Minimum affinity player must have with secondary NPC for them to intervene
    MIN_PLAYER_AFFINITY = 20
    
    # Cooldown: NPC can't intervene again for this many turns after intervening
    INTERVENTION_COOLDOWN = 3
    
    def __init__(
        self,
        world: Optional["WorldDefinition"] = None,
        personality_engine: Optional["PersonalityEngine"] = None,
        enabled: bool = True,
    ):
        """Initialize the multi-NPC manager.
        
        Args:
            world: World definition containing NPC data
            personality_engine: Personality engine for relationship data
            enabled: Global toggle for the system
        """
        self.world = world
        self.personality_engine = personality_engine
        self.enabled = enabled
        self.ruleset = InteractionRuleset()
        
        # Track interventions per turn to enforce limits
        self._intervention_counts: Dict[str, int] = {}
        
        # Track last intervention turn per NPC for cooldown
        self._last_intervention_turn: Dict[str, int] = {}
    
    def is_enabled_for_scene(
        self,
        game_state: Optional[Any] = None,
        active_npc: Optional[str] = None,
    ) -> bool:
        """Check if multi-NPC is enabled for current scene.
        
        Checks multiple levels:
        1. Global enabled flag
        2. Scene flag (disable_multi_npc)
        3. Per-NPC setting (allow_multi_npc_interrupts)
        
        Args:
            game_state: Current game state for flag checking
            active_npc: Currently active NPC name
            
        Returns:
            True if multi-NPC interactions are enabled
        """
        # Global toggle
        if not self.enabled:
            return False
        
        # Scene flag check
        if game_state and hasattr(game_state, 'flags'):
            if game_state.flags.get("disable_multi_npc", False):
                return False
        
        # Per-NPC check
        if active_npc and self.world:
            companion = self.world.companions.get(active_npc)
            if companion:
                allow = getattr(companion, 'allow_multi_npc_interrupts', True)
                if not allow:
                    return False
        
        return True
    
    def get_present_npcs(
        self,
        active_npc: str,
        game_state: Optional[Any] = None,
    ) -> List[str]:
        """Get list of NPCs present in the current scene.
        
        For now, returns all companions in world except active.
        Future: Filter by location/schedule.
        
        Args:
            active_npc: Currently active NPC
            game_state: Current game state
            
        Returns:
            List of NPC names present
        """
        if not self.world:
            return []
        
        # Get all companions except active
        all_npcs = list(self.world.companions.keys())
        present = [n for n in all_npcs if n != active_npc]
        
        # TODO: Filter by location if game_state has location data
        # TODO: Check NPC schedule (only present if following player or at same location)
        
        return present
    
    def check_intervention(
        self,
        active_npc: str,
        secondary_npc: str,
    ) -> Optional[InteractionType]:
        """Check if a secondary NPC should intervene.
        
        Args:
            active_npc: NPC currently speaking
            secondary_npc: NPC that might intervene
            
        Returns:
            InteractionType or None if no intervention
        """
        if not self.personality_engine:
            return None
        
        # Get relationship from personality engine
        state = self.personality_engine._ensure_state(secondary_npc)
        links = state.npc_links.get(active_npc, {})
        rapport = links.get("rapport", 0) if isinstance(links, dict) else 0
        
        # Get current intervention count for this turn
        count = self._intervention_counts.get(secondary_npc, 0)
        
        return self.ruleset.check_interaction(rapport, count)
    
    def process_turn(
        self,
        player_input: str,
        active_npc: str,
        present_npcs: Optional[List[str]] = None,
        game_state: Optional[Any] = None,
    ) -> Optional[DialogueSequence]:
        """Process a player turn and determine if multi-NPC interaction occurs.
        
        This is the main entry point. Returns a DialogueSequence if multi-NPC
        interaction should happen, or None if standard single-NPC flow.
        
        Args:
            player_input: Player's input text
            active_npc: NPC player is addressing
            present_npcs: List of other NPCs present (auto-detected if None)
            game_state: Current game state
            
        Returns:
            DialogueSequence with interaction plan, or None
        """
        # Check if enabled
        if not self.is_enabled_for_scene(game_state, active_npc):
            return None
        
        # Reset intervention counts for new turn
        self._intervention_counts = {}
        
        # Get present NPCs
        if present_npcs is None:
            present_npcs = self.get_present_npcs(active_npc, game_state)
        
        if not present_npcs:
            return None
        
        # Filter NPCs by location - only NPCs at same location as player
        # For early game, this prevents all NPCs from being "present"
        if game_state and hasattr(game_state, 'current_location'):
            current_location = game_state.current_location
            # Only include NPCs that are either:
            # 1. Following the player, or
            # 2. At the same location according to their schedule
            filtered_npcs = []
            for npc_name in present_npcs:
                companion = self.world.companions.get(npc_name) if self.world else None
                if companion and hasattr(companion, 'schedule'):
                    # Check if NPC would be at this location based on schedule
                    from luna.core.models import TimeOfDay
                    time_of_day = game_state.time_of_day
                    if isinstance(time_of_day, TimeOfDay):
                        time_key = time_of_day.value
                    else:
                        time_key = str(time_of_day)
                    
                    schedule = companion.schedule
                    time_enum = TimeOfDay(time_key) if isinstance(time_key, str) else time_key
                    if time_enum in schedule:
                        schedule_entry = schedule[time_enum]
                        npc_location = schedule_entry.location if schedule_entry else ''
                        # Check if NPC is at same location or following player
                        if npc_location == current_location:
                            filtered_npcs.append(npc_name)
                        # Also check if NPC is explicitly following (in flags)
                        elif hasattr(game_state, 'flags') and game_state.flags.get(f'{npc_name}_following', False):
                            filtered_npcs.append(npc_name)
                else:
                    # If no schedule, don't include (conservative approach)
                    pass
            present_npcs = filtered_npcs
        
        if not present_npcs:
            return None
        
        # Check which NPCs might intervene
        # ADDITIONAL CONSTRAINTS for conservative triggering:
        # 1. Player must have min affinity with secondary NPC
        # 2. Player must mention the NPC OR have high affinity
        # 3. NPC must not be on cooldown
        
        potential_candidates = []
        player_input_lower = player_input.lower()
        current_turn = getattr(game_state, 'turn_count', 0)
        
        for npc_name in present_npcs:
            if npc_name == active_npc:
                continue
            
            # Check cooldown
            last_turn = self._last_intervention_turn.get(npc_name, -999)
            if current_turn - last_turn < self.INTERVENTION_COOLDOWN:
                print(f"[MultiNPC] {npc_name} on cooldown ({current_turn - last_turn} turns)")
                continue
            
            # Check player affinity with this NPC
            player_affinity = 0
            if self.personality_engine and game_state:
                state = self.personality_engine._ensure_state(npc_name)
                # Get average of trust and attraction as "bond"
                player_affinity = (state.impression.trust + state.impression.attraction) / 2
            
            # Check if player mentioned this NPC
            is_mentioned = npc_name.lower() in player_input_lower
            
            # NPC can intervene if:
            # - Player mentioned them explicitly, OR
            # - Player has sufficient affinity (knows them well)
            if not is_mentioned and player_affinity < self.MIN_PLAYER_AFFINITY:
                print(f"[MultiNPC] {npc_name} skipped: not mentioned and affinity {player_affinity:.0f} < {self.MIN_PLAYER_AFFINITY}")
                continue
            
            potential_candidates.append(npc_name)
        
        if not potential_candidates:
            return None
        
        # Now check relationships between these candidates and active NPC
        candidates = self.ruleset.get_npcs_that_might_intervene(
            active_npc,
            potential_candidates,
            {
                npc: self.personality_engine._ensure_state(npc).npc_links
                for npc in potential_candidates
                if self.personality_engine
            } if self.personality_engine else {},
        )
        
        if not candidates:
            return None
        
        # Build sequence - only take the most likely intervener (first in sorted list)
        # Max 1 intervention per sequence (total 3 turns: active, secondary, active)
        sequence = DialogueSequence(
            player_input=player_input,
            active_npc=active_npc,
        )
        
        # First turn: Active NPC responds to player (foreground focus)
        sequence.add_turn(DialogueTurn(
            speaker=active_npc,
            speaker_type=SpeakerType.ACTIVE_NPC,
            focus_position="foreground",  # Active NPC in focus
        ))
        
        # Second turn: Secondary NPC intervention (if qualifies)
        if candidates and sequence.can_add_intervention():
            npc_name, interaction_type, rapport = candidates[0]
            
            sequence.add_turn(DialogueTurn(
                speaker=npc_name,
                speaker_type=SpeakerType.SECONDARY_NPC,
                interaction_type=interaction_type,
                target_npc=active_npc,
                focus_position="foreground",  # Secondary NPC now in focus
            ))
            
            # Track intervention
            self._intervention_counts[npc_name] = 1
            
            # Track cooldown
            current_turn = getattr(game_state, 'turn_count', 0)
            self._last_intervention_turn[npc_name] = current_turn
            print(f"[MultiNPC] {npc_name} intervenes (cooldown starts, turn {current_turn})")
            
            # Third turn: Active NPC responds to intervention (back to focus)
            sequence.add_turn(DialogueTurn(
                speaker=active_npc,
                speaker_type=SpeakerType.ACTIVE_NPC,
                is_final=True,
                focus_position="foreground",  # Back to active NPC
            ))
        
        return sequence
    
    def format_prompt_for_llm(
        self,
        sequence: DialogueSequence,
        npc_personalities: Dict[str, str],
    ) -> str:
        """Format a prompt section for the LLM explaining multi-NPC context.
        
        Args:
            sequence: Dialogue sequence with planned interactions
            npc_personalities: Dict of npc_name -> personality description
            
        Returns:
            Formatted prompt section
        """
        lines = [
            "=== MULTI-NPC SCENE ===",
            f"Active: {sequence.active_npc}",
            "Present:",
        ]
        
        for turn in sequence.turns:
            if turn.speaker_type == SpeakerType.SECONDARY_NPC:
                lines.append(f"  - {turn.speaker} ({turn.interaction_type.name})")
                
                if turn.speaker in npc_personalities:
                    lines.append(f"    Personality: {npc_personalities[turn.speaker]}")
        
        lines.extend([
            "",
            "INSTRUCTIONS:",
            "1. First, respond as the Active NPC to the player",
        ])
        
        if any(t.speaker_type == SpeakerType.SECONDARY_NPC for t in sequence.turns):
            lines.extend([
                "2. Then, have the Secondary NPC interrupt/react",
                "3. Finally, have the Active NPC respond to the interruption",
            ])
        
        lines.append("4. Use character names in dialogue tags for clarity")
        
        return "\n".join(lines)

    def prepare_characters_for_builder(
        self,
        turn: DialogueTurn,
        all_present_npcs: List[str],
        outfit_data: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Prepare character list for MultiCharacterBuilder.
        
        Creates position mapping where the speaking NPC is in foreground
        and others are positioned in background.
        
        Args:
            turn: Current dialogue turn
            all_present_npcs: All NPCs present in scene
            outfit_data: Dict of npc_name -> outfit info
            
        Returns:
            List of character dicts for MultiCharacterBuilder
        """
        characters = []
        speaker = turn.speaker
        
        # Define position based on focus
        # Speaker always in foreground/center
        # Others distributed in background
        positions = {
            "foreground": "center foreground",
            "center": "center",
            "background": "background",
        }
        
        # Background positions for non-speakers
        bg_positions = ["left background", "right background", "far background"]
        bg_idx = 0
        
        for npc in all_present_npcs:
            if npc == speaker:
                # Speaker gets focus position
                position = positions.get(turn.focus_position, "center")
            else:
                # Non-speakers get background positions
                position = bg_positions[bg_idx % len(bg_positions)]
                bg_idx += 1
            
            # Get base prompt from world
            base_prompt = ""
            if self.world and npc in self.world.companions:
                companion = self.world.companions[npc]
                base_prompt = getattr(companion, 'base_prompt', '')
            
            # Get outfit
            outfit = outfit_data.get(npc, {})
            outfit_desc = outfit.get('description', '') if isinstance(outfit, dict) else str(outfit)
            
            characters.append({
                'name': npc,
                'position': position,
                'outfit': outfit_desc,
                'base_prompt': base_prompt,
            })
        
        return characters
