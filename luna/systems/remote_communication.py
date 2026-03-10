"""Remote Communication System - Handles phone/message conversations with NPCs.

V4.5: New module for remote communication functionality.

Features:
- Detect remote communication patterns ("scrivo a X", "mando messaggio a X", etc.)
- Switch to remote NPC as active companion
- Add context about phone/message conversation to prompts
- Handle return to SOLO mode after conversation ends
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class RemoteCommunicationResult:
    """Result of remote communication detection."""
    is_remote: bool = False
    target_npc: Optional[str] = None
    communication_type: str = "message"  # message, call, text
    should_switch: bool = False
    should_return_solo: bool = False


class RemoteCommunicationHandler:
    """Handles remote (phone/message) communication with NPCs."""
    
    # Patterns that trigger remote communication detection
    COMMUNICATION_PATTERNS = [
        # Writing/Sending messages
        (r'\bscrivo\s+a\b', 'message'),
        (r'\bmando\s+un\s+messaggio\b', 'message'),
        (r'\bmando\s+un\s+sms\b', 'message'),
        (r'\bchatto\s+con\b', 'message'),
        (r'\bwhatsapp\s+a\b', 'message'),
        (r'\bsms\s+a\b', 'message'),
        (r'\bmando\s+un\s+messaggio\s+a\b', 'message'),
        (r'\bscrivo\s+un\s+messaggio\b', 'message'),
        # Calling
        (r'\btelefono\s+a\b', 'call'),
        (r'\bchiamo\b', 'call'),
        (r'\bfaccio\s+una\s+chiamata\b', 'call'),
        # Requesting/Receiving
        (r'\bmandami\b', 'message'),
        (r'\bmandarmi\b', 'message'),
        (r'\bmi\s+mand[ai]\b', 'message'),
        (r'\bchiedo\s+a\b', 'message'),
        (r'\bdire\s+a\b', 'message'),
        (r'\bdici\s+a\b', 'message'),
    ]
    
    # Patterns that end remote conversation and return to SOLO
    FAREWELL_PATTERNS = [
        r'\barrivederci\b',
        r'\bbuonanotte\b',
        r'\ba\s+presto\b',
        r'\bci\s+vediamo\b',
        r'\bscusa\s+devo\s+andare\b',
        r'\bscusa\s+sto\s+uscendo\b',
        r'\bchiudo\b',
        r'\bho\s+finito\b',
    ]
    
    # Acceptance patterns for invitations
    ACCEPTANCE_PATTERNS = [
        r"\bva\s+bene\b",
        r"\bd'accordo\b",
        r"\bci\s+sto\b",
        r"\bok\b",
        r"\bokay\b",
        r"\bsi\b",
        r"\bsì\b",
        r"\bvolentieri\b",
        r"\bcon\s+piacere\b",
        r"\barrivo\b",
        r"\bvengo\b",
        r"\bpasso\b",
        r"\ba\s+presto\b",
        r"\bci\s+vediamo\b",
    ]
    
    def __init__(
        self,
        world,
        npc_detector,
        schedule_manager=None,
    ):
        """Initialize remote communication handler.
        
        Args:
            world: World definition with NPCs and locations
            npc_detector: NPC detector for finding target NPCs
            schedule_manager: Optional schedule manager for NPC locations
        """
        self.world = world
        self.npc_detector = npc_detector
        self.schedule_manager = schedule_manager
    
    def detect_remote_communication(
        self, 
        user_input: str, 
        current_companion: str
    ) -> RemoteCommunicationResult:
        """Detect if user is initiating remote communication.
        
        Args:
            user_input: Player's input text
            current_companion: Currently active companion
            
        Returns:
            RemoteCommunicationResult with detection details
        """
        input_lower = user_input.lower()
        
        # Check for communication patterns
        comm_type = None
        for pattern, comm_type_detected in self.COMMUNICATION_PATTERNS:
            if re.search(pattern, input_lower):
                comm_type = comm_type_detected
                print(f"[RemoteComm] Detected pattern: {pattern} -> type: {comm_type}")
                break
        
        if not comm_type:
            return RemoteCommunicationResult(is_remote=False)
        
        # Find target NPC
        target_npc = self._find_target_npc(input_lower)
        
        if not target_npc:
            print(f"[RemoteComm] Communication pattern detected but no NPC target found")
            return RemoteCommunicationResult(is_remote=False)
        
        # Check if this is ending the conversation
        is_farewell = self._detect_farewell(input_lower)
        
        return RemoteCommunicationResult(
            is_remote=True,
            target_npc=target_npc,
            communication_type=comm_type,
            should_switch=True,
            should_return_solo=is_farewell,
        )
    
    def _find_target_npc(self, user_input: str) -> Optional[str]:
        """Find target NPC name in user input.
        
        Args:
            user_input: Lowercase user input
            
        Returns:
            NPC name or None
        """
        # Get all companion names
        companion_names = list(self.world.companions.keys())
        
        # Check for companion names (case insensitive)
        for name in companion_names:
            # Match whole word only
            pattern = r'\b' + re.escape(name.lower()) + r'\b'
            if re.search(pattern, user_input):
                return name
        
        # Check aliases
        for name, companion in self.world.companions.items():
            if hasattr(companion, 'aliases') and companion.aliases:
                for alias in companion.aliases:
                    pattern = r'\b' + re.escape(alias.lower()) + r'\b'
                    if re.search(pattern, user_input):
                        return name
        
        return None
    
    def _detect_farewell(self, user_input: str) -> bool:
        """Detect if user is ending the conversation."""
        for pattern in self.FAREWELL_PATTERNS:
            if re.search(pattern, user_input):
                return True
        return False
    
    def detect_end_of_conversation(self, user_input: str) -> bool:
        """Public method to detect if user is ending the conversation.
        
        Args:
            user_input: Player's input text
            
        Returns:
            True if farewell detected
        """
        return self._detect_farewell(user_input.lower())
    
    def detect_acceptance(self, npc_response: str) -> bool:
        """Detect if NPC accepted an invitation."""
        response_lower = npc_response.lower()
        for pattern in self.ACCEPTANCE_PATTERNS:
            if re.search(pattern, response_lower):
                return True
        return False
    
    def build_remote_context(
        self,
        target_npc: str,
        player_location: str,
        player_input: str,
        game_state=None
    ) -> str:
        """Build context string for remote conversation.
        
        Args:
            target_npc: Name of NPC being contacted
            player_location: Current player location
            player_input: Original user input
            game_state: Current game state (for schedule lookup)
            
        Returns:
            Context string to add to system prompt
        """
        # Get NPC location and activity (V4.5: uses companion.schedule too)
        npc_location = "sconosciuta"
        npc_activity = ""
        
        if game_state:
            npc_location, npc_activity = self._get_npc_location_and_activity(target_npc, game_state)
        elif self.schedule_manager:
            npc_location = self.schedule_manager.get_npc_current_location(target_npc) or "sconosciuta"
            try:
                npc_state = self.schedule_manager.get_npc_state(target_npc)
                if npc_state and hasattr(npc_state, 'activity'):
                    npc_activity = npc_state.activity
            except:
                pass
        
        context_parts = [
            "",
            "=== COMUNICAZIONE REMOTA (TELEFONO/MESSAGGIO) ===",
            f"📱 Il giocatore ti sta contattando da: {player_location}",
            f"📍 Tu ({target_npc}) sei attualmente a: {npc_location}",
        ]
        
        if npc_activity:
            context_parts.append(f"🎯 Stai facendo: {npc_activity}")
        
        context_parts.extend([
            f"💬 Rispondi come se stessi ricevendo un messaggio/chiamata.",
            f"🎭 Mantieni il tuo carattere anche se sei sorpresa o occupata.",
            "",
        ])
        
        return "\n".join(context_parts)
    
    def _get_npc_location_and_activity(self, target_npc: str, game_state) -> Tuple[str, str]:
        """Get NPC location and activity from schedule or companion definition.
        
        V4.5: Checks both schedule_manager and companion.schedule
        """
        location = None
        activity = None
        
        # Try schedule_manager first (for npc_schedules.yaml)
        if self.schedule_manager:
            location = self.schedule_manager.get_npc_current_location(target_npc)
            print(f"[_get_npc_location] ScheduleManager returned: {location}")
            try:
                npc_state = self.schedule_manager.get_npc_state(target_npc)
                if npc_state:
                    activity = getattr(npc_state, 'activity', None)
            except:
                pass
        
        # If not found, try companion.schedule directly (for modular YAML like luna.yaml)
        print(f"[_get_npc_location] Checking companion.schedule for {target_npc}")
        if not location and target_npc in self.world.companions:
            companion = self.world.companions[target_npc]
            if hasattr(companion, 'schedule') and companion.schedule:
                time_of_day = game_state.time_of_day
                # Handle both string and enum
                if isinstance(time_of_day, str):
                    from luna.core.models import TimeOfDay
                    try:
                        time_of_day = TimeOfDay(time_of_day)
                    except ValueError:
                        time_of_day = TimeOfDay.MORNING
                
                # Get schedule entry
                schedule_entry = companion.schedule.get(time_of_day)
                print(f"[_get_npc_location] Found schedule entry for {time_of_day}: {schedule_entry}")
                if schedule_entry:
                    # Handle both dict and object
                    if isinstance(schedule_entry, dict):
                        location = schedule_entry.get('location')
                        activity = schedule_entry.get('activity')
                    else:
                        location = getattr(schedule_entry, 'location', None)
                        activity = getattr(schedule_entry, 'activity', None)
                    print(f"[_get_npc_location] Extracted from companion.schedule: location={location}, activity={activity}")
        
        print(f"[_get_npc_location] Final result for {target_npc}: location={location}, activity={activity}")
        return location or "sconosciuta", activity or ""
    
    def get_npc_visual_context(self, target_npc: str, game_state) -> Dict[str, Any]:
        """Get visual context for remote NPC image generation.
        
        Args:
            target_npc: Name of NPC
            game_state: Current game state for time
            
        Returns:
            Dict with visual context for image generation
        """
        location, activity = self._get_npc_location_and_activity(target_npc, game_state)
        
        return {
            'location': location,
            'activity': activity,
            'outfit': None,
        }


def is_remote_communication_input(user_input: str) -> bool:
    """Quick check if input is remote communication (for external use).
    
    Args:
        user_input: Player's input text
        
    Returns:
        True if remote communication detected
    """
    input_lower = user_input.lower()
    
    patterns = [
        r'\bscrivo\s+a\b',
        r'\bmando\s+un\s+messaggio\b',
        r'\bmando\s+un\s+sms\b',
        r'\bchatto\s+con\b',
        r'\bwhatsapp\s+a\b',
        r'\bsms\s+a\b',
        r'\btelefono\s+a\b',
        r'\bchiamo\b',
        r'\bmandami\b',
        r'\bmandarmi\b',
        r'\bmi\s+mand[ai]\b',
    ]
    
    for pattern in patterns:
        if re.search(pattern, input_lower):
            return True
    
    return False
