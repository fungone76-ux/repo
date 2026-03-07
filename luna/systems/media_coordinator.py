"""Media Coordinator - Handles async image and video generation.

V4.3 REFACTOR: Extracted from engine.py
Coordinates: Image generation, video generation, outfit changes, multi-NPC scenes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MediaResult:
    """Result of media generation."""
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    secondary_images: Dict[str, str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.secondary_images is None:
            self.secondary_images = {}
        if self.errors is None:
            self.errors = []


class MediaCoordinator:
    """Coordinates media generation without blocking game flow."""
    
    def __init__(
        self,
        media_pipeline: Any,
        enabled: bool = True,
    ) -> None:
        """Initialize coordinator.
        
        Args:
            media_pipeline: MediaPipeline instance
            enabled: Whether media generation is enabled
        """
        self.media_pipeline = media_pipeline
        self.enabled = enabled
        self._generation_tasks: List[asyncio.Task] = []
    
    async def generate_for_turn(
        self,
        game_state: Any,
        llm_response: Any,
        companion_name: str,
        user_input: str,
        is_messaging_mode: bool = False,
        multi_npc_sequence: Optional[Any] = None,
    ) -> MediaResult:
        """Generate all media for a turn.
        
        Args:
            game_state: Current game state
            llm_response: LLM response with visual data
            companion_name: Active companion name
            user_input: User input
            is_messaging_mode: If in messaging mode
            multi_npc_sequence: Optional multi-NPC sequence
            
        Returns:
            MediaResult with paths to generated media
        """
        result = MediaResult()
        
        if not self.enabled or not self.media_pipeline:
            logger.debug("[MediaCoordinator] Media generation disabled")
            return result
        
        try:
            # Check for special generation modes
            if multi_npc_sequence:
                # Multi-NPC scene
                result = await self._generate_multi_npc(
                    game_state, multi_npc_sequence, companion_name
                )
            elif is_messaging_mode and llm_response.updates.get("photo_requested"):
                # Photo request in messaging mode
                result = await self._generate_photo(
                    game_state, llm_response, companion_name
                )
            elif self._is_video_request(user_input, llm_response):
                # Video generation
                result = await self._generate_video(
                    game_state, llm_response, companion_name, user_input
                )
            else:
                # Standard image generation
                result = await self._generate_image(
                    game_state, llm_response, companion_name
                )
        
        except Exception as e:
            logger.error(f"[MediaCoordinator] Media generation failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    async def _generate_image(
        self,
        game_state: Any,
        llm_response: Any,
        companion_name: str,
    ) -> MediaResult:
        """Generate standard image."""
        result = MediaResult()
        
        try:
            # Build image parameters
            params = self._build_image_params(
                game_state, llm_response, companion_name
            )
            
            # Generate
            media_result = await self.media_pipeline.generate(**params)
            
            if media_result and hasattr(media_result, 'image_path'):
                result.image_path = media_result.image_path
                logger.info(f"[MediaCoordinator] Image generated: {result.image_path}")
            
        except Exception as e:
            logger.error(f"[MediaCoordinator] Image generation error: {e}")
            result.errors.append(f"Image: {e}")
        
        return result
    
    async def _generate_video(
        self,
        game_state: Any,
        llm_response: Any,
        companion_name: str,
        user_input: str,
    ) -> MediaResult:
        """Generate video."""
        result = MediaResult()
        
        try:
            # Extract action from user input or LLM response
            action = self._extract_video_action(user_input, llm_response)
            
            # Generate video
            video_result = await self.media_pipeline.generate_video(
                character_name=companion_name,
                user_action=action,
                current_image=result.image_path,  # May be None
            )
            
            if video_result and hasattr(video_result, 'video_path'):
                result.video_path = video_result.video_path
                logger.info(f"[MediaCoordinator] Video generated: {result.video_path}")
        
        except Exception as e:
            logger.error(f"[MediaCoordinator] Video generation error: {e}")
            result.errors.append(f"Video: {e}")
        
        return result
    
    async def _generate_photo(
        self,
        game_state: Any,
        llm_response: Any,
        companion_name: str,
    ) -> MediaResult:
        """Generate photo for messaging mode."""
        result = MediaResult()
        
        try:
            # Get photo outfit if specified
            photo_outfit = llm_response.updates.get("photo_outfit")
            
            # Generate selfie-style image
            params = self._build_image_params(
                game_state, llm_response, companion_name,
                is_photo=True, photo_outfit=photo_outfit
            )
            
            media_result = await self.media_pipeline.generate(**params)
            
            if media_result and hasattr(media_result, 'image_path'):
                result.image_path = media_result.image_path
                logger.info(f"[MediaCoordinator] Photo generated: {result.image_path}")
        
        except Exception as e:
            logger.error(f"[MediaCoordinator] Photo generation error: {e}")
            result.errors.append(f"Photo: {e}")
        
        return result
    
    async def _generate_multi_npc(
        self,
        game_state: Any,
        multi_npc_sequence: Any,
        primary_companion: str,
    ) -> MediaResult:
        """Generate multi-NPC scene."""
        result = MediaResult()
        
        try:
            # Multi-NPC generation
            media_result = await self.media_pipeline.generate_multi_npc(
                sequence=multi_npc_sequence,
                game_state=game_state,
            )
            
            if media_result:
                result.image_path = getattr(media_result, 'image_path', None)
                result.secondary_images = getattr(
                    media_result, 'secondary_images', {}
                )
                logger.info(f"[MediaCoordinator] Multi-NPC image generated")
        
        except Exception as e:
            logger.error(f"[MediaCoordinator] Multi-NPC generation error: {e}")
            result.errors.append(f"Multi-NPC: {e}")
        
        return result
    
    def _build_image_params(
        self,
        game_state: Any,
        llm_response: Any,
        companion_name: str,
        is_photo: bool = False,
        photo_outfit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build parameters for image generation."""
        params = {
            "character_name": companion_name,
            "game_state": game_state,
        }
        
        # Add visual parameters from LLM response
        if hasattr(llm_response, 'visual_en'):
            params["visual_en"] = llm_response.visual_en
        if hasattr(llm_response, 'tags_en'):
            params["tags_en"] = llm_response.tags_en
        if hasattr(llm_response, 'composition'):
            params["composition"] = llm_response.composition
        if hasattr(llm_response, 'body_focus'):
            params["body_focus"] = llm_response.body_focus
        
        # Handle outfit
        if is_photo and photo_outfit:
            params["photo_outfit"] = photo_outfit
        elif hasattr(llm_response, 'updates') and llm_response.updates:
            outfit = llm_response.updates.get("current_outfit")
            if outfit:
                params["outfit_override"] = outfit
        
        return params
    
    def _is_video_request(self, user_input: str, llm_response: Any) -> bool:
        """Check if this is a video generation request."""
        # Check user input for video keywords
        video_keywords = ["video", "animazione", "muoviti", "cammina", "corri"]
        text_lower = user_input.lower()
        
        for keyword in video_keywords:
            if keyword in text_lower:
                return True
        
        # Check LLM response for video flag
        if hasattr(llm_response, 'updates') and llm_response.updates:
            if llm_response.updates.get("generate_video"):
                return True
        
        return False
    
    def _extract_video_action(self, user_input: str, llm_response: Any) -> str:
        """Extract action description for video generation."""
        # Try LLM response first
        if hasattr(llm_response, 'updates') and llm_response.updates:
            action = llm_response.updates.get("video_action")
            if action:
                return action
        
        # Fall back to user input
        return user_input
    
    def cancel_pending(self) -> None:
        """Cancel any pending media generation tasks."""
        for task in self._generation_tasks:
            if not task.done():
                task.cancel()
        self._generation_tasks.clear()
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.cancel_pending()
        if self.media_pipeline:
            # Any pipeline cleanup needed
            pass
