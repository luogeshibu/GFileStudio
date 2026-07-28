from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.widgets.help_widgets import set_secondary


class PathRow(QWidget):
    """带最近目录记忆能力的文件或目录选择行。"""

    pathChanged = Signal(str)

    def __init__(
        self,
        *,
        directory: bool = True,
        file_filter: str = "All Files (*)",
        browse_help: str = "",
        dialog_title: str = "",
        recent_directory_key: str = "",
        location_name: str = "目录",
        settings_service: UserSettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.directory = directory
        self.file_filter = file_filter
        self.dialog_title = dialog_title or ("选择目录" if directory else "选择文件")
        self.recent_directory_key = recent_directory_key
        self.location_name = location_name
        self.settings_service = settings_service or UserSettingsService()

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

    def _current_hint(self) -> Path | None:
        text = self.edit.text().strip()
        if not text:
            return None
        path = Path(text).expanduser()
        if path.is_file():
            return path.parent
        if path.exists() and path.is_dir():
            return path
        if path.parent.exists() and path.parent.is_dir():
            return path.parent
        return None

    def _dialog_start_directory(self) -> Path:
        resolved = self.settings_service.resolve_directory(
            self.recent_directory_key,
            fallback=self._current_hint(),
        )
        if resolved.missing_saved_directory is not None:
            QMessageBox.warning(
                self,
                "上次目录不存在",
                f"上次使用的{self.location_name}已经不存在：\n"
                f"{resolved.missing_saved_directory}\n\n"
                "请重新选择。",
            )
        return resolved.directory

    def browse(self) -> None:
        start_path = self._dialog_start_directory()

        if self.directory:
            selected = QFileDialog.getExistingDirectory(
                self,
                self.dialog_title,
                str(start_path),
                QFileDialog.Option.ShowDirsOnly,
            )
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                str(start_path),
                self.file_filter,
            )
        if not selected:
            return

        selected_path = Path(selected)
        self.edit.setText(str(selected_path))
        recent_directory = selected_path if self.directory else selected_path.parent
        self.settings_service.set_directory(
            self.recent_directory_key,
            recent_directory,
        )

    def path(self) -> Path:
        return Path(self.edit.text().strip()).expanduser()

    def set_path(self, path: Path | str) -> None:
        self.edit.setText(str(path))

    def set_tooltip(self, text: str) -> None:
        self.edit.setToolTip(text)
        self.edit.setStatusTip(text)
        self.button.setToolTip(text)
        self.button.setStatusTip(text)
