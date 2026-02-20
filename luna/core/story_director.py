"""Story Director - Narrative structure controller.

Python controls the narrative arc, AI executes individual beats.
This is the industry-standard approach for AI-driven narrative games.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from luna.core.models import GameState, NarrativeArc, StoryBeat, BeatExecution
from luna.ai.manager import get_llm_manager


class StoryDirector:
    """Controls narrative structure while allowing AI creative freedom.

    The Story Director:
    1. Tracks which story beats have been completed
    2. Evaluates trigger conditions to activate beats
    3. Generates specific instructions for the LLM
    4. Validates that beats were executed correctly
    5. Maintains narrative coherence across turns
    """

    def __init__(self, narrative_arc: NarrativeArc) -> None:
        """Initialize story director.

        Args:
            narrative_arc: Narrative structure from world YAML
        """
        self.arc = narrative_arc
        self.beat_history: List[BeatExecution] = []
        self._beat_completed: set[str] = set()

    def get_active_instruction(self, game_state: GameState) -> Optional[Tuple[StoryBeat, str]]:
        """Check if a story beat should trigger this turn.

        Args:
            game_state: Current game state

        Returns:
            Tuple of (beat, instruction) or None if no beat triggers
        """
        candidates = []

        for beat in self.arc.beats:
            # Skip already completed beats (if once=True)
            if beat.once and beat.id in self._beat_completed:
                continue

            # Check trigger conditions
            if self._evaluate_trigger(beat.trigger, game_state):
                candidates.append(beat)

        if not candidates:
            return None

        # Sort by priority (lower number = higher priority)
        candidates.sort(key=lambda b: b.priority)
        selected_beat = candidates[0]

        # Generate instruction for LLM
        instruction = self._generate_beat_instruction(selected_beat, game_state)

        return selected_beat, instruction

    def _evaluate_trigger(self, trigger: str, game_state: GameState) -> bool:
        """Evaluate trigger condition against game state.

        Args:
            trigger: Condition string (e.g., "turn >= 10 AND affinity > 30")
            game_state: Current game state

        Returns:
            True if condition is met
        """
        if not trigger:
            return True

        # Build evaluation context
        context = {
            "turn": game_state.turn_count,
            "turn_count": game_state.turn_count,
            "location": game_state.current_location,
            "time": game_state.time_of_day,
            "companion": game_state.active_companion,
        }

        # Add affinity values
        for char, value in game_state.affinity.items():
            context[f"{char.lower()}_affinity"] = value
            context[f"affinity_{char.lower()}"] = value

        # Add flags
        for flag, value in game_state.quest_flags.items():
            context[flag] = value

        try:
            # Safe evaluation with limited context
            result = eval(trigger, {"__builtins__": {}}, context)
            return bool(result)
        except Exception as e:
            print(f"[StoryDirector] Error evaluating trigger '{trigger}': {e}")
            return False

    def _generate_beat_instruction(
        self,
        beat: StoryBeat,
        game_state: GameState
    ) -> str:
        """Generate LLM instruction for executing a beat.

        Args:
            beat: Story beat to execute
            game_state: Current game state

        Returns:
            Instruction text for the LLM
        """
        instruction_parts = [
            "=== MOMENTO NARRATIVO OBBLIGATORIO ===",
            "",
            f"Devi narrare ESATTAMENTE questo evento:",
            f"{beat.description}",
            "",
        ]

        if beat.tone:
            instruction_parts.extend([
                f"TONO RICHIESTO: {beat.tone}",
                "",
            ])

        if beat.required_elements:
            instruction_parts.extend([
                "ELEMENTI OBBLIGATORI (devono apparire nella scena):",
            ])
            for element in beat.required_elements:
                instruction_parts.append(f"  - {element}")
            instruction_parts.append("")

        # Add context about current state
        instruction_parts.extend([
            "CONTESTO ATTUALE:",
            f"  Turno: {game_state.turn_count}",
            f"  Location: {game_state.current_location}",
            f"  Companion attivo: {game_state.active_companion}",
            f"  Affinità: {game_state.affinity.get(game_state.active_companion, 0)}",
            "",
            "ISTRUZIONE: Scrivi la scena includendo TUTTI gli elementi obbligatori.",
            "======================================",
        ])

        return "\n".join(instruction_parts)

    async def validate_beat_execution(
        self,
        beat: StoryBeat,
        llm_response: str
    ) -> Tuple[bool, float, List[str]]:
        """Validate that LLM executed the beat correctly using LLM-as-a-Judge.

        Args:
            beat: Story beat that was supposed to be executed
            llm_response: LLM-generated text

        Returns:
            Tuple of (success, quality_score, missing_elements)
        """
        missing = []
        response_lower = llm_response.lower()

        # Check required elements
        for element in beat.required_elements:
            # Simple substring check (can be enhanced with NLP)
            if element.lower() not in response_lower:
                missing.append(element)

        # Calculate quality score
        if not beat.required_elements:
            base_quality = 1.0
        else:
            found = len(beat.required_elements) - len(missing)
            base_quality = found / len(beat.required_elements)

        base_success = len(missing) == 0

        # 2. LLM Judge Validation (Controllo Semantico)
        llm_manager = get_llm_manager()

        judge_prompt = (
            "Sei un Giudice Narrativo imparziale per un gioco di ruolo.\n"
            "Il tuo compito è verificare se un Obiettivo Narrativo è effettivamente "
            "avvenuto nel testo generato.\n\n"
            f"OBIETTIVO RICHIESTO:\n{beat.description}\n\n"
            "REGOLE DI GIUDIZIO:\n"
            "1. L'evento deve essere accaduto veramente (non solo menzionato o pensato).\n"
            "2. Se un personaggio si è rifiutato di farlo, l'evento NON è accaduto (success=false).\n\n"
            "Rispondi SOLO in formato JSON puro:\n"
            "{\n"
            '  "success": true/false,\n'
            '  "reason": "Spiegazione in 1 riga",\n'
            '  "quality": 0.0 a 1.0 (valuta la qualità dell\'esecuzione)\n'
            "}"
        )

        try:
            print(f"[StoryDirector] Validating beat '{beat.id}' via AI Judge...")
            judge_response = await llm_manager.generate(
                system_prompt=judge_prompt,
                user_input=f"TESTO GENERATO:\n{llm_response}",
                history=[],
                json_mode=True
            )

            # Pulisci e analizza il JSON
            text_json = judge_response.text.strip()
            if text_json.startswith("```json"):
                text_json = text_json[7:-3]
            elif text_json.startswith("```"):
                text_json = text_json[3:-3]

            data = json.loads(text_json)

            # Uniamo il giudizio dell'AI con la verifica delle parole chiave
            success = data.get("success", False)
            quality = float(data.get("quality", base_quality))
            print(f"[StoryDirector] Judge Verdict: {success} ({data.get('reason', '')})")

            return success, quality, missing

        except Exception as e:
            print(f"[StoryDirector] LLM Judge failed, using fallback check: {e}")
            return base_success, base_quality, missing

    def mark_beat_completed(
        self,
        beat: StoryBeat,
        narrative_text: str,
        quality: float = 1.0
    ) -> None:
        """Mark a beat as completed.

        Args:
            beat: Completed beat
            narrative_text: The narrative that fulfilled this beat
            quality: Execution quality score
        """
        from luna.core.models import BeatExecution

        execution = BeatExecution(
            beat_id=beat.id,
            triggered_at=0,  # Will be set from game state
            completed=True,
            execution_quality=quality,
            narrative_snapshot=narrative_text[:500],  # First 500 chars
        )

        self.beat_history.append(execution)

        if beat.once:
            self._beat_completed.add(beat.id)

    def get_narrative_context(self) -> str:
        """Get context about narrative arc for regular turns (no beat).

        Returns:
            Context text to add to LLM prompt
        """
        if not self.arc.premise:
            return ""

        context_parts = ["=== CONTESTO NARRATIVO ==="]

        if self.arc.premise:
            context_parts.extend(["", "PREMESSA:", self.arc.premise])

        if self.arc.themes:
            context_parts.extend([
                "", "TEMI DA ESPLORARE:",
            ])
            for theme in self.arc.themes:
                context_parts.append(f"  - {theme}")

        if self.arc.hard_limits:
            context_parts.extend([
                "", "VINCOLI ASSOLUTI (non violare mai):",
            ])
            for limit in self.arc.hard_limits:
                context_parts.append(f"  ✗ {limit}")

        # Add completed beats summary
        if self.beat_history:
            context_parts.extend([
                "", "EVENTI GIÀ AVVENUTI:",
            ])
            for exec in self.beat_history[-3:]:  # Last 3 beats
                context_parts.append(f"  ✓ {exec.beat_id}")

        context_parts.append("\n===========================")

        return "\n".join(context_parts)

    def get_upcoming_beats(self, game_state: GameState) -> List[StoryBeat]:
        """Get list of beats that might trigger soon.

        Useful for UI "story progress" indicator.

        Args:
            game_state: Current game state

        Returns:
            List of upcoming beats
        """
        upcoming = []

        for beat in self.arc.beats:
            if beat.id in self._beat_completed:
                continue

            # Check if trigger condition is partially met or close
            # This is a simplified check - could be enhanced
            if "turn >=" in beat.trigger:
                match = re.search(r'turn >= (\d+)', beat.trigger)
                if match:
                    required_turn = int(match.group(1))
                    if game_state.turn_count >= required_turn - 3:
                        upcoming.append(beat)

        return upcoming

    def apply_consequences(self, beat: StoryBeat, game_state: GameState) -> None:
        """Apply beat consequences to game state.

        Args:
            beat: Beat with consequences
            game_state: Game state to modify
        """
        if not beat.consequence:
            return

        # Parse simple consequence format: "affinity += 10, flag:x = true"
        # This is a simplified parser - could be enhanced
        try:
            for part in beat.consequence.split(","):
                part = part.strip()

                # Affinity change
                if "affinity" in part:
                    match = re.search(r'([\w]+)\s*([\+\-])=\s*(\d+)', part)
                    if match:
                        char = match.group(1)
                        op = match.group(2)
                        amount = int(match.group(3))

                        if op == "-":
                            amount = -amount

                        if char in game_state.affinity:
                            game_state.affinity[char] = max(0, min(100,
                                game_state.affinity[char] + amount))

                # Flag set
                elif "flag:" in part:
                    match = re.search(r'flag:(\w+)\s*=\s*(\w+)', part)
                    if match:
                        flag_name = match.group(1)
                        flag_value = match.group(2).lower() == "true"
                        game_state.quest_flags[flag_name] = flag_value

        except Exception as e:
            print(f"[StoryDirector] Error applying consequences: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize director state."""
        return {
            "beat_history": [b.model_dump() for b in self.beat_history],
            "completed_beats": list(self._beat_completed),
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore director state."""
        from luna.core.models import BeatExecution

        self.beat_history = [
            BeatExecution(**b) for b in data.get("beat_history", [])
        ]
        self._beat_completed = set(data.get("completed_beats", []))