from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QVBoxLayout

from g_file_studio.models import InputMode, OrthogonalizeSettings
from g_file_studio.processors.orthogonalize_processor import process_orthogonalize
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel


class OrthogonalizePage(BasePage):
    """Standalone safe geometry cleanup for electrical line routes and devices."""

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        help_title, help_html = APP_HELP["orthogonalize"]
        super().__init__(
            "线路正交化",
            "按单个 G 文件对设备连接进行局部整理，并在安全条件下重画电气线路。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "本模块逐个处理 G 文件，不跨文件建立全局拓扑，专门处理 ConnectLine、FeedLine、BusDis、Bus、ACLine 和 line 的 d 路径。"
                "读取当前文件的线路 d 端点及 node_area/link 端点引用：同一标准图元在明确形成横排或竖列时按真实连接点对齐，线路端点同步移动；"
                "不同类设备只对拓扑末端进行小范围连接点对齐，中间多连接设备保持不动；"
                "两端设备身份明确的短线会按设备边界安全重画，保留原 ID 和 link/node_area；"
                "其余斜线在保留端点的前提下增加水平/垂直直角段。Text、DText、Poke 和未知图元不修改。"
                "若对齐或重画会与其他设备重叠/相交，则保守跳过。"
                "原始 G 文件不会覆盖，结果写入本次 workspace 目录。"
            )
        )

        io_box = QGroupBox("输入与输出")
        io_layout = QVBoxLayout(io_box)
        io_layout.setContentsMargins(12, 18, 12, 12)
        io_layout.setSpacing(10)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要整理线路的 G 文件。",
            directory_tooltip="选择包含多个需要整理线路的 G 文件目录；程序只扫描目录第一层。",
            settings_prefix="orthogonalize",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择线路正交化输出目录",
            recent_directory_key="recent_paths/orthogonalize/output_directory",
            persistent_path_key="orthogonalize/output_directory",
            default_path=default_workspace() / "orthogonalized",
            location_name="线路正交化输出目录",
            settings_service=self.user_settings,
        )
        configure_managed_output(self.output_path, "orthogonalize")
        io_layout.addWidget(self.output_path)
        self.layout.addWidget(io_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始线路正交化")
        self.task.run_button.setToolTip(
            "按当前 G 文件分析同类设备、明确端点和线路障碍，在安全条件下对齐设备并重画/正交化线路；输出不会覆盖源 G 文件。"
        )
        self.task.run_button.clicked.connect(self.run)
        self.layout.addWidget(self.task, 1)

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()

    def run(self) -> None:
        if not validate_input_source(
            self,
            self.source,
            display_name="线路正交化输入",
            log=self.task.append_log,
        ):
            return
        self.source.persist_current()
        # Managed workspace output is recreated automatically if the whole workspace
        # was deleted between runs.
        output_dir = begin_managed_run(self.output_path, "orthogonalize", "normalize")
        prepared_source = self.source.prepare_for_processing(log=self.task.append_log)
        input_mode = self.source.mode()
        if input_mode == InputMode.REMOTE_SSH:
            input_mode = InputMode.DIRECTORY
        settings = OrthogonalizeSettings(
            source_path=prepared_source,
            input_mode=input_mode,
            output_dir=output_dir,
        )
        self.task.start(lambda log, progress: process_orthogonalize(settings, log, progress), output_dir)
