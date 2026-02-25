"""Global Events System - Dynamic world events.

Manages global events like weather, school events, social situations.
Events activate based on conditions (time, location, random) and affect gameplay.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum


class EventTriggerType(Enum):
    """Types of event triggers."""
    RANDOM = "random"           # Random chance per turn
    TIME_BASED = "time"         # Specific time of day
    LOCATION_BASED = "location"  # Player in specific location
    AFFINITY_BASED = "affinity"  # Affinity threshold reached
    FLAG_BASED = "flag"         # Specific flag set
    SCHEDULED = "scheduled"     # Specific turn number


@dataclass
class GlobalEventInstance:
    """An active global event instance."""
    event_id: str
    name: str
    description: str
    icon: str = "🌍"
    duration_turns: int = 5
    remaining_turns: int = 5
    effects: Dict[str, Any] = field(default_factory=dict)
    narrative_prompt: str = ""  # Template for LLM context
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "duration_turns": self.duration_turns,
            "remaining_turns": self.remaining_turns,
            "effects": self.effects,
            "narrative_prompt": self.narrative_prompt,
        }


class GlobalEventManager:
    """Manages global events in the world.
    
    Events can be triggered by:
    - Random chance each turn
    - Specific conditions (time, location, affinity)
    - Story progression (specific turn)
    
    Active events affect:
    - Available actions
    - Character moods
    - Location descriptions
    - Quest triggers
    """
    
    def __init__(self, world: Any) -> None:
        """Initialize event manager.
        
        Args:
            world: World definition with global_events config
        """
        self.world = world
        self.event_definitions = getattr(world, 'global_events', {})
        
        # Active events
        self.active_events: Dict[str, GlobalEventInstance] = {}
        
        # Event history (to prevent immediate re-trigger)
        self.event_history: Dict[str, int] = {}  # event_id -> last_turn_ended
        
        # Current turn for tracking
        self._current_turn = 0
        
        # Callback when event activates/deactivates
        self.on_event_changed: Optional[Callable[[Optional[GlobalEventInstance]], None]] = None
        
        print(f"[GlobalEventManager] Loaded {len(self.event_definitions)} event definitions")
    
    def check_and_activate_events(
        self,
        game_state: Any,
        force_random: bool = False,
    ) -> List[GlobalEventInstance]:
        """Check conditions and activate events.
        
        Called each turn by GameEngine.
        
        Args:
            game_state: Current game state
            force_random: Force random roll even if not turn-based
            
        Returns:
            List of newly activated events
        """
        self._current_turn = getattr(game_state, 'turn_count', 0)
        newly_activated: List[GlobalEventInstance] = []
        
        # Check each event definition
        for event_id, event_def in self.event_definitions.items():
            # Skip if already active
            if event_id in self.active_events:
                continue
            
            # Skip if in cooldown
            if self._is_in_cooldown(event_id):
                continue
            
            # Check trigger conditions
            if self._should_activate(event_def, game_state, force_random):
                event_instance = self._activate_event(event_id, event_def)
                if event_instance:
                    newly_activated.append(event_instance)
        
        # Decrement remaining turns for active events
        self._update_active_events()
        
        return newly_activated
    
    def _is_in_cooldown(self, event_id: str) -> bool:
        """Check if event is in cooldown period."""
        if event_id not in self.event_history:
            return False
        
        last_ended = self.event_history[event_id]
        turns_since = self._current_turn - last_ended
        
        # Default 10-turn cooldown
        return turns_since < 10
    
    def _should_activate(
        self,
        event_def: Any,
        game_state: Any,
        force_random: bool,
    ) -> bool:
        """Check if event should activate based on conditions."""
        meta = getattr(event_def, 'meta', None)
        if not meta:
            return False
        
        trigger = getattr(event_def, 'trigger', None)
        if not trigger:
            # No trigger defined, use random chance
            return random.random() < 0.05  # 5% base chance
        
        trigger_type = trigger.get('type', 'random')
        
        # RANDOM trigger
        if trigger_type == 'random':
            chance = trigger.get('chance', 0.15)
            if force_random or random.random() < chance:
                return True
        
        # TIME_BASED trigger
        elif trigger_type == 'time':
            required_time = trigger.get('time_of_day')
            if required_time:
                current_time = getattr(game_state, 'time_of_day', None)
                if hasattr(current_time, 'value'):
                    current_time = current_time.value
                if str(current_time).lower() == required_time.lower():
                    return random.random() < trigger.get('chance', 0.3)
        
        # LOCATION_BASED trigger
        elif trigger_type == 'location':
            required_loc = trigger.get('location')
            current_loc = getattr(game_state, 'current_location', '')
            if required_loc and required_loc.lower() in str(current_loc).lower():
                return random.random() < trigger.get('chance', 0.4)
        
        # AFFINITY_BASED trigger
        elif trigger_type == 'affinity':
            char = trigger.get('character')
            threshold = trigger.get('threshold', 50)
            affinity = getattr(game_state, 'affinity', {})
            if char and affinity.get(char, 0) >= threshold:
                return random.random() < trigger.get('chance', 0.5)
        
        # FLAG_BASED trigger
        elif trigger_type == 'flag':
            required_flag = trigger.get('flag')
            flags = getattr(game_state, 'flags', {})
            if required_flag and flags.get(required_flag, False):
                return random.random() < trigger.get('chance', 0.6)
        
        # SCHEDULED trigger
        elif trigger_type == 'scheduled':
            target_turn = trigger.get('turn')
            if target_turn and self._current_turn >= target_turn:
                return True
        
        return False
    
    def _activate_event(self, event_id: str, event_def: Any) -> Optional[GlobalEventInstance]:
        """Activate an event."""
        try:
            meta = event_def.meta
            
            # Get duration
            duration = getattr(event_def, 'duration', {}).get('turns', 5)
            if isinstance(duration, dict):
                # Random duration between min/max
                min_d = duration.get('min', 3)
                max_d = duration.get('max', 8)
                duration = random.randint(min_d, max_d)
            
            # Get narrative prompt from definition
            narrative_prompt = ""
            if hasattr(event_def, 'narrative_prompt'):
                narrative_prompt = event_def.narrative_prompt
            elif isinstance(event_def, dict):
                narrative_prompt = event_def.get('narrative_prompt', '')
            
            instance = GlobalEventInstance(
                event_id=event_id,
                name=meta.name,
                description=meta.description,
                icon=getattr(meta, 'icon', '🌍'),
                duration_turns=duration,
                remaining_turns=duration,
                effects=getattr(event_def, 'effects', {}),
                narrative_prompt=narrative_prompt,
            )
            
            self.active_events[event_id] = instance
            print(f"[GlobalEventManager] ACTIVATED: {instance.name} ({instance.icon})")
            
            # Notify callback
            if self.on_event_changed:
                self.on_event_changed(instance)
            
            return instance
            
        except Exception as e:
            print(f"[GlobalEventManager] Error activating {event_id}: {e}")
            return None
    
    def _update_active_events(self) -> None:
        """Update all active events (decrement turns, expire if needed)."""
        expired = []
        
        for event_id, event in self.active_events.items():
            event.remaining_turns -= 1
            
            if event.remaining_turns <= 0:
                expired.append(event_id)
        
        # Remove expired events
        for event_id in expired:
            self._deactivate_event(event_id)
    
    def _deactivate_event(self, event_id: str) -> None:
        """Deactivate an event."""
        if event_id in self.active_events:
            event = self.active_events.pop(event_id)
            self.event_history[event_id] = self._current_turn
            print(f"[GlobalEventManager] ENDED: {event.name}")
            
            # Notify callback (no active event = None)
            if self.active_events:
                # Return first active event or None
                first_event = next(iter(self.active_events.values()))
                if self.on_event_changed:
                    self.on_event_changed(first_event)
            else:
                if self.on_event_changed:
                    self.on_event_changed(None)
    
    def get_primary_event(self) -> Optional[GlobalEventInstance]:
        """Get the primary/most important active event.
        
        Returns:
            The first active event, or None if no events active
        """
        if not self.active_events:
            return None
        return next(iter(self.active_events.values()))
    
    def get_all_active_events(self) -> List[GlobalEventInstance]:
        """Get all currently active events."""
        return list(self.active_events.values())
    
    def get_event_modifiers(self) -> Dict[str, Any]:
        """Get combined modifiers from all active events.
        
        Returns:
            Dict of modifiers (affinity_bonus, action_restrictions, etc.)
        """
        modifiers = {
            'affinity_multiplier': 1.0,
            'action_restrictions': [],
            'location_modifiers': {},
            'mood_override': None,
        }
        
        for event in self.active_events.values():
            effects = event.effects
            
            # Affinity multiplier
            if 'affinity_multiplier' in effects:
                modifiers['affinity_multiplier'] *= effects['affinity_multiplier']
            
            # Action restrictions
            if 'restrict_actions' in effects:
                modifiers['action_restrictions'].extend(effects['restrict_actions'])
            
            # Mood override (last one wins)
            if 'force_mood' in effects:
                modifiers['mood_override'] = effects['force_mood']
        
        return modifiers
    
    def force_activate_event(self, event_id: str) -> bool:
        """Force activate an event (for debug/story)."""
        if event_id not in self.event_definitions:
            return False
        
        if event_id in self.active_events:
            return False  # Already active
        
        event_def = self.event_definitions[event_id]
        instance = self._activate_event(event_id, event_def)
        return instance is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize active events for saving."""
        return {
            "active_events": {
                eid: evt.to_dict() 
                for eid, evt in self.active_events.items()
            },
            "event_history": self.event_history,
            "current_turn": self._current_turn,
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore active events from save."""
        self.active_events = {}
        for eid, evt_data in data.get("active_events", {}).items():
            self.active_events[eid] = GlobalEventInstance(**evt_data)
        
        self.event_history = data.get("event_history", {})
        self._current_turn = data.get("current_turn", 0)
