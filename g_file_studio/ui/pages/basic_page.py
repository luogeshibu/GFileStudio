from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QVBoxLayout

from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import (
    BasicRulesEditor,
    HelpLabel,
    InfoBanner,
    InputSourceSelector,
    PathRow,
    TaskPanel,
)


class BasicPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["basic"]
        super().__init__(
            "基础处理",
            "支持处理单个 G 文件或整个目录，并执行通用属性替换和元素删除规则。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "输入可以是单个 G 文件，也可以是 G 文件目录。所有删除和属性替换只处理 G 根节点直属 Layer 的直接子元素。"
            )
        )

        path_box = QGroupBox("输入与输出")
        path_layout = QVBoxLayout(path_box)
        path_layout.setContentsMargins(12, 18, 12, 12)
        path_layout.setSpacing(10)

        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要执行基础处理的 G 文件。",
            directory_tooltip="选择包含多个待处理 G 文件的目录；程序只扫描目录第一层。",
            settings_prefix="basic",
            settings_service=self.user_settings,
        )
        path_layout.addWidget(self.source)

        output_form = QFormLayout()
        output_form.setHorizontalSpacing(16)
        output_form.setVerticalSpacing(10)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择基础处理输出目录",
            recent_directory_key="recent_paths/basic/output_directory",
            location_name="基础处理输出目录",
            settings_service=self.user_settings,
        )
        self.output_path.set_path(default_workspace() / "processed")
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        output_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        path_layout.addLayout(output_form)
        self.layout.addWidget(path_box)

        rules_box = QGroupBox("处理规则")
        rules_layout = QVBoxLayout(rules_box)
        rules_layout.setContentsMargins(12, 18, 12, 12)
        rules_layout.setSpacing(12)
        self.rules_editor = BasicRulesEditor()
        self.rules_editor.set_input_dir(self.source.path())
        self.source.pathChanged.connect(self.rules_editor.set_input_dir)
        rules_layout.addWidget(self.rules_editor)
        self.layout.addWidget(rules_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始基础处理")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="基础处理输入"):
            return
        if not validate_existing_directory(self, self.output_path.path(), "基础处理输出目录"):
            return

        settings = self.rules_editor.build_settings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=self.output_path.path(),
        )
        self.task.start(
            lambda log, progress: process_basic(settings, log, progress),
            settings.output_dir,
        )
