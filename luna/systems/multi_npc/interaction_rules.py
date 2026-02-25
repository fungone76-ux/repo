"""Interaction rules for Multi-NPC system.

Defines when and how NPCs interact with each other based on their relationships.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Any


class InteractionType(Enum):
    """Types of NPC-NPC interactions."""
    
    HOSTILE = auto()      # Interrupts with criticism, mockery
    SUPPORTIVE = auto()   # Interrupts with agreement, defense  
    NEUTRAL = auto()      # Observation, curiosity
    NONE = auto()         # No interaction


@dataclass
class InteractionRule:
    """Rule defining when an NPC should intervene.
    
    Attributes:
        min_rapport: Minimum rapport value to trigger (for SUPPORTIVE)
        max_rapport: Maximum rapport value to trigger (for HOSTILE)
        interaction_type: Type of interaction
        probability: Chance of triggering (0.0-1.0)
        max_per_turn: Max interventions by this NPC per turn
    """
    min_rapport: int = -100
    max_rapport: int = 100
    interaction_type: InteractionType = InteractionType.NONE
    probability: float = 1.0
    max_per_turn: int = 1
    
    def should_trigger(self, rapport: int) -> bool:
        """Check if this rule should trigger given a rapport value.
        
        Args:
            rapport: Current rapport between NPCs (-100 to 100)
            
        Returns:
            True if interaction should occur
        """
        if rapport < self.min_rapport:
            return False
        if rapport > self.max_rapport:
            return False
        return True


class InteractionRuleset:
    """Collection of interaction rules for Multi-NPC system."""
    
    # CONSERVATIVE rules - Multi-NPC should be rare and meaningful
    DEFAULT_RULES = {
        # Hostile: Strong negative rapport - NPC interrupts to criticize
        # Only if there's actual conflict between NPCs
        "hostile_strong": InteractionRule(
            min_rapport=-100,
            max_rapport=-50,
            interaction_type=InteractionType.HOSTILE,
            probability=0.3,  # Reduced from 0.8 - should be rare
        ),
        # Supportive: Strong positive rapport - NPC defends/agrees
        # Only if they're actual friends
        "supportive_strong": InteractionRule(
            min_rapport=70,  # Increased from 50 - must be very close
            max_rapport=100,
            interaction_type=InteractionType.SUPPORTIVE,
            probability=0.2,  # Reduced from 0.7 - should be rare
        ),
        # Neutral: Very rare observation
        "neutral": InteractionRule(
            min_rapport=-20,
            max_rapport=20,
            interaction_type=InteractionType.NEUTRAL,
            probability=0.05,  # Very rare - 5% chance
        ),
    }
    
    def __init__(self, custom_rules: Optional[Dict[str, InteractionRule]] = None):
        """Initialize ruleset.
        
        Args:
            custom_rules: Optional custom rules to override defaults
        """
        self.rules = self.DEFAULT_RULES.copy()
        if custom_rules:
            self.rules.update(custom_rules)
    
    def check_interaction(
        self,
        rapport: int,
        interaction_count: int = 0,
    ) -> Optional[InteractionType]:
        """Check what type of interaction should occur.
        
        Args:
            rapport: Current rapport between NPCs
            interaction_count: How many times this NPC has intervened this turn
            
        Returns:
            InteractionType or None if no interaction
        """
        for rule in self.rules.values():
            if interaction_count >= rule.max_per_turn:
                continue
                
            if rule.should_trigger(rapport):
                # Check probability
                import random
                if random.random() <= rule.probability:
                    return rule.interaction_type
        
        return None
    
    def get_npcs_that_might_intervene(
        self,
        active_npc: str,
        present_npcs: List[str],
        npc_links: Dict[str, Dict[str, Any]],
    ) -> List[tuple]:
        """Get list of NPCs that might intervene based on relationships.
        
        Args:
            active_npc: Currently speaking NPC
            present_npcs: All NPCs present in scene
            npc_links: Relationship data between NPCs
            
        Returns:
            List of (npc_name, interaction_type, rapport) tuples
        """
        candidates = []
        
        for npc in present_npcs:
            if npc == active_npc:
                continue
            
            # Get rapport from npc_links
            links = npc_links.get(npc, {})
            link_data = links.get(active_npc, {})
            rapport = link_data.get("rapport", 0) if isinstance(link_data, dict) else 0
            
            interaction = self.check_interaction(rapport)
            if interaction and interaction != InteractionType.NONE:
                candidates.append((npc, interaction, rapport))
        
        # Sort by rapport extremity (most extreme first)
        candidates.sort(key=lambda x: abs(x[2]), reverse=True)
        return candidates
