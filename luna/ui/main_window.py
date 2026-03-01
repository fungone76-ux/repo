"""Main application window for Luna RPG v4.

4-panel layout:
- Left: Action Bar (gameplay actions)
- Center: Image display
- Right Top: Status Widgets (Quest, Companion, Location, Outfit)
- Right Bottom: Story log + Input
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLineEdit, QPushButton, QStatusBar,
    QLabel, QProgressBar, QToolBar, QMessageBox, QMenu,
)
from qasync import asyncSlot
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction

from luna.core.models import TimeOfDay
from luna.core.config import get_settings

from luna.core.engine import GameEngine, TurnResult
from luna.ui.widgets import (
    QuestTrackerWidget,
    StoryBeatsWidget,
    CompanionStatusWidget,
    GlobalEventWidget,
    StoryLogWidget,
    ImageDisplayWidget,
    OutfitWidget,
    LocationWidget,
    PersonalityArchetypeWidget,
)
from luna.ui.companion_locator_widget import CompanionLocatorWidget
from luna.ui.action_bar import ActionBarWidget, QuickActionBar
from luna.ui.feedback_visualizer import FeedbackVisualizer
from luna.ui.quest_choice_widget import QuestChoiceWidget, QuestChoice, PendingChoiceManager


class MainWindow(QMainWindow):
    """Main game window - REVISED LAYOUT."""

    def __init__(self, parent=None) -> None:
        """Initialize main window."""
        super().__init__(parent)
        self.setWindowTitle("LUNA RPG v4")
        self.setMinimumSize(1400, 850)
        
        # Start maximized
        self.showMaximized()

        # Engine (initialized later)
        self.engine: Optional[GameEngine] = None
        
        # Feedback visualizer
        self.feedback = FeedbackVisualizer(self)
        
        # Quest choice manager
        self.choice_manager = PendingChoiceManager()
        
        # Track current quest being decided
        self._current_choice_quest_id: Optional[str] = None

        # UI setup
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()

        # Timer for async updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_update)
        self.update_timer.start(100)  # 100ms

    def _setup_ui(self) -> None:
        """Setup main UI layout - WIDGETS ON RIGHT VERSION."""
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal splitter (3 main panels)
        main_splitter = QSplitter(Qt.Horizontal)

        # === LEFT PANEL (Personality + Event + Location + Outfit - compact) ===
        left_panel = QWidget()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(6)
        left_layout.setContentsMargins(6, 6, 6, 6)

        # Personality Profile widget (replaces ActionBar)
        self.personality_widget = PersonalityArchetypeWidget()
        left_layout.addWidget(self.personality_widget, stretch=1)

        # Event widget (più alto)
        self.event_widget = GlobalEventWidget()
        self.event_widget.setMinimumHeight(100)
        self.event_widget.setMaximumHeight(180)
        self.event_widget.choice_selected.connect(self._on_event_choice_selected)
        self.event_widget.event_dismissed.connect(self._on_event_dismissed)
        left_layout.addWidget(self.event_widget)

        # Location widget (compact)
        self.location_widget = LocationWidget()
        self.location_widget.setMaximumHeight(160)
        left_layout.addWidget(self.location_widget)

        # Outfit widget (più alto)
        self.outfit_widget = OutfitWidget()
        self.outfit_widget.setMinimumHeight(130)
        self.outfit_widget.setMaximumHeight(180)
        # Connect outfit widget signals
        self.outfit_widget.change_outfit_requested.connect(self._on_change_outfit)
        self.outfit_widget.modify_outfit_requested.connect(self._on_modify_outfit)
        left_layout.addWidget(self.outfit_widget)

        main_splitter.addWidget(left_panel)

        # === CENTER PANEL (Image) ===
        center_panel = QWidget()
        center_panel.setMinimumWidth(450)
        center_panel.setMaximumWidth(650)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(8, 8, 8, 8)

        self.image_display = ImageDisplayWidget()
        center_layout.addWidget(self.image_display)

        main_splitter.addWidget(center_panel)

        # === RIGHT PANEL (Status Widgets + Story) ===
        right_panel = QWidget()
        right_panel.setMinimumWidth(500)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(8, 8, 8, 8)

        # TOP: Story Beats for active companion
        self.story_beats_widget = StoryBeatsWidget()
        self.story_beats_widget.setMaximumHeight(150)
        right_layout.addWidget(self.story_beats_widget)

        # MIDDLE: Status widgets (Quest + Companion + Locator)
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setSpacing(10)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # Quest Tracker (with activation button)
        self.quest_tracker = QuestTrackerWidget()
        self.quest_tracker.setMinimumWidth(220)
        self.quest_tracker.setMaximumWidth(300)
        self.quest_tracker.quest_activate_requested.connect(self._on_quest_activate_requested)
        
        # Companion Status (più spazio per le barre affinità)
        self.companion_status = CompanionStatusWidget()
        self.companion_status.setMinimumWidth(260)
        
        # Companion Locator (where are they)
        self.companion_locator = CompanionLocatorWidget()
        self.companion_locator.setMinimumWidth(200)

        status_layout.addWidget(self.quest_tracker)
        status_layout.addWidget(self.companion_status, stretch=1)
        status_layout.addWidget(self.companion_locator)

        right_layout.addWidget(status_container)

        # MIDDLE: Quick actions bar
        self.quick_actions = QuickActionBar()
        self.quick_actions.action_triggered.connect(self._on_action_triggered)
        right_layout.addWidget(self.quick_actions)

        # CHOICE WIDGET: Quest choices overlay (hidden by default)
        self.choice_widget = QuestChoiceWidget()
        self.choice_widget.choice_made.connect(self._on_choice_made)
        self.choice_widget.cancelled.connect(self._on_choice_cancelled)
        right_layout.addWidget(self.choice_widget)
        
        # Track input enabled state
        self._input_blocked = False

        # BOTTOM: Story log (reduced height) + Input
        story_container = QWidget()
        story_layout = QVBoxLayout(story_container)
        story_layout.setSpacing(6)
        story_layout.setContentsMargins(0, 0, 0, 0)

        # Story log
        self.story_log = StoryLogWidget()
        story_layout.addWidget(self.story_log, stretch=1)

        # Input area
        input_group = QWidget()
        input_layout = QHBoxLayout(input_group)
        input_layout.setSpacing(8)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Scrivi qui il tuo messaggio...")
        self.txt_input.returnPressed.connect(self._on_send)
        self.txt_input.setMinimumHeight(42)
        self.txt_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 15px;
                font-size: 14px;
                border: 2px solid #555;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: #fff;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
                background-color: #333;
            }
        """)

        self.btn_send = QPushButton("▶ Invia")
        self.btn_send.setMinimumHeight(42)
        self.btn_send.setMinimumWidth(90)
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)

        input_layout.addWidget(self.txt_input, stretch=1)
        input_layout.addWidget(self.btn_send)

        story_layout.addWidget(input_group)
        right_layout.addWidget(story_container, stretch=1)

        main_splitter.addWidget(right_panel)

        # Set splitter sizes
        # Left: 220px | Center: 550px | Right: 630px
        main_splitter.setSizes([220, 550, 630])
        
        # Stretch factors
        main_splitter.setStretchFactor(0, 0)  # Left fixed
        main_splitter.setStretchFactor(1, 0)  # Center semi-fixed
        main_splitter.setStretchFactor(2, 1)  # Right expands

        # Main layout
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)

    def _setup_toolbar(self) -> None:
        """Setup toolbar."""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Audio toggle
        self.act_audio = QAction("🔊 Audio", self)
        self.act_audio.setCheckable(True)
        self.act_audio.setChecked(True)
        self.act_audio.triggered.connect(self._on_toggle_audio)
        toolbar.addAction(self.act_audio)

        # Time advance button
        self.act_time = QAction("☀️ Time", self)
        self.act_time.setToolTip("Advance time of day")
        self.act_time.triggered.connect(self._on_advance_time)
        toolbar.addAction(self.act_time)

        # Active companion indicator
        self.lbl_companion = QLabel("👤 Companion")
        self.lbl_companion.setStyleSheet("color: #fff; padding: 0 10px;")
        toolbar.addWidget(self.lbl_companion)
        
        # Personality archetype indicator
        self.lbl_archetype = QLabel("🎭 Analyzing...")
        self.lbl_archetype.setStyleSheet("""
            color: #FFD700; 
            padding: 0 10px;
            font-weight: bold;
        """)
        self.lbl_archetype.setToolTip("Your personality profile is being analyzed based on your actions")
        toolbar.addWidget(self.lbl_archetype)

        # Video generation button
        self.act_video = QAction("🎬 Video", self)
        self.act_video.triggered.connect(self._on_toggle_video)
        toolbar.addAction(self.act_video)

        toolbar.addSeparator()

        # New Game
        act_new = QAction("🎮 New Game", self)
        act_new.triggered.connect(self._on_new_game)
        toolbar.addAction(act_new)

        # Save
        act_save = QAction("💾 Save", self)
        act_save.triggered.connect(self._on_save)
        toolbar.addAction(act_save)

        # Load
        act_load = QAction("📂 Load", self)
        act_load.triggered.connect(self._on_load)
        toolbar.addAction(act_load)

        toolbar.addSeparator()

        # Settings
        act_settings = QAction("⚙️ Settings", self)
        act_settings.triggered.connect(self._on_settings)
        toolbar.addAction(act_settings)

    def _setup_statusbar(self) -> None:
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #2d2d2d;
                border-top: 2px solid #4CAF50;
                min-height: 30px;
            }
        """)
        self.setStatusBar(self.statusbar)

        # Status labels
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #ccc; padding: 0 10px;")
        
        self.lbl_turn = QLabel("🎲 TURN: 0")
        self.lbl_turn.setStyleSheet("""
            color: #4CAF50; 
            padding: 0 15px; 
            font-weight: bold;
            font-size: 14px;
            background-color: #1a1a1a;
            border-radius: 4px;
            border: 1px solid #4CAF50;
        """)
        
        self.lbl_location = QLabel("📍 Unknown")
        self.lbl_location.setStyleSheet("color: #4CAF50; padding: 0 10px;")

        # Time widget
        self.btn_time = QPushButton("☀️ MORNING")
        self.btn_time.setToolTip("Click to advance time")
        self.btn_time.setCursor(Qt.PointingHandCursor)
        self.btn_time.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
                color: #000;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
        """)
        self.btn_time.clicked.connect(self._on_advance_time)

        self.statusbar.addWidget(self.lbl_status, stretch=1)
        self.statusbar.addWidget(self.lbl_turn)
        self.statusbar.addWidget(self.lbl_location)
        
        # Debug: ensure turn label is visible
        self.lbl_turn.setMinimumWidth(100)
        self.lbl_turn.setAlignment(Qt.AlignCenter)
        self.statusbar.addPermanentWidget(self.btn_time)

    async def initialize_game(
        self,
        world_id: str,
        companion: str,
        session_id: Optional[int] = None,
    ) -> None:
        """Initialize game engine and show opening scene."""
        self.lbl_status.setText("Initializing game...")

        try:
            self.engine = GameEngine(world_id, companion)

            if session_id:
                await self.engine.load_session(session_id)
            else:
                await self.engine.initialize()

            # Connect global event callback
            if self.engine.event_manager:
                self.engine.event_manager.on_event_changed = self._on_event_changed
            
            # Update UI
            self._update_companion_list()
            self._update_companion_locator()
            self._update_status()
            self._update_location_widget()
            self._update_video_toggle()
            self._update_outfit_widget()
            self._update_quest_tracker()
            self._update_story_beats()
            self._update_action_bars()
            
            # Welcome notification
            self.feedback.info(
                "Game Started",
                f"Playing with {companion} in {world_id}"
            )

            # Generate and show opening introduction
            self.lbl_status.setText("Generating opening scene...")
            intro_result = await self.engine.generate_intro()
            
            # Display intro
            self._display_result(intro_result)
            
            self.lbl_status.setText("Ready")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize: {e}")

    def _update_companion_list(self) -> None:
        """Update companion list widget."""
        if not self.engine:
            return

        world = self.engine.world
        companions = list(world.companions.keys())
        self.companion_status.set_companions(companions)
    
    def _update_companion_locator(self) -> None:
        """Update companion location hints."""
        if not self.engine:
            return
        
        self.companion_locator.set_engine(self.engine)
        self.companion_locator.update_hints()

    def _update_status(self) -> None:
        """Update status bar."""
        if not self.engine:
            return
        
        # Clear any temporary message to show permanent widgets
        self.statusbar.clearMessage()

        state = self.engine.get_game_state()
        self.lbl_turn.setText(f"Turn: {state.turn_count}")
        
        # Get location name (not ID) for display
        location_name = state.current_location
        if self.engine.world and state.current_location in self.engine.world.locations:
            location_obj = self.engine.world.locations[state.current_location]
            location_name = location_obj.name
        self.lbl_location.setText(f"📍 {location_name}")
        
        # Update time button
        time_val = state.time_of_day
        if hasattr(time_val, 'value'):
            time_str = time_val.value
            time_enum = time_val
        else:
            time_str = str(time_val)
            try:
                time_enum = TimeOfDay(time_str)
            except ValueError:
                time_enum = TimeOfDay.MORNING
        
        time_icons = {
            TimeOfDay.MORNING: "☀️",
            TimeOfDay.AFTERNOON: "🌅",
            TimeOfDay.EVENING: "🌆",
            TimeOfDay.NIGHT: "🌙",
        }
        icon = time_icons.get(time_enum, "🕐")
        self.btn_time.setText(f"{icon} {time_str.upper()}")
        
        # Update toolbar time action
        if hasattr(self, 'act_time'):
            self.act_time.setText(f"{icon} Time")
        
        # Update tooltip with next time
        times = list(TimeOfDay)
        current_idx = times.index(time_enum)
        next_time = times[(current_idx + 1) % len(times)]
        self.btn_time.setToolTip(f"Click to advance to {next_time.value}")
        
        # Update active companion label
        if self.engine:
            active = self.engine.get_game_state().active_companion
            self.lbl_companion.setText(f"👤 {active}")

    def _update_all_widgets(self) -> None:
        """Update all UI widgets (used after load/new game)."""
        self._update_status()
        self._update_location_widget()
        self._update_outfit_widget()
        self._update_quest_tracker()
        self._update_story_beats()
        self._update_action_bars()
        self._update_companion_list()
        self._update_companion_locator()
        self._update_video_toggle()
        self._update_personality_display()

    def _update_location_widget(self) -> None:
        """Update location widget display."""
        if not self.engine or not self.engine.location_manager:
            return
        
        loc_mgr = self.engine.location_manager
        current = loc_mgr.get_current_location()
        instance = loc_mgr.get_current_instance()
        
        if not current or not instance:
            return
        
        # Get visible locations
        visible_ids = loc_mgr.get_visible_locations()
        visible_names = []
        for loc_id in visible_ids:
            loc = loc_mgr.get_location(loc_id)
            if loc:
                visible_names.append(loc.name)
        
        # Get description
        state = self.engine.get_game_state()
        desc = instance.get_effective_description(current, state.time_of_day)
        
        # Handle both enum and string state
        loc_state = instance.current_state.value if hasattr(instance.current_state, 'value') else str(instance.current_state)
        self.location_widget.set_location(
            name=current.name,
            description=desc,
            state=loc_state,
            exits=visible_names,
        )

    def _update_outfit_widget(self) -> None:
        """Update outfit widget display."""
        if not self.engine:
            return
        
        state = self.engine.get_game_state()
        outfit = state.get_outfit()
        
        # Get available styles from world
        world = self.engine.world
        companion = world.companions.get(state.active_companion)
        
        # V3.1 FIX: Fallback description from wardrobe if outfit has no description
        description = outfit.description
        if companion and companion.wardrobe and not description:
            # Try to get description from wardrobe
            wardrobe_def = companion.wardrobe.get(outfit.style)
            if wardrobe_def:
                if isinstance(wardrobe_def, str):
                    description = wardrobe_def
                else:
                    description = getattr(wardrobe_def, 'description', '') or \
                                 getattr(wardrobe_def, 'sd_prompt', '')
            # If still no description, use style name
            if not description:
                description = outfit.style
        
        if companion:
            styles = list(companion.wardrobe.keys()) if companion.wardrobe else ["default"]
            self.outfit_widget.set_available_styles(styles)
        
        self.outfit_widget.set_outfit(
            style=outfit.style,
            description=description,
            components=outfit.components,
        )

    def _update_quest_tracker(self) -> None:
        """Update quest tracker display for active companion."""
        if not self.engine or not self.engine.quest_engine:
            print("[QuestTracker] No engine or quest_engine")
            return
        
        from luna.core.models import QuestStatus
        
        game_state = self.engine.get_game_state()
        active_companion = game_state.active_companion
        
        # Get active quest states (for status tracking)
        active_states = {s.quest_id: s for s in self.engine.quest_engine.get_all_states()}
        
        # Iterate over ALL quest definitions (not just active ones)
        # This shows available quests too!
        all_quest_defs = self.engine.world.quests
        print(f"[QuestTracker] Active: {active_companion}, Total quest defs: {len(all_quest_defs)}, Active states: {len(active_states)}")
        
        quests = []
        for quest_id, quest_def in all_quest_defs.items():
            # Filter by active companion
            quest_character = getattr(quest_def, 'character', '')
            if quest_character and quest_character != active_companion:
                print(f"[QuestTracker] Skipping {quest_id} (character: {quest_character} != {active_companion})")
                continue  # Skip quests for other companions
            
            # Get requirements from activation conditions
            requirements = {}
            if hasattr(quest_def, 'activation') and quest_def.activation:
                for cond in quest_def.activation.conditions:
                    if cond.type == 'affinity':
                        requirements['affinity'] = cond.value
            
            # Get state if exists
            quest_state = active_states.get(quest_id)
            
            # Determine status
            if quest_state:
                if quest_state.status == QuestStatus.ACTIVE:
                    current_stage = quest_def.stages.get(quest_state.current_stage_id or "")
                    stage_desc = current_stage.description if current_stage else ""
                    
                    quests.append({
                        'quest_id': quest_id,
                        'title': quest_def.title,
                        'description': stage_desc or quest_def.description,
                        'status': 'active',
                        'requirements': requirements,
                    })
                elif quest_state.status == QuestStatus.COMPLETED:
                    quests.append({
                        'quest_id': quest_id,
                        'title': quest_def.title,
                        'description': quest_def.description,
                        'status': 'completed',
                        'requirements': {},
                    })
                else:
                    # Has state but not active/completed (rare)
                    quests.append({
                        'quest_id': quest_id,
                        'title': quest_def.title,
                        'description': quest_def.description,
                        'status': 'available',
                        'requirements': requirements,
                    })
            else:
                # No state = available to activate
                quests.append({
                    'quest_id': quest_id,
                    'title': quest_def.title,
                    'description': quest_def.description,
                    'status': 'available',
                    'requirements': requirements,
                })
        
        print(f"[QuestTracker] Found {len(quests)} quests for {active_companion}")
        self.quest_tracker.update_quests(quests)
    
    def _update_story_beats(self) -> None:
        """Update story beats widget for active companion."""
        if not self.engine or not self.engine.world:
            print("[StoryBeats] No engine or world")
            return
        
        game_state = self.engine.get_game_state()
        active_companion = game_state.active_companion
        
        # Get story beats from world meta
        story_beats = getattr(self.engine.world, 'story_beats', None)
        print(f"[StoryBeats] Loading beats for {active_companion}: {story_beats is not None}")
        
        if not story_beats:
            self.story_beats_widget.update_beats(active_companion, [])
            return
        
        beats = story_beats.get('beats', [])
        print(f"[StoryBeats] Total beats: {len(beats)}")
        companion_beats = []
        
        # Get current affinity
        current_affinity = game_state.affinity.get(active_companion, 0)
        
        for beat in beats:
            # Check if beat belongs to active companion
            beat_id = beat.get('id', '')
            if not beat_id.lower().startswith(active_companion.lower()):
                continue
            
            # Parse trigger to get required affinity
            trigger = beat.get('trigger', '')
            required_affinity = 0
            if 'affinity >=' in trigger:
                try:
                    required_affinity = int(trigger.split('>=')[1].split()[0])
                except (ValueError, IndexError):
                    pass
            
            # Check if completed (via flags)
            completed = False
            consequence = beat.get('consequence', '')
            if '=' in consequence:
                flag_name = consequence.split('=')[0].strip()
                if flag_name in game_state.flags:
                    completed = True
            
            companion_beats.append({
                'title': beat.get('description', beat_id),
                'required_affinity': required_affinity,
                'current_affinity': current_affinity,
                'completed': completed,
            })
        
        print(f"[StoryBeats] Found {len(companion_beats)} beats for {active_companion}")
        self.story_beats_widget.update_beats(active_companion, companion_beats)
    
    def _on_quest_activate_requested(self, quest_id: str) -> None:
        """Handle user clicking to activate a quest.
        
        Args:
            quest_id: ID of quest to activate
        """
        if not self.engine:
            return
        
        # Force activation through quest engine
        asyncio.create_task(self._activate_quest_async(quest_id))
    
    async def _activate_quest_async(self, quest_id: str) -> None:
        """Async activate quest.
        
        Args:
            quest_id: Quest to activate
        """
        try:
            game_state = self.engine.get_game_state()
            
            # Try to activate the quest
            result = self.engine.quest_engine.activate_quest(quest_id, game_state)
            
            if result:
                self.feedback.success("🎯 Quest Attivata!", f"Hai attivato: {result.title}")
                self.story_log.append_system_message(f"📜 Quest attivata: {result.title}")
                self._update_quest_tracker()
            else:
                # Quest might need specific conditions - inform user
                quest_def = self.engine.world.quests.get(quest_id)
                if quest_def:
                    self.feedback.info("ℹ️ Quest non ancora disponibile", 
                                      f"{quest_def.title} richiede condizioni specifiche")
        
        except Exception as e:
            print(f"[Quest Activation] Error: {e}")
            self.feedback.error("Errore", f"Impossibile attivare quest: {e}")

    def _update_action_bars(self) -> None:
        """Update quick action bar with available actions."""
        if not self.engine:
            return
        
        actions = self.engine.get_available_actions()
        self.quick_actions.update_actions(actions)

    def _update_video_toggle(self) -> None:
        """Update video button state based on execution mode."""
        settings = get_settings()
        
        if settings.is_runpod:
            self.act_video.setEnabled(True)
            self.act_video.setToolTip("Genera video dall'immagine corrente")
        else:
            self.act_video.setEnabled(False)
            self.act_video.setToolTip("Video generation requires RunPod mode")

    @asyncSlot()
    async def _on_send(self) -> None:
        """Handle send button."""
        if not self.engine:
            return
        
        # Block input if choice is active
        if self._input_blocked or self.choice_widget.is_active():
            return

        text = self.txt_input.text().strip()
        if not text:
            return

        self.txt_input.clear()
        self.btn_send.setEnabled(False)
        self.lbl_status.setText("Processing...")

        try:
            # Process turn
            result = await self.engine.process_turn(text)

            # Update UI
            self._display_result(result)
            self._update_status()
            self._update_location_widget()
            self._update_outfit_widget()  # Aggiunto aggiornamento outfit
            self._update_quest_tracker()
            self._update_story_beats()
            self._update_action_bars()
            self._update_personality_display()
            
            # Check for pending quest choices
            self._check_pending_quest_choices()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Turn failed: {e}")

        finally:
            if not self.choice_widget.is_active():
                self.btn_send.setEnabled(True)
                self.txt_input.setEnabled(True)
            self.lbl_status.setText("Ready")

    @asyncSlot()
    async def _on_action_triggered(self, action_id: str, target: str) -> None:
        """Handle action button click."""
        if not self.engine:
            return
        
        self.btn_send.setEnabled(False)
        self.lbl_status.setText(f"Executing: {action_id}...")
        
        try:
            # Execute the gameplay action
            result = self.engine.execute_action(action_id, target)
            
            if result.success:
                # Display result message
                if result.message:
                    self.story_log.append_system_message(result.message)
                
                # Show affinity changes
                for char, amount in result.affinity_changes.items():
                    if amount != 0:
                        current_aff = self.engine.gameplay_manager.affinity.get_affinity(char) if self.engine.gameplay_manager.affinity else 0
                        self.feedback.affinity_change(char, amount, current_aff)
                        self.companion_status.update_companion(char, current_aff, "", "😐")
                        
                        # Check for tier unlock
                        if self.engine.gameplay_manager.affinity:
                            tier = self.engine.gameplay_manager.affinity.get_tier(char)
                            if hasattr(tier, 'name'):
                                self.feedback.tier_unlocked(char, tier.name)
                
                # Show item changes
                for item in result.items_gained:
                    self.story_log.append_system_message(f"📦 Received: {item.name}")
                
                if result.money_change != 0:
                    icon = "💰" if result.money_change > 0 else "💸"
                    self.story_log.append_system_message(
                        f"{icon} Money: {'+' if result.money_change > 0 else ''}{result.money_change}"
                    )
                
                # Refresh action bars
                self._update_action_bars()
            else:
                # Show error
                self.story_log.append_system_message(f"❌ {result.message}")
            
        except Exception as e:
            print(f"[MainWindow] Action execution failed: {e}")
            self.story_log.append_system_message(f"❌ Error: {str(e)}")
        
        finally:
            self.btn_send.setEnabled(True)
            self.lbl_status.setText("Ready")

    def _display_result(self, result: TurnResult) -> None:
        """Display turn result."""
        # Show user input
        if result.user_input:
            self.story_log.append_user_message(result.user_input)
        
        # Handle companion switch notification
        if result.switched_companion and result.previous_companion and result.current_companion:
            print(f"[MainWindow] SWITCHED COMPANION: {result.previous_companion} -> {result.current_companion}")
            self.story_log.append_system_message(
                f"📍 Ora parli con {result.current_companion} (prima: {result.previous_companion})"
            )
            self.lbl_companion.setText(f"👤 {result.current_companion}")
            # Update quest tracker and story beats for new companion
            self._update_quest_tracker()
            self._update_story_beats()
            self._update_outfit_widget()
            # Update personality widget for new companion
            self._update_personality_display()
            # Update event widget (in case there was an active event)
            self.event_widget.set_event()  # Clear any event choices
        
        # Show character/narrator response
        current_companion = result.current_companion or (self.engine.companion if self.engine else "Narrator")
        
        # Use "NPC" label for temporary companions, actual name for regular companions
        display_name = "NPC" if result.is_temporary_companion else current_companion
        self.story_log.append_character_message(result.text, display_name)
        
        # Play audio if available and enabled
        if result.audio_path:
            self._play_audio(result.audio_path)

        # Image
        if result.image_path:
            from pathlib import Path
            img_path = Path(result.image_path)
            if img_path.exists():
                self.image_display.set_image(str(img_path))

        # Handle Multi-NPC sequence
        if result.multi_npc_sequence:
            self._display_multi_npc_sequence(result)
        else:
            # Standard single image display
            if result.image_path:
                from pathlib import Path
                img_path = Path(result.image_path)
                if img_path.exists():
                    self.image_display.set_image(str(img_path))
        
        # Quest updates with feedback
        if result.new_quests:
            for quest_title in result.new_quests:
                self.story_log.append_system_message(f"📜 New Quest: {quest_title}")
                self.feedback.quest_started(quest_title)
        
        if result.completed_quests:
            for quest_title in result.completed_quests:
                self.story_log.append_system_message(f"✅ Quest Completed: {quest_title}")
                self.feedback.quest_completed(quest_title)

        # Global event updates
        if result.active_event:
            self.event_widget.set_event(
                title=result.active_event.get('name', ''),
                description=result.active_event.get('description', ''),
                icon=result.active_event.get('icon', '🌍'),
            )
            # Notify if new event started this turn
            if result.new_event_started:
                self.feedback.info(
                    f"{result.active_event.get('icon', '🌍')} {result.active_event.get('name', '')}",
                    result.active_event.get('description', '')
                )
        
        # Dynamic event (random/daily) with choices - SHOW WIDGET
        if result.dynamic_event and result.dynamic_event.get('choices'):
            self._show_dynamic_event_choices(result.dynamic_event)
        
        # Companion updates
        state = self.engine.get_game_state()
        for name, delta in result.affinity_changes.items():
            # Get current total affinity value, not the delta
            current_affinity = state.affinity.get(name, 0)
            self.companion_status.update_companion(
                name, current_affinity, "", "😐"
            )
        
        # Update action bar
        if result.available_actions:
            self.quick_actions.update_actions(result.available_actions)

    def _display_multi_npc_sequence(self, result) -> None:
        """Display a multi-NPC dialogue sequence with focus switching.
        
        Args:
            result: TurnResult containing multi_npc_sequence
        """
        from pathlib import Path
        
        sequence = result.multi_npc_sequence
        if not sequence or not sequence.turns:
            return
        
        # Get unique speakers from turns
        unique_speakers = list(dict.fromkeys([t.speaker for t in sequence.turns]))
        
        # Get color map for different NPCs
        npc_colors = {}
        if len(unique_speakers) > 0:
            npc_colors[unique_speakers[0]] = "#4FC3F7"  # Cyan for primary
        if len(unique_speakers) > 1:
            npc_colors[unique_speakers[1]] = "#FF8A65"  # Orange for secondary
        if len(unique_speakers) > 2:
            npc_colors[unique_speakers[2]] = "#AED581"  # Green for third
        
        # Display each turn with its own dialogue box
        for i, turn in enumerate(sequence.turns):
            color = npc_colors.get(turn.speaker, "#E0E0E0")
            prefix = f"[{turn.speaker}]"
            
            # Add to story log with NPC-specific color
            self.story_log._append_formatted(f"{prefix} {turn.text}", color=color)
        
        # Display the last generated image (shows final scene state)
        if result.image_path:
            img_path = Path(result.image_path)
            if img_path.exists():
                self.image_display.set_image(str(img_path))
        elif result.multi_npc_image_paths and len(result.multi_npc_image_paths) > 0:
            # Multiple images generated - show the last one (final state)
            last_path = Path(result.multi_npc_image_paths[-1])
            if last_path.exists():
                self.image_display.set_image(str(last_path))

    def _on_update(self) -> None:
        """Timer update for async operations."""
        pass
    
    def _on_event_changed(self, event) -> None:
        """Handle global event activation/deactivation.
        
        Args:
            event: GlobalEventInstance or None if no active event
        """
        print(f"[GlobalEvent] Event changed: {event}")
        if event:
            print(f"[GlobalEvent] Setting event: {event.name} - {event.description[:50]}...")
            self.event_widget.set_event(
                title=event.name,
                description=event.description,
                icon=event.icon,
            )
            # Show notification for new events
            if hasattr(event, 'event_id'):
                self.feedback.info(
                    f"{event.icon} {event.name}",
                    event.description
                )
        else:
            print("[GlobalEvent] Clearing event widget")
            self.event_widget.set_event()  # Clear event

    def _on_toggle_audio(self, checked: bool) -> None:
        """Toggle audio."""
        if self.engine:
            self.engine.toggle_audio()
        self.act_audio.setText("🔊 Audio" if checked else "🔇 Audio")
    
    def _play_audio(self, audio_path: str) -> None:
        """Play audio file.
        
        Args:
            audio_path: Path to audio file
        """
        if not self.act_audio.isChecked():
            return  # Audio muted
        
        try:
            import pygame
            
            # Initialize pygame mixer if not already
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            # Load and play
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            
        except Exception as e:
            print(f"[MainWindow] Audio playback failed: {e}")

    def _on_toggle_video(self) -> None:
        """Handle video button click."""
        settings = get_settings()
        
        if not settings.is_runpod:
            self.act_video.setChecked(False)
            QMessageBox.information(
                self,
                "Video Non Disponibile",
                "🎬 La generazione video è disponibile solo in modalità RunPod.\n\n"
                "Vai in Settings → Execution Mode e seleziona RUNPOD"
            )
            return
        
        # Get current image path
        if not self.engine:
            QMessageBox.warning(self, "Errore", "Gioco non inizializzato")
            return
        
        # Check for latest image
        from pathlib import Path
        import os
        
        images_dir = Path("storage/images")
        if images_dir.exists():
            image_files = sorted(images_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
            if image_files:
                current_image = str(image_files[0])
                # Open video dialog
                from luna.ui.video_dialog import VideoGenerationDialog
                
                game_state = self.engine.get_game_state()
                dialog = VideoGenerationDialog(
                    image_path=current_image,
                    character_name=game_state.active_companion,
                    parent=self,
                )
                
                if dialog.exec() == VideoGenerationDialog.Accepted:
                    user_action = dialog.get_action()
                    if user_action:
                        self._generate_video(current_image, user_action, game_state.active_companion)
                return
        
        QMessageBox.warning(self, "Nessuna Immagine", "Genera prima un'immagine.")

    def _generate_video(self, image_path: str, user_action: str, character_name: str) -> None:
        """Generate video from image."""
        from PySide6.QtWidgets import QProgressDialog
        
        progress = QProgressDialog(
            "🎬 Generazione video in corso...\n\n"
            f"Azione: {user_action}\n\n"
            "Questo processo richiede ~5-7 minuti.",
            "Annulla",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Generazione Video")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        
        import asyncio
        asyncio.create_task(self._generate_video_async(image_path, user_action, character_name, progress))

    async def _generate_video_async(
        self,
        image_path: str,
        user_action: str,
        character_name: str,
        progress: QMessageBox,
    ) -> None:
        """Async video generation."""
        try:
            from luna.media.video_client import VideoClient
            from pathlib import Path
            
            video_client = VideoClient()
            
            video_path = await video_client.generate_video(
                image_path=Path(image_path),
                user_action=user_action,
                character_name=character_name,
            )
            
            progress.close()
            
            if video_path:
                QMessageBox.information(
                    self,
                    "Video Generato!",
                    f"🎬 Video salvato in:\n{video_path}"
                )
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(video_path)))
            else:
                QMessageBox.warning(self, "Errore", "Impossibile generare il video.")
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Errore", f"Errore durante la generazione video:\n{str(e)}")

    @asyncSlot()
    async def _on_new_game(self) -> None:
        """Start a new game - resets everything to zero."""
        print("[MainWindow] New Game button clicked")
        
        # Confirm with user
        reply = QMessageBox.question(
            self, "New Game",
            "Start a new game?\n\nCurrent progress will be lost unless saved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Reset engine completely
            if self.engine:
                self.engine = None
            
            # Clear UI
            self.story_log.clear()
            self._update_all_widgets()
            
            # Show startup dialog again
            from luna.ui.startup_dialog import StartupDialog
            from luna.core.config import reload_settings
            
            dialog = StartupDialog()
            
            # Wait for user selection
            result = await self._show_dialog_async(dialog)
            
            if result:
                # Get selection
                selection = dialog.get_selection()
                world_id = selection.get("world_id")
                companion = selection.get("companion")
                
                if not world_id or not companion:
                    QMessageBox.warning(self, "Error", "Please select world and companion!")
                    return
                
                # Reload settings
                reload_settings()
                
                # Initialize new game (NO session_id = fresh start)
                await self.initialize_game(world_id, companion, session_id=None)
                
                self.feedback.success("🎮 Nuova Partita", "Nuova partita iniziata!")
            
        except Exception as e:
            print(f"[New Game Error] {e}")
            QMessageBox.critical(self, "Error", f"Failed to start new game: {str(e)}")
    
    async def _show_dialog_async(self, dialog) -> bool:
        """Helper to show dialog asynchronously."""
        import asyncio
        future = asyncio.Future()
        
        def on_accepted():
            if not future.done():
                future.set_result(True)
        
        def on_rejected():
            if not future.done():
                future.set_result(False)
        
        dialog.accepted.connect(on_accepted)
        dialog.rejected.connect(on_rejected)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        
        return await future

    @asyncSlot()
    async def _on_save(self) -> None:
        """Save game to database."""
        print("[MainWindow] Save button clicked")
        
        if not self.engine or not self.engine.state_manager.is_loaded:
            QMessageBox.warning(self, "Save", "No game to save!")
            return
        
        try:
            from luna.core.database import get_db_session
            async with get_db_session() as db:
                success = await self.engine.state_manager.save(db)
                if success:
                    session_id = self.engine.state_manager.current.session_id
                    self.statusbar.showMessage(f"Game saved! (Session: {session_id})", 3000)
                    self.feedback.success("💾 Salvato", f"Partita salvata (ID: {session_id})")
                    print(f"[MainWindow] Game saved to slot {session_id}")
                else:
                    QMessageBox.critical(self, "Save Error", "Failed to save game!")
        except Exception as e:
            print(f"[Save Error] {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", f"Error saving: {str(e)}")

    @asyncSlot()
    async def _on_load(self) -> None:
        """Load game from database - restores EVERYTHING."""
        print("[MainWindow] Load button clicked")
        
        from PySide6.QtWidgets import QInputDialog
        session_id, ok = QInputDialog.getInt(
            self, "Load Game", "Enter save slot number:", 
            value=1, minValue=1, maxValue=9999
        )
        
        if not ok:
            return
        
        try:
            from luna.core.database import get_db_session, get_db_manager
            from luna.core.engine import GameEngine
            
            async with get_db_session() as db:
                # Create temporary state manager to load the state
                from luna.core.state import StateManager
                db_manager = get_db_manager()
                temp_manager = StateManager(db_manager)
                state = await temp_manager.load(db, session_id)
                
                if not state:
                    QMessageBox.warning(
                        self, "Load Error", 
                        f"No save found in slot {session_id}!"
                    )
                    return
                
                # Reset current engine
                if self.engine:
                    self.engine = None
                
                # Create NEW engine with loaded state
                self.engine = GameEngine(state.world_id, state.active_companion)
                
                # Initialize with loaded state (this sets up everything)
                await self.engine.initialize()
                
                # Replace the state manager's current state with loaded one
                self.engine.state_manager._current = state
                
                # Re-initialize systems with loaded state
                game_state = self.engine.get_game_state()
                
                # Restore outfit states
                for comp_name, outfit_state in state.companion_outfits.items():
                    game_state.companion_outfits[comp_name] = outfit_state
                
                # Restore NPC states
                for npc_name, npc_state in state.npc_states.items():
                    game_state.npc_states[npc_name] = npc_state
                
                # Restore affinity
                game_state.affinity = state.affinity
                
                # Restore flags
                game_state.flags = state.flags
                
                # Restore quests
                game_state.active_quests = state.active_quests
                game_state.completed_quests = state.completed_quests
                
                # Connect callbacks
                if self.engine.event_manager:
                    self.engine.event_manager.on_event_changed = self._on_event_changed
                
                # Update ALL UI widgets
                self._update_all_widgets()
                self.story_log.clear()
                
                # Welcome message
                self.story_log.append_system_message(
                    f"Game loaded from slot {session_id}!\n"
                    f"   Turn: {state.turn_count} | Location: {state.current_location}\n"
                    f"   Companion: {state.active_companion}"
                )
                
                self.statusbar.showMessage(f"Loaded slot {session_id}", 3000)
                self.feedback.success("📂 Caricato", f"Partita caricata (ID: {session_id})")
                
        except Exception as e:
            print(f"[Load Error] {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Load Error", f"Error loading: {str(e)}")

    def _on_settings(self) -> None:
        """Open settings."""
        QMessageBox.information(self, "Settings", "Settings coming soon!")

    def _on_advance_time(self) -> None:
        """Advance time of day when button is clicked."""
        if not self.engine:
            return
        
        # Advance time
        new_time = self.engine.state_manager.advance_time()
        
        # Update UI
        self._update_status()
        self._update_companion_locator()  # Location hints change with time
        
        # Add to story log
        time_names = {
            TimeOfDay.MORNING: "A new day begins... ☀️",
            TimeOfDay.AFTERNOON: "The sun climbs higher... 🌅",
            TimeOfDay.EVENING: "The day draws to a close... 🌆",
            TimeOfDay.NIGHT: "Night falls... 🌙",
        }
        
        # Handle both enum and string
        if hasattr(new_time, 'value'):
            time_str = new_time.value
        else:
            time_str = str(new_time)
            
        from luna.core.models import TimeOfDay
        try:
            time_enum = TimeOfDay(time_str) if isinstance(time_str, str) else new_time
        except ValueError:
            time_enum = TimeOfDay.MORNING
            
        message = time_names.get(time_enum, f"Time passes... {time_str}")
        self.story_log.append_system_message(message)

    
    def _update_personality_display(self) -> None:
        """Update personality archetype and impression display."""
        if not self.engine or not self.engine.personality_engine:
            return
        
        # Get active companion
        game_state = self.engine.get_game_state()
        companion = game_state.active_companion
        
        # Get archetype
        archetype = self.engine.personality_engine.detect_archetype(companion)
        
        # Update toolbar label
        if archetype:
            self.lbl_archetype.setText(f"🎭 {archetype}")
            self.lbl_archetype.setToolTip(
                f"Your personality profile with {companion}\n"
                f"Detected archetype: {archetype}\n"
                f"Based on your behavioral patterns"
            )
        else:
            # Count behaviors to show progress
            state = self.engine.personality_engine._ensure_state(companion)
            total_behaviors = sum(m.occurrences for m in state.behavioral_memory.values())
            if total_behaviors > 0:
                self.lbl_archetype.setText(f"🎭 Analyzing... ({total_behaviors}/3)")
            else:
                self.lbl_archetype.setText("🎭 Analyzing...")
        
        # Update personality widget with full details
        state = self.engine.personality_engine._ensure_state(companion)
        imp = state.impression
        
        # Update widget
        self.personality_widget.set_archetype(archetype)
        self.personality_widget.set_impressions(
            trust=imp.trust,
            attraction=imp.attraction,
            fear=imp.fear,
            curiosity=imp.curiosity,
            dominance_balance=imp.dominance_balance,
        )
        
        # Update behaviors list
        behaviors = [
            (b.value if hasattr(b, 'value') else str(b)).replace("_", " ").title() 
            for b, m in state.behavioral_memory.items() 
            if m.occurrences > 0
        ]
        self.personality_widget.set_behaviors(behaviors)
        
        # Check for newly detected behaviors and show notifications
        for behavior, memory in state.behavioral_memory.items():
            # Show notification on first detection or when intensity increases
            if memory.occurrences == 1 and memory.last_turn == game_state.turn_count - 1:
                behavior_str = behavior.value if hasattr(behavior, 'value') else str(behavior)
                behavior_name = behavior_str.replace("_", " ").title()
                self.feedback.behavior_detected(companion, behavior_name)
    
    # ===================================================================
    # Outfit Management
    # ===================================================================
    
    @asyncSlot()
    async def _on_change_outfit(self) -> None:
        """Handle 'Cambia' button - change to random outfit from wardrobe."""
        if not self.engine:
            return
        
        game_state = self.engine.get_game_state()
        companion_def = self.engine.world.companions.get(game_state.active_companion)
        
        if not companion_def:
            return
        
        # Change to random outfit
        new_outfit = self.engine.outfit_modifier.change_random_outfit(game_state, companion_def)
        
        if new_outfit:
            self._update_outfit_widget()
            self.feedback.info("👗 Outfit Cambiato", f"Luna indossa ora: {new_outfit}")
            print(f"[MainWindow] Random outfit changed to: {new_outfit}")
            
            # Generate new image with updated outfit
            self.lbl_status.setText("Generazione immagine...")
            image_path = await self.engine.generate_image_after_outfit_change()
            
            if image_path:
                from pathlib import Path
                img_path = Path(image_path)
                if img_path.exists():
                    self.image_display.set_image(str(img_path))
                    self.feedback.info("🖼️ Immagine Aggiornata", "Outfit cambiato visualizzato")
            
            self.lbl_status.setText("Ready")
    
    @asyncSlot()
    async def _on_modify_outfit(self) -> None:
        """Handle 'Modifica' button - custom outfit description."""
        if not self.engine:
            return
        
        # Show input dialog
        from PySide6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(
            self,
            "Modifica Outfit",
            "Descrivi l'outfit che vuoi (in italiano):\n\n"
            "Esempi:\n"
            "• vestito da sera rosso\n"
            "• pigiama con orsetti\n"
            "• bikini blu\n"
            "• solo intimo nero",
        )
        
        if not ok or not text.strip():
            return
        
        # Apply custom outfit
        game_state = self.engine.get_game_state()
        
        try:
            description_en = await self.engine.outfit_modifier.change_custom_outfit(
                game_state,
                text.strip(),
                self.engine.llm_manager,
            )
            
            self._update_outfit_widget()
            self.feedback.info("👗 Outfit Modificato", f"Nuovo outfit: {text[:30]}...")
            print(f"[MainWindow] Custom outfit: {text} -> {description_en}")
            
            # Generate new image with updated outfit
            self.lbl_status.setText("Generazione immagine...")
            image_path = await self.engine.generate_image_after_outfit_change()
            
            if image_path:
                from pathlib import Path
                img_path = Path(image_path)
                if img_path.exists():
                    self.image_display.set_image(str(img_path))
                    self.feedback.info("🖼️ Immagine Aggiornata", "Outfit modificato visualizzato")
            
            self.lbl_status.setText("Ready")
            
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile modificare outfit: {e}")
    
    # ===================================================================
    # Quest Choice System
    # ===================================================================
    
    def _check_pending_quest_choices(self) -> None:
        """Check for quests awaiting player choice and show dialog."""
        if not self.engine:
            return
        
        pending = self.engine.get_pending_quest_choices()
        for choice_data in pending:
            # Check if already showing this choice
            if self.choice_widget.is_active():
                break
            
            quest_id = choice_data["quest_id"]
            title = choice_data["title"]
            description = choice_data["description"]
            giver = choice_data["giver"]
            
            print(f"[MainWindow] Showing pending quest choice: {quest_id}")
            
            # Store current quest being decided
            self._current_choice_quest_id = quest_id
            
            # Block normal input
            self._input_blocked = True
            self.txt_input.setEnabled(False)
            self.btn_send.setEnabled(False)
            self.txt_input.setPlaceholderText("⛔ Scegli un'opzione sopra...")
            
            # Show choice widget
            self.choice_widget.show_quest_acceptance(
                quest_title=title,
                quest_description=description,
                giver_name=giver,
            )
            
            # Only show one choice at a time
            break
    
    def show_quest_choice(
        self,
        quest_id: str,
        title: str,
        description: str,
        giver_name: str,
    ) -> None:
        """Show quest acceptance choice dialog.
        
        Args:
            quest_id: Unique quest identifier
            title: Quest title
            description: Quest description
            giver_name: NPC offering the quest
        """
        # Store current quest being decided
        self._current_choice_quest_id = quest_id
        
        # Block normal input
        self._input_blocked = True
        self.txt_input.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.txt_input.setPlaceholderText("⛔ Scegli un'opzione sopra...")
        
        # Show choice widget
        self.choice_widget.show_quest_acceptance(
            quest_title=title,
            quest_description=description,
            giver_name=giver_name,
        )
        
        print(f"[Choice] Showing quest choice: {quest_id} - {title}")
    
    @asyncSlot()
    async def _on_choice_made(self, choice_id: str) -> None:
        """Handle player making a choice.
        
        Args:
            choice_id: The choice selected by player
        """
        print(f"[Choice] Player selected: {choice_id}")
        
        # Determine if this is a quest choice
        is_accept = choice_id in ("accept", "yes")
        is_decline = choice_id in ("decline", "no")
        
        if hasattr(self, '_current_choice_quest_id') and self._current_choice_quest_id:
            # This is a quest choice - resolve through engine
            if self.engine and (is_accept or is_decline):
                self.lbl_status.setText(f"Processing choice: {choice_id}...")
                
                quest_title = await self.engine.resolve_quest_choice(
                    self._current_choice_quest_id,
                    accepted=is_accept,
                )
                
                if quest_title and is_accept:
                    self.feedback.success("Quest Accettata!", f"Hai accettato: {quest_title}")
                    self.story_log.append_system_message(f"📜 Quest accettata: {quest_title}")
                elif is_decline:
                    self.feedback.info("Quest Rifiutata", "Hai rifiutato la missione")
                    self.story_log.append_system_message("❌ Quest rifiutata")
                
                # Update quest tracker
                self._update_quest_tracker()
                
                # Clear the stored quest ID
                self._current_choice_quest_id = None
        else:
            # Regular choice (includes dynamic event choices) - convert to text
            if self.engine:
                choice_text = self._choice_to_text(choice_id)
                await self._process_choice_turn(choice_text)
        
        # Clear dynamic event flag if set
        if hasattr(self, '_current_dynamic_event'):
            self._current_dynamic_event = None
        
        # Unblock input
        self._input_blocked = False
        self.txt_input.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.txt_input.setPlaceholderText("Scrivi qui il tuo messaggio...")
        self.txt_input.setFocus()
    
    def _on_choice_cancelled(self) -> None:
        """Handle player cancelling choice."""
        print("[Choice] Player cancelled")
        
        # Clear dynamic event flag if set
        if hasattr(self, '_current_dynamic_event'):
            self._current_dynamic_event = None
        
        # Unblock input
        self._input_blocked = False
        self.txt_input.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.txt_input.setPlaceholderText("Scrivi qui il tuo messaggio...")
        
        self.lbl_status.setText("Ready")
    
    def _choice_to_text(self, choice_id: str) -> str:
        """Convert choice ID to text command.
        
        Args:
            choice_id: The choice ID
            
        Returns:
            Text representation for engine
        """
        # Map choice IDs to commands
        choice_map = {
            "accept": "Accetto la missione.",
            "decline": "Rifiuto, non sono interessato.",
            "ask_more": "Dimmi di più su questa missione.",
            "yes": "Sì.",
            "no": "No.",
        }
        
        # Check for dynamic event choices (event_choice_0, event_choice_1, etc.)
        if choice_id.startswith("event_choice_"):
            # Extract index and convert to 1-based number for engine
            try:
                index = int(choice_id.split("_")[-1])
                return str(index + 1)  # Engine expects 1-based indexing
            except (ValueError, IndexError):
                return "1"
        
        # Check for quest-specific choices
        if choice_id.startswith("quest_"):
            # Extract result from choice_id (e.g., "quest_xyz_accept")
            parts = choice_id.rsplit("_", 1)
            if len(parts) == 2:
                result = parts[1]
                return choice_map.get(result, f"Scelgo: {choice_id}")
        
        return choice_map.get(choice_id, f"Scelgo: {choice_id}")
    
    async def _process_choice_turn(self, choice_text: str) -> None:
        """Process a turn from choice selection.
        
        Args:
            choice_text: Text command from choice
        """
        try:
            self.lbl_status.setText("Processing choice...")
            
            # Process turn with choice text
            result = await self.engine.process_turn(choice_text)
            
            # Update UI
            self._display_result(result)
            self._update_status()
            self._update_location_widget()
            self._update_quest_tracker()
            self._update_action_bars()
            self._update_personality_display()
            
            self.lbl_status.setText("Ready")
            
        except Exception as e:
            print(f"[Choice] Error processing choice: {e}")
            QMessageBox.critical(self, "Error", f"Choice processing failed: {e}")
    
    def show_binary_choice(
        self,
        title: str,
        question: str,
        yes_text: str = "Sì",
        no_text: str = "No",
    ) -> None:
        """Show simple yes/no choice.
        
        Args:
            title: Dialog title
            question: Question text
            yes_text: Yes button text
            no_text: No button text
        """
        # Block normal input
        self._input_blocked = True
        self.txt_input.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.txt_input.setPlaceholderText("⛔ Scegli un'opzione sopra...")
        
        # Show choice widget
        self.choice_widget.show_binary_choice(
            title=title,
            question=question,
            yes_text=yes_text,
            no_text=no_text,
        )
    
    def show_custom_choices(
        self,
        title: str,
        context: str,
        choices: list,
    ) -> None:
        """Show custom choice dialog (for quest choices - blocks input).
        
        Args:
            title: Dialog title
            context: Context/question
            choices: List of QuestChoice objects
        """
        # Block normal input (only for quest choices, not event choices)
        self._input_blocked = True
        self.txt_input.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.txt_input.setPlaceholderText("⛔ Scegli un'opzione sopra...")
        
        # Show choice widget
        self.choice_widget.show_choices(
            title=title,
            context=context,
            choices=choices,
        )
    
    def _show_dynamic_event_choices(self, dynamic_event: dict) -> None:
        """Show choice buttons for dynamic event (random/daily) in Event widget.
        
        Args:
            dynamic_event: Event data with 'narrative' and 'choices'
        """
        event_id = dynamic_event.get('event_id', 'Evento')
        narrative = dynamic_event.get('narrative', '')
        choices_data = dynamic_event.get('choices', [])
        
        if not choices_data:
            return
        
        # Store that we're handling a dynamic event
        self._current_dynamic_event = event_id
        self._current_event_choices = choices_data
        
        # Extract choice texts
        choice_texts = [c.get('text', f'Opzione {i+1}') for i, c in enumerate(choices_data)]
        
        # Show in Event widget (does NOT block input)
        self.event_widget.show_event_choices(
            event_title=event_id.replace('_', ' ').title(),
            description=narrative,
            choices=choice_texts,
        )
        
        print(f"[MainWindow] Showing dynamic event choices in Event widget for: {event_id}")
    
    @asyncSlot()
    async def _on_event_choice_selected(self, choice_index: int) -> None:
        """Handle event choice selected from Event widget.
        
        Args:
            choice_index: Index of selected choice (0-based)
        """
        print(f"[MainWindow] Event choice selected: {choice_index}")
        
        if not self.engine or not hasattr(self, '_current_dynamic_event'):
            return
        
        # Convert to text and process
        choice_text = str(choice_index + 1)  # 1-based for engine
        await self._process_choice_turn(choice_text)
        
        # Clear event state
        self._current_dynamic_event = None
        self._current_event_choices = None
    
    def _on_event_dismissed(self) -> None:
        """Handle event dismissed (user clicked Ignora)."""
        print(f"[MainWindow] Event dismissed: {getattr(self, '_current_dynamic_event', None)}")
        
        # Skip the event in engine
        if self.engine and hasattr(self, '_current_dynamic_event'):
            # Tell engine to skip current event
            if (hasattr(self.engine, 'gameplay_manager') and 
                self.engine.gameplay_manager and
                hasattr(self.engine.gameplay_manager, 'event_manager') and
                self.engine.gameplay_manager.event_manager):
                self.engine.gameplay_manager.event_manager.skip_event()
                print(f"[MainWindow] Event skipped via event_manager")
        
        # Clear event state
        self._current_dynamic_event = None
        self._current_event_choices = None

