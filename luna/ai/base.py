"""Abstract base class for LLM clients.

All LLM providers must implement this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from luna.core.models import LLMResponse


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers.
    
    All LLM clients must implement:
    - generate(): Main method to get LLM response
    - health_check(): Verify client is ready
    - get_provider_name(): Return provider identifier
    """
    
    def __init__(self, model: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize the LLM client.
        
        Args:
            model: Model identifier (provider-specific)
            **kwargs: Provider-specific configuration
        """
        self.model = model
        self.config = kwargs
        self._initialized = False
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (e.g., 'gemini', 'moonshot')."""
        ...
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]],
        json_mode: bool = True,
    ) -> LLMResponse:
        """Generate LLM response.
        
        Args:
            system_prompt: System instructions for the LLM
            user_input: Current user input
            history: List of previous messages [{"role": "user|assistant", "content": "..."}]
            json_mode: Whether to request JSON output
            
        Returns:
            Structured LLMResponse
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if client is properly configured and ready.
        
        Returns:
            True if client can make requests
        """
        ...
    
    def _build_messages(
        self,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Build message list for API call.
        
        Args:
            system_prompt: System instructions
            user_input: Current input
            history: Previous messages
            
        Returns:
            Formatted messages list
        """
        messages: List[Dict[str, str]] = []
        
        # System prompt as first message (if supported)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # History
        for msg in history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        
        # Current input
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def _create_error_response(self, error_msg: str) -> LLMResponse:
        """Create error response when generation fails.
        
        Args:
            error_msg: Error description
            
        Returns:
            LLMResponse with error text
        """
        return LLMResponse(
            text=f"[Error: {error_msg}]",
            visual_en="",
            tags_en=[],
            raw_response=error_msg,
            provider=self.provider_name,
        )
