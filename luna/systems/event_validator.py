"""Event Schema Validator - Verifies global events have all required fields for LLM transmission.

This module ensures that event definitions in YAML are complete and can be properly
transmitted to the LLM for narrative coherence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"       # Blocks functionality
    WARNING = "warning"   # Degraded functionality
    INFO = "info"         # Suggestion for improvement


@dataclass
class ValidationIssue:
    """Single validation issue."""
    event_id: str
    severity: ValidationSeverity
    field: str
    message: str


@dataclass
class ValidationResult:
    """Complete validation result for all events."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    
    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    def get_warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class EventSchemaValidator:
    """Validates global event definitions against the LLM transmission schema.
    
    Required fields for proper LLM transmission:
    - meta.title: Display name
    - meta.description: Short description
    - effects.duration: How long the event lasts
    - effects.atmosphere_change: Emotional tone for LLM
    - narrative_prompt: Narrative context for LLM
    
    Optional but recommended:
    - meta.icon: Visual indicator
    - effects.visual_tags: Image generation hints
    """
    
    # Fields required for LLM transmission
    REQUIRED_FIELDS = {
        "meta.title": "Event display name (shown to player)",
        "meta.description": "Short description of the event",
        "effects.duration": "Event duration in turns",
        "effects.atmosphere_change": "Emotional tone/atmosphere (CRITICAL for LLM)",
        "narrative_prompt": "Detailed narrative context (CRITICAL for LLM)",
    }
    
    # Fields that are recommended but not required
    RECOMMENDED_FIELDS = {
        "meta.icon": "Emoji/icon for visual identification",
        "effects.visual_tags": "Tags for image generation coherence",
        "effects.location_modifiers": "Changes to location accessibility",
    }
    
    # Valid trigger types
    VALID_TRIGGER_TYPES = {
        "random", "conditional", "time", "location", 
        "affinity", "flag", "scheduled"
    }
    
    def __init__(self, world: Any) -> None:
        """Initialize validator with world definition.
        
        Args:
            world: World definition containing global_events
        """
        self.world = world
        self.event_definitions = getattr(world, 'global_events', {})
    
    def validate_all(self) -> ValidationResult:
        """Validate all event definitions in the world.
        
        Returns:
            ValidationResult with all issues found
        """
        issues: List[ValidationIssue] = []
        
        if not self.event_definitions:
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    event_id="global",
                    severity=ValidationSeverity.WARNING,
                    field="global_events",
                    message="No global events defined in world"
                )]
            )
        
        for event_id, event_def in self.event_definitions.items():
            event_issues = self._validate_single_event(event_id, event_def)
            issues.extend(event_issues)
        
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            issues=issues
        )
    
    def _validate_single_event(
        self, 
        event_id: str, 
        event_def: Any
    ) -> List[ValidationIssue]:
        """Validate a single event definition.
        
        Args:
            event_id: Event identifier
            event_def: Event definition object
            
        Returns:
            List of validation issues
        """
        issues: List[ValidationIssue] = []
        
        # Get raw data for validation
        raw_data = self._get_raw_event_data(event_id, event_def)
        
        # Validate required fields
        issues.extend(self._validate_required_fields(event_id, raw_data))
        
        # Validate trigger configuration
        issues.extend(self._validate_trigger(event_id, raw_data))
        
        # Validate effects
        issues.extend(self._validate_effects(event_id, raw_data))
        
        # Validate narrative prompt
        issues.extend(self._validate_narrative_prompt(event_id, raw_data))
        
        # Validate recommended fields
        issues.extend(self._validate_recommended_fields(event_id, raw_data))
        
        return issues
    
    def _get_raw_event_data(self, event_id: str, event_def: Any) -> Dict[str, Any]:
        """Extract raw data from event definition for validation.
        
        Handles both Pydantic models and dict-like objects.
        """
        data: Dict[str, Any] = {"id": event_id}
        
        if hasattr(event_def, 'dict'):
            # Pydantic model
            data.update(event_def.dict())
        elif hasattr(event_def, '__dict__'):
            # Dataclass or regular object
            data.update(event_def.__dict__)
        elif isinstance(event_def, dict):
            # Plain dictionary
            data.update(event_def)
        
        return data
    
    def _validate_required_fields(
        self, 
        event_id: str, 
        data: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate that all required fields are present and non-empty."""
        issues: List[ValidationIssue] = []
        
        # Check title (can be in meta.title or top-level title)
        meta = data.get('meta', {})
        if isinstance(meta, dict):
            title = meta.get('title', '').strip()
        else:
            title = getattr(meta, 'title', '').strip()
        
        # Also check top-level title (Pydantic model stores it there)
        if not title:
            title = data.get('title', '').strip()
        
        if not title:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="meta.title",
                message=f"Missing required field: meta.title - {self.REQUIRED_FIELDS['meta.title']}"
            ))
        
        # Check description (can be in meta.description or top-level description)
        if isinstance(meta, dict):
            desc = meta.get('description', '').strip()
        else:
            desc = getattr(meta, 'description', '').strip()
        
        # Also check top-level description (Pydantic model stores it there)
        if not desc:
            desc = data.get('description', '').strip()
        
        if not desc:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="meta.description",
                message=f"Missing required field: meta.description - {self.REQUIRED_FIELDS['meta.description']}"
            ))
        
        # Check effects.duration
        effects = data.get('effects', {})
        if isinstance(effects, dict):
            duration = effects.get('duration')
        else:
            duration = getattr(effects, 'duration', None)
        
        if duration is None or duration <= 0:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="effects.duration",
                message=f"Invalid or missing: effects.duration must be > 0 - {self.REQUIRED_FIELDS['effects.duration']}"
            ))
        
        # Check effects.atmosphere_change
        if isinstance(effects, dict):
            atmosphere = effects.get('atmosphere_change', '').strip()
        else:
            atmosphere = getattr(effects, 'atmosphere_change', '').strip()
        
        if not atmosphere:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="effects.atmosphere_change",
                message=f"Missing required field: effects.atmosphere_change - {self.REQUIRED_FIELDS['effects.atmosphere_change']}"
            ))
        else:
            # Check for Italian words (common atmosphere words in Italian)
            italian_atmosphere = ['drammatico', 'teso', 'romantico', 'intimo', 'oscur', 'buio', 'luce', 'felice', 'triste']
            if any(word in atmosphere.lower() for word in italian_atmosphere):
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.WARNING,
                    field="effects.atmosphere_change",
                    message=f"atmosphere_change appears to be in Italian ('{atmosphere}'). Use English for better LLM comprehension."
                ))
        
        # Check narrative_prompt
        prompt = data.get('narrative_prompt', '').strip()
        if not prompt:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="narrative_prompt",
                message=f"Missing required field: narrative_prompt - {self.REQUIRED_FIELDS['narrative_prompt']}"
            ))
        elif len(prompt) < 20:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.WARNING,
                field="narrative_prompt",
                message=f"narrative_prompt is very short ({len(prompt)} chars). Consider adding more context for the LLM."
            ))
        else:
            # Check if it might be Italian (simple heuristic)
            italian_words = ['il ', 'la ', 'lo ', 'un ', 'una ', 'con ', 'per ', 'che ', 'sono', 'sei', 'tuoni', 'pioggia', 'scuola', 'notte', 'giorno']
            if any(word in prompt.lower() for word in italian_words):
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.WARNING,
                    field="narrative_prompt",
                    message="narrative_prompt appears to be in Italian. For best LLM results, use English (the game will still respond in Italian)."
                ))
        
        return issues
    
    def _validate_trigger(
        self, 
        event_id: str, 
        data: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate trigger configuration."""
        issues: List[ValidationIssue] = []
        
        trigger = data.get('trigger', {})
        if isinstance(trigger, dict):
            trigger_type = trigger.get('type', 'random')
        else:
            trigger_type = getattr(trigger, 'type', 'random')
        
        if trigger_type not in self.VALID_TRIGGER_TYPES:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="trigger.type",
                message=f"Invalid trigger type: '{trigger_type}'. Valid: {', '.join(self.VALID_TRIGGER_TYPES)}"
            ))
        
        # Check chance for random triggers
        if trigger_type == 'random':
            if isinstance(trigger, dict):
                chance = trigger.get('chance')
            else:
                chance = getattr(trigger, 'chance', None)
            
            if chance is None:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.WARNING,
                    field="trigger.chance",
                    message="Random trigger without 'chance' field will use default 0.1"
                ))
            elif not 0 <= chance <= 1:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.ERROR,
                    field="trigger.chance",
                    message=f"trigger.chance must be between 0 and 1, got {chance}"
                ))
        
        return issues
    
    def _validate_effects(
        self, 
        event_id: str, 
        data: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate effects configuration."""
        issues: List[ValidationIssue] = []
        
        effects = data.get('effects', {})
        if not effects:
            return issues
        
        if isinstance(effects, dict):
            effects_dict = effects
        else:
            effects_dict = effects.__dict__ if hasattr(effects, '__dict__') else {}
        
        # Validate visual_tags
        visual_tags = effects_dict.get('visual_tags', [])
        if visual_tags and not isinstance(visual_tags, list):
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="effects.visual_tags",
                message="visual_tags must be a list of strings"
            ))
        
        # Validate location_modifiers
        location_mods = effects_dict.get('location_modifiers', [])
        if location_mods:
            if not isinstance(location_mods, list):
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.ERROR,
                    field="effects.location_modifiers",
                    message="location_modifiers must be a list"
                ))
            else:
                for i, mod in enumerate(location_mods):
                    if not isinstance(mod, dict):
                        issues.append(ValidationIssue(
                            event_id=event_id,
                            severity=ValidationSeverity.ERROR,
                            field=f"effects.location_modifiers[{i}]",
                            message="Each location_modifier must be an object with 'location' field"
                        ))
                    elif 'location' not in mod:
                        issues.append(ValidationIssue(
                            event_id=event_id,
                            severity=ValidationSeverity.ERROR,
                            field=f"effects.location_modifiers[{i}]",
                            message="location_modifier missing required 'location' field"
                        ))
        
        # Validate affinity_multiplier
        mult = effects_dict.get('affinity_multiplier')
        if mult is not None and not isinstance(mult, (int, float)):
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.ERROR,
                field="effects.affinity_multiplier",
                message="affinity_multiplier must be a number"
            ))
        
        return issues
    
    def _validate_narrative_prompt(
        self, 
        event_id: str, 
        data: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate narrative prompt content."""
        issues: List[ValidationIssue] = []
        
        prompt = data.get('narrative_prompt', '')
        if not prompt:
            return issues
        
        # Check for placeholders that will be substituted
        valid_placeholders = {
            '{current_companion}',
            '{location}',
            '{time}',
            '{player_name}',
        }
        
        # Simple placeholder detection
        import re
        placeholders = re.findall(r'\{[^}]+\}', prompt)
        
        for ph in placeholders:
            if ph not in valid_placeholders:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    severity=ValidationSeverity.WARNING,
                    field="narrative_prompt",
                    message=f"Unknown placeholder '{ph}' in narrative_prompt. Valid: {', '.join(valid_placeholders)}"
                ))
        
        # Check prompt quality
        word_count = len(prompt.split())
        if word_count < 10:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.WARNING,
                field="narrative_prompt",
                message=f"narrative_prompt is very short ({word_count} words). Aim for 20-50 words for best LLM results."
            ))
        elif word_count > 100:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.INFO,
                field="narrative_prompt",
                message=f"narrative_prompt is quite long ({word_count} words). Consider being more concise."
            ))
        
        return issues
    
    def _validate_recommended_fields(
        self, 
        event_id: str, 
        data: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Check for recommended but optional fields."""
        issues: List[ValidationIssue] = []
        
        # Check icon (can be in meta.icon or top-level)
        meta = data.get('meta', {})
        if isinstance(meta, dict):
            icon = meta.get('icon')
        else:
            icon = getattr(meta, 'icon', None)
        
        # Also check top-level (some models store it there)
        if not icon:
            icon = data.get('icon')
        
        if not icon:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.INFO,
                field="meta.icon",
                message=f"Missing recommended field: meta.icon - {self.RECOMMENDED_FIELDS['meta.icon']}"
            ))
        
        effects = data.get('effects', {})
        if isinstance(effects, dict):
            visual_tags = effects.get('visual_tags', [])
        else:
            visual_tags = getattr(effects, 'visual_tags', [])
        
        if not visual_tags:
            issues.append(ValidationIssue(
                event_id=event_id,
                severity=ValidationSeverity.INFO,
                field="effects.visual_tags",
                message=f"Missing recommended field: effects.visual_tags - {self.RECOMMENDED_FIELDS['effects.visual_tags']}"
            ))
        
        return issues
    
    def print_report(self, result: Optional[ValidationResult] = None) -> None:
        """Print a formatted validation report.
        
        Args:
            result: Validation result to print. If None, runs validation.
        """
        if result is None:
            result = self.validate_all()
        
        print("=" * 60)
        print("GLOBAL EVENTS VALIDATION REPORT")
        print("=" * 60)
        print(f"Events checked: {len(self.event_definitions)}")
        print(f"Overall status: {'VALID' if result.is_valid else 'INVALID'}")
        print(f"Errors: {len(result.get_errors())}")
        print(f"Warnings: {len(result.get_warnings())}")
        print("-" * 60)
        
        if not result.issues:
            print("All events are properly configured for LLM transmission!")
        else:
            for issue in result.issues:
                icon = "❌" if issue.severity == ValidationSeverity.ERROR else \
                       "⚠️" if issue.severity == ValidationSeverity.WARNING else "ℹ️"
                print(f"{icon} [{issue.event_id}] {issue.field}: {issue.message}")
        
        print("=" * 60)


def validate_world_events(world: Any, print_report_output: bool = True) -> ValidationResult:
    """Convenience function to validate events in a world.
    
    Args:
        world: World definition
        print_report_output: Whether to print the report
        
    Returns:
        ValidationResult
    """
    validator = EventSchemaValidator(world)
    result = validator.validate_all()
    
    if print_report_output:
        validator.print_report(result)
    
    return result
