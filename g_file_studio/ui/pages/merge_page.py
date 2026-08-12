from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLineEdit

from g_file_studio.models import MergeSettings
from g_file_studio.processors.merge_processor import merge_feeders
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory
from g_file_studio.ui.widgets import (
    FileOrderEditor,
    HelpLabel,
    InfoBanner,
    IntegerInput,
    PathRow,
    TaskPanel,
)


class MergePage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["merge"]
        super().__init__(
            "馈线图合并",
            "按用户选择顺序合并多个馈线 G 图，完成垂直对齐、冲突 ID 处理和画布计算。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "输入文件名不解析站点或馈线号。先加载目录，再使用模糊查询选择或全选文件并导入顺序列表；第一行是合并基准。G File Studio 内置图框会在合并前自动移除，客户或来源不明的图框禁止参与。垂直对齐只识别有效水平 <Bus>，不会把 <BusDis> 当作 Bus；无 Bus 时使用最高图元。"
            )
        )

        path_box = QGroupBox("输入与输出")
        path_form = QFormLayout(path_box)
        path_form.setHorizontalSpacing(16)
        path_form.setVerticalSpacing(10)
        self.input_path = PathRow(
            directory=True,
            dialog_title="选择待合并 G 文件目录",
            recent_directory_key="recent_paths/merge/input_directory",
            persistent_path_key="merge/input_directory",
            default_path=default_workspace() / "processed",
            location_name="馈线图合并输入目录",
            settings_service=self.user_settings,
        )
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择合并结果输出目录",
            recent_directory_key="recent_paths/merge/output_directory",
            persistent_path_key="merge/output_directory",
            default_path=default_workspace() / "merged",
            location_name="馈线图合并输出目录",
            settings_service=self.user_settings,
        )
        self.input_path.set_tooltip(FIELD_HELP["merge_input_dir"])
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("留空自动生成 MERGED-时间戳.sln.pic.g；也可手动输入名称")
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
        self.feeder_min_width = self.spin(1000)
        self.merge_main_bus = QCheckBox("合并主母线为一条")
        self.merge_main_bus.setToolTip("合并完成后，仅保留顶部对齐主母线中的第一条 Bus，并将其延伸到最后一张馈线的主母线末端；其余顶部主母线删除，所有原连接关系改接到保留的 Bus。BusDis 和其他非主母线不处理。")
        self.left = self.spin(300)
        self.top = self.spin(300)
        self.right = self.spin(300)
        self.bottom = self.spin(300)
        self.gap.setToolTip(FIELD_HELP["feeder_gap"])
        for widget in (self.left, self.top, self.right, self.bottom):
            widget.setToolTip(FIELD_HELP["merge_margin"])
        settings_form.addRow(HelpLabel("默认单线图宽度", "每个馈线图的最小占用宽度。实际宽度小于该值时按该值预留；实际宽度超过该值时使用实际宽度。该宽度不包含相邻馈线间隔。"), self.feeder_min_width)
        settings_form.addRow(HelpLabel("主母线处理", "勾选后，将所有馈线已对齐的顶部水平 <Bus> 合并成一条连续母线，从第一张馈线延伸到最后一张馈线，并保持所有馈线原有连接关系。"), self.merge_main_bus)
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
    def spin(value: int) -> IntegerInput:
        return IntegerInput(value=value, minimum=0, maximum=100000)

    def settings(self) -> MergeSettings:
        return MergeSettings(
            input_dir=self.input_path.path(),
            output_dir=self.output_path.path(),
            output_name=self.output_name.text(),
            ordered_file_names=self.file_order.ordered_file_names(),
            feeder_gap=self.gap.value(),
            feeder_min_width=self.feeder_min_width.value(),
            merge_main_bus=self.merge_main_bus.isChecked(),
            left_margin=self.left.value(),
            top_margin=self.top.value(),
            right_margin=self.right.value(),
            bottom_margin=self.bottom.value(),
        )

    def save_state(self) -> None:
        self.input_path.persist_current_text()
        self.output_path.persist_current_text()

    def run(self) -> None:
        if not validate_existing_directory(self, self.input_path.path(), "馈线图合并输入目录"):
            return
        if not validate_existing_directory(self, self.output_path.path(), "馈线图合并输出目录"):
            return
        self.input_path.persist_valid_path()
        self.output_path.persist_valid_path()
        self.file_order.set_input_dir(self.input_path.path())
        if not self.file_order.ensure_ready():
            return
        settings = self.settings()
        self.task.start(
            lambda log, progress: merge_feeders(settings, log, progress),
            settings.output_dir,
        )
