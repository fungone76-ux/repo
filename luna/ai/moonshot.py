"""Moonshot AI (Kimi) LLM client."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from luna.core.models import LLMResponse, StateUpdate
from luna.ai.base import BaseLLMClient


class MoonshotClient(BaseLLMClient):
    """Moonshot AI provider client.
    
    Fallback provider for Luna RPG v4.
    OpenAI-compatible API with JSON mode support.
    """
    
    DEFAULT_MODEL = "kimi-k2.5"
    BASE_URL = "https://api.moonshot.cn/v1"
    
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        temperature: float = 0.95,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        """Initialize Moonshot client.
        
        Args:
            api_key: Moonshot API key
            model: Model name (defaults to kimi-k2.5)
            temperature: Sampling temperature (0-2)
            max_tokens: Max output tokens
            timeout: Request timeout in seconds
        """
        super().__init__(model or self.DEFAULT_MODEL, **kwargs)
        
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        self._client: Optional[httpx.AsyncClient] = None
        self._init_client()
    
    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "moonshot"
    
    def _init_client(self) -> None:
        """Initialize HTTP client."""
        if not self.api_key:
            print("[Moonshot] No API key provided")
            return
        
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        self._initialized = True
    
    async def health_check(self) -> bool:
        """Check if Moonshot is ready."""
        if not self._client:
            return False
        
        try:
            response = await self._client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]],
        json_mode: bool = True,
    ) -> LLMResponse:
        """Generate response using Moonshot.
        
        Args:
            system_prompt: System instructions
            user_input: Current user message
            history: Previous conversation
            json_mode: Request JSON output
            
        Returns:
            Parsed LLMResponse
        """
        if not self._client:
            return self._create_error_response("Client not initialized")
        
        messages = self._build_messages(system_prompt, user_input, history)
        
        # Try JSON mode first, then fallback to text
        if json_mode:
            try:
                return await self._generate_json(messages)
            except Exception as e:
                print(f"[Moonshot] JSON mode failed: {e}, trying text mode...")
        
        try:
            return await self._generate_text(messages)
        except Exception as e:
            return self._create_error_response(str(e))
    
    async def _generate_json(self, messages: List[Dict[str, str]]) -> LLMResponse:
        """Generate with JSON mode.
        
        Args:
            messages: Formatted messages
            
        Returns:
            Parsed LLMResponse
        """
        # JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Narrative text in Italian",
                },
                "visual_en": {
                    "type": "string",
                    "description": "Visual description for image generation",
                },
                "tags_en": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "SD tags for image generation",
                },
                "body_focus": {
                    "type": "string",
                    "description": "Body part in focus (optional)",
                },
                "approach_used": {
                    "type": "string",
                    "enum": ["standard", "physical_action", "question", "choice"],
                },
                "composition": {
                    "type": "string",
                    "enum": ["close_up", "medium_shot", "wide_shot", "group", "scene"],
                },
                "updates": {
                    "type": "object",
                    "properties": {
                        "affinity_change": {"type": "object"},
                        "current_outfit": {"type": "string"},
                        "location": {"type": "string"},
                        "set_flags": {"type": "object"},
                    },
                },
            },
            "required": ["text"],
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "luna_response",
                    "schema": json_schema,
                },
            },
        }
        
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        return self._parse_response(content)
    
    async def _generate_text(self, messages: List[Dict[str, str]]) -> LLMResponse:
        """Generate with text mode (fallback).
        
        Args:
            messages: Formatted messages
            
        Returns:
            LLMResponse (may have empty metadata)
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        # Try to parse as JSON anyway (LLM might still output JSON)
        return self._parse_response(content)
    
    def _parse_response(self, text: str) -> LLMResponse:
        """Parse Moonshot response to LLMResponse.
        
        Args:
            text: Raw response text
            
        Returns:
            Parsed LLMResponse
        """
        try:
            # Try JSON parsing
            data = json.loads(text)
            
            updates_data = data.get("updates", {})
            updates = StateUpdate(**updates_data) if updates_data else StateUpdate()
            
            return LLMResponse(
                text=data.get("text", ""),
                visual_en=data.get("visual_en", ""),
                tags_en=data.get("tags_en", []),
                body_focus=data.get("body_focus"),
                approach_used=data.get("approach_used", "standard"),
                composition=data.get("composition", "medium_shot"),
                updates=updates,
                raw_response=text,
                provider=f"{self.provider_name}/{self.model}",
            )
            
        except json.JSONDecodeError:
            # Not JSON - treat as plain text
            return LLMResponse(
                text=text,
                visual_en="",
                tags_en=[],
                raw_response=text,
                provider=f"{self.provider_name}/{self.model}",
            )
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
