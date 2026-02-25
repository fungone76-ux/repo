"""Multi-NPC Dialogue System.

Enables dynamic interactions between multiple NPCs in the same scene.
NPCs with extreme relationships (love/hate) can interrupt and respond to each other.

Usage:
    from luna.systems.multi_npc import MultiNPCManager, InteractionRule
    
    manager = MultiNPCManager(world, personality_engine)
    sequence = manager.process_turn(player_input, active_companion, present_npcs)
"""
from luna.systems.multi_npc.interaction_rules import InteractionRule, InteractionType
from luna.systems.multi_npc.dialogue_sequence import DialogueSequence, DialogueTurn
from luna.systems.multi_npc.manager import MultiNPCManager

__all__ = [
    "MultiNPCManager",
    "InteractionRule",
    "InteractionType", 
    "DialogueSequence",
    "DialogueTurn",
]
