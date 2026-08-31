from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel, QMessageBox, QPushButton, QVBoxLayout

from g_file_studio.processors.poke_processor import PokeProcessingSettings, process_pokes
from g_file_studio.services.database_service import OracleDatabaseService
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_existing_directory, validate_input_source
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel
from g_file_studio.ui.widgets.help_widgets import set_secondary



class PokePage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.database_service = OracleDatabaseService(user_settings)
        self.last_html_report: Path | None = None
        help_title, help_html = APP_HELP["poke"]
        super().__init__(
            "Poke 跳转处理",
            "独立生成/修复 RMU 与站点跳转 Poke；数据库命名和 RMU 识别均复用公共能力。",
            help_title,
            help_html,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "Poke 已从“环网柜处理”独立，facID 不再作为执行前提。RMU Poke 直接复用公共 RMU 识别结果，"
                "并按每个已识别环网柜名称查询 DMS_COMBINED_DEVICE.FEEDER_ID，再沿 DMS_FEEDER_DEVICE/SUBSTATION/SUBCONTROLAREA "
                "生成各自的完整馈线目标；一张大图可同时处理多条馈线。站点跳转 Poke 只按标签中的站名关键字查询 SUBSTATION/SUBCONTROLAREA，"
                "本身不使用 facID。GRAPH_NAME 不参与目标名称生成。"
            )
        )

        io_box = QGroupBox("输入与输出")
        io_layout = QVBoxLayout(io_box)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一个需要生成/修复 Poke 的 G 文件。",
            directory_tooltip="选择包含多个待处理 G 文件的目录；程序只扫描目录第一层。",
            settings_prefix="poke",
            settings_service=self.user_settings,
        )
        io_layout.addWidget(self.source)
        self.output_path = PathRow(
            directory=True,
            dialog_title="选择 Poke 跳转处理输出目录",
            recent_directory_key="recent_paths/poke/output_directory",
            persistent_path_key="poke/output_directory",
            default_path=default_workspace() / "poke-processed",
            location_name="Poke 跳转处理输出目录",
            settings_service=self.user_settings,
        )
        configure_managed_output(self.output_path, "poke")
        io_layout.addWidget(self.output_path)
        self.layout.addWidget(io_box)

        mode_box = QGroupBox("跳转类型")
        mode_layout = QVBoxLayout(mode_box)
        self.enable_rmu_poke = QCheckBox("RMU Poke：跳转到具体环网柜明细图")
        self.enable_station_poke = QCheckBox("站点跳转 Poke：跳转到对端变电站馈线总图")
        self.enable_rmu_poke.setChecked(self.user_settings.get_bool("poke/enable_rmu", True))
        self.enable_station_poke.setChecked(self.user_settings.get_bool("poke/enable_station", True))
        mode_layout.addWidget(self.enable_rmu_poke)
        mode_layout.addWidget(self.enable_station_poke)
        self.layout.addWidget(mode_box)

        recognition_box = QGroupBox("识别与数据库规则")
        recognition_layout = QVBoxLayout(recognition_box)
        shared_rmu = QLabel(
            "RMU Poke 不在本模块重新定义 RMU 规则：运行时直接读取“环网柜处理”保存的柜名方向、"
            "名称排除项和智能标记，并调用同一个 identify_rmus()。识别到柜名后，以 RMU 名称查询 DMS_COMBINED_DEVICE，"
            "由 FEEDER_ID 找到所属 DMS_FEEDER_DEVICE，再按 SUBSTATION/SUBCONTROLAREA 生成该 RMU 自己的馈线完整业务名；不依赖 facID。"
        )
        shared_rmu.setWordWrap(True)
        shared_rmu.setObjectName("mutedText")
        recognition_layout.addWidget(shared_rmu)
        station_rule = QLabel(
            "站点跳转示例：DHN-40 → 只取 DHN → SUBSTATION.NAME → SUBAREA_ID → SUBCONTROLAREA.NAME → "
            "JED-CTL-DHN → ahref=JED-CTL-DHN.sln.pic.g，对端目标为变电站馈线总图。后缀 40 和附近 (14858) 等数字均忽略。"
        )
        station_rule.setWordWrap(True)
        station_rule.setObjectName("mutedText")
        recognition_layout.addWidget(station_rule)
        fallback = QLabel(
            "识别优先级：已有覆盖标签的非 RMU Poke > 线路末端附近标签 > 紧凑背景图形。背景颜色只作视觉信息，"
            "不作为必要条件；所有候选必须通过 Oracle 唯一匹配才允许修改。多个相关 Poke 删除多余项只保留一个。"
        )
        fallback.setWordWrap(True)
        fallback.setObjectName("mutedText")
        recognition_layout.addWidget(fallback)
        self.layout.addWidget(recognition_box)

        self.task = TaskPanel()
        self.task.run_button.setText("开始 Poke 跳转处理")
        self.task.run_button.clicked.connect(self.run)
        self.report_button = QPushButton("打开 Poke 报告")
        self.report_button.setToolTip("打开最近一次 Poke 跳转处理生成的 HTML 报告；报告包含 RMU/站点跳转识别、写入 ahref、处理动作及未加跳转原因。")
        set_secondary(self.report_button)
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.open_last_report)
        self.task.buttons_layout.insertWidget(1, self.report_button)
        self.task.resultReceived.connect(self._on_result)
        self.layout.addWidget(self.task, 1)

    def _shared_rmu_settings(self) -> tuple[tuple[str, ...], str, str]:
        positions = tuple(
            key for key, default in (("top", True), ("bottom", False), ("left", False), ("right", False))
            if self.user_settings.get_bool(f"basic/rmu/name_{key}", default)
        )
        if not positions:
            positions = ("top",)
        exclusions = self.user_settings.get_value("basic/rmu/name_exclusions", "").strip()
        markers = self.user_settings.get_value("basic/rmu/intelligent_markers", "SMART, SMR").strip() or "SMART, SMR"
        return positions, exclusions, markers

    def run(self) -> None:
        if not validate_input_source(self, self.source, display_name="Poke 跳转处理输入"):
            return
        if not validate_existing_directory(self, self.output_path.path(), "Poke 跳转处理输出目录"):
            return
        if not self.enable_rmu_poke.isChecked() and not self.enable_station_poke.isChecked():
            QMessageBox.warning(self, "Poke 跳转处理", "请至少选择一种 Poke 跳转类型。")
            return

        self.source.persist_current()
        self.user_settings.set_value("poke/enable_rmu", self.enable_rmu_poke.isChecked())
        self.user_settings.set_value("poke/enable_station", self.enable_station_poke.isChecked())
        positions, exclusions, markers = self._shared_rmu_settings()
        output_dir = begin_managed_run(self.output_path, "poke", "process")
        settings = PokeProcessingSettings(
            source_path=Path(self.source.path()),
            input_mode=self.source.mode(),
            output_dir=output_dir,
            enable_rmu_poke=self.enable_rmu_poke.isChecked(),
            enable_station_poke=self.enable_station_poke.isChecked(),
            rmu_name_positions=positions,
            rmu_name_exclusions=exclusions,
            rmu_intelligent_markers=markers,
        )
        self.last_html_report = None
        self.report_button.setEnabled(False)
        self.task.start(
            lambda log, progress: process_pokes(settings, self.database_service, log, progress),
            output_dir,
        )

    def _on_result(self, result) -> None:
        self.last_html_report = None
        path_text = str(result.statistics.get("html_report_path", "")) if getattr(result, "statistics", None) else ""
        if path_text:
            path = Path(path_text)
            if path.exists():
                self.last_html_report = path
        self.report_button.setEnabled(self.last_html_report is not None)
        if self.last_html_report is not None:
            stats = result.statistics
            self.task.append_log(
                "[Poke报告摘要] "
                f"识别 RMU {stats.get('rmu_identified_total', 0)} 个，智能 RMU {stats.get('smart_rmu_identified_total', 0)} 个；"
                f"新增 RMU Poke {stats.get('rmu_added', 0)} 个；"
                f"站点跳转候选 {stats.get('station_candidates', 0)} 个，成功解析 {stats.get('station_resolved_count', 0)} 个，"
                f"新增站点跳转 Poke {stats.get('station_added', 0)} 个，未加跳转 {stats.get('station_skipped', 0)} 个。"
            )

    def open_last_report(self) -> None:
        if not self.last_html_report or not self.last_html_report.exists():
            QMessageBox.information(self, "暂无报告", "请先执行一次 Poke 跳转处理并生成报告。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html_report.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
        self.user_settings.set_value("poke/enable_rmu", self.enable_rmu_poke.isChecked())
        self.user_settings.set_value("poke/enable_station", self.enable_station_poke.isChecked())
