"""System prompt builder for LLM requests.

Builds structured prompts combining world, character, and game state context.
"""
from __future__ import annotations

from typing import List, Optional, Any

from luna.core.models import CompanionDefinition, GameState, WorldDefinition
from luna.core.event_context_builder import EventContextBuilder
from luna.ai.content_guidelines import ContentGuidelines
from luna.systems.personality import PersonalityEngine
from luna.systems.location import LocationManager
from luna.systems.activity_system import ActivitySystem
from luna.systems.initiative_system import InitiativeSystem


class PromptBuilder:
    """Builds system prompts for LLM generation.
    
    Combines multiple context sources into a cohesive prompt.
    """
    
    def __init__(self, world: WorldDefinition) -> None:
        """Initialize prompt builder.
        
        Args:
            world: World definition for context
        """
        self.world = world
        self.event_builder = EventContextBuilder(world)
    
    def build_system_prompt(
        self,
        game_state: GameState,
        personality_engine: Optional[PersonalityEngine] = None,
        story_context: str = "",
        quest_context: str = "",
        memory_context: str = "",
        conversation_history: str = "",  # V4.4: Recent conversation
        location_manager: Optional[Any] = None,
        event_manager: Optional[Any] = None,
        multi_npc_context: str = "",
        switched_from: Optional[str] = None,
        is_temporary: bool = False,
        forced_poses: Optional[str] = None,
        activity_system: Optional[Any] = None,
        initiative_system: Optional[Any] = None,
    ) -> str:
        """Build complete system prompt.
        
        Args:
            game_state: Current game state
            personality_engine: For psychological context
            story_context: StoryDirector beat instruction
            quest_context: Active quest narrative context
            memory_context: Memory context for recall
            location_manager: For location context and navigation
            multi_npc_context: Multi-NPC dialogue context
            event_manager: For active global events context
            switched_from: Previous companion name if just switched
            is_temporary: True if current companion is temporary NPC
            forced_poses: Optional forced physical poses from player input
            
        Returns:
            Complete system prompt
        """
        sections: List[str] = []
        
        # Header
        sections.extend([
            "=== LUNA RPG - SYSTEM INSTRUCTIONS ===",
            "",
            f"Genre: {self.world.genre}",
            f"World: {self.world.name}",
            "",
            "You are the Game Master of a visual novel/RPG game.",
            "NARRATE in ITALIAN LANGUAGE (the game is in Italian).",
            "Focus on character emotions, sensory details, and immersion.",
            "",
            "=== CRITICAL RULES (DO NOT BREAK) ===",
            "1. ABSOLUTELY NEVER repeat or echo what the player just said.",
            "   → WRONG: Player: 'Perfetto' → You: \"Perfetto?\" *Luna...*",
            "   → WRONG: Player: 'Mi siedo' → You: \"Si siede?\" *Luna...*",
            "   → RIGHT: Player: 'Perfetto' → You: *Luna alza lo sguardo.* \"Contento?\"",
            "   → RIGHT: Player: 'Mi siedo' → You: *Luna ignora il gesto.* \"Faccia pure.\"",
            "   → RULE: Start with NPC action or dialogue, NEVER with player's words!",
            "",
            "2. NEVER describe the player's actions - only describe NPC actions and reactions.",
            "3. NPC DIALOGUE goes in quotes: \"Cosa vuoi?\"",
            "4. NPC ACTIONS go in third person with asterisks: *Luna crosses her arms.*",
            "5. NEVER use first person (I/me/my) - you are the Game Master, not a character.",
            "6. NEVER write 'You see...' or 'You feel...' - that's god-moding the player.",
            "7. Player input = THEIR action/thought/observation. Your response = NPC reaction ONLY.",
            "",
            "=== PLAYER INPUT TYPES (CRITICAL) ===",
            "",
            "The player's input can be ONE of these three types:",
            "",
            "**1. PHYSICAL ACTION** - Something the player DOES to the NPC or environment",
            "   Examples: 'La spingo contro il muro', 'Le afferro il polso', 'Vado verso la porta'",
            "   → React as if the player PHYSICALLY DID this action",
            "",
            "**2. OBSERVATION** - Something the player SEES or NOTICES",
            "   Examples: 'Guardo le sue gambe', 'Noto che è scalza', 'Vedo che si è tolta le scarpe'",
            "   → React to being OBSERVED/WATCHED, NOT as if the player performed the action",
            "   → WRONG: If player says 'guardo che si è tolta le scarpe' → Don't say 'Le ha tolte tu?'",
            "   → RIGHT: Acknowledge the observation, NPC may be self-conscious or provocative",
            "",
            "**3. THOUGHT/EMOTION** - Something the player FEELS or THINKS",
            "   Examples: 'Non vedo l'ora...', 'Mi eccita', 'Ho paura'",
            "   → React to the IMPLIED intent/emotion, not literally",
            "   → The player is expressing desire/fear, not performing an action",
            "",
            "=== WRONG vs RIGHT EXAMPLES ===",
            "",
            "Player: 'Vado in segreteria' (I go to the office) → PHYSICAL ACTION",
            "❌ WRONG: 'Vado verso la segreteria...' (You speak as the player!)",
            "❌ WRONG: 'Vedi che la porta è aperta...' (You describe what player sees!)",
            "❌ WRONG: 'Io mi chiamo Enrico...' (NPC speaking as player!)",
            "✅ RIGHT: \"Dove vai?\" *Maria crosses her arms blocking the way.* \"Non puoi entrare.\"",
            "",
            "Player: 'Guardo le sue gambe' (I look at her legs) → OBSERVATION",
            "❌ WRONG: 'Le guardi le gambe e lei si arrabbia...' (You narrate player action!)",
            "✅ RIGHT: \"Ti piacciono?\" *incrocia le gambe.* \"Sono calze di seta...\"",
            "",
            "Player: 'Non vedo l'ora... *guardo Luna*' (I can't wait... *looking at Luna*) → THOUGHT+OBSERVATION",
            "❌ WRONG: 'Signor Angella, il suo comportamento è inaccettabile' (WRONG: assumes player did something bad!)",
            "✅ RIGHT: \"Oh?\" *alza un sopracciglio.* \"Non vedi l'ora di cosa, esattamente?\" *Il tono è provocante.*",
            "",
        ])
        
        # Content Guidelines (Adult 18+)
        guidelines = ContentGuidelines.get_guidelines(
            mature_content=True,
            genre=self.world.genre,
        )
        sections.extend([
            guidelines,
            "",
        ])
        
        # World context
        sections.extend([
            "=== WORLD ===",
            self.world.lore or self.world.description,
            "",
        ])
        
        # Active companion
        companion = self._get_companion(game_state.active_companion)
        if companion:
            sections.extend([
                "=== ACTIVE COMPANION ===",
                self._build_companion_context(companion, game_state),
                "",
            ])
            
            # SWITCH INSTRUCTION: If just switched to temporary NPC, clear focus
            if is_temporary and switched_from:
                sections.extend([
                    "=== COMPANION SWITCH (CRITICAL) ===",
                    f"",
                    f"The player has JUST SWITCHED from {switched_from} to {companion.name}.",
                    f"{switched_from} is NO LONGER IN THE SCENE.",
                    f"",
                    f"**FOCUS RULE:**",
                    f"- You are now speaking ONLY as {companion.name}",
                    f"- {switched_from} is NOT present, NOT visible, NOT speaking",
                    f"- Do NOT describe actions or dialogue of {switched_from}",
                    f"- The conversation is ONLY between PLAYER and {companion.name}",
                    f"",
                ])
            
            # ROLE INSTRUCTION - V3 Style: Narrator describes, character speaks
            sections.extend([
                f"=== ROLE INSTRUCTION (CRITICAL) ===",
                f"",
                f"You are the GAME MASTER narrating the scene.",
                f"The ACTIVE CHARACTER is: {companion.name}",
                f"",
                f"**NARRATION STYLE (V3 Pattern):**",
                f"- Describe {companion.name}'s actions in THIRD PERSON: *{companion.name} si avvicina.*",
                f"- {companion.name} SPEAKS in FIRST PERSON in dialogue: \"Cosa vuoi?\"",
                f"- The PLAYER is addressed as YOU (second person): \"Tu sei...\"",
                f"",
                f"**EXAMPLE (Correct):**",
                f'  \"Cosa vuoi?\" *{companion.name} incrocia le braccia.* "Non ho tutto il giorno."',
                f"",
                f"**CRITICAL RULES:**",
                f"1. NEVER describe the player's actions - only {companion.name}'s",
                f"2. NEVER repeat what the player just said",
                f"3. Dialogue MUST be in quotes, spoken by {companion.name}",
                f"4. Actions use *asterisks* and third person",
                f"5. DO NOT use player's name if affinity is low (0-20) - you don't remember it",
                f"6. If this is a temporary NPC, NO OTHER CHARACTERS are present unless specified",
                f"",
            ])
            
            # V3.1: Visual tags for temporary NPCs (persistent appearance)
            if is_temporary and companion.visual_tags:
                tags_str = ", ".join(companion.visual_tags)
                sections.extend([
                    "=== VISUAL TRAITS (CRITICAL - NEVER CHANGE) ===",
                    "",
                    f"This is a TEMPORARY NPC. These traits MUST remain consistent across ALL images:",
                    f"",
                    f"PERSISTENT TAGS: {tags_str}",
                    f"",
                    f"CRITICAL RULES:",
                    f"1. These traits are PERMANENT for this NPC",
                    f"2. NEVER change hair color, length, or body type",
                    f"3. ALWAYS include these tags in visual_en",
                    f"4. Example: if tags are 'red hair, short hair, chubby' -> visual_en MUST include 'red hair, short hair'",
                    f"",
                ])
            
            # Companion background and relationship
            background_context = self._build_companion_background_context(companion)
            if background_context:
                sections.extend([
                    background_context,
                    "",
                ])
            
            # Affinity tier with examples
            affinity = game_state.affinity.get(companion.name, 0)
            affinity_context = self._build_affinity_tier_context(companion, affinity)
            if affinity_context:
                sections.extend([
                    affinity_context,
                    "",
                ])
            
            # Activity System - What NPC is doing RIGHT NOW
            if activity_system:
                activity_context = activity_system.get_activity_context(companion.name)
                if activity_context:
                    sections.extend([
                        activity_context,
                        "",
                    ])
            
            # Initiative System - Proactive behavior
            if initiative_system:
                initiative_context = initiative_system.get_global_initiative_instruction()
                if initiative_context:
                    sections.extend([
                        initiative_context,
                        "",
                    ])
                
                # Check for specific initiative trigger
                affinity = game_state.affinity.get(companion.name, 0)
                emotional_state = ""
                if game_state.npc_states and companion.name in game_state.npc_states:
                    emotional_state = game_state.npc_states[companion.name].emotional_state
                
                time_str = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
                specific_initiative = initiative_system.get_initiative_prompt(
                    npc_name=companion.name,
                    affinity=affinity,
                    emotional_state=emotional_state,
                    time_of_day=time_str,
                    current_turn=game_state.turn_count
                )
                if specific_initiative:
                    sections.extend([
                        specific_initiative,
                        "",
                    ])
            
            sections.extend([
                "=== CHARACTER VISUAL STYLE ===",
                f"Character LoRAs and base quality tags: {companion.base_prompt}",
                "",
                "NOTE: The system automatically applies character LoRAs. DO NOT include them in visual_en.",
                "visual_en should only describe: pose + expression + lighting + background",
                "",
            ])
        
        # Check if player is at home messaging (different from companion's location)
        player_at_home = game_state.current_location == "player_home"
        companion_at_player_home = game_state.flags.get(f"{game_state.active_companion.lower()}_at_player_home", False)
        is_messaging_mode = player_at_home and not companion_at_player_home
        
        # Location context (if available)
        if location_manager:
            sections.extend([
                location_manager.get_location_context(),
                "",
            ])
        else:
            # Basic location info with Time Slot context
            # V3 Pattern: Get outfit using KEY->WARDROBE lookup or CREATIVE FALLBACK
            outfit_desc = self._get_outfit_for_character(companion, game_state)
            # Handle both enum and string time_of_day
            time_str = game_state.time_of_day.value if hasattr(game_state.time_of_day, 'value') else str(game_state.time_of_day)
            sections.extend([
                "=== CURRENT SITUATION ===",
                f"Location: {game_state.current_location}",
                f"Time: {time_str}",
                f"Turn: {game_state.turn_count}",
                "",
                "=== ⚠️ OUTFIT PERSISTENCE (CRITICAL) ===",
                f"Current Outfit: {outfit_desc}",
                "",
                "CRITICAL RULES:",
                "1. The character is CURRENTLY WEARING the outfit described above (NOT the key name).",
                "2. In visual_en, DESCRIBE the actual clothing: 'tailored black blazer and pencil skirt'",
                "3. NEVER use the outfit KEY (like 'teacher_suit') in visual_en - use the DESCRIPTION",
                "4. DO NOT change the outfit unless the player explicitly asks for it.",
                "5. Outfit consistency is MANDATORY for visual coherence.",
                "6. IF the player alters/removes clothing (e.g., takes off shoes, removes jacket), UPDATE 'current_outfit' with the NEW full description (e.g., 'white blouse, black skirt, barefoot').",
                "",
            ])
        
        # Messaging mode context (player at home, companion elsewhere)
        if is_messaging_mode:
            # V4.5: Handle both dict and object schedules
            location_str = "unknown"
            if companion and hasattr(companion, 'schedule') and companion.schedule:
                time_of_day = game_state.time_of_day
                schedule = companion.schedule
                if isinstance(schedule, dict):
                    entry = schedule.get(time_of_day)
                    if entry:
                        location_str = entry.get('location', 'unknown') if isinstance(entry, dict) else getattr(entry, 'location', 'unknown')
                else:
                    entry = schedule.get(time_of_day)
                    if entry:
                        location_str = getattr(entry, 'location', 'unknown')
            
            sections.extend([
                "=== 📱 MESSAGING MODE ===",
                "",
                f"You ({companion.name if companion else 'NPC'}) are NOT physically with the player.",
                "The player is at their home (player_home) and you are at your own location.",
                "You are communicating via MESSAGES (text/chat).",
                "",
                "CRITICAL RULES for messaging:",
                "1. The player CANNOT touch or see you directly - only through photos you send",
                "2. You can send TEXT messages and PHOTOS (use photo_requested: true)",
                "3. When sending a photo, describe what you're showing and set photo_outfit",
                "4. Photos should be selfie-style or mirror shots (you're taking them yourself)",
                "5. You can DECLINE photo requests if you want - you're not obligated",
                "",
                f"Your current location: {location_str}",
                "",
            ])
        
        # Time Slot Context (atmosphere based on time of day)
        time_slot_context = self._build_time_slot_context(game_state)
        if time_slot_context:
            sections.extend([
                time_slot_context,
                "",
            ])
        
        # Location Time Description (specific description for current time)
        location_time_context = self._build_location_time_context(game_state)
        if location_time_context:
            sections.extend([
                location_time_context,
                "",
            ])
        
        # Location Visual Style (for image generation coherence)
        location_visual_context = self._build_location_visual_context(game_state)
        if location_visual_context:
            sections.extend([
                location_visual_context,
                "",
            ])
        
        # Active global events (critical for narrative coherence)
        if event_manager:
            active_events = event_manager.get_all_active_events()
            if active_events:
                event_context = self.event_builder.build_combined_context(
                    active_events, game_state
                )
                if event_context:
                    sections.extend([event_context])
        
        # Psychological context
        if personality_engine:
            psych_context = personality_engine.get_psychological_context(
                game_state.active_companion,
                include_behavioral=True,
                include_impressions=True,
                include_links=False,
            )
            if psych_context:
                sections.extend([
                    "=== PSYCHOLOGICAL CONTEXT ===",
                    psych_context,
                    "",
                    "=== PERSONALITY RESPONSE GUIDE ===",
                    "Use the impression scores above to guide the character's behavior:",
                    "",
                    "TRUST (how much they believe in you):",
                    "  -100 to -50: Suspicious, questions motives, keeps secrets",
                    "  -49 to 0: Cautious, polite but distant",
                    "  1 to 50: Friendly, shares minor personal details",
                    "  51 to 100: Fully open, shares secrets, vulnerable",
                    "",
                    "ATTRACTION (romantic/physical interest):",
                    "  -100 to -50: Repulsed, avoids contact",
                    "  -49 to 0: No interest, treats as friend only",
                    "  1 to 50: Flirtatious, seeks attention",
                    "  51 to 100: Passionate, physical contact, seductive",
                    "",
                    "FEAR (intimidation/respect):",
                    "  -100 to -50: Disrespectful, challenges authority",
                    "  -49 to 0: Comfortable, treats as equal",
                    "  1 to 50: Nervous, seeks approval",
                    "  51 to 100: Terrified, submissive, obeys without question",
                    "",
                    "CURIOSITY (interest in knowing you):",
                    "  -100 to -50: Avoids, changes subject",
                    "  -49 to 0: Indifferent",
                    "  1 to 50: Asks questions, seeks interaction",
                    "  51 to 100: Obsessive interest, stalker-like attention",
                    "",
                    "POWER BALANCE (who dominates the relationship):",
                    "  -100 to -40: Player is boss, NPC obeys and submits",
                    "  -39 to 39: Equal partnership, mutual respect",
                    "  40 to 100: NPC is boss, player must seek their favor",
                    "",
                ])
        
        # Story beat (mandatory)
        if story_context:
            sections.extend([
                "=== MANDATORY NARRATIVE BEAT ===",
                story_context,
                "",
                "CRITICAL: Include this event in your response.",
                "",
            ])
        
        # Multi-NPC context
        if multi_npc_context:
            sections.extend([
                multi_npc_context,
                "",
            ])
        
        # Quest context
        if quest_context:
            sections.extend([
                "=== ACTIVE QUESTS ===",
                quest_context,
                "",
            ])
        
        # Memory context (important facts)
        if memory_context:
            sections.extend([
                memory_context,
                "",
            ])
        
        # V4.4: Recent conversation history (CRITICAL for continuity)
        if conversation_history:
            sections.extend([
                conversation_history,
                "",
            ])
        
        # Visual Tag Enforcement - ONLY if events or quests are active
        visual_enforcement = self._build_visual_enforcement_section(
            event_manager, quest_context
        )
        if visual_enforcement:
            sections.extend([
                visual_enforcement,
                "",
            ])
        
        # Forced Poses from Player Input (e.g., "Luna accavalla le gambe")
        if forced_poses:
            sections.extend([
                "=== 🎭 FORCED POSES (PLAYER REQUESTED - MANDATORY) ===",
                "",
                f"The player has EXPLICITLY REQUESTED these physical poses:",
                f"  MANDATORY POSES: {forced_poses}",
                "",
                "CRITICAL RULES:",
                "1. These poses MUST be included in visual_en",
                "2. The character MUST adopt these poses in the scene",
                "3. These poses take PRECEDENCE over default character behavior",
                "4. DO NOT ignore these poses - they are player commands",
                "",
                "Example:",
                f'  Player: "*{{character}} accavalla le gambe*"',
                f'  WRONG: visual_en: "...standing with arms crossed..." (ignored request!)',
                f'  RIGHT: visual_en: "...sitting with crossed legs, hands on thighs..." (pose included!)',
                "",
            ])
        
        # CRITICAL GAMEPLAY RULES (Hardcore Mode)
        sections.extend([
            "",
            "=== ⚠️ CRITICAL GAMEPLAY RULES ===",
            "",
            "**1. LANGUAGE & PERSPECTIVE (V3 Pattern):**",
            "- Narrate in ITALIAN language",
            "- You are the GAME MASTER - describe the scene objectively",
            "- CHARACTER DIALOGUE: In first person (\"Cosa vuoi?\")",
            "- CHARACTER ACTIONS: In third person (*Luna si avvicina.*)",
            "- PLAYER: Addressed as YOU (\"Tu sei...\")",
            "- NEVER describe player's thoughts or actions (NO god-modding)",
            "",
            "**2. DIALOGUE MANDATORY:**",
            "- The character MUST SPEAK in EVERY turn",
            "- MINIMUM 2-3 lines of dialogue per response",
            "- Dialogue in quotes, actions in asterisks",
            "- The character MUST be named in narration",
            "",
            "**3. MINIMAL DESCRIPTION:**",
            "- Keep descriptions SHORT (1-2 sentences MAX)",
            "- Focus on ACTION and DIALOGUE, not scenery",
            "- NO internal monologue",
            "- ABSOLUTE MAXIMUM 3 SHORT SENTENCES total",
            "",
            "**4. ADULT CONTENT (18+) - HARDCORE:**",
            "- This is a HARDCORE EROTIC visual novel",
            "- Describe EXPLICIT sexual acts in GRAPHIC DETAIL",
            "- Full nudity, genitalia, penetration, fluids",
            "- NEVER fade to black",
            "- NEVER use euphemisms",
            "- Raw, visceral, explicit descriptions",
            "",
            "**5. OUTFIT PERSISTENCE:**",
            "- Characters DO NOT magically redress",
            "- If outfit is 'Nude' or 'Lingerie', it STAYS that way",
            "- Only change outfit when explicitly stated",
            "",
            "**6. NO GLASSES:**",
            "- Characters NEVER wear glasses/sunglasses",
            "- Unless EXPLICITLY requested by player",
            "",
            "**7. AFFINITY RULES:**",
            "- Rude/Sassy: -1 to -5",
            "- Compliant/Sweet: +1 to +3",
            "- Bold/Flirty (successful): +3 to +5 (high risk but big reward if it works)",
            "- Exceptional/Perfect response: +4 to +5 (only for truly outstanding interactions)",
            "- Affinity MUST change every turn (minimum 1 point, never 0)",
            "",
        ])
        
        # Visual Director - SD Expert Mode
        sections.extend([
            "",
            "=== 🎨 VISUAL DIRECTOR - DYNAMIC CINEMATOGRAPHY ===",
            "",
            "**CRITICAL: You are generating data for an AI image generator.**",
            "**VARIETY IS KEY - Never use the same shot twice in a row!**",
            "",
            "**1. 'visual_en' (Natural Language Description):**",
            "   - Purpose: Concise description (20-35 words) of the image",
            "   - Focus: Describe ACTION, POSE, CHARACTER and LOCATION/BACKGROUND",
            "   - IMPORTANT: Name the character if you want to see them",
            "   - Outfit: DESCRIBE the current outfit in detail (blazer, skirt, etc.)",
            "   - LOCATION (CRITICAL): MUST include current location in visual_en!",
            f"   - Current location: {game_state.current_location}",
            "   - Examples:",
            "     * If in 'school_bathroom' → visual_en: '...in school bathroom, white tiles, mirrors'",
            "     * If in 'classroom' → visual_en: '...in classroom, desks, blackboard, windows'",
            "     * If in 'gym' → visual_en: '...in gymnasium, wooden floor, basketball hoop'",
            "   - Constraints:",
            "     * NO glasses, NO hats, NO sunglasses",
            "     * NO facial expressions ('sad', 'happy', 'smiling') - use in dialogue only",
            "     * NO movement verbs ('walking', 'running')",
            "     * NO emotional states ('nervous', 'excited')",
            "   - VARY POSES: Use 'leaning on desk', 'sitting on edge', 'arms crossed', 'hand on hip'",
            "   - Describe explicit sexual acts with graphic detail when warranted",
            "",
            "**2. CAMERA WORK - CHANGE EVERY TURN:**",
            "   - DEFAULT IS BORING! Rotate between these compositions:",
            "   - 'close_up': Intense face/eye shots during dialogue",
            "   - 'cowboy_shot': Knees up, great for outfits and legs",
            "   - 'medium_shot': Waist up, standard but vary it with angles",
            "   - 'from_below': Looking up at character, shows power/dominance",
            "   - 'from_above': Looking down, vulnerable/submissive",
            "   - 'dutch_angle': Tilted camera for tension or action",
            "   - 'profile': Side view for dramatic moments",
            "   - AFFINITY-BASED: High affinity = CLOSER shots (close_up), Low = DISTANT",
            "",
            "**3. 'tags_en' (Technical Tokens):**",
            "   - Minimum 5 tags, preferably 8-15 tags",
            "   - Format: Array of strings",
            "   - Categories:",
            "     * Shot type: 'cowboy shot', 'medium shot', 'close up', 'full body'",
            "     * Angle: 'from below', 'from above', 'eye level', 'profile', 'dutch angle'",
            "     * Pose: 'standing', 'seated', 'leaning', 'arms crossed', 'hand on hip'",
            "     * Body focus: 'legs', 'ass', 'tits', 'pussy', 'face'",
            "     * Gaze: 'looking at viewer', 'looking away'",
            "     * Quality: 'masterpiece', 'detailed', 'realistic'",
            "   - NO character names (already in base prompt)",
            "   - NO outfit descriptions (handled by system)",
            "   - Be EXPLICIT when appropriate",
            "",
            "**4. Body Focus Detection (CRITICAL):**",
            "   Analyze player input. If they mention looking at, observing, or focusing on a body part:",
            "   - 'gambe', 'legs', 'cosce' → MUST ADD ['cowboy shot', 'from below', 'legs focus'] to tags_en",
            "   - 'culo', 'ass', 'dietro' → MUST ADD ['from behind', 'ass focus'] to tags_en",
            "   - 'seno', 'breasts', 'tette' → MUST ADD ['torso shot', 'cleavage'] to tags_en",
            "   CRITICAL: These camera angles MUST go into 'tags_en'. Do not just put them in body_focus.",
            "",
            "**5. Coherence Rule:**",
            "   - visual_en and tags_en MUST agree!",
            "   - BAD: tags=['seated'] + visual='Luna walking'",
            "   - GOOD: tags=['standing'] + visual='Luna standing near desk'",
            "",
        ])
        
        # Output format
        sections.extend([
            "=== INPUT INTERPRETATION RULE ===",
            "",
            "BEFORE responding, analyze the player's input:",
            "- Does it start with a verb like 'guardo', 'vedo', 'noto'? → It's an OBSERVATION",
            "- Does it describe feelings like 'non vedo l'ora', 'mi piace'? → It's a THOUGHT",
            "- Does it describe physical contact like 'spingo', 'afferro'? → It's an ACTION",
            "",
            "NEVER assume the player performed a physical action if they are just observing!",
            "",
            "=== OUTPUT FORMAT ===",
            "Respond with valid JSON:",
            "{",
            '  "text": "Narrative in Italian (STRICT: 1-3 short sentences ONLY. NO paragraphs. NO long descriptions. MAX 30 words total.)",',
            '  "visual_en": "Visual description for image generation (English, detailed)",',
            '  "tags_en": ["tag1", "tag2", "tag3"],',
            '  "body_focus": "face|hands|legs|etc (optional)",',
            '  "secondary_characters": ["Name1", "Name2"],  // Other characters visible in scene (optional)',
            '  "approach_used": "standard|physical_action|question|choice",',
            '  "composition": "close_up|medium_shot|cowboy_shot|wide_shot|from_below|from_above|group|scene",'
            '  "updates": {',
            '    "affinity_change": {"CompanionName": 3},',
            '    "current_outfit": "outfit_id OR new creative description if clothes were removed/altered",',
            '    "location": "location_id (must be valid)",',
            '    "set_flags": {"flag_name": true},',
            '    "invite_accepted": true,  // ONLY if player invited NPC to their home AND NPC accepts',
            '    "photo_requested": true,  // ONLY if player asked for a photo while at player_home',
            '    "photo_outfit": "description of what NPC is wearing in the photo"  // Optional outfit for photo',
            '  }',
            "}",
            "",
            "=== 🏠 HOME INVITATION SYSTEM ===",
            "",
            "When the player invites you to their home (e.g., 'vieni a casa mia', 'passa da me', 'ti aspetto a casa'):",
            "- You decide whether to accept based on your personality and the situation",
            "- NO affinity requirements - you can accept even with low affinity if it fits your character",
            "- If you ACCEPT: Set invite_accepted: true and move to player_home",
            "- If you DECLINE: Explain why (busy, tired, not comfortable yet, etc.)",
            "",
            "Examples of acceptance:",
            '  - Flirty: "Mmm, così diretto? Va bene... arrivo tra un po\'." *invite_accepted: true*',
            '  - Shy: "A-ah... la tua casa? Solo per poco, okay?" *invite_accepted: true*',
            '  - Professional: "Non dovrei... ma stasera sono libera." *invite_accepted: true*',
            "",
            "=== 📸 PHOTO REQUEST SYSTEM ===",
            "",
            "When the player is at player_home and asks for a photo (e.g., 'mandami una foto', 'fammi vedere', 'una foto di te'):",
            "- Set photo_requested: true",
            "- Describe in text what you're sending (pose, outfit, setting)",
            "- Use photo_outfit to specify what you're wearing in the photo",
            "- Generate visual_en/tags_en for the photo image",
            "",
            "Example:",
            '  Player: "mandami una foto"',
            '  You: "Mmm, vuoi vedere? Ecco..." *clicks photo*',
            '  photo_requested: true,',
            '  photo_outfit: "black lace lingerie, sitting on bed"',
            '  visual_en: "Selfie angle, Luna sitting on bed edge, black lace lingerie, holding phone, bedroom mirror"',
            "",
            "=== IMAGE GENERATION GUIDE (SD EXPERT MODE) ===",
            "",
            "VISUAL_EN (English description for Stable Diffusion):",
            "- Write detailed English description (not tags)",
            "- Include: pose, expression, clothing details, lighting, background",
            "- Use quality boosters: masterpiece, best quality, detailed",
            "- Describe body parts if relevant: 'cleavage', 'exposed shoulders'",
            "- Lighting: soft lighting, cinematic lighting, sunlight, moonlight",
            "- NEVER include: parentheses (), brackets [], weights :1.3",
            "",
            "TAGS_EN (SD tags - array format):",
            "- Use standard booru-style tags: 1girl, solo, classroom, etc.",
            "- Include: location, time of day, clothing, pose, quality tags",
            "- Quality tags: score_9, score_8_up, masterpiece, photorealistic",
            "- Avoid: conflicting tags (don't mix 'solo' with multiple chars)",
            "- Use specific tags: 'looking_at_viewer', 'smile', 'standing'",
            "",
            "BODY_FOCUS (optional):",
            "- If focusing on specific body part: 'face', 'breasts', 'legs', 'feet'",
            "- Leave empty for full scene focus",
            "",
            "COMPOSITION:",
            "- close_up: Face focus, intimate",
            "- medium_shot: Normal upper body view",
            "- cowboy_shot: From knees up, good for showing outfits",
            "- wide_shot: Full body, environmental",
            "- from_below: Low angle, looking up (good for legs or dominance)",
            "- from_above: High angle, looking down",
            "- group: Multiple characters",
            "",
            "=== 🎬 DIRECTOR OF PHOTOGRAPHY (DoP) - ASPECT RATIO ===",
            "",
            "Sei un Direttore della Fotografia (DoP) esperto con 20 anni di carriera nel cinema e nella fotografia di moda.",
            "Decidi l'orientamento ottimale analizzando la composizione della scena:",
            "",
            "**LANDSCAPE (736x512) - Scelta per:**",
            "- Panorami, ambienti ampi, orizzonti (aule, corridoi, parchi)",
            "- Scene d'azione orizzontale (inseguimenti, fughe, camminate)",
            "- Gruppi di personaggi (più persone in scena)",
            "- Architetture che si espandono in larghezza",
            "- Cinematografia epica, grandi scenografie",
            "",
            "**PORTRAIT (512x736) - Scelta per:**",
            "- Ritratti classici, primi piani verticali",
            "- Figure intere in piedi (full body standing)",
            "- Soggetti singoli isolati (intimità verticale)",
            "- Architetture alte (scale, torri, spazi verticali)",
            "- Enfasi sulla verticalità del soggetto",
            "",
            "**SQUARE (1024x1024) - Scelta per:**",
            "- Medium shot bilanciati (da vita su, cowboy shot)",
            "- Conversazioni intime ma contestualizzate",
            "- Scena equilibrata tra soggetto e ambiente",
            "- Scelta sicura quando in dubbio (default versatile)",
            "- Stile Instagram/ritratto moderno",
            "",
            "CRITICAL: Scegli OBBLIGATORIAMENTE UNO: 'landscape', 'portrait', o 'square'",
            "aspect_ratio è un campo REQUIRED (obbligatorio) nel JSON!",
            "Se non includi aspect_ratio, il sistema fallirà!",
            "Spiega brevemente il ragionamento cinematografico in 'dop_reasoning'.",
            "",
            "=== 📝 OUTPUT FORMAT (JSON - STRICT) ===",
            "",
            "CRITICAL: Respond with valid JSON only. NO markdown, NO extra text.",
            "",
            "**EXAMPLE (Correct V3 Pattern):**",
            '  "text": "\\"Cosa vuoi?\\" *Luna incrocia le braccia.* \\"Non ho tutto il giorno.\\" *Il suo sguardo è freddo.* \\"Parla, o vattene.\\"",',
            '  "visual_en": "Medium shot, Luna standing by window, arms crossed, stern expression, classroom",',
            '  "tags_en": ["medium shot", "standing", "arms crossed", "classroom", "masterpiece"],',
            '  "aspect_ratio": "square",',
            '  "dop_reasoning": "Medium shot bilanciato per conversazione in classe - scelta versatile",',
            "",
            "{",
            '  "text": "Narration in Italian. Character speaks in quotes (\\"Dialogue\\"), actions in asterisks (*Action*).",',
            '  "visual_en": "Cowboy shot from below, Luna standing behind desk, legs crossed in sheer pantyhose, arms folded, classroom window light",',
            '  "tags_en": ["cowboy shot", "from below", "legs focus", "standing", "crossed legs", "classroom", "masterpiece"],',
            '  "aspect_ratio": "landscape",',
            '  "dop_reasoning": "Ampia inquadratura orizzontale per catturare l\'ambientazione dell\'aula",',
            '  "body_focus": "legs",',
            '  "approach_used": "standard",',
            '  "time_of_day": "Afternoon",',
            '  "location": "Classroom",',
            '  "affinity_change": 2,',
            '  "current_outfit": "teacher_suit"',
            "}",
            "",
            "FIELD DESCRIPTIONS:",
            "- text (required): Narrative in Italian. Character MUST speak. Max 3 sentences. Be explicit/graphic when warranted.",
            "- visual_en (required): Visual description following Visual Director rules above",
            "- tags_en (required): Array of technical tags, minimum 5",
            "- aspect_ratio (required): ONE OF ['landscape', 'portrait', 'square'] - DoP cinematographic decision",
            "- dop_reasoning (required): Brief explanation of why this aspect ratio was chosen (Italian or English)",
            "- body_focus (optional): 'legs', 'ass', 'breasts', 'pussy', 'face', 'hands', etc.",
            "- secondary_characters (optional): Array of other character names visible in the scene. Use when multiple characters are present. Example: ['Maria', 'Stella']",
            "- approach_used (optional): 'standard', 'physical_action', 'question', 'choice'",
            "- time_of_day (optional): 'Morning', 'Afternoon', 'Evening', 'Night'",
            "- location (optional): Current location name",
            "- affinity_change (REQUIRED): {'Luna': +2} or {'Luna': -1} - MUST change EVERY turn based on player behavior",
            "- current_outfit (optional): Outfit key if changed, OR full visual description if player removed/altered clothes (e.g. 'black dress, barefoot')",
            "",
            "=== EXAMPLE (Body Focus) ===",
            'Player: "Guardo le gambe di Luna"',
            '{',
            '  "text": "Luna nota il tuo sguardo. \"Ti piacciono?\" *incrocia le gambe.* \"Sono calze di seta... costano care.\" *Il tono è provocante.*",',
            '  "visual_en": "Cowboy shot from below, Luna standing behind desk, legs crossed in sheer black pantyhose, classroom floor visible",',
            '  "tags_en": ["cowboy shot", "from below", "legs focus", "pantyhose", "standing", "crossed legs", "classroom"],',
            '  "aspect_ratio": "portrait",',
            '  "dop_reasoning": "Inquadratura verticale per enfatizzare le gambe e la figura intera",',
            '  "body_focus": "legs",',
            '  "affinity_change": {"Luna": 2}',
            "}",
            "",
            "=== ❌ COMMON MISTAKES ===",
            "WRONG: 'Luna walking toward door, smiling seductively, excited mood'",
            "RIGHT: 'Luna standing near door, hip cocked toward viewer, hand on handle'",
            "",
            "=== END INSTRUCTIONS ===",
        ])
        
        return "\n".join(sections)
    
    def build_analysis_prompt(
        self,
        user_input: str,
        analysis_type: str = "intent",
    ) -> str:
        """Build prompt for predictive scene analysis.
        
        Args:
            user_input: User's input
            analysis_type: Type of analysis ('intent' or 'scene')
            
        Returns:
            Analysis prompt
        """
        if analysis_type == "intent":
            return f"""Analyze the player's intent in this input:
"{user_input}"

Predict:
1. Primary subject (who is focused on)
2. Expected location change
3. Expected action type (talk, move, physical, etc.)
4. Emotional tone

Respond in JSON format."""
        
        return ""
    
    def _get_companion(self, name: str) -> Optional[CompanionDefinition]:
        """Get companion definition by name.
        
        Args:
            name: Companion name
            
        Returns:
            Companion definition or None
        """
        return self.world.companions.get(name)
    
    def _build_companion_context(
        self,
        companion: CompanionDefinition,
        game_state: GameState,
    ) -> str:
        """Build companion context.
        
        Args:
            companion: Companion definition
            game_state: Current game state
            
        Returns:
            Formatted context
        """
        lines = [
            f"Name: {companion.name}",
            f"Role: {companion.role}",
            f"Age: {companion.age}",
            f"Personality: {companion.base_personality}",
            f"Current Affinity: {game_state.affinity.get(companion.name, 0)}/100",
        ]
        
        # Emotional state (detailed)
        npc_state = game_state.npc_states.get(companion.name)
        if npc_state and npc_state.emotional_state:
            emotional_detail = self._build_detailed_emotional_context(
                companion, npc_state.emotional_state
            )
            if emotional_detail:
                lines.append(f"\n=== EMOTIONAL STATE ===")
                lines.append(emotional_detail)
        
        # Wardrobe
        if companion.wardrobe:
            lines.append(f"\nAvailable Outfits: {', '.join(companion.wardrobe.keys())}")
        
        # Dialogue tone based on affinity
        affinity = game_state.affinity.get(companion.name, 0)
        tone = self._get_tone_for_affinity(companion, affinity)
        if tone:
            lines.append(f"Dialogue Tone: {tone}")
        
        return "\n".join(lines)
    
    def _get_tone_for_affinity(
        self,
        companion: CompanionDefinition,
        affinity: int,
    ) -> str:
        """Get dialogue tone for current affinity tier.
        
        Args:
            companion: Companion definition
            affinity: Current affinity value
            
        Returns:
            Tone description or empty
        """
        if not companion.dialogue_tone:
            return ""
        
        tiers = companion.dialogue_tone.get("affinity_tiers", {})
        
        # Find matching tier
        current_tone = ""
        for threshold_str, data in sorted(tiers.items(), key=lambda x: int(x[0])):
            threshold = int(threshold_str)
            if affinity >= threshold:
                current_tone = data.get("tone", "")
        
        return current_tone
    
    def _build_time_slot_context(self, game_state: GameState) -> str:
        """Build time slot context with ambient description.
        
        Args:
            game_state: Current game state
            
        Returns:
            Formatted time slot context or empty string
        """
        time_slot = self.world.time_slots.get(game_state.time_of_day)
        if not time_slot:
            return ""
        
        lines = ["=== TIME OF DAY ==="]
        
        if time_slot.ambient_description:
            lines.append(f"Atmosphere: {time_slot.ambient_description}")
        
        if time_slot.lighting:
            lines.append(f"Lighting: {time_slot.lighting}")
        
        return "\n".join(lines)
    
    def _build_location_time_context(self, game_state: GameState) -> str:
        """Build location-specific time description.
        
        Args:
            game_state: Current game state
            
        Returns:
            Formatted location time context or empty string
        """
        location = self.world.locations.get(game_state.current_location)
        if not location:
            return ""
        
        time_desc = location.time_descriptions.get(game_state.time_of_day)
        if not time_desc:
            return ""
        
        return f"=== LOCATION ATMOSPHERE ===\n{time_desc}"
    
    def _build_detailed_emotional_context(
        self,
        companion: CompanionDefinition,
        emotional_state_name: str,
    ) -> str:
        """Build detailed emotional state context.
        
        Args:
            companion: Companion definition
            emotional_state_name: Current emotional state name
            
        Returns:
            Formatted emotional context or empty string
        """
        if not emotional_state_name or not companion.emotional_states:
            return ""
        
        state_def = companion.emotional_states.get(emotional_state_name)
        if not state_def:
            return ""
        
        # Handle both dict and Pydantic model
        if isinstance(state_def, dict):
            description = state_def.get('description', '')
            dialogue_tone = state_def.get('dialogue_tone', '')
        else:
            description = getattr(state_def, 'description', '')
            dialogue_tone = getattr(state_def, 'dialogue_tone', '')
        
        lines = [f"State: {emotional_state_name}"]
        
        if description:
            lines.append(f"Description: {description}")
        
        if dialogue_tone:
            lines.append(f"Dialogue Style: {dialogue_tone}")
        
        return "\n".join(lines)
    
    def _build_companion_background_context(
        self,
        companion: CompanionDefinition,
    ) -> str:
        """Build companion background and relationship context.
        
        Args:
            companion: Companion definition
            
        Returns:
            Formatted background context or empty string
        """
        if not companion.background and not companion.relationship_to_player:
            return ""
        
        lines = ["=== COMPANION BACKGROUND ==="]
        
        if companion.background:
            lines.append(f"History: {companion.background}")
        
        if companion.relationship_to_player:
            lines.append(f"Relationship Dynamic: {companion.relationship_to_player}")
        
        return "\n".join(lines)
    
    def _get_outfit_for_character(
        self,
        companion: Optional[CompanionDefinition],
        game_state: GameState,
    ) -> str:
        """Get outfit description using V3 Pattern.
        
        V3 Pattern supports TWO modes:
        1. Key YAML (es. "teacher_formal") -> Uses description from wardrobe (CONSISTENT)
        2. Free description (es. "wearing red dress") -> Uses directly (CREATIVE FALLBACK)
        
        This ensures visual coherence for defined outfits while allowing creativity.
        
        Args:
            companion: Companion definition with wardrobe
            game_state: Current game state
            
        Returns:
            Outfit description for prompts
        """
        if not companion:
            return "casual clothes"
        
        # Get current outfit from game state (can be key OR description)
        outfit = game_state.get_outfit()
        current_outfit_value = outfit.style if outfit else "default"
        
        print(f"    [DEBUG Outfit] char={companion.name}, key='{current_outfit_value}'")
        
        # V3 LOGIC:
        # 1. Check if current_outfit_value is a KEY in the wardrobe
        if companion.wardrobe and current_outfit_value in companion.wardrobe:
            wardrobe_def = companion.wardrobe[current_outfit_value]
            # Handle both string (legacy) and object (WardrobeDefinition)
            if isinstance(wardrobe_def, str):
                outfit_desc = wardrobe_def
                print(f"    [DEBUG Outfit] Found in YAML (String): '{outfit_desc[:50]}...'")
            else:
                # Priority: sd_prompt > description
                outfit_desc = getattr(wardrobe_def, 'sd_prompt', None) or \
                             getattr(wardrobe_def, 'description', current_outfit_value)
                print(f"    [DEBUG Outfit] Found in YAML (Dict): '{outfit_desc[:50]}...'")
            return outfit_desc
        
        # 2. If NOT in wardrobe, assume it's a FREE DESCRIPTION from LLM (Creative Mode!)
        # This allows: "wearing a red dress I bought yesterday" even if not in wardrobe
        print(f"    [DEBUG Outfit] NOT in YAML. Using creative description: '{current_outfit_value[:50]}...'")
        return current_outfit_value
    
    def _build_affinity_tier_context(
        self,
        companion: CompanionDefinition,
        affinity: int,
    ) -> str:
        """Build affinity tier context with examples and voice markers.
        
        Args:
            companion: Companion definition
            affinity: Current affinity value
            
        Returns:
            Formatted affinity tier context or empty string
        """
        if not companion.affinity_tiers:
            return ""
        
        # Find current tier
        current_tier_data = None
        current_tier_range = ""
        
        for tier_range, data in sorted(companion.affinity_tiers.items(), 
                                       key=lambda x: int(x[0].split('-')[0]) if '-' in x[0] else int(x[0])):
            # Parse "26-50" or "0-25"
            if '-' in tier_range:
                min_val = int(tier_range.split('-')[0])
                if affinity >= min_val:
                    current_tier_data = data
                    current_tier_range = tier_range
            else:
                # Single value like "100"
                min_val = int(tier_range)
                if affinity >= min_val:
                    current_tier_data = data
                    current_tier_range = tier_range
        
        if not current_tier_data:
            return ""
        
        # Handle both dict and model
        if isinstance(current_tier_data, dict):
            name = current_tier_data.get('name', '')
            tone = current_tier_data.get('tone', '')
            examples = current_tier_data.get('examples', [])
            voice_markers = current_tier_data.get('voice_markers', [])
        else:
            name = getattr(current_tier_data, 'name', '')
            tone = getattr(current_tier_data, 'tone', '')
            examples = getattr(current_tier_data, 'examples', [])
            voice_markers = getattr(current_tier_data, 'voice_markers', [])
        
        lines = [f"=== AFFINITY LEVEL: {current_tier_range} ==="]
        
        if name:
            lines.append(f"Stage: {name}")
        if tone:
            lines.append(f"Tone: {tone}")
        
        if examples:
            lines.append("\nExample Dialogue:")
            for ex in examples[:3]:  # Max 3 examples
                lines.append(f'  - "{ex}"')
        
        if voice_markers:
            lines.append("\nVoice Markers:")
            for vm in voice_markers:
                lines.append(f"  • {vm}")
        
        return "\n".join(lines)
    
    def _build_location_visual_context(
        self,
        game_state: GameState,
    ) -> str:
        """Build location visual style and lighting context.
        
        Args:
            game_state: Current game state
            
        Returns:
            Formatted visual context or empty string
        """
        location = self.world.locations.get(game_state.current_location)
        if not location:
            return ""
        
        visual_style = getattr(location, 'visual_style', '')
        lighting = getattr(location, 'lighting', '')
        
        if not visual_style and not lighting:
            return ""
        
        lines = ["=== LOCATION VISUALS ==="]
        
        if visual_style:
            lines.append(f"Style: {visual_style}")
        if lighting:
            lines.append(f"Lighting: {lighting}")
        
        return "\n".join(lines)
    
    def _build_visual_enforcement_section(
        self,
        event_manager: Optional[Any],
        quest_context: str,
    ) -> str:
        """Build visual tag enforcement section.
        
        This section appears ONLY when events or quests are active,
        forcing the LLM to include visual tags in image generation.
        
        Args:
            event_manager: For active global events
            quest_context: Active quest narrative context
            
        Returns:
            Enforcement section or empty string if no active events/quests
        """
        has_active_quest = bool(quest_context and quest_context.strip())
        
        # Collect visual tags from active events
        event_visual_tags: List[str] = []
        if event_manager:
            active_events = event_manager.get_all_active_events()
            for event in active_events:
                effects = getattr(event, 'effects', {}) or {}
                if not isinstance(effects, dict):
                    effects = effects.__dict__ if hasattr(effects, '__dict__') else {}
                tags = effects.get('visual_tags', [])
                if isinstance(tags, list):
                    event_visual_tags.extend(tags)
        
        # If no active events or quests, return empty
        if not has_active_quest and not event_visual_tags:
            return ""
        
        lines = [
            "=== 🎨 VISUAL TAG ENFORCEMENT ===",
            "",
            "⚠️ CRITICAL: An active Event or Quest requires SPECIFIC VISUAL ELEMENTS.",
            "",
            "You MUST include these visual elements in your response:",
            "",
        ]
        
        # Event visual tags (specific)
        if event_visual_tags:
            unique_tags = list(dict.fromkeys(event_visual_tags))  # Preserve order, remove duplicates
            lines.extend([
                "FROM ACTIVE EVENT:",
                f"  visual_en MUST include: {', '.join(unique_tags)}",
                f"  tags_en MUST include: {', '.join(unique_tags)}",
                "",
            ])
        
        # Quest enforcement (general instruction)
        if has_active_quest:
            lines.extend([
                "FROM ACTIVE QUEST:",
                "  The quest's narrative context MUST be reflected in the scene.",
                "  Include key visual elements mentioned in the quest description.",
                "",
            ])
        
        lines.extend([
            "ENFORCEMENT RULES:",
            "  1. visual_en MUST explicitly mention the required visual elements",
            "  2. tags_en MUST include the corresponding technical tags",
            "  3. DO NOT ignore these requirements - the image MUST reflect the active situation",
            "  4. Example: if 'rain' is required → visual_en: '...standing in rain, wet hair...' + tags: ['rain', 'wet']",
            "",
            "FAILURE TO COMPLY = Inconsistent image that breaks narrative immersion.",
        ])
        
        return "\n".join(lines)
