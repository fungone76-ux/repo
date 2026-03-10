"""Situational Interventions System - NPCs react proactively to situations.

V4.3 FEATURE: Allows NPCs to intervene based on context without player explicitly
addressing them. Examples:
- Teacher catching you talking in class
- Guard catching you sneaking
- Parent catching misbehavior
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from luna.core.models import GameState
    from luna.core.engine import GameEngine


class SituationType(Enum):
    """Types of situations that can trigger interventions."""
    TALKING_IN_CLASS = "talking_in_class"
    SNEAKING = "sneaking"
    CHEATING = "cheating"
    BEING_LATE = "being_late"
    INAPPROPRIATE_BEHAVIOR = "inappropriate_behavior"


@dataclass
class SituationalTrigger:
    """A trigger condition for situational intervention."""
    situation_type: SituationType
    location_patterns: List[str]
    behavior_patterns: List[str]
    required_roles: List[str]
    priority: int = 1  # Higher = checked first


class SituationalInterventionSystem:
    """System for proactive NPC interventions based on context."""
    
    def __init__(self, engine: GameEngine, world, state_manager, 
                 multi_npc_manager, llm_manager, state_memory):
        """Initialize the situational intervention system.
        
        Args:
            engine: GameEngine reference
            world: World definition
            state_manager: State manager
            multi_npc_manager: Multi-NPC manager
            llm_manager: LLM manager for generating responses
            state_memory: State memory manager
        """
        self.engine = engine
        self.world = world
        self.state_manager = state_manager
        self.multi_npc_manager = multi_npc_manager
        self.llm_manager = llm_manager
        self.state_memory = state_memory
        
        # Define situational triggers
        self._triggers = self._setup_triggers()
    
    def _setup_triggers(self) -> List[SituationalTrigger]:
        """Setup all situational triggers."""
        return [
            # Teacher catching talking in class
            SituationalTrigger(
                situation_type=SituationType.TALKING_IN_CLASS,
                location_patterns=[
                    "classroom", "aula", "classe", "school_classroom",
                    "school_office_luna", "ufficio_luna", "laboratorio"
                ],
                behavior_patterns=[
                    r"\b(parlo\s+con|discuto\s+con|chiacchiero\s+con|sussurro\s+a)\b",
                    r"\b(guardo\s+stella|guardo\s+luna|osservo\s+la\s+classe)\b",
                    r"\b(rido|sorriso|sghignazzo|ridacchio)\b",
                    r"\b(passo\s+un\s+biglietto|bigliettino|messaggio\s+a)\b",
                    r"\b(distratto|non\s+ascolto|ignoro\s+la\s+lezione)\b",
                ],
                required_roles=["teacher", "professoressa", "professore", "instructor"],
                priority=10,
            ),
            # Add more triggers here as needed
        ]
    
    async def check_and_intervene(
        self,
        user_input: str,
        game_state: GameState,
    ) -> Optional[Any]:  # Returns TurnResult or None
        """Check if any NPC should intervene and generate response.
        
        Args:
            user_input: Player's input text
            game_state: Current game state
            
        Returns:
            TurnResult if intervention triggered, None otherwise
        """
        text_lower = user_input.lower()
        current_location = game_state.current_location
        
        # Get present NPCs
        present_npcs = self._get_present_npcs(game_state, user_input)
        
        # Check each trigger
        for trigger in sorted(self._triggers, key=lambda t: t.priority, reverse=True):
            if self._matches_trigger(trigger, text_lower, current_location):
                # Find appropriate NPC to intervene
                intervener = self._find_intervener(
                    trigger.required_roles, 
                    present_npcs, 
                    game_state.active_companion
                )
                
                if intervener:
                    print(f"[Situational] {intervener} intervenes for {trigger.situation_type.value}")
                    return await self._generate_intervention(
                        game_state,
                        trigger.situation_type,
                        intervener,
                        user_input
                    )
        
        return None
    
    def _matches_trigger(
        self, 
        trigger: SituationalTrigger, 
        text: str, 
        location: str
    ) -> bool:
        """Check if current situation matches a trigger.
        
        Args:
            trigger: The trigger to check
            text: Lowercase user input
            location: Current location
            
        Returns:
            True if matches
        """
        # Check location
        location_match = any(
            pat in location.lower() for pat in trigger.location_patterns
        )
        if not location_match:
            return False
        
        # Check behavior patterns
        behavior_match = any(
            re.search(pat, text) for pat in trigger.behavior_patterns
        )
        
        return behavior_match
    
    def _get_present_npcs(self, game_state: GameState, user_input: str) -> List[str]:
        """Get NPCs present at current location."""
        # Use multi_npc_manager if available
        if self.multi_npc_manager:
            # Get from multi_npc_manager
            all_npcs = self.multi_npc_manager.get_present_npcs(
                game_state.active_companion,
                game_state
            )
            # Filter by location
            return [npc for npc in all_npcs if npc != "_solo_"]
        return []
    
    def _find_intervener(
        self,
        required_roles: List[str],
        present_npcs: List[str],
        active_companion: str
    ) -> Optional[str]:
        """Find an NPC with appropriate role to intervene.
        
        Args:
            required_roles: List of acceptable roles
            present_npcs: NPCs present at location
            active_companion: Currently active companion
            
        Returns:
            Name of intervener or None
        """
        # Check present NPCs first
        for npc_name in present_npcs:
            npc_def = self.world.companions.get(npc_name)
            if npc_def and npc_def.role:
                if npc_def.role.lower() in required_roles:
                    return npc_name
        
        # Check active companion
        active_def = self.world.companions.get(active_companion)
        if active_def and active_def.role:
            if active_def.role.lower() in required_roles:
                return active_companion
        
        return None
    
    async def _generate_intervention(
        self,
        game_state: GameState,
        situation_type: SituationType,
        intervener: str,
        context: str,
    ) -> Optional[Any]:  # TurnResult
        """Generate intervention response.
        
        Args:
            game_state: Current game state
            situation_type: Type of situation
            intervener: Name of intervening NPC
            context: User input that triggered this
            
        Returns:
            TurnResult with intervention
        """
        from luna.core.models import TurnResult
        
        npc_def = self.world.companions.get(intervener)
        if not npc_def:
            return None
        
        # Build prompt based on situation
        prompts = {
            SituationType.TALKING_IN_CLASS: f"""Sei {intervener}, {npc_def.base_personality[:200]}...

SITUAZIONE: Hai appena notato che uno studente sta parlando/chiacchierando durante la tua lezione invece di ascoltare.

COMPORTAMENTO RICHIESTO:
- Sei severa, autoritaria, professionale
- Non tolleri mancanze di rispetto
- Interrompi la conversazione dello studente
- Puoi essere sarcastica o intimidatoria
- Minaccia conseguenze se necessario
- Vuoi ristabilire l'ordine

RISPONDI come se stessi parlando direttamente allo studente. Usa *azioni* tra asterischi.

FORMATTAMENTO JSON:
{{
    "text": "Il tuo dialogo severo qui con *azioni*",
    "visual_en": "descrizione inglese per l'immagine",
    "tags_en": ["tag1", "tag2"]
}}""",
        }
        
        system_prompt = prompts.get(
            situation_type,
            f"Sei {intervener}. Intervieni in una situazione inappropriata."
        )
        
        try:
            # Generate response
            llm_response = await self.llm_manager.generate(
                system_prompt=system_prompt,
                user_input=f"Lo studente ha appena fatto: '{context}'",
                history=[],
                json_mode=True,
            )
            
            response_text = getattr(llm_response, 'text', '') or getattr(llm_response, 'raw_response', '')
            
            if response_text:
                # Format with dramatic header
                full_text = f"**{intervener} ti interrompe improvvisamente:**\n\n{response_text}"
                
                # Switch to intervener
                old_companion = game_state.active_companion
                switched = intervener != old_companion
                
                if switched:
                    self.state_manager.switch_companion(intervener)
                    self.engine.companion = intervener
                
                # Save to memory
                await self.state_memory.add_message(
                    role="user",
                    content=context,
                    turn_number=game_state.turn_count,
                )
                await self.state_memory.add_message(
                    role="assistant",
                    content=response_text,
                    turn_number=game_state.turn_count,
                    visual_en=getattr(llm_response, 'visual_en', ''),
                    tags_en=getattr(llm_response, 'tags_en', []),
                )
                
                # Advance and save
                self.state_manager.advance_turn()
                await self.state_memory.save_all()
                
                # Build result
                return TurnResult(
                    text=full_text,
                    user_input=context,
                    turn_number=game_state.turn_count,
                    provider_used="situational_intervention",
                    switched_companion=switched,
                    previous_companion=old_companion if switched else None,
                    current_companion=intervener,
                )
                
        except Exception as e:
            print(f"[Situational] Error generating intervention: {e}")
            import traceback
            traceback.print_exc()
        
        return None
