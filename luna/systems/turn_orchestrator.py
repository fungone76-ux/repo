"""Turn Orchestrator - Coordinates the entire turn flow.

V4.3 REFACTOR: Main orchestrator extracted from engine.py.
Replicates ALL original engine.py functionality exactly.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from luna.core.models import TurnResult, GameState
from luna.systems.quests import QuestUpdateResult
from luna.systems.remote_communication import RemoteCommunicationHandler, RemoteCommunicationResult
from luna.systems.invitation_manager import InvitationManager
from luna.systems.affinity_calculator import get_calculator

logger = logging.getLogger(__name__)


@dataclass
class PreprocessResult:
    """Result from input preprocessing step."""
    should_stop: bool = False
    stop_reason: Optional[str] = None
    turn_result: Optional[TurnResult] = None
    movement_result: Optional[Any] = None
    farewell_detected: bool = False
    old_companion: Optional[str] = None
    rest_message: Optional[str] = None
    schedule_query_result: Optional[Tuple] = None
    freeze_result: Optional[str] = None


@dataclass 
class TurnSummary:
    """Summary of turn updates."""
    affinity_changes: Dict[str, float] = field(default_factory=dict)
    new_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    quest_updates: List[QuestUpdateResult] = field(default_factory=list)
    photo_requested: bool = False
    story_beat_executed: bool = False
    time_messages: List[str] = field(default_factory=list)


class TurnOrchestrator:
    """Orchestrates the complete turn flow, replicating all original engine.py behavior."""
    
    def __init__(
        self,
        engine: 'GameEngine',
    ) -> None:
        """Initialize orchestrator with reference to main engine.
        
        Args:
            engine: The GameEngine instance with all dependencies
        """
        self.engine = engine
        
        # Cache engine components for easy access
        self.state_manager = engine.state_manager
        self.state_memory = engine.state_memory
        self.movement_handler = engine.movement_handler
        self.personality_engine = engine.personality_engine
        self.outfit_modifier = engine.outfit_modifier
        self.story_director = engine.story_director
        self.quest_engine = engine.quest_engine
        self.prompt_builder = engine.prompt_builder
        self.llm_manager = engine.llm_manager
        self.multi_npc_manager = engine.multi_npc_manager
        self.event_manager = engine.event_manager
        self.time_manager = engine.time_manager
        self.phase_manager = engine.phase_manager
        self.schedule_manager = engine.schedule_manager
        self.gameplay_manager = engine.gameplay_manager
        self.pose_extractor = engine.pose_extractor
        self.npc_detector = engine.npc_detector
        self.activity_system = engine.activity_system
        self.initiative_system = engine.initiative_system
        self.world = engine.world
        self.settings = engine.settings
        self.tracer = engine.tracer
        
        # V4.5: Remote communication handler
        self.remote_comm_handler = RemoteCommunicationHandler(
            world=self.world,
            npc_detector=self.npc_detector,
            schedule_manager=self.schedule_manager
        )
        
        # V4.5: Invitation manager for NPC visits
        self.invitation_manager = InvitationManager(
            state_manager=self.state_manager,
            world=self.world,
            schedule_manager=self.schedule_manager
        )
        
        # Track remote communication state
        self._in_remote_communication = False
        self._remote_communication_target = None
        
        # V4.5: Track pending invitations to player's home
        self._pending_invitation = None  # NPC name invited to player's home
        self._invited_to_home = False  # Whether NPC should arrive at door
        
        # Store last user input for affinity calculation (Python-based)
        self._last_user_input = ""
        
        # Flags
        self._no_media = engine._no_media
        # Note: _pending_time_message and _pending_phase_message are accessed via self.engine
    
    async def execute_turn(self, user_input: str) -> TurnResult:
        """Execute complete turn flow - EXACT replica of original engine.py process_turn.
        
        All 10 steps from original engine.py are preserved:
        1. Dynamic event checking
        2. Movement detection & handling
        3. Companion switching (mentioned/schedule/temporary)
        4. Multi-NPC detection
        5. Personality analysis
        6. StoryDirector check
        7. Quest engine update
        8. LLM generation with retry logic
        9. State updates (affinity, outfit, flags)
        10. Media generation (solo mode handling)
        """
        game_state = self.state_manager.current
        turn_number = game_state.turn_count
        old_companion = game_state.active_companion
        switched_companion = False
        is_temporary = False
        
        # Store for affinity calculation (Python-based, not LLM)
        self._last_user_input = user_input
        
        print(f"\n{'='*60}")
        print(f"[TurnOrchestrator] === TURN {turn_number} ===")
        print(f"[TurnOrchestrator] Input: '{user_input}'")
        print(f"[TurnOrchestrator] Companion: {game_state.active_companion}")
        print(f"[TurnOrchestrator] Location: {game_state.current_location}")
        print(f"{'='*60}\n")
        
        # V4.5: Update outfit based on location and time
        self._update_outfit_for_context(game_state)
        
        self.tracer.start_turn(turn_number, user_input)
        
        # -------------------------------------------------------------------
        # STEP 0: Check for pending dynamic event choice
        # -------------------------------------------------------------------
        pending_event = self._check_pending_event(game_state, user_input)
        if pending_event:
            # Event choice was processed
            return pending_event
        
        # -------------------------------------------------------------------
        # STEP 0a: Check for Movement Intent
        # -------------------------------------------------------------------
        with self.tracer.step_context("Movement Detection", "movement"):
            self.tracer.info(f"Input: '{user_input}'")
            
            movement_result = await self.movement_handler.handle_movement(user_input)
            
            if movement_result:
                self.tracer.actual("movement_success", movement_result.success)
                self.tracer.actual("target_location", movement_result.target_location_id)
                self.tracer.actual("companion_left", movement_result.companion_left_behind)
                
                if not movement_result.success:
                    # Movement failed
                    return TurnResult(
                        text=movement_result.error_message,
                        user_input=user_input,
                        turn_number=game_state.turn_count,
                        provider_used="system",
                    )
                
                # Handle successful movement
                return await self._handle_movement_turn(
                    user_input, game_state, movement_result, old_companion
                )
        
        # -------------------------------------------------------------------
        # STEP 0b: Check for Farewell (player leaving companion)
        # -------------------------------------------------------------------
        farewell_result = await self._check_farewell(user_input, game_state, old_companion)
        if farewell_result:
            return farewell_result
        
        # -------------------------------------------------------------------
        # STEP 0c: Check for Rest/Sleep command
        # -------------------------------------------------------------------
        rest_message = None
        if self.time_manager:
            rest_message = self.time_manager.check_rest_command(user_input)
            if rest_message:
                print(f"[TurnOrchestrator] Rest command detected: {rest_message}")
        
        # -------------------------------------------------------------------
        # STEP 0c2: Check for Freeze/Unfreeze commands
        # -------------------------------------------------------------------
        freeze_result = self._check_freeze_command(user_input)
        if freeze_result:
            return TurnResult(
                text=freeze_result,
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
        # -------------------------------------------------------------------
        # STEP 0d: Check for Schedule query
        # -------------------------------------------------------------------
        schedule_query = self._check_schedule_query(user_input)
        if schedule_query:
            npc_name, location, activity = schedule_query
            return TurnResult(
                text=f"📍 {npc_name} è a {location}. {activity}",
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
            )
        
        # -------------------------------------------------------------------
        # V4.5: Check for Remote Communication (phone/message)
        # -------------------------------------------------------------------
        remote_comm_result = self.remote_comm_handler.detect_remote_communication(
            user_input, game_state.active_companion
        )
        
        # Handle end of remote conversation (farewell)
        if self._in_remote_communication:
            if self.remote_comm_handler.detect_end_of_conversation(user_input):
                print(f"[TurnOrchestrator] End of remote conversation with {self._remote_communication_target}")
                solo_name = self.engine._ensure_solo_companion()
                self.state_manager.switch_companion(solo_name)
                self.engine.companion = solo_name
                self._in_remote_communication = False
                self._remote_communication_target = None
                switched_companion = True
        
        # Handle start of remote communication
        if remote_comm_result.is_remote and remote_comm_result.should_switch:
            target = remote_comm_result.target_npc
            print(f"[TurnOrchestrator] Remote communication: switching to {target}")
            success = self.state_manager.switch_companion(target)
            if success:
                self.engine.companion = target
                self._in_remote_communication = True
                self._remote_communication_target = target
                switched_companion = True
                print(f"[TurnOrchestrator] Now in remote communication with {target}")
        
        # -------------------------------------------------------------------
        # STEP 0e: Auto-switch Companion based on user input
        # -------------------------------------------------------------------
        if not remote_comm_result.is_remote:  # Only if not handled by remote comm
            switched_companion, is_temporary = await self._handle_companion_switch(
                user_input, game_state, old_companion
            )
        
        # -------------------------------------------------------------------
        # STEP 0c: Multi-NPC Check
        # -------------------------------------------------------------------
        multi_npc_sequence, present_npcs = self._check_multi_npc(game_state, user_input)
        
        # -------------------------------------------------------------------
        # STEP 1: Personality Analysis (regex-based, always)
        # -------------------------------------------------------------------
        current_companion_def = self.world.companions.get(game_state.active_companion)
        is_temporary_flag = getattr(current_companion_def, 'is_temporary', False)
        
        personality_update = self.personality_engine.analyze_player_action(
            game_state.active_companion,
            user_input,
            game_state.turn_count,
            is_temporary=is_temporary_flag,
        )
        
        # -------------------------------------------------------------------
        # STEP 1b: Outfit Modifier (deterministic)
        # -------------------------------------------------------------------
        modified, is_major, outfit_desc_it = self.outfit_modifier.process_turn(
            user_input, game_state, current_companion_def
        )
        
        # Handle major outfit change
        if is_major and outfit_desc_it:
            await self.outfit_modifier.apply_major_change(
                game_state, outfit_desc_it, self.llm_manager
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
        quest_context, new_quests, quest_updates = await self._update_quests(game_state, user_input)
        
        # -------------------------------------------------------------------
        # STEP 4: Build System Prompt
        # -------------------------------------------------------------------
        system_prompt = self._build_system_prompt(
            game_state, user_input, story_context, quest_context,
            multi_npc_sequence, old_companion if switched_companion else None,
            is_temporary_flag,
            remote_comm_result  # V4.5: Pass remote communication context
        )
        
        # -------------------------------------------------------------------
        # STEP 5: LLM Generation with Guardrails
        # -------------------------------------------------------------------
        llm_response, provider_used = await self._generate_llm_response(
            system_prompt, user_input, game_state
        )
        
        if llm_response is None:
            return TurnResult(
                text="[Unable to generate valid response after retries]",
                error="Guardrails validation failed",
                turn_number=game_state.turn_count,
            )
        
        # Save messages to memory
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
                print(f"[TurnOrchestrator] Auto-frozen turns: {self.phase_manager._freeze_reason}")
        
        # Save any new fact from response
        if llm_response.updates and llm_response.updates.new_fact:
            await self.state_memory.add_fact(
                text=llm_response.updates.new_fact,
                importance=7,
                source=game_state.active_companion,
            )
        
        # V4.5: Handle invitations to player's home
        # Check if user sent an invitation
        is_invite, invited_npc, arrival_time = self.invitation_manager.detect_invitation_intent(user_input)
        if is_invite and invited_npc:
            # Check if NPC accepted (from LLM response)
            if self.invitation_manager.detect_acceptance(llm_response.text):
                self.invitation_manager.register_invitation(
                    npc_name=invited_npc,
                    current_turn=game_state.turn_count,
                    arrival_time=arrival_time
                )
                print(f"[TurnOrchestrator] {invited_npc} accepted invitation for {arrival_time}")
        
        # Check if any invited NPCs should arrive now
        current_time = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
        arrivals = self.invitation_manager.check_arrivals(
            current_time=current_time,
            player_location=game_state.current_location
        )
        
        arrival_message = ""
        for arrival in arrivals:
            arrival_msg = self.invitation_manager.build_arrival_message(arrival)
            arrival_message += arrival_msg
            print(f"[TurnOrchestrator] {arrival.npc_name} arrived at the door")
        
        if arrivals:
            self.invitation_manager.clear_arrived_invitations()
        
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
        # STEP 7a: Phase Manager
        # -------------------------------------------------------------------
        phase_result = self._handle_phase_manager()
        
        # V4.5: Generate narrative message when companion leaves at phase change
        phase_narrative_message = ""
        if phase_result and phase_result.companion_left:
            old_companion_name = phase_result.old_companion
            new_location = ""
            activity = ""
            
            # CRITICAL: Switch to solo mode immediately
            if old_companion_name:
                solo_name = self.engine._ensure_solo_companion()
                self.state_manager.switch_companion(solo_name)
                game_state.active_companion = solo_name  # Update local reference
                switched_companion = True
                print(f"[TurnOrchestrator] Companion {old_companion_name} left, switched to {solo_name}")
            
            if self.schedule_manager and old_companion_name:
                new_location = self.schedule_manager.get_npc_current_location(old_companion_name) or ""
                # Try to get activity
                try:
                    npc_state = self.schedule_manager.get_npc_state(old_companion_name)
                    if npc_state:
                        activity = getattr(npc_state, 'activity', '')
                except:
                    pass
            
            # Get location display name
            location_name = new_location
            if new_location and self.world:
                loc_def = self.world.locations.get(new_location)
                if loc_def:
                    location_name = loc_def.name
            
            # Build narrative message
            time_display = {
                "Morning": "mattina",
                "Afternoon": "pomeriggio", 
                "Evening": "sera",
                "Night": "notte"
            }
            new_time_str = time_display.get(str(phase_result.new_time), str(phase_result.new_time))
            
            phase_narrative_message = f"\n\n⏰ La campanella suona. È {new_time_str}.\n\n"
            
            if old_companion_name:
                npc_def = self.world.companions.get(old_companion_name)
                article = "la" if npc_def and getattr(npc_def, 'gender', 'female') == 'female' else "il"
                
                phase_narrative_message += f"*{old_companion_name} raccoglie le sue cose.* "
                
                if activity:
                    phase_narrative_message += f'"Devo andare {activity}."\n\n'
                else:
                    phase_narrative_message += f'"Devo andare. Ci vediamo dopo."\n\n'
                
                if location_name:
                    phase_narrative_message += f"[{article.capitalize()} {old_companion_name} è andat{'a' if article == 'la' else 'o'} in: {location_name}]"
                else:
                    phase_narrative_message += f"[{old_companion_name} è andat{'a' if article == 'la' else 'o'} via]"
                
                print(f"[TurnOrchestrator] Phase change narrative: {old_companion_name} left for {new_location}")
        
        # -------------------------------------------------------------------
        # STEP 7b: Time Manager (Deadlines only)
        # -------------------------------------------------------------------
        time_messages = self._handle_time_manager()
        
        # -------------------------------------------------------------------
        # STEP 7b: Check Global Events
        # -------------------------------------------------------------------
        active_event, new_events = self._check_global_events(game_state)
        
        # -------------------------------------------------------------------
        # STEP 7c: Build Dynamic Event Data
        # -------------------------------------------------------------------
        dynamic_event = self._build_dynamic_event_data(game_state)
        
        # -------------------------------------------------------------------
        # STEP 8: Media Generation
        # -------------------------------------------------------------------
        media_result, multi_npc_image_paths = await self._generate_media(
            game_state, llm_response, multi_npc_sequence, present_npcs
        )
        
        # -------------------------------------------------------------------
        # STEP 9: Save State
        # -------------------------------------------------------------------
        await self.state_memory.save_all()
        
        # -------------------------------------------------------------------
        # STEP 10: LLM Personality Analysis (fire and forget)
        # -------------------------------------------------------------------
        if self.personality_engine._use_llm and not is_temporary_flag:
            asyncio.create_task(
                self._run_personality_analysis(
                    game_state.active_companion,
                    user_input,
                    llm_response.text,
                    game_state.turn_count,
                )
            )
        
        # -------------------------------------------------------------------
        # V4.5: Combine phase narrative with arrival message
        combined_narrative = phase_narrative_message + arrival_message
        
        # Build and Return Result
        # -------------------------------------------------------------------
        return self._build_final_result(
            game_state=game_state,
            user_input=user_input,
            llm_response=llm_response,
            media_result=media_result,
            multi_npc_sequence=multi_npc_sequence,
            multi_npc_image_paths=multi_npc_image_paths,
            new_quests=new_quests,
            quest_updates=quest_updates,
            validated_updates=validated_updates,
            active_event=active_event,
            new_events=new_events,
            switched_companion=switched_companion,
            old_companion=old_companion,
            is_temporary=is_temporary_flag,
            phase_result=phase_result,
            rest_message=rest_message,
            time_messages=time_messages,
            provider_used=provider_used,
            arrival_message=combined_narrative,  # V4.5: Phase change + NPC arrival messages
        )
    
    # ====================================================================
    # Helper Methods (replicated from engine.py)
    # ====================================================================
    
    def _check_pending_event(self, game_state: GameState, user_input: str) -> Optional[TurnResult]:
        """Check for and process pending dynamic event choice."""
        if not self.gameplay_manager:
            return None
            
        pending_event = self.gameplay_manager.get_pending_event()
        if pending_event:
            # Check if user input is a valid choice
            choice = self._parse_event_choice(user_input)
            if choice is not None:
                return self.engine._process_event_choice(choice, game_state)
            
            # Check for new event
            if not pending_event:
                new_event = self.gameplay_manager.check_dynamic_event(game_state)
                if new_event:
                    print(f"[TurnOrchestrator] Dynamic event available: {new_event.event_id}")
        
        return None
    
    def _parse_event_choice(self, user_input: str) -> Optional[int]:
        """Parse choice index from user input."""
        user_input = user_input.strip().lower()
        try:
            choice_num = int(user_input)
            return choice_num - 1
        except ValueError:
            pass
        
        # Try to match by text
        event = self.gameplay_manager.get_pending_event() if self.gameplay_manager else None
        if event:
            for i, choice in enumerate(event.choices):
                if choice.text.lower().startswith(user_input[:3]):
                    return i
        return None
    
    async def _handle_movement_turn(
        self,
        user_input: str,
        game_state: GameState,
        movement_result: Any,
        old_companion: str,
    ) -> TurnResult:
        """Handle movement turn with solo mode and schedule-based auto-switch."""
        print(f"[TurnOrchestrator] MOVEMENT: companion_left={movement_result.companion_left_behind}")
        
        if movement_result.companion_left_behind and game_state.active_companion:
            solo_name = self.engine._ensure_solo_companion()
            self.state_manager.switch_companion(solo_name)
            self.engine.companion = solo_name
            print(f"[TurnOrchestrator] Movement left {old_companion} behind, switching to solo")
            
            # Build combined message
            transition_text = movement_result.transition_text or ""
            left_message = movement_result.companion_message or f"{old_companion} rimane indietro."
            combined_text = f"{transition_text}\n\n{left_message}"
            
            # Save user message to memory
            await self.state_memory.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )
            await self.state_memory.save_all()
            
            # Advance turn
            self.state_manager.advance_turn()
            
            # Phase manager
            if self.phase_manager:
                self.phase_manager.on_turn_end()
            
            # Generate solo mode image
            image_path = await self._generate_solo_mode_image(movement_result, combined_text)
            
            # V4.5: Auto-switch only if companion was explicitly invited
            # Check affinity and invitation status
            switched_from_schedule = False
            if self.schedule_manager and old_companion != "_solo_":
                # Check if companion should follow (affinity > 65 AND was invited)
                current_affinity = game_state.affinity.get(old_companion, 0)
                was_invited = self._was_companion_invited(old_companion, game_state.turn_count)
                
                # Check if companion is temporary NPC (no affinity tracking)
                companion_def = self.world.companions.get(old_companion)
                is_temporary_npc = getattr(companion_def, 'is_temporary', False)
                
                if is_temporary_npc:
                    # NPC temporanei non seguono mai (non hanno affinity)
                    print(f"[TurnOrchestrator] {old_companion} is temporary NPC, not following")
                elif current_affinity >= 65 and was_invited:
                    # Companion segue solo se affinity > 65 ed è stato invitato
                    print(f"[TurnOrchestrator] {old_companion} follows (affinity={current_affinity}, invited={was_invited})")
                    self.state_manager.switch_companion(old_companion)
                    self.engine.companion = old_companion
                    solo_name = old_companion
                    switched_from_schedule = True
                    # V4.5: Update outfit for new location
                    self._update_outfit_for_context(game_state)
                    # V4.5: Messaggio narrativo dell'arrivo del companion
                    arrival_message = f"\n\n*Mentre entri in casa, senti suonare il campanello. Aprendo la porta, trovi {old_companion} che ti ha seguito.*"
                    combined_text += arrival_message
                else:
                    print(f"[TurnOrchestrator] {old_companion} stays behind (affinity={current_affinity}, invited={was_invited})")
            
            # Get available actions
            available_actions = []
            if self.gameplay_manager:
                actions = self.gameplay_manager.get_available_actions(game_state)
                available_actions = [a.to_dict() for a in actions]
            
            return TurnResult(
                text=combined_text,
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
                new_location_id=movement_result.target_location_id,
                switched_companion=True or switched_from_schedule,
                previous_companion=old_companion,
                current_companion=solo_name,
                image_path=image_path,
                available_actions=available_actions,
            )
        else:
            # Normal movement
            await self.state_memory.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )
            await self.state_memory.save_all()
            
            self.state_manager.advance_turn()
            
            if self.phase_manager:
                self.phase_manager.on_turn_end()
            
            available_actions = []
            if self.gameplay_manager:
                actions = self.gameplay_manager.get_available_actions(game_state)
                available_actions = [a.to_dict() for a in actions]
            
            return TurnResult(
                text=movement_result.transition_text or "Ti muovi verso la nuova location.",
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
                new_location_id=movement_result.target_location_id,
                available_actions=available_actions,
            )
    
    async def _generate_solo_mode_image(self, movement_result: Any, text: str) -> Optional[str]:
        """Generate solo mode image for movement."""
        if not movement_result.target_location_id:
            return None
        
        img_params = self.movement_handler.get_solo_mode_image_params(
            movement_result.target_location_id
        )
        if not img_params:
            return None
        
        if self._no_media:
            with self.tracer.step_context("Movement Solo Mode Prompt", "media"):
                self.tracer.info(f"Solo mode movement to: {movement_result.target_location_id}")
                print(f"\n{'='*60}")
                print("🖼️  SOLO MODE PROMPT (Media Disabled):")
                print(f"{'='*60}")
                print(f"Location: {movement_result.target_location_id}")
                print(f"{'='*60}\n")
            return None
        
        if not self.engine.media_pipeline:
            return None
        
        try:
            print(f"[TurnOrchestrator] Generating solo mode image for {movement_result.target_location_id}")
            media_result = await self.engine.media_pipeline.generate_all(
                text=text,
                visual_en=img_params["visual_en"],
                tags=img_params["tags"],
                companion_name="_solo_",
                base_prompt="",
                location_id=movement_result.target_location_id,
                location_visual_style=img_params["location_visual_style"],
            )
            return media_result.image_path if media_result else None
        except Exception as e:
            print(f"[TurnOrchestrator] Failed to generate solo image: {e}")
            return None
    
    def _was_companion_invited(self, companion_name: str, current_turn: int) -> bool:
        """Check if companion was explicitly invited to follow within last 5 turns.
        
        V4.5: Companion follows only if explicitly invited via message or chat.
        
        Args:
            companion_name: Name of the companion
            current_turn: Current turn number
            
        Returns:
            True if companion was invited recently
        """
        # Check last 5 messages for invitation patterns
        recent_history = self.state_memory.get_recent_history(limit=10)
        
        invitation_patterns = [
            r'\bvieni\s+(?:con\s+)?me\b',
            r'\bsegui(?:imi)?\b',
            r'\bvenire\s+(?:con\s+)?me\b',
            r'\bvieni\s+a\s+casa\b',
            r'\bti\s+(?:invito|porto)\b',
            r'\bviene\s+a\s+casa\s+mia\b',
            r'\bvieni\s+da\s+me\b',
            r'\bportami\s+a\s+casa\b',
        ]
        
        for msg in recent_history:
            # Only check user messages
            if msg.role != "user":
                continue
            
            # Check if message mentions the companion
            if companion_name.lower() not in msg.content.lower():
                continue
            
            # Check for invitation patterns
            msg_lower = msg.content.lower()
            for pattern in invitation_patterns:
                if re.search(pattern, msg_lower):
                    print(f"[TurnOrchestrator] Found invitation for {companion_name}: '{msg.content[:50]}...'")
                    return True
        
        return False
    
    async def _check_farewell(
        self,
        user_input: str,
        game_state: GameState,
        old_companion: str,
    ) -> Optional[TurnResult]:
        """Check for and handle farewell command."""
        is_farewell = self.engine._detect_farewell(user_input)
        
        if is_farewell and game_state.active_companion:
            solo_name = self.engine._ensure_solo_companion()
            success = self.state_manager.switch_companion(solo_name)
            if success:
                self.engine.companion = solo_name
                print(f"[TurnOrchestrator] Farewell detected: {old_companion} -> solo mode")
            
            await self.state_memory.add_message(
                role="user",
                content=user_input,
                turn_number=game_state.turn_count,
            )
            await self.state_memory.save_all()
            
            self.state_manager.advance_turn()
            
            if self.phase_manager:
                self.phase_manager.on_turn_end()
            
            return TurnResult(
                text=f"Hai salutato {old_companion}. Ora sei da solo.",
                user_input=user_input,
                turn_number=game_state.turn_count,
                provider_used="system",
                switched_companion=True,
                previous_companion=old_companion,
                current_companion=solo_name,
                new_location_id=game_state.current_location,
            )
        
        return None
    
    def _check_freeze_command(self, user_input: str) -> Optional[str]:
        """Check for freeze/unfreeze commands."""
        if not self.phase_manager:
            return None
        
        user_lower = user_input.strip().lower()
        
        # Freeze patterns
        freeze_patterns = [
            "congela il tempo", "ferma il tempo", "pausa tempo",
            "freeze time", "stop time", "pause time",
        ]
        for pattern in freeze_patterns:
            if pattern in user_lower:
                self.phase_manager.freeze_turns("manual")
                return "⏸️ Tempo congelato. Il turno non avanzerà automaticamente."
        
        # Unfreeze patterns
        unfreeze_patterns = [
            "scongela il tempo", "riprendi tempo", "avvia tempo",
            "unfreeze time", "resume time", "start time",
        ]
        for pattern in unfreeze_patterns:
            if pattern in user_lower:
                self.phase_manager.unfreeze_turns()
                return "▶️ Tempo ripreso. Il turno avanzerà normalmente."
        
        return None
    
    def _check_schedule_query(self, user_input: str) -> Optional[Tuple[str, str, str]]:
        """Check for schedule query commands."""
        if not self.schedule_manager:
            return None
        
        user_lower = user_input.lower()
        
        # Pattern: "dove è X?", "trova X", "routine di X"
        query_patterns = [
            r"dove (?:è|e|sono) (\w+)",
            r"trova (\w+)",
            r"routine di (\w+)",
            r"schedul[ea] di (\w+)",
            r"dove si trova (\w+)",
        ]
        
        import re
        for pattern in query_patterns:
            match = re.search(pattern, user_lower)
            if match:
                npc_name = match.group(1).capitalize()
                # Check if valid NPC
                if npc_name in self.world.companions:
                    location, activity = self.schedule_manager.get_current_activity(npc_name)
                    return (npc_name, location, activity)
        
        return None
    
    async def _handle_companion_switch(
        self,
        user_input: str,
        game_state: GameState,
        old_companion: str,
    ) -> Tuple[bool, bool]:
        """Handle companion switching based on user input.
        
        Returns:
            Tuple of (switched, is_temporary)
        """
        mentioned = self.npc_detector.detect_companion_in_input(user_input)
        print(f"[TurnOrchestrator] Mentioned companion: '{mentioned}'")
        
        if mentioned and mentioned != game_state.active_companion:
            success = self.state_manager.switch_companion(mentioned)
            if success:
                self.engine.companion = mentioned
                print(f"[TurnOrchestrator] Auto-switched: {old_companion} -> {mentioned}")
                return True, False
        
        # Check for generic NPC
        if not mentioned:
            generic_npc = self.npc_detector.detect_generic_npc_interaction(user_input)
            if generic_npc:
                temp_name = self.engine._create_temporary_companion(generic_npc)
                
                # Initialize outfit
                from luna.core.models import OutfitState
                temp_companion = self.world.companions.get(temp_name)
                if temp_companion:
                    outfit = OutfitState(
                        style="default",
                        description=generic_npc.get('description', ''),
                    )
                    game_state.companion_outfits[temp_name] = outfit
                
                success = self.state_manager.switch_companion(temp_name)
                if success:
                    self.engine.companion = temp_name
                    print(f"[TurnOrchestrator] Auto-switched to temp: {old_companion} -> {temp_name}")
                    return True, True
        
        return False, False
    
    def _check_multi_npc(self, game_state: GameState, user_input: str) -> Tuple[Optional[Any], List[str]]:
        """Check for multi-NPC interactions.
        
        Returns:
            Tuple of (multi_npc_sequence, present_npcs)
        """
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
                print(f"[TurnOrchestrator] Multi-NPC sequence: {len(multi_npc_sequence.turns)} turns")
                return multi_npc_sequence, present_npcs
        
        return None, present_npcs
    
    async def _update_quests(
        self,
        game_state: GameState,
        user_input: str,
    ) -> Tuple[str, List[str], List[QuestUpdateResult]]:
        """Update quest engine and return context.
        
        Returns:
            Tuple of (quest_context, new_quests, quest_updates)
        """
        quest_context = ""
        new_quests: List[str] = []
        quest_updates: List[QuestUpdateResult] = []
        
        # Check activations
        activated = self.quest_engine.check_activations(game_state)
        
        auto_quests = []
        choice_quests = []
        
        for quest_id in activated:
            if quest_id.startswith("CHOICE:"):
                choice_quests.append(quest_id.replace("CHOICE:", ""))
            else:
                auto_quests.append(quest_id)
        
        if auto_quests:
            print(f"[TurnOrchestrator] Quests auto-activated: {auto_quests}")
        if choice_quests:
            print(f"[TurnOrchestrator] Quests awaiting choice: {choice_quests}")
        
        # Activate auto-quests
        for quest_id in auto_quests:
            from luna.core.database import DatabaseManager
            async with self.engine.db.session() as db_session:
                result = self.quest_engine.activate_quest(quest_id, game_state)
                if result:
                    new_quests.append(result.title)
                    quest_context += f"\n{result.narrative_context}"
        
        # Add choice quests to pending
        for quest_id in choice_quests:
            self.quest_engine.add_pending_choice(quest_id, game_state)
        
        # Process active quests
        for quest_id in self.quest_engine.get_active_quests():
            result = self.quest_engine.process_turn(quest_id, game_state, user_input)
            if result:
                quest_updates.append(result)
                quest_context += f"\n{result.narrative_context}"
        
        return quest_context, new_quests, quest_updates
    
    def _build_system_prompt(
        self,
        game_state: GameState,
        user_input: str,
        story_context: str,
        quest_context: str,
        multi_npc_sequence: Optional[Any],
        switched_from: Optional[str],
        is_temporary: bool,
        remote_comm_result: Optional[RemoteCommunicationResult] = None,
    ) -> str:
        """Build complete system prompt for LLM."""
        # Get memory context
        memory_context = self.state_memory.get_memory_context(
            query=user_input,
            max_facts=self.settings.memory_max_context_facts,
            min_importance=self.settings.memory_min_importance,
        )
        
        # V4.5: Add remote communication context if active
        remote_context = ""
        if remote_comm_result and remote_comm_result.is_remote:
            remote_context = self.remote_comm_handler.build_remote_context(
                target_npc=remote_comm_result.target_npc or game_state.active_companion,
                player_location=game_state.current_location,
                player_input=user_input,
                game_state=game_state
            )
        
        # Add multi-NPC context
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
        
        # Extract forced poses
        forced_poses = None
        if self.pose_extractor.has_explicit_pose(user_input):
            forced_poses = self.pose_extractor.get_forced_visual_description(user_input)
            if forced_poses:
                print(f"[TurnOrchestrator] Forced poses: {forced_poses}")
        
        # Update activity system
        if self.activity_system:
            time_str = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
            self.activity_system.update_activity(
                npc_name=game_state.active_companion,
                time_of_day=time_str,
                current_turn=game_state.turn_count
            )
        
        # Build base prompt
        system_prompt = self.prompt_builder.build_system_prompt(
            game_state=game_state,
            personality_engine=self.personality_engine,
            story_context=story_context,
            quest_context=quest_context,
            memory_context=memory_context,
            location_manager=self.engine.location_manager,
            event_manager=self.event_manager,
            multi_npc_context=multi_npc_context,
            switched_from=switched_from,
            is_temporary=is_temporary,
            forced_poses=forced_poses,
            activity_system=self.activity_system,
            initiative_system=self.initiative_system,
        )
        
        # Add schedule context
        if self.schedule_manager:
            schedule_context = self.schedule_manager.build_schedule_context(
                game_state.active_companion
            )
            if schedule_context:
                system_prompt += f"\n\n=== CURRENT SITUATION ===\n{schedule_context}\n"
        
        # V4.5: Add remote communication context if present
        if remote_context:
            system_prompt += remote_context
        
        return system_prompt
    
    async def _generate_llm_response(
        self,
        system_prompt: str,
        user_input: str,
        game_state: GameState,
    ) -> Tuple[Optional[Any], str]:
        """Generate LLM response with guardrails and retry logic."""
        # Build history
        history = []
        recent_msgs = self.state_memory.get_recent_history(limit=20)
        for msg in recent_msgs:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        max_retries = 2
        current_retry = 0
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
                    return llm_response, provider_used
                    
                except Exception as guard_err:
                    from luna.ai.guardrails import GuardrailsValidationError
                    if isinstance(guard_err, GuardrailsValidationError):
                        print(f"[Guardrails] Validation failed (attempt {current_retry + 1}): {guard_err.suggestion}")
                        
                        if current_retry < max_retries:
                            from luna.ai.guardrails import ResponseGuardrails
                            correction = ResponseGuardrails.get_retry_prompt(guard_err)
                            system_prompt += correction
                            print(f"[Guardrails] Retrying with correction...")
                        else:
                            print(f"[Guardrails] Max retries reached, using fallback")
                            llm_response = self.engine._create_fallback_response(guard_err)
                            return llm_response, provider_used
                    else:
                        raise
                    
            except Exception as e:
                print(f"[TurnOrchestrator] LLM generation failed: {e}")
                if current_retry >= max_retries:
                    return None, provider_used
            
            current_retry += 1
        
        return None, provider_used
    
    def _validate_updates(self, updates: Any, game_state: GameState) -> Dict[str, Any]:
        """Validate and normalize updates from LLM response.
        
        V4.5: Affinity is calculated by Python (deterministic), not LLM.
        """
        result = {}
        
        # V4.5 FIX: Affinity changes - CALCULATED BY PYTHON (deterministic)
        # NOT by LLM for more predictable and balanced gameplay
        calculator = get_calculator()
        affinity_result = calculator.calculate(
            user_input=self._last_user_input,
            companion_name=game_state.active_companion,
            turn_count=game_state.turn_count,
        )
        
        result['affinity_change'] = {
            game_state.active_companion: affinity_result.delta
        }
        print(f"[Affinity] Python calculated: {affinity_result.delta} ({affinity_result.reason})")
        
        # Validate outfit changes
        if updates and hasattr(updates, 'outfit_change') and updates.outfit_change:
            result['outfit_change'] = updates.outfit_change
        
        # Validate new fact
        if updates and hasattr(updates, 'new_fact') and updates.new_fact:
            result['new_fact'] = updates.new_fact[:500]  # Limit length
        
        # Validate photo request
        if updates and hasattr(updates, 'photo_requested'):
            result['photo_requested'] = bool(updates.photo_requested)
        
        return result
    
    def _apply_updates(self, validated_updates: Dict[str, Any], game_state: GameState) -> None:
        """Apply validated updates to game state."""
        # Apply affinity changes
        if 'affinity_change' in validated_updates:
            for npc, delta in validated_updates['affinity_change'].items():
                if npc in game_state.affinity:
                    game_state.affinity[npc] += delta
                    # Clamp
                    game_state.affinity[npc] = max(0, min(100, game_state.affinity[npc]))
        
        # Outfit changes handled by outfit_modifier
    
    def _handle_phase_manager(self) -> Optional[Any]:
        """Handle phase manager update."""
        with self.tracer.step_context("Phase Manager", "phase"):
            if not self.phase_manager:
                self.tracer.critical_alert("PhaseManager Missing", "phase_manager is None!")
                return None
            
            turns_before = self.phase_manager._turns_in_phase
            self.tracer.expect("turns_incremented", turns_before + 1)
            
            phase_result = self.phase_manager.on_turn_end()
            
            turns_after = self.phase_manager._turns_in_phase
            self.tracer.actual("turns_incremented", turns_after)
            self.tracer.actual("is_frozen", self.phase_manager.is_frozen)
            
            if phase_result:
                from luna.core.debug_tracer import CheckStatus
                self.tracer.check("phase_changed", True, True, CheckStatus.PASS,
                               f"{phase_result.old_time} -> {phase_result.new_time}")
                if self.time_manager:
                    self.time_manager._turns_since_last_advance = 0
            else:
                self.tracer.info(f"No phase change yet (turn {turns_after}/8)")
            
            return phase_result
    
    def _handle_time_manager(self) -> List[str]:
        """Handle time manager (deadlines only)."""
        time_messages = []
        if self.time_manager:
            deadline_messages = self.time_manager.check_deadlines()
            time_messages.extend(deadline_messages)
        return time_messages
    
    def _update_outfit_for_context(self, game_state: GameState) -> None:
        """Update companion outfit based on location and time of day.
        
        V4.5: Automatically adapts outfit to location context:
        - School/office locations -> teacher_suit/professional/uniform
        - Gym/sports locations -> athletic/gym_teacher/cheerleader
        - Home locations -> casual/loungewear/home/pajamas
        - Night time -> nightwear/pajamas
        
        Supports Luna (teacher), Stella (student), Maria (cleaning), and any NPC with wardrobe.
        """
        companion = game_state.active_companion
        if not companion or companion == "_solo_":
            return
        
        location = game_state.current_location
        time_of_day = game_state.time_of_day
        time_str = time_of_day.value if hasattr(time_of_day, 'value') else str(time_of_day)
        
        # Get companion definition
        companion_def = self.world.companions.get(companion)
        if not companion_def or not companion_def.wardrobe:
            return
        
        # Determine appropriate outfit based on location and time
        target_outfit = None
        location_lower = location.lower()
        wardrobe = companion_def.wardrobe
        
        # Night time at home -> nightwear/pajamas
        if time_str == "Night" and ("home" in location_lower or "casa" in location_lower):
            target_outfit = (
                "pajamas" if "pajamas" in wardrobe else
                "nightwear" if "nightwear" in wardrobe else
                "home" if "home" in wardrobe else
                None
            )
        
        # Gym/sports locations -> athletic/gym/cheerleader
        if target_outfit is None and any(x in location_lower for x in ["gym", "palestra", "sport", "field", "court"]):
            target_outfit = (
                "gym_teacher" if "gym_teacher" in wardrobe else
                "cheerleader" if "cheerleader" in wardrobe else
                "athletic" if "athletic" in wardrobe else
                "sportswear" if "sportswear" in wardrobe else
                None
            )
        
        # Pool/beach -> swimsuit
        if target_outfit is None and any(x in location_lower for x in ["pool", "piscina", "beach", "spiaggia"]):
            target_outfit = "swimsuit" if "swimsuit" in wardrobe else None
        
        # School/office/classroom locations -> uniform/professional/teacher/work
        if target_outfit is None and any(x in location_lower for x in ["school", "office", "classroom", "aula", "ufficio", "classe"]):
            target_outfit = (
                "uniform_mod" if "uniform_mod" in wardrobe else
                "teacher_suit" if "teacher_suit" in wardrobe else
                "cleaning_uniform" if "cleaning_uniform" in wardrobe else
                "professional" if "professional" in wardrobe else
                None
            )
        
        # Home locations (not night) -> casual/home/loungewear
        if target_outfit is None and ("home" in location_lower or "casa" in location_lower):
            target_outfit = (
                "home" if "home" in wardrobe else
                "casual" if "casual" in wardrobe else
                "casual_teacher" if "casual_teacher" in wardrobe else
                "loungewear" if "loungewear" in wardrobe else
                None
            )
        
        # Default -> use schedule outfit if available
        if target_outfit is None and self.schedule_manager:
            schedule = self.schedule_manager._schedules.get(companion)
            if schedule:
                entry = schedule.get_current(time_of_day)
                if entry and entry.outfit:
                    schedule_outfit = entry.outfit
                    # Map schedule outfit names to wardrobe names
                    outfit_mapping = {
                        "teacher_formal": "teacher_suit",
                        "teacher_strict": "strict_teacher",
                    }
                    # Apply mapping if needed
                    if schedule_outfit in outfit_mapping:
                        schedule_outfit = outfit_mapping[schedule_outfit]
                    # Check if mapped outfit exists in wardrobe
                    if schedule_outfit in companion_def.wardrobe:
                        target_outfit = schedule_outfit
        
        # Apply outfit if determined and different from current
        if target_outfit:
            current_outfit = game_state.get_outfit(companion)
            if current_outfit.style != target_outfit:
                print(f"[TurnOrchestrator] Outfit change for {companion}: {current_outfit.style} -> {target_outfit} (location: {location}, time: {time_str})")
                wardrobe_def = companion_def.wardrobe[target_outfit]
                from luna.core.models import OutfitState
                if isinstance(wardrobe_def, str):
                    new_outfit = OutfitState(style=target_outfit, description=wardrobe_def)
                else:
                    new_outfit = OutfitState(
                        style=target_outfit,
                        description=getattr(wardrobe_def, 'sd_prompt', '') or getattr(wardrobe_def, 'description', target_outfit)
                    )
                game_state.set_outfit(new_outfit, companion)
    
    def _check_global_events(self, game_state: GameState) -> Tuple[Optional[Any], List[Any]]:
        """Check and activate global events.
        
        Returns:
            Tuple of (active_event, new_events)
        """
        active_event = None
        new_events = []
        
        if self.event_manager:
            new_events = self.event_manager.check_and_activate_events(game_state)
            if new_events:
                active_event = new_events[0]
                print(f"[TurnOrchestrator] Global event activated: {active_event.event_id}")
            else:
                active_event = self.event_manager.get_primary_event()
        
        return active_event, new_events
    
    def _build_dynamic_event_data(self, game_state: GameState) -> Optional[Dict]:
        """Build dynamic event data if pending."""
        if not self.gameplay_manager:
            return None
        
        pending_event = self.gameplay_manager.get_pending_event()
        if pending_event:
            return {
                "event_id": pending_event.event_id,
                "event_type": pending_event.event_type.value if hasattr(pending_event.event_type, 'value') else str(pending_event.event_type),
                "narrative": pending_event.narrative,
                "choices": [
                    {"text": c.text, "index": i+1}
                    for i, c in enumerate(pending_event.choices)
                ],
            }
        return None
    
    async def _generate_media(
        self,
        game_state: GameState,
        llm_response: Any,
        multi_npc_sequence: Optional[Any],
        present_npcs: List[str],
    ) -> Tuple[Optional[Any], List[str]]:
        """Generate media (images/video) for the turn."""
        media_result = None
        multi_npc_image_paths = []
        
        if multi_npc_sequence:
            # Multi-NPC sequence
            multi_npc_image_paths = await self._generate_multi_npc_media(
                game_state, llm_response, multi_npc_sequence, present_npcs
            )
            first_image = multi_npc_image_paths[0] if multi_npc_image_paths else None
            from luna.media.pipeline import MediaResult
            media_result = MediaResult(success=True, image_path=first_image)
        else:
            # Standard single image
            # V4.5: For remote communication, use target's location for image
            effective_location = None
            if self._in_remote_communication and self._remote_communication_target:
                # Use remote_comm_handler to get location from companion.schedule
                visual_context = self.remote_comm_handler.get_npc_visual_context(
                    self._remote_communication_target, game_state
                )
                effective_location = visual_context.get('location')
                print(f"[MediaGen] Remote comm: using {self._remote_communication_target}'s location: {effective_location}")
            
            media_result = await self._generate_standard_media(
                game_state, llm_response, effective_location
            )
        
        return media_result, multi_npc_image_paths
    
    async def _generate_multi_npc_media(
        self,
        game_state: GameState,
        llm_response: Any,
        multi_npc_sequence: Any,
        present_npcs: List[str],
    ) -> List[str]:
        """Generate multi-NPC image sequence."""
        print(f"[TurnOrchestrator] Generating Multi-NPC image sequence...")
        
        if self._no_media:
            with self.tracer.step_context("Multi-NPC Media", "media"):
                self.tracer.info("Multi-NPC sequence skipped (media disabled)")
                self.tracer.info(f"Would generate {len(multi_npc_sequence.turns)} images")
            return []
        
        if not self.engine.media_pipeline:
            print("[TurnOrchestrator] Multi-NPC: No media pipeline available!")
            return []
        
        # Prepare turn data
        sequence_turns = []
        for turn in multi_npc_sequence.turns:
            speaker_type_val = turn.speaker_type.value if hasattr(turn.speaker_type, 'value') else str(turn.speaker_type)
            if speaker_type_val == "PLAYER":
                continue
            
            characters = self.multi_npc_manager.prepare_characters_for_builder(
                turn,
                present_npcs + [game_state.active_companion],
                {name: game_state.get_outfit(name) for name in present_npcs + [game_state.active_companion]}
            )
            
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
        
        return await self.engine.media_pipeline.generate_multi_npc_sequence(
            sequence_turns,
            on_image_ready=None,
        )
    
    async def _generate_standard_media(
        self,
        game_state: GameState,
        llm_response: Any,
        effective_location: Optional[str] = None,
    ) -> Optional[Any]:
        """Generate standard single image."""
        outfit = game_state.get_outfit()
        active_companion_def = self.world.companions.get(game_state.active_companion)
        
        # Use consistent wardrobe description
        if active_companion_def and outfit:
            has_custom_components = bool(outfit.components and len(outfit.components) > 0)
            
            if not has_custom_components:
                wardrobe_style = outfit.style
                if active_companion_def.wardrobe and wardrobe_style in active_companion_def.wardrobe:
                    wardrobe_def = active_companion_def.wardrobe[wardrobe_style]
                    if isinstance(wardrobe_def, str):
                        consistent_desc = wardrobe_def
                    else:
                        consistent_desc = getattr(wardrobe_def, 'sd_prompt', None) or \
                                         getattr(wardrobe_def, 'description', wardrobe_style)
                    outfit.description = consistent_desc
        
        base_prompt = active_companion_def.base_prompt if active_companion_def else None
        
        # Build secondary characters list
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
        
        # Get location description
        # V4.5: Use effective_location for remote communication, otherwise current location
        location_id = effective_location or game_state.current_location
        location_desc = None
        if location_id and self.world:
            loc_def = self.world.locations.get(location_id)
            if loc_def:
                location_desc = loc_def.visual_style if loc_def.visual_style else loc_def.name
        
        # Log prompt if media disabled
        if self._no_media:
            with self.tracer.step_context("Media Prompt", "media"):
                self.tracer.info("Media generation disabled - logging prompt")
                self.tracer.info(f"Companion: {game_state.active_companion}")
                self.tracer.info(f"Outfit: {outfit}")
                self.tracer.info(f"Base prompt: {base_prompt[:80] if base_prompt else 'None'}...")
                self.tracer.info(f"Visual EN: {llm_response.visual_en}")
                self.tracer.info(f"Tags: {llm_response.tags_en}")
                actual_location = effective_location or game_state.current_location
                self.tracer.info(f"Location: {actual_location} - {location_desc}")
            return None
        
        if not self.engine.media_pipeline:
            self.tracer.warning("No media pipeline available!")
            return None
        
        # V4.5: For remote communication, override visual_en to match NPC's actual location
        visual_en = llm_response.visual_en
        if self._in_remote_communication and effective_location and location_desc:
            # Build context-appropriate visual description
            remote_visual = f"{game_state.active_companion} in {location_desc}, {outfit.description if outfit else 'casual outfit'}"
            # Use remote visual if the LLM's visual_en doesn't match the location
            if location_id and location_id.lower() not in (visual_en or '').lower():
                print(f"[MediaGen] Overriding visual_en for remote comm: '{visual_en}' -> '{remote_visual}'")
                visual_en = remote_visual
        
        # Generate media
        media_task = asyncio.create_task(
            self.engine.media_pipeline.generate_all(
                text=llm_response.text,
                visual_en=visual_en,
                tags=llm_response.tags_en,
                companion_name=game_state.active_companion,
                outfit=outfit,
                base_prompt=base_prompt,
                secondary_characters=secondary_characters,
                location_id=location_id,
                location_description=location_desc,
                location_visual_style=location_desc,
            )
        )
        
        return await media_task
    
    async def _run_personality_analysis(
        self,
        companion: str,
        user_input: str,
        response_text: str,
        turn_number: int,
    ) -> None:
        """Run LLM personality analysis (fire and forget)."""
        try:
            await self.personality_engine.analyze_with_llm(
                companion, user_input, response_text, turn_number
            )
        except Exception as e:
            print(f"[TurnOrchestrator] Personality analysis failed: {e}")
    
    def _build_final_result(
        self,
        game_state: GameState,
        user_input: str,
        llm_response: Any,
        media_result: Optional[Any],
        multi_npc_sequence: Optional[Any],
        multi_npc_image_paths: List[str],
        new_quests: List[str],
        quest_updates: List[QuestUpdateResult],
        validated_updates: Dict[str, Any],
        active_event: Optional[Any],
        new_events: List[Any],
        switched_companion: bool,
        old_companion: str,
        is_temporary: bool,
        phase_result: Optional[Any],
        rest_message: Optional[str],
        time_messages: List[str],
        provider_used: str,
        arrival_message: str = "",  # V4.5: NPC arrival message
    ) -> TurnResult:
        """Build final TurnResult with all fields."""
        completed_quests = [u.quest_id for u in quest_updates if u.quest_completed]
        is_photo = validated_updates.get("photo_requested", False)
        
        # Check if phase change caused companion to leave
        companion_left_due_to_phase = False
        needs_location_refresh = False
        if phase_result and phase_result.companion_left:
            companion_left_due_to_phase = True
            needs_location_refresh = True
        
        # Build final text
        final_text = llm_response.text
        
        # V4.5: Add arrival message if present
        if arrival_message:
            final_text += arrival_message
        
        all_time_messages = []
        if rest_message:
            all_time_messages.append(rest_message)
        if time_messages:
            all_time_messages.extend(time_messages)
        if self.engine._pending_time_message:
            all_time_messages.append(self.engine._pending_time_message)
            self.engine._pending_time_message = None
        if self.engine._pending_phase_message:
            all_time_messages.append(self.engine._pending_phase_message)
            self.engine._pending_phase_message = None
        
        if all_time_messages:
            final_text = "\n\n".join(all_time_messages) + "\n\n" + final_text
        
        # Event data
        event_data = None
        new_event_started = False
        if active_event:
            event_data = active_event.to_dict()
            new_event_started = len(new_events) > 0
        
        # Get available actions
        available_actions = []
        if self.gameplay_manager:
            actions = self.gameplay_manager.get_available_actions(game_state)
            available_actions = [a.to_dict() for a in actions]
        
        # Finalize tracing
        with self.tracer.step_context("Final Result", "result"):
            self.tracer.expect("result_has_user_input", True)
            self.tracer.actual("result_has_user_input", user_input is not None and len(user_input) > 0)
            self.tracer.expect("result_companion", game_state.active_companion)
            self.tracer.actual("result_companion", game_state.active_companion)
            self.tracer.expect("result_turn_number", game_state.turn_count)
            self.tracer.actual("result_turn_number", game_state.turn_count)
        
        self.tracer.finalize_turn()
        
        return TurnResult(
            text=final_text,
            user_input=user_input,
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
            is_photo=is_photo,
            dynamic_event=self._build_dynamic_event_data(game_state),
            phase_change_result=phase_result,
            companion_left_due_to_phase=companion_left_due_to_phase,
            needs_location_refresh=needs_location_refresh,
            turn_number=game_state.turn_count,
            provider_used=provider_used,
        )
