from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from g_file_studio.models import (
    BasicOutputConflictAction, BasicSettings, RmuAction, RmuLedgerInputMode, RmuStatusPosition
)
from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.processors.common import discover_g_inputs
from g_file_studio.services.output_naming import make_task_timestamp
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import (
    ColorRuleRow,
    InfoBanner,
    InputSourceSelector,
    IntegerInput,
    PathRow,
    TaskPanel,
    WheelSafeComboBox,
)
from g_file_studio.ui.widgets.help_widgets import set_secondary


class RmuPage(BasePage):
    """独立环网柜处理页面。

    仅承载原基础处理中的“环网柜图元处理”和“RMU 信息汇总”。
    底层仍调用既有 process_basic / RMU 引擎，避免改变已验证业务算法。
    """

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["rmu"]
        super().__init__(
            "环网柜处理",
            "独立处理环网柜组合/取消组合、增强操作，以及柜名与柜型识别。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "本页面由原“基础处理”中的环网柜功能独立拆分而来。环网柜组合/取消组合、SMART 外框改色、"
                "channel_status 状态点、带 Bus 外框处理，以及柜名/柜型识别算法均保持原逻辑不变；SMART 与 SMR 仅在信息汇总统计层统一归类为智能环网柜。"
            )
        )

        io_box = QGroupBox("输入与输出")
        io_layout = QVBoxLayout(io_box)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要执行环网柜处理的 G 文件。",
            directory_tooltip="选择包含多个待处理 G 文件的目录；程序只扫描目录第一层。",
            settings_prefix="rmu",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择环网柜处理输出目录",
            recent_directory_key="recent_paths/rmu/output_directory",
            persistent_path_key="rmu/output_directory",
            default_path=default_workspace() / "rmu-processed",
            location_name="环网柜处理输出目录",
            settings_service=self.user_settings,
        )
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        row = QHBoxLayout()
        label = QLabel("输出目录")
        label.setMinimumWidth(72)
        row.addWidget(label)
        row.addWidget(self.output_path, 1)
        io_layout.addLayout(row)
        self.layout.addWidget(io_box)

        self._build_rmu_options()
        self._build_rmu_identification_options()
        self._build_rmu_ledger_options()
        self._restore_options()

        self.task = TaskPanel()
        self.task.run_button.setText("开始环网柜处理")
        self.task.run_button.clicked.connect(self.run)

        self.rmu_graphic_report_button = QPushButton("打开图元处理报告")
        self.rmu_summary_report_button = QPushButton("打开 RMU 汇总报告")
        self.rmu_ledger_report_button = QPushButton("打开台账对比报告")
        for button in (
            self.rmu_graphic_report_button,
            self.rmu_summary_report_button,
            self.rmu_ledger_report_button,
        ):
            set_secondary(button)
            button.setVisible(False)
            button.setEnabled(False)
        self.task.buttons_layout.insertWidget(1, self.rmu_graphic_report_button)
        self.task.buttons_layout.insertWidget(2, self.rmu_summary_report_button)
        self.task.buttons_layout.insertWidget(3, self.rmu_ledger_report_button)
        self.rmu_graphic_report_button.clicked.connect(
            lambda: self._open_report("rmu-graphic-processing-report.html", "环网柜图元处理")
        )
        self.rmu_summary_report_button.clicked.connect(
            lambda: self._open_report("rmu-summary-report.html", "RMU 信息汇总")
        )
        self.rmu_ledger_report_button.clicked.connect(
            lambda: self._open_report("rmu-ledger-comparison.html", "RMU 台账对比")
        )
        self.task.resultReceived.connect(self._on_task_result)
        self.layout.addWidget(self.task, 1)
        self._connect_report_button_linkage()
        self._refresh_report_buttons()

    def _build_rmu_options(self) -> None:
        box = QGroupBox("环网柜图元处理")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)
        description = QLabel(
            "“组合所有环网柜”会将每个直属 <rect> 作为环网柜外框，只组合完整位于矩形框内部的直属图元；"
            "任何部分位于框外的连接线、状态图标和文字都不会进入组合。"
            "“取消所有环网柜组合”会删除成员中含 <rect> 的 <Merge> 头元素，并把 rect 外框移动到柜内设备之前，"
            "使外框位于设备下层；坐标、ID、引用和业务属性不变，其他业务 Merge 不受影响。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        options = QHBoxLayout()
        options.setSpacing(12)
        self.rmu_action_group = QButtonGroup(self)
        self.rmu_action_group.setExclusive(True)
        self.rmu_none = QRadioButton("不处理环网柜组合")
        self.rmu_group = QRadioButton("组合所有环网柜")
        self.rmu_ungroup = QRadioButton("取消所有环网柜组合")
        for button in (self.rmu_none, self.rmu_group, self.rmu_ungroup):
            button.setProperty("optionChoice", True)
            self.rmu_action_group.addButton(button)
            options.addWidget(button)
        options.addStretch(1)
        layout.addLayout(options)

        title = QLabel("环网柜增强操作（可多选）")
        title.setObjectName("sectionCaption")
        layout.addWidget(title)

        self.rmu_smart_frame_color = ColorRuleRow("含 SMART 的环网柜外框", "rect + Text[ts=SMART]", "#00A651")
        self.rmu_smart_frame_color.enabled_box.setText("修改含 SMART 的环网柜外框颜色")
        layout.addWidget(self.rmu_smart_frame_color)

        self.rmu_smr_frame_color = ColorRuleRow("含 SMR 的最近环网柜外框", "Text[ts=SMR] → 最近有效 RMU rect", "#FF0000")
        self.rmu_smr_frame_color.enabled_box.setText("修改含 SMR 的环网柜外框颜色")
        layout.addWidget(self.rmu_smr_frame_color)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.rmu_reposition_channel_status = QCheckBox("移动环网柜红色状态点（channel_status）")
        self.rmu_reposition_channel_status.setProperty("optionChoice", True)
        self.rmu_channel_status_position = WheelSafeComboBox()
        self.rmu_channel_status_position.setFixedWidth(135)
        for position in RmuStatusPosition:
            self.rmu_channel_status_position.addItem(position.label, position.value)
        self.rmu_channel_status_margin = IntegerInput(5, 0, 1000)
        self.rmu_channel_status_margin.setFixedWidth(90)
        status_row.addWidget(self.rmu_reposition_channel_status)
        status_row.addWidget(QLabel("框内位置"))
        status_row.addWidget(self.rmu_channel_status_position)
        status_row.addWidget(QLabel("距边"))
        status_row.addWidget(self.rmu_channel_status_margin)
        status_row.addWidget(QLabel("像素"))
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self.rmu_reposition_channel_status.toggled.connect(self.rmu_channel_status_position.setEnabled)
        self.rmu_reposition_channel_status.toggled.connect(self.rmu_channel_status_margin.setEnabled)

        self.rmu_remove_bus_frame = QCheckBox("删除带 Bus 的环网柜外框，并将最近标题放到母线上方")
        self.rmu_remove_bus_frame.setProperty("optionChoice", True)
        layout.addWidget(self.rmu_remove_bus_frame)
        self.layout.addWidget(box)

    def _build_rmu_identification_options(self) -> None:
        box = QGroupBox("RMU 信息汇总")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)
        description = QLabel(
            "直接解析 G 文件，不使用 OCR。只有 rect 框内同时存在 BusDis、CBreakerDis 和 ZhaiWaiJieDiDaoZha 才认定为环网柜；"
            "柜名严格只在用户勾选方向中寻找：单候选直接使用；同一最近文字组存在多个候选时才优先绿色文字。"
            "柜型优先按 Y1/Y2/... 与 Q1/Q2/... 名称计数，名称无法判断时才回退到设备 devref。SMART 与 SMR 统一统计为“智能环网柜”，并保留识别来源。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.identify_rmu = QCheckBox("启用 RMU 信息汇总")
        self.identify_rmu.setProperty("optionChoice", True)
        layout.addWidget(self.identify_rmu)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("柜名可能位置："))
        self.rmu_name_top = QCheckBox("上方")
        self.rmu_name_bottom = QCheckBox("下方")
        self.rmu_name_left = QCheckBox("左侧")
        self.rmu_name_right = QCheckBox("右侧")
        for item in (self.rmu_name_top, self.rmu_name_bottom, self.rmu_name_left, self.rmu_name_right):
            item.setProperty("optionChoice", True)
            name_row.addWidget(item)
        name_row.addStretch(1)
        layout.addLayout(name_row)

        self.rmu_smart_in_type = QCheckBox("启用智能环网柜分类（SMART / SMR）")
        self.rmu_smart_in_type.setProperty("optionChoice", True)
        self.rmu_smart_in_type.setToolTip(
            "RMU 信息汇总始终统计全部有效环网柜。勾选后额外将 SMART/SMR 统一归类为智能环网柜；"
            "不勾选时仅汇总 RMU 名称、柜型、重复和识别异常，不进行智能/普通分类。"
        )
        layout.addWidget(self.rmu_smart_in_type)
        classify_note = QLabel(
            "无论是否启用智能分类，都会统计全部有效 RMU，并检查重复名称/ID、柜名或柜型未识别、"
            "中低置信度等异常；这些信息会在 RMU 汇总 HTML 报告中重点提示。"
        )
        classify_note.setWordWrap(True)
        classify_note.setObjectName("mutedText")
        layout.addWidget(classify_note)
        for item in (self.rmu_name_top, self.rmu_name_bottom, self.rmu_name_left, self.rmu_name_right, self.rmu_smart_in_type):
            self.identify_rmu.toggled.connect(item.setEnabled)
        self.layout.addWidget(box)

    def _build_rmu_ledger_options(self) -> None:
        box = QGroupBox("现有 RMU 台账对比（可选）")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        description = QLabel(
            "将用户现有 RMU 台账与 G 文件识别结果进行对比。RMU 名称为必填匹配键；柜型、是否智能为可选字段。"
            "SMART 与 SMR 在对比时统一视为“智能环网柜”。原有 G 图形识别算法不因启用台账对比而改变。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.compare_rmu_ledger = QCheckBox("启用现有 RMU 台账对比")
        self.compare_rmu_ledger.setProperty("optionChoice", True)
        layout.addWidget(self.compare_rmu_ledger)

        modes = QHBoxLayout()
        modes.addWidget(QLabel("台账输入方式："))
        self.rmu_ledger_mode_group = QButtonGroup(self)
        self.rmu_ledger_mode_group.setExclusive(True)
        self.rmu_ledger_file_mode = QRadioButton("Excel / CSV 导入")
        self.rmu_ledger_paste_mode = QRadioButton("直接粘贴表格")
        self.rmu_ledger_names_mode = QRadioButton("只粘贴 RMU 名称")
        for button in (self.rmu_ledger_file_mode, self.rmu_ledger_paste_mode, self.rmu_ledger_names_mode):
            button.setProperty("optionChoice", True)
            self.rmu_ledger_mode_group.addButton(button)
            modes.addWidget(button)
        modes.addStretch(1)
        layout.addLayout(modes)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("台账文件"))
        self.rmu_ledger_file = PathRow(
            directory=False,
            file_filter="RMU Ledger (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)",
            dialog_title="选择 RMU 台账",
            recent_directory_key="recent_paths/rmu/ledger_directory",
            persistent_path_key="rmu/ledger_file",
            location_name="RMU 台账文件",
            settings_service=self.user_settings,
        )
        file_row.addWidget(self.rmu_ledger_file, 1)
        layout.addLayout(file_row)

        self.rmu_ledger_text = QPlainTextEdit()
        self.rmu_ledger_text.setMinimumHeight(120)
        self.rmu_ledger_text.setMaximumHeight(180)
        self.rmu_ledger_text.setPlaceholderText(
            "直接粘贴表格：\nRMU名称\tRMU类型\t是否智能\n30839\t2L1T\t是\n30864\t3L1T\t否\n\n"
            "或选择“只粘贴 RMU 名称”后每行一个名称。"
        )
        layout.addWidget(self.rmu_ledger_text)

        note = QLabel("Excel/CSV 支持列：RMU名称（必填）、RMU类型（可选）、是否智能（可选）。没有表头时默认第1/2/3列分别作为名称/类型/智能。")
        note.setWordWrap(True)
        note.setObjectName("mutedText")
        layout.addWidget(note)

        self.compare_rmu_ledger.toggled.connect(self._refresh_ledger_controls)
        self.compare_rmu_ledger.toggled.connect(lambda checked: self.identify_rmu.setChecked(True) if checked else None)
        self.compare_rmu_ledger.toggled.connect(lambda checked: self.rmu_smart_in_type.setChecked(True) if checked else None)
        self.rmu_ledger_file_mode.toggled.connect(self._refresh_ledger_controls)
        self.rmu_ledger_paste_mode.toggled.connect(self._refresh_ledger_controls)
        self.rmu_ledger_names_mode.toggled.connect(self._refresh_ledger_controls)
        self.layout.addWidget(box)

    def _graphic_processing_enabled(self) -> bool:
        return (
            self._selected_rmu_action() != RmuAction.NONE
            or self.rmu_smart_frame_color.is_enabled()
            or self.rmu_smr_frame_color.is_enabled()
            or self.rmu_reposition_channel_status.isChecked()
            or self.rmu_remove_bus_frame.isChecked()
        )

    def _connect_report_button_linkage(self) -> None:
        for button in (self.rmu_none, self.rmu_group, self.rmu_ungroup):
            button.toggled.connect(self._refresh_report_buttons)
        self.rmu_smart_frame_color.enabled_box.toggled.connect(self._refresh_report_buttons)
        self.rmu_smr_frame_color.enabled_box.toggled.connect(self._refresh_report_buttons)
        self.rmu_reposition_channel_status.toggled.connect(self._refresh_report_buttons)
        self.rmu_remove_bus_frame.toggled.connect(self._refresh_report_buttons)
        self.identify_rmu.toggled.connect(self._refresh_report_buttons)
        self.compare_rmu_ledger.toggled.connect(self._refresh_report_buttons)

    def _refresh_report_buttons(self) -> None:
        output_dir = self.output_path.path()
        mapping = (
            (self.rmu_graphic_report_button, self._graphic_processing_enabled(), "rmu-graphic-processing-report.html"),
            (self.rmu_summary_report_button, self.identify_rmu.isChecked(), "rmu-summary-report.html"),
            (self.rmu_ledger_report_button, self.compare_rmu_ledger.isChecked(), "rmu-ledger-comparison.html"),
        )
        for button, visible, file_name in mapping:
            button.setVisible(bool(visible))
            button.setEnabled(bool(visible and (output_dir / file_name).exists()))

    def _on_task_result(self, _result) -> None:
        self._refresh_report_buttons()

    def _open_report(self, file_name: str, title: str) -> None:
        path = self.output_path.path() / file_name
        if not path.exists():
            QMessageBox.information(self, "暂无报告", f"尚未生成“{title}”HTML 报告，请先执行对应模块。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _refresh_ledger_controls(self) -> None:
        enabled = self.compare_rmu_ledger.isChecked()
        for button in (self.rmu_ledger_file_mode, self.rmu_ledger_paste_mode, self.rmu_ledger_names_mode):
            button.setEnabled(enabled)
        file_mode = enabled and self.rmu_ledger_file_mode.isChecked()
        text_mode = enabled and not self.rmu_ledger_file_mode.isChecked()
        self.rmu_ledger_file.setEnabled(file_mode)
        self.rmu_ledger_text.setEnabled(text_mode)

    def _selected_ledger_mode(self) -> RmuLedgerInputMode:
        if self.rmu_ledger_paste_mode.isChecked():
            return RmuLedgerInputMode.PASTE_TABLE
        if self.rmu_ledger_names_mode.isChecked():
            return RmuLedgerInputMode.NAME_LIST
        return RmuLedgerInputMode.FILE

    def _selected_rmu_action(self) -> RmuAction:
        if self.rmu_group.isChecked():
            return RmuAction.GROUP
        if self.rmu_ungroup.isChecked():
            return RmuAction.UNGROUP
        return RmuAction.NONE

    def _restore_options(self) -> None:
        value = self.user_settings.get_value("basic/rmu_action", RmuAction.NONE.value)
        {RmuAction.NONE.value: self.rmu_none, RmuAction.GROUP.value: self.rmu_group, RmuAction.UNGROUP.value: self.rmu_ungroup}.get(value, self.rmu_none).setChecked(True)
        self.rmu_smart_frame_color.set_color(self.user_settings.get_value("basic/rmu/smart_frame_color", "#00A651"))
        self.rmu_smart_frame_color.set_enabled(self.user_settings.get_bool("basic/rmu/smart_frame_color_enabled", False))
        self.rmu_smr_frame_color.set_color(self.user_settings.get_value("basic/rmu/smr_frame_color", "#FF0000"))
        self.rmu_smr_frame_color.set_enabled(self.user_settings.get_bool("basic/rmu/smr_frame_color_enabled", False))
        self.rmu_reposition_channel_status.setChecked(self.user_settings.get_bool("basic/rmu/reposition_channel_status", False))
        pos = self.user_settings.get_value("basic/rmu/channel_status_position", RmuStatusPosition.BOTTOM_LEFT.value)
        idx = self.rmu_channel_status_position.findData(pos)
        self.rmu_channel_status_position.setCurrentIndex(idx if idx >= 0 else 0)
        self.rmu_channel_status_margin.setValue(self.user_settings.get_int("basic/rmu/channel_status_inner_margin", 5))
        self.rmu_channel_status_position.setEnabled(self.rmu_reposition_channel_status.isChecked())
        self.rmu_channel_status_margin.setEnabled(self.rmu_reposition_channel_status.isChecked())
        self.rmu_remove_bus_frame.setChecked(self.user_settings.get_bool("basic/rmu/remove_bus_frame", False))
        self.identify_rmu.setChecked(self.user_settings.get_bool("basic/rmu/identify_name_type", False))
        self.rmu_name_top.setChecked(self.user_settings.get_bool("basic/rmu/name_top", True))
        self.rmu_name_bottom.setChecked(self.user_settings.get_bool("basic/rmu/name_bottom", False))
        self.rmu_name_left.setChecked(self.user_settings.get_bool("basic/rmu/name_left", False))
        self.rmu_name_right.setChecked(self.user_settings.get_bool("basic/rmu/name_right", False))
        self.rmu_smart_in_type.setChecked(self.user_settings.get_bool("basic/rmu/smart_in_type", False))
        self.compare_rmu_ledger.setChecked(self.user_settings.get_bool("rmu/ledger/compare_enabled", False))
        ledger_mode = self.user_settings.get_value("rmu/ledger/input_mode", RmuLedgerInputMode.FILE.value)
        {
            RmuLedgerInputMode.FILE.value: self.rmu_ledger_file_mode,
            RmuLedgerInputMode.PASTE_TABLE.value: self.rmu_ledger_paste_mode,
            RmuLedgerInputMode.NAME_LIST.value: self.rmu_ledger_names_mode,
        }.get(ledger_mode, self.rmu_ledger_file_mode).setChecked(True)
        self.rmu_ledger_text.setPlainText(self.user_settings.get_value("rmu/ledger/text", ""))
        self._refresh_ledger_controls()
        enabled = self.identify_rmu.isChecked()
        for item in (self.rmu_name_top, self.rmu_name_bottom, self.rmu_name_left, self.rmu_name_right, self.rmu_smart_in_type):
            item.setEnabled(enabled)

    def _persist_options(self) -> None:
        self.user_settings.set_value("basic/rmu_action", self._selected_rmu_action().value)
        self.user_settings.set_value("basic/rmu/smart_frame_color", self.rmu_smart_frame_color.color())
        self.user_settings.set_value("basic/rmu/smart_frame_color_enabled", self.rmu_smart_frame_color.is_enabled())
        self.user_settings.set_value("basic/rmu/smr_frame_color", self.rmu_smr_frame_color.color())
        self.user_settings.set_value("basic/rmu/smr_frame_color_enabled", self.rmu_smr_frame_color.is_enabled())
        self.user_settings.set_value("basic/rmu/reposition_channel_status", self.rmu_reposition_channel_status.isChecked())
        self.user_settings.set_value("basic/rmu/channel_status_position", self.rmu_channel_status_position.currentData())
        self.user_settings.set_value("basic/rmu/channel_status_inner_margin", self.rmu_channel_status_margin.value())
        self.user_settings.set_value("basic/rmu/remove_bus_frame", self.rmu_remove_bus_frame.isChecked())
        self.user_settings.set_value("basic/rmu/identify_name_type", self.identify_rmu.isChecked())
        self.user_settings.set_value("basic/rmu/name_top", self.rmu_name_top.isChecked())
        self.user_settings.set_value("basic/rmu/name_bottom", self.rmu_name_bottom.isChecked())
        self.user_settings.set_value("basic/rmu/name_left", self.rmu_name_left.isChecked())
        self.user_settings.set_value("basic/rmu/name_right", self.rmu_name_right.isChecked())
        self.user_settings.set_value("basic/rmu/smart_in_type", self.rmu_smart_in_type.isChecked())
        self.user_settings.set_value("rmu/ledger/compare_enabled", self.compare_rmu_ledger.isChecked())
        self.user_settings.set_value("rmu/ledger/input_mode", self._selected_ledger_mode().value)
        self.user_settings.set_value("rmu/ledger/text", self.rmu_ledger_text.toPlainText())
        self.rmu_ledger_file.persist_current_text()

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(str(right.resolve(strict=False)))

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="环网柜处理输入"):
            return
        output_dir = self.output_path.path()
        if not validate_existing_directory(self, output_dir, "环网柜处理输出目录"):
            return
        if self.identify_rmu.isChecked() and not any((self.rmu_name_top.isChecked(), self.rmu_name_bottom.isChecked(), self.rmu_name_left.isChecked(), self.rmu_name_right.isChecked())):
            QMessageBox.warning(self, "RMU 信息汇总设置", "柜名位置至少选择上方、下方、左侧或右侧中的一个。")
            return
        if self.compare_rmu_ledger.isChecked():
            if not self.identify_rmu.isChecked():
                QMessageBox.warning(self, "RMU 台账设置", "启用台账对比时必须启用 RMU 信息汇总。")
                return
            if self._selected_ledger_mode() == RmuLedgerInputMode.FILE and not self.rmu_ledger_file.path().is_file():
                QMessageBox.warning(self, "RMU 台账设置", "请选择有效的 Excel / CSV 台账文件。")
                return
            if self._selected_ledger_mode() != RmuLedgerInputMode.FILE and not self.rmu_ledger_text.toPlainText().strip():
                QMessageBox.warning(self, "RMU 台账设置", "请粘贴 RMU 台账内容。")
                return

        self.source.persist_current()
        self.output_path.persist_valid_path()
        files = discover_g_inputs(self.source.path(), self.source.mode())
        conflicts = [p for p in files if (output_dir / p.name).exists() or self._same_path(p, output_dir / p.name)]
        action = BasicOutputConflictAction.OVERWRITE
        timestamp = ""
        if conflicts:
            answer = QMessageBox.question(
                self,
                "输出文件冲突",
                f"检测到 {len(conflicts)} 个目标文件已存在或与源文件相同。是否自动添加时间戳后输出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            action = BasicOutputConflictAction.TIMESTAMP
            timestamp = make_task_timestamp()

        self._persist_options()
        settings = BasicSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=output_dir,
            rmu_action=self._selected_rmu_action(),
            change_smart_rmu_frame_color=self.rmu_smart_frame_color.is_enabled(),
            smart_rmu_frame_color=self.rmu_smart_frame_color.color(),
            change_smr_rmu_frame_color=self.rmu_smr_frame_color.is_enabled(),
            smr_rmu_frame_color=self.rmu_smr_frame_color.color(),
            reposition_channel_status=self.rmu_reposition_channel_status.isChecked(),
            channel_status_position=RmuStatusPosition(self.rmu_channel_status_position.currentData()),
            channel_status_inner_margin=self.rmu_channel_status_margin.value(),
            remove_bus_rmu_frame_and_reposition_title=self.rmu_remove_bus_frame.isChecked(),
            identify_rmu_name_and_type=self.identify_rmu.isChecked(),
            rmu_name_top=self.rmu_name_top.isChecked(),
            rmu_name_bottom=self.rmu_name_bottom.isChecked(),
            rmu_name_left=self.rmu_name_left.isChecked(),
            rmu_name_right=self.rmu_name_right.isChecked(),
            rmu_smart_in_type=(self.rmu_smart_in_type.isChecked() or self.compare_rmu_ledger.isChecked()),
            export_rmu_identification_csv=True,
            compare_rmu_ledger=self.compare_rmu_ledger.isChecked(),
            rmu_ledger_input_mode=self._selected_ledger_mode(),
            rmu_ledger_file=(self.rmu_ledger_file.path() if self._selected_ledger_mode() == RmuLedgerInputMode.FILE else None),
            rmu_ledger_text=self.rmu_ledger_text.toPlainText(),
            output_conflict_action=action,
            task_timestamp=timestamp,
        )
        self.task.start(lambda log, progress: process_basic(settings, log, progress), output_dir)

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
        self.rmu_ledger_file.persist_current_text()
        self._persist_options()
