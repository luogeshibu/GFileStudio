from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from g_file_studio.ui.widgets.help_widgets import set_secondary


class PathRow(QWidget):
    pathChanged = Signal(str)

    def __init__(
        self,
        *,
        directory: bool = True,
        file_filter: str = "All Files (*)",
        browse_help: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.directory = directory
        self.file_filter = file_filter
        self.edit = QLineEdit()
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self.pathChanged)

        self.button = QPushButton("浏览…")
        set_secondary(self.button)
        default_help = "选择目录" if directory else "选择文件"
        self.button.setToolTip(browse_help or default_help)
        self.button.setStatusTip(self.button.toolTip())
        self.button.clicked.connect(self.browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def browse(self) -> None:
        current = self.edit.text().strip()
        start_path = Path(current).expanduser() if current else Path.cwd()
        if not start_path.exists():
            start_path = start_path.parent if start_path.parent.exists() else Path.cwd()

        if self.directory:
            selected = QFileDialog.getExistingDirectory(self, "选择目录", str(start_path))
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "选择文件",
                str(start_path),
                self.file_filter,
            )
        if selected:
            self.edit.setText(selected)

    def path(self) -> Path:
        return Path(self.edit.text().strip()).expanduser()

    def set_path(self, path: Path | str) -> None:
        self.edit.setText(str(path))

    def set_tooltip(self, text: str) -> None:
        self.edit.setToolTip(text)
        self.edit.setStatusTip(text)
        self.button.setToolTip(text)
        self.button.setStatusTip(text)
