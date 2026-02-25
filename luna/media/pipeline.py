"""Media generation pipeline.

Handles async generation of images, audio, and video.
All operations are non-blocking - content appears when ready.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from luna.core.config import get_settings
from luna.core.models import OutfitState


@dataclass
class MediaResult:
    """Result of media generation."""
    success: bool
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    error: Optional[str] = None


class MediaPipeline:
    """Async media generation pipeline.
    
    Generates content asynchronously:
    - Text → displayed immediately
    - Image → generated in background, displayed when ready
    - Audio → optional, can be muted
    - Video → optional, requires RunPod
    """
    
    def __init__(self) -> None:
        """Initialize media pipeline."""
        self.settings = get_settings()
        
        # Clients (lazy init)
        self._image_client: Optional[Any] = None
        self._audio_client: Optional[Any] = None
        self._video_client: Optional[Any] = None
        
        # Audio settings (like v3)
        self.audio_enabled = True
        self.audio_muted = False
        
        # Callbacks for async updates
        self._on_image_ready: Optional[Callable[[str], None]] = None
        self._on_audio_ready: Optional[Callable[[str], None]] = None
    
    def set_callbacks(
        self,
        on_image_ready: Optional[Callable[[str], None]] = None,
        on_audio_ready: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set callbacks for async media completion.
        
        Args:
            on_image_ready: Called when image is generated
            on_audio_ready: Called when audio is generated
        """
        self._on_image_ready = on_image_ready
        self._on_audio_ready = on_audio_ready
    
    async def generate_all(
        self,
        text: str,
        visual_en: str,
        tags: List[str],
        companion_name: str = "companion",
        outfit: Optional[OutfitState] = None,
        generate_video: bool = False,
        video_action: str = "posing",
        base_prompt: Optional[str] = None,
        secondary_characters: Optional[List[Dict[str, str]]] = None,
    ) -> MediaResult:
        """Generate all media types asynchronously.
        
        Args:
            text: Narrative text (for audio)
            visual_en: Visual description
            tags: SD tags
            companion_name: For character-specific settings
            generate_video: Whether to generate video
            video_action: Action for video generation
            base_prompt: Character base prompt from world YAML (SACRED for visual consistency)
            secondary_characters: Optional list of secondary characters with 'name' and 'base_prompt'
            
        Returns:
            Media result (paths may be None if async)
        """
        result = MediaResult(success=True)
        
        # DEBUG MODE: Skip image/video generation
        if self.settings.debug_no_media:
            print("[MediaPipeline] DEBUG MODE: Skipping image/video generation")
            # Still generate audio if enabled (doesn't require ComfyUI)
            if self.audio_enabled and not self.audio_muted:
                try:
                    audio_path = await self._generate_audio_async(text, companion_name)
                    result.audio_path = audio_path
                except Exception as e:
                    print(f"[MediaPipeline] Audio generation failed: {e}")
            return result
        
        # Start all generations concurrently
        tasks = []
        
        # Image (always, unless in debug mode checked above)
        image_task = asyncio.create_task(
            self._generate_image_async(visual_en, tags, companion_name, outfit, base_prompt, secondary_characters)
        )
        tasks.append(("image", image_task))
        
        # Audio (if enabled)
        if self.audio_enabled and not self.audio_muted:
            audio_task = asyncio.create_task(
                self._generate_audio_async(text, companion_name)
            )
            tasks.append(("audio", audio_task))
        
        # Video (optional, RunPod only)
        if generate_video:
            if self.settings.video_available:
                # Video needs image first - wait for it
                video_task = asyncio.create_task(
                    self._generate_video_after_image(image_task, video_action)
                )
                tasks.append(("video", video_task))
            else:
                print("[MediaPipeline] Video generation skipped: requires RunPod mode")
        
        # Wait for all tasks
        for media_type, task in tasks:
            try:
                path = await task
                if media_type == "image":
                    result.image_path = path
                elif media_type == "audio":
                    result.audio_path = path
                elif media_type == "video":
                    result.video_path = path
            except Exception as e:
                print(f"[MediaPipeline] {media_type} generation failed: {e}")
                result.success = False
                result.error = str(e)
        
        return result
    
    async def generate_multi_npc_sequence(
        self,
        sequence_turns: List[Dict[str, Any]],
        on_image_ready: Optional[Callable[[int, str], None]] = None,
    ) -> List[Optional[str]]:
        """Generate image sequence for Multi-NPC dialogue.
        
        Generates images sequentially (not concurrently) for each turn
        in a Multi-NPC dialogue sequence. Each image has different focus
        based on who is speaking.
        
        Args:
            sequence_turns: List of turn dicts with:
                - visual_en: Visual description
                - tags: SD tags
                - characters: List of character dicts for MultiCharacterBuilder
                - companion_name: Primary companion name
            on_image_ready: Callback(turn_index, image_path) when each image is ready
            
        Returns:
            List of image paths (one per turn)
        """
        # DEBUG MODE: Skip image generation
        if self.settings.debug_no_media:
            print("[MediaPipeline] DEBUG MODE: Skipping Multi-NPC image generation")
            return [None] * len(sequence_turns)
        
        image_paths = []
        
        print(f"[MediaPipeline] Generating {len(sequence_turns)} images for Multi-NPC sequence...")
        
        for idx, turn in enumerate(sequence_turns):
            print(f"[MediaPipeline] Generating image {idx + 1}/{len(sequence_turns)}...")
            
            try:
                # Generate single image for this turn
                path = await self._generate_image_async(
                    visual_en=turn.get("visual_en", ""),
                    tags=turn.get("tags", []),
                    companion_name=turn.get("companion_name", "unknown"),
                    outfit=turn.get("outfit"),
                    base_prompt=turn.get("base_prompt"),
                    secondary_characters=turn.get("characters"),  # For MultiCharacterBuilder
                )
                
                image_paths.append(path)
                
                # Notify callback if provided
                if on_image_ready and path:
                    on_image_ready(idx, path)
                
            except Exception as e:
                print(f"[MediaPipeline] Image {idx + 1} generation failed: {e}")
                image_paths.append(None)
        
        print(f"[MediaPipeline] Multi-NPC sequence complete: {len([p for p in image_paths if p])} images generated")
        return image_paths
    
    def toggle_audio(self) -> bool:
        """Toggle audio mute state.
        
        Returns:
            New mute state (True = muted)
        """
        self.audio_muted = not self.audio_muted
        return self.audio_muted
    
    def set_audio_enabled(self, enabled: bool) -> None:
        """Enable/disable audio completely.
        
        Args:
            enabled: True to enable audio
        """
        self.audio_enabled = enabled
    
    # ========================================================================
    # Private async methods
    # ========================================================================
    
    def _detect_generic_npc(self, visual_en: str, companion_name: str, base_prompt: str) -> bool:
        """Detect if the visual description is for a generic NPC, not the main character.
        
        Checks if the description mentions physical traits different from the companion's base prompt.
        
        Args:
            visual_en: Visual description from LLM
            companion_name: Name of active companion
            base_prompt: Base prompt of active companion (contains their defining traits)
            
        Returns:
            True if this appears to be a generic NPC, not the main companion
        """
        if not visual_en or not base_prompt:
            return False
        
        visual_lower = visual_en.lower()
        base_lower = base_prompt.lower()
        
        # Common hair colors to check
        hair_colors = {
            'red hair': ['brown hair', 'blonde hair', 'black hair', 'white hair', 'grey hair', 'silver hair'],
            'blonde hair': ['brown hair', 'red hair', 'black hair', 'white hair', 'grey hair'],
            'black hair': ['brown hair', 'blonde hair', 'red hair', 'white hair'],
            'white hair': ['brown hair', 'blonde hair', 'red hair', 'black hair'],
            'grey hair': ['brown hair', 'blonde hair', 'red hair', 'black hair'],
            'silver hair': ['brown hair', 'blonde hair', 'red hair', 'black hair'],
            'short hair': ['long hair'],
            'long hair': ['short hair'],
        }
        
        # Check if visual_en mentions hair color that conflicts with companion's base prompt
        for color_key, conflicting_colors in hair_colors.items():
            if color_key in visual_lower:
                # Check if companion's base prompt has a different hair color
                for conflicting in conflicting_colors:
                    if conflicting in base_lower:
                        print(f"[MediaPipeline] Detected NPC with {color_key} (companion has {conflicting})")
                        return True
        
        # Check for generic NPC indicators
        generic_indicators = [
            'secretary', 'librarian', 'nurse', 'teacher', 'student', 'shopkeeper',
            'receptionist', 'bartender', 'waitress', 'cashier', 'passerby',
            'random woman', 'unknown woman', 'young woman', 'mature woman',
            'redhead', 'brunette', 'blonde woman',
        ]
        
        for indicator in generic_indicators:
            if indicator in visual_lower:
                # Check if this is NOT the companion's name
                if companion_name.lower() not in visual_lower:
                    print(f"[MediaPipeline] Detected generic NPC: {indicator}")
                    return True
        
        return False
    
    async def _generate_image_async(
        self,
        visual_en: str,
        tags: List[str],
        companion_name: str,
        outfit: Optional[OutfitState] = None,
        base_prompt: Optional[str] = None,
        secondary_characters: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """Generate image asynchronously.
        
        Args:
            visual_en: Visual description
            tags: SD tags
            companion_name: Character name
            outfit: Character outfit state
            base_prompt: Character base prompt from world YAML (SACRED)
            secondary_characters: Optional list of secondary characters for multi-character scenes
            
        Returns:
            Path to generated image or None
        """
        if self.settings.mock_media:
            return "storage/images/mock_image.png"
        
        # Initialize client if needed
        if self._image_client is None:
            self._image_client = self._init_image_client()
        
        # If no client available, return placeholder
        if self._image_client is None:
            print("[MediaPipeline] No image client available, skipping generation")
            return None
        
        # Check if this is a generic NPC scene (not the main companion)
        effective_base_prompt = base_prompt
        if base_prompt and self._detect_generic_npc(visual_en, companion_name, base_prompt):
            from luna.media.builders import NPC_BASE
            effective_base_prompt = NPC_BASE
            print(f"[MediaPipeline] Using generic NPC base prompt instead of {companion_name}")
        
        # Build prompt using ImagePromptBuilder
        try:
            from luna.media.builders import ImagePromptBuilder
            
            prompt_builder = ImagePromptBuilder()
            prompt = prompt_builder.build(
                visual_description=visual_en,
                tags=tags,
                composition="medium_shot",
                character_name=companion_name,
                outfit=outfit,
                base_prompt=effective_base_prompt,  # Use possibly modified base prompt
                secondary_characters=secondary_characters,  # Multi-character support
            )
            
            # Generate image
            path = await self._image_client.generate(
                prompt=prompt,
                character_name=companion_name,
            )
            
            # Notify callback
            if path and self._on_image_ready:
                self._on_image_ready(str(path))
            
            return str(path) if path else None
            
        except Exception as e:
            print(f"[MediaPipeline] Image generation failed: {e}")
            return None
    
    async def _generate_audio_async(
        self,
        text: str,
        companion_name: str,
    ) -> Optional[str]:
        """Generate audio asynchronously.
        
        Args:
            text: Text to speak
            companion_name: Character name (not used - single voice)
            
        Returns:
            Path to generated audio or None
        """
        if not self.audio_enabled or self.audio_muted:
            return None
        
        if self.settings.mock_media:
            return "storage/audio/mock_audio.mp3"
        
        # Initialize client if needed
        if self._audio_client is None:
            self._audio_client = self._init_audio_client()
        
        if self._audio_client is None:
            print("[MediaPipeline] Audio client not available")
            return None
        
        try:
            # Generate unique filename
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            path = f"storage/audio/narration_{text_hash}.mp3"
            
            # Generate audio
            audio_path = self._audio_client.synthesize(text, path)
            
            if audio_path and self._on_audio_ready:
                self._on_audio_ready(audio_path)
            
            return audio_path
        except Exception as e:
            print(f"[MediaPipeline] Audio generation failed: {e}")
            return None
    
    async def _generate_video_after_image(
        self,
        image_task: asyncio.Task,
        action: str,
    ) -> Optional[str]:
        """Generate video after image is ready.
        
        Args:
            image_task: Task that returns image path
            action: Action description for video
            
        Returns:
            Path to generated video or None
        """
        # Wait for image
        image_path = await image_task
        if not image_path:
            return None
        
        if self.settings.mock_media:
            return "storage/videos/mock_video.mp4"
        
        # Initialize client if needed
        if self._video_client is None:
            self._video_client = self._init_video_client()
        
        # Generate (placeholder)
        await asyncio.sleep(0.5)  # Video takes longer
        
        return f"storage/videos/{asyncio.get_event_loop().time()}.mp4"
    
    def _init_image_client(self) -> Any:
        """Initialize image generation client based on execution mode.
        
        LOCAL mode: SD WebUI (Automatic1111)
        RUNPOD mode: ComfyUI
        """
        try:
            if self.settings.is_local:
                # Local mode: Use SD WebUI
                print("[MediaPipeline] Using SD WebUI (local mode)")
                from luna.media.sd_webui_client import SDWebUIClient
                return SDWebUIClient()
            else:
                # RunPod mode: Use ComfyUI
                print("[MediaPipeline] Using ComfyUI (RunPod mode)")
                from luna.media.comfy_client import ComfyUIClient
                return ComfyUIClient()
        except Exception as e:
            print(f"[MediaPipeline] Image client init failed: {e}")
            return None
    
    def _init_audio_client(self) -> Any:
        """Initialize audio/TTS client."""
        try:
            from luna.media.audio_client import AudioClient
            from luna.core.config import get_settings
            
            settings = get_settings()
            return AudioClient(
                credentials_path=str(settings.google_credentials_path),
                language_code="it-IT",
                voice_name="it-IT-Standard-A",
                speaking_rate=1.0,
            )
        except Exception as e:
            print(f"[MediaPipeline] Audio client init failed: {e}")
            return None
    
    def _init_video_client(self) -> Any:
        """Initialize video generation client."""
        # TODO: Import and init Wan2.1 client
        # from luna.media.video_client import VideoClient
        # return VideoClient()
        return None
