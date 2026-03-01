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
from typing import Any, Dict, List, Optional

from luna.core.config import get_settings, get_user_prefs
from luna.core.database import get_db_manager
from luna.core.models import GameState, LLMResponse, MovementResponse, QuestInstance, QuestStatus, WorldDefinition
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
from luna.systems.global_events import GlobalEventManager, GlobalEventInstance
from luna.systems.multi_npc import MultiNPCManager
from luna.systems.affinity_calculator import get_calculator


@dataclass
class TurnResult:
    """Result of a game turn."""
    text: str  # Character/Narrator response
    user_input: str = ""  # What the player said (for chat display)
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    
    # Game state updates
    affinity_changes: Dict[str, int] = field(default_factory=dict)
    new_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    
    # Gameplay system results
    gameplay_result: Optional[Any] = None
    available_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Global events
    active_event: Optional[Dict[str, Any]] = None  # Current global event
    new_event_started: bool = False  # True if event just started this turn
    
    # Companion switch info
    switched_companion: bool = False
    previous_companion: Optional[str] = None
    current_companion: Optional[str] = None
    is_temporary_companion: bool = False  # True if current companion is a temporary NPC
    
    # Multi-NPC dialogue
    multi_npc_sequence: Optional[Any] = None  # DialogueSequence if multi-NPC interaction
    multi_npc_image_paths: Optional[List[str]] = None  # Image paths for each turn
    secondary_characters: Optional[List[str]] = None  # For backward compatibility
    
    # Photo request (when player asks for photo from remote NPC)
    is_photo: bool = False  # True if image is a photo requested by player
    
    # Dynamic events (random/daily)
    dynamic_event: Optional[Dict[str, Any]] = None  # Current pending event with choices
    
    # Metadata
    turn_number: int = 0
    provider_used: str = ""
    error: Optional[str] = None


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
        # Lazy import to avoid circular imports
        from luna.media.pipeline import MediaPipeline
        self.media_pipeline = MediaPipeline()
        
        # Multi-NPC System (CONSERVATIVE - enabled but with strict rules)
        self.multi_npc_manager = MultiNPCManager(
            world=self.world,
            personality_engine=None,  # Will be set after personality_engine init
            enabled=True,  # ENABLED - now with conservative triggering rules
        )
        
        # State
        self._initialized = False
        self._session_id: Optional[int] = None
        
        # V3.2: NPC cache for consistent secondary characters
        # Maps template_id -> companion_name to ensure same NPC always appears
        self._npc_template_cache: Dict[str, str] = {}
    
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
        
        # Initialize gameplay manager (lazy import to avoid circular imports)
        from luna.systems.gameplay_manager import GameplayManager
        self.gameplay_manager = GameplayManager(self.world)
        
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
            if session_model and session_model.personality_state:
                try:
                    from luna.systems.personality import PersonalityState
                    personality_data = session_model.personality_state
                    states_list = personality_data.get("states", [])
                    personality_states = [
                        PersonalityState(**state_data) 
                        for state_data in states_list
                    ]
                    self.personality_engine.load_states(personality_states)
                    print(f"[GameEngine] Loaded {len(personality_states)} personality states")
                except Exception as e:
                    print(f"[GameEngine] Error loading personality states: {e}")
        
        # Initialize NPC links
        self._init_npc_links()
        
        # Link personality engine to multi-npc manager
        self.multi_npc_manager.personality_engine = self.personality_engine
        
        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager,
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
        
        game_state = self.state_manager.current
        
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
        # STEP 0a: Check for Movement Intent
        # -------------------------------------------------------------------
        movement_result = self._check_and_handle_movement(user_input)
        if movement_result:
            # Movement was handled, return result
            return TurnResult(
                text=movement_result.transition_text or movement_result.block_description,
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
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
            return TurnResult(
                text=f"Hai salutato {old_companion}. Ora sei da solo.",
                turn_number=game_state.turn_count,
                provider_used="system",
                switched_companion=True,
                previous_companion=old_companion,
                current_companion=solo_name,
            )
        
        # -------------------------------------------------------------------
        # STEP 0c: Auto-switch Companion based on user input
        # -------------------------------------------------------------------
        mentioned_companion = self._detect_companion_in_input(user_input)
        
        if mentioned_companion and mentioned_companion != game_state.active_companion:
            # Switch to the mentioned companion
            success = self.state_manager.switch_companion(mentioned_companion)
            if success:
                switched_companion = True
                self.companion = mentioned_companion  # Update engine's current companion
                print(f"[GameEngine] Auto-switched companion: {old_companion} -> {mentioned_companion}")
        
        # Check for generic NPC interaction if no known companion mentioned
        elif not mentioned_companion:
            generic_npc = self._detect_generic_npc_interaction(user_input)
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
        memory_context = ""
        if self.memory_manager:
            memory_context = self.memory_manager.get_memory_context(
                query=user_input,  # Use user input for targeted retrieval
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
                            correction = guard_err.get_retry_prompt(guard_err)
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
            
            media_task = asyncio.create_task(
                self.media_pipeline.generate_all(
                    text=llm_response.text,
                    visual_en=llm_response.visual_en,
                    tags=llm_response.tags_en,
                    companion_name=game_state.active_companion,
                    outfit=outfit,
                    base_prompt=base_prompt,  # SACRED: Use companion's base prompt from world YAML
                    secondary_characters=secondary_characters,  # Multi-character support
                )
            )
            
            # For now, wait for completion (UI can be made truly async later)
            media_result = await media_task
        
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
            
            # Save global event states
            if self.event_manager:
                event_states_data = list(self.event_manager.to_dict()["active_events"].values())
                await self.db.save_global_event_states(
                    db_session,
                    self._session_id,
                    event_states_data,
                )
            
            # Save StoryDirector state
            if self.story_director:
                sd_data = self.story_director.to_dict()
                await self.db.save_story_director_state(
                    db_session,
                    self._session_id,
                    sd_data.get("current_chapter", ""),
                    sd_data.get("current_beat_index", 0),
                    sd_data.get("completed_beats", []),
                    sd_data.get("beat_history", []),
                )
            
            # Save personality state (to session model)
            if self.personality_engine:
                personality_states = self.personality_engine.get_all_states()
                personality_data = {
                    "states": [state.model_dump() for state in personality_states]
                }
                await self.db.update_session(
                    db_session,
                    self._session_id,
                    personality_state=personality_data,
                )
        
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
        # Note: dynamic_event is passed separately to UI, not appended to text
        
        # -------------------------------------------------------------------
        # Return Result
        # -------------------------------------------------------------------
        completed_quests = [u.quest_id for u in quest_updates if u.quest_completed]
        
        # Check if photo was requested
        is_photo = validated_updates.get("photo_requested", False)
        
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
            switched_companion=switched_companion,
            previous_companion=old_companion if switched_companion else None,
            current_companion=game_state.active_companion,
            is_temporary_companion=is_temporary,
            multi_npc_sequence=multi_npc_sequence,
            multi_npc_image_paths=multi_npc_image_paths if multi_npc_sequence else None,
            is_photo=is_photo,  # Flag indicating this is a requested photo
            dynamic_event=dynamic_event,  # Pending dynamic event with choices
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
                prompt=prompt,
                system_prompt=f"You are {companion_name}. {companion.base_personality[:200]}",
                max_tokens=150,
                temperature=0.8,
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
    
    def _detect_companion_in_input(self, user_input: str) -> Optional[str]:
        """Detect if user is addressing a specific companion.
        
        Checks for:
        1. Companion name (exact match)
        2. Explicit aliases (e.g., "Professoressa" for Luna)
        3. Role-based references (e.g., "la professoressa", "il bidello")
        
        This enables automatic companion switching based on conversation.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Companion name if detected, None otherwise
        """
        input_lower = user_input.lower()
        
        # Priority 1: Check companion names (exact match)
        for name in self.world.companions.keys():
            if name.lower() in input_lower:
                return name
        
        # Priority 2: Check explicit aliases from YAML
        for name, companion in self.world.companions.items():
            aliases = getattr(companion, 'aliases', []) or []
            for alias in aliases:
                if alias.lower() in input_lower:
                    return name
        
        # Priority 3: Check role-based references (CONSERVATIVE)
        # Only trigger if explicitly addressed with article/preposition
        role_patterns_strict = {
            "professoressa": ["professoressa", "prof.", "prof "],
            "insegnante": ["insegnante"],
            "bidella": ["bidella"],
            "studentessa": ["studentessa","ragazza bionda", "alunna"],
            "direttore": ["direttore", "preside"],
        }
        
        for name, companion in self.world.companions.items():
            role = getattr(companion, 'role', '').lower()
            aliases = [a.lower() for a in getattr(companion, 'aliases', [])]
            
            for role_key, patterns in role_patterns_strict.items():
                # Check if role contains the key OR if any alias matches
                role_matches = role_key in role
                alias_matches = any(role_key in alias for alias in aliases)
                
                if role_matches or alias_matches:
                    for pattern in patterns:
                        # Require word boundaries (space, punctuation, start/end)
                        if re.search(rf'(^|[\s\.,;:!?]){re.escape(pattern)}([\s\.,;:!?]|$)', input_lower):
                            return name
        
        return None
    
    def _detect_farewell(self, user_input: str) -> bool:
        """Detect if player is saying goodbye to current companion.
        
        Args:
            user_input: Player's input text
            
        Returns:
            True if farewell detected
        """
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
    
    def _detect_generic_npc_interaction(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Detect if user is interacting with a generic NPC (not a defined companion).
        
        V3 STYLE: Simple keyword matching. Extract the first noun after interaction verbs.
        If it's not a known companion, it's a generic NPC.
        
        Args:
            user_input: Player's input text
            
        Returns:
            Dict with npc info if detected, None otherwise
        """
        input_lower = user_input.lower()
        
        # Get known companions (excluding temporaries)
        known_companions = {
            name.lower() for name, comp in self.world.companions.items()
            if not getattr(comp, 'is_temporary', False)
        }
        for name, companion in self.world.companions.items():
            if not getattr(companion, 'is_temporary', False):
                for alias in getattr(companion, 'aliases', []):
                    known_companions.add(alias.lower())
        
        # V3 STYLE: Find noun after interaction verbs
        # Match verb+prep, then manually extract next non-article word
        # NOTE: Longer alternatives first to avoid matching 'a' before 'alla'
        patterns = [
            r"\b(dico|parlo|chiedo|sussurro|grido)\s+(alla|all'|ad|al|a|con|da|di)",
            r"\b(saluto|incontro)\s+(il|la|lo|l'|i|gli|le|un|una|uno)",
            r"\b(vedo|noto|trovo|guardo|scorgo)\s+(una|uno|un|il|i|gli|la|le|lo|l')?",
            r"\b(accoglie|appare|compare|si avvicina|arriva)\s+(una|uno|un|il|la|lo|l'|i|gli|le)?",
            r"\b(c'e'|c'è|ecco)\s+(una|uno|un|il|la|lo|l'|i|gli|le)",
        ]
        
        articles = {'il', 'la', 'lo', 'l', 'i', 'gli', 'le', 'un', 'una', 'uno', 'a', 'ad', 'al', 'alla', 'con', 'da', 'di', 'all', "all'", 'ad'}
        
        for pattern in patterns:
            match = re.search(pattern, input_lower)
            if match:
                # Get text after the match
                start_pos = match.end()
                remaining = input_lower[start_pos:].strip()
                words = remaining.split()[:5]  # Check first 5 words max

                target = None
                target_idx = -1
                for idx, word in enumerate(words):
                    word_clean = word.strip(".,;:'!?()[]{}").lower()

                    # FIX: Accetta la parola SOLO se è esplicitamente definita nei ruoli NPC!
                    if word_clean in self.NPC_TRANSLATIONS:
                        target = word_clean
                        target_idx = idx
                        break
                
                if not target:
                    continue
                
                # Skip if it's a known companion
                if target in known_companions:
                    return None
                
                # Skip common non-NPC words
                skip_words = {'me', 'te', 'se', 'che', 'mi', 'ti', 'si', 'ma', 'e', 'o', 'in', 'su', 'per', 'tra', 'fra', 'che', 'non', 'mi', 'ti'}
                if target in skip_words:
                    continue
                
                # V3.1: Extract full description - include context after the target word
                # Get up to 10 more words after target for the description
                all_words = remaining.split()
                description_words = [target]
                
                # Stop words that break the description context
                context_breakers = {'che', 'e', 'poi', 'dopo', 'quando', 'mentre', 'se', 'perché', 'perche', 'ma', 'però', 'pero', 'tuttavia'}
                
                for i in range(target_idx + 1, min(target_idx + 12, len(all_words))):
                    word = all_words[i].strip(".,;:'!?()[]{}").lower()
                    # Stop at context breakers (but allow some through if they're part of description)
                    if word in context_breakers and i > target_idx + 5:
                        break
                    # Stop at sentence-ending punctuation in original
                    if any(p in all_words[i] for p in '.;:!?'):
                        description_words.append(all_words[i].strip(".,;:'!?()[]{}"))
                        break
                    description_words.append(word)
                
                full_description = ' '.join(description_words)
                
                return {
                    'name': target.title(),
                    'type': 'generic_npc',
                    'description': full_description,
                }
        
        return None
    
    # Translation mapping for common Italian -> English terms
    NPC_TRANSLATIONS = {
        # People
        'donna': 'woman', 'ragazza': 'girl', 'signora': 'lady', 'femmina': 'female',
        'uomo': 'man', 'ragazzo': 'boy', 'signore': 'gentleman', 'maschio': 'male',
        'persona': 'person',
        
        # Fantasy
        'amazzona': 'amazon warrior', 'guerriera': 'warrior woman', 'guerriero': 'warrior',
        'strega': 'witch', 'maga': 'mage', 'sacerdotessa': 'priestess',
        'elfa': 'elf girl', 'elfo': 'elf', 'orco': 'orc', 'nano': 'dwarf',
        'ladro': 'rogue', 'chierico': 'cleric', 'mago': 'wizard',
        'cavaliere': 'knight', 'paladino': 'paladin', 'ranger': 'ranger',
        'bardo': 'bard', 'druido': 'druid', 'monaco': 'monk',
        'vampira': 'vampire woman', 'vampiro': 'vampire', 'demone': 'demon',
        'angelo': 'angel', 'sirena': 'mermaid', 'centauro': 'centaur',
        'minotauro': 'minotaur', 'goblin': 'goblin', 'troll': 'troll',
        
        # Modern/School
        'segretaria': 'secretary', 'bibliotecaria': 'librarian',
        'cameriera': 'waitress', 'barista': 'bartender', 'infermiera': 'nurse',
        'professoressa': 'teacher', 'professore': 'teacher',
        'studentessa': 'student', 'studente': 'student',
        'preside': 'principal', 'bidella': 'janitor', 'bidello': 'janitor',
        'commesso': 'clerk', 'cassiera': 'cashier', 'cuoca': 'cook', 'chef': 'chef',
        'poliziotta': 'policewoman', 'poliziotto': 'policeman',
        'pompiere': 'firefighter', 'dottoressa': 'doctor', 'dottore': 'doctor',
        
        # Sci-Fi
        'pilota': 'pilot', 'ufficiale': 'officer', 'comandante': 'commander',
        'soldato': 'soldier', 'marine': 'marine', 'cyborg': 'cyborg',
        'androide': 'android', 'aliena': 'alien woman', 'alieno': 'alien',
        'astronauta': 'astronaut', 'mercante': 'merchant', 'contrabbandiere': 'smuggler',
        'cacciatore': 'bounty hunter', 'hacker': 'hacker', 'scienziata': 'scientist',
        'scienziato': 'scientist', 'ingegnere': 'engineer',
        
        # Physical traits
        'capelli': 'hair', 'rossi': 'red', 'biondi': 'blonde', 'neri': 'black',
        'castani': 'brown', 'grigi': 'grey', 'bianchi': 'white',
        'corti': 'short', 'lunghi': 'long', 'ricci': 'curly', 'lisci': 'straight',
        'occhi': 'eyes', 'azzurri': 'blue', 'verdi': 'green', 'azzurri': 'blue',
        'alta': 'tall', 'bassa': 'short', 'magra': 'slim', 'grassa': 'chubby',
        'muscolosa': 'muscular', 'atletica': 'athletic', 'giovane': 'young',
        'vecchia': 'old', 'anziana': 'elderly', 'matura': 'mature',
        
        # Clothing/Appearance
        'vestito': 'dress', 'uniforme': 'uniform', 'armatura': 'armor',
        'abito': 'suit', 'casual': 'casual clothes', 'elegante': 'elegant',
        'sporco': 'dirty', 'pulito': 'clean', 'strappato': 'torn',
        'scollato': 'low-cut', 'aderente': 'tight', 'largo': 'loose',
        
        # Common adjectives
        'bella': 'beautiful', 'brutta': 'ugly', 'carina': 'cute', 'seducente': 'seductive',
        'minacciosa': 'threatening', 'amichevole': 'friendly', 'sospettosa': 'suspicious',
        'stanca': 'tired', 'energica': 'energetic', 'triste': 'sad', 'felice': 'happy',
        'arrabbiata': 'angry', 'spaventata': 'scared', 'coraggiosa': 'brave',
        
        # Locations/Context
        'seduta': 'sitting', 'in piedi': 'standing', 'sdraiata': 'lying down',
        'in sella': 'riding', 'a cavallo': 'on horseback', 'armata': 'armed',
    }
    
    def _translate_npc_description(self, description: str) -> str:
        """Translate NPC description from Italian to English for SD prompt.
        
        Uses simple word-by-word translation with phrase handling.
        
        Args:
            description: Italian description (e.g., "donna dai capelli rossi")
            
        Returns:
            English description (e.g., "woman with red hair")
        """
        if not description:
            return "unknown character"
        
        desc_lower = description.lower()
        result = desc_lower
        
        # Sort by length (longest first) to handle multi-word phrases
        sorted_translations = sorted(
            self.NPC_TRANSLATIONS.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for italian, english in sorted_translations:
            # Word boundary aware replacement
            pattern = r'\b' + re.escape(italian) + r'\b'
            result = re.sub(pattern, english, result, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Capitalize first letter
        return result.title()
    
    def _extract_visual_tags(self, description: str) -> List[str]:
        """Extract persistent visual tags from NPC description.
        
        These tags are used to maintain visual consistency across multiple images.
        
        Args:
            description: Italian description of the NPC
            
        Returns:
            List of visual trait tags (in English for SD)
        """
        tags = []
        desc_lower = description.lower()
        
        # Hair color mapping (Italian -> English SD tags)
        hair_colors = {
            'rossi': 'red hair', 'rosse': 'red hair', 'rosso': 'red hair',
            'biondi': 'blonde hair', 'bionde': 'blonde hair', 'bionda': 'blonde hair', 'biondo': 'blonde hair',
            'neri': 'black hair', 'nere': 'black hair', 'nero': 'black hair',
            'castani': 'brown hair', 'castane': 'brown hair', 'castano': 'brown hair', 'castana': 'brown hair',
            'grigi': 'grey hair', 'grigie': 'grey hair', 'grigio': 'grey hair',
            'bianchi': 'white hair', 'bianche': 'white hair', 'bianco': 'white hair',
            'blu': 'blue hair', 'verdi': 'green hair', 'verde': 'green hair',
            'rosa': 'pink hair', 'viola': 'purple hair', 'arancioni': 'orange hair',
        }
        
        # Hair length/style
        hair_length = {
            'corti': 'short hair', 'corte': 'short hair', 'corto': 'short hair', 'corta': 'short hair',
            'lunghi': 'long hair', 'lunghe': 'long hair', 'lungo': 'long hair', 'lunga': 'long hair',
            'ricci': 'curly hair', 'ricce': 'curly hair', 'riccio': 'curly hair',
            'lisci': 'straight hair', 'lisce': 'straight hair',
            'mosci': 'wavy hair', 'mosce': 'wavy hair',
            'acconciati': 'styled hair',
            'raccolti': 'hair up', 'raccolto': 'hair up', 'raccolta': 'hair up',
            'sciolti': 'hair down', 'sciolto': 'hair down', 'sciolta': 'hair down',
        }
        
        # Body type
        body_types = {
            'paffuta': 'chubby', 'paffuto': 'chubby',
            'grassa': 'fat', 'grasso': 'fat',
            'magra': 'skinny', 'magro': 'skinny',
            'atletica': 'athletic', 'atletico': 'athletic',
            'muscolosa': 'muscular', 'muscoloso': 'muscular',
            'curvy': 'curvy', 'curva': 'curvy',
            'alta': 'tall', 'alto': 'tall',
            'bassa': 'short', 'basso': 'short',
        }
        
        # Eyes
        eye_colors = {
            'occhi azzurri': 'blue eyes',
            'occhi verdi': 'green eyes',
            'occhi marroni': 'brown eyes',
            'occhi neri': 'black eyes',
            'occhi grigi': 'grey eyes',
        }
        
        # Skin
        skin_traits = {
            'pelle chiara': 'pale skin',
            'pelle scura': 'dark skin',
            'abbronzata': 'tanned',
            'pallida': 'pale',
        }
        
        # Extract hair color (prioritize first match)
        for it, en in hair_colors.items():
            if it in desc_lower and en not in tags:
                tags.append(en)
                break  # Only first hair color
        
        # Extract hair length/style (can have multiple)
        for it, en in hair_length.items():
            if it in desc_lower and en not in tags:
                tags.append(en)
                break  # Only first hair style
        
        # Extract body type (first match)
        for it, en in body_types.items():
            if it in desc_lower and en not in tags:
                tags.append(en)
                break
        
        # Extract eye color
        for it, en in eye_colors.items():
            if it in desc_lower and en not in tags:
                tags.append(en)
                break
        
        # Extract skin trait
        for it, en in skin_traits.items():
            if it in desc_lower and en not in tags:
                tags.append(en)
                break
        
        return tags
    
    def _find_matching_npc_template(self, description: str) -> Optional[Dict[str, Any]]:
        """Find matching NPC template based on description.
        
        V3.2: Searches npc_templates for a matching character type.
        
        Args:
            description: Italian description of the NPC
            
        Returns:
            Template dict if found, None otherwise
        """
        if not self.world or not self.world.npc_templates:
            return None
        
        desc_lower = description.lower()
        
        # Search for template matches by aliases
        for template_id, template in self.world.npc_templates.items():
            aliases = template.get('aliases', [])
            for alias in aliases:
                if alias.lower() in desc_lower:
                    return template
            
            # Also check if template name is in description
            template_name = template.get('name', '').lower()
            if template_name and template_name in desc_lower:
                return template
            
            # Check template id
            if template_id.lower() in desc_lower:
                return template
        
        return None
    
    def _create_npc_from_template(self, name: str, template: Dict[str, Any]) -> str:
        """Create a temporary companion from a predefined template.
        
        V3.2: Creates consistent secondary characters using YAML templates.
        Uses cache to ensure same NPC always appears when encountered again.
        
        Args:
            name: Name for this NPC instance
            template: Template dict from npc_templates.yaml
            
        Returns:
            Name of the temporary companion
        """
        from luna.core.models import CompanionDefinition
        
        template_id = template.get('id', 'unknown')
        template_name = template.get('name', name)
        
        # V3.2: Check cache - if we've seen this template before, reuse the same NPC
        if template_id in self._npc_template_cache:
            cached_name = self._npc_template_cache[template_id]
            print(f"[GameEngine] Reusing cached NPC: {cached_name}")
            return cached_name
        
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
            "entra ", "entriamo ", "entro ",
            "uscire ", "uscite ", "esco ", "esci ", "usciamo ",
            "raggiungi ", "raggiungiamo ", "raggiungo ",
            "torniamo ", "torna ", "torno ",
            "vado a ", "vado in ", "vado da ",
            "esco in ", "esco a ", "esco da ",
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
        
        try:
            media_result = await self.media_pipeline.generate_all(
                text=f"{game_state.active_companion} shows off her new outfit.",
                visual_en=visual_desc,
                tags=tags,
                companion_name=game_state.active_companion,
                outfit=outfit,
                base_prompt=base_prompt,
            )
            
            if media_result and media_result.image_path:
                print(f"[GameEngine] Outfit change image: {media_result.image_path}")
                return media_result.image_path
                
        except Exception as e:
            print(f"[GameEngine] Failed to generate outfit change image: {e}")
        
        return None
    
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


