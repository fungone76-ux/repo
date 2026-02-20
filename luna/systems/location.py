"""Location management system with full immersion features.

Handles:
- Location hierarchy (parent/child)
- Dynamic states and descriptions
- Discovery of hidden locations
- Companion following logic
- Narrative transitions
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from luna.core.models import (
    GameState,
    Location,
    LocationInstance,
    LocationState,
    LocationTransition,
    MovementRequest,
    MovementResponse,
    TimeOfDay,
    WorldDefinition,
)


class LocationManager:
    """Manages location states and navigation.
    
    Features:
    - Hierarchical navigation (parent/child locations)
    - Dynamic location states (crowded, empty, damaged, etc)
    - Discovery system for hidden locations
    - Companion following with refusal logic
    - Narrative transitions between locations
    """
    
    def __init__(
        self,
        world: WorldDefinition,
        game_state: GameState,
    ) -> None:
        """Initialize location manager.
        
        Args:
            world: World definition with locations
            game_state: Current game state
        """
        self.world = world
        self.game_state = game_state
        
        # Runtime location instances
        self._instances: Dict[str, LocationInstance] = {}
        self._init_instances()
    
    def _init_instances(self) -> None:
        """Initialize location instances from world definition."""
        for loc_id, loc_def in self.world.locations.items():
            self._instances[loc_id] = LocationInstance(
                location_id=loc_id,
                discovered=not loc_def.hidden,  # Hidden = not discovered
            )
    
    # ========================================================================
    # Query Methods
    # ========================================================================
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """Get location definition by ID."""
        return self.world.locations.get(location_id)
    
    def get_instance(self, location_id: str) -> Optional[LocationInstance]:
        """Get location instance (runtime state)."""
        return self._instances.get(location_id)
    
    def get_current_location(self) -> Optional[Location]:
        """Get current location definition."""
        return self.get_location(self.game_state.current_location)
    
    def get_current_instance(self) -> Optional[LocationInstance]:
        """Get current location instance."""
        return self.get_instance(self.game_state.current_location)
    
    # ========================================================================
    # Visibility & Discovery
    # ========================================================================
    
    def get_visible_locations(self) -> List[str]:
        """Get locations visible from current position.
        
        Returns:
            List of location IDs reachable from current location
        """
        current = self.get_current_location()
        if not current:
            return []
        
        visible = []
        current_id = self.game_state.current_location
        
        for loc_id, loc_def in self.world.locations.items():
            # Skip self
            if loc_id == current_id:
                continue
            
            instance = self._instances[loc_id]
            
            # Check if discovered
            if not instance.discovered and loc_def.hidden:
                continue
            
            # Check if connected
            if loc_id in current.connected_to:
                visible.append(loc_id)
                continue
            
            # Check if sub-location of current
            if loc_def.parent_location == current_id:
                visible.append(loc_id)
                continue
            
            # Check if parent of current (can go back)
            if current.parent_location == loc_id:
                visible.append(loc_id)
                continue
        
        return visible
    
    def get_visible_locations_description(self) -> str:
        """Get formatted description of visible locations."""
        visible = self.get_visible_locations()
        if not visible:
            return "Non ci sono altre location visibili da qui."
        
        lines = ["\n**Puoi raggiungere:**"]
        for loc_id in visible:
            loc = self.get_location(loc_id)
            instance = self.get_instance(loc_id)
            if loc:
                # Show state if not normal
                state_str = ""
                if instance and instance.current_state != LocationState.NORMAL:
                    state_str = f" [{instance.current_state.value}]"
                
                # Show discovery hint if not discovered
                if not instance.discovered and loc.discovery_hint:
                    lines.append(f"  - ??? ({loc.discovery_hint})")
                else:
                    lines.append(f"  - {loc.name}{state_str}")
        
        return "\n".join(lines)
    
    def discover_location(self, location_id: str) -> bool:
        """Mark a location as discovered.
        
        Args:
            location_id: Location to discover
            
        Returns:
            True if newly discovered
        """
        instance = self._instances.get(location_id)
        if instance and not instance.discovered:
            instance.discovered = True
            return True
        return False
    
    # ========================================================================
    # Movement Validation
    # ========================================================================
    
    def can_move_to(
        self,
        target_id: str,
        check_companion: bool = True,
    ) -> Tuple[bool, str]:
        """Check if movement to target is possible.
        
        Args:
            target_id: Target location ID
            check_companion: Whether to check companion restrictions
            
        Returns:
            Tuple of (can_move, reason_message)
        """
        target = self.get_location(target_id)
        if not target:
            return False, "Location non esistente."
        
        instance = self.get_instance(target_id)
        current = self.get_current_location()
        
        # Check if already there
        if target_id == self.game_state.current_location:
            return False, "Sei già qui."
        
        # Check if location is locked
        if instance and instance.current_state == LocationState.LOCKED:
            return False, target.closed_description or "È chiuso a chiave."
        
        # Check parent requirement
        if target.requires_parent and target.parent_location != self.game_state.current_location:
            if target.parent_location:
                parent = self.get_location(target.parent_location)
                parent_name = parent.name if parent else "area"
                return False, f"Devi essere in {parent_name} per entrare qui."
            return False, "Non puoi arrivarci da qui."
        
        # Check connectivity
        visible = self.get_visible_locations()
        if target_id not in visible:
            return False, "Non c'è connessione diretta. Prova un altro percorso."
        
        # Check time availability
        if target.available_times:
            if self.game_state.time_of_day not in target.available_times:
                return False, target.closed_description or "È chiuso a quest'ora."
        
        # Check required item
        if target.requires_item:
            has_item = target.requires_item in self.game_state.player.inventory
            if not has_item:
                return False, f"Ti serve: {target.requires_item}"
        
        # Check required flag
        if target.requires_flag:
            has_flag = self.game_state.flags.get(target.requires_flag, False)
            if not has_flag:
                return False, "Non sai come arrivarci."
        
        # Check companion
        if check_companion and not target.companion_can_follow:
            companion_name = self.game_state.active_companion
            return False, f"{companion_name} non vuole entrare qui."
        
        return True, "OK"
    
    # ========================================================================
    # Movement Execution
    # ========================================================================
    
    def move_to(
        self,
        target_id: str,
        force: bool = False,
    ) -> MovementResponse:
        """Execute movement to target location.
        
        Args:
            target_id: Target location ID
            force: If True, bypass some restrictions
            
        Returns:
            Movement result
        """
        # Validate
        can_move, reason = self.can_move_to(target_id, check_companion=not force)
        
        if not can_move:
            # Check if companion would refuse
            target = self.get_location(target_id)
            if target and not target.companion_can_follow and not force:
                companion_name = self.game_state.active_companion
                return MovementResponse(
                    success=False,
                    block_reason="companion_refused",
                    block_description=target.companion_refuse_message or 
                        f"{companion_name} si rifiuta di entrare.",
                )
            
            return MovementResponse(
                success=False,
                block_reason="blocked",
                block_description=reason,
            )
        
        # Generate transition
        transition = self._generate_transition(target_id)
        
        # Update state
        old_location = self.game_state.current_location
        self.game_state.current_location = target_id
        
        # Discover location
        self.discover_location(target_id)
        
        return MovementResponse(
            success=True,
            new_location=target_id,
            transition_text=transition,
        )
    
    def _generate_transition(self, target_id: str) -> str:
        """Generate narrative transition text.
        
        Args:
            target_id: Target location
            
        Returns:
            Transition narrative
        """
        target = self.get_location(target_id)
        current = self.get_current_location()
        
        if not target or not current:
            return ""
        
        # Build default transition
        lines = []
        
        # Movement description
        from_name = current.name
        to_name = target.name
        lines.append(f"Ti muovi da {from_name} verso {to_name}...")
        
        # Time-based atmosphere
        time_desc = {
            TimeOfDay.MORNING: "La luce del mattino ti accompagna.",
            TimeOfDay.AFTERNOON: "Il sole pomeridiano riscalda l'aria.",
            TimeOfDay.EVENING: "La luce del tramonto colora tutto di arancione.",
            TimeOfDay.NIGHT: "L'oscurità della notte avvolge i tuoi passi.",
        }
        if self.game_state.time_of_day in time_desc:
            lines.append(time_desc[self.game_state.time_of_day])
        
        return " ".join(lines)
    
    # ========================================================================
    # Location State Management
    # ========================================================================
    
    def set_location_state(
        self,
        location_id: str,
        state: LocationState,
    ) -> None:
        """Set dynamic state of a location.
        
        Args:
            location_id: Location to modify
            state: New state
        """
        instance = self._instances.get(location_id)
        if instance:
            instance.current_state = state
    
    def set_location_flag(
        self,
        location_id: str,
        flag: str,
        value: Any,
    ) -> None:
        """Set a flag on a location.
        
        Args:
            location_id: Location
            flag: Flag name
            value: Flag value
        """
        instance = self._instances.get(location_id)
        if instance:
            instance.flags[flag] = value
    
    # ========================================================================
    # NPC Presence
    # ========================================================================
    
    def get_npcs_at_location(self, location_id: str) -> List[str]:
        """Get NPCs currently at a location.
        
        Args:
            location_id: Location to check
            
        Returns:
            List of NPC names
        """
        instance = self.get_instance(location_id)
        if instance:
            return instance.npcs_present
        return []
    
    def add_npc_to_location(
        self,
        location_id: str,
        npc_name: str,
    ) -> None:
        """Add an NPC to a location.
        
        Args:
            location_id: Location
            npc_name: NPC to add
        """
        instance = self.get_instance(location_id)
        if instance and npc_name not in instance.npcs_present:
            instance.npcs_present.append(npc_name)
    
    def remove_npc_from_location(
        self,
        location_id: str,
        npc_name: str,
    ) -> None:
        """Remove an NPC from a location.
        
        Args:
            location_id: Location
            npc_name: NPC to remove
        """
        instance = self.get_instance(location_id)
        if instance and npc_name in instance.npcs_present:
            instance.npcs_present.remove(npc_name)
    
    # ========================================================================
    # Context for LLM
    # ========================================================================
    
    def get_location_context(self) -> str:
        """Generate location context for LLM prompt.
        
        Returns:
            Formatted location context
        """
        current = self.get_current_location()
        instance = self.get_current_instance()
        
        if not current or not instance:
            return ""
        
        lines = ["=== LOCATION ==="]
        
        # Current location
        desc = instance.get_effective_description(
            current,
            self.game_state.time_of_day,
        )
        lines.append(f"You are in: {current.name}")
        lines.append(f"Description: {desc}")
        
        # State if not normal
        if instance.current_state != LocationState.NORMAL:
            lines.append(f"State: {instance.current_state.value}")
        
        # Visible locations
        visible = self.get_visible_locations()
        if visible:
            lines.append("\nFrom here you can reach:")
            for loc_id in visible[:5]:  # Limit to 5
                loc = self.get_location(loc_id)
                inst = self.get_instance(loc_id)
                if loc:
                    if inst and not inst.discovered and loc.discovery_hint:
                        lines.append(f"  - {loc.discovery_hint}")
                    else:
                        lines.append(f"  - {loc.name}")
        
        # Other NPCs present
        other_npcs = [npc for npc in instance.npcs_present 
                     if npc != self.game_state.active_companion]
        if other_npcs:
            lines.append(f"\nAlso present: {', '.join(other_npcs)}")
        
        lines.append("=== END LOCATION ===")
        
        return "\n".join(lines)
    
    def resolve_location_alias(self, alias: str) -> Optional[str]:
        """Resolve a location alias to ID.
        
        Args:
            alias: Name or alias to resolve
            
        Returns:
            Location ID or None
        """
        alias_lower = alias.lower()
        
        for loc_id, loc_def in self.world.locations.items():
            # Direct ID match
            if loc_id.lower() == alias_lower:
                return loc_id
            
            # Name match
            if loc_def.name.lower() == alias_lower:
                return loc_id
            
            # Alias match
            if any(a.lower() == alias_lower for a in loc_def.aliases):
                return loc_id
        
        return None
