"""Guardrails - Validazione rigorosa JSON con Pydantic.

Sistema di validazione "a scacchi" che garantisce:
1. Schema rigoroso (extra='forbid')
2. Validazione tipi completa
3. Errori dettagliati per retry
4. Sanitizzazione input/output
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel, ValidationError, ConfigDict

# NOTA: Import luna.core.models fatto dentro le funzioni per evitare circular import


class GuardrailsValidationError(Exception):
    """Errore validazione con dettagli per correzione."""
    
    def __init__(self, message: str, errors: list, suggestion: str):
        super().__init__(message)
        self.errors = errors
        self.suggestion = suggestion


class ResponseGuardrails:
    """Guardrails per validazione risposte LLM.
    
    Implementa validazione a più livelli:
    1. Sintassi JSON valida
    2. Schema Pydantic rigoroso (extra='forbid')
    3. Vincoli business logic
    """
    
    # Schema JSON per LLM (più dettagliato del precedente)
    JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Risposta narrativa in italiano. OBBLIGATORIO."
            },
            "visual_en": {
                "type": "string", 
                "description": "Descrizione visiva dettagliata in inglese per Stable Diffusion. OBBLIGATORIO."
            },
            "tags_en": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tag per qualità immagine (es. masterpiece, detailed)"
            },
            "body_focus": {
                "type": ["string", "null"],
                "description": "Parte del corpo in primo piano, se rilevante"
            },
            "secondary_characters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Altri personaggi visibili nella scena"
            },
            "approach_used": {
                "type": "string",
                "enum": ["standard", "physical_action", "question", "choice"],
                "description": "Tipo di approccio usato nella risposta"
            },
            "composition": {
                "type": "string", 
                "enum": ["close_up", "medium_shot", "wide_shot", "group", "scene"],
                "description": "Inquadratura fotografica"
            },
            "updates": {
                "type": "object",
                "description": "Aggiornamenti di stato proposti",
                "properties": {
                    "location": {"type": ["string", "null"]},
                    "time_of_day": {
                        "type": ["string", "null"],
                        "enum": ["Morning", "Afternoon", "Evening", "Night", None]
                    },
                    "current_outfit": {"type": ["string", "null"]},
                    "outfit_update": {
                        "type": ["object", "null"],
                        "properties": {
                            "style": {"type": ["string", "null"]},
                            "description": {"type": ["string", "null"]},
                            "modify_components": {"type": "object"},
                            "is_special": {"type": ["boolean", "null"]}
                        },
                        "additionalProperties": False
                    },
                    "affinity_change": {
                        "type": "object",
                        "description": "Cambi affinità: {nome: valore}"
                    },
                    "set_flags": {"type": "object"},
                    "npc_emotion": {"type": ["string", "null"]}
                },
                "additionalProperties": False
            },
            "new_fact": {
                "type": ["string", "null"],
                "description": "Nuovo fatto da ricordare"
            }
        },
        "required": ["text", "visual_en"],
        "additionalProperties": False
    }
    
    @classmethod
    def validate(cls, raw_response: Union[str, dict]):
        """Valida risposta LLM con guardrails rigorosi.
        
        Args:
            raw_response: JSON string o dict dalla risposta LLM
            
        Returns:
            LLMResponse validata
            
        Raises:
            GuardrailsValidationError: Se validazione fallisce con dettagli
        """
        # Step 1: Parse JSON
        if isinstance(raw_response, str):
            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise GuardrailsValidationError(
                    message=f"JSON non valido: {e}",
                    errors=[{"type": "json_parse", "detail": str(e)}],
                    suggestion="Verifica virgolette e parentesi nel JSON"
                )
        else:
            data = raw_response
        
        # Step 2: Rimuovi campi extra (prima di validazione)
        data = cls._sanitize_input(data)
        
        # Step 3: Validazione Pydantic rigorosa
        # Import qui per evitare circular import
        from luna.core.models import LLMResponse
        
        try:
            # Usa model_validate che rispetta extra='forbid'
            response = LLMResponse.model_validate(data)
        except ValidationError as e:
            errors = cls._format_pydantic_errors(e)
            suggestion = cls._generate_suggestion(errors)
            raise GuardrailsValidationError(
                message="Validazione schema fallita",
                errors=errors,
                suggestion=suggestion
            )
        
        # Step 4: Validazione business logic
        business_errors = cls._validate_business_logic(response)
        if business_errors:
            raise GuardrailsValidationError(
                message="Violazione vincoli business",
                errors=business_errors,
                suggestion=cls._generate_business_suggestion(business_errors)
            )
        
        return response
    
    @classmethod
    def _sanitize_input(cls, data: dict) -> dict:
        """Pulisci input rimuovendo campi non autorizzati.
        
        Questo previene errori extra='forbid' rimuovendo
        campi che l'LLM potrebbe aver inventato.
        """
        allowed_top_level = {
            "text", "visual_en", "tags_en", "body_focus",
            "secondary_characters", "approach_used", "composition",
            "updates", "new_fact", "raw_response", "provider"
        }
        
        allowed_updates = {
            "location", "time_of_day", "current_outfit", "outfit_update",
            "affinity_change", "set_flags", "npc_emotion", "npc_location",
            "npc_outfit", "new_quests", "complete_quests"
        }
        
        # Filtra top level
        sanitized = {k: v for k, v in data.items() if k in allowed_top_level}
        
        # Filtra updates se presente
        if "updates" in sanitized and isinstance(sanitized["updates"], dict):
            updates = sanitized["updates"]
            sanitized["updates"] = {
                k: v for k, v in updates.items() if k in allowed_updates
            }
        
        return sanitized
    
    @classmethod
    def _format_pydantic_errors(cls, error: ValidationError) -> list:
        """Formatta errori Pydantic in struttura leggibile."""
        errors = []
        for err in error.errors():
            errors.append({
                "field": " → ".join(str(x) for x in err["loc"]),
                "type": err["type"],
                "message": err["msg"],
                "input": str(err.get("input", "N/A"))[:50]
            })
        return errors
    
    @classmethod
    def _validate_business_logic(cls, response) -> list:
        """Valida vincoli di business specifici."""
        errors = []
        
        # Vincolo 1: text non vuoto
        if not response.text or len(response.text.strip()) < 10:
            errors.append({
                "field": "text",
                "type": "too_short",
                "message": "Risposta testuale troppo corta (< 10 caratteri)"
            })
        
        # Vincolo 2: visual_en non vuoto
        if not response.visual_en or len(response.visual_en.strip()) < 5:
            errors.append({
                "field": "visual_en",
                "type": "too_short", 
                "message": "Descrizione visiva troppo corta"
            })
        
        # Vincolo 3: affinity_change in range valido
        if response.updates and response.updates.affinity_change:
            for char, delta in response.updates.affinity_change.items():
                if not isinstance(delta, (int, float)):
                    errors.append({
                        "field": f"updates.affinity_change.{char}",
                        "type": "type_error",
                        "message": f"Affinità deve essere numero, trovato: {type(delta)}"
                    })
                elif abs(delta) > 10:
                    errors.append({
                        "field": f"updates.affinity_change.{char}",
                        "type": "value_error",
                        "message": f"Cambio affinità troppo grande: {delta} (max ±10)"
                    })
        
        # Vincolo 4: No HTML/script injection
        dangerous_patterns = [r'<script', r'javascript:', r'on\w+=', r'href=' ]
        text_combined = f"{response.text} {response.visual_en}"
        for pattern in dangerous_patterns:
            if re.search(pattern, text_combined, re.IGNORECASE):
                errors.append({
                    "field": "text/visual_en",
                    "type": "security",
                    "message": "Rilevato possibile codice dannoso"
                })
                break
        
        return errors
    
    @classmethod
    def _generate_suggestion(cls, errors: list) -> str:
        """Genera suggerimento per correzione errori."""
        suggestions = []
        
        for err in errors:
            field = err.get("field", "unknown")
            msg = err.get("message", "")
            
            if "extra_forbidden" in err.get("type", ""):
                suggestions.append(f"Rimuovi il campo non autorizzato: '{field}'")
            elif "type_error" in err.get("type", ""):
                suggestions.append(f"Correggi il tipo di '{field}': {msg}")
            elif "missing" in err.get("type", ""):
                suggestions.append(f"Aggiungi il campo richiesto: '{field}'")
            else:
                suggestions.append(f"Correggi '{field}': {msg}")
        
        return "; ".join(suggestions[:3])  # Max 3 suggerimenti
    
    @classmethod
    def _generate_business_suggestion(cls, errors: list) -> str:
        """Genera suggerimento per errori business logic."""
        if not errors:
            return ""
        
        first_error = errors[0]
        field = first_error.get("field", "")
        
        if "text" in field:
            return "Fornisci una risposta narrativa più dettagliata (min 10 char)"
        elif "visual_en" in field:
            return "Fornisci una descrizione visiva dettagliata per l'immagine"
        elif "affinity" in field:
            return "Correggi i valori affinità: devono essere numeri tra -10 e +10"
        elif "security" in first_error.get("type", ""):
            return "Rimuovi codice HTML/script dalla risposta"
        
        return "Correggi i vincoli di validazione indicati"
    
    @classmethod
    def get_retry_prompt(cls, error: GuardrailsValidationError) -> str:
        """Genera prompt per retry con correzione errori.
        
        Args:
            error: Errore di validazione
            
        Returns:
            Prompt da aggiungere per retry
        """
        prompt = "\n\n=== CORREZIONE ERRORI ===\n"
        prompt += f"La risposta precedente ha errori:\n"
        
        for i, err in enumerate(error.errors[:3], 1):
            prompt += f"{i}. {err.get('field', 'field')}: {err.get('message', 'error')}\n"
        
        prompt += f"\nISTRUZIONE: {error.suggestion}\n"
        prompt += "Genera una nuova risposta corretta seguendo rigorosamente lo schema."
        
        return prompt


class StrictValidator:
    """Validatore stretto per modelli Pydantic.
    
    Wrapper che garantisce extra='forbid' su qualsiasi modello.
    """
    
    @staticmethod
    def validate_strict(data: dict, model_class: Type[BaseModel]) -> BaseModel:
        """Valida dati con modello, rifiutando campi extra.
        
        Args:
            data: Dati da validare
            model_class: Classe Pydantic
            
        Returns:
            Istanza validata
            
        Raises:
            GuardrailsValidationError: Se validazione fallisce
        """
        # Crea modello temporaneo con extra='forbid'
        strict_model = type(
            f"Strict{model_class.__name__}",
            (model_class,),
            {
                "model_config": ConfigDict(
                    strict=True,
                    extra="forbid",
                    validate_assignment=True
                )
            }
        )
        
        try:
            return strict_model.model_validate(data)
        except ValidationError as e:
            errors = [
                {
                    "field": " → ".join(str(x) for x in err["loc"]),
                    "type": err["type"],
                    "message": err["msg"]
                }
                for err in e.errors()
            ]
            raise GuardrailsValidationError(
                message=f"Validazione {model_class.__name__} fallita",
                errors=errors,
                suggestion="Rimuovi campi non autorizzati o correggi i tipi"
            )


# Singleton per uso globale
guardrails = ResponseGuardrails()


def validate_llm_response(raw_response: Union[str, dict]):
    """Funzione di convenienza per validazione.
    
    Args:
        raw_response: Risposta grezza dall'LLM
        
    Returns:
        LLMResponse validata
    """
    return guardrails.validate(raw_response)