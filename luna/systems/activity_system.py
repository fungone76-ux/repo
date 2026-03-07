"""Activity System - NPC Autonomous Awareness.

Tracks what each NPC is doing RIGHT NOW and manages autonomous behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum
import random


class ActivityType(Enum):
    """Types of activities NPCs can engage in."""
    IDLE = "idle"                    # Doing nothing specific
    WORKING = "working"              # Job/school related
    TRAVELING = "traveling"          # Moving between locations
    EATING = "eating"                # Having a meal
    EXERCISING = "exercising"        # Sports/training
    RELAXING = "relaxing"            # Resting, watching TV, etc.
    SOCIALIZING = "socializing"      # With friends/others
    PREPARING = "preparing"          # Getting ready for something
    WAITING = "waiting"              # Waiting for player/someone
    SLEEPING = "sleeping"            # Asleep


@dataclass
class ActivityState:
    """Current activity of an NPC."""
    
    action: str                      # What they're doing (e.g., "corregge compiti")
    location: str                    # Where they are
    activity_type: ActivityType      # Category
    duration_remaining: int = 0      # How many more turns (0 = indefinite)
    next_activity: Optional[str] = None  # What they'll do next
    next_location: Optional[str] = None  # Where they'll go next
    
    def describe(self) -> str:
        """Get natural description of current activity."""
        if self.activity_type == ActivityType.TRAVELING:
            return f"Si sta dirigendo verso {self.next_location}"
        return f"{self.action} a {self.location}"


class ActivitySystem:
    """Manages autonomous NPC activities based on schedule and time."""
    
    # Activity templates by time and character personality
    ACTIVITY_TEMPLATES = {
        "Luna": {
            "Morning": [
                ("sta spiegando matematica alla lavagna", ActivityType.WORKING, "Aula 3B"),
                ("sta preparando la lezione", ActivityType.WORKING, "Ufficio"),
                ("sta interrogando uno studente", ActivityType.WORKING, "Aula 3B"),
            ],
            "Afternoon": [
                ("sta correggendo compiti", ActivityType.WORKING, "Ufficio"),
                ("sta preparando la lezione di domani", ActivityType.WORKING, "Ufficio"),
                ("sta bevendo caffè", ActivityType.RELAXING, "Sala professori"),
            ],
            "Evening": [
                ("sta sistemando l'ufficio", ActivityType.WORKING, "Ufficio"),
                ("sta leggendo un libro", ActivityType.RELAXING, "Ufficio"),
                ("sta preparando le lezioni private", ActivityType.PREPARING, "Ufficio"),
            ],
            "Night": [
                ("sta guardando la TV", ActivityType.RELAXING, "Casa"),
                ("sta leggendo in poltrona", ActivityType.RELAXING, "Casa"),
                ("sta preparando la cena", ActivityType.EATING, "Casa"),
                ("sta pensando al divorzio", ActivityType.IDLE, "Casa"),
            ],
        },
        "Stella": {
            "Morning": [
                ("sta prendendo appunti", ActivityType.WORKING, "Aula 3B"),
                ("sta chiacchierando con le amiche", ActivityType.SOCIALIZING, "Corridoio"),
                ("sta guardando lo smartphone", ActivityType.IDLE, "Aula 3B"),
            ],
            "Afternoon": [
                ("sta allenandosi a pallavolo", ActivityType.EXERCISING, "Palestra"),
                ("sta correndo in palestra", ActivityType.EXERCISING, "Palestra"),
                ("sta facendo stretching", ActivityType.EXERCISING, "Palestra"),
            ],
            "Evening": [
                ("sta facendo la doccia", ActivityType.PREPARING, "Spogliatoi"),
                ("sta cambiandosi", ActivityType.PREPARING, "Spogliatoi"),
                ("sta aspettando qualcuno", ActivityType.WAITING, "Ingresso"),
            ],
            "Night": [
                ("sta guardando Netflix", ActivityType.RELAXING, "Casa"),
                ("sta scrivendo messaggi", ActivityType.SOCIALIZING, "Casa"),
                ("sta ascoltando musica", ActivityType.RELAXING, "Casa"),
            ],
        },
        "Maria": {
            "Morning": [
                ("sta lavando i pavimenti", ActivityType.WORKING, "Corridoio"),
                ("sta pulendo i bagni", ActivityType.WORKING, "Bagni"),
                ("sta sparecchiando", ActivityType.WORKING, "Aula"),
            ],
            "Afternoon": [
                ("sta pulendo la palestra", ActivityType.WORKING, "Palestra"),
                ("sta riordinando il deposito", ActivityType.WORKING, "Deposito"),
                ("sta riposandosi un attimo", ActivityType.RELAXING, "Deposito"),
            ],
            "Evening": [
                ("sta finendo il turno", ActivityType.WORKING, "Scuola"),
                ("sta preparando la cena", ActivityType.EATING, "Casa"),
                ("sta guardando la TV", ActivityType.RELAXING, "Casa"),
            ],
            "Night": [
                ("sta cenando", ActivityType.EATING, "Casa"),
                ("sta guardando telenovelas", ActivityType.RELAXING, "Casa"),
                ("sta pensando alla solitudine", ActivityType.IDLE, "Casa"),
            ],
        },
    }
    
    def __init__(self) -> None:
        """Initialize activity system."""
        self.npc_activities: Dict[str, ActivityState] = {}
        self.turn_counter = 0
    
    def update_activity(
        self,
        npc_name: str,
        time_of_day: str,
        current_turn: int,
        force_update: bool = False
    ) -> ActivityState:
        """Update or get activity for an NPC.
        
        Args:
            npc_name: Name of the NPC
            time_of_day: Current time of day
            current_turn: Current turn number
            force_update: Force a new activity even if duration hasn't expired
            
        Returns:
            Current activity state
        """
        # Check if we need to update
        current = self.npc_activities.get(npc_name)
        
        needs_update = force_update or current is None
        
        if current and current.duration_remaining > 0 and not force_update:
            # Decrement duration
            current.duration_remaining -= 1
            if current.duration_remaining <= 0:
                needs_update = True
            else:
                return current
        
        # Generate new activity
        if needs_update:
            new_activity = self._generate_activity(npc_name, time_of_day)
            self.npc_activities[npc_name] = new_activity
            return new_activity
        
        return current
    
    def _generate_activity(self, npc_name: str, time_of_day: str) -> ActivityState:
        """Generate appropriate activity for NPC based on time."""
        templates = self.ACTIVITY_TEMPLATES.get(npc_name, {}).get(time_of_day, [])
        
        if not templates:
            # Default fallback
            return ActivityState(
                action="sta aspettando",
                location="Sconosciuto",
                activity_type=ActivityType.IDLE,
                duration_remaining=random.randint(2, 4)
            )
        
        # Pick random activity from templates
        action, act_type, location = random.choice(templates)
        
        # Determine next activity (usually after this one)
        next_act = None
        next_loc = None
        if act_type == ActivityType.EXERCISING and "palestra" in location.lower():
            next_act = "sta facendo la doccia"
            next_loc = "Spogliatoi"
        elif act_type == ActivityType.WORKING and time_of_day == "Evening":
            next_act = "sta andando a casa"
            next_loc = "Casa"
        
        return ActivityState(
            action=action,
            location=location,
            activity_type=act_type,
            duration_remaining=random.randint(3, 6),  # 3-6 turns
            next_activity=next_act,
            next_location=next_loc
        )
    
    def get_activity_context(self, npc_name: str) -> str:
        """Get activity description for prompt context."""
        activity = self.npc_activities.get(npc_name)
        if not activity:
            return ""
        
        context = f"\n### COSA STA FACENDO ORA {npc_name.upper()}\n"
        context += f"- Azione attuale: {activity.action}\n"
        context += f"- Luogo: {activity.location}\n"
        context += f"- Stato: {activity.activity_type.value}\n"
        
        if activity.next_activity:
            context += f"- Prossimamente: {activity.next_activity}"
            if activity.next_location:
                context += f" a {activity.next_location}"
            context += "\n"
        
        # Add behavioral instruction
        context += f"\n**ISTRUZIONE IMPORTANTE**: {npc_name} deve comportarsi coerentemente con ciò che sta facendo. "
        context += f"Se sta {activity.action.split()[1]}, deve mostrarlo nelle azioni e nel dialogo. "
        
        if activity.activity_type == ActivityType.RELAXING:
            context += "È rilassata e disponibile per chiacchiere. "
        elif activity.activity_type == ActivityType.WORKING:
            context += "È concentrata ma può interagire. Potrebbe essere distratta o interrompere il lavoro. "
        elif activity.activity_type == ActivityType.EXERCISING:
            context += "È sudata e stanca. Respira affannosamente. "
        elif activity.activity_type == ActivityType.WAITING:
            context += "È impaziente e aspetta qualcosa/qualcuno. Potrebbe prendere l'iniziativa. "
        
        context += "\n"
        return context
    
    def interrupt_activity(
        self,
        npc_name: str,
        reason: str,
        new_action: Optional[str] = None
    ) -> ActivityState:
        """Interrupt current activity (e.g., player arrives)."""
        current = self.npc_activities.get(npc_name)
        if not current:
            return None
        
        # Modify activity to show interruption
        interrupted_action = new_action or f"ha interrotto {current.action} perché {reason}"
        
        interrupted = ActivityState(
            action=interrupted_action,
            location=current.location,
            activity_type=ActivityType.IDLE,
            duration_remaining=2,  # Short duration, will resume or change
            next_activity=current.action,  # May go back to original
            next_location=current.location
        )
        
        self.npc_activities[npc_name] = interrupted
        return interrupted
    
    def force_activity(
        self,
        npc_name: str,
        action: str,
        location: str,
        activity_type: ActivityType = ActivityType.IDLE,
        duration: int = 3
    ) -> ActivityState:
        """Force a specific activity (for quests/events)."""
        forced = ActivityState(
            action=action,
            location=location,
            activity_type=activity_type,
            duration_remaining=duration
        )
        self.npc_activities[npc_name] = forced
        return forced
