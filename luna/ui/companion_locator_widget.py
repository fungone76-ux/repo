"""Widget to display companion location hints.

Shows where companions are based on time and affinity.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox
)
from PySide6.QtCore import Qt

from luna.systems.companion_locator import get_locator


class CompanionLocatorWidget(QGroupBox):
    """Widget showing where companions are located."""
    
    def __init__(self, parent=None) -> None:
        super().__init__("📍 Where are they?", parent)
        self._setup_ui()
        self.locator = None
    
    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)
        
        # Status label
        self.lbl_status = QLabel("Start playing to discover locations")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        
        # Hint labels (one per companion)
        self.hint_labels: dict[str, QLabel] = {}
        
        layout.addStretch()
    
    def set_engine(self, engine) -> None:
        """Connect to game engine."""
        if engine and engine.world and engine.state_manager.current:
            self.locator = get_locator(engine.world, engine.state_manager.current)
            self._create_hint_labels(engine.world.companions.keys())
    
    def _create_hint_labels(self, companion_names: list[str]) -> None:
        """Create labels for each companion."""
        layout = self.layout()
        
        # Remove existing hint labels
        for label in self.hint_labels.values():
            layout.removeWidget(label)
            label.deleteLater()
        self.hint_labels.clear()
        
        # Create new labels
        for name in companion_names:
            lbl = QLabel(f"• {name}: ?")
            lbl.setWordWrap(True)
            layout.insertWidget(layout.count() - 1, lbl)  # Before stretch
            self.hint_labels[name] = lbl
    
    def update_hints(self) -> None:
        """Update all hint displays."""
        if not self.locator:
            return
        
        for name, label in self.hint_labels.items():
            hint = self.locator.get_hint(name)
            if hint:
                if hint.can_find_them:
                    label.setText(f"• {name}: {hint.hint_text}")
                    label.setStyleSheet("color: #4CAF50;")  # Green = can find
                else:
                    label.setText(f"• {name}: {hint.hint_text} (🔒)")
                    label.setStyleSheet("color: #888;")  # Gray = locked
            else:
                label.setText(f"• {name}: Unknown")
    
    def set_time(self, time_str: str) -> None:
        """Update when time changes."""
        self.lbl_status.setText(f"Time: {time_str}")
        self.update_hints()