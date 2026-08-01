from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from g_file_studio.models import (
    BasicIdAction,
    BasicOutputConflictAction,
    RmuAction,
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
    PathRow,
    TaskPanel,
)


class BasicPage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["basic"]
        super().__init__(
            "基础处理",
            "支持处理单个 G 文件或整个目录；所有已选择功能统一通过“开始基础处理”执行。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "输入可以是单个 G 文件，也可以是 G 文件目录。属性替换、元素删除、重复 ID 检查/修复、"
                "环网柜组合/取消组合，以及线路与母线颜色修改，都在点击“开始基础处理”后统一执行。"
                "目录模式下每个文件独立处理。"
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

        self._build_id_options()
        self._build_rmu_options()
        self._build_color_options()
        self._restore_options()

        self.task = TaskPanel()
        self.task.run_button.setText("开始基础处理")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def _build_id_options(self) -> None:
        box = QGroupBox("ID 校验与修复")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)
        description = QLabel(
            "请选择本次基础处理的 ID 操作。只检查每个 G 文件自身直属 Layer 图元的重复 ID，"
            "不比较不同文件之间的 ID。检查和修复结果只写入下方当前任务日志，不生成 CSV 报告。"
        )
        description.setWordWrap(True)
        description.setObjectName("mutedText")
        layout.addWidget(description)

        options = QHBoxLayout()
        options.setSpacing(12)
        self.id_action_group = QButtonGroup(self)
        self.id_action_group.setExclusive(True)
        self.id_none = QCheckBox("不处理 ID")
        self.id_check = QCheckBox("检查重复 ID")
        self.id_repair = QCheckBox("检查并修复重复 ID")
        self.id_none.setToolTip("本次基础处理不执行重复 ID 检查。")
        self.id_check.setToolTip("只检查并将结果写入当前日志，不修改 ID。")
        self.id_repair.setToolTip(
            "检查并修复当前文件内部的重复 ID；保留第一处，后续重复图元参考同类元素主流前缀与固定总位数生成新 ID。"
        )
        for button in (self.id_none, self.id_check, self.id_repair):
            button.setProperty("optionChoice", True)
            self.id_action_group.addButton(button)
            options.addWidget(button)
        options.addStretch(1)
        layout.addLayout(options)
        self.layout.addWidget(box)

    def _build_rmu_options(self) -> None:
        box = QGroupBox("环网柜组合处理")
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
        self.rmu_none = QCheckBox("不处理环网柜组合")
        self.rmu_group = QCheckBox("组合所有环网柜")
        self.rmu_ungroup = QCheckBox("取消所有环网柜组合")
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

    def _restore_options(self) -> None:
        id_value = self.user_settings.get_value("basic/id_action", BasicIdAction.NONE.value)
        id_buttons = {
            BasicIdAction.NONE.value: self.id_none,
            BasicIdAction.CHECK.value: self.id_check,
            BasicIdAction.REPAIR.value: self.id_repair,
        }
        id_buttons.get(id_value, self.id_none).setChecked(True)

        rmu_value = self.user_settings.get_value("basic/rmu_action", RmuAction.NONE.value)
        rmu_buttons = {
            RmuAction.NONE.value: self.rmu_none,
            RmuAction.GROUP.value: self.rmu_group,
            RmuAction.UNGROUP.value: self.rmu_ungroup,
        }
        rmu_buttons.get(rmu_value, self.rmu_none).setChecked(True)

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
        self.user_settings.set_value("basic/id_action", self._selected_id_action().value)
        self.user_settings.set_value("basic/rmu_action", self._selected_rmu_action().value)
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

    def _selected_id_action(self) -> BasicIdAction:
        if self.id_repair.isChecked():
            return BasicIdAction.REPAIR
        if self.id_check.isChecked():
            return BasicIdAction.CHECK
        return BasicIdAction.NONE

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
                "id_action": self._selected_id_action(),
                "rmu_action": self._selected_rmu_action(),
                "group_rmu_elements": False,
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
