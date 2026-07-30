from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from g_file_studio.models import BasicIdAction
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
            "支持处理单个 G 文件或整个目录；所有已选择功能统一通过“开始基础处理”执行。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "输入可以是单个 G 文件，也可以是 G 文件目录。属性替换、元素删除、重复 ID 检查/修复和环网柜组合都在点击“开始基础处理”后统一执行。目录模式下每个文件独立处理。"
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

        id_box = QGroupBox("ID 校验与修复")
        id_layout = QVBoxLayout(id_box)
        id_layout.setContentsMargins(16, 18, 16, 14)
        id_layout.setSpacing(10)
        id_description = QLabel(
            "请选择本次基础处理的 ID 操作。只检查每个 G 文件自身直属 Layer 图元的重复 ID，"
            "不比较不同文件之间的 ID。检查和修复结果只写入下方当前任务日志，不生成 CSV 报告。"
        )
        id_description.setWordWrap(True)
        id_description.setObjectName("mutedText")
        id_layout.addWidget(id_description)

        id_options = QHBoxLayout()
        id_options.setSpacing(18)
        self.id_action_group = QButtonGroup(self)
        self.id_action_group.setExclusive(True)
        self.id_none = QCheckBox("不处理 ID")
        self.id_check = QCheckBox("检查重复 ID")
        self.id_repair = QCheckBox("检查并修复重复 ID")
        self.id_none.setChecked(True)
        self.id_none.setToolTip("本次基础处理不执行重复 ID 检查。")
        self.id_check.setToolTip("只检查并将结果写入当前日志，不修改 ID。")
        self.id_repair.setToolTip(
            "检查并修复当前文件内部的重复 ID；保留第一处，后续重复图元参考同类元素主流前缀与固定总位数生成新 ID。"
        )
        for button in (self.id_none, self.id_check, self.id_repair):
            button.setProperty("optionChoice", True)
            self.id_action_group.addButton(button)
            id_options.addWidget(button)
        id_options.addStretch(1)
        id_layout.addLayout(id_options)
        self.layout.addWidget(id_box)

        rmu_box = QGroupBox("环网柜图元组合")
        rmu_layout = QVBoxLayout(rmu_box)
        rmu_layout.setContentsMargins(16, 18, 16, 14)
        rmu_layout.setSpacing(10)
        rmu_description = QLabel(
            "启用后，程序会将每个直属 <rect> 识别为一个环网柜矩形框，并为每个 rect 重建一个 <Merge>。"
            "只组合完整位于该矩形框内部的直属图元；任何部分位于框外的连接线、状态图标、标题文字或其他图元都不会进入组合。"
            "文件中已有 Merge 也会按同一严格规则重建，避免旧组合误包含框外图元。"
        )
        rmu_description.setWordWrap(True)
        rmu_description.setObjectName("mutedText")
        rmu_layout.addWidget(rmu_description)
        self.group_rmu = QCheckBox("组合文件中的所有环网柜")
        self.group_rmu.setToolTip(
            "单文件模式处理所选文件；目录模式处理目录第一层的全部 G 文件。每个 rect 对应一个 Merge，框外图元不组合。"
        )
        self.group_rmu.setChecked(False)
        rmu_layout.addWidget(self.group_rmu)
        self.layout.addWidget(rmu_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始基础处理")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()

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

    def _settings(self):
        settings = self.rules_editor.build_settings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=self.output_path.path(),
        )
        return settings.model_copy(
            update={
                "id_action": self._selected_id_action(),
                "group_rmu_elements": self.group_rmu.isChecked(),
            }
        )

    def run(self) -> None:
        if not self._validate_common_paths():
            return
        settings = self._settings()
        self.task.start(
            lambda log, progress: process_basic(settings, log, progress),
            settings.output_dir,
        )
