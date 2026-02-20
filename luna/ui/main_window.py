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
    QLabel, QProgressBar, QToolBar, QMessageBox,
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

        # Video toggle (disabled in local mode)
        self.act_video = QAction("🎬 Video", self)
        self.act_video.setCheckable(True)
        self.act_video.setChecked(False)
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
        self.setStatusBar(self.statusbar)

        # Status labels
        self.lbl_status = QLabel("Ready")
        self.lbl_turn = QLabel("Turn: 0")
        self.lbl_location = QLabel("📍 Unknown")

        # Time widget (clickable)
        self.btn_time = QPushButton("☀️ MORNING")
        self.btn_time.setToolTip("Click to advance time")
        self.btn_time.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                color: #fff;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #4CAF50;
            }
        """)
        self.btn_time.clicked.connect(self._on_advance_time)

        self.statusbar.addWidget(self.lbl_status, stretch=1)
        self.statusbar.addWidget(self.lbl_turn)
        self.statusbar.addWidget(self.lbl_location)
        self.statusbar.addWidget(self.btn_time)

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
            self._update_status()
            self._update_location_widget()
            self._update_video_toggle()
            self._update_outfit_widget()

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
        
        # Update time button with icon
        time_icons = {
            TimeOfDay.MORNING: "☀️",
            TimeOfDay.AFTERNOON: "🌅",
            TimeOfDay.EVENING: "🌆",
            TimeOfDay.NIGHT: "🌙",
        }
        icon = time_icons.get(state.time_of_day, "🕐")
        self.btn_time.setText(f"{icon} {state.time_of_day.value.upper()}")
        
        # Update tooltip with next time
        times = list(TimeOfDay)
        current_idx = times.index(state.time_of_day)
        next_time = times[(current_idx + 1) % len(times)]
        self.btn_time.setToolTip(f"Click to advance to {next_time.value}")

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

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Turn failed: {e}")

        finally:
            self.btn_send.setEnabled(True)
            self.statusbar.showMessage("Ready")

    def _display_result(self, result: TurnResult) -> None:
        """Display turn result.

        Args:
            result: Turn result
        """
        # Story text
        self.story_log.append_text(result.text)

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
        """Update video toggle state based on execution mode."""
        settings = get_settings()
        
        if settings.is_runpod:
            self.act_video.setEnabled(True)
            self.act_video.setToolTip("Enable video generation (Wan2.1 I2V)")
        else:
            self.act_video.setEnabled(False)
            self.act_video.setChecked(False)
            self.act_video.setToolTip("Video generation requires RunPod mode")

    def _on_toggle_video(self, checked: bool) -> None:
        """Toggle video generation."""
        settings = get_settings()
        
        if checked and not settings.is_runpod:
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
        
        # Update video state in media pipeline
        if self.engine:
            self.engine.media_pipeline.video_enabled = checked
        
        self.act_video.setText("🎬 Video" if checked else "📹 Video")

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
        message = time_names.get(new_time, f"Time passes... {new_time.value}")
        self.story_log.append_system_message(message)
