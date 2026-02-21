"""Image prompt builders for ComfyUI/Stable Diffusion.

Transforms game scene descriptions into optimized prompts.
Supports single character, multi-character (anti-fusion), and NPC scenes.

BASE_PROMPTS are sacred - they define the core visual style.
"""
from __future__ import annotations

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
            "glasses": ("glasses, eyeglasses", "no glasses"),
            "sunglasses": ("sunglasses, shades", "no glasses"),
            "hat": ("hat, cap", "no hat, bare head"),
            "jewelry": ("jewelry, necklace, earrings", "no jewelry"),
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
    height: int = 1152
    steps: int = 24
    cfg_scale: float = 7.0
    sampler: str = "dpmpp_2m"  # ComfyUI format, not A1111
    seed: Optional[int] = None
    composition: str = "medium_shot"
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
    """
    
    def build_prompt(
        self,
        visual_description: str,
        tags: List[str],
        scene_analysis: Optional[SceneAnalysis] = None,
        character_name: str = "",
        outfit_description: str = "",
        outfit: Optional[OutfitState] = None,
        body_focus: Optional[str] = None,
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
            
        Returns:
            Image prompt
        """
        # Get character base prompt from v3 format
        char_prompt = self.base_prompts.get(character_name, NPC_BASE)
        
        # Build additional context
        context_parts = []
        outfit_negative = ""
        
        # Add outfit (prefer structured outfit, fallback to description)
        if outfit:
            # Use new OutfitPromptMapper
            outfit_pos, outfit_neg = OutfitPromptMapper.map_outfit(outfit)
            if outfit_pos:
                context_parts.append(f"({outfit_pos}:1.3),")
            outfit_negative = outfit_neg
        elif outfit_description:
            # Legacy: v3 style outfit formatting
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
            height=kwargs.get("height", 1152),
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
            width=kwargs.get("width", 1024),
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
            height=kwargs.get("height", 1152),
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
        height: int = 1152,
        base_prompt: Optional[str] = None,
        secondary_characters: Optional[List[Dict[str, str]]] = None,
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
        
        # Single character - use original logic
        # Get character-specific base prompt (SACRED - defines visual style)
        # Priority: 1) Explicit base_prompt parameter, 2) BASE_PROMPTS dict, 3) NPC_BASE fallback
        if base_prompt:
            character_base = base_prompt
        else:
            character_base = BASE_PROMPTS.get(character_name, NPC_BASE)
        
        # Build positive prompt - BASE_PROMPTS first (LoRAs must be at start)
        positive_parts = [
            character_base,  # SACRED: Contains LoRAs and core quality tags
            visual_description,
            ", ".join(tags),
        ]
        
        # Add composition hints
        composition_hints = {
            "close_up": "close-up portrait, face focus, detailed face",
            "medium_shot": "medium shot, waist up, upper body",
            "wide_shot": "wide shot, full body, environmental",
        }
        if composition in composition_hints:
            positive_parts.append(composition_hints[composition])
        
        positive = ", ".join(filter(None, positive_parts))
        
        # Build negative prompt
        negative = NEGATIVE_BASE
        
        return ImagePrompt(
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            composition=composition,
        )
