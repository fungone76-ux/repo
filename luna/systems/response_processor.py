"""Response Processor - Handles LLM response validation and parsing.

V4.3 REFACTOR: Extracted from engine.py
Handles: JSON parsing, guardrails validation, retry logic, fallback responses.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from luna.core.models import LLMResponse, TurnResult
from luna.ai.json_repair import repair_json

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of response processing."""
    success: bool
    llm_response: Optional[LLMResponse] = None
    error_message: str = ""
    needs_retry: bool = False
    retry_prompt_addition: str = ""


class ResponseProcessor:
    """Processes and validates LLM responses with retry logic."""
    
    def __init__(self, max_retries: int = 3) -> None:
        """Initialize processor.
        
        Args:
            max_retries: Maximum retry attempts for validation failures
        """
        self.max_retries = max_retries
    
    async def process(
        self,
        raw_response: Any,
        user_input: str,
        system_prompt: str,
        llm_manager: Any,
    ) -> Tuple[ProcessResult, str]:
        """Process raw LLM response with validation and retries.
        
        Args:
            raw_response: Raw response from LLM
            user_input: Original user input
            system_prompt: System prompt used
            llm_manager: LLM manager for retries
            
        Returns:
            Tuple of (ProcessResult, updated_system_prompt)
        """
        current_retry = 0
        updated_prompt = system_prompt
        last_error = ""
        
        while current_retry <= self.max_retries:
            try:
                # Parse JSON
                parsed = self._parse_response(raw_response)
                if not parsed:
                    raise ValueError("Failed to parse JSON response")
                
                # Validate with guardrails
                validation_result = self._validate_with_guardrails(parsed)
                
                if validation_result.success:
                    return validation_result, updated_prompt
                
                # Validation failed but recoverable
                if current_retry < self.max_retries and validation_result.needs_retry:
                    logger.warning(
                        f"[ResponseProcessor] Validation failed (attempt {current_retry + 1}): "
                        f"{validation_result.error_message}"
                    )
                    updated_prompt += validation_result.retry_prompt_addition
                    
                    # Retry with corrected prompt
                    raw_response = await llm_manager.generate(
                        system_prompt=updated_prompt,
                        user_input=user_input,
                        history=[],  # Fresh retry
                        json_mode=True,
                    )
                    current_retry += 1
                    continue
                
                # Validation failed irrecoverably
                return validation_result, updated_prompt
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"[ResponseProcessor] Processing error: {e}")
                
                if current_retry < self.max_retries:
                    current_retry += 1
                    # Add error context to prompt
                    updated_prompt += f"\n\nERROR PREVIOUS ATTEMPT: {last_error}\nPlease fix the JSON format."
                    
                    try:
                        raw_response = await llm_manager.generate(
                            system_prompt=updated_prompt,
                            user_input=user_input,
                            history=[],
                            json_mode=True,
                        )
                    except Exception as retry_err:
                        logger.error(f"[ResponseProcessor] Retry failed: {retry_err}")
                        break
                else:
                    break
        
        # All retries exhausted
        return ProcessResult(
            success=False,
            error_message=f"Failed after {self.max_retries} retries. Last error: {last_error}",
        ), updated_prompt
    
    def _parse_response(self, raw_response: Any) -> Optional[Dict[str, Any]]:
        """Parse raw response into dict, with JSON repair."""
        raw_text = ""
        
        if hasattr(raw_response, 'raw_response'):
            raw_text = raw_response.raw_response
        elif hasattr(raw_response, 'text'):
            raw_text = raw_response.text
        elif isinstance(raw_response, str):
            raw_text = raw_response
        else:
            raw_text = str(raw_response)
        
        if not raw_text:
            return None
        
        try:
            # Try direct parsing
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try repair
            try:
                repaired = repair_json(raw_text)
                return json.loads(repaired)
            except Exception as repair_err:
                logger.error(f"[ResponseProcessor] JSON repair failed: {repair_err}")
                return None
    
    def _validate_with_guardrails(self, parsed: Dict[str, Any]) -> ProcessResult:
        """Validate parsed response using guardrails."""
        try:
            from luna.ai.guardrails import validate_llm_response, GuardrailsValidationError
            
            llm_response = validate_llm_response(parsed)
            
            return ProcessResult(
                success=True,
                llm_response=llm_response,
            )
            
        except GuardrailsValidationError as guard_err:
            from luna.ai.guardrails import ResponseGuardrails
            
            correction = ResponseGuardrails.get_retry_prompt(guard_err)
            
            return ProcessResult(
                success=False,
                error_message=str(guard_err),
                needs_retry=True,
                retry_prompt_addition=correction,
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                error_message=f"Validation error: {e}",
                needs_retry=False,
            )
    
    def create_fallback_response(
        self,
        user_input: str,
        turn_number: int,
        companion_name: str,
    ) -> LLMResponse:
        """Create a fallback response when all processing fails."""
        logger.warning(f"[ResponseProcessor] Creating fallback response for turn {turn_number}")
        
        return LLMResponse(
            text=f"*{companion_name} sembra confusa e non risponde immediatamente.* "
                 f'"Scusi... ho perso il filo. Cosa stavamo dicendo?"',
            visual_en=f"close up, {companion_name} confused expression, soft lighting",
            tags_en=["close up", "confused", "masterpiece", "detailed"],
            approach_used="fallback",
            composition="close_up",
            updates={},
            raw_response="{}",
        )
    
    def apply_safety_filters(self, llm_response: LLMResponse) -> LLMResponse:
        """Apply final safety filters to response."""
        # Check for blocked terms in text
        blocked_patterns = [
            r"\b(ascoltami|ti stai sbagliando|non capisci un nulla)\b",
        ]
        
        import re
        text_lower = llm_response.text.lower()
        
        for pattern in blocked_patterns:
            if re.search(pattern, text_lower):
                # Replace with safer alternative
                llm_response.text = llm_response.text.replace(
                    re.search(pattern, text_lower).group(),
                    "*sospira*"
                )
        
        return llm_response
