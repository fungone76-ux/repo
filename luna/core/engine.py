from __future__ import annotations

"""Main Game Engine - Orchestrates all systems.

10-step game loop integrating all subsystems:
1. Personality Analysis
2. StoryDirector Check
3. Quest Engine Update
4. System Prompt Building
5. LLM Generation
6. Response Validation
7. State Updates
8. Media Generation (async)
9. Save State
10. Return Result
"""

import asyncio
import logging
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from luna.core.config import get_settings, get_user_prefs
from luna.core.database import get_db_manager
from luna.core.models import GameState, LLMResponse, QuestInstance, QuestStatus, TimeOfDay, TurnResult, WorldDefinition
from luna.core.prompt_builder import PromptBuilder
from luna.core.state import StateManager
from luna.core.story_director import StoryDirector
from luna.ai.manager import get_llm_manager
from luna.systems.quests import QuestActivationResult, QuestEngine, QuestUpdateResult

# MediaPipeline imported lazily to avoid circular imports
from luna.media.pipeline import MediaResult
from luna.systems.personality import BehavioralUpdate, PersonalityEngine
from luna.systems.memory import MemoryManager
from luna.systems.location import LocationManager
from luna.systems.movement import MovementHandler, MovementResult
from luna.systems.intro import IntroGenerator
from luna.systems.pose_extractor import get_pose_extractor, PoseExtractor
from luna.systems.global_events import GlobalEventManager, GlobalEventInstance
from luna.systems.multi_npc import MultiNPCManager
from luna.systems.affinity_calculator import get_calculator
from luna.systems.state_memory import StateMemoryManager
from luna.systems.npc_detector import NPCDetector
from luna.systems.input_preprocessor import InputPreprocessor
from luna.systems.response_processor import ResponseProcessor
from luna.systems.state_updater import StateUpdater
from luna.systems.media_coordinator import MediaCoordinator
from luna.systems.turn_orchestrator import TurnOrchestrator
from luna.core.debug_tracer import tracer, CheckStatus


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
            world=self.world,
            use_llm_analysis=use_llm_personality,
            llm_analysis_interval=5,  # Fire-and-forget: 5 turns interval
        )
        
        # Outfit modifier (deterministic clothing changes)
        from luna.systems.outfit_modifier import create_outfit_modifier
        self.outfit_modifier = create_outfit_modifier()
        
        # Pose extractor (deterministic pose detection)
        self.pose_extractor = get_pose_extractor()
        self.story_director = StoryDirector(self.world.narrative_arc)
        self.location_manager: Optional[LocationManager] = None
        self.gameplay_manager: Optional[GameplayManager] = None
        
        # Store last user input for affinity calculation
        self._last_user_input: str = ""
        
        # Memory manager (initialized later with session_id)
        self.memory_manager: Optional[MemoryManager] = None
        
        # AI & Media
        self.prompt_builder = PromptBuilder(self.world)
        self.llm_manager = get_llm_manager()
        
        # Activity & Initiative Systems (NEW)
        from luna.systems.activity_system import ActivitySystem
        from luna.systems.initiative_system import InitiativeSystem
        self.activity_system = ActivitySystem()
        self.initiative_system = InitiativeSystem()
        
        # V4.3: NPC Detector (refactored from inline code)
        self.npc_detector = NPCDetector(self.world)
        # Lazy import to avoid circular imports
        from luna.media.pipeline import MediaPipeline
        
        # V4.2: Check for --no-media flag
        import os
        self._no_media = os.environ.get("LUNA_DEBUG_NO_MEDIA") == "1"
        if self._no_media:
            print("[GameEngine] Media generation DISABLED (--no-media)")
            self.media_pipeline = None  # Will skip media generation
        else:
            self.media_pipeline = MediaPipeline()
        
        # V4.3: New coordinator components (refactored from process_turn)
        self.input_preprocessor = InputPreprocessor(self.world, self.state_manager)
        self.response_processor = ResponseProcessor(max_retries=3)
        # StateUpdater needs affinity calculator
        from luna.systems.affinity_calculator import get_calculator
        self.state_updater = StateUpdater(
            state_manager=self.state_manager,
            affinity_calculator=get_calculator(),
            outfit_modifier=self.outfit_modifier,
            quest_engine=self.quest_engine,
            personality_engine=self.personality_engine,
        )
        self.media_coordinator = MediaCoordinator(
            media_pipeline=self.media_pipeline,
            enabled=not self._no_media,
 )
        
        # Multi-NPC System (CONSERVATIVE - enabled but with strict rules)
        self.multi_npc_manager = MultiNPCManager(
            world=self.world,
            personality_engine=None,  # Will be set after personality_engine init
            enabled=True,  # ENABLED - now with conservative triggering rules
        )
        
        # State
        self._initialized = False
        self._session_id: Optional[int] = None
        
        # V4.1: Time Manager (auto-advance, rest commands, deadlines)
        self.time_manager: Optional['TimeManager'] = None
        self._pending_time_message: Optional[str] = None
        self._pending_phase_message: Optional[str] = None  # V4.2
        
        # V4.1: Schedule Manager (NPC routines)
        self.schedule_manager: Optional['ScheduleManager'] = None
        
        # V4.2: Phase Manager (8 turns per phase, freeze system)
        self.phase_manager: Optional['PhaseManager'] = None
        
        # V3.2: NPC cache for consistent secondary characters
        # Maps template_id -> companion_name to ensure same NPC always appears
        self._npc_template_cache: Dict[str, str] = {}
        
        # V4.5: UI callback for time changes
        self._ui_time_change_callback: Optional[Callable[[Any, str], None]] = None
        
        # V4.3: Expose tracer for TurnOrchestrator and other components
        self.tracer = tracer
    
    # ========================================================================
    # UI Callback Registration
    # ========================================================================
    
    def set_ui_time_change_callback(self, callback: Callable[[Any, str], None]) -> None:
        """Register UI callback for time change notifications.
        
        Args:
            callback: Function(new_time, message) to call when time changes
        """
        self._ui_time_change_callback = callback
        print(f"[GameEngine] UI time change callback registered")
    
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
                player_character=self.world.player_character,
            )
            
            self._session_id = game_state.session_id
            
            # V4.1: Initialize Time Manager
            from luna.systems.time_manager import TimeManager, TimeConfig
            self.time_manager = TimeManager(
                game_state=game_state,
                config=TimeConfig(
                    turns_per_period=5,  # Auto-advance every 5 turns
                    enable_auto_advance=True,
                    enable_rest_commands=True,
                    enable_deadlines=True,
                ),
                on_time_change=self._on_time_change,
            )
            
            # V4.1: Initialize Schedule Manager (NPC routines)
            from luna.systems.schedule_manager import ScheduleManager
            self.schedule_manager = ScheduleManager(game_state=game_state, world=self.world)
            
            # V4.2: Initialize Phase Manager (8 turns per phase)
            from luna.systems.phase_manager import PhaseManager, PhaseConfig
            self.phase_manager = PhaseManager(
                game_state=game_state,
                schedule_manager=self.schedule_manager,
                config=PhaseConfig(turns_per_phase=8),  # 8 turni per fase
                on_phase_change=self._on_phase_change,
            )
            
            # V4.5: Load phase manager state if exists
            phase_state = game_state.flags.get("_phase_manager_state")
            if phase_state:
                self.phase_manager.from_dict(phase_state)
                print(f"[GameEngine] Loaded phase manager state: {phase_state}")
            
            # Set starting location if not already set
            if game_state.current_location == "Unknown" and self.world.locations:
                # Use first location as starting location
                first_location_id = next(iter(self.world.locations.keys()))
                game_state.current_location = first_location_id
                print(f"[GameEngine] Set starting location: {first_location_id}")
            
            # V3.1 FIX: Initialize outfit for ALL companions from their wardrobe
            from luna.core.models import OutfitState
            
            for companion_name, companion_def in self.world.companions.items():
                # Skip temporary NPCs
                if getattr(companion_def, 'is_temporary', False):
                    continue
                
                if companion_def and companion_def.wardrobe:
                    # Use default_outfit if specified, otherwise first style
                    default_style = getattr(companion_def, 'default_outfit', None)
                    if not default_style or default_style not in companion_def.wardrobe:
                        default_style = next(iter(companion_def.wardrobe.keys()))
                    
                    wardrobe_def = companion_def.wardrobe[default_style]
                    
                    # Handle both string (legacy) and WardrobeDefinition
                    if isinstance(wardrobe_def, str):
                        outfit_desc = wardrobe_def
                    else:
                        outfit_desc = getattr(wardrobe_def, 'sd_prompt', '') or \
                                      getattr(wardrobe_def, 'description', default_style)
                    
                    # Parse description to extract components
                    components = {}
                    desc_lower = outfit_desc.lower()
                    
                    # Common clothing keywords
                    if 'shirt' in desc_lower or 'blouse' in desc_lower or 'top' in desc_lower:
                        components['top'] = 'shirt'
                    if 'skirt' in desc_lower:
                        components['bottom'] = 'skirt'
                    if 'pants' in desc_lower or 'jeans' in desc_lower or 'trousers' in desc_lower:
                        components['bottom'] = 'pants'
                    if 'dress' in desc_lower:
                        components['dress'] = 'dress'
                    if 'shoes' in desc_lower or 'heels' in desc_lower:
                        components['shoes'] = 'shoes'
                    if 'jacket' in desc_lower or 'blazer' in desc_lower:
                        components['outerwear'] = 'jacket'
                    if 'apron' in desc_lower:
                        components['special'] = 'apron'
                    if 'towel' in desc_lower:
                        components['special'] = 'towel'
                    
                    outfit = OutfitState(
                        style=default_style,
                        description=outfit_desc,
                        components=components,
                    )
                    game_state.set_outfit(outfit, companion_name)
                    print(f"[GameEngine] Set outfit for {companion_name}: {default_style}")
        
        # Initialize NPC links for personality
        self._init_npc_links()
        
        # Link personality engine to multi-npc manager
        self.multi_npc_manager.personality_engine = self.personality_engine
        
        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager,
        )
        
        # Initialize movement handler (V4 refactor)
        self.movement_handler = MovementHandler(
            self.world,
            self.location_manager,
            self.state_manager.current,
        )
        
        # Initialize gameplay manager (lazy import to avoid circular imports)
        from luna.systems.gameplay_manager import GameplayManager
        self.gameplay_manager = GameplayManager(self.world)
        
        # Initialize intro generator (V4 refactor)
        self.intro_generator = IntroGenerator(
            self.world,
            self.llm_manager,
            self.media_pipeline,
            self.memory_manager,
            self.gameplay_manager,
        )
        
        # Initialize global event manager
        self.event_manager = GlobalEventManager(self.world)
        
        # Validate event definitions (warn about missing fields)
        from luna.systems.event_validator import validate_world_events
        event_validation = validate_world_events(self.world, print_report_output=False)
        if not event_validation.is_valid:
            print("[GameEngine] Event validation warnings:")
            for issue in event_validation.get_errors():
                print(f"  [ERROR] [{issue.event_id}] {issue.field}: {issue.message}")
            for issue in event_validation.get_warnings():
                print(f"  [WARN] [{issue.event_id}] {issue.field}: {issue.message}")
        else:
            event_count = len(getattr(self.world, 'global_events', {}))
            print(f"[GameEngine] {event_count} event(s) validated successfully")
        
        # Initialize memory manager with user preferences
        user_prefs = get_user_prefs()
        self.memory_manager = MemoryManager(
            self.db,
            self._session_id,
            history_limit=self.settings.memory_history_limit,
            enable_semantic=user_prefs.enable_semantic_memory,
            storage_path=self.settings.worlds_path.parent / "storage",
            llm_manager=self.llm_manager,  # V4: Pass LLM for intelligent summarization
        )
        
        # V4.5 FIX: For new games, ensure memory is completely empty
        # Clear any existing data for this session (safety check)
        print(f"[GameEngine] New game - clearing memory for session {self._session_id}")
        await self.memory_manager.clear()
        
        await self.memory_manager.load()
        
        # V4 Refactor: Initialize unified state-memory manager
        self.state_memory = StateMemoryManager(
            db=self.db,
            session_id=self._session_id,
            state_manager=self.state_manager,
            memory_manager=self.memory_manager,
            quest_engine=self.quest_engine,
            event_manager=self.event_manager,
            story_director=self.story_director,
            personality_engine=self.personality_engine,
        )
        
        # V4.3: Initialize TurnOrchestrator
        from luna.systems.turn_orchestrator import TurnOrchestrator
        self.turn_orchestrator = TurnOrchestrator(self)
        
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
        
        # Load quest states into QuestEngine
        async with self.db.session() as db_session:
            quest_state_models = await self.db.get_all_quest_states(db_session, session_id)
            # Convert DB models to QuestInstance
            quest_instances = []
            for qm in quest_state_models:
                try:
                    instance = QuestInstance(
                        quest_id=qm.quest_id,
                        status=QuestStatus(qm.status),
                        current_stage_id=qm.current_stage_id,
                        stage_data=qm.stage_data or {},
                        started_at=qm.started_at,
                        completed_at=qm.completed_at,
                    )
                    quest_instances.append(instance)
                except Exception as e:
                    print(f"[GameEngine] Error loading quest state {qm.quest_id}: {e}")
            
            self.quest_engine.load_states(quest_instances)
            print(f"[GameEngine] Loaded {len(quest_instances)} quest states")
            
            # If no quest states found, initialize from world definitions
            if not quest_instances:
                print("[GameEngine] No quest states found, initializing from world definitions...")
                from luna.systems.quests import QuestInstance as QEInstance, QuestStatus
                for quest_id, quest_def in self.world.quests.items():
                    # Create initial available quest
                    q_instance = QEInstance(
                        quest_id=quest_id,
                        status=QuestStatus.AVAILABLE,
                        current_stage_id="",
                        stage_data={},
                    )
                    quest_instances.append(q_instance)
                    # Save to database
                    await self.db.save_quest_state(
                        db_session,
                        session_id=session_id,
                        quest_id=quest_id,
                        status="available",
                    )
                self.quest_engine.load_states(quest_instances)
                print(f"[GameEngine] Initialized {len(quest_instances)} quests")
        
        # Load personality states
        async with self.db.session() as db_session:
            session_model = await self.db.get_session(db_session, session_id)
            print(f"[GameEngine] Loading personality state... Session model: {session_model is not None}")
            if session_model:
                print(f"[GameEngine] personality_state: {session_model.personality_state is not None}")
            if session_model and session_model.personality_state:
                try:
                    from luna.systems.personality import PersonalityState
                    personality_data = session_model.personality_state
                    states_list = personality_data.get("states", [])
                    print(f"[GameEngine] Loading {len(states_list)} personality states from DB")
                    personality_states = [
                        PersonalityState(**state_data) 
                        for state_data in states_list
                    ]
                    self.personality_engine.load_states(personality_states)
                    print(f"[GameEngine] ✅ Loaded {len(personality_states)} personality states")
                except Exception as e:
                    print(f"[GameEngine] ❌ Error loading personality states: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[GameEngine] No personality state found, starting fresh")
        
        # Initialize NPC links
        self._init_npc_links()
        
        # Link personality engine to multi-npc manager
        self.multi_npc_manager.personality_engine = self.personality_engine
        
        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager,
        )
        
        # Initialize movement handler (V4 refactor)
        self.movement_handler = MovementHandler(
            self.world,
            self.location_manager,
            self.state_manager.current,
        )
        
        # Initialize gameplay manager (lazy import to avoid circular imports)
        from luna.systems.gameplay_manager import GameplayManager
        self.gameplay_manager = GameplayManager(self.world)
        
        # Initialize global event manager and load saved events
        self.event_manager = GlobalEventManager(self.world)
        async with self.db.session() as db_session:
            event_states = await self.db.get_global_event_states(db_session, session_id)
            if event_states:
                # Convert DB models to dict format expected by GlobalEventManager
                events_data = {
                    "active_events": {
                        evt.event_id: {
                            "event_id": evt.event_id,
                            "name": evt.name,
                            "description": evt.description,
                            "icon": evt.icon,
                            "duration_turns": evt.duration_turns,
                            "remaining_turns": evt.remaining_turns,
                            "effects": evt.effects,
                            "narrative_prompt": evt.narrative_prompt,
                        }
                        for evt in event_states
                    },
                    "event_history": {},  # History not persisted for now
                    "current_turn": game_state.turn_count,
                }
                self.event_manager.from_dict(events_data)
                print(f"[GameEngine] Loaded {len(event_states)} active global events")
        
        # Load StoryDirector state
        async with self.db.session() as db_session:
            sd_state = await self.db.get_story_director_state(db_session, session_id)
            if sd_state:
                self.story_director.from_dict({
                    "current_chapter": sd_state.current_chapter,
                    "current_beat_index": sd_state.current_beat_index,
                    "completed_beats": sd_state.completed_beats,
                    "beat_history": sd_state.beat_history,
                })
                print(f"[GameEngine] Loaded StoryDirector state")
        
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
        
        # V4.1: Initialize Time Manager (NEEDED for loaded games too)
        from luna.systems.time_manager import TimeManager, TimeConfig
        self.time_manager = TimeManager(
            game_state=game_state,
            config=TimeConfig(
                turns_per_period=5,
                enable_auto_advance=True,
                enable_rest_commands=True,
                enable_deadlines=True,
            ),
            on_time_change=self._on_time_change,
        )
        
        # V4.1: Initialize Schedule Manager (NPC routines)
        from luna.systems.schedule_manager import ScheduleManager
        self.schedule_manager = ScheduleManager(game_state=game_state, world=self.world)
        
        # V4.2: Initialize Phase Manager (8 turns per phase)
        from luna.systems.phase_manager import PhaseManager, PhaseConfig
        self.phase_manager = PhaseManager(
            game_state=game_state,
            schedule_manager=self.schedule_manager,
            config=PhaseConfig(turns_per_phase=8),
            on_phase_change=self._on_phase_change,
        )
        
        # V4.5: Load phase manager state if exists
        phase_state = game_state.flags.get("_phase_manager_state")
        if phase_state:
            self.phase_manager.from_dict(phase_state)
            print(f"[GameEngine] Loaded phase manager state: {phase_state}")
        
        # V4 Refactor: Initialize unified state-memory manager
        self.state_memory = StateMemoryManager(
            db=self.db,
            session_id=self._session_id,
            state_manager=self.state_manager,
            memory_manager=self.memory_manager,
            quest_engine=self.quest_engine,
            event_manager=self.event_manager,
            story_director=self.story_director,
            personality_engine=self.personality_engine,
        )
        
        # V4.3: Initialize TurnOrchestrator
        from luna.systems.turn_orchestrator import TurnOrchestrator
        self.turn_orchestrator = TurnOrchestrator(self)
        
        self._initialized = True
        return True
    
    # ========================================================================
    # Main Game Loop
    # ========================================================================
    
    async def process_turn(self, user_input: str) -> TurnResult:
        """Process a single game turn (10 steps).
        
        V4.3 REFACTOR: Delegates to TurnOrchestrator while preserving
        all original functionality.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Turn result with narrative and media paths
        """
        # V3.1 FIX: Skip empty inputs
        if not user_input or not user_input.strip():
            print("[GameEngine] Empty input received, skipping turn")
            return TurnResult(
                text="[Nessun input ricevuto]",
                turn_number=0,
                provider_used="system",
            )
        
        # Store for affinity calculation (Python-based, not LLM)
        self._last_user_input = user_input
        
        if not self._initialized:
            await self.initialize()
        
        # V4.3: Delegate to TurnOrchestrator
        return await self.turn_orchestrator.execute_turn(user_input)
    
    async def _process_turn_legacy(self, user_input: str) -> TurnResult:
        """LEGACY: Original process_turn implementation (kept for reference).
        
        This method contains the original ~1000 line implementation.
        All functionality has been migrated to TurnOrchestrator.
        """
        # Store for affinity calculation (Python-based, not LLM)
        self._last_user_input = user_input
        
        if not self._initialized:
            await self.initialize()
        
        game_state = self.state_manager.current
        
        # V4.2 DEBUG: Start turn tracing
        tracer.start_turn(game_state.turn_count, user_input)
        
        # Check critical: initialized
        tracer.expect("engine_initialized", True)
        tracer.actual("engine_initialized", self._initialized)
        
        # -------------------------------------------------------------------
        # STEP 0d: Check for Dynamic Event (Random/Daily)
        # Events are NON-BLOCKING - they appear in the Event widget while
        # conversation with Luna continues normally
        # -------------------------------------------------------------------
        pending_event = None
        if self.gameplay_manager:
            # Check if there's already a pending event
            if self.gameplay_manager.has_pending_event():
                pending_event = self.gameplay_manager.get_pending_event()
                # Check if user is making a choice (1, 2, etc.)
                choice_index = self._parse_event_choice(user_input)
                if choice_index is not None:
                    print(f"[GameEngine] Processing event choice: {choice_index}")
                    return await self._process_event_choice(choice_index, game_state)
                # Otherwise, user is writing normally - event persists in widget
                # User can interact with event via UI buttons or let it expire
                print(f"[GameEngine] User writing normally, event remains pending")
            # Check for new event (only if no pending event)
            if not pending_event:
                new_event = self.gameplay_manager.check_dynamic_event(game_state)
                if new_event:
                    print(f"[GameEngine] Dynamic event available: {new_event.event_id}")
                    pending_event = new_event
        else:
            print("[GameEngine] WARNING: Gameplay manager not initialized!")
        
        # -------------------------------------------------------------------
        # STEP 0a: Check for Movement Intent (V4: using MovementHandler)
        # -------------------------------------------------------------------
        with tracer.step_context("Movement Detection", "movement"):
            tracer.info(f"Input: '{user_input}'")
            
            # Check: pattern detection
            tracer.expect("pattern_detected", True if any(v in user_input.lower() for v in ["vado", "esco", "entro", "torno"]) else None)
            
            print(f"[GameEngine] Checking movement intent for: '{user_input}'")
            movement_result = await self.movement_handler.handle_movement(user_input)
            
            actual_detected = movement_result is not None
            tracer.actual("pattern_detected", actual_detected, f"MovementHandler returned {movement_result}")
            
            if movement_result:
                tracer.actual("movement_success", movement_result.success)
                tracer.actual("target_location", movement_result.target_location_id)
                tracer.actual("companion_left", movement_result.companion_left_behind)
            
            print(f"[GameEngine] Movement result: {movement_result}")
            if movement_result is not None:
                print(f"[GameEngine] Movement detected: success={movement_result.success}, target={movement_result.target_location_id}")
            
        if movement_result:
            if not movement_result.success:
                # Movement failed (blocked, invalid location, etc.)
                return TurnResult(
                    text=movement_result.error_message,
                    user_input=user_input,  # V4.2 FIX: Include user input for chat display
                    turn_number=game_state.turn_count,
                    provider_used="system",
                )
            
            # V4.1: Handle movement with companion left behind
            print(f"[GameEngine] MOVEMENT DEBUG: companion_left_behind={movement_result.companion_left_behind}, active_companion={game_state.active_companion}")
            if movement_result.companion_left_behind and game_state.active_companion:
                print(f"[GameEngine] MOVEMENT DEBUG: Entering movement block")
                try:
                    old_companion = game_state.active_companion
                    print(f"[GameEngine] MOVEMENT DEBUG: old_companion={old_companion}")
                    solo_name = self._ensure_solo_companion()
                    print(f"[GameEngine] MOVEMENT DEBUG: solo_name={solo_name}")
                    self.state_manager.switch_companion(solo_name)
                    self.companion = solo_name
                    print(f"[GameEngine] Movement left {old_companion} behind, switching to solo")
                    
                    # Build combined message
                    transition_text = movement_result.transition_text or ""
                    left_message = movement_result.companion_message or f"{old_companion} rimane indietro."
                    combined_text = f"{transition_text}\n\n{left_message}"
                    
                    # V4.1: Save user message to memory (BUG FIX - was missing!)
                    await self.state_memory.add_message(
                        role="user",
                        content=user_input,
                        turn_number=game_state.turn_count,
                    )
                    
                    # V4.1: Save state BEFORE generating image (so location is persisted)
                    await self.state_memory.save_all()
                    
                    # V4.1 FIX: Advance turn count
                    self.state_manager.advance_turn()
                    
                    # V4.2 FIX: Call phase manager to increment turns_in_phase
                    if self.phase_manager:
                        self.phase_manager.on_turn_end()
                    
                    # V4.1: Generate image for new location (solo mode - empty location)
                    image_path = None
                    if movement_result.target_location_id:
                        img_params = self.movement_handler.get_solo_mode_image_params(
                            movement_result.target_location_id
                        )
                        if img_params:
                            if self._no_media:
                                # V4.2: Log prompt even when media disabled
                                with tracer.step_context("Movement Solo Mode Prompt", "media"):
                                    tracer.info(f"Solo mode movement to: {movement_result.target_location_id}")
                                    tracer.info(f"Visual EN: {img_params.get('visual_en', 'N/A')}")
                                    tracer.info(f"Location style: {img_params.get('location_visual_style', 'N/A')}")
                                    print(f"\n{'='*60}")
                                    print("🖼️  SOLO MODE PROMPT (Media Disabled):")
                                    print(f"{'='*60}")
                                    print(f"Location: {movement_result.target_location_id}")
                                    print(f"Visual: {img_params.get('visual_en', 'N/A')}")
                                    print(f"{'='*60}\n")
                            elif self.media_pipeline:
                                print(f"[GameEngine] Generating solo mode image for {movement_result.target_location_id}")
                                try:
                                    media_result = await self.media_pipeline.generate_all(
                                        text=combined_text,
                                        visual_en=img_params["visual_en"],
                                        tags=img_params["tags"],
                                        companion_name="_solo_",  # No character
                                        base_prompt="",  # No LoRAs
                                        location_id=movement_result.target_location_id,
                                        location_visual_style=img_params["location_visual_style"],
                                    )
                                    image_path = media_result.image_path if media_result else None
                                    print(f"[GameEngine] Solo mode image: {image_path}")
                                except Exception as e:
                                    print(f"[GameEngine] Failed to generate solo image: {e}")
                            else:
                                tracer.warning("No media pipeline for solo mode image")
                    
                    # V4.1: Schedule-based auto-switch (who's at this location?)
                    switched_from_schedule = False
                    schedule_companion = None
                    if self.schedule_manager:
                        tracer.info("Checking schedule for NPCs in new location")
                        schedule_companion = self.schedule_manager.get_primary_npc(
                            movement_result.target_location_id
                        )
                        
                        tracer.expect("schedule_companion_found", True)  # Ci aspettiamo di trovare qualcuno
                        tracer.actual("schedule_companion_found", schedule_companion is not None, 
                                     f"Found: {schedule_companion}")
                        
                        if schedule_companion and schedule_companion != solo_name:
                            # Found someone here! Switch from solo to them
                            print(f"[Schedule] Auto-switch on arrival: solo -> {schedule_companion}")
                            tracer.check("auto_switch_executed", True, True, CheckStatus.PASS,
                                        f"Switched to {schedule_companion}")
                            self.state_manager.switch_companion(schedule_companion)
                            self.companion = schedule_companion
                            solo_name = schedule_companion  # Update for result
                            switched_from_schedule = True
                            # Add to text
                            schedule_context = self.schedule_manager.build_schedule_context(schedule_companion)
                            combined_text += f"\n\n[Trovi {schedule_companion} qui. {schedule_context.split(chr(10))[2]}]"
                        elif schedule_companion is None:
                            tracer.check("auto_switch_executed", True, False, CheckStatus.FAIL,
                                        "No NPC found in location according to schedule!")
                        else:
                            tracer.info(f"Schedule companion is same as solo: {schedule_companion}")
                    
                    # Get available actions for new location (BUG FIX - was missing!)
                    available_actions = []
                    if self.gameplay_manager:
                        actions = self.gameplay_manager.get_available_actions(game_state)
                        available_actions = [a.to_dict() for a in actions]
                    
                    return TurnResult(
                        text=combined_text,
                        user_input=user_input,  # V4.2 FIX: Include user input for chat display
                        turn_number=game_state.turn_count,
                        provider_used="system",
                        new_location_id=movement_result.target_location_id,  # Force UI update
                        switched_companion=True or switched_from_schedule,
                        previous_companion=old_companion,
                        current_companion=solo_name,
                        image_path=image_path,
                        available_actions=available_actions,
                    )
                except Exception as e:
                    print(f"[GameEngine] ERROR in movement handling: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fall through to normal processing
                print(f"[GameEngine] MOVEMENT DEBUG: After try/except block")
            else:
                print(f"[GameEngine] MOVEMENT DEBUG: Skipped movement block (conditions not met)")
            
            # Normal movement (no companion or companion followed - rare in V4)
            print(f"[GameEngine] MOVEMENT DEBUG: Entering NORMAL movement block")
            # Still save state and message
            await self.state_memory.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )
            await self.state_memory.save_all()
            
            # V4.1 FIX: Advance turn count
            self.state_manager.advance_turn()
            
            # V4.2 FIX: Call phase manager to increment turns_in_phase
            if self.phase_manager:
                self.phase_manager.on_turn_end()
            
            # Get available actions for new location (BUG FIX - was missing!)
            available_actions = []
            if self.gameplay_manager:
                actions = self.gameplay_manager.get_available_actions(game_state)
                available_actions = [a.to_dict() for a in actions]
            
            return TurnResult(
                text=movement_result.transition_text or "Ti muovi verso la nuova location.",
                user_input=user_input,  # V4.2 FIX: Include user input for chat display
                turn_number=game_state.turn_count,
                provider_used="system",
                new_location_id=movement_result.target_location_id,  # Force UI update
                available_actions=available_actions,
            )
        else:
            print(f"[GameEngine] No movement detected, proceeding to normal LLM processing")
        
        # -------------------------------------------------------------------
        # STEP 0b: Check for Farewell (player leaving companion)
        # -------------------------------------------------------------------
        is_farewell = self._detect_farewell(user_input)
        switched_companion = False
        old_companion = game_state.active_companion
        
        if is_farewell and game_state.active_companion:
            # Player said goodbye to current companion
            # Switch to "solo" mode (player alone)
            solo_name = self._ensure_solo_companion()
            success = self.state_manager.switch_companion(solo_name)
            if success:
                switched_companion = True
                self.companion = solo_name
                print(f"[GameEngine] Farewell detected: {old_companion} -> solo mode")
            
            # Save user message to memory (BUG FIX - was missing!)
            await self.state_memory.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )
            await self.state_memory.save_all()
            
            # V4.1 FIX: Advance turn count
            self.state_manager.advance_turn()
            
            # V4.2 FIX: Call phase manager to increment turns_in_phase
            if self.phase_manager:
                self.phase_manager.on_turn_end()
            
            return TurnResult(
                text=f"Hai salutato {old_companion}. Ora sei da solo.",
                user_input=user_input,  # V4.2 FIX: Include user input for chat update
                turn_number=game_state.turn_count,
                provider_used="system",
                switched_companion=True,
                previous_companion=old_companion,
                current_companion=solo_name,
                new_location_id=game_state.current_location,  # V4 FIX: Current location for UI update
            )
        
        # -------------------------------------------------------------------
        # STEP 0c: Check for Rest/Sleep command (Time Manager Phase 2)
        # -------------------------------------------------------------------
        rest_message = None
        if self.time_manager:
            rest_message = self.time_manager.check_rest_command(user_input)
            if rest_message:
                print(f"[GameEngine] Rest command detected: {rest_message}")
        
        # -------------------------------------------------------------------
        # STEP 0c2: Check for Freeze/Unfreeze commands (V4.2)
        # -------------------------------------------------------------------
        freeze_result = self._check_freeze_command(user_input)
        if freeze_result:
            return TurnResult(
                text=freeze_result,
                user_input=user_input,  # V4.2 FIX: Include user input for chat display
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
        # -------------------------------------------------------------------
        # STEP 0d: Check for Schedule query ("dove è Luna?", "routine di Stella")
        # -------------------------------------------------------------------
        schedule_query = self._check_schedule_query(user_input)
        if schedule_query:
            npc_name, location, activity = schedule_query
            return TurnResult(
                text=f"📍 {npc_name} è a {location}. {activity}",
                user_input=user_input,  # V4.2 FIX: Include user input for chat display
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
        # -------------------------------------------------------------------
        # STEP 0e: Auto-switch Companion based on user input
        # V4.3: Using refactored NPCDetector
        # -------------------------------------------------------------------
        mentioned_companion = self.npc_detector.detect_companion_in_input(user_input)
        print(f"[GameEngine] Mentioned companion detection: '{mentioned_companion}'")
        
        if mentioned_companion and mentioned_companion != game_state.active_companion:
            # Switch to the mentioned companion
            success = self.state_manager.switch_companion(mentioned_companion)
            if success:
                switched_companion = True
                self.companion = mentioned_companion
                print(f"[GameEngine] Auto-switched companion: {old_companion} -> {mentioned_companion}")
        
        # Check for generic NPC interaction if no known companion mentioned
        elif not mentioned_companion:
            generic_npc = self.npc_detector.detect_generic_npc_interaction(user_input)
            print(f"[GameEngine] Generic NPC detection result: {generic_npc}")
            if generic_npc:
                # Create temporary companion for this NPC
                temp_name = self._create_temporary_companion(generic_npc)
                
                # Initialize outfit for the temporary companion
                from luna.core.models import OutfitState
                temp_companion = self.world.companions.get(temp_name)
                if temp_companion:
                    outfit = OutfitState(
                        style="default",
                        description=generic_npc['description'],
                    )
                    game_state.companion_outfits[temp_name] = outfit
                
                # Switch to the temporary companion
                success = self.state_manager.switch_companion(temp_name)
                if success:
                    switched_companion = True
                    self.companion = temp_name
                    print(f"[GameEngine] Auto-switched to temporary NPC: {old_companion} -> {temp_name}")
                else:
                    print(f"[GameEngine] Failed to switch to temporary NPC: {temp_name}")
        
        # -------------------------------------------------------------------
        # STEP 0c: Multi-NPC Check
        # -------------------------------------------------------------------
        # Check if multi-NPC interaction should occur
        multi_npc_sequence = None
        present_npcs = self.multi_npc_manager.get_present_npcs(
            game_state.active_companion,
            game_state
        )
        
        if len(present_npcs) > 0:
            multi_npc_sequence = self.multi_npc_manager.process_turn(
                player_input=user_input,
                active_npc=game_state.active_companion,
                present_npcs=present_npcs,
                game_state=game_state,
            )
            
            if multi_npc_sequence:
                print(f"[GameEngine] Multi-NPC sequence detected: {len(multi_npc_sequence.turns)} turns")
        
        # -------------------------------------------------------------------
        # STEP 1: Personality Analysis (regex-based, always)
        # -------------------------------------------------------------------
        # Check if current companion is temporary (generic NPC)
        current_companion_def = self.world.companions.get(game_state.active_companion)
        is_temporary = getattr(current_companion_def, 'is_temporary', False)
        
        personality_update = self.personality_engine.analyze_player_action(
            game_state.active_companion,
            user_input,
            game_state.turn_count,
            is_temporary=is_temporary,
        )
        
        # -------------------------------------------------------------------
        # STEP 1b: Outfit Modifier (deterministic)
        # -------------------------------------------------------------------
        modified, is_major, outfit_desc_it = self.outfit_modifier.process_turn(
            user_input, game_state, current_companion_def
        )
        
        # Handle major outfit change (needs async translation)
        if is_major and outfit_desc_it:
            await self.outfit_modifier.apply_major_change(
                game_state, 
                outfit_desc_it, 
                self.llm_manager
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
        
        # Separate auto-activations from choice-required quests
        auto_quests = []
        choice_quests = []
        
        for quest_id in activated:
            if quest_id.startswith("CHOICE:"):
                choice_quests.append(quest_id.replace("CHOICE:", ""))
            else:
                auto_quests.append(quest_id)
        
        if auto_quests:
            print(f"[GameEngine] Quests auto-activated: {auto_quests}")
        if choice_quests:
            print(f"[GameEngine] Quests awaiting choice: {choice_quests}")
        
        # Activate auto-quests immediately
        for quest_id in auto_quests:
            async with self.db.session() as db_session:
                result = self.quest_engine.activate_quest(quest_id, game_state)
                if result:
                    new_quests.append(result.title)
                    quest_context += f"\n{result.narrative_context}"
        
        # Add choice quests to pending (UI will handle them)
        for quest_id in choice_quests:
            self.quest_engine.add_pending_choice(quest_id, game_state)
        
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
        # V4 Refactor: Get memory context via unified manager
        memory_context = self.state_memory.get_memory_context(
            query=user_input,
            max_facts=self.settings.memory_max_context_facts,
            min_importance=self.settings.memory_min_importance,
        )
        
        # Add Multi-NPC context if sequence detected
        multi_npc_context = ""
        if multi_npc_sequence:
            npc_personalities = {
                name: getattr(comp, 'base_personality', '')
                for name, comp in self.world.companions.items()
            }
            multi_npc_context = self.multi_npc_manager.format_prompt_for_llm(
                multi_npc_sequence,
                npc_personalities
            )
        
        # Extract forced poses from user input (e.g., "Luna accavalla le gambe")
        forced_poses = None
        if self.pose_extractor.has_explicit_pose(user_input):
            forced_poses = self.pose_extractor.get_forced_visual_description(user_input)
            if forced_poses:
                print(f"[GameEngine] Forced poses detected: {forced_poses}")
        
        # Update activity system for active companion (NEW)
        if self.activity_system:
            time_str = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
            self.activity_system.update_activity(
                npc_name=game_state.active_companion,
                time_of_day=time_str,
                current_turn=game_state.turn_count
            )
        
        system_prompt = self.prompt_builder.build_system_prompt(
            game_state=game_state,
            personality_engine=self.personality_engine,
            story_context=story_context,
            quest_context=quest_context,
            memory_context=memory_context,
            location_manager=self.location_manager,
            event_manager=self.event_manager,
            multi_npc_context=multi_npc_context,
            switched_from=old_companion if switched_companion else None,
            is_temporary=is_temporary,
            forced_poses=forced_poses,
            activity_system=self.activity_system,
            initiative_system=self.initiative_system,
        )
        
        # V4.1: Add schedule context for active companion
        if self.schedule_manager:
            schedule_context = self.schedule_manager.build_schedule_context(
                game_state.active_companion
            )
            if schedule_context:
                system_prompt += f"\n\n=== CURRENT SITUATION ===\n{schedule_context}\n"
        
        # -------------------------------------------------------------------
        # STEP 5: LLM Generation
        # -------------------------------------------------------------------
        # Build history from memory (V4 Refactor: Unified manager)
        history = []
        recent_msgs = self.state_memory.get_recent_history(limit=20)
        for msg in recent_msgs:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        # -------------------------------------------------------------------
        # STEP 5: LLM Generation with Guardrails
        # -------------------------------------------------------------------
        max_retries = 2
        current_retry = 0
        llm_response = None
        provider_used = "unknown"
        
        while current_retry <= max_retries:
            try:
                raw_response = await self.llm_manager.generate(
                    system_prompt=system_prompt,
                    user_input=user_input,
                    history=history,
                    json_mode=True,
                )
                provider_used = raw_response.provider or "unknown"
                
                # Guardrails validation
                try:
                    from luna.ai.guardrails import validate_llm_response, GuardrailsValidationError
                    llm_response = validate_llm_response(raw_response.raw_response or raw_response)
                    break  # Success! Exit retry loop
                    
                except Exception as guard_err:
                    from luna.ai.guardrails import GuardrailsValidationError
                    if isinstance(guard_err, GuardrailsValidationError):
                        print(f"[Guardrails] Validation failed (attempt {current_retry + 1}): {guard_err.suggestion}")
                        
                        if current_retry < max_retries:
                            # Add correction prompt and retry
                            from luna.ai.guardrails import ResponseGuardrails
                            correction = ResponseGuardrails.get_retry_prompt(guard_err)
                            system_prompt += correction
                            print(f"[Guardrails] Retrying with correction...")
                        else:
                            # Max retries reached, use fallback
                            print(f"[Guardrails] Max retries reached, using fallback")
                            llm_response = self._create_fallback_response(guard_err)
                            break
                    else:
                        raise  # Reraise if not validation error
                    
            except Exception as e:
                print(f"[GameEngine] LLM generation failed: {e}")
                if current_retry >= max_retries:
                    return TurnResult(
                        text="[Error generating response. Please try again.]",
                        error=str(e),
                        turn_number=game_state.turn_count,
                    )
            
            current_retry += 1
        
        if llm_response is None:
            return TurnResult(
                text="[Unable to generate valid response after retries]",
                error="Guardrails validation failed",
                turn_number=game_state.turn_count,
            )
        
        # Save messages to memory (V4 Refactor: Unified state-memory manager)
        await self.state_memory.add_message(
            role="user",
            content=user_input,
            turn_number=game_state.turn_count,
        )
        
        await self.state_memory.add_message(
            role="assistant",
            content=llm_response.text,
            turn_number=game_state.turn_count,
            visual_en=llm_response.visual_en,
            tags_en=llm_response.tags_en,
        )
        
        # V4.2: Auto-freeze turns during important scenes
        if self.phase_manager:
            auto_frozen = self.phase_manager.auto_freeze_if_needed(user_input, llm_response.text)
            if auto_frozen:
                print(f"[GameEngine] Auto-frozen turns: {self.phase_manager._freeze_reason}")
        
        # Save any new fact from response
        if llm_response.updates and llm_response.updates.new_fact:
            await self.state_memory.add_fact(
                text=llm_response.updates.new_fact,
                importance=7,  # High importance for explicit facts
                source=game_state.active_companion,
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
        # STEP 7a: Phase Manager (V4.2 - 8 turns per phase)
        # -------------------------------------------------------------------
        with tracer.step_context("Phase Manager", "phase"):
            phase_result = None
            if self.phase_manager:
                turns_before = self.phase_manager._turns_in_phase
                tracer.expect("turns_incremented", turns_before + 1)
                
                phase_result = self.phase_manager.on_turn_end()
                
                turns_after = self.phase_manager._turns_in_phase
                tracer.actual("turns_incremented", turns_after)
                tracer.actual("is_frozen", self.phase_manager.is_frozen)
                
                if phase_result:
                    tracer.check("phase_changed", True, True, CheckStatus.PASS,
                               f"{phase_result.old_time} -> {phase_result.new_time}")
                    if self.time_manager:
                        self.time_manager._turns_since_last_advance = 0
                else:
                    tracer.info(f"No phase change yet (turn {turns_after}/8)")
            else:
                tracer.critical_alert("PhaseManager Missing", "phase_manager is None!")
                tracer.actual("phase_manager_exists", False)
        
        # -------------------------------------------------------------------
        # STEP 7b: Time Manager (Deadlines only - PhaseManager gestisce il tempo)
        # -------------------------------------------------------------------
        time_messages = []
        if self.time_manager:
            # V4.2: PhaseManager gestisce l'avanzamento del tempo (8 turni/fase)
            # TimeManager si occupa solo delle deadline delle quest
            # Non chiamare on_turn_end() qui per evitare conflitti
            
            # Check deadlines (ALWAYS check)
            deadline_messages = self.time_manager.check_deadlines()
            time_messages.extend(deadline_messages)
        
        # -------------------------------------------------------------------
        # STEP 7b: Check Global Events
        # -------------------------------------------------------------------
        active_event = None
        if self.event_manager:
            new_events = self.event_manager.check_and_activate_events(game_state)
            if new_events:
                active_event = new_events[0]  # Primary event
                print(f"[GameEngine] Global event activated: {active_event.event_id}")
            else:
                active_event = self.event_manager.get_primary_event()
        else:
            print("[GameEngine] WARNING: Event manager not initialized!")
        
        # -------------------------------------------------------------------
        # STEP 7c: Build Dynamic Event Data (if pending)
        # -------------------------------------------------------------------
        dynamic_event = None
        if pending_event:
            dynamic_event = {
                "event_id": pending_event.event_id,
                "event_type": pending_event.event_type.value,
                "narrative": pending_event.narrative,
                "choices": [
                    {"text": c.text, "index": i+1}
                    for i, c in enumerate(pending_event.choices)
                ],
            }
            print(f"[GameEngine] Attaching dynamic event to result: {pending_event.event_id}")
        
        # -------------------------------------------------------------------
        # STEP 8: Media Generation (async, non-blocking)
        # -------------------------------------------------------------------
        media_result = None
        multi_npc_image_paths = []
        
        if multi_npc_sequence:
            # Multi-NPC: Generate sequence of images sequentially
            print(f"[GameEngine] Generating Multi-NPC image sequence...")
            
            # V4.2: Check if media pipeline available
            if self._no_media:
                print("[GameEngine] Multi-NPC: Media disabled - skipping image generation")
                with tracer.step_context("Multi-NPC Media", "media"):
                    tracer.info("Multi-NPC sequence skipped (media disabled)")
                    tracer.info(f"Would generate {len(multi_npc_sequence.turns)} images")
            elif not self.media_pipeline:
                print("[GameEngine] Multi-NPC: No media pipeline available!")
            else:
                # Prepare turn data for image generation
                sequence_turns = []
                for turn in multi_npc_sequence.turns:
                    # Skip player turns
                    speaker_type_val = turn.speaker_type.value if hasattr(turn.speaker_type, 'value') else str(turn.speaker_type)
                    if speaker_type_val == "PLAYER":
                        continue
                        
                    # Build character list for this turn
                    characters = self.multi_npc_manager.prepare_characters_for_builder(
                        turn,
                        present_npcs + [game_state.active_companion],
                        {name: game_state.get_outfit(name) for name in present_npcs + [game_state.active_companion]}
                    )
                    
                    # Get base prompt for primary speaker
                    speaker_def = self.world.companions.get(turn.speaker)
                    base_prompt = speaker_def.base_prompt if speaker_def else None
                    
                    sequence_turns.append({
                        "visual_en": turn.visual_en or llm_response.visual_en,
                        "tags": turn.tags_en or llm_response.tags_en,
                        "characters": characters,
                        "companion_name": turn.speaker,
                        "base_prompt": base_prompt,
                        "outfit": game_state.get_outfit(turn.speaker),
                    })
                
                # Generate images sequentially
                multi_npc_image_paths = await self.media_pipeline.generate_multi_npc_sequence(
                    sequence_turns,
                    on_image_ready=None,  # Callback handled by UI
                )
            
            # Create media result with first image
            first_image = multi_npc_image_paths[0] if multi_npc_image_paths else None
            media_result = MediaResult(
                success=True,
                image_path=first_image,
            )
            
        else:
            # Standard single image generation
            outfit = game_state.get_outfit()
            
            # V3 PATTERN: Override outfit description with WARDROBE description for consistency
            # This prevents LLM-generated descriptions from changing the visual appearance every turn
            # EXCEPTION: If outfit was modified by OutfitModifier, preserve those changes
            active_companion_def = self.world.companions.get(game_state.active_companion)
            if active_companion_def and outfit:
                # Check if outfit has custom modifications (from OutfitModifier)
                has_custom_components = bool(outfit.components and len(outfit.components) > 0)
                
                if has_custom_components:
                    # Outfit was modified by system - keep the modified description
                    print(f"[GameEngine] Using modified outfit: {outfit.description[:50]}...")
                else:
                    # Standard case: use wardrobe for consistency
                    wardrobe_style = outfit.style
                    if active_companion_def.wardrobe and wardrobe_style in active_companion_def.wardrobe:
                        wardrobe_def = active_companion_def.wardrobe[wardrobe_style]
                        if isinstance(wardrobe_def, str):
                            consistent_desc = wardrobe_def
                        else:
                            consistent_desc = getattr(wardrobe_def, 'sd_prompt', None) or \
                                             getattr(wardrobe_def, 'description', wardrobe_style)
                        # Override the potentially variable LLM description with consistent wardrobe description
                        outfit.description = consistent_desc
                        print(f"[GameEngine] Using consistent wardrobe outfit: {wardrobe_style} = {consistent_desc[:50]}...")
            
            # Get base prompt for active companion (SACRED for visual consistency)
            base_prompt = active_companion_def.base_prompt if active_companion_def else None
            
            # DEBUG: Track base prompt changes
            if active_companion_def:
                bp_preview = base_prompt[:60] if base_prompt else "NONE"
                print(f"[BasePrompt DEBUG] {game_state.active_companion}: {bp_preview}...")
            
            # Build secondary characters list for multi-character scenes
            secondary_characters = None
            if llm_response.secondary_characters:
                secondary_characters = []
                for char_name in llm_response.secondary_characters:
                    char_def = self.world.companions.get(char_name)
                    if char_def:
                        secondary_characters.append({
                            'name': char_name,
                            'base_prompt': char_def.base_prompt,
                        })
                
                if secondary_characters:
                    print(f"[GameEngine] Multi-character scene: {game_state.active_companion} + "
                          f"{[c['name'] for c in secondary_characters]}")
            
            # V4.0: Get location description for image generation
            location_id = game_state.current_location
            location_desc = None
            if location_id and self.world:
                loc_def = self.world.locations.get(location_id)
                if loc_def:
                    # Use visual_style (English) for SD prompt, fallback to name
                    location_desc = loc_def.visual_style if loc_def.visual_style else loc_def.name
                    print(f"[GameEngine] Image location: {location_id} ({location_desc})")
            
            # V4.2: Log prompt parameters even if media is disabled
            if self._no_media:
                with tracer.step_context("Media Prompt", "media"):
                    tracer.info("Media generation disabled - logging prompt that would be sent")
                    tracer.info(f"Companion: {game_state.active_companion}")
                    tracer.info(f"Outfit: {outfit}")
                    tracer.info(f"Base prompt: {base_prompt[:80] if base_prompt else 'None'}...")
                    tracer.info(f"Visual EN: {llm_response.visual_en}")
                    tracer.info(f"Tags: {llm_response.tags_en}")
                    tracer.info(f"Location: {location_id} - {location_desc}")
                    tracer.info(f"Secondary chars: {[c['name'] for c in secondary_characters] if secondary_characters else 'None'}")
                    
                    # Try to build the actual prompt that would be sent
                    try:
                        from luna.media.builders import ImagePromptBuilder
                        builder = ImagePromptBuilder()
                        prompt_data = builder.build(
                            visual_en=llm_response.visual_en,
                            tags=llm_response.tags_en,
                            companion_name=game_state.active_companion,
                            outfit=outfit,
                            base_prompt=base_prompt,
                            location_id=location_id,
                            location_visual_style=location_desc,
                        )
                        tracer.info(f"\n{'='*60}")
                        tracer.info("FULL PROMPT THAT WOULD BE SENT TO COMFYUI:")
                        tracer.info(f"{'='*60}")
                        tracer.info(prompt_data.get("positive", "N/A"))
                        tracer.info(f"{'='*60}\n")
                        print(f"\n{'='*60}")
                        print("🖼️  MEDIA DISABLED - PROMPT PREVIEW:")
                        print(f"{'='*60}")
                        print(f"Character: {game_state.active_companion}")
                        print(f"Location: {location_id}")
                        print(f"Prompt: {prompt_data.get('positive', 'N/A')[:200]}...")
                        print(f"{'='*60}\n")
                    except Exception as e:
                        tracer.warning(f"Could not build prompt preview: {e}")
                    
                    # Create a dummy result
                    media_result = None
            elif self.media_pipeline:
                media_task = asyncio.create_task(
                    self.media_pipeline.generate_all(
                        text=llm_response.text,
                        visual_en=llm_response.visual_en,
                        tags=llm_response.tags_en,
                        companion_name=game_state.active_companion,
                        outfit=outfit,
                        base_prompt=base_prompt,  # SACRED: Use companion's base prompt from world YAML
                        secondary_characters=secondary_characters,  # Multi-character support
                        location_id=location_id,  # V4.0: Pass location for visual enforcement
                        location_description=location_desc,
                        location_visual_style=location_desc,  # V4.1: Pass for solo mode
                    )
                )
                
                # For now, wait for completion (UI can be made truly async later)
                media_result = await media_task
            else:
                # No media pipeline available (shouldn't happen normally)
                tracer.warning("No media pipeline available!")
                media_result = None
        
        # -------------------------------------------------------------------
        # STEP 9: Save State (V4 Refactor: Unified state-memory manager)
        # -------------------------------------------------------------------
        # V4.5: Save phase manager state before saving game state
        if self.phase_manager:
            game_state.flags["_phase_manager_state"] = self.phase_manager.to_dict()
        
        await self.state_memory.save_all()
        
        # -------------------------------------------------------------------
        # STEP 10: LLM Personality Analysis (periodic) - FIRE AND FORGET
        # -------------------------------------------------------------------
        # Skip LLM personality analysis for temporary NPCs
        # Fire-and-forget: runs in background without blocking the response
        if self.personality_engine._use_llm and not is_temporary:
            # Create background task - don't await it!
            asyncio.create_task(
                self._run_personality_analysis(
                    game_state.active_companion,
                    user_input,
                    llm_response.text,
                    game_state.turn_count,
                )
            )
        
        # -------------------------------------------------------------------
        # Get available actions for next turn
        # -------------------------------------------------------------------
        available_actions = []
        if self.gameplay_manager:
            actions = self.gameplay_manager.get_available_actions(game_state)
            available_actions = [a.to_dict() for a in actions]
        
        # -------------------------------------------------------------------
        # Check for Dynamic Events (Random/Daily)
        # -------------------------------------------------------------------
        dynamic_event = self._check_for_new_event(game_state)
        
        # -------------------------------------------------------------------
        # Prepare event data for result
        # -------------------------------------------------------------------
        event_data = None
        new_event_started = False
        if active_event:
            event_data = active_event.to_dict()
            new_event_started = len(new_events) > 0
        
        # -------------------------------------------------------------------
        # Build final text (Luna's response only - event is shown separately in widget)
        # -------------------------------------------------------------------
        final_text = llm_response.text
        
        # V4.1: Append time messages (rest, auto-advance, deadlines)
        all_time_messages = []
        if rest_message:
            all_time_messages.append(rest_message)
        if time_messages:  # time_messages from auto-advance/deadlines
            all_time_messages.extend(time_messages)
        if self._pending_time_message:
            all_time_messages.append(self._pending_time_message)
            self._pending_time_message = None
        
        # V4.2: Append phase change message
        if self._pending_phase_message:
            all_time_messages.append(self._pending_phase_message)
            self._pending_phase_message = None
        
        if all_time_messages:
            final_text = "\n\n".join(all_time_messages) + "\n\n" + final_text
        
        # Note: dynamic_event is passed separately to UI, not appended to text
        
        # -------------------------------------------------------------------
        # Return Result
        # -------------------------------------------------------------------
        completed_quests = [u.quest_id for u in quest_updates if u.quest_completed]
        
        # Check if photo was requested
        is_photo = validated_updates.get("photo_requested", False)
        
        # V4.2: Check if phase change caused companion to leave
        companion_left_due_to_phase = False
        needs_location_refresh = False
        if phase_result and phase_result.companion_left:
            companion_left_due_to_phase = True
            needs_location_refresh = True  # Need to show empty location
        
        # V4.2 DEBUG: Final checks before return
        with tracer.step_context("Final Result", "result"):
            tracer.expect("result_has_user_input", True)
            tracer.actual("result_has_user_input", user_input is not None and len(user_input) > 0)
            tracer.expect("result_companion", game_state.active_companion)
            tracer.actual("result_companion", game_state.active_companion)
            tracer.expect("result_turn_number", game_state.turn_count)
            tracer.actual("result_turn_number", game_state.turn_count)
        
        # V4.2 DEBUG: Finalize turn tracing
        tracer.finalize_turn()
        
        return TurnResult(
            text=final_text,
            user_input=user_input,  # Include user input for chat display
            image_path=media_result.image_path if media_result else None,
            audio_path=media_result.audio_path if media_result else None,
            video_path=media_result.video_path if media_result else None,
            affinity_changes=validated_updates.get("affinity_change", {}),
            new_quests=new_quests,
            completed_quests=completed_quests,
            gameplay_result=None,
            available_actions=available_actions,
            active_event=event_data,
            new_event_started=new_event_started,
            switched_companion=switched_companion or (phase_result and phase_result.companion_left),
            previous_companion=old_companion if switched_companion else (phase_result.old_companion if phase_result and phase_result.companion_left else None),
            current_companion=game_state.active_companion,
            is_temporary_companion=is_temporary,
            multi_npc_sequence=multi_npc_sequence,
            multi_npc_image_paths=multi_npc_image_paths if multi_npc_sequence else None,
            is_photo=is_photo,  # Flag indicating this is a requested photo
            dynamic_event=dynamic_event,  # Pending dynamic event with choices
            phase_change_result=phase_result,  # V4.2: Phase change details
            companion_left_due_to_phase=companion_left_due_to_phase,  # V4.2
            needs_location_refresh=needs_location_refresh,  # V4.2: UI should refresh image
            turn_number=game_state.turn_count,
            provider_used=provider_used,
        )
    
    # ========================================================================
    # Dynamic Events Processing
    # ========================================================================
    
    def _parse_event_choice(self, user_input: str) -> Optional[int]:
        """Parse choice index from user input.
        
        Args:
            user_input: Raw user input
            
        Returns:
            Choice index (0-based) or None if invalid
        """
        user_input = user_input.strip().lower()
        
        # Try to parse as number
        try:
            choice_num = int(user_input)
            return choice_num - 1  # Convert to 0-based
        except ValueError:
            pass
        
        # Try to match by text (first few characters)
        event = self.gameplay_manager.get_pending_event()
        if event:
            for i, choice in enumerate(event.choices):
                if choice.text.lower().startswith(user_input[:3]):
                    return i
        
        return None
    
    async def _process_event_choice(
        self,
        choice_index: int,
        game_state: GameState,
    ) -> TurnResult:
        """Process a choice from the Event widget.
        
        Args:
            choice_index: Index of chosen option (0-based)
            game_state: Current game state
            
        Returns:
            Turn result with event outcome
        """
        print(f"[_process_event_choice] Processing choice index {choice_index}")
        
        # Process the choice
        result = self.gameplay_manager.process_event_choice(choice_index, game_state)
        print(f"[_process_event_choice] Result: success={result.success}")
        
        # Advance turn
        self.state_manager.advance_turn()
        self.gameplay_manager.on_turn_end(game_state)
        
        # Build response text
        text_parts = [result.narrative]
        if result.followup:
            text_parts.append(result.followup)
        if result.message:
            text_parts.append(result.message)
        
        event_result_text = "\n\n".join(text_parts)
        
        # Generate companion response to the event result
        companion_response = await self._generate_event_response(
            event_result_text, 
            game_state
        )
        
        final_text = f"{event_result_text}\n\n{companion_response}"
        
        return TurnResult(
            text=final_text,
            turn_number=game_state.turn_count,
            provider_used="system",
            affinity_changes=result.affinity_changes,
        )
    
    def _on_time_change(self, new_time: TimeOfDay, message: str) -> None:
        """Callback when time changes (auto or rest).
        
        Args:
            new_time: New time of day
            message: Message to display to player
        """
        # Handle both enum and string
        time_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        print(f"[GameEngine] Time changed to {time_str}: {message}")
        # Message will be added to result in process_turn
        self._pending_time_message = message
        
        # V4.5: Notify UI if callback registered
        if self._ui_time_change_callback:
            try:
                self._ui_time_change_callback(new_time, message)
            except Exception as e:
                print(f"[GameEngine] Error in UI time change callback: {e}")
    
    def _on_phase_change(self, result: 'PhaseChangeResult') -> None:
        """Callback when phase changes (8 turns passed).
        
        Args:
            result: Phase change result with NPC movements
        """
        # Handle both enum and string
        old_time = result.old_time
        new_time = result.new_time
        if isinstance(old_time, str):
            try:
                old_time = TimeOfDay(old_time)
            except ValueError:
                old_time = TimeOfDay.MORNING
        if isinstance(new_time, str):
            try:
                new_time = TimeOfDay(new_time)
            except ValueError:
                new_time = TimeOfDay.MORNING
        old_str = old_time.value if hasattr(old_time, 'value') else str(old_time)
        new_str = new_time.value if hasattr(new_time, 'value') else str(new_time)
        print(f"[GameEngine] Phase changed: {old_str} -> {new_str}")
        
        # Build phase change message
        messages = [result.time_message]
        
        if result.movement_message:
            messages.append(result.movement_message)
        
        if result.companion_message:
            messages.append(result.companion_message)
            # Switch to solo if companion left
            if result.new_companion == "_solo_":
                solo_name = self._ensure_solo_companion()
                self.state_manager.switch_companion(solo_name)
                self.companion = solo_name
        
        # Store message to show player
        self._pending_phase_message = "\n\n".join(messages)
    
    def _check_for_new_event(self, game_state: GameState) -> Optional[Dict[str, Any]]:
        """Check for new random/daily event.
        
        Args:
            game_state: Current game state
            
        Returns:
            Event data if new event started, None otherwise
        """
        if not self.gameplay_manager:
            return None
        
        event = self.gameplay_manager.check_dynamic_event(game_state)
        if event:
            return {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "narrative": event.narrative,
                "choices": [
                    {"text": c.text, "index": i+1}
                    for i, c in enumerate(event.choices)
                ],
            }
        return None
    
    async def _generate_event_response(
        self,
        event_result: str,
        game_state: GameState,
    ) -> str:
        """Generate companion response to event result.
        
        Args:
            event_result: Text describing what happened in the event
            game_state: Current game state
            
        Returns:
            Companion's reaction/comment to the event
        """
        companion_name = game_state.active_companion
        print(f"[_generate_event_response] Generating response for: {companion_name}")
        
        companion = self.world.companions.get(companion_name) if self.world else None
        
        if not companion:
            print(f"[_generate_event_response] No companion data found for {companion_name}")
            return ""
        
        # Build a simple prompt for companion reaction
        prompt = f"""The following event just happened:

{event_result}

React briefly (1-2 sentences) as {companion_name} would. Stay in character."""

        try:
            response = await self.llm_manager.generate(
                system_prompt=f"You are {companion_name}. {companion.base_personality[:200]}",
                user_input=prompt,
                history=[],
                json_mode=False,
            )
            return response.text if response else ""
        except Exception as e:
            print(f"[_generate_event_response] Error: {e}")
            return ""
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    def _load_world(self, world_id: str) -> Optional[WorldDefinition]:
        """Load world definition."""
        from luna.systems.world import get_world_loader
        loader = get_world_loader()
        return loader.load_world(world_id)
    
    async def _run_personality_analysis(
        self,
        companion_name: str,
        user_input: str,
        assistant_response: str,
        turn_count: int,
    ) -> None:
        """Run personality analysis in background (fire-and-forget).
        
        This method is designed to run as a background task via asyncio.create_task().
        It handles the LLM-based personality analysis without blocking the main response.
        Any errors are logged but don't affect the user experience.
        
        Args:
            companion_name: Active companion being analyzed
            user_input: User's input text
            assistant_response: Assistant's response text
            turn_count: Current turn number
        """
        try:
            # Small delay to ensure the main response has completed
            # and to avoid overwhelming the LLM API with back-to-back calls
            await asyncio.sleep(1.5)
            
            # Run the actual analysis
            result = await self.personality_engine.analyze_with_llm(
                companion_name,
                user_input,
                assistant_response,
                turn_count,
            )
            
            if result:
                print(f"[PersonalityAnalysis] Background analysis complete for {companion_name}")
            else:
                print(f"[PersonalityAnalysis] Skipped (not turn {self.personality_engine._llm_interval})")
                
        except Exception as e:
            # Fire-and-forget: errors don't propagate, just log them
            print(f"[PersonalityAnalysis] Background analysis failed (non-critical): {e}")
    
    def _init_npc_links(self) -> None:
        """Initialize NPC relationship links."""
        companions = list(self.world.companions.keys())
        for name in companions:
            companion_def = self.world.companions.get(name)
            if companion_def:
                self.personality_engine.initialize_npc_links(
                    name, companions, companion_def.relations
                )
    
    def _find_matching_npc_template(self, description: str) -> Optional[Dict[str, Any]]:
        """Find matching NPC template based on description.
        
        V3.2: Searches npc_templates for a matching character type.
        
        Args:
            description: Italian description of the NPC
            
        Returns:
            Template dict if found, None otherwise
        """
        print(f"[NPC Template] Looking for template matching: '{description}'")
        print(f"[NPC Template] Available templates: {list(self.world.npc_templates.keys()) if self.world and self.world.npc_templates else 'NONE'}")
        
        if not self.world or not self.world.npc_templates:
            print("[NPC Template] No world or no templates available")
            return None
        
        desc_lower = description.lower()
        print(f"[NPC Template] Searching in: {desc_lower}")
        
        # Search for template matches by aliases
        for template_id, template in self.world.npc_templates.items():
            aliases = template.get('aliases', [])
            print(f"[NPC Template] Checking template '{template_id}' with aliases: {aliases}")
            
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in desc_lower:
                    print(f"[NPC Template] ✓ MATCH by alias: '{alias}' in '{desc_lower}'")
                    return template
            
            # Also check if template name is in description
            template_name = template.get('name', '').lower()
            if template_name and template_name in desc_lower:
                print(f"[NPC Template] ✓ MATCH by name: '{template_name}'")
                return template
            
            # Check template id
            if template_id.lower() in desc_lower:
                print(f"[NPC Template] ✓ MATCH by id: '{template_id}'")
                return template
        
        print(f"[NPC Template] ✗ No match found for: '{description}'")
        return None
    
    def _create_npc_from_template(self, name: str, template: Dict[str, Any]) -> str:
        """Create a temporary companion from a predefined template.
        
        V3.2: Creates consistent secondary characters using YAML templates.
        Uses cache to ensure same NPC always appears when encountered again.
        V4.1: Also replaces generic NPC if it exists with the same name.
        
        Args:
            name: Name for this NPC instance (from detection)
            template: Template dict from npc_templates.yaml
            
        Returns:
            Name of the temporary companion
        """
        from luna.core.models import CompanionDefinition
        
        template_id = template.get('id', 'unknown')
        template_name = template.get('name', name)
        
        # V4.1: Check if a generic NPC with the same name already exists
        # If so, we'll replace it with the template version
        generic_name = name.capitalize() if name else template_name
        if generic_name in self.world.companions:
            print(f"[GameEngine] Replacing generic NPC '{generic_name}' with template version")
            del self.world.companions[generic_name]
        
        # V3.2: Check cache - if we've seen this template before, reuse the same NPC
        if template_id in self._npc_template_cache:
            cached_name = self._npc_template_cache[template_id]
            print(f"[GameEngine] Reusing cached NPC: {cached_name} (template: {template_id})")
            # Verify the NPC still exists
            if cached_name in self.world.companions:
                companion = self.world.companions[cached_name]
                bp_check = companion.base_prompt[:50] if companion.base_prompt else "NONE"
                print(f"[GameEngine] Cached NPC base_prompt: {bp_check}...")
                return cached_name
            else:
                print(f"[GameEngine] WARNING: Cached NPC {cached_name} not found in world!")
        
        # Use template values
        base_prompt = template.get('base_prompt', '')
        visual_tags = template.get('visual_tags', [])
        physical_desc = template.get('physical_description', '')
        personality = template.get('personality', '')
        voice_tone = template.get('voice_tone', '')
        
        # Build base personality for LLM
        base_personality = f"{template_name}: {personality}"
        if voice_tone:
            base_personality += f". Tono di voce: {voice_tone}"
        
        # Build wardrobe from template or use default
        wardrobe = {"default": {"description": physical_desc, "sd_prompt": base_prompt}}
        
        # Create the companion
        temp_companion = CompanionDefinition(
            name=template_name,  # Use template name for consistency
            role=template.get('role', 'NPC'),
            base_personality=base_personality,
            base_prompt=base_prompt,
            physical_description=physical_desc,
            visual_tags=visual_tags,
            default_outfit="default",
            wardrobe=wardrobe,
            is_temporary=True,
        )
        
        # Add to world temporarily (using template_id for consistency)
        instance_name = f"npc_{template_id}"
        self.world.companions[instance_name] = temp_companion
        print(f"[GameEngine] Created template NPC: {instance_name} with {len(base_prompt)} char base_prompt")
        
        # Add to affinity system
        if instance_name not in self.state_manager.current.affinity:
            self.state_manager.current.affinity[instance_name] = 0
        
        # V3.2: Cache this NPC for future encounters
        self._npc_template_cache[template_id] = instance_name
        
        print(f"[GameEngine] Created NPC from template: {template_name} ({instance_name})")
        return instance_name
    
    def _create_temporary_companion(self, npc_info: Dict[str, Any]) -> str:
        """Create a temporary companion for a generic NPC interaction.
        
        V3 LOGIC: Determines gender from world hints, uses appropriate base.
        Translates description to English for SD prompt compatibility.
        Works for ANY world (fantasy, modern, sci-fi, etc.).
        
        V3.1: Added visual_tags extraction for persistent NPC appearance.
        V3.2: Added NPC template support for consistent secondary characters.
        
        Args:
            npc_info: Dict with name, description from _detect_generic_npc_interaction
            
        Returns:
            Name of the temporary companion
        """
        from luna.core.models import CompanionDefinition
        from luna.media.builders import NPC_BASE, NPC_MALE_BASE
        
        name = npc_info['name']
        description_it = npc_info['description']
        
        # V3.2: Check if there's a matching template for this NPC type
        template = self._find_matching_npc_template(description_it)
        if template:
            print(f"[GameEngine] Using NPC template: {template.get('id', 'unknown')}")
            return self._create_npc_from_template(name, template)
        
        # Translate to English for SD prompt
        description_en = self._translate_npc_description(description_it)
        
        # V3.1: Extract visual tags for persistent appearance
        visual_tags = self._extract_visual_tags(description_it)
        visual_tags_str = ", ".join(visual_tags) if visual_tags else ""
        
        # V3: Determine gender from world hints or description keywords
        female_hints = set(h.lower() for h in self.world.female_hints) if self.world.female_hints else set()
        male_hints = set(h.lower() for h in self.world.male_hints) if self.world.male_hints else set()
        
        # Add default hints if world doesn't specify
        default_female = {'donna', 'ragazza', 'femmina', 'signora', 'donnina', 'madame', 
                          'amazzona', 'guerriera', 'strega', 'elfa', 'maga', 'sacerdotessa',
                          'segretaria', 'bibliotecaria', 'cameriera', 'infermiera'}
        default_male = {'uomo', 'ragazzo', 'maschio', 'signore', 'signor', 
                        'guerriero', 'mago', 'elfo', 'orco', 'nano', 'ladro', 'chierico',
                        'mercante', 'barista', 'pilota', 'ufficiale', 'professore', 'preside'}
        
        female_hints.update(default_female)
        male_hints.update(default_male)
        
        # Check description for gender hints (using Italian description)
        desc_lower = description_it.lower()
        is_female = any(hint in desc_lower for hint in female_hints)
        is_male = any(hint in desc_lower for hint in male_hints)
        
        # Default to female if unclear (most VN are female-focused)
        if is_female:
            base_prompt = NPC_BASE  # 1girl
            gender_tag = "1girl"
        elif is_male:
            base_prompt = NPC_MALE_BASE  # 1boy
            gender_tag = "1boy"
        else:
            # Default to female NPC base
            base_prompt = NPC_BASE
            gender_tag = "1girl"
        
        # V3.1: Build base prompt with visual tags injected
        # Tags are added with weight to ensure they persist in generation
        if visual_tags:
            # Format: (trait1:1.1), (trait2:1.1), base_description
            weighted_tags = ", ".join([f"({tag}:1.1)" for tag in visual_tags])
            final_base = f"{weighted_tags}, ({description_en}:1.1), {base_prompt}"
        else:
            # V3: Inject translated npc type with weight, add gender tag
            final_base = f"({description_en}:1.2), {base_prompt}"
        
        # Ensure gender tag is present
        if gender_tag not in final_base.lower():
            final_base = f"{gender_tag}, {final_base}"
        
        # V3.1: Build persistent physical description with tags for LLM context
        # This ensures the LLM remembers these traits in dialogue
        physical_desc = description_it
        if visual_tags:
            # Add tags to physical description for LLM context
            tags_it = []
            for tag in visual_tags:
                # Translate back to Italian for LLM context
                tag_it = tag.replace(' hair', '').replace(' eyes', '').replace(' skin', '')
                tags_it.append(tag_it)
            physical_desc = f"{description_it}. CARATTERISTICHE PERSISTENTI: {', '.join(tags_it)}. MAI cambiare questi tratti."
        
        # Create temporary companion with V3-style base_prompt (ENGLISH)
        temp_companion = CompanionDefinition(
            name=name,
            role="NPC",
            base_personality=f"Generic NPC: {description_it}",  # Keep Italian for LLM context
            base_prompt=final_base,  # English for SD with visual tags
            physical_description=physical_desc,  # V3.1: Includes persistent traits reminder
            visual_tags=visual_tags,  # V3.1: Store tags for later use
            default_outfit="default",
            wardrobe={
                "default": {
                    "description": description_it,  # Italian for display
                    "sd_prompt": description_en,    # English for SD
                }
            },
            is_temporary=True,
        )
        
        # Add to world temporarily
        self.world.companions[name] = temp_companion
        
        # Add to affinity system so switch_companion works
        if name not in self.state_manager.current.affinity:
            self.state_manager.current.affinity[name] = 0  # Neutral starting affinity
            print(f"[GameEngine] Added {name} to affinity system")
        
        gender_str = "female" if is_female else ("male" if is_male else "unknown")
        print(f"[GameEngine] Created temporary NPC: {name} ({gender_str}) EN: '{description_en}'")
        return name
    
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
        
        # Affinity changes - NOW CALCULATED BY PYTHON (deterministic)
        # NOT by LLM for more predictable and balanced gameplay
        calculator = get_calculator()
        affinity_result = calculator.calculate(
            user_input=self._last_user_input,  # Need to store this
            companion_name=game_state.active_companion,
            turn_count=game_state.turn_count,
        )
        
        validated["affinity_change"] = {
            game_state.active_companion: affinity_result.delta
        }
        print(f"[Affinity] Python calculated: {affinity_result.delta} ({affinity_result.reason})")
        
        # V3 PATTERN: Outfit can be either:
        # 1. A KEY in wardrobe (es. "casual", "formal") -> Use wardrobe description
        # 2. A FREE DESCRIPTION (es. "wearing red dress") -> Creative fallback
        if updates.current_outfit:
            companion = self.world.companions.get(game_state.active_companion)
            if companion:
                if updates.current_outfit in companion.wardrobe:
                    # Case 1: Valid wardrobe key
                    validated["current_outfit"] = updates.current_outfit
                    print(f"[Validate] Outfit key accepted: {updates.current_outfit}")
                elif " " in updates.current_outfit or len(updates.current_outfit) > 15:
                    # Case 2: Creative description (contains spaces or is long)
                    # Accept as creative outfit - will be used directly as description
                    validated["current_outfit"] = updates.current_outfit
                    print(f"[Validate] Creative outfit accepted: {updates.current_outfit[:50]}...")
                else:
                    print(f"[Validate] Rejected unknown outfit: {updates.current_outfit}")
        
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
        
        # V3 PATTERN: Outfit update
        if "current_outfit" in updates:
            outfit_value = updates["current_outfit"]
            companion = self.world.companions.get(game_state.active_companion)
            
            if companion and outfit_value in companion.wardrobe:
                # Case 1: Valid wardrobe key - set style, description will come from wardrobe
                self.state_manager.set_outfit_style(outfit_value)
                print(f"[Apply] Outfit style set: {outfit_value}")
            else:
                # Case 2: Creative description - set as description directly
                # This allows "wearing a red dress" even if not in wardrobe
                current_outfit = game_state.get_outfit()
                current_outfit.style = "custom"  # Mark as custom
                current_outfit.description = outfit_value  # Use the creative description
                print(f"[Apply] Creative outfit set: {outfit_value[:50]}...")
        
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
        
        # Home invitation accepted - move NPC to player_home
        if updates.get("invite_accepted"):
            companion_name = game_state.active_companion
            print(f"[Apply] {companion_name} accepted invitation to player_home")
            # Set companion location to player_home
            self.state_manager.set_location("player_home")
            # Set flag to indicate companion is at player's home
            self.state_manager.set_flag(f"{companion_name.lower()}_at_player_home", True)
        
        # Photo requested - handle special image generation
        if updates.get("photo_requested"):
            companion_name = game_state.active_companion
            photo_outfit = updates.get("photo_outfit")
            print(f"[Apply] Photo requested from {companion_name}, outfit: {photo_outfit}")
            # Set flag for photo request - will be handled in media generation
            self.state_manager.set_flag("photo_request_pending", True)
            if photo_outfit:
                self.state_manager.set_flag("photo_outfit_description", photo_outfit)
        
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
    
    async def generate_solo_location_image(self, location_id: Optional[str] = None) -> Optional[str]:
        """Generate an image of the current location without any NPC (solo mode).
        
        V4.2: Called by UI when companion leaves due to phase change.
        Uses the existing MovementHandler.get_solo_mode_image_params().
        
        Args:
            location_id: Location to generate image for, or None for current location
            
        Returns:
            Path to generated image, or None if failed
        """
        if self._no_media:
            print("[GameEngine] Solo location image: skipped (media disabled)")
            return None
        
        if not self.media_pipeline or not self.movement_handler:
            return None
        
        game_state = self.state_manager.current
        target_location = location_id or game_state.current_location
        
        if not target_location:
            return None
        
        # Use existing method from MovementHandler
        img_params = self.movement_handler.get_solo_mode_image_params(target_location)
        if not img_params:
            return None
        
        try:
            print(f"[GameEngine] Generating solo location image for {target_location}")
            media_result = await self.media_pipeline.generate_all(
                text=f"Location: {img_params['location_name']}",
                visual_en=img_params["visual_en"],
                tags=img_params["tags"],
                companion_name="_solo_",  # No character
                base_prompt="",  # No LoRAs
                location_id=target_location,
                location_visual_style=img_params["location_visual_style"],
            )
            
            if media_result and media_result.image_path:
                print(f"[GameEngine] Solo location image generated: {media_result.image_path}")
                return media_result.image_path
            
        except Exception as e:
            print(f"[GameEngine] Failed to generate solo location image: {e}")
        
        return None
    
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
    
    def get_pending_quest_choices(self) -> List[dict]:
        """Get quests awaiting player choice.
        
        Returns:
            List of choice data dicts with keys:
            - quest_id, title, description, giver
        """
        return self.quest_engine.get_pending_choices()
    
    async def resolve_quest_choice(self, quest_id: str, accepted: bool) -> Optional[str]:
        """Resolve a pending quest choice.
        
        Args:
            quest_id: Quest being resolved
            accepted: True if player accepted
            
        Returns:
            Quest title if activated, None if declined
        """
        game_state = self.state_manager.current
        
        result = self.quest_engine.resolve_choice(quest_id, accepted, game_state)
        
        if result:
            # Save to database
            async with self.db.session() as db_session:
                await self.db.save_quest_states(
                    game_state.session_id,
                    self.quest_engine.get_all_states(),
                )
            return result.title
        
        return None
    
    # ========================================================================
    # Gameplay Actions API
    # ========================================================================
    
    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Get available gameplay actions for current state.
        
        Returns:
            List of action dictionaries
        """
        if not self.gameplay_manager:
            return []
        
        game_state = self.state_manager.current
        actions = self.gameplay_manager.get_available_actions(game_state)
        return [a.to_dict() for a in actions]
    
    def execute_action(self, action_id: str, target: Optional[str] = None) -> Any:
        """Execute a gameplay action.
        
        Args:
            action_id: Action identifier
            target: Optional target
            
        Returns:
            Gameplay result
        """
        from luna.systems.gameplay_manager import GameplayResult
        
        if not self.gameplay_manager:
            return GameplayResult(
                success=False,
                message="Gameplay manager not available",
            )
        
        game_state = self.state_manager.current
        return self.gameplay_manager.execute_action(action_id, game_state, target)
    
    async def generate_intro(self) -> TurnResult:
        """Generate opening introduction with character image.
        
        V4 Refactor: Delegates to IntroGenerator.
        
        Returns:
            Turn result with intro text and image path
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.intro_generator.generate(self.state_manager.current)
    
    # ===================================================================
    # Outfit Change Image Generation
    # ===================================================================
    
    async def generate_image_after_outfit_change(self) -> Optional[str]:
        """Generate new image after outfit change.
        
        Called by UI after user modifies outfit via buttons.
        Generates image without LLM text generation (quick refresh).
        
        Returns:
            Path to generated image or None
        """
        if not self._initialized:
            return None
        
        if self._no_media:
            print("[GameEngine] Outfit change image: skipped (media disabled)")
            return None
        
        if not self.media_pipeline:
            return None
        
        game_state = self.state_manager.current
        outfit = game_state.get_outfit()
        
        # Build simple visual description from current outfit
        companion_def = self.world.companions.get(game_state.active_companion)
        base_prompt = companion_def.base_prompt if companion_def else None
        
        # Create basic visual description
        visual_desc = f"{game_state.active_companion} wearing {outfit.description}"
        visual_desc += f", standing in {game_state.current_location}"
        
        # Basic tags
        tags = ["medium_shot", "1girl", "solo", "masterpiece", "score_9"]
        
        print(f"[GameEngine] Generating image after outfit change...")
        print(f"[GameEngine] Visual: {visual_desc[:60]}...")
        
        # V4.0: Get location description
        location_id = game_state.current_location
        location_desc = None
        if location_id and self.world:
            loc_def = self.world.locations.get(location_id)
            if loc_def:
                location_desc = loc_def.visual_style if loc_def.visual_style else loc_def.name
        
        try:
            media_result = await self.media_pipeline.generate_all(
                text=f"{game_state.active_companion} shows off her new outfit.",
                visual_en=visual_desc,
                tags=tags,
                companion_name=game_state.active_companion,
                outfit=outfit,
                base_prompt=base_prompt,
                location_id=location_id,  # V4.0: Pass location for visual enforcement
                location_description=location_desc,
                location_visual_style=location_desc,  # V4.1: Pass for solo mode
            )
            
            if media_result and media_result.image_path:
                print(f"[GameEngine] Outfit change image: {media_result.image_path}")
                return media_result.image_path
                
        except Exception as e:
            print(f"[GameEngine] Failed to generate outfit change image: {e}")
        
        return None
    
    def toggle_audio(self) -> bool:
        """Toggle audio on/off.
        
        Returns:
            New audio state (True = enabled)
        """
        if self.media_pipeline:
            return self.media_pipeline.toggle_audio()
        return False
    
    def _create_fallback_response(self, guard_err) -> LLMResponse:
        """Create a fallback response when guardrails validation fails.
        
        Args:
            guard_err: GuardrailsValidationError with error details
            
        Returns:
            Safe LLMResponse
        """
        from luna.core.models import LLMResponse, StateUpdate
        
        game_state = self.state_manager.current
        companion = game_state.active_companion
        location = game_state.current_location
        
        # Build safe fallback text
        fallback_text = (
            f"{companion.title() if companion else 'Qualcuno'} ti guarda in modo strano. "
            "Sembra confusa, come se avesse sentito qualcosa di incomprensibile. "
            "'Scusa, puoi ripetere?' chiede con un'espressione perplessa."
        )
        
        # Build safe visual
        visual_desc = (
            f"{companion if companion else '1girl'}, confused expression, "
            f"{location if location else 'indoor'} background, "
            "head tilt, questioning look"
        )
        
        print(f"[GameEngine] Using fallback response due to: {guard_err.suggestion}")
        
        return LLMResponse(
            text=fallback_text,
            visual_en=visual_desc,
            tags_en=["masterpiece", "detailed", "confused", "questioning"],
            updates=StateUpdate(),  # No state changes in fallback
            provider="guardrails_fallback"
        )
    
    def _detect_farewell(self, user_input: str) -> bool:
        """Detect if player is saying goodbye to current companion.
        
        Args:
            user_input: Player's input text
            
        Returns:
            True if farewell detected
        """
        import re
        
        # V3.1 FIX: Skip empty or very short inputs
        if not user_input or len(user_input.strip()) < 3:
            return False
        
        input_lower = user_input.lower().strip()
        
        # V3.1: More specific farewell patterns to avoid false positives
        farewell_patterns = [
            # Direct goodbyes (require word boundaries)
            r"^(ciao|arrivederci|addio|a presto|a più tardi|ci vediamo|buona giornata|buona serata|buonanotte)$",
            # Goodbye + name/pronoun
            r"\b(ciao|arrivederci|addio)\s+(luna|maria|stella|prof|professoressa|tesoro|amore|cara)\b",
            # Leave expressions
            r"\b(mi congedo|me ne vado|devo andare|scappo|torno a casa|ci sentiamo dopo)\b",
            # Explicit leaving
            r"\b(vado via|me ne torno|faccio tardi|è tardi)\b",
        ]
        
        for pattern in farewell_patterns:
            if re.search(pattern, input_lower):
                print(f"[GameEngine] Farewell detected in: '{user_input[:50]}...'")
                return True
        
        return False
    
    def _ensure_solo_companion(self) -> str:
        """Ensure 'solo' companion exists for when player is alone.
        
        Returns:
            Name of solo companion
        """
        solo_name = "_solo_"
        
        if solo_name not in self.world.companions:
            from luna.core.models import CompanionDefinition
            
            solo_companion = CompanionDefinition(
                name=solo_name,
                role="none",
                base_personality="You are alone. No companion is present.",
                base_prompt="",  # No LoRA
                physical_description="",
                is_temporary=True,  # Skip personality engine
            )
            
            self.world.companions[solo_name] = solo_companion
            print(f"[GameEngine] Created solo companion")
        
        return solo_name


