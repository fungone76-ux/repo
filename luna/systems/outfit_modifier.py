"""Outfit Modifier System V5.0 - Simplified deterministic clothing changes.

Detects outfit modifications from player input (Italian patterns) and applies
them as overlay modifications (OutfitModification) on top of the base outfit.

Key changes from V4:
- Modifications stored in outfit.modifications dict (persistent per phase)
- Description generation delegated to OutfitRenderer
- Simplified: ~10 modification types instead of 20+
- reset_modifications() for phase-change integration

Public API (unchanged for TurnOrchestrator compatibility):
    process_turn(user_input, game_state, companion_def) -> (modified, is_major, desc_it)
    apply_major_change(game_state, desc_it, llm_manager) -> bool
    change_random_outfit(game_state, companion_def) -> Optional[str]
    change_custom_outfit(game_state, desc_it, llm_manager) -> str
    reset_modifications(game_state) -> None  [NEW]
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from luna.core.models import GameState, OutfitState


# =============================================================================
# MODIFICATION TYPE PATTERNS (Italian)
# Each entry maps a modification TYPE to a list of regex triggers.
# =============================================================================

MOD_TYPE_PATTERNS: Dict[str, List[str]] = {
    "removal": [
        r"\b(senza|scalz[ao]|nud[ao]\s+(ai\s+piedi|in\s+alto|dal\s+busto|dai\s+fianchi))\b",
        r"\b(tolt[oaie]|levat[oaie]|rimoss[oaie]|sfilat[oaie])\b",
        r"\b(si\s+togli[eè]|toglie?|si\s+sfila?|sfila?|si\s+leva|leva)\b",
    ],
    "added": [
        r"\b(rimess[oaie]|indossat[oaie]|mett[eoa]|calzat[oaie])\b",
        r"\b(si\s+rimett[eoa]|rimett[eoa]|indoss[ao]|riprende|si\s+rivest)\b",
    ],
    "wet": [
        r"\b(bagnato|bagnata|bagnati|bagnate|inzuppat[oaie]|fradici[ao])\b",
    ],
    "partial_unbuttoned": [
        r"\b(sbottonat[oaie]|slacciat[oaie]|bottoni\s+aperti)\b",
        r"\b(si\s+sbotton[a]|sbotton[a]|apr[ea]\s+(la\s+)?camicia)\b",
    ],
    "lifted": [
        r"\b(sollevat[oaie]|alzat[oaie]|upskirt|sotto\s+la\s+gonna)\b",
        r"\b(si\s+solleva|solleva|si\s+alza|alza)\b",
    ],
    "lowered": [
        r"\b(abbassati?|abbassate?|calati?|calate?|giù\s+(i|le|il|la))\b",
        r"\b(si\s+abbassa|abbassa|si\s+cala|cala)\b",
    ],
    "torn": [
        r"\b(strappat[oaie]|rott[oaie])\b",
    ],
    "pulled_down": [
        r"\b(calate|attorno\s+(alle\s+)?caviglie|arrotolat[oa])\b",
    ],
    "see_through": [
        r"\b(trasparente|trasparenti|see[\s\-]?through|visibile\s+sotto)\b",
    ],
}

# Which components each modification type can apply to
MOD_APPLIES_TO: Dict[str, List[str]] = {
    "removal":             ["shoes", "top", "bra", "outerwear", "bottom", "panties", "pantyhose"],
    "added":               ["shoes", "top", "bra", "outerwear", "bottom", "panties", "pantyhose"],
    "wet":                 ["top", "bottom", "dress", "shoes"],
    "partial_unbuttoned":  ["top"],
    "lifted":              ["bottom", "dress"],
    "lowered":             ["bottom", "panties"],
    "torn":                ["pantyhose"],
    "pulled_down":         ["pantyhose"],
    "see_through":         ["bra", "top"],
}

# Italian noun patterns per component
COMPONENT_PATTERNS: Dict[str, List[str]] = {
    "shoes":     [r"\b(scarpe?|tacchi|calzini|sandali|stivali|mocassini)\b"],
    "top":       [r"\b(camicia|maglia|top|blusa|maglietta|canottiera|canotta|t-shirt)\b"],
    "bra":       [r"\b(reggiseno|bra|reggipetto)\b"],
    "outerwear": [r"\b(giacca|blazer|cardigan|cappotto|giubbotto)\b"],
    "bottom":    [r"\b(gonna|pantaloni|shorts|pantaloncini|jeans|pantalone)\b"],
    "panties":   [r"\b(mutande|perizoma|slip|intimo)\b"],
    "pantyhose": [r"\b(calze|collant|autoreggenti)\b"],
    "dress":     [r"\b(vestito|abito)\b"],
}

# Fast-path direct phrases - checked first for common expressions
DIRECT_PHRASES: List[Dict] = [
    {"pattern": r"\b(scalz[ao]|piedi\s+nudi|senza\s+scarpe?|nud[ao]\s+ai\s+piedi)\b",
     "component": "shoes", "state": "removed"},
    {"pattern": r"\b(rimett[eoa]\s+(le\s+)?scarpe?|scarpe?\s+(rimesse?|ai\s+piedi))\b",
     "component": "shoes", "state": "added"},
    {"pattern": r"\b(upskirt|sotto\s+la\s+gonna|gonna\s+sollevata|gonna\s+alzata)\b",
     "component": "bottom", "state": "lifted"},
    {"pattern": r"\b(vestito\s+bagnato|abito\s+bagnato|bagnata\s+fradicia)\b",
     "component": "dress", "state": "wet"},
    {"pattern": r"\b(calze\s+strappate|collant\s+strappato)\b",
     "component": "pantyhose", "state": "torn"},
    {"pattern": r"\b(calze\s+calate|collant\s+calato|calze\s+alle\s+caviglie)\b",
     "component": "pantyhose", "state": "pulled_down"},
    {"pattern": r"\b(camicia\s+sbottonata|camicia\s+aperta|scollo\s+aperto)\b",
     "component": "top", "state": "partial_unbuttoned"},
    {"pattern": r"\b(piedi\s+scalzi|feet\s+bare|barefoot)\b",
     "component": "shoes", "state": "removed"},
]

# Major-change patterns (complete outfit replacement)
MAJOR_CHANGE_PATTERNS: List[str] = [
    r"\b(si\s+cambia\s+(il\s+)?(vestito|abito|outfit))\b",
    r"\b(mette\s+(un\s+)?(altro|nuovo|diverso)\s+(vestito|abito|outfit|completo))\b",
    r"\b(vestito\s+da\s+sera|abito\s+da\s+sera|evening\s+gown)\b",
    r"\b(pigiama|pajamas|sleepwear)\b",
    r"\b(bikini|costume\s+da\s+bagno|swimsuit)\b",
    r"\b(lingerie|intimo\s+sexy|biancheria\s+intima)\b",
    r"\b(kimono|accappatoio|vestaglia)\b",
    r"\b(uniforme|divisa)\b",
    r"\b(indossa\s+(un|una)\s+(?!poco|solo|solo\s+un)(\w+\s+){0,3}(vestito|abito|outfit|completo))\b",
]


# =============================================================================
# OutfitModifierSystem
# =============================================================================

class OutfitModifierSystem:
    """Standalone outfit modification system V5.0.

    Parses player input for clothing modifications and applies them
    as OutfitModification overlay entries in game_state.outfit.modifications.
    Call once per turn via process_turn().
    """

    def __init__(self) -> None:
        self._type_compiled: Dict[str, List[re.Pattern]] = {}
        self._comp_compiled: Dict[str, List[re.Pattern]] = {}
        self._direct_compiled: List[Dict] = []
        self._major_compiled: List[re.Pattern] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        for mod_type, patterns in MOD_TYPE_PATTERNS.items():
            self._type_compiled[mod_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        for component, patterns in COMPONENT_PATTERNS.items():
            self._comp_compiled[component] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        for entry in DIRECT_PHRASES:
            self._direct_compiled.append({
                "pattern": re.compile(entry["pattern"], re.IGNORECASE),
                "component": entry["component"],
                "state": entry["state"],
            })
        self._major_compiled = [
            re.compile(p, re.IGNORECASE) for p in MAJOR_CHANGE_PATTERNS
        ]

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def process_turn(
        self,
        user_input: str,
        game_state: "GameState",
        companion_def=None,
    ) -> Tuple[bool, bool, str]:
        """Process a turn for outfit modifications.

        Args:
            user_input: Player's input text
            game_state: Current game state (will be modified in-place)
            companion_def: Optional companion definition for wardrobe lookup

        Returns:
            (modified, is_major_change, outfit_description_it)
            - modified: True if any overlay modification was detected
            - is_major_change: True if a complete outfit replacement was requested
            - outfit_description_it: Italian description for major-change async handling
        """
        # Check for complete outfit replacement first
        is_major, desc_it = self._is_major_change(user_input)
        if is_major:
            return False, True, desc_it

        # Detect overlay modifications
        detected = self._detect_modifications(user_input)
        if not detected:
            return False, False, ""

        outfit = game_state.get_outfit()
        self._apply_modifications(outfit, detected, game_state.turn_count, companion_def)
        game_state.set_outfit(outfit)

        changed = ", ".join(f"{c}:{s}" for c, s in detected)
        print(f"[OutfitModifier] Modifications applied: {changed}")
        return True, False, ""

    def reset_modifications(self, game_state: "GameState") -> None:
        """Clear all overlay modifications (call on phase change).

        Args:
            game_state: Current game state
        """
        outfit = game_state.get_outfit()
        if outfit.modifications:
            print(f"[OutfitModifier] Resetting {len(outfit.modifications)} modifications on phase change")
            outfit.modifications.clear()
            game_state.set_outfit(outfit)

    async def apply_major_change(
        self,
        game_state: "GameState",
        outfit_description_it: str,
        llm_manager=None,
    ) -> bool:
        """Apply a complete outfit change with optional LLM translation.

        Args:
            game_state: Current game state
            outfit_description_it: Italian outfit description
            llm_manager: Optional LLM manager for IT→EN translation

        Returns:
            True if the change was applied
        """
        outfit = game_state.get_outfit()
        old_style = outfit.style

        if llm_manager:
            try:
                outfit_description_en = await self._translate_outfit(
                    outfit_description_it, llm_manager
                )
            except Exception as e:
                print(f"[OutfitModifier] Translation failed, using original: {e}")
                outfit_description_en = outfit_description_it
        else:
            outfit_description_en = outfit_description_it

        # Reset to custom outfit
        outfit.style = "custom"
        outfit.description = outfit_description_en
        outfit.base_description = outfit_description_it
        outfit.base_sd_prompt = outfit_description_en
        outfit.llm_generated_description = None
        outfit.llm_generated_sd_prompt = None
        outfit.components.clear()
        outfit.modifications.clear()
        outfit.is_special = False

        game_state.set_outfit(outfit)

        print(f"[OutfitModifier] MAJOR CHANGE: {old_style} -> custom")
        print(f"[OutfitModifier] IT: {outfit_description_it[:60]}...")
        print(f"[OutfitModifier] EN: {outfit_description_en[:60]}...")
        return True

    def change_random_outfit(self, game_state: "GameState", companion_def) -> Optional[str]:
        """Change to a random wardrobe outfit.

        Called by the UI "Cambia" button (via luna/ui/ handlers).

        Args:
            game_state: Current game state
            companion_def: Companion definition with wardrobe

        Returns:
            New outfit style name or None
        """
        if not companion_def or not getattr(companion_def, "wardrobe", None):
            return None

        import random
        outfits = list(companion_def.wardrobe.keys())
        current = game_state.get_outfit().style
        available = [o for o in outfits if o != current] or outfits

        new_outfit = random.choice(available)
        self._apply_wardrobe_outfit(game_state, new_outfit, companion_def)
        print(f"[OutfitModifier] Random change: {current} -> {new_outfit}")
        return new_outfit

    async def change_custom_outfit(
        self,
        game_state: "GameState",
        description_it: str,
        llm_manager=None,
    ) -> str:
        """Change to a custom outfit from a text description.

        Called by the UI "Modifica" button.

        Args:
            game_state: Current game state
            description_it: Italian outfit description
            llm_manager: For translation

        Returns:
            Final English outfit description
        """
        await self.apply_major_change(game_state, description_it, llm_manager)
        return game_state.get_outfit().description

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _detect_modifications(self, text: str) -> List[Tuple[str, str]]:
        """Detect (component, state) modifications from input text.

        Uses direct-phrase fast path first, then two-step type+component matching.
        Returns a list of (component, state) tuples with no duplicates per component.
        """
        detected: Dict[str, str] = {}  # component -> state (first match wins)
        lower = text.lower()

        # Fast path: direct phrases
        for entry in self._direct_compiled:
            if entry["pattern"].search(lower):
                comp = entry["component"]
                if comp not in detected:
                    detected[comp] = entry["state"]

        # Two-step: mod-type + component
        for mod_type, type_patterns in self._type_compiled.items():
            if not any(p.search(lower) for p in type_patterns):
                continue
            allowed = MOD_APPLIES_TO.get(mod_type, [])
            for component in allowed:
                if component in detected:
                    continue
                comp_patterns = self._comp_compiled.get(component, [])
                if any(p.search(lower) for p in comp_patterns):
                    detected[component] = mod_type

        return list(detected.items())

    def _apply_modifications(
        self,
        outfit: "OutfitState",
        modifications: List[Tuple[str, str]],
        turn: int,
        companion_def=None,
    ) -> None:
        """Apply a list of (component, state) modifications to the outfit."""
        from luna.core.models import OutfitModification
        from luna.systems.outfit_renderer import (
            MODIFICATION_DESCRIPTIONS_IT,
            MODIFICATION_DESCRIPTIONS_SD,
        )

        for component, state in modifications:
            desc_it = MODIFICATION_DESCRIPTIONS_IT.get(component, {}).get(
                state, f"{component} {state}"
            )
            desc_sd = MODIFICATION_DESCRIPTIONS_SD.get(component, {}).get(
                state, f"{component} {state}"
            )

            mod = OutfitModification(
                component=component,
                state=state,
                description=desc_it,
                sd_description=desc_sd,
                applied_at_turn=turn,
            )

            if state == "added" and component in outfit.modifications:
                # Restore: remove the previous removal/modification
                del outfit.modifications[component]
            else:
                outfit.modifications[component] = mod

        # Rebuild legacy description field using the SD prompt (English)
        # so that media/builders.py (which uses outfit.description for SD) stays correct.
        from luna.systems.outfit_renderer import OutfitRenderer
        outfit.description = OutfitRenderer.render_sd_prompt(outfit, companion_def)

    def _apply_wardrobe_outfit(
        self,
        game_state: "GameState",
        outfit_key: str,
        companion_def,
    ) -> None:
        """Apply a wardrobe outfit (by key) to the game state."""
        from luna.core.models import OutfitState
        wardrobe_def = companion_def.wardrobe[outfit_key]

        if isinstance(wardrobe_def, str):
            new_outfit = OutfitState(
                style=outfit_key,
                description=wardrobe_def,
                base_description=wardrobe_def,
                base_sd_prompt=wardrobe_def,
            )
        else:
            desc = getattr(wardrobe_def, "description", "") or outfit_key
            sd = getattr(wardrobe_def, "sd_prompt", "") or desc
            new_outfit = OutfitState(
                style=outfit_key,
                description=desc,
                base_description=desc,
                base_sd_prompt=sd,
                is_special=bool(getattr(wardrobe_def, "special", False)),
            )

        game_state.set_outfit(new_outfit)

    # -------------------------------------------------------------------------
    # Major-change detection
    # -------------------------------------------------------------------------

    def _is_major_change(self, user_input: str) -> Tuple[bool, str]:
        """Detect if the user wants a complete outfit replacement.

        Returns:
            (is_major, italian_description)
        """
        lower = user_input.lower()
        for pattern in self._major_compiled:
            if pattern.search(lower):
                return True, self._extract_outfit_description(user_input)
        return False, ""

    def _extract_outfit_description(self, user_input: str) -> str:
        """Extract a concise outfit description from the user's input."""
        patterns = [
            r"mette\s+(?:un|una)\s+(?:altro|nuovo|diverso)?\s*([\w\s]+?)(?:\s+(?:abito|vestito|outfit))?[.,!?]?$",
            r"si\s+cambia\s+(?:con\s+|in\s+)?([\w\s]+?)(?:[.,!?]|$)",
            r"vestito\s+([\w\s]+?)(?:[.,!?]|$)",
            r"abito\s+([\w\s]+?)(?:[.,!?]|$)",
            r"indossa\s+(?:un|una)?\s*([\w\s]+?)(?:[.,!?]|$)",
        ]
        lower = user_input.lower()
        for pattern in patterns:
            match = re.search(pattern, lower, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 3:
                    return desc
        return user_input

    # -------------------------------------------------------------------------
    # Translation (IT → EN for SD prompt)
    # -------------------------------------------------------------------------

    async def _translate_outfit(self, description_it: str, llm_manager) -> str:
        """Translate Italian outfit description to English using LLM."""
        basic = self._basic_translate(description_it)
        try:
            prompt = (
                f"Translate this clothing description from Italian to English.\n"
                f"Be concise and use fashion/Stable Diffusion terminology.\n\n"
                f"Italian: {description_it}\nEnglish:"
            )
            response = await llm_manager.generate(
                system_prompt="Translate Italian clothing descriptions to English concisely.",
                user_input=prompt,
                json_mode=False,
            )
            if response and response.text:
                translated = response.text.strip()
                error_indicators = [
                    "mi scusi", "errore", "spiacente", "non posso",
                    "i'm sorry", "error", "cannot",
                ]
                if (
                    not any(ind in translated.lower() for ind in error_indicators)
                    and len(translated) > 5
                ):
                    return translated
        except Exception as e:
            print(f"[OutfitModifier] LLM translation failed: {e}")
        return basic

    def _basic_translate(self, text: str) -> str:
        """Basic Italian → English word substitution for common outfit terms."""
        translations = {
            "vestito": "dress", "abito": "dress", "gonna": "skirt",
            "camicia": "shirt", "blusa": "blouse", "maglia": "sweater",
            "scarpe": "shoes", "tacchi": "high heels", "calze": "stockings",
            "collant": "pantyhose", "reggiseno": "bra", "mutande": "panties",
            "perizoma": "thong", "giacca": "jacket", "blazer": "blazer",
            "cravatta": "tie", "rosso": "red", "rossa": "red", "blu": "blue",
            "nero": "black", "nera": "black", "bianco": "white", "bianca": "white",
            "verde": "green", "giallo": "yellow", "rosa": "pink",
            "viola": "purple", "arancione": "orange", "grigio": "grey",
            "marrone": "brown", "elegante": "elegant", "sera": "evening",
            "formale": "formal", "casual": "casual", "sportivo": "sportswear",
            "sexy": "sexy", "mini": "mini", "corto": "short", "corta": "short",
            "lungo": "long", "lunga": "long", "aderente": "tight",
            "scollato": "low-cut", "scollata": "low-cut",
            "trasparente": "see-through", "pigiama": "pajamas",
            "bikini": "bikini", "kimono": "kimono", "lingerie": "lingerie",
            "intimo": "underwear", "uniforme": "uniform", "costume": "swimsuit",
            "da sera": "evening gown", "da bagno": "swimsuit", "da notte": "nightgown",
            "strappato": "torn", "strappata": "torn", "bagnato": "wet",
            "bagnata": "wet", "aperto": "open", "aperta": "open",
            "sbottonato": "unbuttoned", "sbottonata": "unbuttoned",
            "slacciato": "loose", "slacciata": "loose",
            "senza": "without", "nudo": "nude", "nuda": "nude",
        }
        result = text.lower()
        for it_word, en_word in translations.items():
            result = re.sub(
                rf"\b{re.escape(it_word)}\b", en_word, result, flags=re.IGNORECASE
            )
        return (result[0].upper() + result[1:]).strip() if result else result


# Factory function for easy initialization
def create_outfit_modifier() -> OutfitModifierSystem:
    """Create a new outfit modifier system instance."""
    return OutfitModifierSystem()
