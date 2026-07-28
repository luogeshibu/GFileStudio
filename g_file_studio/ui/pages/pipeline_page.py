from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from g_file_studio.models import FrameSettings, MergeSettings, PersonSettings, PipelineSettings
from g_file_studio.processors.pipeline_processor import run_pipeline
from g_file_studio.services.paths import default_template, default_workspace
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import (
    BasicRulesEditor,
    FileOrderEditor,
    HelpLabel,
    InfoBanner,
    PathRow,
    PersonEditor,
    TaskPanel,
)


class PipelinePage(BasePage):
    def __init__(self, parent=None) -> None:
        help_title, help_html = APP_HELP["pipeline"]
        super().__init__(
            "一键处理",
            "按选择的阶段依次完成基础处理、G 文件合并和图框添加。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "合并阶段只接收以 .sln.pic.g 结尾、且不包含外框架图的输入文件。扫描后可自由调整顺序，第一行文件作为合并基准。"
            )
        )

        path_box = QGroupBox("项目目录")
        path_form = QFormLayout(path_box)
        path_form.setHorizontalSpacing(16)
        path_form.setVerticalSpacing(10)
        self.source = PathRow()
        self.work = PathRow()
        self.output = PathRow()
        self.template = PathRow(directory=False, file_filter="SLD G Files (*.sln.pic.g);;G Files (*.g)")
        self.source.set_path(default_workspace() / "input")
        self.work.set_path(default_workspace() / "work")
        self.output.set_path(default_workspace() / "output")
        self.template.set_path(default_template())
        self.source.set_tooltip(FIELD_HELP["input_dir"])
        self.work.set_tooltip(FIELD_HELP["work_dir"])
        self.output.set_tooltip(FIELD_HELP["output_dir"])
        self.template.set_tooltip(FIELD_HELP["template"])
        path_form.addRow(HelpLabel("原始输入目录", FIELD_HELP["input_dir"]), self.source)
        path_form.addRow(HelpLabel("中间工作目录", FIELD_HELP["work_dir"]), self.work)
        path_form.addRow(HelpLabel("最终输出目录", FIELD_HELP["output_dir"]), self.output)
        path_form.addRow(HelpLabel("图框模板", FIELD_HELP["template"]), self.template)
        self.layout.addWidget(path_box)

        stage_box = QGroupBox("处理阶段")
        stage_layout = QVBoxLayout(stage_box)
        stage_layout.setContentsMargins(14, 18, 14, 12)
        stage_layout.setSpacing(9)
        self.run_basic = QCheckBox("1. 基础处理：执行通用属性替换和元素删除规则")
        self.run_merge = QCheckBox("2. G 文件合并：使用下面定义的用户顺序、对齐基准和 ID 处理")
        self.run_frame = QCheckBox("3. 添加图框：写入外框、标题和签字栏")
        self.clean_work = QCheckBox("运行前清理本次流程的中间阶段目录")
        for check in (self.run_basic, self.run_merge, self.run_frame, self.clean_work):
            check.setChecked(True)
        self.clean_work.setToolTip(FIELD_HELP["clean_work"])
        stage_layout.addWidget(self.run_basic)
        stage_layout.addWidget(self.run_merge)
        stage_layout.addWidget(self.run_frame)
        stage_layout.addSpacing(4)
        stage_layout.addWidget(self.clean_work)
        self.layout.addWidget(stage_box)

        basic_box = QGroupBox("基础处理规则")
        basic_layout = QVBoxLayout(basic_box)
        basic_layout.setContentsMargins(12, 18, 12, 12)
        self.basic_rules = BasicRulesEditor()
        basic_layout.addWidget(self.basic_rules)
        self.layout.addWidget(basic_box)
        self.basic_box = basic_box

        merge_box = QGroupBox("G 文件合并参数与顺序")
        merge_layout = QVBoxLayout(merge_box)
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
        merge_form.addRow(HelpLabel("左边距", FIELD_HELP["merge_margin"]), self.left_margin)
        merge_form.addRow(HelpLabel("上边距", FIELD_HELP["merge_margin"]), self.top_margin)
        merge_form.addRow(HelpLabel("右边距", FIELD_HELP["merge_margin"]), self.right_margin)
        merge_form.addRow(HelpLabel("下边距", FIELD_HELP["merge_margin"]), self.bottom_margin)
        merge_layout.addLayout(merge_form)

        self.merge_order = FileOrderEditor()
        self.merge_order.set_input_dir(self.source.path())
        merge_layout.addWidget(self.merge_order)
        self.layout.addWidget(merge_box)
        self.merge_box = merge_box

        frame_box = QGroupBox("图框内容")
        frame_form = QFormLayout(frame_box)
        frame_form.setHorizontalSpacing(16)
        frame_form.setVerticalSpacing(10)
        self.title = QLineEdit()
        self.title.setPlaceholderText("留空时取合并文件名")
        self.draw_editor = PersonEditor("Draw")
        self.approve_editor = PersonEditor("Approve")
        self.issue_editor = PersonEditor("Issue")
        self.frame_margin = self.spin(50)
        self.output_suffix = QLineEdit()
        self.output_suffix.setPlaceholderText("留空保持原名")
        frame_form.addRow(HelpLabel("标题覆盖", FIELD_HELP["title"]), self.title)
        frame_form.addRow(HelpLabel("Draw", FIELD_HELP["draw"]), self.draw_editor)
        frame_form.addRow(HelpLabel("Approve", FIELD_HELP["approve"]), self.approve_editor)
        frame_form.addRow(HelpLabel("Issue", FIELD_HELP["issue"]), self.issue_editor)
        frame_form.addRow(HelpLabel("图框四边距", FIELD_HELP["frame_margin"]), self.frame_margin)
        frame_form.addRow(HelpLabel("输出后缀", FIELD_HELP["output_suffix"]), self.output_suffix)
        self.layout.addWidget(frame_box)
        self.frame_box = frame_box

        self.run_basic.toggled.connect(self.basic_box.setEnabled)
        self.run_merge.toggled.connect(self.merge_box.setEnabled)
        self.run_frame.toggled.connect(self.frame_box.setEnabled)
        self.source.pathChanged.connect(self._source_path_changed)

        self.task = TaskPanel()
        self.task.run_button.setText("运行一键流程")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def _source_path_changed(self, text: str) -> None:
        self.merge_order.set_input_dir(text)

    @staticmethod
    def spin(value: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(0, 100000)
        widget.setSingleStep(10)
        widget.setValue(value)
        return widget

    def run(self) -> None:
        source = self.source.path()
        work = self.work.path()
        output = self.output.path()

        if self.run_merge.isChecked():
            self.merge_order.set_input_dir(source)
            if not self.merge_order.ensure_ready():
                return

        basic = self.basic_rules.build_settings(
            input_dir=source,
            output_dir=work / "01_basic_processed",
        )
        merge = MergeSettings(
            input_dir=work / "01_basic_processed",
            output_dir=work / "02_merged",
            output_name=self.merge_output_name.text(),
            ordered_file_names=self.merge_order.ordered_file_names(),
            feeder_gap=self.gap.value(),
            left_margin=self.left_margin.value(),
            top_margin=self.top_margin.value(),
            right_margin=self.right_margin.value(),
            bottom_margin=self.bottom_margin.value(),
        )
        frame = FrameSettings(
            input_dir=work / "02_merged",
            output_dir=output,
            template_file=self.template.path(),
            title=self.title.text().strip(),
            draw=PersonSettings(name=self.draw_editor.name(), date=self.draw_editor.date()),
            approve=PersonSettings(name=self.approve_editor.name(), date=self.approve_editor.date()),
            issue=PersonSettings(name=self.issue_editor.name(), date=self.issue_editor.date()),
            frame_left=self.frame_margin.value(),
            frame_top=self.frame_margin.value(),
            frame_right=self.frame_margin.value(),
            frame_bottom=self.frame_margin.value(),
            output_suffix=self.output_suffix.text().strip(),
        )
        settings = PipelineSettings(
            source_dir=source,
            work_dir=work,
            output_dir=output,
            template_file=self.template.path(),
            run_basic=self.run_basic.isChecked(),
            run_merge=self.run_merge.isChecked(),
            run_frame=self.run_frame.isChecked(),
            clear_work_dirs=self.clean_work.isChecked(),
            basic=basic,
            merge=merge,
            frame=frame,
        )
        self.task.start(
            lambda log, progress: run_pipeline(settings, log, progress),
            output,
        )
