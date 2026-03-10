"""Invitation Manager - Handles NPC invitations to player's home.

V4.5: New module for managing NPC invitations via message/chat.

Features:
- Register invitations with scheduled arrival time
- Track accepted invitations
- Trigger arrival events when time comes
- Generate narrative messages when NPCs arrive
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PendingInvitation:
    """An invitation sent to an NPC."""
    npc_name: str
    invited_at_turn: int
    arrival_time: str  # "evening", "night", "afternoon", etc.
    arrived: bool = False
    

class InvitationManager:
    """Manages invitations to player's home."""
    
    # Time keywords in invitations
    TIME_PATTERNS = {
        "morning": [r'\bmattina\b', r'\bstamattina\b', r'\bdomani\s+mattina\b'],
        "afternoon": [r'\bpomeriggio\b', r'\bsta\s+pomeriggio\b', r'\bdomani\s+pomeriggio\b'],
        "evening": [r'\bsera\b', r'\bstasera\b', r'\bquesta\s+sera\b', r'\bsta\s+sera\b'],
        "night": [r'\bnotte\b', r'\bstanotte\b', r'\bquesta\s+notte\b'],
    }
    
    def __init__(self, state_manager: Any, world: Any, schedule_manager: Optional[Any] = None):
        """Initialize invitation manager.
        
        Args:
            state_manager: For accessing game state
            world: World definition
            schedule_manager: For NPC locations
        """
        self.state_manager = state_manager
        self.world = world
        self.schedule_manager = schedule_manager
        self._pending_invitations: Dict[str, PendingInvitation] = {}
    
    def detect_invitation_intent(self, user_input: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Detect if user is inviting an NPC to their home.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Tuple of (is_invitation, target_npc, arrival_time)
        """
        input_lower = user_input.lower()
        
        # Check for invitation patterns
        invitation_patterns = [
            r'\bvieni\s+a\s+casa\b',
            r'\bvieni\s+da\s+me\b',
            r'\bvieni\s+a\s+casa\s+mia\b',
            r'\bperche\s+non\s+vieni\b',
            r'\bpassa\s+a\s+casa\b',
            r'\bvenire\s+a\s+casa\b',
            r'\bti\s+aspetto\s+a\s+casa\b',
            r'\bvieni\s+stasera\b',
            r'\bvieni\s+questa\s+sera\b',
            r'\bvieni\s+oggi\b',
            r'\bvieni\s+domani\b',
        ]
        
        is_invitation = any(re.search(p, input_lower) for p in invitation_patterns)
        
        if not is_invitation:
            return False, None, None
        
        # Find target NPC
        target_npc = self._find_target_npc(input_lower)
        
        # Determine arrival time
        arrival_time = self._detect_arrival_time(input_lower)
        
        return True, target_npc, arrival_time
    
    def register_invitation(
        self, 
        npc_name: str, 
        current_turn: int,
        arrival_time: Optional[str] = None
    ) -> bool:
        """Register an invitation for an NPC.
        
        Args:
            npc_name: Name of invited NPC
            current_turn: Current game turn
            arrival_time: When they should arrive (default: next evening)
            
        Returns:
            True if registered successfully
        """
        if not arrival_time:
            arrival_time = "evening"  # Default to evening
        
        invitation = PendingInvitation(
            npc_name=npc_name,
            invited_at_turn=current_turn,
            arrival_time=arrival_time,
            arrived=False
        )
        
        self._pending_invitations[npc_name] = invitation
        print(f"[InvitationManager] Registered invitation for {npc_name} at {arrival_time}")
        return True
    
    def check_arrivals(
        self, 
        current_time: str, 
        player_location: str
    ) -> List[PendingInvitation]:
        """Check if any invited NPCs should arrive now.
        
        Args:
            current_time: Current time of day (morning, afternoon, evening, night)
            player_location: Current player location
            
        Returns:
            List of NPCs arriving now
        """
        arrivals = []
        
        # Only process arrivals if player is at home
        if player_location != "player_home":
            return arrivals
        
        for npc_name, invitation in list(self._pending_invitations.items()):
            if invitation.arrived:
                continue
            
            # Check if it's time for arrival
            if invitation.arrival_time == current_time:
                invitation.arrived = True
                arrivals.append(invitation)
                print(f"[InvitationManager] {npc_name} arrives at player's home")
        
        return arrivals
    
    def build_arrival_message(self, invitation: PendingInvitation) -> str:
        """Build narrative message for NPC arrival.
        
        Args:
            invitation: The pending invitation
            
        Returns:
            Narrative text
        """
        npc_name = invitation.npc_name
        
        # Get NPC definition for gender/role
        npc_def = self.world.companions.get(npc_name)
        article = "la" if npc_def and getattr(npc_def, 'gender', 'female') == 'female' else "il"
        
        # Build message based on time
        time_context = {
            "morning": "mentre ti prepari per la giornata",
            "afternoon": "mentre riposi nel pomeriggio", 
            "evening": "mentre ti rilassi in salotto",
            "night": "quando stai per andare a dormire"
        }
        
        context = time_context.get(invitation.arrival_time, "")
        
        message = f"\n\n*{context.capitalize() if context else 'Improvvisamente'}, senti suonare il campanello. Aprendo la porta, trovi {article} {npc_name} che è venut{'a' if article == 'la' else 'o'} come promesso.*"
        
        return message
    
    def clear_arrived_invitations(self):
        """Clear invitations that have been processed."""
        to_remove = [
            name for name, inv in self._pending_invitations.items() 
            if inv.arrived
        ]
        for name in to_remove:
            del self._pending_invitations[name]
    
    def _find_target_npc(self, input_lower: str) -> Optional[str]:
        """Find target NPC in user input."""
        for name in self.world.companions.keys():
            name_lower = name.lower()
            if re.search(r'\b' + re.escape(name_lower) + r'\b', input_lower):
                companion = self.world.companions[name]
                if not getattr(companion, 'is_temporary', False):
                    return name
        return None
    
    def _detect_arrival_time(self, input_lower: str) -> Optional[str]:
        """Detect when the NPC should arrive from user input."""
        for time_key, patterns in self.TIME_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, input_lower):
                    return time_key
        return "evening"  # Default
    
    def get_pending_invitations(self) -> Dict[str, PendingInvitation]:
        """Get all pending invitations."""
        return {k: v for k, v in self._pending_invitations.items() if not v.arrived}
