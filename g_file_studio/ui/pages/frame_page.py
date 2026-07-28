from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.models import FrameSettings, PersonSettings
from g_file_studio.processors.frame_processor import add_drawing_frames
from g_file_studio.services.paths import default_template, default_workspace
from g_file_studio.ui.help_content import APP_HELP, FIELD_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import (
    HelpLabel,
    InfoBanner,
    IntegerInput,
    PathRow,
    PersonEditor,
    TaskPanel,
)
from g_file_studio.ui.widgets.help_widgets import set_secondary


class FramePage(BasePage):
    def __init__(self, parent=None) -> None:
        help_title, help_html = APP_HELP["frame"]
        super().__init__(
            "添加图框",
            "读取固定 SLD 模板，为已经合并的 G 文件添加外框、左上标题以及右下 Draw/Approve/Issue 信息。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "标题留空时自动取输入文件名。模板图元会重新分配唯一 ID，不会覆盖原有图元 ID。"
            )
        )

        path_box = QGroupBox("文件与目录")
        path_form = QFormLayout(path_box)
        path_form.setHorizontalSpacing(16)
        path_form.setVerticalSpacing(10)
        self.input_path = PathRow()
        self.output_path = PathRow()
        self.template_path = PathRow(directory=False, file_filter="G Files (*.g)")
        self.input_path.set_path(default_workspace() / "merged")
        self.output_path.set_path(default_workspace() / "output")
        self.template_path.set_path(default_template())
        self.input_path.set_tooltip(FIELD_HELP["input_dir"])
        self.output_path.set_tooltip(FIELD_HELP["output_dir"])
        self.template_path.set_tooltip(FIELD_HELP["template"])
        path_form.addRow(HelpLabel("输入目录", FIELD_HELP["input_dir"]), self.input_path)
        path_form.addRow(HelpLabel("输出目录", FIELD_HELP["output_dir"]), self.output_path)
        path_form.addRow(HelpLabel("图框模板", FIELD_HELP["template"]), self.template_path)
        self.layout.addWidget(path_box)

        title_box = QGroupBox("标题与签字栏")
        title_form = QFormLayout(title_box)
        title_form.setHorizontalSpacing(16)
        title_form.setVerticalSpacing(10)
        self.title = QLineEdit()
        self.title.setPlaceholderText("留空时取输入文件名，例如 JED-CTL-ADF")
        self.title.setToolTip(FIELD_HELP["title"])
        self.draw_editor = PersonEditor("Draw")
        self.approve_editor = PersonEditor("Approve")
        self.issue_editor = PersonEditor("Issue")
        title_form.addRow(HelpLabel("左上标题", FIELD_HELP["title"]), self.title)
        title_form.addRow(HelpLabel("Draw", FIELD_HELP["draw"]), self.draw_editor)
        title_form.addRow(HelpLabel("Approve", FIELD_HELP["approve"]), self.approve_editor)
        title_form.addRow(HelpLabel("Issue", FIELD_HELP["issue"]), self.issue_editor)
        self.layout.addWidget(title_box)

        layout_box = QGroupBox("图框与输出参数")
        layout_form = QFormLayout(layout_box)
        layout_form.setHorizontalSpacing(16)
        layout_form.setVerticalSpacing(10)
        self.left, self.top, self.right, self.bottom = [self.spin(50) for _ in range(4)]
        for widget in (self.left, self.top, self.right, self.bottom):
            widget.setToolTip(FIELD_HELP["frame_margin"])
        self.suffix = QLineEdit()
        self.suffix.setPlaceholderText("例如 -WITH-FRAME；留空保持原名")
        self.suffix.setToolTip(FIELD_HELP["output_suffix"])
        layout_form.addRow(HelpLabel("图框左边距", FIELD_HELP["frame_margin"]), self.left)
        layout_form.addRow(HelpLabel("图框上边距", FIELD_HELP["frame_margin"]), self.top)
        layout_form.addRow(HelpLabel("图框右边距", FIELD_HELP["frame_margin"]), self.right)
        layout_form.addRow(HelpLabel("图框下边距", FIELD_HELP["frame_margin"]), self.bottom)
        layout_form.addRow(HelpLabel("输出后缀", FIELD_HELP["output_suffix"]), self.suffix)
        self.layout.addWidget(layout_box)

        config_box = QGroupBox("配置文件")
        config_layout = QVBoxLayout(config_box)
        config_layout.setContentsMargins(12, 18, 12, 12)
        config_layout.setSpacing(8)
        config_buttons = QHBoxLayout()
        load_btn = QPushButton("载入 JSON")
        save_btn = QPushButton("保存 JSON")
        set_secondary(load_btn)
        set_secondary(save_btn)
        load_btn.setToolTip("从 drawing_frame_config.json 载入标题、姓名和日期。")
        save_btn.setToolTip("把当前标题、姓名和日期保存为可复用 JSON 配置。")
        load_btn.clicked.connect(self.load_json)
        save_btn.clicked.connect(self.save_json)
        config_buttons.addWidget(load_btn)
        config_buttons.addWidget(save_btn)
        config_buttons.addStretch(1)
        config_layout.addLayout(config_buttons)
        self.layout.addWidget(config_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始添加图框")
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    @staticmethod
    def spin(value: int) -> IntegerInput:
        return IntegerInput(value=value, minimum=0, maximum=100000)

    def settings(self) -> FrameSettings:
        return FrameSettings(
            input_dir=self.input_path.path(),
            output_dir=self.output_path.path(),
            template_file=self.template_path.path(),
            title=self.title.text().strip(),
            draw=PersonSettings(name=self.draw_editor.name(), date=self.draw_editor.date()),
            approve=PersonSettings(name=self.approve_editor.name(), date=self.approve_editor.date()),
            issue=PersonSettings(name=self.issue_editor.name(), date=self.issue_editor.date()),
            frame_left=self.left.value(),
            frame_top=self.top.value(),
            frame_right=self.right.value(),
            frame_bottom=self.bottom.value(),
            output_suffix=self.suffix.text().strip(),
        )

    def save_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图框配置",
            "drawing_frame_config.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.settings().config_dict(), file, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        QMessageBox.information(self, "保存成功", f"配置已保存到：\n{path}")

    def load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "载入图框配置",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                root = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "载入失败", str(exc))
            return

        data = root.get("default", root)
        if not isinstance(data, dict):
            QMessageBox.warning(self, "配置无效", "配置文件 default 必须是 JSON 对象。")
            return

        self.title.setText(str(data.get("title", "")))
        for key, editor in (
            ("draw", self.draw_editor),
            ("approve", self.approve_editor),
            ("issue", self.issue_editor),
        ):
            row = data.get(key, {})
            if isinstance(row, dict):
                editor.set_values(str(row.get("name", "")), str(row.get("date", "")))

    def run(self) -> None:
        settings = self.settings()
        self.task.start(
            lambda log, progress: add_drawing_frames(settings, log, progress),
            settings.output_dir,
        )
