"""JSON Repair utilities for LLM responses.

Handles malformed JSON from LLM providers with automatic fixing.
"""
from __future__ import annotations

import json
import re
from typing import Optional, Dict, Any


class JSONRepair:
    """Repair malformed JSON from LLM responses."""
    
    @staticmethod
    def repair(text: str) -> Optional[str]:
        """Attempt to repair malformed JSON.
        
        Args:
            text: Raw JSON string that may be malformed
            
        Returns:
            Repaired JSON string, or None if unrepairable
        """
        if not text or not text.strip():
            return None
        
        text = text.strip()
        
        # Try parsing as-is first
        try:
            json.loads(text)
            return text  # Already valid
        except json.JSONDecodeError:
            pass
        
        # Remove markdown code blocks
        text = JSONRepair._strip_markdown(text)
        
        # Fix common issues
        fixes = [
            JSONRepair._fix_trailing_commas,
            JSONRepair._fix_missing_commas,
            JSONRepair._fix_single_quotes,
            JSONRepair._fix_unquoted_keys,
            JSONRepair._fix_newlines_in_strings,
            JSONRepair._fix_comments,
        ]
        
        repaired = text
        for fix in fixes:
            try:
                repaired = fix(repaired)
            except Exception:
                pass
        
        # Validate
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown code block markers."""
        # Remove ```json and ``` markers
        text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text.strip()
    
    @staticmethod
    def _fix_trailing_commas(text: str) -> str:
        """Remove trailing commas before closing brackets."""
        # Remove trailing commas in objects and arrays
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text
    
    @staticmethod
    def _fix_missing_commas(text: str) -> str:
        """Add missing commas between properties/elements."""
        # Fix missing comma between "}  {" or "]  ["
        text = re.sub(r'(}\s*)(?={)', r'\1,', text)
        text = re.sub(r'("\s*)(?=")', r'\1,', text)
        return text
    
    @staticmethod
    def _fix_single_quotes(text: str) -> str:
        """Convert single quotes to double quotes."""
        # Simple replacement - may need refinement for edge cases
        return text.replace("'", '"')
    
    @staticmethod
    def _fix_unquoted_keys(text: str) -> str:
        """Quote unquoted object keys."""
        # Match word characters followed by colon
        pattern = r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:'
        replacement = r'\1"\2":'
        return re.sub(pattern, replacement, text)
    
    @staticmethod
    def _fix_newlines_in_strings(text: str) -> str:
        """Escape newlines inside JSON strings."""
        # Find string content and escape newlines within
        def escape_newlines(match):
            content = match.group(1)
            escaped = content.replace('\n', '\\n').replace('\r', '\\r')
            return f'"{escaped}"'
        
        # Match quoted strings
        return re.sub(r'"((?:[^"\\]|\\.)*?)"', escape_newlines, text)
    
    @staticmethod
    def _fix_comments(text: str) -> str:
        """Remove JSON comments (// and /* */)."""
        # Remove // comments
        text = re.sub(r'//[^\n]*', '', text)
        # Remove /* */ comments
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text
    
    @staticmethod
    def extract_json(text: str) -> Optional[str]:
        """Extract JSON object/array from text.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Extracted JSON string, or None if not found
        """
        if not text:
            return None
        
        # Try to find JSON object
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    # Try repairing
                    repaired = JSONRepair.repair(match)
                    if repaired:
                        return repaired
        
        return None


def repair_json(text: str, strict: bool = False) -> Optional[Dict[str, Any]]:
    """Repair and parse JSON.
    
    Args:
        text: Raw JSON text
        strict: If True, returns None if repair fails
        
    Returns:
        Parsed dict, or None if failed and strict=True
    """
    repaired = JSONRepair.repair(text)
    
    if repaired:
        try:
            result = json.loads(repaired)
            # Ensure we return a dict, not a list
            if isinstance(result, dict):
                return result
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                # If it's a list of dicts, return the first one
                return result[0]
            return None
        except json.JSONDecodeError:
            pass
    
    if strict:
        return None
    
    # Last resort: try to extract
    extracted = JSONRepair.extract_json(text)
    if extracted:
        try:
            result = json.loads(extracted)
            # Ensure we return a dict, not a list
            if isinstance(result, dict):
                return result
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                return result[0]
            return None
        except json.JSONDecodeError:
            pass
    
    return None
