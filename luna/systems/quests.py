"""Quest Engine - State machine for quest management.

Integrates with StoryDirector for narrative-driven quest activation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from luna.core.models import (
    GameState,
    QuestAction,
    QuestCondition,
    QuestDefinition,
    QuestInstance,
    QuestStatus,
    QuestStage,
    WorldDefinition,
)
from luna.core.state import StateManager


class ConditionType(str, Enum):
    """Types of quest conditions."""
    AFFINITY = "affinity"
    LOCATION = "location"
    TIME = "time"
    FLAG = "flag"
    TURN_COUNT = "turn_count"
    INVENTORY = "inventory"
    ACTION = "action"
    COMPANION = "companion"
    QUEST_STATUS = "quest_status"


class ActionType(str, Enum):
    """Types of quest actions."""
    SET_FLAG = "set_flag"
    ADD_FLAG = "add_flag"
    CHANGE_AFFINITY = "change_affinity"
    SET_LOCATION = "set_location"
    SET_OUTFIT = "set_outfit"
    SET_EMOTIONAL_STATE = "set_emotional_state"
    START_QUEST = "start_quest"
    COMPLETE_QUEST = "complete_quest"
    FAIL_QUEST = "fail_quest"


@dataclass
class QuestActivationResult:
    """Result of quest activation."""
    quest_id: str
    title: str
    actions_executed: List[QuestAction] = field(default_factory=list)
    narrative_context: str = ""
    hidden: bool = False


@dataclass
class QuestUpdateResult:
    """Result of processing a quest turn."""
    quest_id: str
    stage_changed: bool = False
    old_stage: Optional[str] = None
    new_stage: Optional[str] = None
    actions_executed: List[QuestAction] = field(default_factory=list)
    quest_completed: bool = False
    quest_failed: bool = False
    narrative_context: str = ""


@dataclass
class ConditionContext:
    """Context for condition evaluation."""
    game_state: GameState
    user_input: str = ""
    turn_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for evaluation."""
        return {
            "affinity": self.game_state.affinity,
            "location": self.game_state.current_location,
            "time": self.game_state.time_of_day.value,
            "turn": self.turn_count,
            "turn_count": self.turn_count,
            "companion": self.game_state.active_companion,
            "flags": self.game_state.quest_flags,  # <-- FIX: Aggiornato in quest_flags
            "inventory": self.game_state.player.inventory,
            "user_input": self.user_input,
        }


class ConditionEvaluator:
    """Evaluates quest conditions against game state."""

    @staticmethod
    def evaluate(condition: QuestCondition, context: ConditionContext) -> bool:
        """Evaluate a single condition.

        Args:
            condition: Condition to evaluate
            context: Evaluation context

        Returns:
            True if condition is satisfied
        """
        data = context.to_dict()

        # Get value from context
        if condition.type == ConditionType.AFFINITY:
            target = condition.target or context.game_state.active_companion
            actual_value = data["affinity"].get(target, 0)

        elif condition.type == ConditionType.LOCATION:
            actual_value = data["location"]

        elif condition.type == ConditionType.TIME:
            actual_value = data["time"]

        elif condition.type == ConditionType.FLAG:
            flag_name = condition.target or ""
            actual_value = data["flags"].get(flag_name, False)
            if isinstance(actual_value, bool):
                compare_value = condition.value if isinstance(condition.value, bool) else str(condition.value).lower() == "true"
                return actual_value == compare_value
            return str(actual_value) == str(condition.value)

        elif condition.type == ConditionType.TURN_COUNT:
            actual_value = data["turn_count"]

        elif condition.type == ConditionType.INVENTORY:
            actual_value = condition.target in data["inventory"]
            return actual_value == condition.value

        elif condition.type == ConditionType.ACTION:
            # Pattern matching on user input
            if condition.pattern:
                import re
                return bool(re.search(condition.pattern, data["user_input"], re.IGNORECASE))
            return False

        elif condition.type == ConditionType.COMPANION:
            actual_value = data["companion"]

        elif condition.type == ConditionType.QUEST_STATUS:
            # Handled by quest engine directly
            return True
        else:
            return False

        # Compare values
        return ConditionEvaluator._compare(actual_value, condition.operator, condition.value)

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        """Compare two values with operator.

        Args:
            actual: Actual value
            operator: Comparison operator
            expected: Expected value

        Returns:
            Comparison result
        """
        try:
            # Numeric comparison
            if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                if operator == "eq":
                    return actual == expected
                elif operator == "gt":
                    return actual > expected
                elif operator == "lt":
                    return actual < expected
                elif operator == "gte":
                    return actual >= expected
                elif operator == "lte":
                    return actual <= expected

            # String comparison
            actual_str = str(actual).lower()
            expected_str = str(expected).lower()

            if operator == "eq":
                return actual_str == expected_str
            elif operator == "contains":
                return expected_str in actual_str
            elif operator == "gt":
                return actual_str > expected_str
            elif operator == "lt":
                return actual_str < expected_str

        except (TypeError, ValueError):
            pass

        return False


class ActionExecutor:
    """Executes quest actions on game state."""

    def __init__(self, state_manager: StateManager):
        """Initialize executor.

        Args:
            state_manager: For modifying game state
        """
        self.state_manager = state_manager

    def execute(self, action: QuestAction, game_state: GameState) -> bool:
        """Execute a single action.

        Args:
            action: Action to execute
            game_state: Current game state

        Returns:
            True if executed successfully
        """
        action_type = action.action

        try:
            if action_type == ActionType.SET_FLAG:
                self.state_manager.set_flag(action.key, action.value)

            elif action_type == ActionType.ADD_FLAG:
                # Add to a list flag
                current = game_state.quest_flags.get(action.key, [])  # <-- FIX: Aggiornato in quest_flags
                if isinstance(current, list):
                    current.append(action.value)
                    self.state_manager.set_flag(action.key, current)

            elif action_type == ActionType.CHANGE_AFFINITY:
                char = action.character or game_state.active_companion
                if char:
                    self.state_manager.change_affinity(char, action.value)

            elif action_type == ActionType.SET_LOCATION:
                if action.target:
                    self.state_manager.set_location(action.target)

            elif action_type == ActionType.SET_OUTFIT:
                if action.outfit:
                    self.state_manager.set_outfit(action.outfit)

            elif action_type == ActionType.SET_EMOTIONAL_STATE:
                char = action.character or game_state.active_companion
                if char and action.value:
                    self.state_manager.update_npc_emotion(char, action.value)

            elif action_type == ActionType.START_QUEST:
                if action.quest_id:
                    self.state_manager.start_quest(action.quest_id)

            elif action_type == ActionType.COMPLETE_QUEST:
                if action.quest_id:
                    self.state_manager.complete_quest(action.quest_id)

            elif action_type == ActionType.FAIL_QUEST:
                if action.quest_id:
                    self.state_manager.fail_quest(action.quest_id)
            else:
                return False

            return True

        except Exception as e:
            print(f"[QuestEngine] Action execution failed: {e}")
            return False


class QuestEngine:
    """Main quest engine - manages quest lifecycle.

    Integrates with StoryDirector for narrative-driven activation.
    """

    def __init__(
        self,
        world: WorldDefinition,
        state_manager: StateManager,
    ) -> None:
        """Initialize quest engine.

        Args:
            world: World definition with quest data
            state_manager: For state modifications
        """
        self.world = world
        self.definitions = world.quests
        self.state_manager = state_manager

        self.evaluator = ConditionEvaluator()
        self.executor = ActionExecutor(state_manager)

        # Runtime state
        self.active_states: Dict[str, QuestInstance] = {}
        self._story_director = None  # Set via setter

        print(f"[QuestEngine] Loaded {len(self.definitions)} quest definitions")

    def set_story_director(self, story_director) -> None:
        """Set StoryDirector for bidirectional integration.

        Args:
            story_director: StoryDirector instance
        """
        self._story_director = story_director

    def load_states(self, states: List[QuestInstance]) -> None:
        """Load saved quest states from database.

        Args:
            states: List of saved quest instances
        """
        for state in states:
            self.active_states[state.quest_id] = state

    def get_all_states(self) -> List[QuestInstance]:
        """Get all quest states for saving.

        Returns:
            List of quest instances
        """
        return list(self.active_states.values())

    def check_activations(self, game_state: GameState) -> List[str]:
        """Check which quests should activate.

        Args:
            game_state: Current game state

        Returns:
            List of quest IDs to activate
        """
        activated = []
        context = ConditionContext(
            game_state=game_state,
            turn_count=game_state.turn_count,
        )

        for quest_id, quest in self.definitions.items():
            # Skip if already active or completed
            if quest_id in self.active_states:
                state = self.active_states[quest_id]
                if state.status in (QuestStatus.ACTIVE, QuestStatus.COMPLETED):
                    continue

            # Check activation type
            activation = quest.activation_conditions

            if quest.activation_type == "auto":
                if self._evaluate_conditions(activation, context):
                    activated.append(quest_id)

            elif quest.activation_type == "trigger":
                # Check trigger event in flags
                if quest.trigger_event:
                    if game_state.quest_flags.get(f"trigger_{quest.trigger_event}"):  # <-- FIX: Aggiornato in quest_flags
                        activated.append(quest_id)

        return activated

    def activate_quest(
        self,
        quest_id: str,
        game_state: GameState,
    ) -> Optional[QuestActivationResult]:
        """Activate a quest.

        Args:
            quest_id: Quest to activate
            game_state: Current game state

        Returns:
            Activation result or None if failed
        """
        if quest_id not in self.definitions:
            return None

        quest = self.definitions[quest_id]

        # Check required quests
        for req_id in quest.required_quests:
            if req_id not in self.active_states:
                return None
            req_state = self.active_states[req_id]
            if req_state.status != QuestStatus.COMPLETED:
                return None

        # Determine start stage
        start_stage_id = quest.start_stage
        if start_stage_id not in quest.stages:
            start_stage_id = list(quest.stages.keys())[0] if quest.stages else ""

        # Create instance
        instance = QuestInstance(
            quest_id=quest_id,
            status=QuestStatus.ACTIVE,
            current_stage_id=start_stage_id,
            started_at=game_state.turn_count,
        )
        self.active_states[quest_id] = instance

        # Execute on_enter actions
        start_stage = quest.stages.get(start_stage_id)
        actions_executed = []
        if start_stage:
            for action in start_stage.on_enter:
                if self.executor.execute(action, game_state):
                    actions_executed.append(action)

        print(f"[QuestEngine] Activated '{quest.title}' (stage: {start_stage_id})")

        return QuestActivationResult(
            quest_id=quest_id,
            title=quest.title,
            actions_executed=actions_executed,
            narrative_context=start_stage.narrative_prompt if start_stage else "",
            hidden=quest.hidden,
        )

    def process_turn(
        self,
        quest_id: str,
        game_state: GameState,
        user_input: str,
    ) -> Optional[QuestUpdateResult]:
        """Process a turn for an active quest.

        Args:
            quest_id: Quest to process
            game_state: Current game state
            user_input: User's input text

        Returns:
            Update result or None if no changes
        """
        if quest_id not in self.active_states:
            return None

        instance = self.active_states[quest_id]
        if instance.status != QuestStatus.ACTIVE:
            return None

        quest = self.definitions.get(quest_id)
        if not quest:
            return None

        current_stage = quest.stages.get(instance.current_stage_id)
        if not current_stage:
            return None

        # Build context with user input
        context = ConditionContext(
            game_state=game_state,
            user_input=user_input,
            turn_count=game_state.turn_count,
        )

        # Evaluate exit conditions
        triggered_idx = None
        for i, condition in enumerate(current_stage.exit_conditions):
            if self.evaluator.evaluate(condition, context):
                triggered_idx = i
                break

        # Find transition
        target_stage_id = None
        for trans in current_stage.transitions:
            cond_name = trans.condition

            # Map index to condition name
            if triggered_idx is not None and cond_name == f"condition_{triggered_idx}":
                target_stage_id = trans.target_stage
                break
            elif cond_name == "default" and triggered_idx is None:
                target_stage_id = trans.target_stage
                break

        if not target_stage_id:
            return None

        # Execute stage transition
        return self._transition_stage(
            quest_id, quest, instance,
            current_stage, target_stage_id,
            game_state,
        )

    def _transition_stage(
        self,
        quest_id: str,
        quest: QuestDefinition,
        instance: QuestInstance,
        from_stage: QuestStage,
        to_stage_id: str,
        game_state: GameState,
    ) -> QuestUpdateResult:
        """Execute stage transition.

        Args:
            quest_id: Quest ID
            quest: Quest definition
            instance: Quest instance
            from_stage: Current stage
            to_stage_id: Target stage
            game_state: Current game state

        Returns:
            Transition result
        """
        old_stage_id = instance.current_stage_id
        actions_executed = []
        completed = False
        failed = False
        narrative_context = ""

        # Check for completion/failure
        if to_stage_id == "_complete":
            instance.status = QuestStatus.COMPLETED
            instance.completed_at = game_state.turn_count
            completed = True

            # Execute rewards
            for action in self._rewards_to_actions(quest.rewards):
                if self.executor.execute(action, game_state):
                    actions_executed.append(action)

            # Check for story beat trigger
            if self._story_director:
                self._trigger_story_beat(f"quest_{quest_id}_completed")

        elif to_stage_id == "_fail":
            instance.status = QuestStatus.FAILED
            failed = True

        else:
            # Normal stage transition
            to_stage = quest.stages.get(to_stage_id)
            if not to_stage:
                return QuestUpdateResult(quest_id=quest_id)

            instance.current_stage_id = to_stage_id

            # Execute on_enter actions
            for action in to_stage.on_enter:
                if self.executor.execute(action, game_state):
                    actions_executed.append(action)

            narrative_context = to_stage.narrative_prompt

            # Check for story beat trigger
            if self._story_director:
                self._trigger_story_beat(f"quest_{quest_id}_stage_{to_stage_id}")

        print(f"[QuestEngine] '{quest.title}': {old_stage_id} → {to_stage_id}")

        return QuestUpdateResult(
            quest_id=quest_id,
            stage_changed=True,
            old_stage=old_stage_id,
            new_stage=to_stage_id,
            actions_executed=actions_executed,
            quest_completed=completed,
            quest_failed=failed,
            narrative_context=narrative_context,
        )

    def _evaluate_conditions(
        self,
        conditions: List[QuestCondition],
        context: ConditionContext,
    ) -> bool:
        """Evaluate multiple conditions (ALL must be true).

        Args:
            conditions: List of conditions
            context: Evaluation context

        Returns:
            True if all conditions satisfied
        """
        if not conditions:
            return True
        return all(self.evaluator.evaluate(c, context) for c in conditions)

    def _rewards_to_actions(self, rewards) -> List[QuestAction]:
        """Convert rewards to actions.

        Args:
            rewards: Quest rewards

        Returns:
            List of actions
        """
        actions = []

        # Affinity rewards
        for char, value in rewards.affinity.items():
            actions.append(QuestAction(
                action=ActionType.CHANGE_AFFINITY,
                character=char,
                value=value,
            ))

        # Flag rewards
        for key, value in rewards.flags.items():
            actions.append(QuestAction(
                action=ActionType.SET_FLAG,
                key=key,
                value=value,
            ))

        # Unlock quest rewards
        for quest_id in rewards.unlock_quests:
            actions.append(QuestAction(
                action=ActionType.START_QUEST,
                quest_id=quest_id,
            ))

        return actions

    def _trigger_story_beat(self, event_id: str) -> None:
        """Notify StoryDirector of quest event.

        Args:
            event_id: Event identifier
        """
        if self._story_director:
            # Set flag that StoryDirector can detect
            self.state_manager.set_flag(f"event_{event_id}", True)

    # ========================================================================
    # Public API
    # ========================================================================

    def get_active_quests(self) -> List[str]:
        """Get list of active quest IDs.

        Returns:
            List of quest IDs
        """
        return [
            qid for qid, state in self.active_states.items()
            if state.status == QuestStatus.ACTIVE
        ]

    def get_quest_status(self, quest_id: str) -> Optional[QuestStatus]:
        """Get status of a quest.

        Args:
            quest_id: Quest ID

        Returns:
            Status or None
        """
        if quest_id in self.active_states:
            return self.active_states[quest_id].status
        return None

    def get_quest_context(self, quest_id: str) -> str:
        """Get narrative context for active quest.

        Args:
            quest_id: Quest ID

        Returns:
            Narrative prompt for current stage
        """
        if quest_id not in self.active_states:
            return ""

        instance = self.active_states[quest_id]
        quest = self.definitions.get(quest_id)

        if not quest:
            return ""

        stage = quest.stages.get(instance.current_stage_id)
        if stage:
            return stage.narrative_prompt
        return ""

    def get_all_active_context(self) -> str:
        """Get narrative context for all active quests.

        Returns:
            Combined narrative context
        """
        contexts = []
        for quest_id in self.get_active_quests():
            quest = self.definitions.get(quest_id)
            if quest and not quest.hidden:
                ctx = self.get_quest_context(quest_id)
                if ctx:
                    contexts.append(f"Quest '{quest.title}': {ctx}")

        return "\n\n".join(contexts) if contexts else ""