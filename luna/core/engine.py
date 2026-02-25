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
            llm_analysis_interval=3,
        )
        self.story_director = StoryDirector(self.world.narrative_arc)
        self.location_manager: Optional[LocationManager] = None
        self.gameplay_manager: Optional[GameplayManager] = None
        
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
            
            # Initialize outfit for active companion from wardrobe
            companion_def = self.world.companions.get(self.companion)
            if companion_def and companion_def.wardrobe:
                # Get first wardrobe style
                first_style = next(iter(companion_def.wardrobe.keys()))
                from luna.core.models import OutfitState
                wardrobe_def = companion_def.wardrobe[first_style]
                # Handle both string (legacy) and WardrobeDefinition
                if isinstance(wardrobe_def, str):
                    outfit_desc = wardrobe_def
                else:
                    outfit_desc = getattr(wardrobe_def, 'description', first_style)
                
                # Parse description to extract components
                # Simple parsing: look for keywords in the description
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
                    style=first_style,
                    description=outfit_desc,
                    components=components,
                )
                game_state.set_outfit(outfit, self.companion)
                print(f"[GameEngine] Set starting outfit: {first_style} with components: {components}")
        
        # Initialize NPC links for personality
        self._init_npc_links()
        
        # Link personality engine to multi-npc manager
        self.multi_npc_manager.personality_engine = self.personality_engine
        
        # Initialize location manager
        self.location_manager = LocationManager(
            self.world,
            self.state_manager.current,
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
        if not self._initialized:
            await self.initialize()
        
        game_state = self.state_manager.current
        
        # -------------------------------------------------------------------
        # STEP 0d: Check for Dynamic Event (Random/Daily)
        # If there's a pending event, user input is a choice, not normal action
        # -------------------------------------------------------------------
        if self.gameplay_manager and self.gameplay_manager.has_pending_event():
            return await self._process_event_turn(user_input, game_state)
        
        # -------------------------------------------------------------------
        # STEP 0a: Check for Movement Intent
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
        # STEP 0b: Auto-switch Companion based on user input
        # -------------------------------------------------------------------
        mentioned_companion = self._detect_companion_in_input(user_input)
        switched_companion = False
        old_companion = game_state.active_companion
        
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
        # STEP 7b: Check Global Events
        # -------------------------------------------------------------------
        active_event = None
        if self.event_manager:
            new_events = self.event_manager.check_and_activate_events(game_state)
            if new_events:
                active_event = new_events[0]  # Primary event
            else:
                active_event = self.event_manager.get_primary_event()
        
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
            active_companion_def = self.world.companions.get(game_state.active_companion)
            if active_companion_def and outfit:
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
        # STEP 10: LLM Personality Analysis (periodic)
        # -------------------------------------------------------------------
        # Skip LLM personality analysis for temporary NPCs
        if self.personality_engine._use_llm and not is_temporary:
            await self.personality_engine.analyze_with_llm(
                game_state.active_companion,
                user_input,
                llm_response.text,
                game_state.turn_count,
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
        # Build final text (include event if present)
        # -------------------------------------------------------------------
        final_text = llm_response.text
        if dynamic_event:
            choices_text = "\n".join([
                f"{c['index']}. {c['text']}" 
                for c in dynamic_event['choices']
            ])
            final_text += f"\n\n--- EVENTO SPECIALE ---\n\n{dynamic_event['narrative']}\n\nScegli:\n{choices_text}"
        
        # -------------------------------------------------------------------
        # Return Result
        # -------------------------------------------------------------------
        completed_quests = [u.quest_id for u in quest_updates if u.quest_completed]
        
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
            turn_number=game_state.turn_count,
            provider_used=provider_used,
        )
    
    # ========================================================================
    # Dynamic Events Processing
    # ========================================================================
    
    async def _process_event_turn(
        self,
        user_input: str,
        game_state: GameState,
    ) -> TurnResult:
        """Process a turn where player responds to an event.
        
        Args:
            user_input: Player's choice (number or text)
            game_state: Current game state
            
        Returns:
            Turn result
        """
        # Parse choice from input
        choice_index = self._parse_event_choice(user_input)
        
        if choice_index is None:
            # Invalid choice, return event prompt again
            event = self.gameplay_manager.get_pending_event()
            choices_text = "\n".join([
                f"{i+1}. {choice.text}" 
                for i, choice in enumerate(event.choices)
            ])
            return TurnResult(
                text=f"{event.narrative}\n\nScegli:\n{choices_text}\n\n(Inserisci il numero della scelta)",
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
        # Process the choice
        result = self.gameplay_manager.process_event_choice(choice_index, game_state)
        
        # Advance turn
        self.state_manager.advance_turn()
        self.gameplay_manager.on_turn_end(game_state)
        
        # Build response text
        text_parts = [result.narrative]
        if result.followup:
            text_parts.append(result.followup)
        if result.message:
            text_parts.append(result.message)
        
        return TurnResult(
            text="\n\n".join(text_parts),
            turn_number=game_state.turn_count,
            provider_used="system",
            affinity_changes=result.affinity_changes,
        )
    
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
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    def _load_world(self, world_id: str) -> Optional[WorldDefinition]:
        """Load world definition."""
        from luna.systems.world import get_world_loader
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
            "studentessa": ["studentessa", "studente", "alunna", "alunno"],
            "direttore": ["direttore", "preside"],
        }
        
        for name, companion in self.world.companions.items():
            role = getattr(companion, 'role', '').lower()
            
            # Only check if role is defined
            if not role:
                continue
                
            for role_key, patterns in role_patterns_strict.items():
                if role_key in role:
                    for pattern in patterns:
                        # Require word boundaries (space, punctuation, start/end)
                        # Pattern: word at start OR after space/punctuation
                        if re.search(rf'(^|[\s\.,;:!?]){re.escape(pattern)}([\s\.,;:!?]|$)', input_lower):
                            return name
        
        return None
    
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
                for word in words:
                    word_clean = word.strip(".,;:'!?()[]{}").lower()
                    if word_clean and word_clean not in articles and len(word_clean) > 1:
                        target = word_clean
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
                
                return {
                    'name': target.title(),
                    'type': 'generic_npc',
                    'description': target,
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
    
    def _create_temporary_companion(self, npc_info: Dict[str, Any]) -> str:
        """Create a temporary companion for a generic NPC interaction.
        
        V3 LOGIC: Determines gender from world hints, uses appropriate base.
        Translates description to English for SD prompt compatibility.
        Works for ANY world (fantasy, modern, sci-fi, etc.).
        
        Args:
            npc_info: Dict with name, description from _detect_generic_npc_interaction
            
        Returns:
            Name of the temporary companion
        """
        from luna.core.models import CompanionDefinition
        from luna.media.builders import NPC_BASE, NPC_MALE_BASE
        
        name = npc_info['name']
        description_it = npc_info['description']
        
        # Translate to English for SD prompt
        description_en = self._translate_npc_description(description_it)
        
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
        
        # V3: Inject translated npc type with weight, add gender tag
        # Example: "(amazon warrior:1.2), score_9, score_8_up, masterpiece, 1girl, ..."
        final_base = f"({description_en}:1.2), {base_prompt}"
        
        # Ensure gender tag is present
        if gender_tag not in final_base.lower():
            final_base = f"{gender_tag}, {final_base}"
        
        # Create temporary companion with V3-style base_prompt (ENGLISH)
        temp_companion = CompanionDefinition(
            name=name,
            role="NPC",
            base_personality=f"Generic NPC: {description_it}",  # Keep Italian for LLM context
            base_prompt=final_base,  # English for SD
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
        
        # Affinity changes (clamped -5/+5)
        if updates.affinity_change:
            validated["affinity_change"] = {}
            for char, delta in updates.affinity_change.items():
                if char in game_state.affinity:
                    validated["affinity_change"][char] = max(-5, min(5, delta))
        
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
    
    def get_gameplay_status(self) -> Dict[str, Any]:
        """Get status of all gameplay systems.
        
        Returns:
            System status dictionary
        """
        if not self.gameplay_manager:
            return {}
        
        return self.gameplay_manager.get_status_summary()
    
    # ========================================================================
    # Integrated Gameplay API
    # ========================================================================
    
    def buy_item(self, item_id: str, shop_id: str = "default") -> Any:
        """Buy an item from shop (Economy + Inventory)."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.buy_item(item_id, shop_id)
    
    def sell_item(self, item_id: str) -> Any:
        """Sell an item (Inventory + Economy)."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.sell_item(item_id)
    
    def use_skill(self, skill_id: str, target: Optional[str] = None) -> Any:
        """Use a skill (Skills + Combat)."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.use_skill_in_combat(skill_id, target)
    
    def discover_clue(self, clue_id: str) -> Any:
        """Discover a clue."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.discover_clue(clue_id)
    
    def add_reputation(self, faction: str, amount: int, reason: str = "") -> Any:
        """Add reputation with a faction."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.add_reputation(faction, amount, reason)
    
    def start_combat(self, enemy_name: str, enemy_hp: int = 50) -> Any:
        """Start a combat encounter."""
        from luna.systems.gameplay_manager import GameplayResult
        if not self.gameplay_manager:
            return GameplayResult(success=False, message="Gameplay manager not available")
        return self.gameplay_manager.start_combat_encounter(enemy_name, enemy_hp)

    async def generate_intro(self) -> TurnResult:
        """Generate opening introduction with character image.
        
        Creates the initial scene when the game starts:
        - Narrative introduction text
        - Character portrait image
        
        Returns:
            Turn result with intro text and image path
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
        
        # Generate image
        outfit = game_state.get_outfit()
        
        # Get base prompt for active companion (SACRED for visual consistency)
        active_companion_def = self.world.companions.get(game_state.active_companion)
        base_prompt = active_companion_def.base_prompt if active_companion_def else None
        
        media_result = await self.media_pipeline.generate_all(
            text=llm_response.text,
            visual_en=llm_response.visual_en,
            tags=llm_response.tags_en,
            companion_name=game_state.active_companion,
            outfit=outfit,
            base_prompt=base_prompt,  # SACRED: Use companion's base prompt from world YAML
            secondary_characters=None,  # Intro is always single character
        )
        
        # Get available actions for intro
        available_actions = []
        if self.gameplay_manager:
            actions = self.gameplay_manager.get_available_actions(game_state)
            available_actions = [a.to_dict() for a in actions]
        
        return TurnResult(
            text=llm_response.text,
            image_path=media_result.image_path,
            audio_path=media_result.audio_path,
            turn_number=0,
            provider_used=getattr(llm_response, 'provider', 'unknown'),
            available_actions=available_actions,
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
        
        # Handle both enum and string time_of_day
        time_str = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
        sections.extend([
            "",
            f"=== STARTING LOCATION ===",
            f"Location: {game_state.current_location}",
            f"Time: {time_str}",
            "",
            "=== YOUR TASK ===",
            "Write an engaging OPENING SCENE where the player FIRST ENCOUNTERS the main character.",
            "",
            "CRITICAL - FIRST MEETING RULES:",
            "1. This is the VERY FIRST TIME the characters meet",
            "2. The NPC does NOT know the player's name yet",
            "3. The NPC must NOT use the player's name in dialogue",
            "4. The NPC should address the player formally or with generic terms ('you', 'new student', 'stranger')",
            "5. Include a moment of introduction where names would naturally be exchanged",
            "",
            "Set the mood, describe the atmosphere, introduce the character naturally.",
            "",
            "=== VISUAL GENERATION (CRITICAL) ===",
            "The visual_en MUST include the character's BASE PROMPT for image generation:",
            "",
            f"BASE PROMPT for {companion.name if companion else 'character'}:",
            companion.base_prompt if companion else "1girl, solo, detailed",
            "",
            "INSTRUCTIONS:",
            "1. visual_en MUST start with the BASE PROMPT above (contains LoRAs and core features)",
            "2. Add pose, expression, clothing, lighting details AFTER the base prompt",
            "3. NEVER omit the base prompt - it defines the character's visual identity!",
            "",
            "=== OUTPUT FORMAT ===",
            "Respond with valid JSON:",
            "{",
            '  "text": "Opening narrative in Italian (2-3 paragraphs, immersive, set the scene)",',
            '  "visual_en": "BASE_PROMPT_HERE, pose, expression, lighting, background",',
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


# Need to import asyncio for create_task
import asyncio
