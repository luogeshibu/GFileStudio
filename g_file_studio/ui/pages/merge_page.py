from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLineEdit, QSpinBox

from g_file_studio.models import MergeSettings
from g_file_studio.processors.merge_processor import merge_feeders
from g_file_studio.services.paths import default_workspace
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import FileOrderEditor, HelpLabel, InfoBanner, PathRow, TaskPanel


class MergePage(BasePage):
    def __init__(self, parent=None) -> None:
        help_title, help_html = APP_HELP["merge"]
        super().__init__(
            "G 文件合并",
            "合并任意命名的 .sln.pic.g 文件，并由用户自由定义顺序、完成垂直对齐、ID 处理和画布计算。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "输入文件名不解析站点或馈线号。扫描后可用上移、下移、置顶和置底自由定义合并顺序；第一行文件是基准。输入不能包含外框架图。"
            )
        )

        path_box = QGroupBox("输入与输出")
        path_form = QFormLayout(path_box)
        path_form.setHorizontalSpacing(16)
        path_form.setVerticalSpacing(10)
        self.input_path = PathRow()
        self.output_path = PathRow()
        self.input_path.set_path(default_workspace() / "processed")
        self.output_path.set_path(default_workspace() / "merged")
        self.input_path.set_tooltip(FIELD_HELP["merge_input_dir"])
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("留空时生成 MERGED.sln.pic.g")
        self.output_name.setToolTip(FIELD_HELP["output_name"])
        path_form.addRow(HelpLabel("输入目录", FIELD_HELP["merge_input_dir"]), self.input_path)
        path_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        path_form.addRow(HelpLabel("输出文件名", FIELD_HELP["output_name"]), self.output_name)
        self.layout.addWidget(path_box)

        order_box = QGroupBox("输入文件与合并顺序")
        order_form = QFormLayout(order_box)
        order_form.setContentsMargins(12, 18, 12, 12)
        self.file_order = FileOrderEditor()
        self.file_order.set_input_dir(self.input_path.path())
        order_form.addRow(self.file_order)
        self.layout.addWidget(order_box)

        settings_box = QGroupBox("布局参数")
        settings_form = QFormLayout(settings_box)
        settings_form.setHorizontalSpacing(16)
        settings_form.setVerticalSpacing(10)
        self.gap = self.spin(300)
        self.left = self.spin(300)
        self.top = self.spin(300)
        self.right = self.spin(300)
        self.bottom = self.spin(300)
        self.gap.setToolTip(FIELD_HELP["feeder_gap"])
        for widget in (self.left, self.top, self.right, self.bottom):
            widget.setToolTip(FIELD_HELP["merge_margin"])
        settings_form.addRow(HelpLabel("相邻图形间隔", FIELD_HELP["feeder_gap"]), self.gap)
        settings_form.addRow(HelpLabel("左边距", FIELD_HELP["merge_margin"]), self.left)
        settings_form.addRow(HelpLabel("上边距", FIELD_HELP["merge_margin"]), self.top)
        settings_form.addRow(HelpLabel("右边距", FIELD_HELP["merge_margin"]), self.right)
        settings_form.addRow(HelpLabel("下边距", FIELD_HELP["merge_margin"]), self.bottom)
        self.layout.addWidget(settings_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始合并")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

        self.input_path.pathChanged.connect(self._input_path_changed)

    def _input_path_changed(self, text: str) -> None:
        self.file_order.set_input_dir(text)

    @staticmethod
    def spin(value: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(0, 100000)
        widget.setSingleStep(10)
        widget.setValue(value)
        return widget

    def settings(self) -> MergeSettings:
        return MergeSettings(
            input_dir=self.input_path.path(),
            output_dir=self.output_path.path(),
            output_name=self.output_name.text(),
            ordered_file_names=self.file_order.ordered_file_names(),
            feeder_gap=self.gap.value(),
            left_margin=self.left.value(),
            top_margin=self.top.value(),
            right_margin=self.right.value(),
            bottom_margin=self.bottom.value(),
        )

    def run(self) -> None:
        self.file_order.set_input_dir(self.input_path.path())
        if not self.file_order.ensure_ready():
            return
        settings = self.settings()
        self.task.start(
            lambda log, progress: merge_feeders(settings, log, progress),
            settings.output_dir,
        )
