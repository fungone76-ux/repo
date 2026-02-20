"""Main Game Engine - Orchestrates all systems.

10-step game loop integrating all subsystems:
1. Personality Analysis
2. StoryDirector Check
3. Quest Engine Update
4. System Prompt Building
5. LLM Generation
6. Response Validation
7. State Updates
8. Media Generation (async, non-blocking)
9. Save State
10. Return Result
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luna.core.config import get_settings, get_user_prefs
from luna.core.database import get_db_manager
from luna.core.models import GameState, LLMResponse, MovementResponse, WorldDefinition
from luna.core.prompt_builder import PromptBuilder
from luna.core.state import StateManager
from luna.core.story_director import StoryDirector
from luna.ai.manager import get_llm_manager
from luna.media.pipeline import MediaPipeline, MediaResult
from luna.systems.quests import QuestActivationResult, QuestEngine, QuestUpdateResult
from luna.systems.personality import BehavioralUpdate, PersonalityEngine
from luna.systems.memory import MemoryManager
from luna.systems.location import LocationManager
from luna.systems.world import get_world_loader


@dataclass
class TurnResult:
    """Result of a game turn."""
    text: str
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None

    # Game state updates
    affinity_changes: Dict[str, int] = field(default_factory=dict)
    new_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)

    # Metadata
    turn_number: int = 0
    provider_used: str = ""
    error: Optional[str] = None

    # Async Media Task
    media_task: Optional[asyncio.Task] = None


class GameEngine:
    """Main game engine orchestrating all systems.

    Coordinates:
    - StoryDirector (narrative beats)
    - QuestEngine (quest management)
    - PersonalityEngine (behavioral analysis)
    - LLMManager (AI generation)
    - MediaPipeline (images, audio, video)
    - StateManager (persistence)
    """

    def __init__(
        self,
        world_id: str,
        companion: str,
        use_llm_personality: bool = True,
    ) -> None:
        """Initialize game engine.

        Args:
            world_id: World identifier
            companion: Starting companion
            use_llm_personality: Enable LLM-based deep analysis
        """
        self.world_id = world_id
        self.companion = companion

        # Settings
        self.settings = get_settings()

        # Load world
        self.world = self._load_world(world_id)
        if not self.world:
            raise ValueError(f"World not found: {world_id}")

        # Core systems
        self.db = get_db_manager()
        self.state_manager = StateManager(self.db)

        # Game systems
        self.quest_engine = QuestEngine(self.world, self.state_manager)
        self.personality_engine = PersonalityEngine(
            self.state_manager,
            use_llm_analysis=use_llm_personality,
            llm_analysis_interval=3,
        )
        self.story_director = StoryDirector(self.world.narrative_arc)
        self.location_manager: Optional[LocationManager] = None

        # Memory manager (initialized later with session_id)
        self.memory_manager: Optional[MemoryManager] = None

        # AI & Media
        self.prompt_builder = PromptBuilder(self.world)
        self.llm_manager = get_llm_manager()
        self.media_pipeline = MediaPipeline()

        # State
        self._initialized = False
        self._session_id: Optional[int] = None

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def initialize(self) -> None:
        """Initialize database and create/load game session."""
        if self._initialized:
            return

        # Create tables
        await self.db.create_tables()

        # Create new game
        async with self.db.session() as db_session:
            companions_list = list(self.world.companions.keys())

            game_state = await self.state_manager.create_new(
                db=db_session,
                world_id=self.world_id,
                companion=self.companion,
                companions_list=companions_list,
            )

            self._session_id = game_state.session_id

        # Initialize NPC links for personality
        self._init_npc_links()

        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager.current,
        )

        # Initialize memory manager with user preferences
        user_prefs = get_user_prefs()
        self.memory_manager = MemoryManager(
            self.db,
            self._session_id,
            history_limit=self.settings.memory_history_limit,
            enable_semantic=user_prefs.enable_semantic_memory,
            storage_path=self.settings.worlds_path.parent / "storage",
        )
        await self.memory_manager.load()

        self._initialized = True
        print(f"[GameEngine] Initialized session {self._session_id}")

    async def load_session(self, session_id: int) -> bool:
        """Load existing game session.

        Args:
            session_id: Session to load

        Returns:
            True if loaded successfully
        """
        async with self.db.session() as db_session:
            game_state = await self.state_manager.load(db_session, session_id)
            if not game_state:
                return False

            self._session_id = session_id

        # Load quest states
        # TODO: Load from DB

        # Load personality states
        # TODO: Load from DB

        # Initialize NPC links
        self._init_npc_links()

        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager.current,
        )

        # Initialize memory manager with user preferences
        user_prefs = get_user_prefs()
        self.memory_manager = MemoryManager(
            self.db,
            self._session_id,
            history_limit=self.settings.memory_history_limit,
            enable_semantic=user_prefs.enable_semantic_memory,
            storage_path=self.settings.worlds_path.parent / "storage",
        )
        await self.memory_manager.load()

        self._initialized = True
        return True

    # ========================================================================
    # Main Game Loop
    # ========================================================================

    async def process_turn(self, user_input: str) -> TurnResult:
        """Process a single game turn (10 steps).

        Args:
            user_input: Player's input text

        Returns:
            Turn result with narrative and media task
        """
        if not self._initialized:
            await self.initialize()

        game_state = self.state_manager.current

        # -------------------------------------------------------------------
        # STEP 0: Check for Movement Intent
        # -------------------------------------------------------------------
        movement_result = self._check_and_handle_movement(user_input)
        if movement_result:
            # Movement was handled, return result
            if movement_result.success:
                self._update_status()
            return TurnResult(
                text=movement_result.transition_text or movement_result.block_description,
                turn_number=game_state.turn_count,
                provider_used="system",
            )

        # -------------------------------------------------------------------
        # STEP 1: Personality Analysis (regex-based, always)
        # -------------------------------------------------------------------
        personality_update = self.personality_engine.analyze_player_action(
            game_state.active_companion,
            user_input,
            game_state.turn_count,
        )

        # -------------------------------------------------------------------
        # STEP 2: StoryDirector Check
        # -------------------------------------------------------------------
        story_beat_result = self.story_director.get_active_instruction(game_state)
        story_context = ""
        if story_beat_result:
            beat, instruction = story_beat_result
            story_context = instruction

        # -------------------------------------------------------------------
        # STEP 3: Quest Engine Update
        # -------------------------------------------------------------------
        quest_context = ""
        new_quests: List[str] = []
        quest_updates: List[QuestUpdateResult] = []

        # Check activations
        activated = self.quest_engine.check_activations(game_state)
        for quest_id in activated:
            async with self.db.session() as db_session:
                result = self.quest_engine.activate_quest(quest_id, game_state)
                if result:
                    new_quests.append(result.title)
                    quest_context += f"\n{result.narrative_context}"

        # Process active quests
        for quest_id in self.quest_engine.get_active_quests():
            result = self.quest_engine.process_turn(quest_id, game_state, user_input)
            if result:
                quest_updates.append(result)
                quest_context += f"\n{result.narrative_context}"

        # -------------------------------------------------------------------
        # STEP 4: Build System Prompt
        # -------------------------------------------------------------------
        # Get memory context if available (with query for semantic search)
        memory_context = ""
        if self.memory_manager:
            memory_context = self.memory_manager.get_memory_context(
                query=user_input,  # Use user input for targeted retrieval
                max_facts=self.settings.memory_max_context_facts,
                min_importance=self.settings.memory_min_importance,
            )

        system_prompt = self.prompt_builder.build_system_prompt(
            game_state=game_state,
            personality_engine=self.personality_engine,
            story_context=story_context,
            quest_context=quest_context,
            memory_context=memory_context,
            location_manager=self.location_manager,
        )

        # -------------------------------------------------------------------
        # STEP 5: LLM Generation
        # -------------------------------------------------------------------
        # Build history from memory
        history = []
        if self.memory_manager:
            recent_msgs = self.memory_manager.get_recent_history(limit=20)
            for msg in recent_msgs:
                history.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        try:
            llm_response = await self.llm_manager.generate(
                system_prompt=system_prompt,
                user_input=user_input,
                history=history,
                json_mode=True,
            )
            provider_used = llm_response.provider or "unknown"
        except Exception as e:
            print(f"[GameEngine] LLM generation failed: {e}")
            return TurnResult(
                text="[Error generating response. Please try again.]",
                error=str(e),
                turn_number=game_state.turn_count,
            )

        # Save user message to memory
        if self.memory_manager:
            await self.memory_manager.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )

            # Save assistant response to memory
            await self.memory_manager.add_message(
                role="assistant",
                content=llm_response.text,
                turn_number=game_state.turn_count,
                visual_en=llm_response.visual_en,
                tags_en=llm_response.tags_en,
            )

            # Save any new fact from response
            if llm_response.updates and llm_response.updates.new_fact:
                await self.memory_manager.add_fact(
                    content=llm_response.updates.new_fact,
                    turn_number=game_state.turn_count,
                    importance=7,  # High importance for explicit facts
                    associated_npc=game_state.active_companion,
                )

        # -------------------------------------------------------------------
        # STEP 6: Validate & Parse Response
        # -------------------------------------------------------------------
        validated_updates = self._validate_updates(llm_response.updates, game_state)

        # Validate story beat execution
        if story_beat_result:
            beat, _ = story_beat_result
            success, quality, missing = self.story_director.validate_beat_execution(
                beat, llm_response.text
            )
            if success:
                self.story_director.mark_beat_completed(beat, llm_response.text, quality)
                self.story_director.apply_consequences(beat, game_state)

        # -------------------------------------------------------------------
        # STEP 7: Apply State Updates
        # -------------------------------------------------------------------
        self._apply_updates(validated_updates, game_state)

        # Advance turn
        self.state_manager.advance_turn()

        # -------------------------------------------------------------------
        # STEP 8: Media Generation (async, non-blocking)
        # -------------------------------------------------------------------
        # Start media generation in background
        outfit = game_state.get_outfit()
        media_task = asyncio.create_task(
            self.media_pipeline.generate_all(
                text=llm_response.text,
                visual_en=llm_response.visual_en,
                tags=llm_response.tags_en,
                companion_name=game_state.active_companion,
                outfit=outfit,
            )
        )

        # NOTA: Rimosso 'await media_task' per non bloccare il loop

        # -------------------------------------------------------------------
        # STEP 9: Save State
        # -------------------------------------------------------------------
        async with self.db.session() as db_session:
            await self.state_manager.save(db_session)

            # Save quest states
            for quest_state in self.quest_engine.get_all_states():
                await self.db.save_quest_state(
                    db_session,
                    self._session_id,
                    quest_state.quest_id,
                    quest_state.status.value,
                    quest_state.current_stage_id,
                )

        # -------------------------------------------------------------------
        # STEP 10: LLM Personality Analysis (periodic)
        # -------------------------------------------------------------------
        if self.personality_engine._use_llm:
            await self.personality_engine.analyze_with_llm(
                game_state.active_companion,
                user_input,
                llm_response.text,
                game_state.turn_count,
            )

        # -------------------------------------------------------------------
        # Return Result
        # -------------------------------------------------------------------
        completed_quests = [u.quest_id for u in quest_updates if u.quest_completed]

        return TurnResult(
            text=llm_response.text,
            affinity_changes=validated_updates.get("affinity_change", {}),
            new_quests=new_quests,
            completed_quests=completed_quests,
            turn_number=game_state.turn_count,
            provider_used=provider_used,
            media_task=media_task,
        )

    # ========================================================================
    # Helpers
    # ========================================================================

    def _load_world(self, world_id: str) -> Optional[WorldDefinition]:
        """Load world definition."""
        loader = get_world_loader()
        return loader.load_world(world_id)

    def _init_npc_links(self) -> None:
        """Initialize NPC relationship links."""
        companions = list(self.world.companions.keys())
        for name in companions:
            companion_def = self.world.companions.get(name)
            if companion_def:
                self.personality_engine.initialize_npc_links(
                    name, companions, companion_def.relations
                )

    def _validate_updates(
        self,
        updates,
        game_state: GameState,
    ) -> Dict[str, Any]:
        """Validate LLM-proposed state updates.

        Args:
            updates: StateUpdate from LLM
            game_state: Current game state

        Returns:
            Validated updates dict
        """
        validated = {}

        # Affinity changes (clamped -5/+5)
        if updates.affinity_change:
            validated["affinity_change"] = {}
            for char, delta in updates.affinity_change.items():
                if char in game_state.affinity:
                    validated["affinity_change"][char] = max(-5, min(5, delta))

        # Outfit (must exist in wardrobe)
        if updates.current_outfit:
            companion = self.world.companions.get(game_state.active_companion)
            if companion and updates.current_outfit in companion.wardrobe:
                validated["current_outfit"] = updates.current_outfit

        # Detailed outfit update
        if updates.outfit_update:
            validated["outfit_update"] = updates.outfit_update

        # Location (must exist)
        if updates.location:
            if updates.location in self.world.locations:
                validated["location"] = updates.location

        # Time
        if updates.time_of_day:
            validated["time_of_day"] = updates.time_of_day

        # Flags
        if updates.set_flags:
            validated["set_flags"] = updates.set_flags

        # NPC updates
        if updates.npc_emotion:
            validated["npc_emotion"] = updates.npc_emotion

        return validated

    def _apply_updates(
        self,
        updates: Dict[str, Any],
        game_state: GameState,
    ) -> None:
        """Apply validated updates to game state.

        Args:
            updates: Validated updates
            game_state: Game state to modify
        """
        # Affinity
        for char, delta in updates.get("affinity_change", {}).items():
            self.state_manager.change_affinity(char, delta)

        # Outfit
        if "current_outfit" in updates:
            self.state_manager.set_outfit_style(updates["current_outfit"])

        # Detailed outfit update
        if "outfit_update" in updates:
            self._apply_outfit_update(updates["outfit_update"], game_state)

        # Location
        if "location" in updates:
            self.state_manager.set_location(updates["location"])

        # Time
        if "time_of_day" in updates:
            from luna.core.models import TimeOfDay
            self.state_manager.set_time(TimeOfDay(updates["time_of_day"]))

        # Flags
        for key, value in updates.get("set_flags", {}).items():
            self.state_manager.set_flag(key, value)

        # NPC emotion
        if "npc_emotion" in updates:
            self.state_manager.update_npc_emotion(
                game_state.active_companion,
                updates["npc_emotion"]
            )

    def _apply_outfit_update(
        self,
        update: Any,  # OutfitUpdate
        game_state: GameState,
    ) -> None:
        """Apply outfit update from LLM.

        Args:
            update: OutfitUpdate from LLM
            game_state: Current game state
        """
        from luna.core.models import OutfitUpdate

        if not isinstance(update, OutfitUpdate):
            return

        current_outfit = game_state.get_outfit()

        # If style changed, update it (marks for regeneration)
        if update.style:
            self.state_manager.set_outfit_style(update.style)

        # If full description provided, update it
        if update.description:
            current_outfit.description = update.description

        # Apply component modifications
        for component, value in update.modify_components.items():
            self.state_manager.modify_outfit_component(component, value)

        # Update special flag if provided
        if update.is_special is not None:
            current_outfit.is_special = update.is_special

    def _check_and_handle_movement(self, user_input: str) -> Optional[MovementResponse]:
        """Check if user input is a movement command and handle it.

        Args:
            user_input: Player's input

        Returns:
            MovementResponse if handled, None otherwise
        """
        if not self.location_manager:
            return None

        # Movement keywords (Italian)
        movement_patterns = [
            "vado ", "vai ", "andiamo ", "muoviti ", "spostati ",
            "entra ", "entriamo ", "uscire ", "uscite ",
            "raggiungi ", "raggiungiamo ",
            "torniamo ", "torna ",
        ]

        input_lower = user_input.lower()

        # Check if it's a movement intent
        is_movement = any(pattern in input_lower for pattern in movement_patterns)

        if not is_movement:
            return None

        # Try to resolve location from input
        # Remove movement keywords and try to match
        target_name = user_input.lower()
        for pattern in movement_patterns:
            target_name = target_name.replace(pattern.strip(), "")

        # Clean up
        target_name = target_name.strip().strip(".")

        # Try to resolve to location ID
        target_id = self.location_manager.resolve_location_alias(target_name)

        if not target_id:
            # Could be partial match - try visible locations
            visible = self.location_manager.get_visible_locations()
            for loc_id in visible:
                loc = self.location_manager.get_location(loc_id)
                if loc and (loc.name.lower() in target_name or
                           any(a.lower() in target_name for a in loc.aliases)):
                    target_id = loc_id
                    break

        if not target_id:
            # Let LLM handle unknown location
            return None

        # Execute movement
        return self.location_manager.move_to(target_id)

    # ========================================================================
    # Public API
    # ========================================================================

    def get_game_state(self) -> GameState:
        """Get current game state."""
        return self.state_manager.current

    def get_active_quests(self) -> List[str]:
        """Get list of active quest titles."""
        return [
            self.world.quests[qid].title
            for qid in self.quest_engine.get_active_quests()
            if qid in self.world.quests
        ]

    def toggle_audio(self) -> bool:
        """Toggle audio mute. Returns new state."""
        return self.media_pipeline.toggle_audio()

    async def generate_intro(self) -> TurnResult:
        """Generate opening introduction with character image.

        Creates the initial scene when the game starts:
        - Narrative introduction text
        - Character portrait image

        Returns:
            Turn result with intro text and async media task
        """
        if not self._initialized:
            await self.initialize()

        game_state = self.state_manager.current
        companion = self.world.companions.get(game_state.active_companion)

        # Build intro-specific system prompt
        system_prompt = self._build_intro_prompt(game_state, companion)

        # Generate intro via LLM
        try:
            llm_response = await self.llm_manager.generate(
                system_prompt=system_prompt,
                user_input="Generate the opening scene introduction.",
                history=[],
                json_mode=True,
            )

            # Save to memory
            if self.memory_manager:
                await self.memory_manager.add_message(
                    role="assistant",
                    content=llm_response.text,
                    turn_number=0,
                    visual_en=llm_response.visual_en,
                    tags_en=llm_response.tags_en,
                )

        except Exception as e:
            print(f"[GameEngine] Intro generation failed: {e}")
            # Fallback intro
            llm_response = LLMResponse(
                text=f"Sei arrivato in {game_state.current_location}. {game_state.active_companion} ti aspetta.",
                visual_en=f"{game_state.active_companion} standing, welcoming expression, {game_state.current_location} background",
                tags_en=["1girl", "solo", "standing", "smile"],
            )

        # Generate image (MODIFIED FOR ASYNC)
        outfit = game_state.get_outfit()
        media_task = asyncio.create_task(
            self.media_pipeline.generate_all(
                text=llm_response.text,
                visual_en=llm_response.visual_en,
                tags=llm_response.tags_en,
                companion_name=game_state.active_companion,
                outfit=outfit,
            )
        )

        return TurnResult(
            text=llm_response.text,
            turn_number=0,
            provider_used=getattr(llm_response, 'provider', 'unknown'),
            media_task=media_task,
        )

    def _build_intro_prompt(
        self,
        game_state: GameState,
        companion: Optional[Any],
    ) -> str:
        """Build system prompt for intro generation.

        Args:
            game_state: Current game state
            companion: Active companion definition

        Returns:
            System prompt for intro
        """
        sections = [
            "=== LUNA RPG - OPENING SCENE ===",
            "",
            f"Genre: {self.world.genre}",
            f"World: {self.world.name}",
            "",
            "You are writing the OPENING SCENE of a visual novel.",
            "This is the first moment the player sees - make it captivating!",
            "",
            "=== SETTING ===",
            self.world.lore or self.world.description,
            "",
            "=== MAIN CHARACTER ===",
        ]

        if companion:
            # Use physical_description if available, fallback to base_prompt
            appearance = companion.physical_description or companion.base_prompt
            sections.extend([
                f"Name: {companion.name}",
                f"Role: {companion.role}",
                f"Age: {companion.age}",
                f"Personality: {companion.base_personality}",
                f"Appearance: {appearance}",
            ])
            if companion.wardrobe:
                default_outfit = list(companion.wardrobe.keys())[0]
                sections.append(f"Current Outfit: {default_outfit}")

        sections.extend([
            "",
            f"=== STARTING LOCATION ===",
            f"Location: {game_state.current_location}",
            f"Time: {game_state.time_of_day.value}",
            "",
            "=== YOUR TASK ===",
            "Write an engaging opening scene where the player first encounters the main character.",
            "Set the mood, describe the atmosphere, introduce the character naturally.",
            "",
            "=== OUTPUT FORMAT ===",
            "Respond with valid JSON:",
            "{",
            '  "text": "Opening narrative in Italian (2-3 paragraphs, immersive, set the scene)",',
            '  "visual_en": "Detailed visual description for character portrait (English, focus on character)",',
            '  "tags_en": ["score_9", "score_8_up", "1girl", "solo", "portrait", ...],',
            '  "composition": "medium_shot"',
            "}",
            "",
            "=== RULES ===",
            "1. Introduce the character and setting naturally",
            "2. Use atmospheric, sensory details",
            "3. visual_en should focus on the character's appearance and expression",
            "4. This is the FIRST impression - make it memorable!",
            "",
            "=== END INSTRUCTIONS ===",
        ])

        return "\n".join(sections)