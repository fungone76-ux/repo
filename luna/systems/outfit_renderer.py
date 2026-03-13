"""Outfit Renderer - Generates final outfit descriptions from OutfitState.

Combines the base outfit with overlay modifications to produce:
- Italian description for LLM context
- English SD prompt for image generation

Three outfit tiers are supported:
1. Wardrobe-based: base_description + base_sd_prompt (set from YAML wardrobe)
2. LLM-generated: llm_generated_description + llm_generated_sd_prompt (custom)
3. Legacy: description field (backward compatibility)

In all cases overlay modifications (OutfitModification) are appended.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from luna.core.models import OutfitState


# =============================================================================
# Modification descriptions - Italian (for LLM context)
# =============================================================================

MODIFICATION_DESCRIPTIONS_IT: dict[str, dict[str, str]] = {
    "shoes": {
        "removed": "piedi nudi",
        "wet": "scarpe bagnate",
        "added": "scarpe ai piedi",
    },
    "top": {
        "removed": "seno nudo, senza top",
        "partial_unbuttoned": "camicia sbottonata, scollatura visibile",
        "wet": "top bagnato trasparente",
        "added": "top indossato",
    },
    "bra": {
        "removed": "senza reggiseno, seno libero",
        "see_through": "reggiseno visibile sotto il tessuto",
        "added": "reggiseno indossato",
    },
    "outerwear": {
        "removed": "senza giacca",
        "added": "giacca indossata",
    },
    "bottom": {
        "removed": "gambe nude, senza gonna/pantaloni",
        "lifted": "gonna sollevata, cosce scoperte",
        "lowered": "pantaloni abbassati",
        "wet": "gonna/pantaloni bagnati",
        "added": "gonna/pantaloni indossati",
    },
    "panties": {
        "removed": "senza mutande",
        "lowered": "mutande abbassate",
        "added": "mutande indossate",
    },
    "pantyhose": {
        "removed": "gambe nude, senza collant",
        "torn": "collant strappati, smagliature sulle cosce",
        "pulled_down": "collant abbassati attorno alle caviglie",
        "added": "collant indossati",
    },
    "dress": {
        "wet": "vestito bagnato trasparente",
        "open": "vestito aperto sul davanti",
        "lifted": "vestito sollevato, fianchi scoperti",
    },
}


# =============================================================================
# Modification descriptions - English (for SD prompt / image generation)
# =============================================================================

MODIFICATION_DESCRIPTIONS_SD: dict[str, dict[str, str]] = {
    "shoes": {
        "removed": "barefoot, bare feet visible",
        "wet": "wet shoes",
        "added": "shoes on",
    },
    "top": {
        "removed": "topless, bare chest",
        "partial_unbuttoned": "unbuttoned shirt, cleavage visible",
        "wet": "wet shirt, see-through fabric clinging to skin",
        "added": "shirt on",
    },
    "bra": {
        "removed": "no bra, breasts free",
        "see_through": "bra visible through wet fabric",
        "added": "bra on",
    },
    "outerwear": {
        "removed": "no jacket",
        "added": "jacket on",
    },
    "bottom": {
        "removed": "bottomless, bare legs",
        "lifted": "skirt lifted high, thighs exposed",
        "lowered": "pants pulled down",
        "wet": "wet skirt or pants",
        "added": "skirt or pants on",
    },
    "panties": {
        "removed": "no panties",
        "lowered": "panties pulled down",
        "added": "panties on",
    },
    "pantyhose": {
        "removed": "bare legs, no stockings",
        "torn": "torn black pantyhose, runs on thighs",
        "pulled_down": "pantyhose pulled down around ankles",
        "added": "pantyhose on",
    },
    "dress": {
        "wet": "wet dress, see-through clinging fabric",
        "open": "dress unzipped, open front",
        "lifted": "dress lifted up, gathered at waist",
    },
}


# =============================================================================
# OutfitRenderer
# =============================================================================

class OutfitRenderer:
    """Renders outfit descriptions by combining base outfit + overlay modifications.

    All methods are static - no instance state needed.
    """

    @staticmethod
    def render_description(outfit: "OutfitState", companion_def=None) -> str:
        """Generate full Italian description for LLM context.

        Priority for base:
        1. LLM-generated description (custom outfit requested by player)
        2. base_description (loaded from wardrobe YAML)
        3. Legacy description field
        4. Wardrobe lookup via companion_def

        Active modifications are appended as a comma-separated overlay.

        Args:
            outfit: Current OutfitState
            companion_def: Optional companion definition for wardrobe lookup fallback

        Returns:
            Italian outfit description string
        """
        if outfit.is_special:
            return (
                outfit.llm_generated_description
                or outfit.base_description
                or outfit.description
                or f"special state: {outfit.style}"
            )

        base = OutfitRenderer._get_base_description_it(outfit, companion_def)

        if outfit.modifications:
            mod_parts = [
                m.description
                for m in outfit.modifications.values()
                if m.description
            ]
            if mod_parts:
                return f"{base}, {', '.join(mod_parts)}"

        return base

    @staticmethod
    def render_sd_prompt(outfit: "OutfitState", companion_def=None) -> str:
        """Generate English SD prompt for image generation.

        Priority for base:
        1. LLM-generated SD prompt (custom outfit)
        2. base_sd_prompt (from wardrobe YAML)
        3. Legacy description field
        4. Wardrobe lookup via companion_def

        Active modifications are appended.

        Args:
            outfit: Current OutfitState
            companion_def: Optional companion definition for wardrobe lookup fallback

        Returns:
            English SD prompt string
        """
        if outfit.is_special:
            return (
                outfit.llm_generated_sd_prompt
                or outfit.base_sd_prompt
                or outfit.description
                or outfit.style
            )

        base = OutfitRenderer._get_base_sd_prompt(outfit, companion_def)

        if outfit.modifications:
            mod_parts = []
            for component, mod in outfit.modifications.items():
                sd_desc = mod.sd_description
                if not sd_desc:
                    sd_desc = MODIFICATION_DESCRIPTIONS_SD.get(component, {}).get(
                        mod.state, mod.description
                    )
                if sd_desc:
                    mod_parts.append(sd_desc)
            if mod_parts:
                return f"{base}, {', '.join(mod_parts)}"

        return base

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_base_description_it(outfit: "OutfitState", companion_def=None) -> str:
        """Return the best available Italian base description."""
        if outfit.llm_generated_description:
            return outfit.llm_generated_description
        if outfit.base_description:
            return outfit.base_description
        if outfit.description:
            return outfit.description
        if companion_def and getattr(companion_def, "wardrobe", None):
            wardrobe_def = companion_def.wardrobe.get(outfit.style)
            if wardrobe_def is not None:
                if isinstance(wardrobe_def, str):
                    return wardrobe_def
                return getattr(wardrobe_def, "description", "") or outfit.style
        return f"{outfit.style} outfit"

    @staticmethod
    def _get_base_sd_prompt(outfit: "OutfitState", companion_def=None) -> str:
        """Return the best available English SD prompt base."""
        if outfit.llm_generated_sd_prompt:
            return outfit.llm_generated_sd_prompt
        if outfit.base_sd_prompt:
            return outfit.base_sd_prompt
        if companion_def and getattr(companion_def, "wardrobe", None):
            wardrobe_def = companion_def.wardrobe.get(outfit.style)
            if wardrobe_def is not None:
                if isinstance(wardrobe_def, str):
                    return wardrobe_def
                return (
                    getattr(wardrobe_def, "sd_prompt", "")
                    or getattr(wardrobe_def, "description", "")
                    or outfit.style
                )
        if outfit.description:
            return outfit.description
        return f"{outfit.style} outfit"

    @staticmethod
    def get_modification_description_it(component: str, state: str) -> str:
        """Look up the Italian description for a (component, state) pair."""
        return MODIFICATION_DESCRIPTIONS_IT.get(component, {}).get(
            state, f"{component} {state}"
        )

    @staticmethod
    def get_modification_description_sd(component: str, state: str) -> str:
        """Look up the English SD description for a (component, state) pair."""
        return MODIFICATION_DESCRIPTIONS_SD.get(component, {}).get(
            state, f"{component} {state}"
        )
