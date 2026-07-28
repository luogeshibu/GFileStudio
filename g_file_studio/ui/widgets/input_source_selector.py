from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from g_file_studio.models import InputMode
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.widgets.path_row import PathRow
from g_file_studio.ui.widgets.wheel_safe_combo_box import WheelSafeComboBox


class InputSourceSelector(QWidget):
    """可复用的单文件 / 目录输入选择器，并分别记住两种模式的最近目录。"""

    modeChanged = Signal(str)
    pathChanged = Signal(str)

    def __init__(
        self,
        *,
        default_directory: Path | None = None,
        default_mode: InputMode = InputMode.DIRECTORY,
        file_filter: str = "G Files (*.sln.pic.g *.g)",
        single_label: str = "单个 G 文件",
        directory_label: str = "G 文件目录",
        file_tooltip: str = "选择一个 G 文件。",
        directory_tooltip: str = "选择包含一个或多个 G 文件的目录。",
        settings_prefix: str = "common",
        settings_service: UserSettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_service = settings_service or UserSettingsService()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("输入方式"))
        self.mode_combo = WheelSafeComboBox()
        self.mode_combo.addItem(single_label, InputMode.SINGLE_FILE.value)
        self.mode_combo.addItem(directory_label, InputMode.DIRECTORY.value)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        self.stack = QStackedWidget()
        self.file_row = PathRow(
            directory=False,
            file_filter=file_filter,
            dialog_title="选择单个 G 文件",
            recent_directory_key=f"recent_paths/{settings_prefix}/single_file_directory",
            location_name="单个 G 文件所在目录",
            settings_service=self.settings_service,
        )
        self.dir_row = PathRow(
            directory=True,
            dialog_title="选择 G 文件目录",
            recent_directory_key=f"recent_paths/{settings_prefix}/input_directory",
            location_name="G 文件输入目录",
            settings_service=self.settings_service,
        )
        self.dir_row.set_path(default_directory or (default_workspace() / "input"))
        self.file_row.set_tooltip(file_tooltip)
        self.dir_row.set_tooltip(directory_tooltip)
        self.stack.addWidget(self.file_row)
        self.stack.addWidget(self.dir_row)
        root.addWidget(self.stack)

        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.file_row.pathChanged.connect(self.pathChanged)
        self.dir_row.pathChanged.connect(self.pathChanged)
        self.set_mode(default_mode)

    def _mode_changed(self, *_args: object) -> None:
        self.stack.setCurrentIndex(0 if self.mode() == InputMode.SINGLE_FILE else 1)
        self.modeChanged.emit(self.mode().value)
        self.pathChanged.emit(str(self.path()))

    def mode(self) -> InputMode:
        value = str(self.mode_combo.currentData())
        return InputMode(value)

    def path(self) -> Path:
        return self.file_row.path() if self.mode() == InputMode.SINGLE_FILE else self.dir_row.path()

    def set_mode(self, mode: InputMode) -> None:
        target = self.mode_combo.findData(mode.value)
        if target >= 0:
            self.mode_combo.setCurrentIndex(target)
        self.stack.setCurrentIndex(0 if mode == InputMode.SINGLE_FILE else 1)
