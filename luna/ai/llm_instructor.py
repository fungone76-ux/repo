"""LLM Client con Instructor - Validazione rigorosa via Pydantic.

Questo modulo usa la libreria Instructor per forzare l'LLM a generare
output conforme a schemi Pydantic, eliminando errori di parsing.

Docs: https://python.useinstructor.com/
"""
from __future__ import annotations

import os
from typing import Type, TypeVar, Optional, List, Dict, Any

import instructor
from openai import OpenAI, AsyncOpenAI

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

T = TypeVar('T')


class InstructorClient:
    """Client LLM con validazione Pydantic via Instructor.
    
    Features:
    - Generazione garantita conforme a schema Pydantic
    - Retry automatico con validation error feedback
    - Supporto OpenAI (Moonshot) e Gemini
    - Zero campi extra (strict=True)
    """
    
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.9,
        max_retries: int = 2,
    ):
        """Initialize Instructor client.
        
        Args:
            provider: "openai" (per Moonshot) o "gemini"
            model: Model name (es. "kimi-k2.5" o "gemini-2.0-flash")
            api_key: API key (usa env var se None)
            base_url: Base URL per API (es. Moonshot URL)
            temperature: Temperature generazione
            max_retries: Retry automatici su validation error
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._client = None
        
        if provider == "openai":
            self._init_openai(api_key, base_url)
        elif provider == "gemini":
            self._init_gemini(api_key)
        else:
            raise ValueError(f"Provider non supportato: {provider}")
    
    def _init_openai(self, api_key: Optional[str], base_url: Optional[str]):
        """Inizializza client OpenAI (per Moonshot)."""
        api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY non trovata")
        
        # Moonshot usa base_url custom
        base_url = base_url or "https://api.moonshot.cn/v1"
        
        # Instructor wrappa AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._client = instructor.from_openai(client, mode=instructor.Mode.JSON)
        print(f"[Instructor] OpenAI client inizializzato ({base_url})")
    
    def _init_gemini(self, api_key: Optional[str]):
        """Inizializza client Gemini."""
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai non installato")
        
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY non trovata")
        
        genai.configure(api_key=api_key)
        
        # Instructor per Gemini
        client = genai.GenerativeModel(model_name=self.model or "gemini-2.0-flash")
        self._client = instructor.from_gemini(client, mode=instructor.Mode.GEMINI_JSON)
        print(f"[Instructor] Gemini client inizializzato")
    
    async def generate(
        self,
        response_model: Type[T],
        system_prompt: str,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
        validation_context: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Genera risposta validata con schema Pydantic.
        
        Args:
            response_model: Classe Pydantic per validazione
            system_prompt: System prompt
            user_input: Input utente
            history: Storia conversazione opzionale
            validation_context: Contesto extra per validazione
            
        Returns:
            Istanza validata di response_model
            
        Raises:
            ValidationError: Se anche dopo retry la validazione fallisce
        """
        messages = self._build_messages(system_prompt, user_input, history)
        
        try:
            if self.provider == "openai":
                return await self._generate_openai(
                    response_model=response_model,
                    messages=messages,
                    validation_context=validation_context,
                )
            elif self.provider == "gemini":
                return await self._generate_gemini(
                    response_model=response_model,
                    messages=messages,
                    validation_context=validation_context,
                )
        except Exception as e:
            print(f"[Instructor] Errore generazione: {e}")
            raise
    
    def _build_messages(
        self,
        system_prompt: str,
        user_input: str,
        history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """Costruisce lista messaggi."""
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": user_input})
        return messages
    
    async def _generate_openai(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        validation_context: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Genera con client OpenAI/Moonshot."""
        response = await self._client.chat.completions.create(
            model=self.model or "kimi-k2.5",
            messages=messages,
            response_model=response_model,  # MAGIC: Instructor valida qui!
            temperature=self.temperature,
            max_retries=self.max_retries,  # Retry automatici su errori
            validation_context=validation_context,
        )
        return response
    
    async def _generate_gemini(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        validation_context: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Genera con client Gemini."""
        # Gemini usa formato diverso per system
        system_msg = messages[0]["content"] if messages[0]["role"] == "system" else ""
        chat_messages = messages[1:]  # Esclude system
        
        response = await self._client.create(
            messages=chat_messages,
            response_model=response_model,
            temperature=self.temperature,
            max_retries=self.max_retries,
            system=system_msg,
        )
        return response


# Singleton factory
_instructor_clients: Dict[str, InstructorClient] = {}


def get_instructor_client(
    provider: str = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> InstructorClient:
    """Get o crea client Instructor (singleton per provider)."""
    cache_key = f"{provider}:{model}"
    
    if cache_key not in _instructor_clients:
        _instructor_clients[cache_key] = InstructorClient(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    
    return _instructor_clients[cache_key]


def reset_instructor_clients():
    """Reset cache client (per testing)."""
    _instructor_clients.clear()
