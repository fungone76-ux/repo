"""LLM-based personality analysis for advanced behavioral detection.

Uses the LLM to analyze player behavior patterns from conversation history.
More accurate than regex, understands context and nuance.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from luna.core.models import BehaviorType, TraitIntensity
from luna.ai.manager import get_llm_manager


class PersonalityAnalyzer:
    """LLM-based personality analysis system.
    
    Analyzes conversation history to detect behavioral patterns.
    Runs periodically (every N turns) for efficiency.
    """
    
    # Behavior types the LLM can detect
    BEHAVIOR_TYPES = [
        "aggressive",
        "shy",
        "romantic",
        "dominant",
        "submissive",
        "curious",
        "teasing",
        "protective",
        "neutral",
    ]
    
    # Impression dimensions
    IMPRESSION_DIMENSIONS = [
        "trust",
        "attraction",
        "fear",
        "curiosity",
        "dominance_balance",
    ]
    
    def __init__(self, analysis_interval: int = 3) -> None:
        """Initialize personality analyzer.
        
        Args:
            analysis_interval: Analyze every N turns (default 3)
        """
        self.analysis_interval = analysis_interval
        self._llm_manager = None  # Lazy loaded
    
    async def analyze_behavior(
        self,
        companion_name: str,
        history: List[Dict[str, str]],
        current_affinity: int,
    ) -> Dict[str, Any]:
        """Analyze player behavior from conversation history.
        
        Args:
            companion_name: Name of current companion
            history: Recent conversation history
            current_affinity: Current affinity level
            
        Returns:
            Analysis result with detected traits and impression changes
        """
        if not history:
            return {"traits": [], "impression_changes": {}}
        
        # Get LLM manager (lazy init)
        if self._llm_manager is None:
            self._llm_manager = get_llm_manager()
        
        # Build analysis prompt
        system_prompt = self._build_system_prompt(companion_name, current_affinity)
        
        # Format history for analysis
        history_text = self._format_history(history)
        
        try:
            # Call LLM for analysis
            response = await self._llm_manager.generate(
                system_prompt=system_prompt,
                user_input=history_text,
                history=[],
                json_mode=True,
                use_mock=False,  # Force real analysis
            )
            
            # Parse result
            return self._parse_analysis_response(response.text)
            
        except Exception as e:
            print(f"[PersonalityAnalyzer] Analysis failed: {e}")
            return {"traits": [], "impression_changes": {}, "error": str(e)}
    
    def should_analyze(self, turn_count: int) -> bool:
        """Check if analysis should run this turn.
        
        Args:
            turn_count: Current turn number
            
        Returns:
            True if analysis should run
        """
        return turn_count % self.analysis_interval == 0
    
    def _build_system_prompt(self, companion_name: str, affinity: int) -> str:
        """Build system prompt for personality analysis.
        
        Args:
            companion_name: Target companion
            affinity: Current affinity level
            
        Returns:
            System prompt
        """
        return f"""=== PERSONALITY ANALYSIS SYSTEM ===

You are analyzing the player's behavior toward {companion_name} in a visual novel game.
Current relationship affinity: {affinity}/100

Analyze the conversation and classify the player's behavior.

BEHAVIOR TYPES (detect top 2-3):
- aggressive: Hostile, angry, threatening language
- shy: Nervous, hesitant, awkward, blushing
- romantic: Loving, affectionate, complimentary, intimate
- dominant: Commanding, controlling, ordering, assertive
- submissive: Yielding, apologizing, deferential, pleading
- curious: Asking questions, investigating, seeking information
- teasing: Playful mocking, flirting, joking, smirking
- protective: Defending, helping, shielding, rescuing
- neutral: None of the above clearly present

IMPRESSION CHANGES (suggest -10 to +10 for each):
Based on the behavior, how should {companion_name}'s impression change?
- trust: Does player seem trustworthy?
- attraction: Is player attractive/appealing?
- fear: Does player intimidate?
- curiosity: Does player make {companion_name} curious?
- dominance_balance: Who has power? (-10 player dominant, +10 NPC dominant)

=== OUTPUT FORMAT ===
Respond with valid JSON:
{{
  "traits": [
    {{"trait": "romantic", "confidence": 0.85, "evidence": "said 'you look beautiful'"}},
    {{"trait": "dominant", "confidence": 0.60, "evidence": "ordered 'come here now'"}}
  ],
  "impression_changes": {{
    "trust": 5,
    "attraction": 8,
    "fear": 0,
    "curiosity": 3,
    "dominance_balance": -5
  }},
  "archetype_hint": "The Romantic Dominant",
  "reasoning": "Brief explanation of analysis"
}}

=== RULES ===
1. Confidence scores 0.0-1.0 (higher = more certain)
2. Only include traits with confidence >= 0.4
3. Evidence must quote specific text
4. Impression changes range -10 to +10
5. Archetype_hint: optional summary descriptor
6. Be objective - analyze what IS present, not what might be"""

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for analysis.
        
        Args:
            history: List of messages
            
        Returns:
            Formatted text
        """
        lines = ["=== CONVERSATION TO ANALYZE ===", ""]
        
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                lines.append(f"Player: {content}")
            else:
                lines.append(f"Companion: {content}")
        
        lines.append("")
        lines.append("=== ANALYZE PLAYER'S BEHAVIOR ABOVE ===")
        
        return "\n".join(lines)
    
    def _parse_analysis_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM analysis response.
        
        Args:
            text: Raw JSON response
            
        Returns:
            Parsed analysis
        """
        try:
            data = json.loads(text)
            
            result = {
                "traits": [],
                "impression_changes": {},
                "archetype_hint": data.get("archetype_hint"),
                "reasoning": data.get("reasoning", ""),
            }
            
            # Parse traits
            for trait_data in data.get("traits", []):
                trait_name = trait_data.get("trait", "").lower()
                confidence = float(trait_data.get("confidence", 0))
                evidence = trait_data.get("evidence", "")
                
                # Map to BehaviorType
                try:
                    behavior_type = BehaviorType(trait_name)
                    # Convert confidence to intensity
                    if confidence >= 0.7:
                        intensity = TraitIntensity.STRONG
                    elif confidence >= 0.5:
                        intensity = TraitIntensity.MODERATE
                    else:
                        intensity = TraitIntensity.SUBTLE
                    
                    result["traits"].append({
                        "type": behavior_type,
                        "intensity": intensity,
                        "confidence": confidence,
                        "evidence": evidence,
                    })
                except ValueError:
                    # Unknown trait, skip
                    continue
            
            # Parse impression changes
            changes = data.get("impression_changes", {})
            for dim in self.IMPRESSION_DIMENSIONS:
                if dim in changes:
                    result["impression_changes"][dim] = int(changes[dim])
            
            return result
            
        except json.JSONDecodeError:
            print(f"[PersonalityAnalyzer] Failed to parse response: {text[:200]}")
            return {"traits": [], "impression_changes": {}}
    
    async def quick_impression_update(
        self,
        companion_name: str,
        user_input: str,
        current_impression: Dict[str, int],
    ) -> Dict[str, int]:
        """Quick impression update for single action (optional).
        
        Args:
            companion_name: Target companion
            user_input: Single user input
            current_impression: Current impression values
            
        Returns:
            Suggested impression changes
        """
        if not user_input:
            return {}
        
        if self._llm_manager is None:
            self._llm_manager = get_llm_manager()
        
        system_prompt = f"""Quick impression update for {companion_name}.
Current impression: {json.dumps(current_impression)}

Analyze this single player action and suggest impression changes (-5 to +5).
Output JSON: {{"trust": 2, "attraction": -1, ...}}"""
        
        try:
            response = await self._llm_manager.generate(
                system_prompt=system_prompt,
                user_input=user_input,
                history=[],
                json_mode=True,
            )
            
            data = json.loads(response.text)
            return {k: int(v) for k, v in data.items() if k in self.IMPRESSION_DIMENSIONS}
            
        except Exception as e:
            print(f"[PersonalityAnalyzer] Quick update failed: {e}")
            return {}
