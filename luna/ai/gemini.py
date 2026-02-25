"""Google Gemini LLM client."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from luna.core.models import LLMResponse, StateUpdate
from luna.ai.base import BaseLLMClient
from luna.config import get_model_config
from luna.ai.json_repair import repair_json, JSONRepair

# Optional import - fail gracefully if not installed
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiClient(BaseLLMClient):
    """Google Gemini provider client.
    
    Primary provider for Luna RPG v4.
    Supports JSON mode for structured responses.
    Models loaded from config/models.yaml
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key (optional, uses env if not provided)
            model: Model name (overrides config if provided)
            temperature: Sampling temperature (0-2, overrides config)
            max_tokens: Max output tokens (overrides config)
        """
        # Load configuration from models.yaml
        config = get_model_config()
        self._primary_model = config.gemini_primary
        self._fallback_models = config.gemini_fallbacks
        settings = config.gemini_settings
        
        # Use provided values or config values
        model = model or self._primary_model
        temperature = temperature if temperature is not None else settings["temperature"]
        max_tokens = max_tokens if max_tokens is not None else settings["max_tokens"]
        
        super().__init__(model, **kwargs)
        
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "Google GenAI not installed. "
                "Install with: pip install google-genai"
            )
        
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Optional[genai.Client] = None
        
        self._init_client()
    
    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "gemini"
    
    def _init_client(self) -> None:
        """Initialize Gemini client."""
        try:
            self._client = genai.Client(api_key=self.api_key)
            self._initialized = True
        except Exception as e:
            print(f"[Gemini] Failed to initialize: {e}")
            self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if Gemini is ready."""
        if not self._initialized or not self._client:
            return False
        
        try:
            # Simple test call
            response = self._client.models.generate_content(
                model=self.model,
                contents="Test",
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            return response.text is not None
        except Exception:
            return False
    
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        history: List[Dict[str, str]],
        json_mode: bool = True,
    ) -> LLMResponse:
        """Generate response using Gemini.
        
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
        
        # Build contents for Gemini (different format)
        contents = self._build_gemini_contents(history, user_input)
        
        # Safety settings - allow mature content
        safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE",
            ),
        ]
        
        # Try primary model, then fallbacks from config
        models_to_try = [self.model] + self._fallback_models
        last_error: Optional[Exception] = None
        
        for model in models_to_try:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    top_p=0.98,
                    top_k=40,
                    max_output_tokens=self.max_tokens,
                    safety_settings=safety_settings,
                )
                
                if json_mode:
                    config.response_mime_type = "application/json"
                
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                
                if not response.text:
                    continue
                
                # Parse response with strict JSON validation when json_mode=True
                parsed = self._parse_response(response.text, model, strict_json=json_mode)
                if parsed is None and json_mode:
                    # JSON parsing failed in strict mode - retry with this model
                    print(f"[Gemini] {model} returned invalid JSON, retrying...")
                    continue
                return parsed
                
            except Exception as e:
                last_error = e
                print(f"[Gemini] {model} failed: {e}")
                continue
        
        # All models failed
        return self._create_error_response(
            f"All models failed. Last error: {last_error}"
        )
    
    def _build_gemini_contents(
        self,
        history: List[Dict[str, str]],
        user_input: str,
    ) -> List[types.Content]:
        """Build Gemini-specific content format.
        
        Args:
            history: Previous messages
            user_input: Current input
            
        Returns:
            List of Content objects
        """
        contents: List[types.Content] = []
        
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))],
            ))
        
        # Current input
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_input)],
        ))
        
        return contents
    
    def _parse_response(
        self, 
        text: str, 
        model_used: str,
        strict_json: bool = False,
    ) -> Optional[LLMResponse]:
        """Parse Gemini response to LLMResponse.
        
        Args:
            text: Raw response text
            model_used: Which model generated this
            strict_json: If True, returns None on JSON parse failure instead of fallback
            
        Returns:
            Parsed LLMResponse, or None if strict_json=True and parsing fails
        """
        try:
            # Try JSON parsing
            data = json.loads(text)
            
            # Handle case where response is a list instead of dict
            if isinstance(data, list):
                print(f"[Gemini] Warning: Response is a list, expected dict. Using first item.")
                if len(data) > 0 and isinstance(data[0], dict):
                    data = data[0]
                elif strict_json:
                    print(f"[Gemini] Strict JSON: Response is empty list, rejecting")
                    return None
                else:
                    # Wrap list as text
                    return LLMResponse(
                        text=str(data),
                        visual_en="",
                        tags_en=[],
                        raw_response=text,
                        provider=f"{self.provider_name}/{model_used}",
                    )
            
            # Ensure data is a dict
            if not isinstance(data, dict):
                print(f"[Gemini] Warning: Response is {type(data).__name__}, expected dict")
                if strict_json:
                    return None
                return LLMResponse(
                    text=str(data),
                    visual_en="",
                    tags_en=[],
                    raw_response=text,
                    provider=f"{self.provider_name}/{model_used}",
                )
            
            # Extract updates - handle validation errors gracefully
            updates_data = data.get("updates", {})
            try:
                updates = StateUpdate(**updates_data) if updates_data else StateUpdate()
            except Exception as validation_error:
                print(f"[Gemini] StateUpdate validation failed: {validation_error}")
                # Create empty updates - game can continue
                updates = StateUpdate()
            
            return LLMResponse(
                text=data.get("text", ""),
                visual_en=data.get("visual_en", ""),
                tags_en=data.get("tags_en", []),
                body_focus=data.get("body_focus"),
                approach_used=data.get("approach_used", "standard"),
                composition=data.get("composition", "medium_shot"),
                updates=updates,
                raw_response=text,
                provider=f"{self.provider_name}/{model_used}",
            )
            
        except json.JSONDecodeError as e:
            # Try automatic JSON repair
            print(f"[Gemini] JSON parse failed, attempting repair...")
            repaired_data = repair_json(text, strict=False)
            
            if repaired_data is not None:
                print(f"[Gemini] JSON repair successful")
                try:
                    # Extract updates
                    updates_data = repaired_data.get("updates", {})
                    updates = StateUpdate(**updates_data) if updates_data else StateUpdate()
                    
                    return LLMResponse(
                        text=repaired_data.get("text", ""),
                        visual_en=repaired_data.get("visual_en", ""),
                        tags_en=repaired_data.get("tags_en", []),
                        body_focus=repaired_data.get("body_focus"),
                        approach_used=repaired_data.get("approach_used", "standard"),
                        composition=repaired_data.get("composition", "medium_shot"),
                        updates=updates,
                        raw_response=text,
                        provider=f"{self.provider_name}/{model_used}",
                    )
                except Exception as repair_error:
                    print(f"[Gemini] Repair parsing failed: {repair_error}")
            
            if strict_json:
                print(f"[Gemini] Strict JSON: Parse failed - {e}")
                return None
            
            # Not JSON - treat as plain text (fallback mode)
            return LLMResponse(
                text=text,
                visual_en="",
                tags_en=[],
                raw_response=text,
                provider=f"{self.provider_name}/{model_used}",
            )
        except Exception as e:
            print(f"[Gemini] Parse error: {e}")
            print(f"[Gemini] Raw text: {text[:500]}")
            if strict_json:
                return None
            # Return as plain text on any parse error
            return LLMResponse(
                text=text,
                visual_en="",
                tags_en=[],
                raw_response=text,
                provider=f"{self.provider_name}/{model_used}",
            )
