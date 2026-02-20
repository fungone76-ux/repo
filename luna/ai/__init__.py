"""AI/LLM layer for Luna RPG v4.

Provides multi-provider LLM support with automatic fallback.
"""
from __future__ import annotations

from luna.ai.base import BaseLLMClient
from luna.ai.gemini import GeminiClient
from luna.ai.moonshot import MoonshotClient
from luna.ai.mock import MockLLMClient
from luna.ai.manager import LLMManager, get_llm_manager, reset_llm_manager
from luna.ai.prompts import build_system_prompt, get_response_schema
from luna.ai.personality_analyzer import PersonalityAnalyzer

__all__ = [
    "BaseLLMClient",
    "GeminiClient",
    "MoonshotClient",
    "MockLLMClient",
    "LLMManager",
    "get_llm_manager",
    "reset_llm_manager",
    "build_system_prompt",
    "get_response_schema",
    "PersonalityAnalyzer",
]
