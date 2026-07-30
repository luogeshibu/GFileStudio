from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

from g_file_studio.engines.color_engine import normalize_hex_color
from g_file_studio.ui.widgets.help_widgets import set_secondary


class ColorRuleRow(QWidget):
    """基础处理中的线路/母线颜色选择行。"""

    changed = Signal()

    def __init__(
        self,
        title: str,
        element_tag: str,
        default_color: str = "#0000FF",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.element_tag = element_tag
        self._color = normalize_hex_color(default_color)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.enabled_box = QCheckBox(f"修改{title}颜色  <{element_tag}>")
        self.enabled_box.setProperty("optionChoice", True)
        self.enabled_box.setToolTip(
            f"启用后只修改 Layer 直属 <{element_tag}> 的静态线色属性 lc 和 lcc。"
        )
        layout.addWidget(self.enabled_box)

        self.preview = QLabel()
        self.preview.setObjectName("colorPreview")
        self.preview.setFixedSize(34, 26)
        layout.addWidget(self.preview)

        self.value_label = QLabel(self._color)
        self.value_label.setObjectName("colorValue")
        self.value_label.setMinimumWidth(78)
        layout.addWidget(self.value_label)

        self.choose_button = QPushButton("选择颜色")
        set_secondary(self.choose_button)
        layout.addWidget(self.choose_button)
        layout.addStretch(1)

        self.enabled_box.toggled.connect(self._update_enabled)
        self.enabled_box.toggled.connect(self.changed)
        self.choose_button.clicked.connect(self._choose_color)
        self._refresh_preview()
        self._update_enabled()

    def _refresh_preview(self) -> None:
        self.preview.setStyleSheet(
            f"background: {self._color}; border: 1px solid #8ea0b6; border-radius: 5px;"
        )
        self.value_label.setText(self._color)

    def _update_enabled(self, *_args: object) -> None:
        enabled = self.enabled_box.isChecked()
        self.preview.setEnabled(enabled)
        self.value_label.setEnabled(enabled)
        self.choose_button.setEnabled(enabled)

    def _choose_color(self) -> None:
        selected = QColorDialog.getColor(QColor(self._color), self, "选择线条颜色")
        if not selected.isValid():
            return
        self.set_color(selected.name(QColor.NameFormat.HexRgb).upper())
        self.changed.emit()

    def is_enabled(self) -> bool:
        return self.enabled_box.isChecked()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled_box.setChecked(enabled)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = normalize_hex_color(color)
        self._refresh_preview()
