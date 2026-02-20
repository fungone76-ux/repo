"""Application configuration with Pydantic Settings.

Handles environment variables, user preferences, and runtime configuration.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file.
    
    All configuration is loaded from environment variables or .env file.
    This is the single source of truth for application configuration.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # =========================================================================
    # Execution Mode
    # =========================================================================
    execution_mode: Literal["LOCAL", "RUNPOD"] = Field(
        default="LOCAL",
        description="Execution mode: LOCAL (SD WebUI) or RUNPOD (ComfyUI + Video)",
    )
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    
    # =========================================================================
    # LLM Configuration
    # =========================================================================
    llm_provider: Literal["gemini", "moonshot", "openai", "ollama"] = Field(
        default="gemini",
        description="Primary LLM provider",
    )
    
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key",
    )
    
    moonshot_api_key: Optional[str] = Field(
        default=None,
        description="Moonshot AI API key",
    )
    
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
    )
    
    # Ollama (local LLM)
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Default Ollama model",
    )
    
    # =========================================================================
    # RunPod Configuration (Cloud GPU)
    # =========================================================================
    runpod_id: Optional[str] = Field(
        default=None,
        description="RunPod ID for cloud GPU",
    )
    
    runpod_api_key: Optional[str] = Field(
        default=None,
        description="RunPod API key",
    )
    
    # =========================================================================
    # Local Services
    # =========================================================================
    local_sd_url: str = Field(
        default="http://127.0.0.1:7860",
        description="Local Stable Diffusion WebUI URL",
    )
    
    local_comfy_url: str = Field(
        default="http://127.0.0.1:8188",
        description="Local ComfyUI URL",
    )
    
    # =========================================================================
    # Database
    # =========================================================================
    database_url: str = Field(
        default="sqlite+aiosqlite:///storage/saves/luna_v4.db",
        description="Database connection URL",
    )
    
    # =========================================================================
    # Media Generation
    # =========================================================================
    google_credentials_path: Path = Field(
        default=Path("google_credentials.json"),
        description="Path to Google Cloud credentials for TTS",
    )
    
    video_enabled: bool = Field(
        default=False,
        description="Enable video generation (requires RunPod)",
    )
    
    video_motion_speed: int = Field(
        default=6,
        ge=1,
        le=10,
        description="Video motion speed (1-10)",
    )
    
    # Image settings
    image_width: int = Field(
        default=896,
        ge=512,
        le=2048,
        description="Image generation width",
    )
    
    image_height: int = Field(
        default=1152,
        ge=512,
        le=2048,
        description="Image generation height",
    )
    
    image_steps: int = Field(
        default=24,
        ge=1,
        le=100,
        description="Image sampling steps",
    )
    
    # =========================================================================
    # Game Settings
    # =========================================================================
    memory_history_limit: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of messages to keep in memory",
    )
    
    enable_semantic_memory: bool = Field(
        default=False,
        description="Enable semantic memory search using ChromaDB and embeddings",
    )
    
    memory_min_importance: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Minimum importance for memories to be included in context",
    )
    
    memory_max_context_facts: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of facts to include in memory context",
    )
    
    worlds_path: Path = Field(
        default=Path("worlds"),
        description="Path to worlds directory",
    )
    
    # =========================================================================
    # Development
    # =========================================================================
    mock_llm: bool = Field(
        default=False,
        description="Mock LLM responses for testing",
    )
    
    mock_media: bool = Field(
        default=False,
        description="Mock media generation for testing",
    )
    
    world_hot_reload: bool = Field(
        default=False,
        description="Enable world hot-reload (development)",
    )
    
    # =========================================================================
    # Validators
    # =========================================================================
    @field_validator("execution_mode")
    @classmethod
    def uppercase_execution_mode(cls, v: str) -> str:
        """Ensure execution mode is uppercase."""
        return v.upper()
    
    # =========================================================================
    # Computed Properties
    # =========================================================================
    @property
    def is_runpod(self) -> bool:
        """True if running in RunPod mode."""
        return self.execution_mode == "RUNPOD"
    
    @property
    def is_local(self) -> bool:
        """True if running in local mode."""
        return self.execution_mode == "LOCAL"
    
    @property
    def sd_url(self) -> str:
        """Stable Diffusion URL based on mode."""
        if self.is_runpod and self.runpod_id:
            return f"https://{self.runpod_id}-7860.proxy.runpod.net"
        return self.local_sd_url
    
    @property
    def comfy_url(self) -> Optional[str]:
        """ComfyUI URL based on mode."""
        if self.is_runpod and self.runpod_id:
            return f"https://{self.runpod_id}-8188.proxy.runpod.net"
        return self.local_comfy_url
    
    @property
    def video_available(self) -> bool:
        """True if video generation is available."""
        return (
            self.is_runpod 
            and self.video_enabled 
            and self.runpod_id is not None
            and self.comfy_url is not None
        )
    
    @property
    def has_llm_config(self) -> bool:
        """True if at least one LLM provider is configured."""
        return any([
            self.gemini_api_key,
            self.moonshot_api_key,
            self.openai_api_key,
        ])
    
    def validate_setup(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check LLM provider
        if not self.has_llm_config:
            errors.append("No LLM API key configured (GEMINI_API_KEY, MOONSHOT_API_KEY, or OPENAI_API_KEY)")
        
        # Check RunPod config
        if self.is_runpod and not self.runpod_id:
            errors.append("RUNPOD_ID required when EXECUTION_MODE=RUNPOD")
        
        # Check Google credentials for TTS
        if not self.google_credentials_path.exists():
            errors.append(f"Google credentials not found: {self.google_credentials_path}")
        
        return errors


# =========================================================================
# User Preferences (Persistent user settings)
# =========================================================================

_USER_PREFS_PATH = Path("storage/config/user_prefs.json")


class UserPreferences:
    """User preferences that persist between sessions.
    
    Stored as JSON file, separate from environment configuration.
    """
    
    def __init__(self) -> None:
        """Initialize and load preferences."""
        self._data: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load preferences from file."""
        if _USER_PREFS_PATH.exists():
            try:
                content = _USER_PREFS_PATH.read_text(encoding="utf-8")
                self._data = json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load user preferences: {e}")
                self._data = {}
    
    def save(self) -> None:
        """Save preferences to file."""
        try:
            _USER_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _USER_PREFS_PATH.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except IOError as e:
            print(f"Warning: Could not save user preferences: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get preference value."""
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set preference value and save."""
        self._data[key] = value
        self.save()
    
    def delete(self, key: str) -> None:
        """Delete preference."""
        if key in self._data:
            del self._data[key]
            self.save()
    
    # Common preferences with defaults
    @property
    def last_world(self) -> Optional[str]:
        """Last selected world."""
        return self.get("last_world")
    
    @last_world.setter
    def last_world(self, value: str) -> None:
        self.set("last_world", value)
    
    @property
    def last_companion(self) -> Optional[str]:
        """Last selected companion."""
        return self.get("last_companion")
    
    @last_companion.setter
    def last_companion(self, value: str) -> None:
        self.set("last_companion", value)
    
    @property
    def runpod_id(self) -> Optional[str]:
        """Saved RunPod ID."""
        return self.get("runpod_id")
    
    @runpod_id.setter
    def runpod_id(self, value: str) -> None:
        self.set("runpod_id", value)
    
    @property
    def enable_semantic_memory(self) -> bool:
        """Enable semantic memory search."""
        return self.get("enable_semantic_memory", False)
    
    @enable_semantic_memory.setter
    def enable_semantic_memory(self, value: bool) -> None:
        self.set("enable_semantic_memory", value)
    
    @property
    def memory_min_importance(self) -> int:
        """Minimum importance for memory context."""
        return self.get("memory_min_importance", 4)
    
    @memory_min_importance.setter
    def memory_min_importance(self, value: int) -> None:
        self.set("memory_min_importance", max(1, min(10, value)))
    
    @property
    def window_geometry(self) -> Optional[Dict[str, int]]:
        """Saved window geometry."""
        return self.get("window_geometry")
    
    @window_geometry.setter
    def window_geometry(self, value: Dict[str, int]) -> None:
        self.set("window_geometry", value)


# =========================================================================
# Singleton Access
# =========================================================================

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Uses lru_cache to ensure single instance across app.
    """
    return Settings()


def get_user_prefs() -> UserPreferences:
    """Get user preferences instance."""
    return UserPreferences()


def reload_settings() -> Settings:
    """Reload settings from environment (clears cache).
    
    Returns:
        Fresh settings instance
    """
    get_settings.cache_clear()
    return get_settings()
