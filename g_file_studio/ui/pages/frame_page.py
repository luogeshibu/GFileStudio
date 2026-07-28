from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from g_file_studio.models import FrameSettings, PersonSettings, TemplateMode
from g_file_studio.processors.frame_processor import add_drawing_frames
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import (
    HelpLabel,
    InfoBanner,
    InputSourceSelector,
    IntegerInput,
    PathRow,
    PersonEditor,
    TaskPanel,
    TemplateSelector,
)
from g_file_studio.ui.widgets.help_widgets import set_secondary


class FramePage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["frame"]
        super().__init__(
            "添加图框",
            "支持为单个 G 文件或整个目录批量添加并适配 SLD 图框。",
            help_title,
            help_html,
            parent,
        )
        self.banner = InfoBanner(
            "输入可以是单个 G 文件，也可以是 G 文件目录。默认使用程序内置模板；客户模板只调整外框尺寸与组件位置，不修改任何内容。"
        )
        self.layout.addWidget(self.banner)

        path_box = QGroupBox("输入与输出")
        path_layout = QVBoxLayout(path_box)
        path_layout.setContentsMargins(12, 18, 12, 12)
        path_layout.setSpacing(10)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "merged",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要添加图框的 G 文件。",
            directory_tooltip="选择包含多个待添加图框 G 文件的目录；程序只扫描目录第一层。",
            settings_prefix="frame",
            settings_service=self.user_settings,
        )
        path_layout.addWidget(self.source)

        output_form = QFormLayout()
        output_form.setHorizontalSpacing(16)
        output_form.setVerticalSpacing(10)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择添加图框输出目录",
            recent_directory_key="recent_paths/frame/output_directory",
            location_name="添加图框输出目录",
            settings_service=self.user_settings,
        )
        self.output_path.set_path(default_workspace() / "output")
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        output_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        path_layout.addLayout(output_form)
        self.layout.addWidget(path_box)

        template_box = QGroupBox("图框模板")
        template_layout = QVBoxLayout(template_box)
        template_layout.setContentsMargins(12, 18, 12, 12)
        self.template_selector = TemplateSelector(
            settings_prefix="frame",
            settings_service=self.user_settings,
        )
        self.template_selector.modeChanged.connect(self._template_mode_changed)
        template_layout.addWidget(self.template_selector)
        self.layout.addWidget(template_box)

        self.title_box = QGroupBox("内置模板：标题与签字栏")
        title_form = QFormLayout(self.title_box)
        title_form.setHorizontalSpacing(16)
        title_form.setVerticalSpacing(10)
        self.title = QLineEdit()
        self.title.setPlaceholderText("留空时取输入文件名，例如 JED-CTL-ADF")
        self.title.setToolTip(FIELD_HELP["title"])
        self.draw_editor = PersonEditor("Draw")
        self.approve_editor = PersonEditor("Approve")
        self.issue_editor = PersonEditor("Issue")
        title_form.addRow(HelpLabel("左上标题", FIELD_HELP["title"]), self.title)
        title_form.addRow(HelpLabel("Draw", FIELD_HELP["draw"]), self.draw_editor)
        title_form.addRow(HelpLabel("Approve", FIELD_HELP["approve"]), self.approve_editor)
        title_form.addRow(HelpLabel("Issue", FIELD_HELP["issue"]), self.issue_editor)
        self.layout.addWidget(self.title_box)

        layout_box = QGroupBox("图框与输出参数")
        layout_form = QFormLayout(layout_box)
        layout_form.setHorizontalSpacing(16)
        layout_form.setVerticalSpacing(10)
        self.left, self.top, self.right, self.bottom = [self.spin(50) for _ in range(4)]
        for widget in (self.left, self.top, self.right, self.bottom):
            widget.setToolTip(FIELD_HELP["frame_margin"])
        self.suffix = QLineEdit()
        self.suffix.setPlaceholderText("例如 -WITH-FRAME；留空保持原名")
        self.suffix.setToolTip(FIELD_HELP["output_suffix"])
        layout_form.addRow(HelpLabel("图框左边距", FIELD_HELP["frame_margin"]), self.left)
        layout_form.addRow(HelpLabel("图框上边距", FIELD_HELP["frame_margin"]), self.top)
        layout_form.addRow(HelpLabel("图框右边距", FIELD_HELP["frame_margin"]), self.right)
        layout_form.addRow(HelpLabel("图框下边距", FIELD_HELP["frame_margin"]), self.bottom)
        layout_form.addRow(HelpLabel("输出后缀", FIELD_HELP["output_suffix"]), self.suffix)
        self.layout.addWidget(layout_box)

        config_box = QGroupBox("内置模板内容配置")
        config_layout = QVBoxLayout(config_box)
        config_layout.setContentsMargins(12, 18, 12, 12)
        config_buttons = QHBoxLayout()
        self.load_btn = QPushButton("载入 JSON")
        self.save_btn = QPushButton("保存 JSON")
        set_secondary(self.load_btn)
        set_secondary(self.save_btn)
        self.load_btn.clicked.connect(self.load_json)
        self.save_btn.clicked.connect(self.save_json)
        config_buttons.addWidget(self.load_btn)
        config_buttons.addWidget(self.save_btn)
        config_buttons.addStretch(1)
        config_layout.addLayout(config_buttons)
        self.layout.addWidget(config_box)
        self.config_box = config_box

        self.task = TaskPanel()
        self.task.run_button.setText("开始添加图框")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)
        self._template_mode_changed(self.template_selector.mode().value)

    @staticmethod
    def spin(value: int) -> IntegerInput:
        return IntegerInput(value=value, minimum=0, maximum=100000)

    def _template_mode_changed(self, mode_value: str) -> None:
        builtin = TemplateMode(mode_value) == TemplateMode.BUILTIN
        self.title_box.setEnabled(builtin)
        self.config_box.setEnabled(builtin)
        if builtin:
            self.banner.set_text(
                "内置模板会按四边距调整外框，并修改左上标题和 Draw/Approve/Issue 信息。输入支持单文件或目录。"
            )
        else:
            self.banner.set_text(
                "客户自定义模板会按四边距调整外框长度和组件位置，但不会修改任何文字、姓名、日期、字体、颜色或表格内容。输入支持单文件或目录。"
            )

    def settings(self) -> FrameSettings:
        return FrameSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=self.output_path.path(),
            template_file=self.template_selector.resolved_template_path(),
            template_mode=self.template_selector.mode(),
            builtin_template_id=self.template_selector.builtin_template_id(),
            title=self.title.text().strip(),
            draw=PersonSettings(name=self.draw_editor.name(), date=self.draw_editor.date()),
            approve=PersonSettings(name=self.approve_editor.name(), date=self.approve_editor.date()),
            issue=PersonSettings(name=self.issue_editor.name(), date=self.issue_editor.date()),
            frame_left=self.left.value(),
            frame_top=self.top.value(),
            frame_right=self.right.value(),
            frame_bottom=self.bottom.value(),
            output_suffix=self.suffix.text().strip(),
        )

    def _config_dialog_directory(self) -> Path:
        key = "recent_paths/frame/config_directory"
        resolved = self.user_settings.resolve_directory(key)
        if resolved.missing_saved_directory is not None:
            QMessageBox.warning(
                self,
                "上次目录不存在",
                f"上次使用的图框配置目录已经不存在：\n"
                f"{resolved.missing_saved_directory}\n\n请重新选择。",
            )
        return resolved.directory

    def save_json(self) -> None:
        start = self._config_dialog_directory() / "drawing_frame_config.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图框配置", str(start), "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.settings().config_dict(), file, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.user_settings.set_directory("recent_paths/frame/config_directory", Path(path).parent)
        QMessageBox.information(self, "保存成功", f"配置已保存到：\n{path}")

    def load_json(self) -> None:
        start = self._config_dialog_directory()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "载入图框配置",
            str(start),
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                root = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "载入失败", str(exc))
            return

        self.user_settings.set_directory("recent_paths/frame/config_directory", Path(path).parent)
        data = root.get("default", root)
        if not isinstance(data, dict):
            QMessageBox.warning(self, "配置无效", "配置文件 default 必须是 JSON 对象。")
            return
        self.title.setText(str(data.get("title", "")))
        for key, editor in (
            ("draw", self.draw_editor),
            ("approve", self.approve_editor),
            ("issue", self.issue_editor),
        ):
            row = data.get(key, {})
            if isinstance(row, dict):
                editor.set_values(str(row.get("name", "")), str(row.get("date", "")))

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="添加图框输入"):
            return
        if not validate_existing_directory(self, self.output_path.path(), "添加图框输出目录"):
            return
        if not self.template_selector.validate_selection():
            return
        settings = self.settings()
        self.task.start(
            lambda log, progress: add_drawing_frames(settings, log, progress),
            settings.output_dir,
        )
