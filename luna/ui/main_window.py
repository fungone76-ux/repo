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
    CompanionStatusWidget,
    GlobalEventWidget,
    StoryLogWidget,
    ImageDisplayWidget,
    OutfitWidget,
    LocationWidget,
    PersonalityArchetypeWidget,
)
from luna.ui.action_bar import ActionBarWidget, QuickActionBar
from luna.ui.feedback_visualizer import FeedbackVisualizer


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
        self.event_widget.setMaximumHeight(140)
        left_layout.addWidget(self.event_widget)

        # Location widget (compact)
        self.location_widget = LocationWidget()
        self.location_widget.setMaximumHeight(160)
        left_layout.addWidget(self.location_widget)

        # Outfit widget (più alto)
        self.outfit_widget = OutfitWidget()
        self.outfit_widget.setMinimumHeight(130)
        self.outfit_widget.setMaximumHeight(180)
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

        # TOP: Status widgets (Quest + Companion) - più spazio
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setSpacing(10)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # Quest Tracker
        self.quest_tracker = QuestTrackerWidget()
        self.quest_tracker.setMinimumWidth(200)
        self.quest_tracker.setMaximumWidth(280)
        
        # Companion Status (più spazio per le barre affinità)
        self.companion_status = CompanionStatusWidget()
        self.companion_status.setMinimumWidth(280)

        status_layout.addWidget(self.quest_tracker)
        status_layout.addWidget(self.companion_status, stretch=1)

        right_layout.addWidget(status_container)

        # MIDDLE: Quick actions bar
        self.quick_actions = QuickActionBar()
        self.quick_actions.action_triggered.connect(self._on_action_triggered)
        right_layout.addWidget(self.quick_actions)

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
        
        self.lbl_turn = QLabel("Turn: 0")
        self.lbl_turn.setStyleSheet("color: #888; padding: 0 10px;")
        
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
        self.statusbar.addPermanentWidget(self.btn_time)

    async def initialize_game(
        self,
        world_id: str,
        companion: str,
        session_id: Optional[int] = None,
    ) -> None:
        """Initialize game engine and show opening scene."""
        self.statusbar.showMessage("Initializing game...")

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
            self._update_status()
            self._update_location_widget()
            self._update_video_toggle()
            self._update_outfit_widget()
            self._update_quest_tracker()
            self._update_action_bars()
            
            # Welcome notification
            self.feedback.info(
                "Game Started",
                f"Playing with {companion} in {world_id}"
            )

            # Generate and show opening introduction
            self.statusbar.showMessage("Generating opening scene...")
            intro_result = await self.engine.generate_intro()
            
            # Display intro
            self._display_result(intro_result)
            
            self.statusbar.showMessage("Game ready!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize: {e}")

    def _update_companion_list(self) -> None:
        """Update companion list widget."""
        if not self.engine:
            return

        world = self.engine.world
        companions = list(world.companions.keys())
        self.companion_status.set_companions(companions)

    def _update_status(self) -> None:
        """Update status bar."""
        if not self.engine:
            return

        state = self.engine.get_game_state()
        self.lbl_turn.setText(f"Turn: {state.turn_count}")
        self.lbl_location.setText(f"📍 {state.current_location}")
        
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
        if companion:
            styles = list(companion.wardrobe.keys()) if companion.wardrobe else ["default"]
            self.outfit_widget.set_available_styles(styles)
        
        self.outfit_widget.set_outfit(
            style=outfit.style,
            description=outfit.description,
            components=outfit.components,
        )

    def _update_quest_tracker(self) -> None:
        """Update quest tracker display."""
        if not self.engine or not self.engine.quest_engine:
            return
        
        from luna.core.models import QuestStatus
        
        # Get all quest states
        quests = []
        for quest_state in self.engine.quest_engine.get_all_states():
            quest_def = self.engine.world.quests.get(quest_state.quest_id)
            if not quest_def:
                continue
            
            # Determine status
            if quest_state.status == QuestStatus.ACTIVE:
                # Get current stage description
                current_stage = quest_def.stages.get(quest_state.current_stage_id or "")
                stage_desc = current_stage.description if current_stage else ""
                
                quests.append({
                    'title': quest_def.title,
                    'description': stage_desc or quest_def.description,
                    'status': 'active',
                })
            elif quest_state.status == QuestStatus.COMPLETED:
                quests.append({
                    'title': quest_def.title,
                    'description': quest_def.description,
                    'status': 'completed',
                })
        
        self.quest_tracker.update_quests(quests)

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

        text = self.txt_input.text().strip()
        if not text:
            return

        self.txt_input.clear()
        self.btn_send.setEnabled(False)
        self.statusbar.showMessage("Processing...")

        try:
            # Process turn
            result = await self.engine.process_turn(text)

            # Update UI
            self._display_result(result)
            self._update_status()
            self._update_location_widget()
            self._update_quest_tracker()
            self._update_action_bars()
            self._update_personality_display()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Turn failed: {e}")

        finally:
            self.btn_send.setEnabled(True)
            self.statusbar.showMessage("Ready")

    @asyncSlot()
    async def _on_action_triggered(self, action_id: str, target: str) -> None:
        """Handle action button click."""
        if not self.engine:
            return
        
        self.btn_send.setEnabled(False)
        self.statusbar.showMessage(f"Executing: {action_id}...")
        
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
            self.statusbar.showMessage("Ready")

    def _display_result(self, result: TurnResult) -> None:
        """Display turn result."""
        # Show user input
        if result.user_input:
            self.story_log.append_user_message(result.user_input)
        
        # Handle companion switch notification
        if result.switched_companion and result.previous_companion and result.current_companion:
            self.story_log.append_system_message(
                f"📍 Ora parli con {result.current_companion} (prima: {result.previous_companion})"
            )
            self.lbl_companion.setText(f"👤 {result.current_companion}")
            # Update personality widget for new companion
            self._update_personality_display()
        
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
        
        # Companion updates
        state = self.engine.get_game_state()
        for name, affinity in result.affinity_changes.items():
            self.companion_status.update_companion(
                name, affinity, "", "😐"
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
        if event:
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

    def _on_save(self) -> None:
        """Save game."""
        QMessageBox.information(self, "Save", "Save feature coming soon!")

    def _on_load(self) -> None:
        """Load game."""
        QMessageBox.information(self, "Load", "Load feature coming soon!")

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

