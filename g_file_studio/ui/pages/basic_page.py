from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QRadioButton,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from g_file_studio.models import (
    BasicOutputConflictAction,
    RmuAction,
    RmuStatusPosition,
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
    BasicRulesEditor,
    ColorRuleRow,
    HelpLabel,
    InfoBanner,
    InputSourceSelector,
    IconUpgradeEditor,
    IntegerInput,
    PathRow,
    TaskPanel,
    WheelSafeComboBox,
)


class BasicPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["basic"]
        super().__init__(
            "基础处理",
            "支持处理单个 G 文件或整个目录；勾选需要的规则后统一点击“开始基础处理”。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "输入可以是单个 G 文件，也可以是 G 文件目录。属性替换、元素删除、"
                "馈线名称定位、连接点修复、图元版本升级以及线路与母线颜色修改，"
                "都在点击“开始基础处理”后统一执行。ID 检查/修复已移到全局“ID 检查与修复”模块。连接点修复仅在勾选时处理 node_area/link；"
                "未勾选时完全跳过。目录模式下每个文件独立处理。"
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
            persistent_path_key="basic/output_directory",
            default_path=default_workspace() / "processed",
            location_name="基础处理输出目录",
            settings_service=self.user_settings,
        )
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        output_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        path_layout.addLayout(output_form)
        self.layout.addWidget(path_box)

        rules_box = QGroupBox("通用处理规则")
        rules_layout = QVBoxLayout(rules_box)
        rules_layout.setContentsMargins(12, 18, 12, 12)
        rules_layout.setSpacing(12)
        self.rules_editor = BasicRulesEditor()
        self.rules_editor.set_input_dir(self.source.path())
        self.source.pathChanged.connect(self.rules_editor.set_input_dir)
        rules_layout.addWidget(self.rules_editor)
        self.layout.addWidget(rules_box)

        self._build_color_options()
        self._build_feeder_title_options()
        self._build_icon_upgrade_options()
        self._build_connection_repair()
        self._restore_options()

        self.task = TaskPanel()
        self.task.run_button.setText("开始基础处理")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

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
        self.rmu_none.setToolTip("保持文件现有 Merge 结构不变。")
        self.rmu_group.setToolTip(
            "单文件模式处理所选文件；目录模式处理第一层全部 G 文件。每个 rect 对应一个 Merge，只组合框内图元。"
        )
        self.rmu_ungroup.setToolTip(
            "删除所有成员中包含 rect 的环网柜 Merge，保留全部成员，并把 rect 调整到柜内设备下层；不删除其他业务 Merge。"
        )
        for button in (self.rmu_none, self.rmu_group, self.rmu_ungroup):
            button.setProperty("optionChoice", True)
            self.rmu_action_group.addButton(button)
            options.addWidget(button)
        options.addStretch(1)
        layout.addLayout(options)

        enhancement_title = QLabel("环网柜增强操作（可多选）")
        enhancement_title.setObjectName("sectionCaption")
        layout.addWidget(enhancement_title)

        self.rmu_smart_frame_color = ColorRuleRow(
            "含 SMART 的环网柜外框",
            "rect + Text[ts=SMART]",
            "#00A651",
        )
        self.rmu_smart_frame_color.enabled_box.setText(
            "修改含 SMART 的环网柜外框颜色"
        )
        self.rmu_smart_frame_color.enabled_box.setToolTip(
            "只识别框内存在 ts=SMART 的 Text 的直属 rect，并修改该 rect 的静态边框色 "
            "lc 和 lcc；SMART 字体颜色以及不含 SMART 的其他环网柜外框均保持不变。"
        )
        layout.addWidget(self.rmu_smart_frame_color)

        # 增强操作按竖列展示；每项仍是独立复选框，可按需多选。
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)
        self.rmu_reposition_channel_status = QCheckBox(
            "移动环网柜红色状态点（channel_status）"
        )
        self.rmu_reposition_channel_status.setProperty("optionChoice", True)
        self.rmu_reposition_channel_status.setToolTip(
            "只处理带 BusDis 的环网柜中 devref 指向 channel_status 的 <Status> 红色状态点。"
            "仅移动该状态点本身，不移动环网柜、母线、设备、标题、连接线或其他图元。"
        )
        self.rmu_channel_status_position = WheelSafeComboBox()
        self.rmu_channel_status_position.setFixedWidth(135)
        for position in RmuStatusPosition:
            self.rmu_channel_status_position.addItem(position.label, position.value)
        self.rmu_channel_status_position.setToolTip(
            "可选择矩形框内四个角或四条边的中点；默认左下角，与示意图中的目标位置一致。"
        )
        self.rmu_channel_status_margin = IntegerInput(5, 0, 1000)
        self.rmu_channel_status_margin.setFixedWidth(90)
        self.rmu_channel_status_margin.setToolTip(
            "状态点与所选矩形框边之间的内边距，默认 5 像素。"
        )
        status_position_label = QLabel("框内位置")
        status_position_label.setObjectName("mutedText")
        status_margin_label = QLabel("距边")
        status_margin_label.setObjectName("mutedText")
        status_margin_unit = QLabel("像素")
        status_margin_unit.setObjectName("mutedText")
        status_row.addWidget(self.rmu_reposition_channel_status)
        status_row.addWidget(status_position_label)
        status_row.addWidget(self.rmu_channel_status_position)
        status_row.addWidget(status_margin_label)
        status_row.addWidget(self.rmu_channel_status_margin)
        status_row.addWidget(status_margin_unit)
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self.rmu_reposition_channel_status.toggled.connect(
            self.rmu_channel_status_position.setEnabled
        )
        self.rmu_reposition_channel_status.toggled.connect(
            self.rmu_channel_status_margin.setEnabled
        )

        self.rmu_remove_bus_frame = QCheckBox(
            "删除带 Bus 的环网柜外框，并将最近标题放到母线上方"
        )
        self.rmu_remove_bus_frame.setProperty("optionChoice", True)
        self.rmu_remove_bus_frame.setToolTip(
            "识别 rect 框内的 Bus，删除该 rect 及对应环网柜 Merge；寻找距离母线最近的业务标题 Text，移动到母线上方并水平居中。"
        )
        layout.addWidget(self.rmu_remove_bus_frame)
        self.layout.addWidget(box)


    def _build_rmu_identification_options(self) -> None:
        box = QGroupBox("环网柜名称与柜型识别")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        description = QLabel(
            "直接解析 G 文件，不使用 OCR。只有 rect 框内同时存在 BusDis、CBreakerDis 和 ZhaiWaiJieDiDaoZha 才认定为环网柜；"
            "柜名只从勾选方向上的绿色 Text 中选择。柜型优先按 Y1/Y2/... 与 Q1/Q2/... 名称计数，名称无法判断时才回退到设备 devref。"
            "柜型始终输出如 2L1T、3L1T；SMART 单独识别成一列，不参与柜型字符串。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.identify_rmu = QCheckBox("启用环网柜名称与柜型识别")
        self.identify_rmu.setProperty("optionChoice", True)
        layout.addWidget(self.identify_rmu)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("柜名可能位置："))
        self.rmu_name_top = QCheckBox("上方")
        self.rmu_name_bottom = QCheckBox("下方")
        self.rmu_name_left = QCheckBox("左侧")
        self.rmu_name_right = QCheckBox("右侧")
        self.rmu_name_top.setChecked(True)
        for item in (self.rmu_name_top, self.rmu_name_bottom, self.rmu_name_left, self.rmu_name_right):
            item.setProperty("optionChoice", True)
            name_row.addWidget(item)
        name_row.addStretch(1)
        layout.addLayout(name_row)

        self.rmu_smart_in_type = QCheckBox("识别 SMART（单独列，不参与柜型）")
        self.rmu_smart_in_type.setProperty("optionChoice", True)
        self.rmu_smart_in_type.setToolTip(
            "启用后在识别结果/CSV 的 SMART 列输出 1 或 0；CabinetType 始终只输出 2L1T、3L1T 等 L/T 柜型。"
        )
        layout.addWidget(self.rmu_smart_in_type)

        for item in (self.rmu_name_top, self.rmu_name_bottom, self.rmu_name_left, self.rmu_name_right, self.rmu_smart_in_type):
            item.setEnabled(False)
            self.identify_rmu.toggled.connect(item.setEnabled)

        self.layout.addWidget(box)

    def _build_color_options(self) -> None:
        box = QGroupBox("线路与母线颜色")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(9)
        description = QLabel(
            "按元素标签修改静态线色，只同步修改 lc（R,G,B）和 lcc（#RRGGBB），不修改填充色、线宽、坐标、ID 或引用。"
            "启用动态颜色的图元仍会修改静态线色，但运行时显示可能被动态规则覆盖。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.feedline_color = ColorRuleRow("馈线", "FeedLine")
        self.connectline_color = ColorRuleRow("连接线", "ConnectLine")
        self.busdis_color = ColorRuleRow("配网母线", "BusDis")
        self.bus_color = ColorRuleRow("主网母线", "Bus")
        for row in (
            self.feedline_color,
            self.connectline_color,
            self.busdis_color,
            self.bus_color,
        ):
            layout.addWidget(row)
        self.layout.addWidget(box)


    def _build_feeder_title_options(self) -> None:
        box = QGroupBox("母线馈线名称定位")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        description = QLabel(
            "识别有效的水平 <Bus>，将上下平行且范围重叠的双母线视为一组；"
            "再依据 Text 的内容、字号和局部几何位置选择唯一可确认的馈线名称，"
            "移动到最上方母线的正上方并水平居中。识别不使用 key_name 或 keyid；"
            "无法唯一判断时跳过。该操作只修改目标 Text 的 x、y，不修改文字内容、字体、颜色、"
            "母线、设备、连接线、ID 或模型关联属性。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.move_feeder_titles_above_bus = QCheckBox("将馈线名称移动到母线上方")
        self.move_feeder_titles_above_bus.setProperty("optionChoice", True)
        self.move_feeder_titles_above_bus.setToolTip(
            "勾选后随‘开始基础处理’执行；不勾选时完全跳过。纯数字、设备标签和说明文字不会移动。"
        )
        layout.addWidget(self.move_feeder_titles_above_bus)
        self.layout.addWidget(box)


    def _build_icon_upgrade_options(self) -> None:
        box = QGroupBox("图元版本升级适配")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        description = QLabel(
            "用于将仍使用旧图元几何参数的主 G 文件适配到新图元库。请分别添加本次涉及的旧图元 G 和新图元 G，"
            "程序按完全相同的文件名强制一一配对，并直接从图元文件读取 w/h、AlignCenter 和 pin(cx,cy)。"
            "任何图元只存在旧版或只存在新版、主体类型/ID 不一致、端口数量变化时都会禁止执行。"
            "处理时保持旧电气对齐中心的绝对位置不变，并把对应连接线端点移动到新图元真实 pin；不需要正常参考主 G。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.upgrade_icon_geometry = QCheckBox("启用图元版本升级适配")
        self.upgrade_icon_geometry.setProperty("optionChoice", True)
        self.upgrade_icon_geometry.setToolTip(
            "只处理主 G 中 devref 命中已配对图元、且当前 w/h 与旧图元尺寸完全一致的实例；"
            "已经是新尺寸的实例会跳过，未知自定义尺寸会告警并跳过。"
        )
        layout.addWidget(self.upgrade_icon_geometry)

        self.icon_upgrade_editor = IconUpgradeEditor()
        self.icon_upgrade_editor.setEnabled(False)
        self.upgrade_icon_geometry.toggled.connect(self.icon_upgrade_editor.setEnabled)
        layout.addWidget(self.icon_upgrade_editor)
        self.layout.addWidget(box)

    def _build_connection_repair(self) -> None:
        box = QGroupBox("连接点修复")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        description = QLabel(
            "用于修复图形中未对齐、缺失或不完整的绿色连接点。程序采用保守增量模式："
            "原有连接和端口编号一律保留；仅对已验证的半像素设备沿 X 方向吸附到整数网格，"
            "不修改任何连接线坐标；随后只补齐缺失的 node_area 和 link。无法唯一判断时跳过，"
            "不会修改设备 Y、ID、文字、颜色、图标、Merge、画布或其他业务属性。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        self.repair_connection_points = QCheckBox("修复连接点（补齐 node_area / link）")
        self.repair_connection_points.setProperty("optionChoice", True)
        self.repair_connection_points.setToolTip(
            "勾选后随“开始基础处理”执行保守连接修复；不勾选时完全跳过。原有连接不会被删除或改号。"
        )
        layout.addWidget(self.repair_connection_points)
        self.layout.addWidget(box)

    def _restore_options(self) -> None:
        self.move_feeder_titles_above_bus.setChecked(
            self.user_settings.get_bool("basic/move_feeder_titles_above_bus", False)
        )
        self.upgrade_icon_geometry.setChecked(
            self.user_settings.get_bool("basic/upgrade_icon_geometry", False)
        )
        self.icon_upgrade_editor.setEnabled(self.upgrade_icon_geometry.isChecked())
        self.repair_connection_points.setChecked(
            self.user_settings.get_bool("basic/repair_connection_points", False)
        )

        color_rows = {
            "feedline": self.feedline_color,
            "connectline": self.connectline_color,
            "busdis": self.busdis_color,
            "bus": self.bus_color,
        }
        for key, row in color_rows.items():
            row.set_color(self.user_settings.get_value(f"basic/colors/{key}", "#0000FF"))
            row.set_enabled(
                self.user_settings.get_bool(f"basic/colors/{key}_enabled", False)
            )

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
        self._persist_options()

    def _persist_options(self) -> None:
        self.user_settings.set_value(
            "basic/move_feeder_titles_above_bus",
            self.move_feeder_titles_above_bus.isChecked(),
        )
        self.user_settings.set_value(
            "basic/upgrade_icon_geometry", self.upgrade_icon_geometry.isChecked()
        )
        self.user_settings.set_value(
            "basic/repair_connection_points", self.repair_connection_points.isChecked()
        )
        color_rows = {
            "feedline": self.feedline_color,
            "connectline": self.connectline_color,
            "busdis": self.busdis_color,
            "bus": self.bus_color,
        }
        for key, row in color_rows.items():
            self.user_settings.set_value(f"basic/colors/{key}", row.color())
            self.user_settings.set_value(
                f"basic/colors/{key}_enabled", row.is_enabled()
            )

    def _validate_common_paths(self) -> bool:
        if not validate_input_source(self, self.source, display_name="基础处理输入"):
            return False
        if not validate_existing_directory(self, self.output_path.path(), "基础处理输出目录"):
            return False
        self.source.persist_current()
        self.output_path.persist_valid_path()
        return True

    def _selected_rmu_action(self) -> RmuAction:
        if self.rmu_group.isChecked():
            return RmuAction.GROUP
        if self.rmu_ungroup.isChecked():
            return RmuAction.UNGROUP
        return RmuAction.NONE

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )

    def _ask_output_conflict_action(
        self,
        conflicts: list[tuple[Path, Path]],
    ) -> BasicOutputConflictAction | None:
        examples = "\n".join(
            f"• {source.name} → {target}"
            for source, target in conflicts[:5]
        )
        if len(conflicts) > 5:
            examples += f"\n• 其余 {len(conflicts) - 5} 个冲突文件……"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("输出文件冲突")
        box.setText(
            f"检测到 {len(conflicts)} 个输出文件与源文件相同，或目标位置已经存在同名文件。"
        )
        box.setInformativeText(
            f"{examples}\n\n请选择本次任务的处理方式。为避免误覆盖，推荐自动添加统一时间戳。"
        )
        timestamp_button = box.addButton(
            "自动添加时间戳（推荐）", QMessageBox.ButtonRole.AcceptRole
        )
        overwrite_button = box.addButton(
            "覆盖原文件/已有文件", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = box.addButton("取消任务", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(timestamp_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is timestamp_button:
            return BasicOutputConflictAction.TIMESTAMP
        if clicked is overwrite_button:
            answer = QMessageBox.question(
                self,
                "确认覆盖",
                "覆盖后原文件或已有输出文件将被替换。程序会先写入临时文件并验证，"
                "验证成功后再原子替换。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                return BasicOutputConflictAction.OVERWRITE
            return None
        if clicked is cancel_button:
            return None
        return None

    def _resolve_output_policy(self) -> tuple[BasicOutputConflictAction, str] | None:
        files = discover_g_inputs(self.source.path(), self.source.mode())
        output_dir = self.output_path.path()
        conflicts: list[tuple[Path, Path]] = []
        for source in files:
            target = output_dir / source.name
            if target.exists() or self._same_path(source, target):
                conflicts.append((source, target))

        if not conflicts:
            return BasicOutputConflictAction.OVERWRITE, ""
        action = self._ask_output_conflict_action(conflicts)
        if action is None:
            return None
        timestamp = make_task_timestamp() if action == BasicOutputConflictAction.TIMESTAMP else ""
        return action, timestamp

    def _settings(self):
        settings = self.rules_editor.build_settings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=self.output_path.path(),
        )
        return settings.model_copy(
            update={
                "upgrade_icon_geometry": self.upgrade_icon_geometry.isChecked(),
                "old_icon_files": self.icon_upgrade_editor.old_paths(),
                "new_icon_files": self.icon_upgrade_editor.new_paths(),
                "repair_connection_points": self.repair_connection_points.isChecked(),
                "move_feeder_titles_above_bus": self.move_feeder_titles_above_bus.isChecked(),
                "change_feedline_color": self.feedline_color.is_enabled(),
                "feedline_color": self.feedline_color.color(),
                "change_connectline_color": self.connectline_color.is_enabled(),
                "connectline_color": self.connectline_color.color(),
                "change_busdis_color": self.busdis_color.is_enabled(),
                "busdis_color": self.busdis_color.color(),
                "change_bus_color": self.bus_color.is_enabled(),
                "bus_color": self.bus_color.color(),
            }
        )

    def run(self) -> None:
        if not self._validate_common_paths():
            return
        if self.upgrade_icon_geometry.isChecked():
            ok, message = self.icon_upgrade_editor.validate_for_run()
            if not ok:
                QMessageBox.warning(self, "图元版本升级适配检查未通过", message)
                return
        try:
            policy = self._resolve_output_policy()
        except Exception as exc:
            QMessageBox.warning(self, "输出检查失败", str(exc))
            return
        if policy is None:
            return

        action, timestamp = policy
        self._persist_options()
        settings = self._settings().model_copy(
            update={
                "output_conflict_action": action,
                "task_timestamp": timestamp,
            }
        )
        self.task.start(
            lambda log, progress: process_basic(settings, log, progress),
            settings.output_dir,
        )
