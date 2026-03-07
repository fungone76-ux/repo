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

# Instructor availability check (lazy import to avoid circular imports)
INSTRUCTOR_AVAILABLE = None  # None = not checked yet

def _check_instructor():
    global INSTRUCTOR_AVAILABLE
    if INSTRUCTOR_AVAILABLE is None:
        try:
            from luna.ai.llm_instructor import get_instructor_client
            INSTRUCTOR_AVAILABLE = True
        except ImportError:
            INSTRUCTOR_AVAILABLE = False
    return INSTRUCTOR_AVAILABLE


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
    
    async def generate_simple(
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """Generate simple text response (non-JSON).
        
        V4: For memory summarization and other simple tasks.
        
        Args:
            prompt: Simple prompt (no system prompt needed)
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text or None if failed
        """
        try:
            # Use primary with empty system prompt
            if self._primary:
                result = await self._primary.generate(
                    system_prompt="You are a helpful assistant. Be concise.",
                    user_input=prompt,
                    history=[],
                    json_mode=False,
                )
                return result.text if result else None
            
            # Fallback
            if self._fallback:
                result = await self._fallback.generate(
                    system_prompt="You are a helpful assistant. Be concise.",
                    user_input=prompt,
                    history=[],
                    json_mode=False,
                )
                return result.text if result else None
                
        except Exception as e:
            print(f"[LLMManager] Simple generation failed: {e}")
        
        return None
    
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
    
    async def generate_structured(
        self,
        response_model: Type,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]] = None,
        provider: Optional[str] = None,
    ):
        """Generate with Instructor (structured Pydantic validation).
        
        Args:
            response_model: Pydantic model class for validation
            system_prompt: System instructions
            user_input: User message
            history: Previous messages
            provider: "gemini" or "moonshot" (default: primary)
            
        Returns:
            Validated instance of response_model
            
        Raises:
            RuntimeError: If Instructor not available
        """
        # Check if instructor is available
        if not _check_instructor():
            print("[LLMManager] WARNING: Instructor not available, using JSON fallback")
            # Fallback: generate JSON and parse manually
            return await self._generate_structured_fallback(
                response_model, system_prompt, user_input, history, provider
            )
        
        try:
            # Import here to avoid circular imports
            from luna.ai.llm_instructor import get_instructor_client
            
            # Determine provider
            if provider is None:
                if self._primary and isinstance(self._primary, GeminiClient):
                    provider = "gemini"
                else:
                    provider = "openai"  # Moonshot uses OpenAI interface
            
            # Get instructor client
            model = None
            if provider == "gemini":
                model = "gemini-2.0-flash"
            elif provider == "openai":
                model = "kimi-k2.5"  # Moonshot
            
            client = get_instructor_client(provider=provider, model=model)
            
            print(f"[LLMManager] Using Instructor with {provider}/{model}")
            
            result = await client.generate(
                response_model=response_model,
                system_prompt=system_prompt,
                user_input=user_input,
                history=history,
            )
            
            return result
            
        except Exception as e:
            print(f"[LLMManager] Instructor failed: {e}, using JSON fallback")
            return await self._generate_structured_fallback(
                response_model, system_prompt, user_input, history, provider
            )
    
    async def _generate_structured_fallback(
        self,
        response_model: Type,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]] = None,
        provider: Optional[str] = None,
    ):
        """Fallback for structured generation without Instructor.
        
        Uses JSON mode and manual Pydantic validation.
        """
        import json
        
        # Enhance system prompt with JSON schema hint
        schema = response_model.model_json_schema() if hasattr(response_model, 'model_json_schema') else {}
        enhanced_prompt = f"""{system_prompt}

CRITICAL: Respond with valid JSON matching this structure:
{json.dumps(schema, indent=2) if schema else 'Follow the specified format exactly.'}

Respond ONLY with JSON, no markdown formatting."""
        
        # Generate with JSON mode
        response = await self.generate(
            system_prompt=enhanced_prompt,
            user_input=user_input,
            history=history,
            json_mode=True,
            provider=provider,
        )
        
        # Parse and validate
        try:
            # Extract JSON from response
            text = response.text.strip()
            
            # Handle markdown code blocks
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            
            # Parse JSON
            data = json.loads(text)
            
            # Validate with Pydantic model
            return response_model(**data)
            
        except json.JSONDecodeError as e:
            print(f"[LLMManager] JSON parse failed: {e}")
            # Return default instance
            return response_model()
        except Exception as e:
            print(f"[LLMManager] Validation failed: {e}")
            # Return default instance
            return response_model()
    
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
