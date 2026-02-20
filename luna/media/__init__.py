"""Media generation for Luna RPG v4.

Image, audio, and video generation pipeline with ComfyUI/SD support.
"""
from __future__ import annotations

from luna.media.pipeline import MediaPipeline, MediaResult
from luna.media.builders import (
    ImagePrompt,
    SingleCharacterBuilder,
    MultiCharacterBuilder,
    NPCBuilder,
    PromptBuilderFactory,
    BASE_PROMPTS,
    NEGATIVE_BASE,
    ANTI_FUSION_NEGATIVE,
)
from luna.media.comfy_client import ComfyUIClient
from luna.media.video_client import VideoClient

__all__ = [
    "MediaPipeline",
    "MediaResult",
    "ImagePrompt",
    "SingleCharacterBuilder",
    "MultiCharacterBuilder",
    "NPCBuilder",
    "PromptBuilderFactory",
    "BASE_PROMPTS",
    "NEGATIVE_BASE",
    "ANTI_FUSION_NEGATIVE",
    "ComfyUIClient",
    "VideoClient",
]
