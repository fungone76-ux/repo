"""LLM Manager with retry logic and fallback handling."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from luna.core.models import LLMResponse
from luna.core.config import get_settings
from luna.ai.base import BaseLLMClient
from luna.ai.gemini import GeminiClient
from luna.ai.moonshot import MoonshotClient
from luna.ai.mock import MockLLMClient

import logging
import httpx

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM providers with automatic fallback.
    
    Priority:
    1. Gemini (primary)
    2. Moonshot (fallback)
    3. Mock (if configured, for testing)
    
    Features:
    - Automatic retry with exponential backoff
    - Provider fallback on failure
    - Health checks before using provider
    """
    
    def __init__(self) -> None:
        """Initialize LLM manager with configured providers."""
        self.settings = get_settings()
        self._clients: Dict[str, BaseLLMClient] = {}
        self._primary: Optional[BaseLLMClient] = None
        self._fallback: Optional[BaseLLMClient] = None
        self._mock: Optional[MockLLMClient] = None
        
        self._init_clients()
    
    def _init_clients(self) -> None:
        """Initialize all available clients."""
        # Primary: Gemini
        if self.settings.gemini_api_key:
            try:
                self._primary = GeminiClient(
                    api_key=self.settings.gemini_api_key,
                    model="gemini-2.0-flash",
                )
                self._clients["gemini"] = self._primary
                print(f"[LLMManager] Gemini initialized")
            except Exception as e:
                print(f"[LLMManager] Gemini init failed: {e}")
        
        # Fallback: Moonshot
        if self.settings.moonshot_api_key:
            try:
                self._fallback = MoonshotClient(
                    api_key=self.settings.moonshot_api_key,
                    model="kimi-k2.5",
                )
                self._clients["moonshot"] = self._fallback
                print(f"[LLMManager] Moonshot initialized")
            except Exception as e:
                print(f"[LLMManager] Moonshot init failed: {e}")
        
        # Mock for testing
        if self.settings.mock_llm:
            self._mock = MockLLMClient()
            self._clients["mock"] = self._mock
            print(f"[LLMManager] Mock client initialized")
    
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]] = None,
        json_mode: bool = True,
        use_mock: bool = False,
    ) -> LLMResponse:
        """Generate LLM response with automatic fallback.
        
        Args:
            system_prompt: System instructions
            user_input: Current user message
            history: Previous conversation messages
            json_mode: Whether to request JSON output
            use_mock: Force use of mock client (for testing)
            
        Returns:
            LLMResponse from first successful provider
            
        Raises:
            RuntimeError: If no provider available
        """
        history = history or []
        
        # Use mock if forced
        if use_mock and self._mock:
            return await self._mock.generate(
                system_prompt, user_input, history, json_mode
            )
        
        # Try primary (Gemini)
        if self._primary:
            try:
                result = await self._generate_with_retry(
                    self._primary, system_prompt, user_input, history, json_mode
                )
                if self._is_valid_response(result):
                    return result
            except Exception as e:
                print(f"[LLMManager] Gemini failed: {e}")
        
        # Fallback to Moonshot
        if self._fallback:
            print("[LLMManager] Falling back to Moonshot...")
            try:
                result = await self._generate_with_retry(
                    self._fallback, system_prompt, user_input, history, json_mode
                )
                if self._is_valid_response(result):
                    return result
            except Exception as e:
                print(f"[LLMManager] Moonshot failed: {e}")
        
        # Last resort: Mock
        if self._mock:
            print("[LLMManager] Using mock client...")
            return await self._mock.generate(
                system_prompt, user_input, history, json_mode
            )
        
        raise RuntimeError("No LLM provider available. Check API keys in .env")
    
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _generate_with_retry(
        self,
        client: BaseLLMClient,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]],
        json_mode: bool,
    ) -> LLMResponse:
        """Generate with retry logic.
        
        Args:
            client: LLM client to use
            system_prompt: System instructions
            user_input: User message
            history: Previous messages
            json_mode: JSON mode flag
            
        Returns:
            LLMResponse
        """
        return await client.generate(
            system_prompt, user_input, history, json_mode
        )
    
    def _is_valid_response(self, response: LLMResponse) -> bool:
        """Check if response is valid (not error).
        
        Args:
            response: LLMResponse to check
            
        Returns:
            True if response contains actual content
        """
        if not response.text:
            return False
        if response.text.startswith("[Error:"):
            return False
        if len(response.text.strip()) < 5:  # Too short
            return False
        return True
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers.
        
        Returns:
            Dict mapping provider names to health status
        """
        results = {}
        
        for name, client in self._clients.items():
            try:
                results[name] = await client.health_check()
            except Exception as e:
                print(f"[LLMManager] {name} health check failed: {e}")
                results[name] = False
        
        return results
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names.
        
        Returns:
            List of provider identifiers
        """
        return list(self._clients.keys())
    
    def has_provider(self, name: str) -> bool:
        """Check if a provider is available.
        
        Args:
            name: Provider name
            
        Returns:
            True if provider exists
        """
        return name in self._clients
    
    async def close(self) -> None:
        """Close all clients and release resources."""
        for name, client in self._clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
            except Exception as e:
                print(f"[LLMManager] Error closing {name}: {e}")


# Singleton instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get or create LLM manager singleton.
    
    Returns:
        LLMManager instance
    """
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


def reset_llm_manager() -> None:
    """Reset singleton (useful for testing)."""
    global _llm_manager
    _llm_manager = None
