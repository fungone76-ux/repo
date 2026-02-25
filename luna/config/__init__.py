"""Configuration loaders for Luna RPG v4."""
from pathlib import Path
from typing import List, Dict, Any
import yaml


class ModelConfig:
    """LLM model configuration loader."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self) -> None:
        """Load model configuration from YAML."""
        config_path = Path(__file__).parent / "models.yaml"
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # Default configuration if file not found
            self._config = {
                "gemini": {
                    "primary": "gemini-2.0-flash",
                    "fallbacks": ["gemini-1.5-pro", "gemini-1.5-flash"],
                    "temperature": 0.95,
                    "max_tokens": 2048,
                    "top_p": 0.98,
                    "top_k": 40,
                },
                "moonshot": {
                    "primary": "kimi-k2.5",
                    "temperature": 0.9,
                    "max_tokens": 2048,
                }
            }
    
    @property
    def gemini_primary(self) -> str:
        """Primary Gemini model."""
        return self._config.get("gemini", {}).get("primary", "gemini-2.0-flash")
    
    @property
    def gemini_fallbacks(self) -> List[str]:
        """List of fallback Gemini models."""
        return self._config.get("gemini", {}).get("fallbacks", [])
    
    @property
    def gemini_settings(self) -> Dict[str, Any]:
        """Gemini generation settings."""
        gemini = self._config.get("gemini", {})
        return {
            "temperature": gemini.get("temperature", 0.95),
            "max_tokens": gemini.get("max_tokens", 2048),
            "top_p": gemini.get("top_p", 0.98),
            "top_k": gemini.get("top_k", 40),
        }
    
    @property
    def moonshot_primary(self) -> str:
        """Primary Moonshot model."""
        return self._config.get("moonshot", {}).get("primary", "kimi-k2.5")
    
    @property
    def moonshot_settings(self) -> Dict[str, Any]:
        """Moonshot generation settings."""
        moonshot = self._config.get("moonshot", {})
        return {
            "temperature": moonshot.get("temperature", 0.9),
            "max_tokens": moonshot.get("max_tokens", 2048),
        }


# Singleton instance
_model_config = None


def get_model_config() -> ModelConfig:
    """Get the model configuration singleton."""
    global _model_config
    if _model_config is None:
        _model_config = ModelConfig()
    return _model_config
