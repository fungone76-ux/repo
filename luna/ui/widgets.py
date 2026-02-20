"""UI Widgets for Luna RPG v4.

Quest tracker, companion status, event display, etc.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QProgressBar,
    QGroupBox, QScrollArea, QFrame, QPushButton,
)
from PySide6.QtCore import Qt


class QuestTrackerWidget(QGroupBox):
    """Widget for tracking active quests."""

    def __init__(self, parent=None) -> None:
        """Initialize quest tracker."""
        super().__init__("📋 Quest Tracker", parent)
        self.setMaximumHeight(250)

        layout = QVBoxLayout(self)

        # Quest list
        self.quest_list = QListWidget()
        self.quest_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.quest_list)

        # Detail label
        self.lbl_detail = QLabel("No active quests")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.lbl_detail)

        self.quest_list.currentRowChanged.connect(self._on_quest_selected)

    def _on_quest_selected(self, row: int) -> None:
        """Handle quest selection."""
        if row >= 0:
            item = self.quest_list.item(row)
            if item:
                self.lbl_detail.setText(item.toolTip())

    def update_quests(self, quests: List[dict]) -> None:
        """Update quest list."""
        self.quest_list.clear()

        for quest in quests:
            status = quest.get('status', 'unknown')
            icon = "🟢" if status == 'active' else "✅" if status == 'completed' else "🔴"
            title = quest.get('title', 'Unknown Quest')

            item = QListWidgetItem(f"{icon} {title}")
            item.setToolTip(quest.get('description', ''))

            if status == 'completed':
                item.setForeground(Qt.gray)

            self.quest_list.addItem(item)


class CompanionStatusWidget(QGroupBox):
    """Widget for displaying all companions' status."""

    def __init__(self, parent=None) -> None:
        """Initialize companion status widget."""
        super().__init__("👥 Companions", parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.companion_widgets: Dict[str, dict] = {}

        # Style
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                color: white;
                font-size: 10px;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:0.5 #FFC107, stop:1 #E91E63);
                border-radius: 2px;
            }
        """)

    def set_companions(self, companions: List[str]) -> None:
        """Initialize widgets for companions."""
        # Clear existing
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.companion_widgets.clear()

        for name in companions:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setSpacing(2)
            container_layout.setContentsMargins(0, 0, 0, 0)

            # Header with name and emotion
            header = QHBoxLayout()
            lbl_name = QLabel(f"<b>{name}</b>")
            lbl_name.setStyleSheet("color: #fff;")

            lbl_emotion = QLabel("--")
            lbl_emotion.setStyleSheet("color: #888; font-size: 10px;")

            header.addWidget(lbl_name)
            header.addStretch()
            header.addWidget(lbl_emotion)

            # Affinity bar
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setFormat("%v/100")

            container_layout.addLayout(header)
            container_layout.addWidget(bar)

            self.layout().addWidget(container)

            self.companion_widgets[name] = {
                'emotion': lbl_emotion,
                'affinity': bar,
            }

        self.layout().addStretch()

    def update_companion(
        self,
        name: str,
        affinity: int,
        emotion: str = "",
        emotion_icon: str = "😐",
    ) -> None:
        """Update companion display."""
        if name not in self.companion_widgets:
            return

        widgets = self.companion_widgets[name]
        widgets['affinity'].setValue(affinity)

        if emotion:
            widgets['emotion'].setText(f"{emotion_icon} {emotion}")


class GlobalEventWidget(QGroupBox):
    """Widget for displaying active global event."""

    def __init__(self, parent=None) -> None:
        """Initialize event widget."""
        super().__init__("🌍 Event", parent)

        layout = QVBoxLayout(self)

        self.lbl_event = QLabel("No active events")
        self.lbl_event.setWordWrap(True)
        self.lbl_event.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")

        layout.addWidget(self.lbl_event)
        layout.addStretch()

    def set_event(
        self,
        title: str = "",
        description: str = "",
        icon: str = "🌍",
    ) -> None:
        """Set active event display."""
        if title:
            self.setTitle(f"{icon} {title}")
            self.lbl_event.setText(description)
            self.lbl_event.setStyleSheet(
                "color: #4CAF50; font-size: 11px; padding: 5px; "
                "background-color: #1a3a1a; border-radius: 4px;"
            )
        else:
            self.setTitle("🌍 Event")
            self.lbl_event.setText("No active events")
            self.lbl_event.setStyleSheet(
                "color: #888; font-size: 11px; padding: 5px;"
            )


class StoryLogWidget(QGroupBox):
    """Widget for displaying story text."""

    def __init__(self, parent=None) -> None:
        """Initialize story log."""
        super().__init__("📖 Story", parent)

        layout = QVBoxLayout(self)

        # Scroll area for story
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.lbl_story = QLabel("Welcome to Luna RPG v4...")
        self.lbl_story.setWordWrap(True)
        self.lbl_story.setStyleSheet("""
            color: #ddd;
            font-size: 13px;
            line-height: 1.5;
            padding: 10px;
        """)
        self.lbl_story.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.lbl_story)
        layout.addWidget(scroll)

    def append_text(self, text: str) -> None:
        """Append text to story."""
        current = self.lbl_story.text()
        self.lbl_story.setText(f"{current}\n\n{text}")

    def append_system_message(self, text: str) -> None:
        """Append system message (time change, etc)."""
        current = self.lbl_story.text()
        formatted = f'<span style="color: #888; font-style: italic;">[{text}]</span>'
        self.lbl_story.setText(f"{current}\n\n{formatted}")

    def set_text(self, text: str) -> None:
        """Set story text."""
        self.lbl_story.setText(text)


class ImageDisplayWidget(QGroupBox):
    """Widget for displaying generated images with zoom/pan support."""

    def __init__(self, parent=None) -> None:
        """Initialize image display."""
        super().__init__("🖼️ Scene", parent)

        layout = QVBoxLayout(self)

        # Use interactive ImageViewer instead of static QLabel
        from luna.ui.image_viewer import ImageViewer
        self.image_viewer = ImageViewer()
        
        layout.addWidget(self.image_viewer)

    def set_image(self, image_path: str) -> None:
        """Set displayed image."""
        self.image_viewer.set_image(image_path)

    def clear(self) -> None:
        """Clear image display."""
        self.image_viewer.clear()


class OutfitWidget(QGroupBox):
    """Widget for displaying and managing character outfit."""
    
    def __init__(self, parent=None) -> None:
        """Initialize outfit widget."""
        super().__init__("👗 Outfit", parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Current outfit display
        self.lbl_style = QLabel("Style: --")
        self.lbl_style.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout.addWidget(self.lbl_style)
        
        self.lbl_description = QLabel("No outfit set")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self.lbl_description)
        
        # Components display
        self.lbl_components = QLabel("")
        self.lbl_components.setWordWrap(True)
        self.lbl_components.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.lbl_components)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_change = QPushButton("🔄 Cambia")
        self.btn_change.setToolTip("Change outfit style")
        self.btn_change.setEnabled(False)
        
        self.btn_modify = QPushButton("✏️ Modifica")
        self.btn_modify.setToolTip("Modify outfit details")
        self.btn_modify.setEnabled(False)
        
        btn_layout.addWidget(self.btn_change)
        btn_layout.addWidget(self.btn_modify)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        # Style list (hidden by default, shown on change)
        self.style_list: Optional[QListWidget] = None
        
    def set_outfit(self, style: str, description: str, components: Optional[Dict[str, str]] = None) -> None:
        """Update outfit display.
        
        Args:
            style: Outfit style name
            description: Outfit description
            components: Optional component dict
        """
        self.lbl_style.setText(f"Style: {style}")
        self.lbl_description.setText(description or "No description")
        
        if components:
            comp_text = " | ".join([f"{k}: {v}" for k, v in components.items()])
            self.lbl_components.setText(comp_text)
        else:
            self.lbl_components.setText("")
            
    def set_available_styles(self, styles: List[str]) -> None:
        """Set available wardrobe styles.
        
        Args:
            styles: List of available style names
        """
        self._available_styles = styles
        self.btn_change.setEnabled(len(styles) > 0)
        self.btn_modify.setEnabled(True)
        
    def clear(self) -> None:
        """Clear outfit display."""
        self.lbl_style.setText("Style: --")
        self.lbl_description.setText("No outfit set")
        self.lbl_components.setText("")
        self.btn_change.setEnabled(False)
        self.btn_modify.setEnabled(False)


class LocationWidget(QGroupBox):
    """Widget for displaying current location and visible exits."""
    
    def __init__(self, parent=None) -> None:
        """Initialize location widget."""
        super().__init__("📍 Location", parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Current location
        self.lbl_location = QLabel("Unknown")
        self.lbl_location.setStyleSheet("font-weight: bold; color: #E91E63; font-size: 14px;")
        layout.addWidget(self.lbl_location)
        
        # Description
        self.lbl_description = QLabel("No location data")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self.lbl_description)
        
        # State indicator
        self.lbl_state = QLabel("")
        self.lbl_state.setStyleSheet("color: #FFC107; font-size: 10px;")
        layout.addWidget(self.lbl_state)
        
        # Visible locations
        layout.addWidget(QLabel("<b>🚪 Puoi raggiungere:</b>"))
        self.list_exits = QListWidget()
        self.list_exits.setMaximumHeight(100)
        self.list_exits.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                color: #4CAF50;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        layout.addWidget(self.list_exits)
        
        layout.addStretch()
    
    def set_location(
        self,
        name: str,
        description: str,
        state: str = "",
        exits: Optional[List[str]] = None,
    ) -> None:
        """Update location display.
        
        Args:
            name: Location name
            description: Location description
            state: Optional state text
            exits: List of visible exit names
        """
        self.lbl_location.setText(name)
        self.lbl_description.setText(description)
        
        if state and state != "normal":
            self.lbl_state.setText(f"State: {state}")
        else:
            self.lbl_state.setText("")
        
        self.list_exits.clear()
        if exits:
            for exit_name in exits:
                self.list_exits.addItem(f"→ {exit_name}")
        else:
            self.list_exits.addItem("(nessuna uscita visibile)")
    
    def clear(self) -> None:
        """Clear location display."""
        self.lbl_location.setText("Unknown")
        self.lbl_description.setText("No location data")
        self.lbl_state.setText("")
        self.list_exits.clear()
