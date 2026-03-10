"""Image prompt builders for ComfyUI/Stable Diffusion.

Transforms game scene descriptions into optimized prompts.
Supports single character, multi-character (anti-fusion), and NPC scenes.

BASE_PROMPTS are sacred - they define the core visual style.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from luna.core.models import CompositionType, OutfitComponent, OutfitState, SceneAnalysis


class OutfitPromptMapper:
    """Maps outfit components to SD prompt keywords.
    
    Converts structured outfit state into positive and negative prompt segments
    for Stable Diffusion image generation.
    """
    
    # Component mappings: value -> (positive_keywords, negative_keywords)
    COMPONENT_MAP: Dict[str, Dict[str, tuple[str, str]]] = {
        OutfitComponent.SHOES.value: {
            "none": ("barefoot, bare feet, no shoes", "shoes, footwear, socks, sneakers, boots, sandals"),
            "barefoot": ("barefoot, bare feet, soles", "shoes, footwear, socks"),
            "sandals": ("sandals, open footwear", "boots, sneakers, socks, closed shoes"),
            "sneakers": ("sneakers, casual shoes, tennis shoes", "boots, sandals, high heels, barefoot"),
            "boots": ("knee-high boots, leather boots", "sandals, sneakers, barefoot, socks"),
            "high_heels": ("high heels, stilettos, pumps", "flat shoes, sneakers, barefoot, boots"),
            "flats": ("flat shoes, ballet flats", "high heels, boots, sneakers"),
            "socks": ("socks, ankle socks", "shoes, barefoot, boots, sandals"),
        },
        OutfitComponent.TOP.value: {
            "t-shirt": ("t-shirt, casual shirt, short sleeves", "formal shirt, suit, jacket"),
            "shirt": ("button-up shirt, collared shirt", "t-shirt, casual top, tank top"),
            "sweater": ("sweater, knitwear, long sleeves", "short sleeves, tank top, t-shirt"),
            "hoodie": ("hoodie, hooded sweatshirt", "formal wear, jacket, coat"),
            "jacket": ("jacket, coat, outerwear", "t-shirt, tank top, bare arms"),
            "dress": ("dress, one-piece dress", "pants, shorts, separate top"),
            "blouse": ("blouse, feminine shirt", "t-shirt, casual shirt"),
            "tank_top": ("tank top, sleeveless shirt, bare shoulders", "long sleeves, jacket, coat"),
            "crop_top": ("crop top, midriff showing", "full shirt, covered midriff"),
            "bikini_top": ("bikini top, swimsuit top", "shirt, dress, covered torso"),
        },
        OutfitComponent.BOTTOM.value: {
            "jeans": ("jeans, denim pants", "skirt, shorts, dress"),
            "pants": ("pants, trousers", "skirt, shorts, dress"),
            "shorts": ("shorts, short pants", "long pants, jeans, skirt, dress"),
            "skirt": ("skirt, flowing skirt", "pants, jeans, shorts"),
            "miniskirt": ("miniskirt, short skirt", "long skirt, pants, jeans"),
            "dress": ("dress, one-piece", "separate top and bottom, pants, skirt"),
            "bikini_bottom": ("bikini bottom, swimsuit bottom", "pants, shorts, skirt"),
            "underwear": ("panties, underwear", "pants, skirt, shorts, covered"),
        },
        OutfitComponent.OUTERWEAR.value: {
            "jacket": ("jacket, blazer", "no jacket, bare arms"),
            "coat": ("coat, overcoat, winter coat", "light clothing, no coat"),
            "cardigan": ("cardigan, knit cardigan", "jacket, coat, no outerwear"),
            "hoodie": ("hoodie, hooded jacket", "formal jacket, coat"),
        },
        OutfitComponent.ACCESSORIES.value: {

            "sunglasses": ("sunglasses, shades", "no glasses"),
            "hat": ("hat, cap", "no hat, bare head"),
            "jewelry":  ( "no jewelry"),
            "scarf": ("scarf, neck scarf", "no scarf"),
        },
        OutfitComponent.SPECIAL.value: {
            "towel": ("wearing only towel, towel wrapped around body", "clothes, shirt, pants, dress"),
            "apron": ("apron, naked apron", "clothes under apron, shirt, pants"),
            "lingerie": ("lingerie, sexy underwear, bra and panties", "regular clothes, dress, pants"),
            "swimsuit": ("swimsuit, one-piece swimsuit", "regular clothes, dress, pants"),
            "bikini": ("bikini, two-piece swimsuit", "regular clothes, dress, covered torso"),
        },
    }
    
    @classmethod
    def map_outfit(cls, outfit: OutfitState) -> tuple[str, str]:
        """Convert outfit state to SD prompt segments.
        
        Returns:
            Tuple of (positive_prompt_segment, negative_prompt_segment)
        """
        positive_parts: List[str] = []
        negative_parts: List[str] = []
        
        # If special state, use that exclusively
        if outfit.is_special and outfit.get_component(OutfitComponent.SPECIAL):
            special = outfit.get_component(OutfitComponent.SPECIAL)
            if special in cls.COMPONENT_MAP[OutfitComponent.SPECIAL.value]:
                pos, neg = cls.COMPONENT_MAP[OutfitComponent.SPECIAL.value][special]
                return pos, neg
            # Unknown special state - use description as-is
            return outfit.description, ""
        
        # Process each component
        for component, value in outfit.components.items():
            if component in cls.COMPONENT_MAP and value in cls.COMPONENT_MAP[component]:
                pos, neg = cls.COMPONENT_MAP[component][value]
                if pos:
                    positive_parts.append(pos)
                if neg:
                    negative_parts.append(neg)
        
        # Add description as base if available (for details not in components)
        if outfit.description:
            # Clean description - remove component-level keywords to avoid duplication
            desc = outfit.description.lower()
            for component_map in cls.COMPONENT_MAP.values():
                for key in component_map.keys():
                    desc = desc.replace(key.lower(), "")
            # Add original description as context
            positive_parts.insert(0, outfit.description)
        
        return ", ".join(positive_parts), ", ".join(negative_parts)
    
    @classmethod
    def is_barefoot(cls, outfit: OutfitState) -> bool:
        """Check if character is barefoot (for foot-focused prompts)."""
        shoes = outfit.get_component(OutfitComponent.SHOES, "").lower()
        return shoes in ("none", "barefoot", "")
    
    @classmethod
    def get_outfit_style_keyword(cls, style: str) -> str:
        """Get SD-friendly style keyword."""
        style_map = {
            "casual": "casual clothes, everyday wear",
            "formal": "formal wear, elegant dress, sophisticated",
            "school_uniform": "school uniform, seifuku, pleated skirt",
            "sportswear": "sportswear, athletic wear, gym clothes",
            "sleepwear": "pajamas, sleepwear, night clothes",
            "swimwear": "swimsuit, beachwear, revealing",
            "lingerie": "lingerie, sexy underwear, intimate apparel",
        }
        return style_map.get(style, f"{style} clothes")


# =============================================================================
# SACRED BASE PROMPTS - Copied IDENTICAL from v3
# These define the core visual style of the game
# =============================================================================
BASE_PROMPTS = {
    "Luna": (
        "score_9, score_8_up, masterpiece, photorealistic, detailed, atmospheric, "
        "stsdebbie, dynamic pose, 1girl, mature woman, brown hair, shiny skin, head tilt, "
        "massive breasts, cleavage, "
        "<lora:stsDebbie-10e:0.7> <lora:Expressive_H-000001:0.20> <lora:FantasyWorldPonyV2:0.40>"
    ),
    "Stella": (
        "score_9, score_8_up, masterpiece, NSFW, photorealistic, 1girl, "
        "alice_milf_catchers, massive breasts, cleavage, blonde hair, beautiful blue eyes, "
        "shapely legs, hourglass figure, skinny body, narrow waist, wide hips, "
        "<lora:alice_milf_catchers_lora:0.7> <lora:Expressive_H:0.2>"
    ),
    "Maria": (
        "score_9, score_8_up, stsSmith, ultra-detailed, realistic lighting, 1girl, "
        "mature female, (middle eastern woman:1.5), veiny breasts, black hair, short hair, "
        "evil smile, glowing magic, "
        "<lora:stsSmith-10e:0.65> <lora:Expressive_H:0.2> <lora:FantasyWorldPonyV2:0.40>"
    ),
}

# NPC base without specific LoRAs
NPC_BASE = (
    "score_9, score_8_up, masterpiece, photorealistic, 1girl, "
    "detailed face, cinematic lighting, 8k, realistic skin texture"
)

NPC_MALE_BASE = (
    "score_9, score_8_up, masterpiece, photorealistic, 1boy, "
    "male npc, detailed face, cinematic lighting, 8k"
)

# Style LoRAs to stack
STYLE_LORAS = [
    {"name": "expressive_h", "weight": 0.2},
    {"name": "fantasyworldponyv2", "weight": 0.4},
]

# Negative prompts by scene type - from v3
NEGATIVE_BASE = (
    "score_5, score_4, low quality, worst quality, "
    "anime, manga, cartoon, 3d render, cgi, illustration, painting, drawing, sketch, "
    "monochrome, grayscale, "
    "deformed, bad anatomy, worst face, extra fingers, mutated, "
    "text, watermark, signature, logo, "
    "glasses, sunglasses, eyewear, spectacles, monocle, goggles, eyeglasses, "
    "blurry face, messy face, spotted face, blotched skin, skin blemishes, "
    "uneven eyes, crossed eyes, disfigured face, bad face"
)

# Enhanced anti-fusion negative from v3
ANTI_FUSION_NEGATIVE = (
    "fused bodies, merged anatomy, conjoined twins, shared limbs, "
    "identical faces, same face, cloned appearance, mirror image, "
    "symmetrical poses, same pose, same angle, "
    "monochrome hair, uniform hairstyle, matching outfits, "
    "ambiguous identity, unclear which is which, blended silhouettes, "
    "overlapping bodies without depth, twin, clone, duplicate"
)

# Positive boosters for differentiation
DIFFERENTIATION_BOOSTERS = [
    "different hair color",
    "different hair style", 
    "different outfits",
    "distinct faces",
    "separate bodies",
    "individual poses",
    "clearly separated",
    "side by side",
    "distinctive appearance",
]

NEGATIVE_PROMPTS = {
    "standard": NEGATIVE_BASE,
    "multi_character": NEGATIVE_BASE + ", " + ANTI_FUSION_NEGATIVE,
}


@dataclass
class ImagePrompt:
    """Structured image generation prompt."""
    positive: str
    negative: str
    width: int = 896
    height: int = 896
    steps: int = 24
    cfg_scale: float = 7.0
    sampler: str = "dpmpp_2m"  # ComfyUI format, not A1111
    seed: Optional[int] = None
    composition: str = "medium_shot"
    aspect_ratio: str = "square"  # landscape, portrait, square
    dop_reasoning: str = ""  # Director of Photography reasoning
    lora_stack: List[Dict[str, Any]] = None
    
    def to_comfyui_workflow(self) -> Dict[str, Any]:
        """Convert to ComfyUI workflow format."""
        return {
            "prompt": self.positive,
            "negative_prompt": self.negative,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg": self.cfg_scale,
            "sampler_name": self.sampler,
            "seed": self.seed,
            "aspect_ratio": self.aspect_ratio,
            "dop_reasoning": self.dop_reasoning,
            "loras": self.lora_stack or [],
        }


class BasePromptBuilder(ABC):
    """Abstract base class for prompt builders.
    
    All builders must implement build_prompt() method.
    """
    
    def __init__(self, base_prompts: Optional[Dict] = None) -> None:
        """Initialize builder.
        
        Args:
            base_prompts: Optional custom base prompts (uses defaults if None)
        """
        self.base_prompts = base_prompts or BASE_PROMPTS
        self.style_loras = STYLE_LORAS.copy()
    
    @abstractmethod
    def build_prompt(
        self,
        visual_description: str,
        tags: List[str],
        scene_analysis: Optional[SceneAnalysis] = None,
        **kwargs: Any,
    ) -> ImagePrompt:
        """Build image prompt.
        
        Args:
            visual_description: Natural language description
            tags: SD tags from LLM
            scene_analysis: Scene analysis for composition
            **kwargs: Builder-specific options
            
        Returns:
            Structured image prompt
        """
        ...
    
    def _build_lora_stack(
        self,
        character_lora: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build LoRA stack with style and character.
        
        Args:
            character_lora: Character-specific LoRA name
            
        Returns:
            List of LoRA configs
        """
        stack = []
        
        # Character LoRA first
        if character_lora:
            stack.append({"name": character_lora, "weight": 1.0})
        
        # Style LoRAs
        stack.extend(self.style_loras)
        
        return stack
    
    def _sanitize_tags(self, tags: List[str]) -> List[str]:
        """Clean and validate tags.
        
        Args:
            tags: Raw tags from LLM
            
        Returns:
            Cleaned tags
        """
        cleaned = []
        for tag in tags:
            # Remove problematic characters
            tag = tag.strip().lower()
            tag = tag.replace("(", "").replace(")", "")
            tag = tag.replace("[", "").replace("]", "")
            if tag and len(tag) < 50:  # Sanity check
                cleaned.append(tag)
        
        # Remove duplicates while preserving order
        seen: Set[str] = set()
        result = []
        for tag in cleaned:
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        
        return result
    
    def _apply_composition(
        self,
        base_prompt: str,
        composition: CompositionType,
    ) -> str:
        """Apply composition framing keywords.
        
        Args:
            base_prompt: Base prompt
            composition: Composition type
            
        Returns:
            Prompt with composition keywords
        """
        composition_keywords = {
            CompositionType.CLOSE_UP: "close-up portrait, face focus,",
            CompositionType.MEDIUM_SHOT: "medium shot, upper body,",
            CompositionType.WIDE_SHOT: "wide shot, full body,",
            CompositionType.GROUP: "group shot, multiple people,",
            CompositionType.SCENE: "wide angle, environmental shot,",
        }
        
        keyword = composition_keywords.get(composition, "")
        if keyword:
            return f"{keyword} {base_prompt}"
        return base_prompt


class SingleCharacterBuilder(BasePromptBuilder):
    """Builder for single character focus scenes.
    
    Optimized for one main character with detailed rendering.
    Uses BASE_PROMPTS from v3 (string format with embedded LoRAs).
    
    CRITICAL V3 FEATURE: Detects generic NPCs and uses NPC_BASE without LoRAs
    when the described character doesn't match the active companion.
    """
    
    # Known companion names (for LoRA detection)
    KNOWN_COMPANIONS = {"Luna", "Stella", "Maria"}
    
    def _is_generic_npc(self, visual_description: str, character_name: str) -> bool:
        """Detect if the scene describes a generic NPC, not the main companion.
        
        V3 Logic: Checks if visual description mentions traits different from companion.
        
        Args:
            visual_description: Visual description from LLM
            character_name: Active companion name
            
        Returns:
            True if this is a generic NPC (use NPC_BASE), False if main companion
        """
        if not visual_description:
            return False
        
        visual_lower = visual_description.lower()
        
        # Check if companion name is explicitly mentioned
        if character_name and character_name.lower() in visual_lower:
            # The description explicitly names the companion - use their LoRA
            return False
        
        # Check for hair color mismatches (companion-specific traits)
        companion_hair = {
            "Luna": ["brown hair", "brunette", "chestnut"],
            "Stella": ["blonde hair", "blond", "golden hair", "yellow hair"],
            "Maria": ["black hair", "dark hair", "grey hair", "gray hair"],
        }
        
        if character_name in companion_hair:
            expected_hair = companion_hair[character_name]
            # Check if visual mentions a DIFFERENT hair color
            hair_colors = {
                "red hair": ["redhead", "ginger", "auburn", "rossi", "rossa"],
                "blonde hair": ["blonde", "blond", "golden", "bionda", "biondo"],
                "brown hair": ["brown", "brunette", "chestnut", "castani", "marrone"],
                "black hair": ["black", "dark", "neri", "nera"],
                "white hair": ["white", "silver", "platinum", "bianchi", "argento"],
                "grey hair": ["grey", "gray", "grigi"],
            }
            
            for color, keywords in hair_colors.items():
                if any(kw in visual_lower for kw in keywords):
                    # This hair color is mentioned - check if it matches companion
                    if color not in expected_hair:
                        print(f"[SingleCharacterBuilder] Detected hair color mismatch: {color} vs {character_name}'s {expected_hair}")
                        return True
        
        # Check for generic NPC indicators
        generic_indicators = [
            "secretary", "segretaria", "librarian", "bibliotecaria",
            "nurse", "infermiera", "teacher", "professoressa",
            "student", "studentessa", "shopkeeper", "negoziante",
            "receptionist", "bartender", "waitress", "cameriera",
            "cashier", "cassiera", "passerby", "passante",
            "random woman", "unknown woman", "young woman", "mature woman",
            "redhead", "brunette", "blonde woman",
        ]
        
        for indicator in generic_indicators:
            if indicator in visual_lower:
                # Generic NPC indicator found and companion not named
                print(f"[SingleCharacterBuilder] Detected generic NPC indicator: {indicator}")
                return True
        
        return False
    
    def build_prompt(
        self,
        visual_description: str,
        tags: List[str],
        scene_analysis: Optional[SceneAnalysis] = None,
        character_name: str = "",
        outfit_description: str = "",
        outfit: Optional[OutfitState] = None,
        body_focus: Optional[str] = None,
        base_prompt: Optional[str] = None,  # V3: Explicit base prompt from companion
        **kwargs: Any,
    ) -> ImagePrompt:
        """Build single character prompt.
        
        Args:
            visual_description: Scene description
            tags: SD tags
            scene_analysis: Scene analysis
            character_name: Character name (for LoRA selection)
            outfit_description: Outfit/clothing description (legacy)
            outfit: Structured outfit state (preferred)
            body_focus: Body part in focus (face, hands, etc.)
            base_prompt: Optional explicit base prompt (from companion definition)
            
        Returns:
            Image prompt
        """
        # V3 LOGIC: Use explicit base_prompt if provided (for temporary NPCs)
        if base_prompt:
            # Use the provided base prompt (already contains NPC_BASE + gender + type)
            char_prompt = base_prompt
            print(f"[SingleCharacterBuilder] Using explicit base_prompt for {character_name}")
        else:
            # V3 LOGIC: Detect if this is a generic NPC scene
            is_generic_npc = self._is_generic_npc(visual_description, character_name)
            
            if is_generic_npc:
                # Generic NPC: Use NPC_BASE without character LoRAs
                print(f"[SingleCharacterBuilder] Using generic NPC base (not {character_name})")
                char_prompt = NPC_BASE
            else:
                # Known companion: Use their specific base prompt with LoRAs
                char_prompt = self.base_prompts.get(character_name, NPC_BASE)
        
        # DEBUG logging
        print(f"    [DEBUG] character_name: {character_name}")
        print(f"    [DEBUG] is_generic_npc: {is_generic_npc}")
        print(f"    [DEBUG] char_prompt[:50]: {char_prompt[:50] if char_prompt else 'None'}...")
        
        # Check if visual_description already contains the base prompt (avoid duplication)
        # This happens when the LLM includes base prompt in visual_en following system prompt instructions
        visual_lower = visual_description.lower()
        
        # Check 1: Contains LoRAs (definite proof of base prompt inclusion)
        if "<lora:" in visual_description:
            print(f"[SingleCharacterBuilder] Detected LoRAs in visual_description, skipping base prompt")
            char_prompt = ""
        # Check 2: Contains quality tags that are in base prompt
        elif "score_9" in visual_lower and "score_8_up" in visual_lower and "masterpiece" in visual_lower:
            print(f"[SingleCharacterBuilder] Detected quality tags (score_9 + score_8_up + masterpiece) in visual_description, skipping base prompt")
            char_prompt = ""
        # Check 3: Contains character-specific LoRA triggers
        elif any(kw in visual_lower for kw in ["stsdebbie", "stssmith", "alice_milf_catchers"]):
            print(f"[SingleCharacterBuilder] Detected character LoRA triggers in visual_description, skipping duplicate")
            char_prompt = ""
        
        # Build additional context
        context_parts = []
        outfit_negative = ""
        
        # V3.5 PATTERN: Use OutfitPromptMapper for component-based outfit generation
        # This ensures clean prompts and proper negative keywords (e.g., barefoot -> no shoes)
        if outfit and outfit.components:
            # Use OutfitPromptMapper for structured component-based prompts
            outfit_pos, outfit_neg = OutfitPromptMapper.map_outfit(outfit)
            if outfit_pos:
                context_parts.append(f"({outfit_pos}:1.3),")
                print(f"    [DEBUG Outfit] Using mapped: '{outfit_pos[:60]}...'")
            if outfit_neg:
                outfit_negative = outfit_neg
                print(f"    [DEBUG Outfit] Negative: '{outfit_neg[:60]}...'")
        elif outfit and outfit.description:
            # Fallback to description-based (wardrobe or creative)
            clean_desc = outfit.description.strip()
            if clean_desc.lower().startswith("wearing "):
                context_parts.append(f"({clean_desc}:1.3),")
            elif "nude" in clean_desc.lower() or "naked" in clean_desc.lower():
                context_parts.append(f"(nude:1.3), {clean_desc},")
            else:
                context_parts.append(f"(wearing {clean_desc}:1.3),")
            print(f"    [DEBUG Outfit] Using description: '{clean_desc[:60]}...'")
        elif outfit_description:
            # Legacy fallback
            clean_desc = outfit_description.strip()
            if clean_desc.lower().startswith("wearing "):
                context_parts.append(f"({clean_desc}:1.3),")
            elif "nude" in clean_desc.lower() or "naked" in clean_desc.lower():
                context_parts.append(f"(nude:1.3), {clean_desc},")
            else:
                context_parts.append(f"(wearing {clean_desc}:1.3),")
        
        # Add visual description
        context_parts.append(visual_description + ",")
        
        # Add tags
        cleaned_tags = self._sanitize_tags(tags)
        # Remove conflicting tags
        cleaned_tags = [t for t in cleaned_tags if t not in ("1girl", "solo")]
        
        # V3 LOGIC: For generic NPCs, remove character-specific tags
        if is_generic_npc:
            character_specific_tags = [
                "stsdebbie", "stssmith", "alice_milf_catchers",
                "brown hair", "blonde hair", "black hair",  # Hair colors from companions
            ]
            cleaned_tags = [t for t in cleaned_tags if t.lower() not in character_specific_tags]
            print(f"[SingleCharacterBuilder] Removed character-specific tags for generic NPC")
        
        if cleaned_tags:
            context_parts.append(", ".join(cleaned_tags) + ",")
        
        # Add body focus
        if body_focus:
            context_parts.append(f"{body_focus} focus,")
        
        # Combine: BASE_PROMPT (contains LoRAs) + context
        context_str = " ".join(context_parts)
        positive = f"{char_prompt}, {context_str}"
        
        # Apply composition
        if scene_analysis:
            positive = self._apply_composition(positive, scene_analysis.composition_type)
        
        # Parse LoRAs from the base prompt (for workflow building)
        lora_stack = self._parse_loras_from_prompt(char_prompt)
        
        # Build negative prompt with outfit negatives
        negative = NEGATIVE_PROMPTS["standard"]
        if outfit_negative:
            negative = f"{negative}, {outfit_negative}"
        
        return ImagePrompt(
            positive=positive,
            negative=negative,
            lora_stack=lora_stack,
            width=kwargs.get("width", 896),
            height=kwargs.get("height", 896),
            sampler="euler",
            cfg_scale=7.0,
        )
    
    def _parse_loras_from_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract LoRA definitions from prompt string.
        
        Args:
            prompt: Prompt containing <lora:name:weight> tags
            
        Returns:
            List of LoRA configs
        """
        import re
        loras = []
        pattern = r'<lora:([^:]+):([\d.]+)>'
        matches = re.findall(pattern, prompt)
        for name, weight in matches:
            loras.append({"name": name, "weight": float(weight)})
        return loras


class MultiCharacterBuilder(BasePromptBuilder):
    """Builder for multi-character scenes (2+ characters).
    
    Uses ENHANCED anti-fusion techniques from v3 to prevent character merging.
    """
    
    def build_prompt(
        self,
        visual_description: str,
        tags: List[str],
        scene_analysis: Optional[SceneAnalysis] = None,
        characters: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> ImagePrompt:
        """Build multi-character prompt with ENHANCED anti-fusion.
        
        Args:
            visual_description: Scene description
            tags: SD tags
            scene_analysis: Scene analysis
            characters: List of dicts with 'name', 'position', 'outfit', 'base_prompt'
            
        Returns:
            Image prompt
        """
        characters = characters or []
        
        # Build character-specific prompts with ENHANCED anti-fusion
        char_sections = []
        all_loras = []
        
        for i, char_data in enumerate(characters):
            name = char_data.get("name", f"girl_{i}")
            position = char_data.get("position", "")
            outfit = char_data.get("outfit", "")
            
            # Get base prompt: prefer explicit base_prompt from char_data, then fall back to dict
            char_base = char_data.get("base_prompt") or self.base_prompts.get(name, NPC_BASE)
            
            # ENHANCED: Individual character section with strong separation
            section_parts = [f"[[Character {i+1}: {name}]]"]
            section_parts.append(char_base)
            
            if outfit:
                section_parts.append(f"wearing {outfit},")
            
            if position:
                section_parts.append(f"positioned {position},")
            
            # ENHANCED: Strong focus on distinct features
            section_parts.append("distinct face, unique appearance,")
            section_parts.append("[[End Character]]")
            
            char_sections.append(" ".join(section_parts))
            
            # Collect LoRAs
            loras = self._parse_loras_from_prompt(char_base)
            all_loras.extend(loras)
        
        # Build main prompt with ENHANCED anti-fusion
        parts = [
            "masterpiece, best quality, highres,",
            f"{len(characters)}girls,",  # Correct girl count
        ]
        
        # ENHANCED: Add differentiation boosters FIRST (higher priority)
        parts.extend(DIFFERENTIATION_BOOSTERS[:4])  # Use top 4 boosters
        
        # Add character sections with clear separation
        parts.append("||")
        parts.extend(char_sections)
        parts.append("||")
        
        # Add scene description
        parts.append(visual_description + ",")
        
        # Add tags
        cleaned_tags = self._sanitize_tags(tags)
        filtered_tags = [t for t in cleaned_tags if t not in ("1girl", "solo", "2girls", "3girls")]
        if filtered_tags:
            parts.append(", ".join(filtered_tags) + ",")
        
        # ENHANCED: Additional anti-fusion positive keywords
        parts.extend([
            "completely separate individuals,",
            "different hairstyles, different clothing,",
            "spatial separation, distinct silhouettes,",
            "no overlapping, no touching,",
        ])
        
        # Combine
        positive = " ".join(parts)
        
        # Force wide shot for groups
        positive = f"wide shot, {positive}"
        
        # Remove duplicate LoRAs
        unique_loras = []
        seen = set()
        for lora in all_loras:
            if lora["name"] not in seen:
                seen.add(lora["name"])
                unique_loras.append(lora)
        
        return ImagePrompt(
            positive=positive,
            negative=NEGATIVE_PROMPTS["multi_character"],  # Enhanced negative
            lora_stack=unique_loras,
            width=kwargs.get("width", 896),
            height=kwargs.get("height", 896),
            sampler="euler",
            cfg_scale=7.0,
        )
    
    def _parse_loras_from_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract LoRA definitions from prompt string."""
        import re
        loras = []
        pattern = r'<lora:([^:]+):([\d.]+)>'
        matches = re.findall(pattern, prompt)
        for name, weight in matches:
            loras.append({"name": name, "weight": float(weight)})
        return loras


class NPCBuilder(BasePromptBuilder):
    """Builder for generic/NPC characters.
    
    No character-specific LoRAs, uses generic high-quality prompts.
    """
    
    def build_prompt(
        self,
        visual_description: str,
        tags: List[str],
        scene_analysis: Optional[SceneAnalysis] = None,
        npc_type: str = "female_student",  # Generic type hint
        **kwargs: Any,
    ) -> ImagePrompt:
        """Build NPC prompt.
        
        Args:
            visual_description: Scene description
            tags: SD tags
            scene_analysis: Scene analysis
            npc_type: Type of NPC (librarian, student, etc.)
            
        Returns:
            Image prompt
        """
        npc_config = self.base_prompts["NPC_BASE"]
        
        parts = [
            "masterpiece, best quality, highres,",
            npc_config["trigger"],
            npc_config["base"],
        ]
        
        # Add NPC type hint
        if npc_type:
            parts.append(f"{npc_type},")
        
        # Add visual description
        parts.append(visual_description + ",")
        
        # Add tags
        cleaned_tags = self._sanitize_tags(tags)
        if cleaned_tags:
            parts.append(", ".join(cleaned_tags) + ",")
        
        # Quality enhancers
        parts.extend([
            "detailed face, detailed eyes,",
            "natural lighting,",
        ])
        
        positive = " ".join(parts)
        
        # Apply composition
        if scene_analysis:
            positive = self._apply_composition(positive, scene_analysis.composition_type)
        
        # No character LoRA, only style
        lora_stack = self.style_loras.copy()
        
        return ImagePrompt(
            positive=positive,
            negative=NEGATIVE_PROMPTS["standard"],
            lora_stack=lora_stack,
            width=kwargs.get("width", 896),
            height=kwargs.get("height", 896),
        )


class PromptBuilderFactory:
    """Factory for creating appropriate builder based on scene."""
    
    @staticmethod
    def create_builder(
        scene_analysis: Optional[SceneAnalysis] = None,
        primary_character: str = "",
        known_companions: Optional[Set[str]] = None,
    ) -> BasePromptBuilder:
        """Create appropriate builder for scene.
        
        Args:
            scene_analysis: Scene analysis
            primary_character: Main character name
            known_companions: Set of known companion names
            
        Returns:
            Appropriate prompt builder
        """
        known = known_companions or set()
        
        # Check if multi-character
        if scene_analysis and scene_analysis.is_multi_character:
            return MultiCharacterBuilder()
        
        # Check if known companion
        if primary_character in known:
            return SingleCharacterBuilder()
        
        # Default to NPC builder
        return NPCBuilder()


class ImagePromptBuilder:
    """Simple builder for creating ImagePrompt from basic parameters.
    
    Used by MediaPipeline for straightforward image generation.
    
    BASE_PROMPTS are SACRED - they define the core visual style and MUST be used.
    """
    
    def build(
        self,
        visual_description: str,
        tags: List[str],
        composition: str = "medium_shot",
        character_name: str = "",
        outfit: Optional[Any] = None,
        width: int = 896,
        height: int = 896,
        base_prompt: Optional[str] = None,
        secondary_characters: Optional[List[Dict[str, str]]] = None,
        location_visual_style: Optional[str] = None,
        aspect_ratio: str = "square",
        dop_reasoning: str = "",
    ) -> ImagePrompt:
        """Build image prompt from basic parameters.
        
        Uses BASE_PROMPTS for character-specific LoRAs and quality tags.
        Supports multi-character scenes when secondary_characters is provided.
        
        Args:
            visual_description: Visual description text
            tags: SD tags list
            composition: Shot composition
            character_name: Character name (for BASE_PROMPTS lookup)
            outfit: Optional outfit state
            width: Image width
            height: Image height
            base_prompt: Optional explicit base prompt (from world YAML). If provided, overrides BASE_PROMPTS.
            secondary_characters: Optional list of secondary characters [{'name': 'X', 'base_prompt': 'Y'}]
            location_visual_style: V4: Visual style of current location (used when solo/no character)
            aspect_ratio: Director of Photography choice (landscape, portrait, square)
            dop_reasoning: Cinematographic reasoning for the aspect ratio choice
            
        Returns:
            ImagePrompt ready for generation
        """
        # Check if multi-character scene
        if secondary_characters and len(secondary_characters) > 0:
            # Use MultiCharacterBuilder for multi-character scenes
            multi_builder = MultiCharacterBuilder()
            
            # Build characters list with primary + secondaries
            # Use the format expected by MultiCharacterBuilder
            characters = []
            
            # Primary character (center position)
            primary_outfit = outfit.style if outfit else ""
            characters.append({
                'name': character_name,
                'position': 'center',
                'outfit': primary_outfit,
            })
            
            # Secondary characters (alternate left/right)
            positions = ['left', 'right']
            for i, char_data in enumerate(secondary_characters):
                char_name = char_data.get('name', '')
                char_outfit = char_data.get('outfit', '')
                position = positions[i % len(positions)]
                characters.append({
                    'name': char_name,
                    'position': position,
                    'outfit': char_outfit,
                })
            
            # Build multi-character prompt using the builder
            return multi_builder.build_prompt(
                visual_description=visual_description,
                tags=tags,
                characters=characters,
                width=width,
                height=height,
            )
        
        # V4: Check if solo mode (no character, just environment)
        is_solo_mode = character_name == "_solo_" or character_name == ""
        
        if is_solo_mode:
            # Solo mode: Use location visual style instead of character
            print(f"[ImagePromptBuilder] Solo mode detected - using location visual style")
            if location_visual_style:
                # Use location style + quality tags
                character_base = f"score_9, score_8_up, masterpiece, photorealistic, detailed, {location_visual_style}"
            else:
                # Fallback to generic quality tags
                character_base = "score_9, score_8_up, masterpiece, photorealistic, detailed, atmospheric"
        elif base_prompt:
            # V3: Explicit base prompt provided
            character_base = base_prompt
        else:
            # Standard character: Use BASE_PROMPTS
            character_base = BASE_PROMPTS.get(character_name, NPC_BASE)
        
        # Check if visual_description already contains the base prompt (avoid duplication)
        # This happens when LLM follows the prompt instructions too literally
        visual_desc_clean = visual_description.strip()
        
        # Remove leading comma if present (to avoid ",," when joining)
        if visual_desc_clean.startswith(","):
            visual_desc_clean = visual_desc_clean[1:].strip()
        
        # Deduplication: Check if visual_description already contains base prompt content
        skip_base_prompt = False
        
        # Check 1: Contains LoRAs and quality tags - definitely has base prompt
        if "<lora:" in visual_desc_clean and "score_9" in visual_desc_clean:
            print(f"[ImagePromptBuilder] Detected LoRAs in visual_description, skipping base prompt")
            skip_base_prompt = True
        # Check 2: Contains key character keywords from base prompt (fuzzy match)
        elif character_base:
            # Extract key keywords from base prompt (first part without LoRAs)
            base_keywords = character_base.split('<lora:')[0].strip()
            # Check if main keywords are present in visual_description
            key_parts = ['score_9', 'score_8_up']
            if all(kw in visual_desc_clean for kw in key_parts):
                print(f"[ImagePromptBuilder] Base prompt keywords detected, skipping duplicate")
                skip_base_prompt = True
            # Check 3: visual_description starts with base prompt content
            elif visual_desc_clean.lower().startswith(base_keywords.lower()[:50]):
                print(f"[ImagePromptBuilder] Visual description starts with base prompt content, skipping")
                skip_base_prompt = True
        
        # If visual description already has base prompt content, remove it from visual_desc_clean
        # AND don't add character_base separately
        if skip_base_prompt:
            character_base = ""  # Don't add base prompt as prefix
            # Try to extract just the scene description part (after the duplicated base prompt)
            # Look for where score_9 ends and actual description begins
            if "score_9" in visual_desc_clean:
                # Find end of base prompt section (usually after first comma following LoRAs)
                lora_end = visual_desc_clean.rfind('>') if '<lora:' in visual_desc_clean else -1
                if lora_end > 0:
                    # Get everything after the last LoRA
                    after_loras = visual_desc_clean[lora_end+1:].strip()
                    # If it starts with comma, remove it
                    if after_loras.startswith(","):
                        after_loras = after_loras[1:].strip()
                    # If it still has score_9, take everything after it
                    if "score_9" in after_loras:
                        score_pos = after_loras.find("score_9")
                        # Find where score section ends (look for comma after score_8_up or similar)
                        search_start = score_pos + 10
                        next_comma = after_loras.find(",", search_start)
                        if next_comma > 0:
                            visual_desc_clean = after_loras[next_comma+1:].strip()
                        else:
                            visual_desc_clean = after_loras
                    else:
                        visual_desc_clean = after_loras
        
        # Build positive prompt - BASE_PROMPTS first (LoRAs must be at start)
        positive_parts = [
            character_base,  # SACRED: Contains LoRAs and core quality tags (if not already in visual_description)
        ]
        
        # Add outfit description if available (V3 Pattern)
        if outfit and outfit.description:
            clean_desc = outfit.description.strip()
            # Clean up any trailing comma to avoid double commas
            if clean_desc.endswith(","):
                clean_desc = clean_desc[:-1].strip()
                
            if clean_desc.lower().startswith("wearing "):
                positive_parts.append(f"({clean_desc}:1.3)")
            elif "nude" in clean_desc.lower() or "naked" in clean_desc.lower():
                positive_parts.append(f"(nude:1.3), {clean_desc}")
            else:
                positive_parts.append(f"(wearing {clean_desc}:1.3)")
            print(f"    [ImagePromptBuilder Outfit] Using: '{clean_desc[:60]}...'")
        elif outfit and outfit.style:
            # Fallback: use style as description
            positive_parts.append(f"(wearing {outfit.style}:1.3)")
            print(f"    [ImagePromptBuilder Outfit] Using style: '{outfit.style}'")
        
        # Add visual description (now cleaned of duplicates)
        if visual_desc_clean:
            positive_parts.append(visual_desc_clean)
        
        # Add tags if any
        if tags:
            positive_parts.append(", ".join(tags))
        
        # Add composition hints
        composition_hints = {
            "close_up": "close-up portrait, face focus, detailed face",
            "medium_shot": "medium shot",  # Rimosso waist up e upper body!
            "cowboy_shot": "cowboy shot, framing from knees up",
            "wide_shot": "wide shot, full body, environmental",
            "from_below": "shot from below, low angle",
            "from_above": "shot from above, high angle",
        }
        if composition in composition_hints:
            positive_parts.append(composition_hints[composition])
        
        positive = ", ".join(filter(None, positive_parts))
        
        # V4.4 FIX: Pantyhose feet coverage correction
        # SD often renders feet as bare even with pantyhose in prompt
        positive = self._fix_pantyhose_feet(positive)
        
        # Build negative prompt
        negative = NEGATIVE_BASE
        
        return ImagePrompt(
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            composition=composition,
            aspect_ratio=aspect_ratio,
            dop_reasoning=dop_reasoning,
        )
    
    def _fix_pantyhose_feet(self, prompt: str) -> str:
        """Fix pantyhose prompt to ensure feet are covered.
        
        SD often renders feet as bare even when pantyhose/stockings are mentioned.
        This adds explicit feet coverage tags when pantyhose are detected.
        
        Args:
            prompt: Original prompt
            
        Returns:
            Corrected prompt
        """
        prompt_lower = prompt.lower()
        
        # Check if pantyhose or stockings are mentioned
        pantyhose_keywords = ['pantyhose', 'stockings', 'collant', 'tights']
        has_pantyhose = any(kw in prompt_lower for kw in pantyhose_keywords)
        
        if has_pantyhose:
            # Check if feet are already explicitly mentioned as covered
            feet_covered_phrases = [
                'feet covered', 'covered feet', 'pantyhose on feet',
                'stockings on feet', 'feet in pantyhose', 'feet in stockings'
            ]
            already_fixed = any(phrase in prompt_lower for phrase in feet_covered_phrases)
            
            if not already_fixed:
                # Add explicit feet coverage
                prompt += ", feet covered by pantyhose, sheer pantyhose on feet"
                print(f"[ImagePromptBuilder] Pantyhose detected - added explicit feet coverage")
        
        return prompt
