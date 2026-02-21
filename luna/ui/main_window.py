"""Main application window for Luna RPG v4.

3-panel layout:
- Left: Status, Quests, Companions
- Center: Image display
- Right: Story log, Input
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
)


class MainWindow(QMainWindow):
    """Main game window."""

    def __init__(self, parent=None) -> None:
        """Initialize main window."""
        super().__init__(parent)
        self.setWindowTitle("LUNA RPG v4")
        self.setMinimumSize(1200, 800)

        # Engine (initialized later)
        self.engine: Optional[GameEngine] = None

        # UI setup
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()

        # Timer for async updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_update)
        self.update_timer.start(100)  # 100ms

    def _setup_ui(self) -> None:
        """Setup main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal splitter (3 panels)
        main_splitter = QSplitter(Qt.Horizontal)

        # === LEFT PANEL ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        self.quest_tracker = QuestTrackerWidget()
        self.event_widget = GlobalEventWidget()
        self.companion_status = CompanionStatusWidget()
        self.outfit_widget = OutfitWidget()
        self.location_widget = LocationWidget()

        left_layout.addWidget(self.quest_tracker)
        left_layout.addWidget(self.event_widget)
        left_layout.addWidget(self.companion_status)
        left_layout.addWidget(self.outfit_widget)
        left_layout.addWidget(self.location_widget, stretch=1)

        main_splitter.addWidget(left_panel)

        # === CENTER PANEL ===
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(5, 5, 5, 5)

        self.image_display = ImageDisplayWidget()
        center_layout.addWidget(self.image_display)

        main_splitter.addWidget(center_panel)

        # === RIGHT PANEL (STORY) - FIXED WIDTH ===
        right_panel = QWidget()
        right_panel.setMinimumWidth(350)
        right_panel.setMaximumWidth(450)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        self.story_log = StoryLogWidget()

        # Input area
        input_group = QWidget()
        input_layout = QHBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Type your action here...")
        self.txt_input.returnPressed.connect(self._on_send)
        self.txt_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #444;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #fff;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)

        self.btn_send = QPushButton("▶ Send")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #444;
            }
        """)

        input_layout.addWidget(self.txt_input, stretch=1)
        input_layout.addWidget(self.btn_send)

        right_layout.addWidget(self.story_log, stretch=1)
        right_layout.addWidget(input_group)

        main_splitter.addWidget(right_panel)

        # Set splitter sizes (20% - 50% - 30%) - STORY PANEL FIXED WIDTH
        main_splitter.setSizes([240, 600, 360])
        
        # Make right panel (story) fixed width - doesn't expand when image loads
        main_splitter.setStretchFactor(0, 0)  # Left panel
        main_splitter.setStretchFactor(1, 1)  # Center panel (image) - expands
        main_splitter.setStretchFactor(2, 0)  # Right panel (story) - FIXED

        # Main layout
        layout = QHBoxLayout(central)
        layout.addWidget(main_splitter)
        layout.setContentsMargins(0, 0, 0, 0)

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

        # Time advance button (alternative to status bar button)
        self.act_time = QAction("☀️ Time", self)
        self.act_time.setToolTip("Advance time of day")
        self.act_time.triggered.connect(self._on_advance_time)
        toolbar.addAction(self.act_time)

        # Active companion indicator (auto-switch based on conversation)
        self.lbl_companion = QLabel("👤 Companion")
        self.lbl_companion.setStyleSheet("color: #fff; padding: 0 10px;")
        toolbar.addWidget(self.lbl_companion)

        # Video generation button (disabled in local mode)
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
            QStatusBar::item {
                border: none;
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

        # Time widget (clickable) - MORE VISIBLE
        self.btn_time = QPushButton("☀️ MORNING")
        self.btn_time.setToolTip("Click to advance time →")
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
                border-color: #81C784;
            }
            QPushButton:pressed {
                background-color: #388E3C;
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
        """Initialize game engine and show opening scene.

        Args:
            world_id: World to load
            companion: Starting companion
            session_id: Optional session to load
        """
        self.statusbar.showMessage("Initializing game...")

        try:
            self.engine = GameEngine(world_id, companion)

            if session_id:
                await self.engine.load_session(session_id)
            else:
                await self.engine.initialize()

            # Update UI
            self._update_companion_list()
            self._update_status()  # Includes companion label update
            self._update_location_widget()
            self._update_video_toggle()
            self._update_outfit_widget()
            self._update_quest_tracker()

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
        
        # Handle time_of_day - could be enum or string from DB
        time_val = state.time_of_day
        if hasattr(time_val, 'value'):
            time_str = time_val.value
            time_enum = time_val
        else:
            time_str = str(time_val)
            # Convert string to enum for icon lookup
            try:
                time_enum = TimeOfDay(time_str)
            except ValueError:
                time_enum = TimeOfDay.MORNING
        
        # Update time button with icon
        time_icons = {
            TimeOfDay.MORNING: "☀️",
            TimeOfDay.AFTERNOON: "🌅",
            TimeOfDay.EVENING: "🌆",
            TimeOfDay.NIGHT: "🌙",
        }
        icon = time_icons.get(time_enum, "🕐")
        time_text = f"{icon} {time_str.upper()}"
        self.btn_time.setText(time_text)
        
        # Update toolbar time action too
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
        
        self.location_widget.set_location(
            name=current.name,
            description=desc,
            state=instance.current_state.value,
            exits=visible_names,
        )

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

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Turn failed: {e}")

        finally:
            self.btn_send.setEnabled(True)
            self.statusbar.showMessage("Ready")

    def _display_result(self, result: TurnResult) -> None:
        """Display turn result like a chat conversation.

        Args:
            result: Turn result
        """
        # Show user input first (if any) - like a chat message
        if result.user_input:
            self.story_log.append_user_message(result.user_input)
        
        # Handle companion switch notification
        if result.switched_companion and result.previous_companion and result.current_companion:
            self.story_log.append_system_message(
                f"📍 Ora parli con {result.current_companion} (prima: {result.previous_companion})"
            )
            # Update companion indicator
            self.lbl_companion.setText(f"👤 {result.current_companion}")
        
        # Show character/narrator response
        current_companion = result.current_companion or (self.engine.companion if self.engine else "Narrator")
        self.story_log.append_character_message(result.text, current_companion)

        # Image (if available)
        if result.image_path:
            from pathlib import Path
            img_path = Path(result.image_path)
            print(f"[MainWindow] Displaying image: {img_path}")
            print(f"[MainWindow] Image exists: {img_path.exists()}")
            if img_path.exists():
                self.image_display.set_image(str(img_path))
            else:
                print(f"[MainWindow] Warning: Image file not found: {img_path}")
        else:
            print("[MainWindow] No image path in result")

        # Quest updates
        if result.new_quests:
            # TODO: Update quest tracker
            pass

        # Companion updates
        state = self.engine.get_game_state()
        for name, affinity in result.affinity_changes.items():
            self.companion_status.update_companion(
                name, affinity, "", "😐"
            )

    def _on_update(self) -> None:
        """Timer update for async operations."""
        # Check for completed async operations
        pass

    def _on_toggle_audio(self, checked: bool) -> None:
        """Toggle audio."""
        if self.engine:
            self.engine.toggle_audio()
        self.act_audio.setText("🔊 Audio" if checked else "🔇 Audio")

    def _update_video_toggle(self) -> None:
        """Update video button state based on execution mode."""
        settings = get_settings()
        
        if settings.is_runpod:
            self.act_video.setEnabled(True)
            self.act_video.setToolTip("Genera video dall'immagine corrente (Wan2.1 I2V)")
        else:
            self.act_video.setEnabled(False)
            self.act_video.setToolTip("Video generation requires RunPod mode")

    def _on_toggle_video(self, checked: bool) -> None:
        """Handle video button click - open video generation dialog."""
        settings = get_settings()
        
        if not settings.is_runpod:
            # Video not available in local mode
            self.act_video.setChecked(False)
            QMessageBox.information(
                self,
                "Video Non Disponibile",
                "🎬 La generazione video è disponibile solo in modalità RunPod.\n\n"
                "Per generare video hai bisogno di:\n"
                "• Una GPU potente (RTX 4090 o superiore)\n"
                "• Wan2.1 I2V model (~20GB VRAM)\n\n"
                "Vai in Settings → Execution Mode e seleziona RUNPOD\n"
                "con un RunPod ID configurato."
            )
            return
        
        # Get current image path
        if not self.engine:
            QMessageBox.warning(self, "Errore", "Gioco non inizializzato")
            return
        
        # Get last generated image path from engine state
        game_state = self.engine.get_game_state()
        # Try to get the last image from various sources
        current_image = None
        
        # Check if we have an image in the display
        # For now, we'll need to track the last image path
        # Let's use a simple approach - check storage/images for latest
        from pathlib import Path
        import os
        
        images_dir = Path("storage/images")
        if images_dir.exists():
            image_files = sorted(images_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
            if image_files:
                current_image = str(image_files[0])
        
        if not current_image:
            QMessageBox.warning(
                self,
                "Nessuna Immagine",
                "Genera prima un'immagine prima di creare un video."
            )
            return
        
        # Open video dialog
        from luna.ui.video_dialog import VideoGenerationDialog
        
        dialog = VideoGenerationDialog(
            image_path=current_image,
            character_name=game_state.active_companion,
            parent=self,
        )
        
        if dialog.exec() != VideoGenerationDialog.Accepted:
            return
        
        user_action = dialog.get_action()
        if not user_action:
            return
        
        # Start video generation
        self._generate_video(current_image, user_action, game_state.active_companion)
    
    def _generate_video(self, image_path: str, user_action: str, character_name: str) -> None:
        """Generate video from image and user action.
        
        Args:
            image_path: Source image path
            user_action: User's motion description
            character_name: Character name
        """
        # Show progress dialog
        from PySide6.QtWidgets import QProgressDialog
        
        progress = QProgressDialog(
            "🎬 Generazione video in corso...\n\n"
            f"Azione: {user_action}\n\n"
            "Questo processo richiede ~5-7 minuti.\n"
            "Wan2.1 I2V sta generando il video...",
            "Annulla",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Generazione Video")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)  # No cancel for now
        progress.show()
        
        # Run generation async
        import asyncio
        asyncio.create_task(self._generate_video_async(image_path, user_action, character_name, progress))
    
    async def _generate_video_async(
        self,
        image_path: str,
        user_action: str,
        character_name: str,
        progress: QProgressDialog,
    ) -> None:
        """Async video generation.
        
        Args:
            image_path: Source image
            user_action: User's motion description
            character_name: Character name
            progress: Progress dialog
        """
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
                    f"🎬 Video salvato in:\n{video_path}\n\n"
                    "Il video è stato generato con successo!"
                )
                # Open video with system default player
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(video_path)))
            else:
                QMessageBox.warning(
                    self,
                    "Errore",
                    "Impossibile generare il video.\n"
                    "Controlla che ComfyUI sia configurato correttamente."
                )
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "Errore",
                f"Errore durante la generazione video:\n{str(e)}"
            )

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
        
        # Handle both enum and string
        if hasattr(new_time, 'value'):
            time_str = new_time.value
            time_enum = new_time
        else:
            time_str = str(new_time)
            # Convert string to enum for dictionary lookup
            try:
                time_enum = TimeOfDay(time_str)
            except ValueError:
                time_enum = TimeOfDay.MORNING
        
        # Add to story log
        time_names = {
            TimeOfDay.MORNING: "A new day begins... ☀️",
            TimeOfDay.AFTERNOON: "The sun climbs higher... 🌅",
            TimeOfDay.EVENING: "The day draws to a close... 🌆",
            TimeOfDay.NIGHT: "Night falls... 🌙",
        }
        message = time_names.get(time_enum, f"Time passes... {time_str}")
        self.story_log.append_system_message(message)
