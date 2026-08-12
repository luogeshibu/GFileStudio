from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QWidget

from g_file_studio.models import MergeSettings
from g_file_studio.engines import merge_engine
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
        self.merge_main_bus = QCheckBox("启用主网母线处理")
        self.merge_main_bus.setToolTip("启用后必须选择单母线或双母线。只检查所选主母线；异常短线 Bus 不再在这里过滤，请统一使用“异常小尺寸图元检测”模块处理。")
        self.main_bus_mode = "single"
        self.main_bus_mode_button = QPushButton("母线类型：未选择")
        self.main_bus_mode_button.setEnabled(False)
        self.main_bus_mode_button.setToolTip("点击选择单母线或双母线；勾选主网母线处理时也会自动弹出选择。")
        self.main_bus_mode_button.clicked.connect(self._choose_main_bus_mode)
        bus_row = QWidget()
        bus_row_layout = QHBoxLayout(bus_row)
        bus_row_layout.setContentsMargins(0, 0, 0, 0)
        bus_row_layout.setSpacing(10)
        bus_row_layout.addWidget(self.merge_main_bus)
        bus_row_layout.addWidget(self.main_bus_mode_button)
        bus_row_layout.addStretch(1)
        self.left = self.spin(300)
        self.top = self.spin(300)
        self.right = self.spin(300)
        self.bottom = self.spin(300)
        self.gap.setToolTip(FIELD_HELP["feeder_gap"])
        for widget in (self.left, self.top, self.right, self.bottom):
            widget.setToolTip(FIELD_HELP["merge_margin"])
        settings_form.addRow(HelpLabel("默认单线图宽度", "每个馈线图的最小占用宽度。实际宽度小于该值时按该值预留；实际宽度超过该值时使用实际宽度。该宽度不包含相邻馈线间隔。"), self.feeder_min_width)
        settings_form.addRow(HelpLabel("主母线处理", "启用后先选择单母线或双母线。单母线只检查 Y 最小的最高有效水平 <Bus>；双母线检查最高母线和同方向下方长度大致相同的第二条母线。选中的母线必须有非空 keyid；相同 keyid 必须连续且合并后处于同一水平线。"), bus_row)
        settings_form.addRow(HelpLabel("相邻图形间隔", FIELD_HELP["feeder_gap"]), self.gap)
        settings_form.addRow(HelpLabel("左边距", FIELD_HELP["merge_margin"]), self.left)
        settings_form.addRow(HelpLabel("上边距", FIELD_HELP["merge_margin"]), self.top)
        settings_form.addRow(HelpLabel("右边距", FIELD_HELP["merge_margin"]), self.right)
        settings_form.addRow(HelpLabel("下边距", FIELD_HELP["merge_margin"]), self.bottom)
        self.layout.addWidget(settings_box)

        output_name_box = QGroupBox("输出文件")
        output_name_form = QFormLayout(output_name_box)
        output_name_form.setHorizontalSpacing(16)
        output_name_form.setVerticalSpacing(10)
        output_name_form.addRow(HelpLabel("输出文件名", FIELD_HELP["output_name"]), self.output_name)
        self.layout.addWidget(output_name_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始合并")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

        self.input_path.pathChanged.connect(self._input_path_changed)
        self.merge_main_bus.toggled.connect(self._on_merge_main_bus_toggled)

    def _input_path_changed(self, text: str) -> None:
        self.file_order.set_input_dir(text)

    def _choose_main_bus_mode(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("选择主母线类型")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("请选择当前参与合并的馈线图属于单母线还是双母线。")
        dialog.setInformativeText(
            "单母线：只检查 Y 值最小的最高有效水平 <Bus>。\n"
            "双母线：检查最高母线，以及同方向下方长度大致相同的第二条有效水平 <Bus>。"
        )
        single_button = dialog.addButton("单母线", QMessageBox.ButtonRole.AcceptRole)
        double_button = dialog.addButton("双母线", QMessageBox.ButtonRole.AcceptRole)
        cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is double_button:
            self.main_bus_mode = "double"
            self.main_bus_mode_button.setText("母线类型：双母线")
        elif clicked is single_button:
            self.main_bus_mode = "single"
            self.main_bus_mode_button.setText("母线类型：单母线")
        else:
            return False
        return True

    def _on_merge_main_bus_toggled(self, checked: bool) -> None:
        self.main_bus_mode_button.setEnabled(checked)
        if not checked:
            self.main_bus_mode_button.setText("母线类型：未选择")
            return
        if not self._choose_main_bus_mode():
            self.merge_main_bus.blockSignals(True)
            self.merge_main_bus.setChecked(False)
            self.merge_main_bus.blockSignals(False)
            self.main_bus_mode_button.setEnabled(False)
            self.main_bus_mode_button.setText("母线类型：未选择")
            return

        names = self.file_order.ordered_file_names()
        input_dir = Path(self.input_path.path())
        if not names:
            QMessageBox.warning(
                self,
                "主母线合并不可用",
                "请先加载并导入需要合并的馈线文件，再启用主母线 keyid 合并。",
                QMessageBox.StandardButton.Ok,
            )
            self.merge_main_bus.setChecked(False)
            return

        paths = [input_dir / name for name in names]
        try:
            metadata = merge_engine.validate_main_bus_keyid_sequence(paths, self.main_bus_mode)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "主母线合并不可用",
                str(exc),
                QMessageBox.StandardButton.Ok,
            )
            self.merge_main_bus.setChecked(False)
            return

        keyid_counts: dict[str, int] = {}
        for item in metadata:
            for keyid in item.get("keyids", []):
                key = str(keyid)
                keyid_counts[key] = keyid_counts.get(key, 0) + 1
        group_text = "\n".join(
            f"- keyid={keyid}：连续出现在 {count} 个馈线中，将按同一水平线合并"
            if count > 1
            else f"- keyid={keyid}：只出现 1 次，保持独立母线"
            for keyid, count in keyid_counts.items()
        )
        QMessageBox.warning(
            self,
            "主母线 keyid 合并确认",
            "请人工确认当前参与合并的馈线确实属于允许共母线的范围。文件名差异只做提醒，程序不会依据文件名、facID 或 facName 禁止你启用该功能。\n\n"
            f"当前选择：{'双母线' if self.main_bus_mode == 'double' else '单母线'}。\n"
            "硬性规则：只检查当前母线类型选中的主母线；选中的 Bus 必须存在非空 keyid；不同 keyid 永远不会连接；同一 keyid 的馈线必须连续排列；最终只有处于同一水平线的同 keyid Bus 才能合并。\n\n"
            + group_text,
            QMessageBox.StandardButton.Ok,
        )

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
            main_bus_mode=self.main_bus_mode,
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
