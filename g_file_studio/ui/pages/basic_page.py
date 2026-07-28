from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QVBoxLayout

from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.services.paths import default_workspace
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import BasicRulesEditor, HelpLabel, InfoBanner, PathRow, TaskPanel


class BasicPage(BasePage):
    def __init__(self, parent=None) -> None:
        help_title, help_html = APP_HELP["basic"]
        super().__init__(
            "基础处理",
            "对一批 G 文件执行可独立开关的通用属性替换和元素删除规则。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "所有删除和属性替换只处理 G 根节点直属 Layer 的直接子元素；G、Theme、Layer 外内容和图元内部子元素保持不变。"
            )
        )

        path_box = QGroupBox("输入与输出")
        path_form = QFormLayout(path_box)
        path_form.setHorizontalSpacing(16)
        path_form.setVerticalSpacing(10)
        self.input_path = PathRow()
        self.output_path = PathRow()
        self.input_path.set_path(default_workspace() / "input")
        self.output_path.set_path(default_workspace() / "processed")
        self.input_path.set_tooltip(FIELD_HELP["input_dir"])
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        path_form.addRow(HelpLabel("输入目录", FIELD_HELP["input_dir"]), self.input_path)
        path_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        self.layout.addWidget(path_box)

        rules_box = QGroupBox("处理规则")
        rules_layout = QVBoxLayout(rules_box)
        rules_layout.setContentsMargins(12, 18, 12, 12)
        rules_layout.setSpacing(12)
        self.rules_editor = BasicRulesEditor()
        self.rules_editor.set_input_dir(self.input_path.path())
        self.input_path.pathChanged.connect(self.rules_editor.set_input_dir)
        rules_layout.addWidget(self.rules_editor)
        self.layout.addWidget(rules_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始基础处理")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def run(self) -> None:
        settings = self.rules_editor.build_settings(
            input_dir=self.input_path.path(),
            output_dir=self.output_path.path(),
        )
        self.task.start(
            lambda log, progress: process_basic(settings, log, progress),
            settings.output_dir,
        )
