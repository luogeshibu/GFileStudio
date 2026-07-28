from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.models import TemplateMode
from g_file_studio.services.template_service import (
    BuiltinTemplate,
    TemplateServiceError,
    export_builtin_template,
    get_builtin_template,
    load_builtin_templates,
)
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.widgets.help_widgets import set_secondary
from g_file_studio.ui.widgets.path_row import PathRow
from g_file_studio.ui.widgets.wheel_safe_combo_box import WheelSafeComboBox


class TemplateSelector(QWidget):
    """内置模板 / 客户自定义模板选择器。"""

    modeChanged = Signal(str)
    templateChanged = Signal(str)

    def __init__(
        self,
        *,
        settings_prefix: str = "frame",
        settings_service: UserSettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_prefix = settings_prefix
        self.settings_service = settings_service or UserSettingsService()
        self._templates: dict[str, BuiltinTemplate] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(9)

        mode_row = QHBoxLayout()
        self.builtin_radio = QRadioButton("使用程序内置模板")
        self.custom_radio = QRadioButton("使用客户自定义模板")
        self.builtin_radio.setChecked(True)
        mode_row.addWidget(self.builtin_radio)
        mode_row.addWidget(self.custom_radio)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        builtin_row = QHBoxLayout()
        self.builtin_combo = WheelSafeComboBox()
        self.builtin_combo.setToolTip("选择随 App 一起发布的内置图框模板。")
        self.version_label = QLabel()
        self.version_label.setObjectName("mutedText")
        self.export_button = QPushButton("导出内置模板")
        set_secondary(self.export_button)
        self.export_button.setToolTip("把当前内置模板复制到外部文件，便于查看或修改。")
        builtin_row.addWidget(self.builtin_combo, 1)
        builtin_row.addWidget(self.version_label)
        builtin_row.addWidget(self.export_button)
        root.addLayout(builtin_row)

        self.custom_path = PathRow(
            directory=False,
            file_filter="SLD G Files (*.sln.pic.g);;G Files (*.g)",
            dialog_title="选择客户自定义图框模板",
            recent_directory_key=f"recent_paths/{settings_prefix}/custom_template_directory",
            location_name="客户自定义模板所在目录",
            settings_service=self.settings_service,
        )
        self.custom_path.set_tooltip(
            "选择客户自己的图框模板。程序只调整外框尺寸和组件位置，不修改模板中的任何文字或签字信息。"
        )
        root.addWidget(self.custom_path)

        self.note = QLabel()
        self.note.setObjectName("mutedText")
        self.note.setWordWrap(True)
        root.addWidget(self.note)

        self.builtin_radio.toggled.connect(self._update_mode)
        self.custom_radio.toggled.connect(self._update_mode)
        self.builtin_combo.currentIndexChanged.connect(self._builtin_changed)
        self.custom_path.pathChanged.connect(self.templateChanged)
        self.export_button.clicked.connect(self.export_current_builtin)

        self._load_templates()
        self._update_mode()

    def _load_templates(self) -> None:
        try:
            default_id, templates = load_builtin_templates()
        except TemplateServiceError as exc:
            QMessageBox.critical(self, "内置模板错误", str(exc))
            return

        self._templates = {item.template_id: item for item in templates}
        self.builtin_combo.clear()
        default_index = 0
        for index, item in enumerate(templates):
            self.builtin_combo.addItem(item.name, item.template_id)
            if item.template_id == default_id:
                default_index = index
        self.builtin_combo.setCurrentIndex(default_index)
        self._builtin_changed()

    def _builtin_changed(self, *_args: object) -> None:
        item = self.current_builtin_template()
        if item is None:
            self.version_label.setText("")
            return
        self.version_label.setText(f"版本 {item.version}")
        self.builtin_combo.setToolTip(item.description or item.name)
        self.templateChanged.emit(str(item.path))

    def _update_mode(self, *_args: object) -> None:
        builtin = self.builtin_radio.isChecked()
        self.builtin_combo.setEnabled(builtin)
        self.version_label.setEnabled(builtin)
        self.export_button.setEnabled(builtin)
        self.custom_path.setEnabled(not builtin)
        if builtin:
            self.note.setText(
                "内置模板：会按四边距调整外框，并允许修改左上标题和 Draw/Approve/Issue 信息。"
            )
        else:
            self.note.setText(
                "客户模板：会按四边距调整外框和锚定组件位置，但不会修改任何文字、姓名、日期、字体、颜色或表格内容。"
            )
        self.modeChanged.emit(self.mode().value)
        self.templateChanged.emit(str(self.resolved_template_path()))

    def mode(self) -> TemplateMode:
        return TemplateMode.BUILTIN if self.builtin_radio.isChecked() else TemplateMode.CUSTOM

    def builtin_template_id(self) -> str:
        return str(self.builtin_combo.currentData() or "default_sld_frame")

    def current_builtin_template(self) -> BuiltinTemplate | None:
        return self._templates.get(self.builtin_template_id())

    def resolved_template_path(self) -> Path:
        if self.mode() == TemplateMode.CUSTOM:
            return self.custom_path.path()
        item = self.current_builtin_template()
        return item.path if item is not None else get_builtin_template().path

    def export_current_builtin(self) -> None:
        item = self.current_builtin_template()
        if item is None:
            return

        key = f"recent_paths/{self.settings_prefix}/export_template_directory"
        resolved = self.settings_service.resolve_directory(key)
        if resolved.missing_saved_directory is not None:
            QMessageBox.warning(
                self,
                "上次目录不存在",
                f"上次导出模板使用的目录已经不存在：\n"
                f"{resolved.missing_saved_directory}\n\n请重新选择。",
            )
        suggested = resolved.directory / item.file_name
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "导出内置图框模板",
            str(suggested),
            "SLD G Files (*.sln.pic.g);;G Files (*.g)",
        )
        if not destination:
            return
        try:
            exported = export_builtin_template(item.template_id, Path(destination))
        except (OSError, TemplateServiceError) as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.settings_service.set_directory(key, exported.parent)
        QMessageBox.information(self, "导出成功", f"内置模板已导出到：\n{exported}")

    def validate_selection(self) -> bool:
        path = self.resolved_template_path()
        if not path.is_file():
            QMessageBox.warning(
                self,
                "模板无效",
                f"图框模板不存在：\n{path}\n\n请重新选择模板，或恢复使用程序内置模板。",
            )
            return False
        return True
