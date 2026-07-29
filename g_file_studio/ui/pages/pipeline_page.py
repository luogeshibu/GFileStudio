from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLineEdit, QVBoxLayout

from g_file_studio.models import (
    FrameSettings,
    InputMode,
    MarginSettings,
    MergeSettings,
    PersonSettings,
    PipelineSettings,
    TemplateMode,
)
from g_file_studio.processors.pipeline_processor import run_pipeline
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.temp_workspace_service import TempWorkspaceService
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import (
    BasicRulesEditor,
    FileOrderEditor,
    HelpLabel,
    InfoBanner,
    InputSourceSelector,
    IntegerInput,
    PathRow,
    PersonEditor,
    TaskPanel,
    TemplateSelector,
)


class PipelinePage(BasePage):
    def __init__(
        self,
        temp_workspace: TempWorkspaceService,
        user_settings: UserSettingsService,
        parent=None,
    ) -> None:
        self.temp_workspace = temp_workspace
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["pipeline"]
        super().__init__(
            "一键处理",
            "选择单个文件或目录，程序自动管理中间文件并只写出最终结果。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "用户只选择原始输入和最终输出。中间结果保存在 AppData 缓存中，开始新任务、正常关闭程序和下次启动时自动清理。"
            )
        )

        path_box = QGroupBox("原始输入与最终输出")
        path_layout = QVBoxLayout(path_box)
        path_layout.setContentsMargins(12, 18, 12, 12)
        path_layout.setSpacing(10)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            settings_prefix="pipeline",
            settings_service=self.user_settings,
        )
        self.output = PathRow(
            directory=True,
            dialog_title="选择一键处理最终输出目录",
            recent_directory_key="recent_paths/pipeline/output_directory",
            persistent_path_key="pipeline/output_directory",
            default_path=default_workspace() / "output",
            location_name="一键处理最终输出目录",
            settings_service=self.user_settings,
        )
        self.output.set_tooltip(FIELD_HELP["output_dir"])
        path_layout.addWidget(self.source)
        output_form = QFormLayout()
        output_form.addRow(HelpLabel("最终输出目录", FIELD_HELP["output_dir"]), self.output)
        path_layout.addLayout(output_form)
        self.layout.addWidget(path_box)

        stage_box = QGroupBox("处理阶段")
        stage_layout = QVBoxLayout(stage_box)
        stage_layout.setContentsMargins(14, 18, 14, 12)
        stage_layout.setSpacing(9)
        self.run_basic = QCheckBox("1. 基础处理：执行通用属性替换和元素删除规则")
        self.run_merge = QCheckBox("2. G 文件合并：目录模式下按用户定义顺序合并")
        self.run_margin = QCheckBox("3. 图形边距调整：主体默认距离画布四边各 500")
        self.run_frame = QCheckBox("4. 添加图框：使用内置模板或客户自定义模板")
        for check in (self.run_basic, self.run_merge, self.run_margin, self.run_frame):
            check.setChecked(True)
            stage_layout.addWidget(check)
        self.layout.addWidget(stage_box)

        self.basic_box = QGroupBox("基础处理规则")
        basic_layout = QVBoxLayout(self.basic_box)
        basic_layout.setContentsMargins(12, 18, 12, 12)
        self.basic_rules = BasicRulesEditor()
        self.basic_rules.set_input_dir(self.source.path())
        basic_layout.addWidget(self.basic_rules)
        self.layout.addWidget(self.basic_box)

        self.merge_box = QGroupBox("G 文件合并参数与顺序")
        merge_layout = QVBoxLayout(self.merge_box)
        merge_layout.setContentsMargins(12, 18, 12, 12)
        merge_layout.setSpacing(14)
        merge_form = QFormLayout()
        merge_form.setHorizontalSpacing(16)
        merge_form.setVerticalSpacing(10)
        self.merge_output_name = QLineEdit()
        self.merge_output_name.setPlaceholderText("留空时生成 MERGED.sln.pic.g")
        self.gap = self.spin(300)
        self.left_margin = self.spin(300)
        self.top_margin = self.spin(300)
        self.right_margin = self.spin(300)
        self.bottom_margin = self.spin(300)
        merge_form.addRow(HelpLabel("合并输出文件名", FIELD_HELP["output_name"]), self.merge_output_name)
        merge_form.addRow(HelpLabel("图形间隔", FIELD_HELP["feeder_gap"]), self.gap)
        merge_form.addRow(HelpLabel("合并左边距", FIELD_HELP["merge_margin"]), self.left_margin)
        merge_form.addRow(HelpLabel("合并上边距", FIELD_HELP["merge_margin"]), self.top_margin)
        merge_form.addRow(HelpLabel("合并右边距", FIELD_HELP["merge_margin"]), self.right_margin)
        merge_form.addRow(HelpLabel("合并下边距", FIELD_HELP["merge_margin"]), self.bottom_margin)
        merge_layout.addLayout(merge_form)
        self.merge_order = FileOrderEditor()
        self.merge_order.set_input_dir(self.source.path())
        merge_layout.addWidget(self.merge_order)
        self.layout.addWidget(self.merge_box)

        self.margin_box = QGroupBox("图形边距调整参数")
        margin_form = QFormLayout(self.margin_box)
        margin_form.setHorizontalSpacing(16)
        margin_form.setVerticalSpacing(10)
        self.content_left = self.spin(500)
        self.content_top = self.spin(500)
        self.content_right = self.spin(500)
        self.content_bottom = self.spin(500)
        for widget in (
            self.content_left,
            self.content_top,
            self.content_right,
            self.content_bottom,
        ):
            widget.setToolTip(FIELD_HELP["content_margin"])
        margin_form.addRow(HelpLabel("主体左边距", FIELD_HELP["content_margin"]), self.content_left)
        margin_form.addRow(HelpLabel("主体上边距", FIELD_HELP["content_margin"]), self.content_top)
        margin_form.addRow(HelpLabel("主体右边距", FIELD_HELP["content_margin"]), self.content_right)
        margin_form.addRow(HelpLabel("主体下边距", FIELD_HELP["content_margin"]), self.content_bottom)
        self.layout.addWidget(self.margin_box)
        self.layout.addWidget(
            InfoBanner(
                "合并阶段会自动移除 G File Studio 内置图框后再合并；客户图框或来源不明的图框禁止参与合并。图形边距调整阶段仍会保留并同步调整已存在的内置图框。"
            )
        )

        self.frame_box = QGroupBox("图框模板与输出参数")
        frame_layout = QVBoxLayout(self.frame_box)
        frame_layout.setContentsMargins(12, 18, 12, 12)
        frame_layout.setSpacing(12)
        self.template_selector = TemplateSelector(
            settings_prefix="pipeline",
            settings_service=self.user_settings,
        )
        frame_layout.addWidget(self.template_selector)

        self.frame_content_box = QGroupBox("内置模板：标题与签字栏")
        content_form = QFormLayout(self.frame_content_box)
        self.title = QLineEdit()
        self.title.setPlaceholderText("留空时取最终 G 文件名")
        self.draw_editor = PersonEditor("Draw")
        self.approve_editor = PersonEditor("Approve")
        self.issue_editor = PersonEditor("Issue")
        content_form.addRow(HelpLabel("标题覆盖", FIELD_HELP["title"]), self.title)
        content_form.addRow(HelpLabel("Draw", FIELD_HELP["draw"]), self.draw_editor)
        content_form.addRow(HelpLabel("Approve", FIELD_HELP["approve"]), self.approve_editor)
        content_form.addRow(HelpLabel("Issue", FIELD_HELP["issue"]), self.issue_editor)
        frame_layout.addWidget(self.frame_content_box)

        frame_form = QFormLayout()
        self.frame_left = self.spin(50)
        self.frame_top = self.spin(50)
        self.frame_right = self.spin(50)
        self.frame_bottom = self.spin(50)
        self.output_suffix = QLineEdit()
        self.output_suffix.setPlaceholderText("留空保持原名")
        frame_form.addRow(HelpLabel("图框左边距", FIELD_HELP["frame_margin"]), self.frame_left)
        frame_form.addRow(HelpLabel("图框上边距", FIELD_HELP["frame_margin"]), self.frame_top)
        frame_form.addRow(HelpLabel("图框右边距", FIELD_HELP["frame_margin"]), self.frame_right)
        frame_form.addRow(HelpLabel("图框下边距", FIELD_HELP["frame_margin"]), self.frame_bottom)
        frame_form.addRow(HelpLabel("最终输出后缀", FIELD_HELP["output_suffix"]), self.output_suffix)
        frame_layout.addLayout(frame_form)
        self.layout.addWidget(self.frame_box)

        self.run_basic.toggled.connect(self.basic_box.setEnabled)
        self.run_merge.toggled.connect(self._update_merge_enabled)
        self.run_margin.toggled.connect(self.margin_box.setEnabled)
        self.run_frame.toggled.connect(self.frame_box.setEnabled)
        self.source.pathChanged.connect(self._source_path_changed)
        self.source.modeChanged.connect(self._input_mode_changed)
        self.template_selector.modeChanged.connect(self._template_mode_changed)

        self.task = TaskPanel()
        self.task.run_button.setText("运行一键流程")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)
        self._input_mode_changed(self.source.mode().value)
        self._template_mode_changed(self.template_selector.mode().value)

    @staticmethod
    def spin(value: int) -> IntegerInput:
        return IntegerInput(value=value, minimum=0, maximum=100000)

    def _source_path_changed(self, text: str) -> None:
        self.basic_rules.set_input_dir(text)
        if self.source.mode() == InputMode.DIRECTORY:
            self.merge_order.set_input_dir(text)

    def _input_mode_changed(self, mode_value: str) -> None:
        directory = InputMode(mode_value) == InputMode.DIRECTORY
        self.run_merge.setEnabled(directory)
        if directory:
            self.merge_order.set_input_dir(self.source.path())
        else:
            self.run_merge.setChecked(False)
        self._update_merge_enabled()
        self.basic_rules.set_input_dir(self.source.path())

    def _update_merge_enabled(self) -> None:
        enabled = self.source.mode() == InputMode.DIRECTORY and self.run_merge.isChecked()
        self.merge_box.setEnabled(enabled)

    def _template_mode_changed(self, mode_value: str) -> None:
        self.frame_content_box.setEnabled(TemplateMode(mode_value) == TemplateMode.BUILTIN)

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output.persist_current_text()
        self.template_selector.persist_current()

    def run(self) -> None:
        source = self.source.path()
        output = self.output.path()
        mode = self.source.mode()

        if not validate_input_source(
            self,
            self.source,
            display_name="一键处理原始输入",
            require_compound_suffix=True,
        ):
            return
        if not validate_existing_directory(self, output, "一键处理最终输出目录"):
            return
        if self.run_frame.isChecked() and not self.template_selector.validate_selection():
            return
        if mode == InputMode.DIRECTORY and self.run_merge.isChecked():
            self.merge_order.set_input_dir(source)
            if not self.merge_order.ensure_ready():
                return

        self.source.persist_current()
        self.output.persist_valid_path()
        self.template_selector.persist_current()

        task_work = self.temp_workspace.reset_task_workspace()
        basic = self.basic_rules.build_settings(
            source_path=task_work / "00_source",
            input_mode=InputMode.DIRECTORY,
            output_dir=task_work / "01_basic_processed",
        )
        merge = MergeSettings(
            input_dir=task_work / "01_basic_processed",
            output_dir=task_work / "02_merged",
            output_name=self.merge_output_name.text(),
            ordered_file_names=(
                self.merge_order.ordered_file_names()
                if mode == InputMode.DIRECTORY and self.run_merge.isChecked()
                else []
            ),
            feeder_gap=self.gap.value(),
            left_margin=self.left_margin.value(),
            top_margin=self.top_margin.value(),
            right_margin=self.right_margin.value(),
            bottom_margin=self.bottom_margin.value(),
        )
        margin = MarginSettings(
            source_path=task_work / "02_merged",
            input_mode=InputMode.DIRECTORY,
            output_dir=task_work / "03_adjusted",
            left_margin=self.content_left.value(),
            top_margin=self.content_top.value(),
            right_margin=self.content_right.value(),
            bottom_margin=self.content_bottom.value(),
            preserve_existing_frame=True,
            output_suffix="",
        )
        frame = FrameSettings(
            source_path=task_work / "03_adjusted",
            input_mode=InputMode.DIRECTORY,
            output_dir=output,
            template_file=self.template_selector.resolved_template_path(),
            template_mode=self.template_selector.mode(),
            builtin_template_id=self.template_selector.builtin_template_id(),
            title=self.title.text().strip(),
            draw=PersonSettings(name=self.draw_editor.name(), date=self.draw_editor.date()),
            approve=PersonSettings(name=self.approve_editor.name(), date=self.approve_editor.date()),
            issue=PersonSettings(name=self.issue_editor.name(), date=self.issue_editor.date()),
            frame_left=self.frame_left.value(),
            frame_top=self.frame_top.value(),
            frame_right=self.frame_right.value(),
            frame_bottom=self.frame_bottom.value(),
            output_suffix=self.output_suffix.text().strip(),
        )
        settings = PipelineSettings(
            source_path=source,
            input_mode=mode,
            temp_work_dir=task_work,
            output_dir=output,
            run_basic=self.run_basic.isChecked(),
            run_merge=self.run_merge.isChecked(),
            run_margin=self.run_margin.isChecked(),
            run_frame=self.run_frame.isChecked(),
            basic=basic,
            merge=merge,
            margin=margin,
            frame=frame,
        )
        self.task.start(
            lambda log, progress: run_pipeline(settings, log, progress),
            output,
        )
