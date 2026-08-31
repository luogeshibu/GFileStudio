from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from g_file_studio.processors.smart_profile_processor import (
    SmartProfileProcessingSettings,
    process_smart_profile_consistency,
    process_smart_profile_correction,
)
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_input_source
from g_file_studio.ui.table_layout import configure_known_dense_table, fit_known_dense_table
from g_file_studio.ui.widgets import InfoBanner, InputSourceSelector, PathRow, TaskPanel, WheelSafeComboBox
from g_file_studio.ui.widgets.help_widgets import set_secondary
from g_file_studio.workers import FunctionWorker


class SiteProfilePage(BasePage):
    """Generic symbol-standard inspection and safe-correction module.

    Existing SiteSmartProfile persistence is retained for backward compatibility.
    Checking is read-only. Correction is explicit and writes only managed workspace
    copies; selected source G files are never overwritten. Same-class OLD→NEW icon
    version upgrades remain in Basic Processing.
    """

    activeProfileChanged = Signal(str)

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.service = SiteProfileService()
        self._last_scan = None
        self._last_report_path: Path | None = None
        self._scan_worker: FunctionWorker | None = None
        self._scan_pool = QThreadPool.globalInstance()
        self._selected_version: int | None = None
        self._selected_is_active = False
        self._task_busy = False
        self._candidate_counts: dict[int, dict[str, int]] = {}
        self._symbol_catalog: dict[str, dict[str, object]] = {}
        self._pending_standard_file_records: list[dict[str, object]] = []
        help_title, help_html = APP_HELP["site_profile"]
        super().__init__(
            "图元标准检查",
            "先由用户上传权威图元 G 建立持久化标准库，再检查业务 G 是否严格使用当前 ACTIVE 标准；需要时可生成纠正副本，源 G 不覆盖。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "这是通用图元标准检查与纠正模块，不绑定吉达或其他现场批处理。标准来源与业务 G 完全分离："
                "标准必须由用户明确上传图元定义 G 文件；业务单线图永远只作为被检查对象，不能自动学习成标准。"
                "标准图元会复制到版本独立的用户标准库，升级程序不会丢失。"
                "“检查图元标准”始终只读；“纠正标准问题”只对当前 ACTIVE 标准已定义的图元生成 workspace 纠正副本，源 G 永不覆盖。"
                "带电气 pin 且与 ConnectLine 关系可可靠解析的标准图元，会保持连接线绝对端点不动并反算图元位置/尺寸；无法可靠映射时只告警不猜测。"
                "同类图元的 OLD → NEW 版本升级仍统一在“基础处理 → 同类图元版本升级”执行；吉达批处理流程不受本模块新增纠正功能影响。"
            )
        )

        standard_box = QGroupBox("图元标准")
        standard_layout = QVBoxLayout(standard_box)
        standard_layout.setContentsMargins(14, 18, 14, 12)
        standard_layout.setSpacing(10)

        self.active_profile_summary = QLabel("当前执行标准：尚未创建标准")
        self.active_profile_summary.setObjectName("sectionCaption")
        self.active_profile_summary.setWordWrap(True)
        standard_layout.addWidget(self.active_profile_summary)

        intro = QLabel(
            "这里不再分成“当前标准列表”和“标准定义”两个表格：一个页面只保留下面这一张图元标准表。"
            "标准版本通过上方下拉框切换。每个设备角色可以分别使用 SMART / NORMAL 标准，也允许两者共用同一个用户上传的标准图元 G。"
            "标准文件保存到用户数据目录；业务单线图永远只作为被检查对象，不会反向学习、发现或补全标准。"
            "设备角色由用户选中的表格行明确绑定；上传 G 只提供该角色的 devref、尺寸、AlignCenter 与 pin 标准。"
            "业务单线图不会参与 devref、尺寸、AlignCenter 或 pin 标准的生成。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")
        standard_layout.addWidget(intro)

        manage_row = QHBoxLayout()
        manage_row.addWidget(QLabel("标准版本"))
        self.profile_selector = WheelSafeComboBox()
        self.profile_selector.setMinimumContentsLength(42)
        self.profile_selector.currentIndexChanged.connect(self._profile_selection_changed)
        manage_row.addWidget(self.profile_selector, 1)
        self.profile_manage_button = QPushButton("标准管理")
        set_secondary(self.profile_manage_button)
        self.profile_menu = QMenu(self.profile_manage_button)
        self.new_action = self.profile_menu.addAction("新建标准")
        self.scan_action = self.profile_menu.addAction("为选中角色上传标准图元 G")
        self.profile_menu.addSeparator()
        self.restore_action = self.profile_menu.addAction("恢复此版本")
        self.delete_action = self.profile_menu.addAction("删除标准")
        self.new_action.triggered.connect(self._new_profile)
        self.scan_action.triggered.connect(self._scan_samples)
        self.restore_action.triggered.connect(self._restore_selected_version)
        self.delete_action.triggered.connect(self._delete_profile)
        self.profile_manage_button.setMenu(self.profile_menu)
        manage_row.addWidget(self.profile_manage_button)
        standard_layout.addLayout(manage_row)

        form = QFormLayout()
        self.site_name = QLineEdit()
        self.site_name.setPlaceholderText("例如：Jeddah / Madinah / General")
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("例如：RMU Standard V1")
        form.addRow("适用范围", self.site_name)
        form.addRow("标准名称", self.profile_name)
        standard_layout.addLayout(form)

        self.lbs_combo = WheelSafeComboBox()
        self.breaker_combo = WheelSafeComboBox()
        self.normal_lbs_combo = WheelSafeComboBox()
        self.normal_breaker_combo = WheelSafeComboBox()
        self.ground_combo = WheelSafeComboBox()
        self.normal_ground_combo = WheelSafeComboBox()

        standard_note = QLabel(
            "表中的 SMART / NORMAL 表示“检查适用范围”，不代表一定要上传两套不同图元。"
            "如果同一设备在 SMART 与 NORMAL 中使用同一个图元，勾选“SMART / NORMAL 共用此标准”后上传一次即可同时绑定两行；"
            "例如接地刀闸没有智能/非智能版本时，就应共用同一个标准 G。若两边确实不同，则分别上传即可。"
            "可以只配置当前需要检查的设备角色，不要求一次补齐全部范围。上传文件名/XML 类型仅作为参考信息，不再阻止人工绑定。"
        )
        standard_note.setWordWrap(True)
        standard_note.setObjectName("mutedText")
        standard_layout.addWidget(standard_note)

        custom_actions = QHBoxLayout()
        self.upload_standard_button = QPushButton("为选中角色上传 / 更新标准 G")
        self.upload_standard_button.clicked.connect(self._scan_samples)
        custom_actions.addWidget(self.upload_standard_button)
        self.share_pair_checkbox = QCheckBox("SMART / NORMAL 共用此标准")
        self.share_pair_checkbox.setToolTip("勾选后，当前标准 G 会同时绑定到同一种设备角色的 SMART 与 NORMAL 检查范围。")
        self.share_pair_checkbox.toggled.connect(self._share_pair_toggled)
        custom_actions.addWidget(self.share_pair_checkbox)
        self.add_custom_button = QPushButton("添加自定义设备角色")
        set_secondary(self.add_custom_button)
        self.add_custom_button.clicked.connect(self._add_custom_standard)
        custom_actions.addWidget(self.add_custom_button)
        self.delete_custom_button = QPushButton("删除选中自定义项")
        set_secondary(self.delete_custom_button)
        self.delete_custom_button.clicked.connect(self._delete_selected_custom_standard)
        custom_actions.addWidget(self.delete_custom_button)
        custom_actions.addStretch(1)
        self.lock_standard_button = QPushButton("锁定当前版本")
        set_secondary(self.lock_standard_button)
        self.lock_standard_button.setToolTip("锁定后当前 ACTIVE 标准版本不可修改、上传、删除或恢复历史版本；检查业务 G 仍可正常执行。")
        self.lock_standard_button.clicked.connect(self._toggle_profile_lock)
        custom_actions.addWidget(self.lock_standard_button)
        standard_layout.addLayout(custom_actions)

        self.standard_table = QTableWidget(6, 12)
        self.standard_table.setHorizontalHeaderLabels(
            ["检查范围", "设备角色", "检查对象 XML", "标准图元文件", "主体 ID", "w×h", "AlignCenter", "Pins", "设备定位规则", "定位条件", "标准来源", "状态"]
        )
        self.standard_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.standard_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.standard_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.standard_table.verticalHeader().setVisible(False)
        self.standard_table.setObjectName("symbolStandardTable")
        self.standard_table.setShowGrid(True)
        self.standard_table.setAlternatingRowColors(True)
        # Cell editors should sit flush with the grid.  The application-wide input
        # style adds padding/borders that look offset when a QComboBox is embedded
        # in a QTableWidget, so only this engineering table uses a compact flat editor.
        self.standard_table.setStyleSheet(
            "QTableWidget#symbolStandardTable { padding: 0px; }"
            "QTableWidget#symbolStandardTable QComboBox { margin: 0px; border: none; border-radius: 0px; padding: 3px 24px 3px 6px; }"
            "QTableWidget#symbolStandardTable QComboBox::drop-down { border: none; width: 22px; }"
        )
        self.standard_table.itemSelectionChanged.connect(self._standard_row_selection_changed)
        for column in (0, 1, 2, 4, 5, 6, 7, 8, 10, 11):
            self.standard_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.standard_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.standard_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        configure_known_dense_table(self.standard_table)
        self.standard_table.setMinimumHeight(380)
        self._standard_specs = [
            ("SMART", "LBS", "CBreakerDis", self.lbs_combo, "系统规则", "Y* / RMU 内"),
            ("SMART", "Circuit Breaker", "CBreakerDis", self.breaker_combo, "系统规则", "Q* / RMU 内"),
            ("SMART", "接地刀闸", "ZhaiWaiJieDiDaoZha", self.ground_combo, "系统规则", "RMU 内接地刀闸"),
            ("NORMAL", "LBS", "CBreakerDis", self.normal_lbs_combo, "系统规则", "Y* / RMU 内"),
            ("NORMAL", "Circuit Breaker", "CBreakerDis", self.normal_breaker_combo, "系统规则", "Q* / RMU 内"),
            ("NORMAL", "接地刀闸", "ZhaiWaiJieDiDaoZha", self.normal_ground_combo, "系统规则", "RMU 内接地刀闸"),
        ]
        for row, (rmu_class, role, element_tag, combo, match_attr, match_value) in enumerate(self._standard_specs):
            combo.setMinimumContentsLength(28)
            combo.setMinimumHeight(36)
            combo.currentIndexChanged.connect(lambda _index, c=combo: self._refresh_standard_row(c))
            self._set_readonly_cell(row, 0, rmu_class, kind="system")
            self._set_readonly_cell(row, 1, role)
            self._set_readonly_cell(row, 2, element_tag)
            # “标准图元文件”是结果展示列，不是下拉编辑器。角色绑定通过
            # “为选中角色上传 / 更新标准 G”完成；这里保持真正的表格单元格，
            # 避免 QComboBox 的白色背景覆盖网格线、选中行底色和单元格边界。
            self._set_readonly_cell(row, 3, "-")
            for column in (4, 5, 6, 7):
                self._set_readonly_cell(row, column, "-")
            self._set_readonly_cell(row, 8, match_attr)
            self._set_readonly_cell(row, 9, match_value)
            self._set_readonly_cell(row, 10, "-")
            self._set_readonly_cell(row, 11, "未上传")
        fit_known_dense_table(self.standard_table)
        standard_layout.addWidget(self.standard_table)

        save_row = QHBoxLayout()
        self.save_button = QPushButton("保存当前标准")
        self.save_button.clicked.connect(self._save_profile)
        save_row.addWidget(self.save_button)
        self.profile_status = QLabel("")
        self.profile_status.setObjectName("mutedText")
        self.profile_status.setWordWrap(True)
        save_row.addWidget(self.profile_status, 1)
        standard_layout.addLayout(save_row)

        self.scan_summary = QLabel("尚未上传标准图元。")
        self.scan_summary.setObjectName("mutedText")
        self.scan_summary.setWordWrap(True)
        standard_layout.addWidget(self.scan_summary)
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setFormat("读取标准图元 %p%")
        self.scan_progress.setToolTip("读取用户上传的标准图元 G，并提取 devref、w/h、AlignCenter、pin 等权威定义。")
        self.scan_progress.setVisible(False)
        standard_layout.addWidget(self.scan_progress)

        self.layout.addWidget(standard_box)

        source_box = QGroupBox("待检查 G 文件")
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(14, 18, 14, 12)
        source_layout.setSpacing(10)
        source_note = QLabel(
            "选择需要被检查的业务单线图 G 文件或目录。本模块只读，不修改源 G；输出目录只保存检查报告和日志。"
            "标准只来自上方用户上传的图元定义 G；业务 G 永远不会参与标准学习。"
        )
        source_note.setWordWrap(True)
        source_note.setObjectName("mutedText")
        source_layout.addWidget(source_note)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一张需要按 ACTIVE 标准检查的业务 G 文件。",
            directory_tooltip="选择包含需要按 ACTIVE 标准检查的业务 G 文件目录。",
            settings_prefix="site_profile_source",
            settings_service=self.user_settings,
        )
        source_layout.addWidget(self.source)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出目录（workspace）"))
        self.output_path = PathRow(
            directory=True,
            dialog_title="图元标准检查输出目录",
            recent_directory_key="recent_paths/site_profile/output_directory",
            persistent_path_key="site_profile/output_directory",
            default_path=default_workspace() / "runs" / "smart-profile",
            location_name="图元标准检查输出目录",
            settings_service=self.user_settings,
        )
        configure_managed_output(self.output_path, "smart-profile")
        output_row.addWidget(self.output_path, 1)
        source_layout.addLayout(output_row)

        self.layout.addWidget(source_box)

        apply_box = QGroupBox("图元标准检查")
        apply_layout = QVBoxLayout(apply_box)
        apply_layout.setContentsMargins(14, 18, 14, 12)
        apply_layout.setSpacing(10)

        self.current_profile_label = QLabel("当前执行标准：未选择")
        self.current_profile_label.setObjectName("sectionCaption")
        self.current_profile_label.setWordWrap(True)
        self.current_profile_label.setVisible(False)
        apply_layout.addWidget(self.current_profile_label)

        execute_note = QLabel(
            "按当前 ACTIVE 标准检查图元类型/变体、devref 与连接锚点几何。“检查图元标准”不修改 G；"
            "“纠正标准问题”会在 workspace/corrected 中生成纠正副本，并自动复查。仅处理标准中已定义的图元；"
            "同类 OLD → NEW 图元版本升级仍请到“基础处理”。"
        )
        execute_note.setWordWrap(True)
        execute_note.setObjectName("mutedText")
        apply_layout.addWidget(execute_note)

        self.result_summary = QLabel("尚未执行图元标准检查。")
        self.result_summary.setObjectName("mutedText")
        self.result_summary.setWordWrap(True)
        apply_layout.addWidget(self.result_summary)

        self.task = TaskPanel()
        # v2.18.85: symbol-standard inspection/correction always stays in determinate
        # v2.18.85 is rebased directly from v2.18.82.  Keep the exact 0~100
        # determinate style, but smooth only the display-side repaint cadence so
        # queued worker progress does not make the bar flash/jump visually.
        self.task.set_live_progress_enabled(False)
        self.task.set_smooth_progress_enabled(True)
        self.task.progress.setToolTip("图元标准检查/纠正始终以 0~100% 百分比样式显示，并平滑递增；后台真实进度只更新目标值，不会造成进度条闪烁或倒退。")
        self.task.set_result_dialogs_enabled(False)
        self.task.run_button.hide()
        self.check_button = QPushButton("检查图元标准")
        self.check_button.clicked.connect(self._check_profile)
        self.task.buttons_layout.insertWidget(0, self.check_button)
        self.correct_button = QPushButton("纠正标准问题")
        set_secondary(self.correct_button)
        self.correct_button.clicked.connect(self._correct_profile)
        self.task.buttons_layout.insertWidget(1, self.correct_button)
        self.open_report_button = QPushButton("查看检查报告")
        set_secondary(self.open_report_button)
        self.open_report_button.setEnabled(False)
        self.open_report_button.clicked.connect(self._open_report)
        self.task.buttons_layout.insertWidget(2, self.open_report_button)
        self.task.open_button.setText("打开结果目录")
        self.toggle_log_button = QPushButton("显示日志")
        set_secondary(self.toggle_log_button)
        self.toggle_log_button.setCheckable(True)
        self.toggle_log_button.toggled.connect(self._toggle_log)
        self.task.buttons_layout.insertWidget(4, self.toggle_log_button)
        self.task.log_view.setVisible(False)
        self.task.clear_button.setVisible(False)
        self.task.resultReceived.connect(self._on_processing_result)
        self.task.busyChanged.connect(self._task_busy_changed)
        apply_layout.addWidget(self.task)
        self.layout.addWidget(apply_box, 1)

        # Workflow order: choose business G -> maintain/select the single standard table -> run check/correction.
        for widget in (source_box, standard_box, apply_box):
            self.layout.removeWidget(widget)
        self.layout.insertWidget(1, source_box)
        self.layout.insertWidget(2, standard_box)
        self.layout.insertWidget(3, apply_box)

        self._reload_profiles()
        self._update_action_state()

    @staticmethod
    def _paired_builtin_row(row: int) -> int:
        return {0: 3, 3: 0, 1: 4, 4: 1, 2: 5, 5: 2}.get(int(row), -1)

    def _standard_row_selection_changed(self) -> None:
        row = self.standard_table.currentRow()
        is_builtin = 0 <= row < len(self._standard_specs)
        self.share_pair_checkbox.setEnabled(is_builtin and not self._task_busy)
        if not is_builtin:
            self.share_pair_checkbox.setChecked(False)
            self._update_action_state()
            return
        pair = self._paired_builtin_row(row)
        selected = str(self._standard_specs[row][3].currentData() or "").strip()
        paired = str(self._standard_specs[pair][3].currentData() or "").strip() if pair >= 0 else ""
        role = self._standard_specs[row][1]
        # Existing shared bindings are reflected automatically. For grounding
        # switches with no binding yet, default to shared because many projects do
        # not distinguish SMART/NORMAL grounding symbols. The user can untick it.
        self.share_pair_checkbox.blockSignals(True)
        self.share_pair_checkbox.setChecked(bool(selected and paired and selected.casefold() == paired.casefold()) or (not selected and not paired and role == "接地刀闸"))
        self.share_pair_checkbox.blockSignals(False)
        self._update_action_state()

    def _share_pair_toggled(self, checked: bool) -> None:
        if not checked or self._task_busy:
            return
        row = self.standard_table.currentRow()
        if not (0 <= row < len(self._standard_specs)):
            return
        pair_row = self._paired_builtin_row(row)
        if pair_row < 0:
            return
        combo = self._standard_specs[row][3]
        devref = str(combo.currentData() or "").strip()
        if not devref:
            return
        pair_combo = self._standard_specs[pair_row][3]
        pair_index = pair_combo.findData(devref)
        if pair_index < 0:
            return
        pair_combo.setCurrentIndex(pair_index)
        self._refresh_standard_row(pair_combo)
        self._refresh_standard_row(combo)

    def _toggle_log(self, checked: bool) -> None:
        visible = bool(checked)
        self.task.log_view.setVisible(visible)
        self.task.clear_button.setVisible(visible)
        self.toggle_log_button.setText("隐藏日志" if visible else "显示日志")

    def _selected_profile_key(self) -> tuple[str, int | None, bool]:
        data = self.profile_selector.currentData() if hasattr(self, "profile_selector") else None
        if not isinstance(data, (tuple, list)) or len(data) != 3:
            return "", None, False
        name = str(data[0] or "").strip()
        try:
            version = int(data[1]) if data[1] is not None else None
        except (TypeError, ValueError):
            version = None
        return name, version, bool(data[2])

    def _selected_profile_name(self) -> str:
        return self._selected_profile_key()[0]

    def _reload_profiles(self, select_name: str = "", select_version: int | None = None) -> None:
        profiles = self.service.load_profiles()
        if not select_name:
            remembered = self.user_settings.get_value("site_profile/last_profile_name", "").strip()
            if remembered in profiles:
                select_name = remembered
                select_version = profiles[remembered].profile_version

        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        selected_index = -1
        for profile_name, current in sorted(profiles.items(), key=lambda row: row[0].casefold()):
            versions = self.service.load_profile_versions(profile_name) or [current]
            for profile in reversed(versions):
                is_active = profile.profile_version == current.profile_version
                ready, _issues = self.service.validate_authoritative_standard(profile)
                role_values = (
                    profile.smart_lbs_devref, profile.smart_breaker_devref, profile.smart_ground_devref,
                    profile.normal_lbs_devref, profile.normal_breaker_devref, profile.normal_ground_devref,
                )
                configured = sum(1 for value in role_values if str(value).strip())
                unique_files = len({str(value).casefold() for value in role_values if str(value).strip()})
                state = "ACTIVE" if is_active else "ARCHIVED"
                readiness = "READY" if ready else "NOT READY"
                lock_label = " · LOCKED" if profile.locked else ""
                label = (
                    f"{profile.site_name} / {profile_name} / V{profile.profile_version} · {state} · {readiness}{lock_label}"
                    f" · 覆盖 {configured}/6 · 标准文件 {unique_files}"
                )
                self.profile_selector.addItem(label, (profile_name, profile.profile_version, is_active))
                index = self.profile_selector.count() - 1
                target_version = select_version if select_version is not None else current.profile_version
                if profile_name == select_name and profile.profile_version == target_version:
                    selected_index = index

        self.profile_selector.blockSignals(False)
        if selected_index >= 0:
            self.profile_selector.setCurrentIndex(selected_index)
            self._profile_selection_changed()
        elif self.profile_selector.count() > 0:
            self.profile_selector.setCurrentIndex(0)
            self._profile_selection_changed()
        else:
            self._new_profile(clear_selection=False)

    @staticmethod
    def _devref_short(devref: str) -> str:
        value = (devref or "").strip()
        if not value:
            return "-"
        tail = value.split(":")[-1].strip()
        if tail:
            return tail.lstrip("#")
        return value

    def _set_readonly_cell(self, row: int, column: int, text: str, *, kind: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if kind:
            item.setData(Qt.ItemDataRole.UserRole, kind)
        self.standard_table.setItem(row, column, item)
        return item

    @staticmethod
    def _format_dimension(value: object) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "-"
        if number <= 0:
            return "-"
        return str(int(round(number))) if abs(number - round(number)) < 1e-9 else f"{number:g}"

    def _symbol_meta(self, devref: str) -> dict[str, object]:
        return dict(self._symbol_catalog.get(str(devref).strip(), {}))

    @staticmethod
    def _catalog_from_standard_records(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        catalog: dict[str, dict[str, object]] = {}
        for raw in records:
            row = dict(raw)
            devref = str(row.get("devref", "")).strip()
            if not devref:
                continue
            catalog[devref] = {
                "devref": devref,
                "element_tag": str(row.get("element_tag", "")).strip(),
                "element_id": str(row.get("element_id", "")).strip(),
                "source_file": str(row.get("original_name", "")).strip(),
                "width": float(row.get("width", 0.0) or 0.0),
                "height": float(row.get("height", 0.0) or 0.0),
                "align_center": list(row.get("align_center", [])),
                "pins": list(row.get("pins", [])),
                "pin_ids": list(row.get("pin_ids", [])),
                "pin_indices": list(row.get("pin_indices", [])),
                "rotations": [0, 90, 180, 270],
                "count": 1,
                "sha256": str(row.get("sha256", "")).strip(),
                "managed_path": str(row.get("managed_path", "")).strip(),
                "p_NameString": "",
                "key_name": "",
            }
        return catalog

    def _editor_standard_records(self) -> list[dict[str, object]]:
        """Return current ACTIVE files plus pending uploads, with pending files winning.

        This makes partial updates safe: replacing one device standard does not force
        the user to re-upload the other five standard files.
        """
        name, _version, active = self._selected_profile_key()
        current = self.service.load_profiles().get(name) if name and active else None
        merged: dict[str, dict[str, object]] = {}
        for raw in (current.managed_standard_files if current else []):
            row = dict(raw)
            devref = str(row.get("devref", "")).strip()
            if devref:
                merged[devref.casefold()] = row
        for raw in self._pending_standard_file_records:
            row = dict(raw)
            devref = str(row.get("devref", "")).strip()
            if devref:
                merged[devref.casefold()] = row
        return sorted(merged.values(), key=lambda row: str(row.get("devref", "")).casefold())

    def _fill_authoritative_combo(
        self, combo: WheelSafeComboBox, expected_tag: str, selected: str, records: list[dict[str, object]]
    ) -> None:
        """Populate with every uploaded authoritative G.

        ``expected_tag`` remains a business-drawing locator hint for the built-in
        role, not an upload restriction. The user-selected row is authoritative;
        filename/XML inference never blocks or silently reassigns a standard file.
        """
        combo.blockSignals(True)
        combo.clear()
        combo.setEditable(False)
        for raw in records:
            row = dict(raw)
            devref = str(row.get("devref", "")).strip()
            if not devref:
                continue
            filename = Path(str(row.get("original_name", "")).strip() or "standard.g").name
            combo.addItem(filename, devref)
            parsed_tag = str(row.get("element_tag", "")).strip() or "-"
            combo.setItemData(
                combo.count() - 1,
                "\n".join([
                    f"文件：{filename}",
                    f"devref：{devref}",
                    f"上传 G 解析 XML：{parsed_tag}",
                    f"当前行检查对象 XML：{expected_tag or '-'}",
                    f"主体 ID：{str(row.get('element_id', '')).strip() or '-'}",
                    "绑定依据：用户明确选择当前设备角色；解析类型仅作参考，不限制绑定。",
                ]),
                Qt.ItemDataRole.ToolTipRole,
            )
        index = combo.findData(selected) if selected else -1
        combo.setCurrentIndex(index if index >= 0 else -1)
        combo.blockSignals(False)
        self._refresh_standard_row(combo)

    def _populate_builtin_standard_combos(self, records: list[dict[str, object]], *, preserve_current: bool = True) -> None:
        selections = {
            "lbs": str(self.lbs_combo.currentData() or "").strip() if preserve_current else "",
            "breaker": str(self.breaker_combo.currentData() or "").strip() if preserve_current else "",
            "ground": str(self.ground_combo.currentData() or "").strip() if preserve_current else "",
            "normal_lbs": str(self.normal_lbs_combo.currentData() or "").strip() if preserve_current else "",
            "normal_breaker": str(self.normal_breaker_combo.currentData() or "").strip() if preserve_current else "",
            "normal_ground": str(self.normal_ground_combo.currentData() or "").strip() if preserve_current else "",
        }
        self._fill_authoritative_combo(self.lbs_combo, "CBreakerDis", selections["lbs"], records)
        self._fill_authoritative_combo(self.breaker_combo, "CBreakerDis", selections["breaker"], records)
        self._fill_authoritative_combo(self.ground_combo, "ZhaiWaiJieDiDaoZha", selections["ground"], records)
        self._fill_authoritative_combo(self.normal_lbs_combo, "CBreakerDis", selections["normal_lbs"], records)
        self._fill_authoritative_combo(self.normal_breaker_combo, "CBreakerDis", selections["normal_breaker"], records)
        self._fill_authoritative_combo(self.normal_ground_combo, "ZhaiWaiJieDiDaoZha", selections["normal_ground"], records)

    def _refresh_symbol_properties(self, row: int, devref: str) -> None:
        meta = self._symbol_meta(devref)
        element_id = str(meta.get("element_id", "")).strip() or (devref.split(":", 1)[1] if ":" in devref else "-")
        width = self._format_dimension(meta.get("width"))
        height = self._format_dimension(meta.get("height"))
        size_text = f"{width}×{height}" if width != "-" and height != "-" else "-"
        align = meta.get("align_center", [])
        if isinstance(align, (list, tuple)) and len(align) >= 2:
            align_text = f"({self._format_dimension(align[0])},{self._format_dimension(align[1])})"
        else:
            align_text = "-"
        pins = meta.get("pins", [])
        if isinstance(pins, list) and pins:
            pin_texts = [
                f"({self._format_dimension(pair[0])},{self._format_dimension(pair[1])})"
                for pair in pins
                if isinstance(pair, (list, tuple)) and len(pair) >= 2
            ]
            pins_text = f"{len(pin_texts)}: " + "; ".join(pin_texts)
        else:
            pins_text = "-"
        for column, value in ((4, element_id or "-"), (5, size_text), (6, align_text), (7, pins_text)):
            item = self.standard_table.item(row, column)
            if item is None:
                item = self._set_readonly_cell(row, column, value)
            else:
                item.setText(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(
                "\n".join([
                    f"devref: {devref or '-'}",
                    f"XML: {meta.get('element_tag', '-') or '-'}",
                    f"主体 ID: {element_id or '-'}",
                    f"w/h: {size_text}",
                    f"AlignCenter: {align_text}",
                    f"Pins: {pins_text}",
                    f"旋转样本: {meta.get('rotations', []) or '-'}",
                    f"来源: {meta.get('source_file', '-') or '-'}",
                    f"p_NameString: {meta.get('p_NameString', '-') or '-'}",
                    f"key_name: {meta.get('key_name', '-') or '-'}",
                ])
            )

    def _clear_custom_standard_rows(self) -> None:
        while self.standard_table.rowCount() > len(self._standard_specs):
            self.standard_table.removeRow(self.standard_table.rowCount() - 1)

    def _custom_standard_rows(self) -> list[int]:
        result: list[int] = []
        for row in range(len(self._standard_specs), self.standard_table.rowCount()):
            marker_item = self.standard_table.item(row, 0)
            if marker_item is not None and marker_item.data(Qt.ItemDataRole.UserRole) == "custom":
                result.append(row)
        return result

    def _set_standard_file_cell(self, row: int, devref: str) -> QTableWidgetItem:
        """Render the authoritative G as a normal table cell and keep devref as data."""
        devref = str(devref or "").strip()
        meta = self._symbol_meta(devref)
        filename = Path(str(meta.get("source_file", "")).strip()).name
        display = filename or (self._devref_short(devref) if devref else "-")
        item = self.standard_table.item(row, 3)
        if item is None:
            item = self._set_readonly_cell(row, 3, display)
        else:
            item.setText(display)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setData(Qt.ItemDataRole.UserRole, devref)
        item.setToolTip(
            "\n".join([
                f"文件：{filename or '-'}",
                f"devref：{devref or '-'}",
                f"XML：{str(meta.get('element_tag', '')).strip() or '-'}",
                f"主体 ID：{str(meta.get('element_id', '')).strip() or '-'}",
                "绑定方式：选中设备角色后，由用户直接上传标准图元 G。",
            ])
        )
        return item

    def _standard_file_devref(self, row: int) -> str:
        item = self.standard_table.item(row, 3)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _insert_custom_standard_row(self, entry: dict[str, object] | None = None) -> int:
        entry = dict(entry or {})
        row = self.standard_table.rowCount()
        self.standard_table.insertRow(row)

        scope_combo = WheelSafeComboBox()
        scope_combo.addItems(["ANY", "SMART", "NORMAL"])
        scope = str(entry.get("scope", "ANY")).strip().upper() or "ANY"
        scope_combo.setCurrentText(scope if scope in {"ANY", "SMART", "NORMAL"} else "ANY")
        self.standard_table.setCellWidget(row, 0, scope_combo)
        marker = QTableWidgetItem("")
        marker.setData(Qt.ItemDataRole.UserRole, "custom")
        marker.setData(Qt.ItemDataRole.UserRole + 1, str(entry.get("uid", "")).strip() or uuid4().hex)
        # Keep a hidden marker in the scope cell's item while the combo is visible.
        self.standard_table.setItem(row, 0, marker)

        role_item = QTableWidgetItem(str(entry.get("role", "")).strip() or "自定义设备")
        self.standard_table.setItem(row, 1, role_item)
        tag_item = QTableWidgetItem(str(entry.get("element_tag", "")).strip())
        self.standard_table.setItem(row, 2, tag_item)

        selected_devref = str(entry.get("standard_devref", "")).strip()
        self._set_standard_file_cell(row, selected_devref)

        for column in (4, 5, 6, 7):
            self._set_readonly_cell(row, column, "-")

        match_combo = WheelSafeComboBox()
        match_combo.addItems(["devref", "XML元素", "p_NameString", "key_name"])
        match_attr = str(entry.get("match_attr", "devref")).strip() or "devref"
        match_combo.setCurrentText(match_attr if match_attr in {"devref", "XML元素", "p_NameString", "key_name"} else "devref")
        self.standard_table.setCellWidget(row, 8, match_combo)
        self.standard_table.setItem(row, 9, QTableWidgetItem(str(entry.get("match_value", "")).strip()))
        self._set_readonly_cell(row, 10, "-")
        self._set_readonly_cell(row, 11, "待确认")

        self._refresh_custom_standard_row(row)
        fit_known_dense_table(self.standard_table)
        return row

    def _refresh_custom_standard_row(self, row: int) -> None:
        if row < len(self._standard_specs) or row >= self.standard_table.rowCount():
            return
        devref = self._standard_file_devref(row)
        self._set_standard_file_cell(row, devref)
        meta = self._symbol_meta(devref)
        tag_item = self.standard_table.item(row, 2)
        if tag_item is not None and not tag_item.text().strip() and meta.get("element_tag"):
            tag_item.setText(str(meta.get("element_tag", "")))
        self._refresh_symbol_properties(row, devref)
        source_item = self.standard_table.item(row, 10) or self._set_readonly_cell(row, 10, "-")
        source_file = Path(str(meta.get("source_file", "")).strip()).name
        source_item.setText("用户上传" if devref and source_file else ("未上传" if not devref else "-"))
        source_item.setToolTip(source_file or "未上传")
        status_item = self.standard_table.item(row, 11) or self._set_readonly_cell(row, 11, "待确认")
        if not devref:
            status_item.setText("缺少标准图元")
        elif not (self.standard_table.item(row, 2) and self.standard_table.item(row, 2).text().strip()):
            status_item.setText("缺少 XML 元素")
        else:
            status_item.setText("就绪")

    def _add_custom_standard(self) -> None:
        row = self._insert_custom_standard_row()
        self.standard_table.selectRow(row)
        self.standard_table.scrollToItem(self.standard_table.item(row, 1))
        self._update_action_state()

    def _delete_selected_custom_standard(self) -> None:
        row = self.standard_table.currentRow()
        if row < len(self._standard_specs):
            QMessageBox.information(self, "系统标准不能删除", "前 6 行是现有 RMU 系统标准。你可以修改标准图元，但不能删除这些系统规则。")
            return
        if row >= 0:
            self.standard_table.removeRow(row)
        self._update_action_state()

    def _add_unmapped_scanned_symbols(self) -> None:
        """Legacy entry retained for compatibility; business G can no longer become a standard."""
        QMessageBox.information(
            self,
            "必须上传标准图元",
            "业务单线图中发现的 devref 只能作为检查线索，不能直接加入图元标准。\n"
            "请通过“标准管理 → 上传标准图元 G”上传对应的真实图元定义文件，再将其绑定到设备角色。",
        )

    def _collect_custom_symbols(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in self._custom_standard_rows():
            marker_item = self.standard_table.item(row, 0)
            scope_combo = self.standard_table.cellWidget(row, 0)
            match_combo = self.standard_table.cellWidget(row, 8)
            if not isinstance(scope_combo, WheelSafeComboBox) or not isinstance(match_combo, WheelSafeComboBox):
                continue
            devref = self._standard_file_devref(row)
            role = (self.standard_table.item(row, 1).text() if self.standard_table.item(row, 1) else "").strip()
            element_tag = (self.standard_table.item(row, 2).text() if self.standard_table.item(row, 2) else "").strip()
            match_value = (self.standard_table.item(row, 9).text() if self.standard_table.item(row, 9) else "").strip()
            if not devref and not role and not element_tag:
                continue
            meta = self._symbol_meta(devref)
            result.append({
                "uid": str(marker_item.data(Qt.ItemDataRole.UserRole + 1) or uuid4().hex) if marker_item else uuid4().hex,
                "scope": scope_combo.currentText().strip().upper() or "ANY",
                "role": role or self._devref_short(devref) or "自定义设备",
                "element_tag": element_tag,
                "standard_devref": devref,
                "match_attr": match_combo.currentText().strip() or "devref",
                "match_value": match_value,
                "enabled": True,
                "source_file": str(meta.get("source_file", "")).strip(),
            })
        return result

    def _load_custom_symbols(self, entries: list[dict[str, object]]) -> None:
        self._clear_custom_standard_rows()
        for entry in entries:
            self._insert_custom_standard_row(entry)

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.site_name.setReadOnly(not enabled)
        self.profile_name.setReadOnly(not enabled)
        for combo in (self.lbs_combo, self.breaker_combo, self.ground_combo, self.normal_lbs_combo, self.normal_breaker_combo, self.normal_ground_combo):
            combo.setEnabled(enabled)
        for row in self._custom_standard_rows():
            for column in (0, 8):
                widget = self.standard_table.cellWidget(row, column)
                if widget is not None:
                    widget.setEnabled(enabled)
        self.standard_table.setEditTriggers(
            (QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            if enabled else QAbstractItemView.EditTrigger.NoEditTriggers
        )
        if hasattr(self, "upload_standard_button"):
            self.upload_standard_button.setEnabled(enabled)
        if hasattr(self, "share_pair_checkbox"):
            self.share_pair_checkbox.setEnabled(enabled and 0 <= self.standard_table.currentRow() < len(self._standard_specs))
        self.add_custom_button.setEnabled(enabled)
        self.delete_custom_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)

    def _current_active_profile(self) -> SiteSmartProfile | None:
        name = self._selected_profile_name()
        return self.service.load_profiles().get(name) if name else None

    def _toggle_profile_lock(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None or not active:
            QMessageBox.information(self, "请先保存标准", "锁定功能只针对已保存的当前 ACTIVE 标准版本。")
            return
        profile = self.service.load_profiles().get(name)
        if profile is None:
            return
        if profile.locked:
            if QMessageBox.question(
                self,
                "解锁当前标准",
                f"确认解锁 {name} V{profile.profile_version}？\n\n解锁后可以重新上传/绑定标准 G、修改表格并保存新版本。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return
            locked = False
        else:
            if QMessageBox.question(
                self,
                "锁定当前标准",
                f"确认锁定 {name} V{profile.profile_version}？\n\n锁定后该 ACTIVE 版本不能修改、上传标准 G、删除或恢复历史版本；仍可正常执行图元标准检查。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return
            locked = True
        try:
            saved = self.service.set_locked(name, locked)
        except ValueError as exc:
            QMessageBox.warning(self, "锁定状态更新失败", str(exc))
            return
        self._reload_profiles(saved.profile_name, saved.profile_version)
        self.activeProfileChanged.emit(saved.profile_name)

    def _new_profile(self, *_args, clear_selection: bool = True) -> None:
        if clear_selection and hasattr(self, "profile_selector"):
            self.profile_selector.blockSignals(True)
            self.profile_selector.setCurrentIndex(-1)
            self.profile_selector.blockSignals(False)
        self._selected_version = None
        self._selected_is_active = False
        self._candidate_counts.clear()
        self._symbol_catalog.clear()
        self._pending_standard_file_records = []
        self._clear_custom_standard_rows()
        self.site_name.clear()
        self.profile_name.clear()
        self.lbs_combo.clear()
        self.breaker_combo.clear()
        self.normal_lbs_combo.clear()
        self.normal_breaker_combo.clear()
        self.ground_combo.clear()
        self.normal_ground_combo.clear()
        self.scan_summary.setText("尚未上传标准图元。")
        self.profile_status.setText("新建标准：填写适用范围 / 标准名称后，点击“上传标准图元 G”建立权威标准库。")
        self.current_profile_label.setText("当前执行标准：未选择")
        self.active_profile_summary.setText("当前执行标准：尚未创建 Profile")
        self._last_scan = None
        self._set_editor_enabled(True)
        if hasattr(self, "lock_standard_button"):
            self.lock_standard_button.setText("锁定当前版本")
            self.lock_standard_button.setEnabled(False)
        self.restore_action.setEnabled(False)
        self.delete_action.setEnabled(False)
        self._update_action_state()

    def _profile_selection_changed(self, *_args) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            return
        profile = self.service.get_profile_version(name, version)
        current = self.service.load_profiles().get(name)
        if profile is None or current is None:
            return
        self._selected_version = version
        self._selected_is_active = active
        self._pending_standard_file_records = []
        records = [dict(row) for row in profile.managed_standard_files]
        self._symbol_catalog = self._catalog_from_standard_records(records)
        self._load_custom_symbols(profile.custom_symbols)
        self.site_name.setText(profile.site_name)
        self.profile_name.setText(profile.profile_name)
        self._fill_authoritative_combo(self.lbs_combo, "CBreakerDis", profile.smart_lbs_devref, records)
        self._fill_authoritative_combo(self.breaker_combo, "CBreakerDis", profile.smart_breaker_devref, records)
        self._fill_authoritative_combo(self.ground_combo, "ZhaiWaiJieDiDaoZha", profile.smart_ground_devref, records)
        self._fill_authoritative_combo(self.normal_lbs_combo, "CBreakerDis", profile.normal_lbs_devref, records)
        self._fill_authoritative_combo(self.normal_breaker_combo, "CBreakerDis", profile.normal_breaker_devref, records)
        self._fill_authoritative_combo(self.normal_ground_combo, "ZhaiWaiJieDiDaoZha", profile.normal_ground_devref, records)
        # Refresh once more after all six scopes are loaded so shared SMART/NORMAL
        # bindings are visible in both paired status cells.
        for _scope, _role, _tag, combo, _match_attr, _match_value in self._standard_specs:
            self._refresh_standard_row(combo)
        builtin_values = (
            profile.smart_lbs_devref, profile.smart_breaker_devref, profile.smart_ground_devref,
            profile.normal_lbs_devref, profile.normal_breaker_devref, profile.normal_ground_devref,
        )
        shared_pairs = sum(
            1 for smart_value, normal_value in (
                (profile.smart_lbs_devref, profile.normal_lbs_devref),
                (profile.smart_breaker_devref, profile.normal_breaker_devref),
                (profile.smart_ground_devref, profile.normal_ground_devref),
            )
            if smart_value and normal_value and smart_value.casefold() == normal_value.casefold()
        )
        self.scan_summary.setText(
            f"标准文件 {len(profile.managed_standard_files)} 个；"
            f"检查范围覆盖 {sum(1 for value in builtin_values if value)}/6；"
            f"SMART/NORMAL 共用 {shared_pairs} 组；"
            f"自定义设备 {len(profile.custom_symbols)} 项；标准指纹 {(profile.standard_fingerprint or '-')[:16]}。"
        )
        if active:
            self.user_settings.set_value("site_profile/last_profile_name", profile.profile_name)
            ready_ok, ready_issues = self.service.validate_authoritative_standard(profile)
            fingerprint = (profile.standard_fingerprint or "-")[:16]
            lock_state = "LOCKED" if profile.locked else "UNLOCKED"
            self.profile_status.setText(
                f"ACTIVE · V{profile.profile_version} · {'READY' if ready_ok else 'NOT READY'} · {lock_state} · 标准指纹 {fingerprint} · 最后保存：{profile.updated_at or '-'}"
            )
            if not ready_ok:
                self.scan_summary.setText("当前标准不可执行：" + "；".join(ready_issues[:3]))
            self.current_profile_label.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
            self.active_profile_summary.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
        else:
            self.profile_status.setText(
                f"ARCHIVED · V{profile.profile_version} · {'LOCKED · ' if profile.locked else ''}仅供查看。当前 ACTIVE 是 V{current.profile_version}；如需回滚请点击“恢复此版本”。"
            )
            self.current_profile_label.setText(
                f"当前执行标准仍为：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
            self.active_profile_summary.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE（当前查看 V{profile.profile_version} 历史版本）"
            )
        self._last_scan = None
        editable = bool(active and not profile.locked)
        self._set_editor_enabled(editable)
        if hasattr(self, "lock_standard_button"):
            self.lock_standard_button.setText("解锁当前版本" if active and profile.locked else "锁定当前版本")
            self.lock_standard_button.setEnabled(bool(active and not self._task_busy))
        self.restore_action.setEnabled(bool(not active and not current.locked))
        self.delete_action.setEnabled(bool(active and not profile.locked))
        self._update_action_state()
        self._standard_row_selection_changed()

    def _restore_selected_version(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择标准", "请先选择需要恢复的历史标准版本。")
            return
        if active:
            QMessageBox.information(self, "已经是当前版本", f"{name} V{version} 已经是 ACTIVE 版本。")
            return
        current = self.service.load_profiles().get(name)
        if current is None:
            return
        if current.locked:
            QMessageBox.information(self, "当前标准已锁定", f"{name} V{current.profile_version} 已锁定。请先解锁后再删除。")
            return
        if QMessageBox.question(
            self,
            "恢复历史版本",
            f"将 {name} V{version} 的图元 devref 与几何标准恢复为新的当前版本。\n"
            f"现有 ACTIVE V{current.profile_version} 会保留在历史中，不会删除。\n\n继续吗？",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            restored = self.service.restore_version(name, version)
        except ValueError as exc:
            QMessageBox.warning(self, "恢复失败", str(exc))
            return
        self._reload_profiles(restored.profile_name, restored.profile_version)
        self.activeProfileChanged.emit(restored.profile_name)
        QMessageBox.information(
            self,
            "已恢复",
            f"已将历史 V{version} 恢复为新的 ACTIVE V{restored.profile_version}。后续一致性处理使用 V{restored.profile_version}。",
        )

    def _fill_candidate_combo(self, combo: WheelSafeComboBox, counts: dict[str, int], selected: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        normalized_counts = {str(key): int(value) for key, value in counts.items()}
        self._candidate_counts[id(combo)] = normalized_counts
        total = sum(max(0, int(value)) for value in normalized_counts.values())
        rows = sorted(normalized_counts.items(), key=lambda row: (-int(row[1]), row[0].casefold()))
        for devref, count in rows:
            confidence = (count / total) if total else 0.0
            combo.addItem(f"{devref}   [{count}, {confidence:.0%}]", devref)
        if selected and combo.findData(selected) < 0:
            combo.addItem(selected, selected)
        index = combo.findData(selected)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        self._refresh_standard_row(combo)

    def _refresh_standard_row(self, combo: WheelSafeComboBox) -> None:
        specs = getattr(self, "_standard_specs", [])
        row = next((idx for idx, (_kind, _role, _tag, widget, _match_attr, _match_value) in enumerate(specs) if widget is combo), -1)
        if row < 0 or not hasattr(self, "standard_table"):
            return
        selected = str(combo.currentData() or combo.currentText() or "").strip()
        self._set_standard_file_cell(row, selected)
        self._refresh_symbol_properties(row, selected)
        meta = self._symbol_meta(selected)
        source_item = self.standard_table.item(row, 10) or self._set_readonly_cell(row, 10, "-")
        status_item = self.standard_table.item(row, 11) or self._set_readonly_cell(row, 11, "未上传")
        source_file = Path(str(meta.get("source_file", "")).strip()).name
        source_item.setText("用户上传" if selected and source_file else "未上传")
        source_item.setToolTip(source_file or "未上传")
        status_text = "READY" if selected and meta else "缺少标准图元"
        if row < len(self._standard_specs) and selected and meta:
            expected_tag = str(self._standard_specs[row][2] or "").strip()
            actual_tag = str(meta.get("element_tag", "") or "").strip()
            if expected_tag and actual_tag and expected_tag != actual_tag:
                status_text = "READY · XML参考不同"
                status_item.setToolTip(
                    f"当前设备角色由用户明确绑定。上传 G 解析 XML={actual_tag}；检查对象 XML={expected_tag}。"
                    "这不会阻止保存/检查，但请确认当前行确实是你希望绑定的设备角色。"
                )
            pair_row = self._paired_builtin_row(row)
            if pair_row >= 0:
                paired = str(self._standard_specs[pair_row][3].currentData() or "").strip()
                if paired and paired.casefold() == selected.casefold():
                    pair_scope = self._standard_specs[pair_row][0]
                    suffix = " · XML参考不同" if "XML参考不同" in status_text else ""
                    status_text = f"READY · 与 {pair_scope} 共用{suffix}"
        status_item.setText(status_text)
        if self.standard_table.currentRow() == row and hasattr(self, "share_pair_checkbox"):
            self._standard_row_selection_changed()
        fit_known_dense_table(self.standard_table)


    def _scan_samples(self) -> None:
        """Upload exactly one authoritative icon G into the currently selected role."""
        if not self.site_name.text().strip():
            QMessageBox.warning(self, "Site Name", "请先输入适用范围，再上传标准图元 G。")
            return
        if not self.profile_name.text().strip():
            QMessageBox.warning(self, "Profile Name", "请先输入标准名称。")
            return
        selected_name, selected_version, selected_active = self._selected_profile_key()
        selected_profile = self.service.load_profiles().get(selected_name) if selected_name and selected_active else None
        if selected_profile is not None and selected_profile.locked:
            QMessageBox.information(
                self,
                "当前标准已锁定",
                f"{selected_name} V{selected_version} 已锁定，不能上传或替换标准 G。请先点击“解锁当前版本”。",
            )
            return

        row = self.standard_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "先选择设备角色",
                "请先在“标准定义”表格中选中要设置的设备角色，例如 NORMAL / Circuit Breaker，"
                "然后点击上传。一个 G 文件只绑定这一行。",
            )
            return

        typed_name = self.profile_name.text().strip()
        selected_name, _version, _active = self._selected_profile_key()
        existing = self.service.load_profiles().get(typed_name)
        if existing is not None and selected_name != typed_name:
            QMessageBox.warning(
                self,
                "标准名称已存在",
                f"图元标准“{typed_name}”已存在。请在“标准版本”下拉框中选择后更新，或者使用新的标准名称。",
            )
            return

        if row < len(self._standard_specs):
            scope, role_label, expected_tag, target_combo, _match_attr, _match_value = self._standard_specs[row]
            role_display = f"{scope} / {role_label}"
        else:
            target_combo = None
            scope_widget = self.standard_table.cellWidget(row, 0)
            scope = scope_widget.currentText().strip().upper() if isinstance(scope_widget, WheelSafeComboBox) else "ANY"
            role_label = (self.standard_table.item(row, 1).text() if self.standard_table.item(row, 1) else "").strip() or "自定义设备"
            expected_tag = (self.standard_table.item(row, 2).text() if self.standard_table.item(row, 2) else "").strip()
            role_display = f"{scope} / {role_label}"

        share_pair = bool(row < len(self._standard_specs) and self.share_pair_checkbox.isChecked())
        if share_pair:
            role_display = f"SMART + NORMAL / {role_label}"

        recent = self.user_settings.resolve_directory(
            "recent_paths/site_profile/standard_icon_directory", fallback=Path.home()
        ).directory
        selected_file, _filter = QFileDialog.getOpenFileName(
            self,
            f"为 {role_display} 选择标准图元 G",
            str(recent),
            "G Icon Files (*.g);;All Files (*.*)",
        )
        if not selected_file:
            return
        path = Path(selected_file)
        self.user_settings.set_path("recent_paths/site_profile/standard_icon_directory", path.parent)
        try:
            record = dict(self.service.prepare_standard_file_records([path])[0])
        except Exception as exc:
            QMessageBox.critical(self, "标准图元无效", str(exc))
            return

        actual_tag = str(record.get("element_tag", "")).strip()

        devref = str(record.get("devref", "")).strip()
        pending_by_devref = {
            str(item.get("devref", "")).casefold(): dict(item)
            for item in self._pending_standard_file_records
            if str(item.get("devref", "")).strip()
        }
        pending_by_devref[devref.casefold()] = record
        self._pending_standard_file_records = list(pending_by_devref.values())

        records = self._editor_standard_records()
        self._symbol_catalog = self._catalog_from_standard_records(records)
        self._populate_builtin_standard_combos(records, preserve_current=True)
        for custom_row in self._custom_standard_rows():
            self._refresh_custom_standard_row(custom_row)

        # Bind the uploaded file to the selected role. The same authoritative G
        # is allowed to serve both SMART and NORMAL for the same device role.
        # This is common for grounding switches and is also valid for LBS/CB when
        # the project actually uses one identical symbol in both cabinet classes.
        if row < len(self._standard_specs):
            target_combo = self._standard_specs[row][3]
            index = target_combo.findData(devref)
            target_combo.setCurrentIndex(index if index >= 0 else -1)
            if share_pair:
                pair_row = self._paired_builtin_row(row)
                if pair_row >= 0:
                    pair_combo = self._standard_specs[pair_row][3]
                    pair_index = pair_combo.findData(devref)
                    pair_combo.setCurrentIndex(pair_index if pair_index >= 0 else -1)
                    self._refresh_standard_row(pair_combo)
                self._refresh_standard_row(target_combo)
                self._standard_row_selection_changed()
        else:
            if not expected_tag:
                tag_item = self.standard_table.item(row, 2)
                if tag_item is not None:
                    tag_item.setText(actual_tag)
            self._set_standard_file_cell(row, devref)
            self._refresh_custom_standard_row(row)

        self._last_scan = None
        shared_text = "并同时用于 SMART / NORMAL 两个检查范围" if share_pair else "仅绑定当前检查范围"
        reference_note = (
            f" 上传 G 解析 XML={actual_tag or '-'}；当前行检查对象 XML={expected_tag or '-'}，二者仅作为参考，不限制人工绑定。"
            if expected_tag and actual_tag and actual_tag != expected_tag else ""
        )
        self.scan_summary.setText(
            f"已将 {path.name} 作为 {role_display} 的权威标准图元，{shared_text}。"
            "保存后只按当前标准中已配置的设备角色检查业务单线图。" + reference_note
        )
        self.profile_status.setText(
            f"待保存：{role_display} → {devref}。devref、w/h、AlignCenter、pin/连接锚点均以这个上传 G 为准。"
        )
        self._update_action_state()

    def _on_scan_error(self, details: str) -> None:
        self.scan_progress.setValue(0)
        message = str(details).split("\n\n---TRACEBACK---", 1)[0].strip()
        QMessageBox.critical(self, "扫描失败", message or str(details))

    def _on_scan_finished(self) -> None:
        self._scan_worker = None
        self.scan_progress.setVisible(False)
        self._update_action_state()

    def _on_scan_result(self, scan: SmartProfileScanResult, files: list[Path]) -> None:
        self._last_scan = scan
        merged_catalog = {str(key): dict(value) for key, value in self._symbol_catalog.items()}
        for devref, meta in scan.symbol_catalog.items():
            existing = merged_catalog.get(devref, {})
            combined = dict(existing)
            for key, value in dict(meta).items():
                if value not in ("", None, [], 0, 0.0) or key not in combined:
                    combined[key] = value
            merged_catalog[devref] = combined
        self._symbol_catalog = merged_catalog
        self.scan_progress.setValue(100)
        def uploaded_counts(expected_tag: str, observed: dict[str, int]) -> dict[str, int]:
            values = {str(key): int(value) for key, value in observed.items()}
            for devref, meta in scan.symbol_catalog.items():
                if str(meta.get("element_tag", "")).strip() == expected_tag:
                    values.setdefault(str(devref), 0)
            return values

        current_fixed = {
            "lbs": str(self.lbs_combo.currentData() or "").strip(),
            "breaker": str(self.breaker_combo.currentData() or "").strip(),
            "ground": str(self.ground_combo.currentData() or "").strip(),
            "normal_lbs": str(self.normal_lbs_combo.currentData() or "").strip(),
            "normal_breaker": str(self.normal_breaker_combo.currentData() or "").strip(),
            "normal_ground": str(self.normal_ground_combo.currentData() or "").strip(),
        }
        self._fill_candidate_combo(self.lbs_combo, uploaded_counts("CBreakerDis", scan.lbs_counts), scan.suggested_lbs_devref or current_fixed["lbs"])
        self._fill_candidate_combo(self.breaker_combo, uploaded_counts("CBreakerDis", scan.breaker_counts), scan.suggested_breaker_devref or current_fixed["breaker"])
        self._fill_candidate_combo(self.ground_combo, uploaded_counts("ZhaiWaiJieDiDaoZha", scan.ground_counts), scan.suggested_ground_devref or current_fixed["ground"])
        self._fill_candidate_combo(self.normal_lbs_combo, uploaded_counts("CBreakerDis", scan.normal_lbs_counts), scan.suggested_normal_lbs_devref or current_fixed["normal_lbs"])
        self._fill_candidate_combo(self.normal_breaker_combo, uploaded_counts("CBreakerDis", scan.normal_breaker_counts), scan.suggested_normal_breaker_devref or current_fixed["normal_breaker"])
        self._fill_candidate_combo(self.normal_ground_combo, uploaded_counts("ZhaiWaiJieDiDaoZha", scan.normal_ground_counts), scan.suggested_normal_ground_devref or current_fixed["normal_ground"])
        for row in self._custom_standard_rows():
            self._refresh_custom_standard_row(row)
        lbs_conf = scan.lbs_candidates[0].confidence if scan.lbs_candidates else 0.0
        brk_conf = scan.breaker_candidates[0].confidence if scan.breaker_candidates else 0.0
        ground_conf = scan.ground_candidates[0].confidence if scan.ground_candidates else 0.0
        normal_lbs_conf = scan.normal_lbs_candidates[0].confidence if scan.normal_lbs_candidates else 0.0
        normal_brk_conf = scan.normal_breaker_candidates[0].confidence if scan.normal_breaker_candidates else 0.0
        normal_ground_conf = scan.normal_ground_candidates[0].confidence if scan.normal_ground_candidates else 0.0
        self.scan_summary.setText(
            f"已读取 {len(self._pending_standard_file_records)} 个用户上传的标准图元 G；"
            f"识别 {len(scan.symbol_catalog)} 个标准 devref。请在下方为 6 个 RMU 基础角色各选择唯一标准图元后保存。"
        )
        old = self.service.load_profiles().get(self._selected_profile_name() or self.profile_name.text().strip())
        changes: list[str] = []
        if old is not None:
            pairs = [
                ("SMART LBS", old.smart_lbs_devref, scan.suggested_lbs_devref),
                ("SMART Q", old.smart_breaker_devref, scan.suggested_breaker_devref),
                ("SMART 接地刀闸", old.smart_ground_devref, scan.suggested_ground_devref),
                ("NORMAL LBS", old.normal_lbs_devref, scan.suggested_normal_lbs_devref),
                ("NORMAL Q", old.normal_breaker_devref, scan.suggested_normal_breaker_devref),
                ("NORMAL 接地刀闸", old.normal_ground_devref, scan.suggested_normal_ground_devref),
            ]
            changes = [label for label, before, after in pairs if after and before != after]
            selected_now = {value for value in (
                scan.suggested_lbs_devref,
                scan.suggested_breaker_devref,
                scan.suggested_ground_devref,
                scan.suggested_normal_lbs_devref,
                scan.suggested_normal_breaker_devref,
                scan.suggested_normal_ground_devref,
            ) if value}
            selected_now.update(
                str(entry.get("standard_devref", "")).strip()
                for entry in self._collect_custom_symbols()
                if str(entry.get("standard_devref", "")).strip()
            )
            learned_geometry = {key: list(value) for key, value in scan.geometry_templates.items() if key in selected_now}
            if learned_geometry and learned_geometry != old.geometry_templates:
                changes.append("图元几何（大小/端口）")
        if changes:
            self.profile_status.setText(
                f"检测到图元标准变化：{', '.join(changes)}。保存后将生成 V{old.profile_version + 1} 并设为 ACTIVE；旧版本保留，可回滚。"
            )
        elif scan.warnings:
            self.profile_status.setText("；".join(scan.warnings[:3]))
        elif min(lbs_conf, brk_conf, ground_conf, normal_lbs_conf, normal_brk_conf, normal_ground_conf) < 0.8:
            self.profile_status.setText("至少一类候选一致率低于 80%，请人工检查 LBS / Circuit Breaker / 接地刀闸候选后再保存。")
        else:
            self.profile_status.setText("标准图元读取完成。请确认 6 个 RMU 基础角色都绑定了本次上传的唯一图元，然后保存为 ACTIVE 标准。")

    def _save_profile(self) -> None:
        selected_name, selected_version, selected_active = self._selected_profile_key()
        selected_profile = self.service.load_profiles().get(selected_name) if selected_name and selected_active else None
        if selected_profile is not None and selected_profile.locked:
            QMessageBox.information(
                self, "当前标准已锁定",
                f"{selected_name} V{selected_version} 已锁定，当前版本不能修改或保存。请先解锁。",
            )
            return
        site_name = self.site_name.text().strip()
        profile_name = self.profile_name.text().strip()
        lbs = str(self.lbs_combo.currentData() or "").strip()
        breaker = str(self.breaker_combo.currentData() or "").strip()
        normal_lbs = str(self.normal_lbs_combo.currentData() or "").strip()
        normal_breaker = str(self.normal_breaker_combo.currentData() or "").strip()
        ground = str(self.ground_combo.currentData() or "").strip()
        normal_ground = str(self.normal_ground_combo.currentData() or "").strip()
        custom_symbols = self._collect_custom_symbols()
        invalid_custom = [
            entry for entry in custom_symbols
            if not str(entry.get("element_tag", "")).strip() or not str(entry.get("standard_devref", "")).strip()
        ]
        if invalid_custom:
            QMessageBox.warning(self, "自定义图元未完成", "自定义设备图元必须至少填写“XML 元素”和“标准图元 devref”。请补充后再保存。")
            return
        if not site_name or not profile_name:
            QMessageBox.warning(self, "标准未完成", "适用范围和标准名称不能为空。")
            return
        required_roles = {
            "SMART / LBS": lbs,
            "SMART / Circuit Breaker": breaker,
            "SMART / 接地刀闸": ground,
            "NORMAL / LBS": normal_lbs,
            "NORMAL / Circuit Breaker": normal_breaker,
            "NORMAL / 接地刀闸": normal_ground,
        }
        if not any(required_roles.values()) and not custom_symbols:
            QMessageBox.warning(
                self, "标准未完成",
                "请至少为 1 个设备角色上传并绑定标准图元 G。可以只配置当前需要检查的角色，不要求一次补齐 6 个。",
            )
            return

        # v2.18.76: the saved standard is built only from user-uploaded icon G
        # files. Historical business-scan observations/confidence never participate
        # in a new authoritative Profile version.
        all_records = self._editor_standard_records()
        selected_devrefs = {
            value for value in (lbs, breaker, ground, normal_lbs, normal_breaker, normal_ground) if value
        }
        selected_devrefs.update(
            str(entry.get("standard_devref", "")).strip()
            for entry in custom_symbols
            if str(entry.get("standard_devref", "")).strip()
        )
        managed_standard_files = [
            dict(row) for row in all_records
            if str(row.get("devref", "")).strip() in selected_devrefs
        ]
        sample_files = [
            str(row.get("original_name", "")).strip()
            for row in managed_standard_files
            if str(row.get("original_name", "")).strip()
        ]
        self._symbol_catalog = self._catalog_from_standard_records(managed_standard_files)
        geometry_templates: dict[str, list[dict[str, object]]] = {}

        # These legacy statistical fields remain in the JSON schema only for old
        # profile compatibility. For uploaded authoritative standards they are not
        # evidence and are deliberately reset.
        smart_rmu_count = normal_rmu_count = ignored_rmu_count = 0
        lbs_observations = breaker_observations = 0
        normal_lbs_observations = normal_breaker_observations = 0
        ground_observations = normal_ground_observations = 0
        lbs_confidence = breaker_confidence = 0.0
        normal_lbs_confidence = normal_breaker_confidence = 0.0
        ground_confidence = normal_ground_confidence = 0.0
        lbs_candidates = {lbs: 1} if lbs else {}
        breaker_candidates = {breaker: 1} if breaker else {}
        normal_lbs_candidates = {normal_lbs: 1} if normal_lbs else {}
        normal_breaker_candidates = {normal_breaker: 1} if normal_breaker else {}
        ground_candidates = {ground: 1} if ground else {}
        normal_ground_candidates = {normal_ground: 1} if normal_ground else {}

        old = self.service.load_profiles().get(profile_name)
        candidate_profile = SiteSmartProfile(
            profile_name=profile_name,
            site_name=site_name,
            smart_lbs_devref=lbs,
            smart_breaker_devref=breaker,
            normal_lbs_devref=normal_lbs,
            normal_breaker_devref=normal_breaker,
            smart_ground_devref=ground,
            normal_ground_devref=normal_ground,
            sample_files=sample_files,
            smart_rmu_count=smart_rmu_count,
            normal_rmu_count=normal_rmu_count,
            ignored_rmu_count=ignored_rmu_count,
            lbs_observations=lbs_observations,
            breaker_observations=breaker_observations,
            normal_lbs_observations=normal_lbs_observations,
            normal_breaker_observations=normal_breaker_observations,
            ground_observations=ground_observations,
            normal_ground_observations=normal_ground_observations,
            lbs_confidence=lbs_confidence,
            breaker_confidence=breaker_confidence,
            normal_lbs_confidence=normal_lbs_confidence,
            normal_breaker_confidence=normal_breaker_confidence,
            ground_confidence=ground_confidence,
            normal_ground_confidence=normal_ground_confidence,
            lbs_candidates=lbs_candidates,
            breaker_candidates=breaker_candidates,
            normal_lbs_candidates=normal_lbs_candidates,
            normal_breaker_candidates=normal_breaker_candidates,
            ground_candidates=ground_candidates,
            normal_ground_candidates=normal_ground_candidates,
            geometry_templates=geometry_templates,
            custom_symbols=custom_symbols,
            symbol_catalog=self._symbol_catalog,
            managed_standard_files=managed_standard_files,
            locked=False,
        ).normalized()
        # Every required ACTIVE role must resolve to exactly one user-uploaded icon file.
        records_by_devref: dict[str, list[dict[str, object]]] = {}
        for row in candidate_profile.managed_standard_files:
            records_by_devref.setdefault(str(row.get("devref", "")).casefold(), []).append(row)
        role_tags = {
            "SMART / LBS": lbs,
            "SMART / Circuit Breaker": breaker,
            "SMART / 接地刀闸": ground,
            "NORMAL / LBS": normal_lbs,
            "NORMAL / Circuit Breaker": normal_breaker,
            "NORMAL / 接地刀闸": normal_ground,
        }
        role_errors: list[str] = []
        for label, devref in role_tags.items():
            if not devref:
                continue
            rows = records_by_devref.get(devref.casefold(), [])
            if len(rows) != 1:
                role_errors.append(f"{label}: 当前选择必须对应且只能对应 1 个本次上传/已持久化的标准图元 G。")
            elif not list(rows[0].get("pins", [])):
                role_errors.append(f"{label}: 上传图元没有 pin 定义，不能作为 RMU 电气设备标准。")
        for entry in custom_symbols:
            if not bool(entry.get("enabled", True)):
                continue
            devref = str(entry.get("standard_devref", "")).strip()
            label = str(entry.get("role", "自定义设备")).strip() or "自定义设备"
            rows = records_by_devref.get(devref.casefold(), []) if devref else []
            if len(rows) != 1:
                role_errors.append(f"自定义设备 {label}: 必须且只能绑定 1 个用户上传的标准图元 G。")
        if role_errors:
            QMessageBox.warning(self, "标准图元绑定无效", "\n".join(role_errors))
            return

        if old is not None and self.service._device_signature(old) != self.service._device_signature(candidate_profile):
            changes = []
            if old.smart_lbs_devref != candidate_profile.smart_lbs_devref:
                changes.append("SMART LBS")
            if old.smart_breaker_devref != candidate_profile.smart_breaker_devref:
                changes.append("SMART Q")
            if old.normal_lbs_devref != candidate_profile.normal_lbs_devref:
                changes.append("NORMAL LBS")
            if old.normal_breaker_devref != candidate_profile.normal_breaker_devref:
                changes.append("NORMAL Q")
            if old.smart_ground_devref != candidate_profile.smart_ground_devref:
                changes.append("SMART 接地刀闸")
            if old.normal_ground_devref != candidate_profile.normal_ground_devref:
                changes.append("NORMAL 接地刀闸")
            if old.geometry_templates != candidate_profile.geometry_templates:
                changes.append("图元几何（大小/端口）")
            if old.custom_symbols != candidate_profile.custom_symbols:
                changes.append("自定义设备图元")
            if old.symbol_catalog != candidate_profile.symbol_catalog:
                changes.append("图元属性目录")
            if QMessageBox.question(
                self,
                "更新图元标准",
                f"当前 ACTIVE 是 {profile_name} V{old.profile_version}。\n"
                f"检测到标准变化：{', '.join(changes) or '图元标准'}。\n\n"
                f"保存后将创建 V{old.profile_version + 1} 并设为 ACTIVE；V{old.profile_version} 会保留为 ARCHIVED，可随时恢复。\n"
                "后续图元标准检查会使用新的 ACTIVE 版本，包括 devref、图元大小和连接锚点几何。\n\n继续吗？",
            ) != QMessageBox.StandardButton.Yes:
                return

        try:
            profile = self.service.upsert(candidate_profile)
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.user_settings.set_value("site_profile/last_profile_name", profile.profile_name)
        self._pending_standard_file_records = []
        self._reload_profiles(profile.profile_name, profile.profile_version)
        self.activeProfileChanged.emit(profile.profile_name)
        QMessageBox.information(self, "标准已保存", f"已保存 {profile.profile_name}（适用范围：{profile.site_name}）V{profile.profile_version}。")

    def _delete_profile(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name:
            QMessageBox.information(self, "请选择标准", "请先选择需要删除的已保存图元标准。")
            return
        if not active:
            QMessageBox.information(
                self,
                "历史版本不能单独删除",
                "ARCHIVED 版本属于 Profile 的版本历史。若要删除整个 Profile，请选择其 ACTIVE 版本后操作。",
            )
            return
        current = self.service.load_profiles().get(name)
        if current is None:
            return
        if QMessageBox.question(
            self,
            "删除标准",
            f"确认删除图元标准“{name}”及其全部历史版本（当前 ACTIVE V{current.profile_version}）？",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.remove(name)
        except ValueError as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self._reload_profiles()
        self.activeProfileChanged.emit("")

    def _check_profile(self) -> None:
        self._start_profile_run(correct=False)

    def _correct_profile(self) -> None:
        if QMessageBox.question(
            self,
            "确认纠正图元标准问题",
            "将按当前 ACTIVE 图元标准纠正已定义图元的变体/devref，以及可可靠计算的 pin/ConnectLine 连接锚点位置。\n\n"
            "源 G 文件不会覆盖；纠正后的 G 会写入本次 workspace 运行目录的 corrected 文件夹，并自动执行一次复查。\n"
            "未纳入当前标准、连接关系不明确或无法可靠拟合的图元不会猜测修改。\n\n继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._start_profile_run(correct=True)

    def _start_profile_run(self, *, correct: bool = False) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name)
        if profile is None:
            QMessageBox.warning(self, "请选择标准", "请先在“标准版本”下拉框中选择并保存一个图元标准。")
            return
        if not active or version != profile.profile_version:
            QMessageBox.information(
                self,
                "请选择 ACTIVE 版本",
                f"当前选中的是历史版本。实际 ACTIVE 是 {name} V{profile.profile_version}。请在“标准版本”下拉框中选择 ACTIVE 版本后执行，或先恢复历史版本。",
            )
            return
        ready, issues = self.service.validate_authoritative_standard(profile)
        if not ready:
            QMessageBox.warning(
                self,
                "标准图元库未就绪",
                "执行图元标准检查前，至少要保存 1 个有效的权威标准图元角色。只会检查已配置的角色。\n\n" + "\n".join(issues[:8]),
            )
            return
        if not validate_input_source(self, self.source, display_name="图元标准检查输入", log=self.task.append_log):
            return
        self.source.persist_current()
        self._last_report_path = None
        self.open_report_button.setEnabled(False)
        self._last_run_mode = "CORRECT" if correct else "CHECK"
        if correct:
            self.result_summary.setText("正在按 ACTIVE 标准生成纠正副本……源 G 文件不会覆盖。")
        else:
            self.result_summary.setText("正在检查图元标准……源 G 文件不会修改。")
        run_dir = begin_managed_run(self.output_path, "symbol-standard", "correct" if correct else "check")
        settings = SmartProfileProcessingSettings(
            source_path=self.source.path(),
            input_mode=self.source.mode(),
            output_dir=run_dir,
            profile=profile,
            require_authoritative_standard=True,
        )
        processor = process_smart_profile_correction if correct else process_smart_profile_consistency
        self.task.start(lambda log, progress: processor(settings, log, progress), run_dir)

    def _update_action_state(self) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name) if name else None
        busy_scan = self._scan_worker is not None
        busy = busy_scan or self._task_busy
        authoritative_ready, _issues = self.service.validate_authoritative_standard(profile)
        ready = bool(profile and authoritative_ready and active and version == profile.profile_version)
        self.check_button.setEnabled(ready and not busy)
        self.correct_button.setEnabled(ready and not busy)
        # New profiles and ACTIVE profiles may be scanned. Archived rows are immutable.
        allow_scan = (not name) or bool(active and profile is not None and not profile.locked)
        self.scan_action.setEnabled(allow_scan and not busy)
        self.scan_action.setText("为选中角色上传 / 更新标准 G")
        if hasattr(self, "upload_standard_button"):
            self.upload_standard_button.setEnabled(allow_scan and not busy)
            self.upload_standard_button.setText("为选中角色上传 / 更新标准 G")
        locked = bool(profile.locked) if profile is not None and active else False
        can_edit = (not name) or bool(active and profile is not None and not locked)
        self.save_button.setEnabled(can_edit and not busy)
        self.add_custom_button.setEnabled(can_edit and not busy)
        selected_standard_row = self.standard_table.currentRow()
        self.delete_custom_button.setEnabled(
            can_edit and not busy and selected_standard_row >= len(self._standard_specs)
        )
        if hasattr(self, "share_pair_checkbox"):
            self.share_pair_checkbox.setEnabled(
                can_edit and not busy and 0 <= selected_standard_row < len(self._standard_specs)
            )
        if hasattr(self, "lock_standard_button"):
            self.lock_standard_button.setEnabled(bool(name and profile and active and not busy))
            self.lock_standard_button.setText("解锁当前版本" if locked else "锁定当前版本")
        current_profile = self.service.load_profiles().get(name) if name else None
        current_locked = bool(current_profile.locked) if current_profile is not None else False
        self.restore_action.setEnabled(bool(name and profile and not active and not busy and not current_locked))
        self.delete_action.setEnabled(bool(name and profile and active and not busy and not locked))
        self.new_action.setEnabled(not busy)

    def _task_busy_changed(self, busy: bool) -> None:
        self._task_busy = bool(busy)
        self._update_action_state()

    def _on_processing_result(self, result) -> None:
        self._last_report_path = None
        for path in getattr(result, "output_files", []):
            candidate = Path(path)
            if candidate.suffix.lower() == ".html" and "symbol-standard-check" in candidate.name.lower():
                self._last_report_path = candidate
                break
        self.open_report_button.setEnabled(bool(self._last_report_path and self._last_report_path.exists()))
        stats = getattr(result, "statistics", {}) or {}
        mode = str(stats.get("Mode", getattr(self, "_last_run_mode", "CHECK")) or "CHECK").upper()
        bad = int(stats.get("Nonstandard Symbols", 0) or 0)
        if stats:
            unmanaged = int(stats.get("Unmanaged Symbols", 0) or 0)
            if mode == "CORRECT":
                corrected = int(stats.get("Corrected Elements", 0) or 0)
                changed_files = int(stats.get("Corrected Files", 0) or 0)
                geometry = int(stats.get("Geometry Corrections", 0) or 0)
                text = (
                    f"纠正完成：{changed_files} 个文件发生修改，共处理 {corrected} 个标准差异，"
                    f"其中连接锚点/几何纠正 {geometry} 个；自动复查后剩余 {bad} 个不符合项。"
                )
                if unmanaged:
                    text += f" 另有 {unmanaged} 种未纳入当前标准的图元未自动处理；业务 G 不会被用于学习或补全标准。"
                text += " 源 G 未覆盖；纠正副本位于本次结果目录的 corrected 文件夹。"
            else:
                if bad:
                    text = f"检查完成：发现 {bad} 个不符合当前标准的问题。"
                else:
                    text = "检查完成：已配置的图元标准全部通过。"
                if unmanaged:
                    text += f" 另发现 {unmanaged} 种尚未纳入当前标准的图元（不计为错误）；如需纳入，请在上方设备角色中手动上传权威图元 G。"
                text += " 源 G 未修改；详细原因请查看检查报告。"
            self.result_summary.setText(text)
        if mode == "CORRECT":
            if bad > 0:
                QMessageBox.warning(
                    self,
                    "图元标准纠正完成（仍有待处理项）",
                    f"已生成纠正副本，但自动复查后仍有 {bad} 个不符合项。\n\n"
                    "这些通常属于未纳入标准、连接关系不明确或无法安全拟合的情况，程序不会猜测修改。"
                    "请点击“查看检查报告”确认。源 G 文件未覆盖。",
                )
            else:
                QMessageBox.information(
                    self,
                    "图元标准纠正完成",
                    "已按当前 ACTIVE 标准生成纠正副本并完成自动复查，未发现剩余标准差异。\n"
                    "源 G 文件未覆盖；请在本次结果目录的 corrected 文件夹中查看输出。",
                )
        elif bad > 0:
            QMessageBox.warning(
                self,
                "图元标准不一致",
                f"检测到 {bad} 个图元/几何与当前 ACTIVE 标准不一致。\n\n"
                "检查模式不会修改 G。可先查看报告；如属于标准中已定义图元的变体/devref或连接锚点位置问题，"
                "可使用“纠正标准问题”生成安全副本。\n"
                "如果是同一设备图元的旧版本 → 新版本升级，请到“基础处理 → 同类图元版本升级”处理。",
            )
        else:
            QMessageBox.information(
                self,
                "图元标准检查完成",
                "未发现图元类型/变体、devref 或连接锚点几何与当前 ACTIVE 标准不一致；源 G 文件未修改。",
            )

    def _open_report(self) -> None:
        path = self._last_report_path
        if path is None or not path.exists():
            QMessageBox.information(self, "报告不存在", "当前还没有检查报告，请先点击“检查图元标准”。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
