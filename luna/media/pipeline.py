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
    ) -> MediaResult:
        """Generate all media types asynchronously.
        
        Args:
            text: Narrative text (for audio)
            visual_en: Visual description
            tags: SD tags
            companion_name: For character-specific settings
            generate_video: Whether to generate video
            video_action: Action for video generation
            
        Returns:
            Media result (paths may be None if async)
        """
        result = MediaResult(success=True)
        
        # Start all generations concurrently
        tasks = []
        
        # Image (always)
        image_task = asyncio.create_task(
            self._generate_image_async(visual_en, tags, companion_name, outfit)
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
    
    async def _generate_image_async(
        self,
        visual_en: str,
        tags: List[str],
        companion_name: str,
        outfit: Optional[OutfitState] = None,
    ) -> Optional[str]:
        """Generate image asynchronously.
        
        Args:
            visual_en: Visual description
            tags: SD tags
            companion_name: Character name
            outfit: Character outfit state
            
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
        
        # Generate (placeholder)
        await asyncio.sleep(0.1)
        
        path = "storage/audio/narration.mp3"
        if self._on_audio_ready:
            self._on_audio_ready(path)
        
        return path
    
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
