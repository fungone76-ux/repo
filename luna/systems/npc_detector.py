"""NPC Detection System - Handles companion and generic NPC detection.

V4.3 REFACTOR: Extracted from engine.py to reduce complexity.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Any, List


class NPCDetector:
    """Detects NPC mentions in user input with proper validation."""
    
    # Words that are NEVER valid NPC names (common adjectives/postures/time words)
    SKIP_WORDS = {
        # Postures
        'seduta', 'seduto', 'sdraiata', 'sdraiato', 'chinata', 'chinato',
        'in piedi', 'in piede', 'acucciolata', 'acucciolato', 
        'in ginocchio', 'appoggiata', 'appoggiato', 'piegata', 'piegato',
        # Common words
        'uno', 'una', 'qualcuno', 'qualcuna', 'persona', 'gente', 'tipo',
        'ragazza', 'ragazzo', 'donna', 'uomo', 'femmina', 'maschio',
        # Body parts
        'occhi', 'occhio', 'naso', 'bocca', 'labbra', 'viso', 'faccia', 
        'capelli', 'testa', 'mano', 'mani', 'braccio', 'braccia',
        # Directions
        'destra', 'sinistra', 'davanti', 'dietro', 'sopra', 'sotto',
        # Time expressions (CRITICAL: prevent "non vedo l'ora" -> "Ora" NPC)
        'ora', 'adesso', 'poi', 'prima', 'dopo', 'sempre', 'mai', 'spesso',
        'oggi', 'ieri', 'domani', 'subito', 'presto', 'tardi',
        # Emotional expressions / gestures (CRITICAL: prevent "arrossendo" -> "Rrossendo" NPC)
        'arrossendo', 'rossendo', 'rrossendo', 'sorridendo', 'ridendo', 'piangendo', 'sospirando',
        'annuendo', 'scuotendo', 'alzando', 'abbassando', 'indicando', 'guardando',
        # Abstract concepts (CRITICAL: prevent "la bellezza" -> "Bellezza" NPC)
        'bellezza', 'bruttezza', 'intelligenza', 'stupidità', 'gentilezza', 'cattiveria',
        'forza', 'debolezza', 'coraggio', 'paura', 'gioia', 'tristezza', 'felicità',
        # Adverbs (CRITICAL: prevent "ti trovo molto intrigante" -> "Molto" NPC)
        'molto', 'poco', 'troppo', 'tanto', 'così', 'abbastanza', 'veramente', 'davvero',
        'probabilmente', 'forse', 'sicuramente', 'certamente', 'assolutamente',
        # Adjectives (CRITICAL: prevent "intrigante", "interessante", etc. -> NPC names)
        'intrigante', 'interessante', 'fredda', 'freddo', 'caldi', 'calda', 'caldo', 
        'bella', 'bello', 'brutta', 'brutto', 'intelligente', 'simpatica', 'simpatico',
        'premurosa', 'premuroso', 'strana', 'strano', 'speciale', 'unica', 'unico',
        'diversa', 'diverso', 'normale', 'particolare', 'tipica', 'tipico',
        # Nouns (CRITICAL: prevent "arriva un messaggio" -> "Messaggio" NPC)
        'messaggio', 'cellulare', 'telefono', 'chiamata', 'sms', 'notifica',
    }
    
    def __init__(self, world: Any) -> None:
        """Initialize detector with world reference.
        
        Args:
            world: WorldDefinition containing companions
        """
        self.world = world
    
    def detect_companion_in_input(self, user_input: str) -> Optional[str]:
        """Detect if user is addressing a specific companion.
        
        V4.3: Uses word boundaries to avoid partial matches.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Companion name if detected, None otherwise
        """
        input_lower = user_input.lower()
        print(f"[NPCDetector] Input: '{input_lower}'")
        
        # Priority 1: Check companion names (word boundary match)
        for name in self.world.companions.keys():
            name_lower = name.lower()
            if re.search(r'\b' + re.escape(name_lower) + r'\b', input_lower):
                # Skip temporary NPCs
                companion = self.world.companions[name]
                if getattr(companion, 'is_temporary', False):
                    continue
                print(f"[NPCDetector] Found by name: '{name}'")
                return name
        
        # Priority 2: Check explicit aliases from YAML
        for name, companion in self.world.companions.items():
            if getattr(companion, 'is_temporary', False):
                continue
            aliases = getattr(companion, 'aliases', []) or []
            for alias in aliases:
                if re.search(r'\b' + re.escape(alias.lower()) + r'\b', input_lower):
                    print(f"[NPCDetector] Found by alias '{alias}': '{name}'")
                    return name
        
        # Priority 3: Check role-based references (CONSERVATIVE)
        return self._detect_by_role(input_lower)
    
    def _detect_by_role(self, input_lower: str) -> Optional[str]:
        """Detect by role with strict patterns."""
        role_patterns_strict = {
            "professoressa": ["professoressa", "prof.", "prof "],
            "insegnante": ["insegnante"],
            "bidella": ["bidella"],
            "studentessa": ["studentessa", "ragazza bionda", "alunna"],
            "direttore": ["direttore", "preside"],
        }
        
        for name, companion in self.world.companions.items():
            if getattr(companion, 'is_temporary', False):
                continue
                
            role = getattr(companion, 'role', '').lower()
            aliases = [a.lower() for a in getattr(companion, 'aliases', [])]
            
            for role_key, patterns in role_patterns_strict.items():
                role_matches = role_key in role
                alias_matches = any(role_key in alias for alias in aliases)
                
                if role_matches or alias_matches:
                    for pattern in patterns:
                        if re.search(r'(^|[\s\.,;:!?])' + re.escape(pattern) + r'([\s\.,;:!?]|$)', input_lower):
                            return name
        
        return None
    
    def detect_generic_npc_interaction(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Detect if user is interacting with a generic NPC.
        
        V4.3: More conservative detection with better filtering.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Dict with npc info if detected, None otherwise
        """
        input_lower = user_input.lower()
        
        # Get known companions
        known_companions = self._get_known_companion_names()
        
        # Improved patterns with negative lookahead for partial words
        patterns = [
            r"\b(dico|parlo|chiedo|sussurro|grido)(?!\w)\s+(alla|all'|ad|al|a|con|da|di)",
            r"\b(saluto|incontro)(?!\w)\s+(il|la|lo|l'|i|gli|le|un|una|uno)",
            r"\b(vedo|noto|trovo|guardo|scorgo)(?!\w)\s+(una|uno|un|il|i|gli|la|le|lo|l')?",
            r"\b(accoglie|appare|compare|si avvicina|arriva)(?!\w)\s+(una|uno|un|il|la|lo|l'|i|gli|le)?",
            r"\b(c'e'|c'è|ecco)(?!\w)\s+(una|uno|un|il|la|lo|l'|i|gli|le)",
        ]
        
        articles = {'il', 'la', 'lo', 'l', 'i', 'gli', 'le', 'un', 'una', 'uno', 
                   'a', 'ad', 'al', 'alla', 'con', 'da', 'di', 'all', "all'", 'negli', 'agli', 'alle'}
        
        print(f"[NPCDetector] Checking generic NPC in: '{input_lower}'")
        
        for pattern in patterns:
            match = re.search(pattern, input_lower)
            if match:
                start_pos = match.end()
                remaining = input_lower[start_pos:].strip()
                words = remaining.split()[:10]
                
                target = None
                for idx, word in enumerate(words):
                    word_clean = word.strip(".,;:'!?()[]{}").lower()
                    
                    # Skip articles and invalid words
                    if word_clean in articles or word_clean in self.SKIP_WORDS:
                        continue
                    
                    # Skip known companions
                    if word_clean in known_companions:
                        return None
                    
                    # Valid target found
                    target = word_clean
                    break
                
                if target:
                    print(f"[NPCDetector] Generic NPC detected: '{target}'")
                    return {
                        'name': target.capitalize(),
                        'description': f"{target} (generic NPC)",
                        'gender': 'female' if target.endswith('a') else 'male',
                        'description_en': f"{target} standing in the scene",
                    }
        
        return None
    
    def _get_known_companion_names(self) -> set:
        """Get all known companion names and aliases."""
        known = set()
        for name, comp in self.world.companions.items():
            if not getattr(comp, 'is_temporary', False):
                known.add(name.lower())
                for alias in getattr(comp, 'aliases', []):
                    known.add(alias.lower())
                role = getattr(comp, 'role', '').lower()
                if role:
                    known.add(role)
        return known
