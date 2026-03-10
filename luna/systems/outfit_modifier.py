"""Outfit Modifier System - Deterministic clothing changes based on player input.

This module provides a standalone system for detecting and applying outfit
modifications based on player input. It works independently from the LLM,
ensuring that visual changes are deterministic and persistent.

Usage:
    In GameEngine.__init__:
        self.outfit_modifier = OutfitModifierSystem()
    
    In GameEngine.process_turn:
        self.outfit_modifier.process_turn(user_input, game_state)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from luna.core.models import GameState, OutfitState


class ModificationType(str, Enum):
    """Type of outfit modification."""
    REMOVED = "removed"
    PARTIAL = "partial"
    DAMAGED = "damaged"
    SPECIAL = "special"
    ADDED = "added"


@dataclass
class OutfitChange:
    """Single outfit change detected."""
    component: str
    new_value: str
    mod_type: ModificationType
    description: str
    confidence: float = 1.0


class OutfitModifierSystem:
    """Standalone outfit modification system.
    
    Parses player input for clothing modifications and applies them
    to the game state. Designed to be called once per turn.
    """
    
    # ===================================================================
    # PATTERN DEFINITIONS - Italian
    # ===================================================================
    
    PATTERNS: Dict[str, Dict[str, List[str]]] = {
        # SHOES - Espansi con molti più pattern
        "shoes": {
            "remove": [
                # Pattern base
                r"\b(senza\s+scarp[ae]|scalz[ao]|piedi\s+nudi|nud[ao]\s+ai\s+piedi)\b",
                r"\b(tol[gt]a?\s+(le\s+)?scarp[ae]|levat[ae]?\s+(le\s+)?scarp[ae]|sfilat[ae]?\s+(le\s+)?scarp[ae])\b",
                r"\b(tol[gt]a?\s+(una\s+)?scarpa|levat[ae]?\s+(una\s+)?scarpa)\b",
                r"\b(rimoss[ae]?\s+(le\s+)?scarpe|togli\s+(le\s+)?scarpe)\b",
                r"\b(scarp[ae]\s+(tolte?|levate?|rimosse?)|hai\s+tolto\s+(le\s+|una\s+)?scarp[ae])\b",
                r"\b(si\s+[eè]\s+tolta\s+(una\s+|la\s+)?scarpa)\b",
                # Pattern narrativi (LLM response)
                r"\b(si\s+sfil[ao]\s+(le\s+)?scarp[ae]|sfil[ao]\s+(le\s+)?scarp[ae])\b",
                r"\b(si\s+leva\s+(le\s+)?scarp[ae]|lev[aà]\s+(le\s+)?scarp[ae])\b",
                r"\b(scarp[ae]\s+(sfilate|levarse|torsesi)|lasci[ao]\s+(le\s+)?scarp[ae])\b",
                r"\b(piedi\s+nud[io]|resta\s+scalz[ao]|rimane\s+scalz[ao])\b",
                r"\b(si\s+liber[ao]\s+(dei\s+piedi|dai\s+piedi)|liber[ao]\s+i\s+piedi)\b",
                r"\b(calz[ae]?\s+(tolte?|sfilate?)|calzini\s+(tolti?|sfilati?))\b",
                r"\b(tacchi\s+(tolti?|sfilati?)|si\s+togli[eè]\s+i\s+tacchi)\b",
            ],
            "add": [
                # Pattern base
                r"\b(rimett[aoe]?\s+(le\s+)?scarpe|indoss[aoe]?\s+(le\s+)?scarpe|mett[aoe]?\s+(le\s+)?scarpe)\b",
                r"\b(rimett[aoe]?\s+(una\s+)?scarpa|indoss[aoe]?\s+(una\s+)?scarpa)\b",
                r"\b(scarpe\s+(ai\s+piedi|rimesse|indossate))\b",
                # Pattern narrativi (LLM response)
                r"\b(si\s+rimett[aoe]?\s+(le\s+)?scarp[ae]|rimett[aoe]?\s+(le\s+)?scarp[ae])\b",
                r"\b(scarp[ae]\s+(rimesse|rimettersi|rimesse))\b",
                r"\b(indoss[ao]\s+di\s+nuovo\s+(le\s+)?scarp[ae])\b",
                r"\b(riprende\s+(le\s+)?scarp[ae]|prende\s+(le\s+)?scarp[ae])\b",
                r"\b(si\s+veste\s+(le\s+)?scarp[ae]|calz[ao]\s+(le\s+)?scarp[ae])\b",
                r"\b(mette\s+(i\s+)?tacchi|indossa\s+(i\s+)?tacchi)\b",
            ],
            "values": {"remove": "barefoot", "add": "elegant high heels"}
        },
        
        # OUTERWEAR
        "outerwear": {
            "remove": [
                r"\b(senza\s+(giacca|blazer|cardigan|coprispalle|paletot))\b",
                r"\b(tol[gt]a?\s+(la\s+)?(giacca|blazer|cardigan)|levat[ae]?\s+(la\s+)?(giacca|blazer))\b",
                r"\b(rimoss[ae]?\s+(la\s+)?(giacca|blazer)|togli\s+(la\s+)?(giacca|blazer))\b",
                r"\b(giacca\s+(tolta|levata|aperta|rimossa)|giacca\s+su\s+spalliera)\b",
                r"\b(svestit[ao]\s+(della\s+)?(giacca|blazer))\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(la\s+)?(giacca|blazer)|indoss[aoe]?\s+(la\s+)?(giacca|blazer))\b",
                r"\b(mett[aoe]?\s+(la\s+)?(giacca|blazer)|chius[ao]\s+(la\s+)?(giacca|blazer))\b",
            ],
            "values": {"remove": "none", "add": "blue blazer"}
        },
        
        # TOP / SHIRT - Espansi
        "top": {
            "unbutton": [
                r"\b(camicia\s+sbottonata|camici[ao]\s+apert[ao]|scollatura\s+aperta)\b",
                r"\b(sbottonat[ae]?\s+(la\s+)?camicia|apert[ae]?\s+(la\s+)?camicia)\b",
                r"\b(bottoni\s+(aperti|slacciati|staccati)|camicia\s+slacciata)\b",
                r"\b(downblouse|scollatura\s+profonda|scollo\s+a\s+V\s+aperto)\b",
                r"\b(camicia\s+che\s+scivola|spalle\s+scoperte|scollatura\s+laterale)\b",
                r"\b(sideboob\s+della\s+camicia|seno\s+laterale\s+visibile)\b",
                # Pattern narrativi LLM
                r"\b(si\s+sbotton[a]\s+(la\s+)?camicia|sbotton[a]\s+(la\s+)?camicia)\b",
                r"\b(apr[a]\s+(la\s+)?camicia|apr[a]\s+i\s+bottoni)\b",
                r"\b(camicia\s+(aperta|sbottonata|slacciata))\b",
                r"\b(bottoni\s+della\s+camicia\s+aperti)\b",
            ],
            "remove": [
                r"\b(senza\s+(camicia|maglia|top|blusa)|camicia\s+tolta)\b",
                r"\b(tol[gt]a?\s+(la\s+)?(camicia|maglia|top)|levat[ae]?\s+(la\s+)?(camicia|maglia))\b",
                r"\b(nud[ao]\s+(dal\s+busto\s+in\s+su|in\s+alto)|torace\s+nudo)\b",
                # Pattern narrativi LLM
                r"\b(si\s+togli[eè]\s+(la\s+)?camicia|toglie\s+(la\s+)?camicia)\b",
                r"\b(si\s+togli[eè]\s+(il\s+)?top|toglie\s+(il\s+)?top)\b",
                r"\b(si\s+togli[eè]\s+(la\s+)?maglia|toglie\s+(la\s+)?maglia)\b",
                r"\b(camicia\s+(tolta|sfilata|levata|rimossa))\b",
                r"\b(top\s+(tolto|sfilato|levato|rimosso))\b",
                r"\b(maglia\s+(tolta|sfilata|levata|rimossa))\b",
                r"\b(senza\s+(la\s+)?camicia|rimane\s+senza\s+camicia)\b",
                r"\b(torace\s+nudo|seno\s+nudo|seni\s+nudi)\b",
                r"\b(si\s+spogli[a]\s+(del\s+)?top|spogliarsi\s+(del\s+)?top)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(la\s+)?(camicia|maglia|top)|indoss[aoe]?\s+(la\s+)?(camicia|maglia))\b",
                r"\b(camicia\s+(chiusa|bottonata|indossata))\b",
                # Pattern narrativi LLM
                r"\b(si\s+rimett[aoe]?\s+(la\s+)?camicia|rimett[aoe]?\s+(la\s+)?camicia)\b",
                r"\b(indoss[ao]\s+di\s+nuovo\s+(la\s+)?camicia)\b",
                r"\b(riprende\s+(la\s+)?camicia|prende\s+(la\s+)?camicia)\b",
                r"\b(mette\s+(la\s+)?camicia|si\s+veste\s+(la\s+)?camicia)\b",
                r"\b(chiud[a]\s+(la\s+)?camicia|botton[a]\s+(la\s+)?camicia)\b",
                r"\b(camicia\s+rimesa|camicia\s+indossata)\b",
            ],
            "values": {
                "unbutton": "unbuttoned white shirt, cleavage visible",
                "remove": "none",
                "add": "white button-up blouse"
            }
        },
        
        # BRA
        "bra": {
            "remove": [
                r"\b(senza\s+(reggiseno|bra|reggipetto)|reggiseno\s+tolto)\b",
                r"\b(tol[gt][ao]?\s+(il\s+)?(reggiseno|bra)|lev[oa]\s+(il\s+)?(reggiseno|bra))\b",
                r"\b(nud[ao]\s+sotto|sotto\s+senza\s+niente|seno\s+libero)\b",
                r"\b(ventaglio|sideboob\s+visible|seno\s+laterale\s+visibile)\b",
                r"\b(tette\s+libere|seno\s+scoperto|sotto\s+nuda)\b",
            ],
            "see_through": [
                r"\b(reggiseno\s+trasparente|camicia\s+bagnata\s+trasparente|vedo\s+(il\s+)?reggiseno)\b",
                r"\b(nipples?\s+visible|capezzoli\s+visibili|turgidi\s+sotto\s+camicia)\b",
                r"\b(see[\s\-]?through|trasparente|bagnata\s+trasparente)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(il\s+)?(reggiseno|bra)|indoss[aoe]?\s+(il\s+)?(reggiseno|bra))\b",
            ],
            "values": {
                "remove": "none",
                "see_through": "lace bra visible through shirt",
                "add": "white lace bra"
            }
        },
        
        # PANTIES
        "panties": {
            "remove": [
                r"\b(senza\s+(mutande|perizoma|slip|intimo)|nud[ao]\s+sotto)\b",
                r"\b(tol[gt][ao]?\s+(le\s+)?(mutande|perizoma)|lev[oa]\s+(le\s+)?(mutande|perizoma))\b",
                r"\b(mutande\s+(tolte|calate|giù)|perizoma\s+rimosso)\b",
                r"\b(giù\s+(le\s+)?mutande|abbass[ao](le\s+)?mutande)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(le\s+)?(mutande|perizoma)|indoss[aoe]?\s+(le\s+)?(mutande|perizoma))\b",
            ],
            "values": {"remove": "none", "add": "white lace panties"}
        },
        
        # PANTYHOSE
        "pantyhose": {
            "remove": [
                r"\b(senza\s+(calze|collant|autoreggenti)|gambe\s+nude)\b",
                r"\b(tol[gt][ao]?\s+(le\s+)?(calze|collant)|lev[oa]\s+(le\s+)?(calze|collant))\b",
                r"\b(calze\s+(tolte|levate)|collant\s+rimosso)\b",
            ],
            "torn": [
                r"\b(calze\s+strappate|collant\s+strappato|strapp[aoi]\s+(nelle\s+)?calze|strappo\s+(le\s+)?calze)\b",
                r"\b(strapp[aoi]\s+sulle\s+gambe|calze\s+rotte|laddered\s+pantyhose)\b",
                r"\b(strappo\s+(sulla\s+coscia|in\s+alto)|velo\s+strappato)\b",
            ],
            "pulled_down": [
                r"\b(calze\s+calate|collant\s+calato|calze\s+abbassate|autoreggenti\s+calate)\b",
                r"\b(calze\s+attorno\s+(alle\s+caviglie|ai\s+piedi)|collant\s+arrotolato)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(le\s+)?(calze|collant)|indoss[aoe]?\s+(le\s+)?(calze|collant))\b",
            ],
            "values": {
                "remove": "none",
                "torn": "torn black pantyhose, runs on thighs",
                "pulled_down": "pantyhose pulled down around ankles",
                "add": "sheer black pantyhose"
            }
        },
        
        # BOTTOM - Espansi con molti più pattern
        "bottom": {
            "lift": [
                r"\b(gonna\s+sollevata|gonna\s+corta|sotto\s+la\s+gonna|upskirt)\b",
                r"\b(sollev[ao]\s+(la\s+)?gonna|alz[oa]\s+(la\s+)?gonna|gonna\s+rintracciata)\b",
                r"\b(gonna\s+da\s+sotto|vista\s+da\s+sotto\s+la\s+gonna|alzo\s+(la\s+)?gonna)\b",
                # Pattern narrativi LLM
                r"\b(si\s+solleva\s+(la\s+)?gonna|solleva\s+(la\s+)?gonna)\b",
                r"\b(gonna\s+(sollevarsi|alzarsi|accorciarsi))\b",
                r"\b(alz[ao]\s+(la\s+)?gonna\s+da\s+sotto)\b",
            ],
            "lower": [
                r"\b(pantaloni\s+abbassati|pantaloni\s+giù|jeans\s+abbassati)\b",
                r"\b(abbass[ao]\s+(i\s+)?pantaloni|cal[oa]\s+(i\s+)?pantaloni)\b",
                r"\b(zip\s+(aperta|giù)|cerniera\s+aperta|pantaloni\s+aperti)\b",
                # Pattern narrativi LLM
                r"\b(si\s+abbassa\s+(i\s+)?pantaloni|abbassa\s+(i\s+)?pantaloni)\b",
            ],
            "remove": [
                r"\b(senza\s+(gonna|pantaloni|pantaloncini)|gonna\s+tolta)\b",
                r"\b(tol[gt][ao]?\s+(la\s+)?(gonna|skirt)|lev[oa]\s+(la\s+)?(gonna|skirt))\b",
                r"\b(nud[ao]\s+(dai\s+fianchi\s+in\s+giù|in\s+basso))\b",
                # Pattern narrativi LLM - gonne
                r"\b(si\s+togli[eè]\s+(la\s+)?gonna|toglie\s+(la\s+)?gonna)\b",
                r"\b(si\s+sfil[a]\s+(la\s+)?gonna|sfil[a]\s+(la\s+)?gonna)\b",
                r"\b(si\s+leva\s+(la\s+)?gonna|leva\s+(la\s+)?gonna)\b",
                r"\b(gonna\s+(sfilata|tolta|levata|rimossa)|lasci[a]\s+(la\s+)?gonna)\b",
                r"\b(senza\s+(la\s+)?gonna|rimane\s+senza\s+gonna)\b",
                r"\b(si\s+libera\s+(della\s+)?gonna)\b",
                r"\b(gonna\s+(scivol[a]\s+giù|cade|scende))\b",
                # Pattern pantaloni
                r"\b(si\s+togli[eè]\s+(i\s+)?pantaloni|toglie\s+(i\s+)?pantaloni)\b",
                r"\b(si\s+sfil[a]\s+(i\s+)?pantaloni|sfil[a]\s+(i\s+)?pantaloni)\b",
                r"\b(pantaloni\s+(tolti|sfilati|levati|rimossi))\b",
                r"\b(senza\s+(i\s+)?pantaloni|rimane\s+senza\s+pantaloni)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(la\s+)?(gonna|skirt)|indoss[aoe]?\s+(la\s+)?(gonna|skirt))\b",
                r"\b(gonna\s+(rimessa|indossata|calata))\b",
                # Pattern narrativi LLM
                r"\b(si\s+rimett[aoe]?\s+(la\s+)?gonna|rimett[aoe]?\s+(la\s+)?gonna)\b",
                r"\b(si\s+rimett[aoe]?\s+(i\s+)?pantaloni|rimett[aoe]?\s+(i\s+)?pantaloni)\b",
                r"\b(indoss[ao]\s+di\s+nuovo\s+(la\s+)?gonna)\b",
                r"\b(riprende\s+(la\s+)?gonna|prende\s+(la\s+)?gonna)\b",
                r"\b(mette\s+(la\s+)?gonna|si\s+veste\s+(la\s+)?gonna)\b",
                r"\b(calz[a]\s+(la\s+)?gonna|si\s+cal[a]\s+(la\s+)?gonna)\b",
                r"\b(pantaloni\s+(rimesse|rimessi|indossati))\b",
            ],
            "values": {
                "lift": "pleated skirt lifted up, exposed",
                "lower": "charcoal grey pencil skirt lowered",
                "remove": "none",
                "add": "charcoal grey pencil skirt"
            }
        },
        
        # TIE
        "tie": {
            "loosen": [
                r"\b(cravatta\s+allentata|cravatta\s+slacciata|cravatta\s+storta)\b",
                r"\b(allent[ao]\s+(la\s+)?cravatta|slacci[ao]\s+(la\s+)?cravatta)\b",
                r"\b(cravatta\s+aperta|nodo\s+allentato)\b",
            ],
            "remove": [
                r"\b(senza\s+cravatta|cravatta\s+tolta|levata\s+(la\s+)?cravatta)\b",
                r"\b(tol[gt][ao]?\s+(la\s+)?cravatta|togli\s+(la\s+)?cravatta)\b",
            ],
            "add": [
                r"\b(rimett[aoe]?\s+(la\s+)?cravatta|sistema\s+(la\s+)?cravatta)\b",
                r"\b(cravatta\s+(stretta|a\s+posto|indossata))\b",
            ],
            "values": {
                "loosen": "loose red ribbon tie, slightly undone",
                "remove": "none",
                "add": "red ribbon tie, neatly tied"
            }
        },
        
        # DRESS
        "dress": {
            "slip": [
                r"\b(vestito\s+che\s+scivola|spalline\s+cadute|vestito\s+abbassato)\b",
                r"\b(scollatura\s+caduta|vestito\s+sfuggente|abito\s+scollato\s+di\s+lato)\b",
                r"\b(sideboob\s+da\s+vestito|seno\s+laterale\s+fuori)\b",
            ],
            "lift": [
                r"\b(vestito\s+sollevato|gonna\s+(del\s+)?vestito\s+su|sotto\s+il\s+vestito)\b",
                r"\b(vestito\s+arrotolato|orlo\s+sollevato|sollev[ao]\s+(il\s+)?vestito)\b",
            ],
            "open": [
                r"\b(vestito\s+aperto|cerniera\s+(aperta|giù)|bottoni\s+aperti)\b",
                r"\b(abito\s+aperto\s+sul\s+davanti|vestito\s+spalancato|apr[io]\s+(il\s+)?vestito)\b",
            ],
            "wet": [
                r"\b(vestito\s+bagnato|abito\s+inzuppato|bagnata\s+fradicia)\b",
                r"\b(trasparente\s+per\s+il\s+bagnato|vedo\s+tutto\s+bagnato)\b",
            ],
            "values": {
                "slip": "dress slipping off shoulder, sideboob visible",
                "lift": "dress lifted up, gathered at waist",
                "open": "dress unzipped, open front",
                "wet": "wet dress, see-through fabric clinging"
            }
        },
        
        # ACCESSORIES
        "accessories": {
            "remove_glasses": [
                r"\b(senza\s+occhiali|occhiali\s+(tolti|levati)|rimoss[oi]\s+occhiali)\b",
                r"\b(tol[gt][io]?\s+(gli\s+)?occhiali|lev[oa]\s+(gli\s+)?occhiali)\b",
            ],
            "add_glasses": [
                r"\b(occhiali\s+(addosso|indossati|rimessi)|rimett[aoe]?\s+(gli\s+)?occhiali)\b",
            ],
            "remove_jewelry": [
                r"\b(senza\s+(gioielli|collana|orecchini)|collana\s+tolta)\b",
                r"\b(tol[gt]a?\s+(la\s+)?collana|levat[ae]?\s+(la\s+)?collana)\b",
            ],
            "values": {
                "remove_glasses": "no glasses",
                "add_glasses": "wearing glasses",
                "remove_jewelry": "no jewelry"
            }
        },
        
        # SPECIAL
        "special": {
            "downblouse": [
                r"\b(downblouse|scollatura\s+da\s+sopra|vedo\s+da\s+sopra|vista\s+dall'alto\s+scollatura)\b",
                r"\b(penso\s+nella\s+scollatura|sguardo\s+nella\s+scollatura|cade\s+lo\s+sguardo)\b",
                r"\b(scollatura\s+profonda\s+vista\s+dall'alto|tette\s+viste\s+dall'alto)\b",
            ],
            "cameltoe": [
                r"\b(cameltoe|taglio\s+visibile|intimo\s+segnato|pantaloni\s+attillati\s+intimo)\b",
                r"\b(camel\s+toe|silhouette\s+intimo|mutande\s+segnate)\b",
            ],
            "pokies": [
                r"\b(pokies?|capezzoli\s+turgidi\s+visibili|tette\s+punzecchiate|seno\s+in\s+evidenza)\b",
                r"\b(nipples?\s+hard|turgidi\s+sotto\s+(camicia|vestito)|bust\s+pointing)\b",
            ],
            "values": {
                "downblouse": "downblouse view, cleavage from above",
                "cameltoe": "tight skirt, cameltoe visible",
                "pokies": "nipples hard and visible through fabric"
            }
        },
    }
    
    # MAJOR CHANGE patterns - trigger complete outfit replacement
    MAJOR_CHANGE_PATTERNS: Dict[str, List[str]] = {
        "change_outfit": [
            r"\b(si\s+cambia|cambia\s+(vestito|abito|outfit)|mette\s+(un\s+)?(altro|nuovo))\b",
            r"\b(vestito\s+da\s+sera|abito\s+da\s+sera|evening\s+gown|dress\s+da\s+sera)\b",
            r"\b(abito\s+rosso|vestito\s+rosso|red\s+dress)\b",
            r"\b(pigiama|pajamas|sleepwear|notte)\b",
            r"\b(bikini|costume\s+da\s+bagno|swimsuit)\b",
            r"\b(lingerie|intimo|biancheria\s+intima)\b",
            r"\b(kimono|accappatoio|vestaglia|robe)\b",
            r"\b(uniforme|divisa|militare|polizia|infermiera)\b",
        ],
        "keywords": [
            "abito", "vestito", "dress", "gown", "sera", "evening", "formal",
            "pigiama", "sleepwear", "bikini", "swimsuit", "costume", "bagno",
            "lingerie", "intimo", "kimono", "vestaglia", "accappatoio",
            "uniforme", "divisa", "sports", "sportivo", "casual",
        ]
    }
    
    # Human-readable descriptions for prompts
    COMPONENT_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
        "shoes": {
            "barefoot": "barefoot, bare feet visible",
            "elegant high heels": "wearing elegant high heels",
        },
        "outerwear": {
            "none": "without jacket, sleeves rolled up",
            "blue blazer": "wearing blue blazer",
        },
        "top": {
            "none": "topless, bare chest",
            "unbuttoned white shirt, cleavage visible": "unbuttoned white shirt, cleavage spilling out",
            "white button-up blouse": "white button-up blouse, fully buttoned",
        },
        "bra": {
            "none": "no bra, breasts free",
            "lace bra visible through shirt": "white lace bra visible through wet shirt",
            "white lace bra": "wearing white lace bra",
        },
        "panties": {
            "none": "no panties, completely naked below",
            "white lace panties": "wearing white lace panties",
        },
        "pantyhose": {
            "none": "bare legs, no stockings",
            "torn black pantyhose, runs on thighs": "torn black pantyhose with runs on thighs",
            "pantyhose pulled down around ankles": "black pantyhose pulled down around ankles",
            "sheer black pantyhose": "sheer black pantyhose on legs",
        },
        "bottom": {
            "none": "bottomless, no skirt or pants",
            "pleated skirt lifted up, exposed": "pleated skirt lifted up high, exposing thighs",
            "charcoal grey pencil skirt": "charcoal grey pencil skirt, knee length",
        },
        "tie": {
            "none": "no tie",
            "loose red ribbon tie, slightly undone": "red ribbon tie loosened",
            "red ribbon tie, neatly tied": "red ribbon tie neatly tied at neck",
        },
    }
    
    def __init__(self) -> None:
        """Initialize outfit modifier system."""
        self._compiled: Dict[str, Dict[str, List[re.Pattern]]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        for component, actions in self.PATTERNS.items():
            self._compiled[component] = {}
            for action, patterns in actions.items():
                if action != "values":
                    self._compiled[component][action] = [
                        re.compile(p, re.IGNORECASE) for p in patterns
                    ]
    
    def process_turn(self, user_input: str, game_state: GameState, companion_def=None) -> Tuple[bool, bool, str]:
        """Process a turn for outfit modifications.
        
        This is the main entry point. Call this once per turn.
        
        Args:
            user_input: Player's input text
            game_state: Current game state (will be modified)
            companion_def: Optional companion definition for wardrobe lookup
            
        Returns:
            Tuple of (modified, is_major_change, outfit_description_it)
            - modified: True if outfit was modified
            - is_major_change: True if it's a complete outfit change (needs async handling)
            - outfit_description_it: For major changes, the Italian description to translate
        """
        # First check for major change (complete outfit replacement)
        is_major, outfit_desc_it = self._is_major_change(user_input)
        
        if is_major:
            # Major changes need async translation - return info for engine to handle
            return False, True, outfit_desc_it
        
        # Regular component modifications
        changes = self._parse_input(user_input)
        
        if not changes:
            return False, False, ""
        
        # Get current outfit
        outfit = game_state.get_outfit()
        old_desc = outfit.description
        
        # Apply changes (with companion_def for wardrobe lookup)
        self._apply_changes(outfit, changes, companion_def)
        
        # Update game state
        game_state.set_outfit(outfit)
        
        # Log
        change_str = ", ".join([c.component for c in changes])
        print(f"[OutfitModifier] Modified: {change_str}")
        print(f"[OutfitModifier] {old_desc[:40]}... -> {outfit.description[:40]}...")
        
        return True, False, ""
    
    def _parse_input(self, user_input: str) -> List[OutfitChange]:
        """Parse user input for outfit modifications."""
        changes: List[OutfitChange] = []
        detected: Set[str] = set()
        
        text_lower = user_input.lower()
        
        for component, actions in self._compiled.items():
            if component in detected:
                continue
            
            for action_type, patterns in actions.items():
                for pattern in patterns:
                    if pattern.search(text_lower):
                        value = self.PATTERNS[component]["values"].get(action_type)
                        if value:
                            mod_type = self._get_mod_type(action_type)
                            changes.append(OutfitChange(
                                component=component,
                                new_value=value,
                                mod_type=mod_type,
                                description=f"{component}: {action_type}",
                            ))
                            detected.add(component)
                            break
                if component in detected:
                    break
        
        return changes
    
    def _get_mod_type(self, action_type: str) -> ModificationType:
        """Map action to modification type."""
        mapping = {
            "remove": ModificationType.REMOVED,
            "unbutton": ModificationType.PARTIAL,
            "loosen": ModificationType.PARTIAL,
            "lift": ModificationType.PARTIAL,
            "lower": ModificationType.PARTIAL,
            "slip": ModificationType.PARTIAL,
            "open": ModificationType.PARTIAL,
            "torn": ModificationType.DAMAGED,
            "pulled_down": ModificationType.PARTIAL,
            "wet": ModificationType.DAMAGED,
            "see_through": ModificationType.SPECIAL,
            "downblouse": ModificationType.SPECIAL,
            "cameltoe": ModificationType.SPECIAL,
            "pokies": ModificationType.SPECIAL,
            "add": ModificationType.ADDED,
            "add_glasses": ModificationType.ADDED,
        }
        return mapping.get(action_type, ModificationType.PARTIAL)
    
    def _apply_changes(self, outfit, changes: List[OutfitChange], companion_def=None) -> None:
        """Apply changes to outfit state."""
        from luna.core.models import OutfitComponent
        
        for change in changes:
            # Update component
            outfit.set_component(change.component, change.new_value)
            
            # Mark special states
            if change.mod_type == ModificationType.SPECIAL:
                outfit.is_special = True
                current_special = outfit.components.get("special", "")
                new_special = change.new_value
                if current_special:
                    new_special = f"{current_special}, {new_special}"
                outfit.set_component("special", new_special)
        
        # Rebuild description (with companion_def for wardrobe lookup)
        outfit.description = self._build_description(outfit, companion_def)
    
    def _build_description(self, outfit, companion_def=None) -> str:
        """Build full outfit description.
        
        If we only have partial components (e.g., just shoes modified), 
        append changes to the wardrobe description instead of replacing it completely.
        """
        # Helper to get wardrobe description
        # Priority: sd_prompt (detailed for SD) > description (human-readable)
        def get_wardrobe_description():
            if companion_def and companion_def.wardrobe and outfit.style in companion_def.wardrobe:
                wardrobe_def = companion_def.wardrobe[outfit.style]
                if isinstance(wardrobe_def, str):
                    return wardrobe_def
                else:
                    # Use sd_prompt first (more detailed for image generation), fallback to description
                    return getattr(wardrobe_def, 'sd_prompt', '') or getattr(wardrobe_def, 'description', '')
            return None
        
        # If we have a style from wardrobe but limited components,
        # use wardrobe description as base and append modifications
        has_partial_components = outfit.components and len(outfit.components) <= 3
        
        if has_partial_components and outfit.style != "custom":
            # Get wardrobe description as base
            wardrobe_desc = get_wardrobe_description()
            base_desc = wardrobe_desc or outfit.description
            
            if base_desc:
                # Build modifications
                modifications = self._build_modifications_only(outfit)
                if modifications:
                    # Remove old shoes description if we're modifying shoes
                    if "shoes" in outfit.components:
                        for term in ["elegant high heels", "wearing heels", "pumps", "stilettos"]:
                            base_desc = base_desc.replace(term, "").replace("  ", " ")
                    return f"{base_desc}, {modifications}".strip().rstrip(",")
                return base_desc
        
        # Full rebuild from components
        parts: List[str] = []
        order = ["top", "bra", "outerwear", "tie", "dress", "bottom", "panties", "pantyhose", "shoes"]
        
        for component in order:
            value = outfit.get_component(component)
            if value:
                # Special case: shoes="none" means barefoot (should be included)
                if value == "none":
                    if component == "shoes":
                        parts.append("barefoot, bare feet visible")
                    # For other components, "none" means removed - check if we have a description
                    else:
                        desc_map = self.COMPONENT_DESCRIPTIONS.get(component, {})
                        if "none" in desc_map:
                            parts.append(desc_map["none"])
                else:
                    desc_map = self.COMPONENT_DESCRIPTIONS.get(component, {})
                    readable = desc_map.get(value, value)
                    parts.append(readable)
        
        # Add special
        special = outfit.components.get("special", "")
        if special:
            parts.append(special)
        
        if parts:
            return ", ".join(parts)
        
        # Fallback to wardrobe or existing description
        wardrobe_desc = get_wardrobe_description()
        return wardrobe_desc or outfit.description or "casual clothes"
    
    def _build_modifications_only(self, outfit) -> str:
        """Build description for modified components only."""
        parts: List[str] = []
        
        for component, value in outfit.components.items():
            if value == "none":
                if component == "shoes":
                    parts.append("barefoot, bare feet visible")
                    print(f"    [DEBUG Outfit] Adding 'barefoot' because shoes='none'")
                else:
                    desc_map = self.COMPONENT_DESCRIPTIONS.get(component, {})
                    if "none" in desc_map:
                        parts.append(desc_map["none"])
            elif value and value not in ["true", "custom"]:
                desc_map = self.COMPONENT_DESCRIPTIONS.get(component, {})
                readable = desc_map.get(value, value)
                parts.append(readable)
                if component == "shoes":
                    print(f"    [DEBUG Outfit] Adding shoes description: '{readable}' (value='{value}')")
        
        return ", ".join(parts)
    
    # ===================================================================
    # MAJOR CHANGE - Complete outfit replacement
    # ===================================================================
    
    def _is_major_change(self, user_input: str) -> Tuple[bool, str]:
        """Detect if user wants complete outfit change.
        
        Returns:
            Tuple of (is_major_change, outfit_description_in_italian)
        """
        text_lower = user_input.lower()
        
        # Check for change outfit keywords
        for pattern in self.MAJOR_CHANGE_PATTERNS["change_outfit"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Extract what they want to wear
                return True, self._extract_outfit_description(user_input)
        
        return False, ""
    
    def _extract_outfit_description(self, user_input: str) -> str:
        """Extract outfit description from input."""
        # Simple extraction - take text after change keywords
        text_lower = user_input.lower()
        
        # Patterns to find the outfit
        patterns = [
            r"mette\s+(un\s+)?(?:altro|nuovo)?\s*('?\w+\s*(?:\w+\s*){0,5})\s*(?:abito|vestito|outfit)?",
            r"si\s+cambia\s+(?:con\s+|in\s+)?('?\w+\s*(?:\w+\s*){0,5})",
            r"vestito\s+(da\s+\w+|\w+\s+(?:rosso|blu|nero|bianco|elegante))",
            r"abito\s+(da\s+\w+|\w+\s+(?:rosso|blu|nero|bianco|elegante))",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.group(1) else match.group(0).strip()
        
        # If no specific pattern matched, return the whole input
        return user_input
    
    async def apply_major_change(
        self,
        game_state,
        outfit_description_it: str,
        llm_manager=None,
    ) -> bool:
        """Apply complete outfit change with LLM translation.
        
        Args:
            game_state: Current game state
            outfit_description_it: Outfit description in Italian
            llm_manager: LLM manager for translation (optional)
            
        Returns:
            True if changed successfully
        """
        outfit = game_state.get_outfit()
        old_style = outfit.style
        
        # Translate to English using LLM if available
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
        
        # Reset outfit completely
        outfit.style = "custom"
        outfit.description = outfit_description_en
        outfit.components = {}  # Clear all components
        outfit.is_special = False
        
        # Mark as major custom outfit
        outfit.set_component("major_custom", "true")
        
        game_state.set_outfit(outfit)
        
        print(f"[OutfitModifier] MAJOR CHANGE: {old_style} -> custom")
        print(f"[OutfitModifier] IT: {outfit_description_it[:50]}...")
        print(f"[OutfitModifier] EN: {outfit_description_en[:50]}...")
        
        return True
    
    async def _translate_outfit(
        self,
        description_it: str,
        llm_manager,
    ) -> str:
        """Translate outfit description from Italian to English.
        
        Uses LLM for accurate translation for Stable Diffusion.
        Falls back to basic translation if LLM fails or returns error text.
        """
        # First try basic translation (fast, reliable)
        basic_result = self._basic_translate(description_it)
        
        # Try LLM for better translation
        try:
            prompt = f"""Translate this clothing description from Italian to English.
This is for a fashion/clothing context. Be concise.

Italian: {description_it}
English:"""
            
            response = await llm_manager.generate(
                system_prompt="You are a translator. Translate Italian clothing descriptions to English.",
                user_input=prompt,
                json_mode=False,
            )
            
            if response and response.text:
                translated = response.text.strip()
                
                # Check if LLM returned an error message (in Italian) instead of translation
                error_indicators = [
                    "mi scusi", "errore", "spiacente", "non posso", 
                    "non posso aiutare", "i'm sorry", "error", "cannot"
                ]
                
                is_error = any(ind in translated.lower() for ind in error_indicators)
                is_italian = len([w for w in translated.split() if w.lower() in [
                    "scusi", "c'è", "stato", "nel", "mio", "modulo"
                ]]) > 2
                
                if not is_error and not is_italian and len(translated) > 5:
                    return translated
                else:
                    print(f"[OutfitModifier] LLM returned error text, using basic translation")
                    return basic_result
                    
        except Exception as e:
            print(f"[OutfitModifier] LLM translation failed: {e}")
        
        # Fallback to basic translation
        return basic_result
    
    def _basic_translate(self, text: str) -> str:
        """Basic Italian to English translation for common outfit terms."""
        translations = {
            # Clothing types
            "vestito": "dress",
            "abito": "dress",
            "gonna": "skirt",
            "camicia": "shirt",
            "blusa": "blouse",
            "maglia": "sweater",
            "scarpe": "shoes",
            "tacchi": "high heels",
            "calze": "stockings",
            "collant": "pantyhose",
            "reggiseno": "bra",
            "mutande": "panties",
            "perizoma": "thong",
            "giacca": "jacket",
            "blazer": "blazer",
            "cravatta": "tie",
            # Colors
            "rosso": "red",
            "rossa": "red",
            "blu": "blue",
            "nero": "black",
            "nera": "black",
            "bianco": "white",
            "bianca": "white",
            "verde": "green",
            "giallo": "yellow",
            "gialla": "yellow",
            "rosa": "pink",
            "viola": "purple",
            "arancione": "orange",
            "grigio": "grey",
            "marrone": "brown",
            # Styles
            "elegante": "elegant",
            "sera": "evening",
            "formale": "formal",
            "casual": "casual",
            "sportivo": "sportswear",
            "sexy": "sexy",
            "mini": "mini",
            "corto": "short",
            "corta": "short",
            "lungo": "long",
            "lunga": "long",
            "aderente": "tight",
            "scollato": "low-cut",
            "scollata": "low-cut",
            "trasparente": "see-through",
            # Specific outfits
            "pigiama": "pajamas",
            "bikini": "bikini",
            "kimono": "kimono",
            "lingerie": "lingerie",
            "intimo": "underwear",
            "uniforme": "uniform",
            "costume": "swimsuit",
            "da sera": "evening gown",
            "da bagno": "swimsuit",
            "da notte": "nightgown",
            # Actions/States
            "strappato": "torn",
            "strappata": "torn",
            "bagnato": "wet",
            "bagnata": "wet",
            "aperto": "open",
            "aperta": "open",
            "sbottonato": "unbuttoned",
            "sbottonata": "unbuttoned",
            "slacciato": "loose",
            "slacciata": "loose",
            "senza": "without",
            "nudo": "nude",
            "nuda": "nude",
            # Body parts
            "tette": "breasts",
            "seno": "breasts",
            "culo": "butt",
            "gambe": "legs",
            "piedi": "feet",
            "viso": "face",
            "capelli": "hair",
            # Misc
            "pelo": "hair",
            "pubico": "pubic",
            "sicuro": "tight",
            "sicura": "tight",
            "visibile": "visible",
            "vedo": "showing",
            "uscire": "showing",
        }
        
        result = text.lower()
        for it_word, en_word in translations.items():
            result = re.sub(rf"\b{re.escape(it_word)}\b", en_word, result, flags=re.IGNORECASE)
        
        # Capitalize first letter
        if result:
            result = result[0].upper() + result[1:]
        
        return result.strip()
    
    # ===================================================================
    # UI BUTTON METHODS
    # ===================================================================
    
    def change_random_outfit(self, game_state, companion_def) -> Optional[str]:
        """Change to random outfit from wardrobe.
        
        Called by UI "Cambia" button.
        
        Args:
            game_state: Current game state
            companion_def: Companion definition with wardrobe
            
        Returns:
            Name of new outfit or None if failed
        """
        if not companion_def or not companion_def.wardrobe:
            return None
        
        import random
        
        # Get available outfits
        outfits = list(companion_def.wardrobe.keys())
        current = game_state.get_outfit().style
        
        # Remove current from options
        available = [o for o in outfits if o != current]
        
        if not available:
            available = outfits  # If only one, allow same
        
        # Pick random
        new_outfit = random.choice(available)
        
        # Apply
        outfit = game_state.get_outfit()
        outfit.style = new_outfit
        outfit.components = {}  # Clear modifications
        outfit.is_special = False
        
        # Get description from wardrobe (use sd_prompt for detailed SD description)
        wardrobe_def = companion_def.wardrobe[new_outfit]
        if isinstance(wardrobe_def, str):
            outfit.description = wardrobe_def
        else:
            outfit.description = getattr(wardrobe_def, 'sd_prompt', '') or \
                                   getattr(wardrobe_def, 'description', new_outfit)
        
        game_state.set_outfit(outfit)
        
        print(f"[OutfitModifier] Random change: {current} -> {new_outfit}")
        
        return new_outfit
    
    async def change_custom_outfit(
        self,
        game_state,
        description_it: str,
        llm_manager=None,
    ) -> str:
        """Change to custom outfit from text description.
        
        Called by UI "Modifica" button.
        
        Args:
            game_state: Current game state
            description_it: User's outfit description in Italian
            llm_manager: For translation
            
        Returns:
            Final outfit description in English
        """
        await self.apply_major_change(game_state, description_it, llm_manager)
        
        outfit = game_state.get_outfit()
        return outfit.description


# Factory function for easy initialization
def create_outfit_modifier() -> OutfitModifierSystem:
    """Create a new outfit modifier system instance."""
    return OutfitModifierSystem()
