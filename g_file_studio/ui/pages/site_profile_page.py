from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from g_file_studio.engines.smart_profile_engine import SmartProfileScanResult, scan_smart_profile_samples
from g_file_studio.processors.common import discover_g_inputs
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
        self._last_scan: SmartProfileScanResult | None = None
        self._last_report_path: Path | None = None
        self._scan_worker: FunctionWorker | None = None
        self._scan_pool = QThreadPool.globalInstance()
        self._selected_version: int | None = None
        self._selected_is_active = False
        self._task_busy = False
        self._candidate_counts: dict[int, dict[str, int]] = {}
        self._symbol_catalog: dict[str, dict[str, object]] = {}
        help_title, help_html = APP_HELP["site_profile"]
        super().__init__(
            "图元标准检查",
            "用标准 G 文件建立可复用图元标准，检查所选 G 是否符合当前 ACTIVE 标准；需要时可生成按标准纠正后的 workspace 副本，源 G 不覆盖。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "这是通用图元标准检查与纠正模块，不绑定吉达或其他现场批处理。同一套 G 文件输入既可作为标准样本学习，也可作为待检查文件。"
                "“检查图元标准”始终只读；“纠正标准问题”只对当前 ACTIVE 标准已定义的图元生成 workspace 纠正副本，源 G 永不覆盖。"
                "带电气 pin 且与 ConnectLine 关系可可靠解析的标准图元，会保持连接线绝对端点不动并反算图元位置/尺寸；无法可靠映射时只告警不猜测。"
                "同类图元的 OLD → NEW 版本升级仍统一在“基础处理 → 同类图元版本升级”执行；吉达批处理流程不受本模块新增纠正功能影响。"
            )
        )

        profile_box = QGroupBox("当前图元标准")
        profile_layout = QVBoxLayout(profile_box)
        profile_layout.setContentsMargins(14, 18, 14, 12)
        profile_layout.setSpacing(10)

        self.active_profile_summary = QLabel("当前执行标准：尚未创建标准")
        self.active_profile_summary.setObjectName("sectionCaption")
        self.active_profile_summary.setWordWrap(True)
        profile_layout.addWidget(self.active_profile_summary)

        intro = QLabel(
            "一个图元标准可以保留多个历史版本，但同一时间只有一个 ACTIVE 版本参与标准检查。"
            "低频的新增、删除、恢复和标准样本重扫统一放在“标准管理”菜单中。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("mutedText")
        profile_layout.addWidget(intro)

        manage_row = QHBoxLayout()
        self.profile_manage_button = QPushButton("标准管理")
        set_secondary(self.profile_manage_button)
        self.profile_menu = QMenu(self.profile_manage_button)
        self.new_action = self.profile_menu.addAction("新建标准")
        self.scan_action = self.profile_menu.addAction("扫描标准样本 / 创建标准")
        self.profile_menu.addSeparator()
        self.review_discovery_action = self.profile_menu.addAction("查看待确认图元")
        self.reset_ignored_action = self.profile_menu.addAction("重新显示已忽略图元")
        self.profile_menu.addSeparator()
        self.restore_action = self.profile_menu.addAction("恢复此版本")
        self.delete_action = self.profile_menu.addAction("删除标准")
        self.new_action.triggered.connect(self._new_profile)
        self.scan_action.triggered.connect(self._scan_samples)
        self.review_discovery_action.triggered.connect(self._review_pending_discoveries)
        self.reset_ignored_action.triggered.connect(self._reset_ignored_discoveries)
        self.restore_action.triggered.connect(self._restore_selected_version)
        self.delete_action.triggered.connect(self._delete_profile)
        self.profile_manage_button.setMenu(self.profile_menu)
        manage_row.addWidget(self.profile_manage_button)
        self.edit_standard_button = QPushButton("编辑标准")
        set_secondary(self.edit_standard_button)
        self.edit_standard_button.setCheckable(True)
        self.edit_standard_button.toggled.connect(self._toggle_standard_editor)
        manage_row.addWidget(self.edit_standard_button)
        manage_hint = QLabel("日常只需选择 ACTIVE 标准并执行检查；新增/修改标准时再展开编辑。")
        manage_hint.setObjectName("mutedText")
        manage_row.addWidget(manage_hint)
        manage_row.addStretch(1)
        profile_layout.addLayout(manage_row)

        self.profile_table = QTableWidget(0, 9)
        self.profile_table.setHorizontalHeaderLabels(
            ["适用范围", "标准名称", "版本", "状态", "内置 RMU 标准", "自定义设备图元", "样本", "置信度", "标准状态"]
        )
        self.profile_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.profile_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profile_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.profile_table.horizontalHeader().setStretchLastSection(True)
        self.profile_table.setMinimumHeight(105)
        self.profile_table.setMaximumHeight(165)
        self.profile_table.itemSelectionChanged.connect(self._profile_selection_changed)
        configure_known_dense_table(self.profile_table)
        profile_layout.addWidget(self.profile_table)

        # Profile learning is a low-frequency maintenance action. Keep only its
        # status/progress here; the trigger itself lives in the Profile menu.
        self.scan_summary = QLabel("尚未扫描标准样本。")
        self.scan_summary.setObjectName("mutedText")
        self.scan_summary.setWordWrap(True)
        profile_layout.addWidget(self.scan_summary)
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setFormat("扫描进度 %p%")
        self.scan_progress.setToolTip("扫描标准样本并学习 SMART / NORMAL 图元、接地刀闸及图元几何的进度。")
        self.scan_progress.setVisible(False)
        profile_layout.addWidget(self.scan_progress)
        self.layout.addWidget(profile_box)

        editor_box = QGroupBox("标准定义")
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.setContentsMargins(14, 18, 14, 12)
        editor_layout.setSpacing(10)

        form = QFormLayout()
        self.site_name = QLineEdit()
        self.site_name.setPlaceholderText("例如：Jeddah / Madinah / General")
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("例如：RMU Standard V1")
        form.addRow("适用范围", self.site_name)
        form.addRow("标准名称", self.profile_name)
        editor_layout.addLayout(form)

        self.lbs_combo = WheelSafeComboBox()
        self.breaker_combo = WheelSafeComboBox()
        self.normal_lbs_combo = WheelSafeComboBox()
        self.normal_breaker_combo = WheelSafeComboBox()
        self.ground_combo = WheelSafeComboBox()
        self.normal_ground_combo = WheelSafeComboBox()

        standard_note = QLabel(
            "前 6 行是现有 RMU 系统标准；下面可以继续添加任意设备图元。扫描标准 G 后，表格会直接显示 XML 元素类型、主体 ID、"
            "w/h、AlignCenter、pin 坐标等属性，便于确认“业务元素 → 标准图元”的对应关系。"
        )
        standard_note.setWordWrap(True)
        standard_note.setObjectName("mutedText")
        editor_layout.addWidget(standard_note)

        custom_actions = QHBoxLayout()
        self.add_custom_button = QPushButton("添加设备图元")
        set_secondary(self.add_custom_button)
        self.add_custom_button.clicked.connect(self._add_custom_standard)
        custom_actions.addWidget(self.add_custom_button)
        self.add_scanned_button = QPushButton("添加扫描到的未映射图元")
        set_secondary(self.add_scanned_button)
        self.add_scanned_button.clicked.connect(self._add_unmapped_scanned_symbols)
        custom_actions.addWidget(self.add_scanned_button)
        self.delete_custom_button = QPushButton("删除选中自定义项")
        set_secondary(self.delete_custom_button)
        self.delete_custom_button.clicked.connect(self._delete_selected_custom_standard)
        custom_actions.addWidget(self.delete_custom_button)
        custom_actions.addStretch(1)
        editor_layout.addLayout(custom_actions)

        self.standard_table = QTableWidget(6, 12)
        self.standard_table.setHorizontalHeaderLabels(
            ["范围", "设备角色", "XML 元素", "标准图元 devref", "主体 ID", "w×h", "AlignCenter", "Pins", "匹配属性", "当前/旧图元匹配值", "置信度", "状态"]
        )
        self.standard_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.standard_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.standard_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.standard_table.verticalHeader().setVisible(False)
        self.standard_table.itemSelectionChanged.connect(self._update_action_state)
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
            combo.setMinimumContentsLength(36)
            combo.setMinimumHeight(36)
            combo.currentIndexChanged.connect(lambda _index, c=combo: self._refresh_standard_row(c))
            self._set_readonly_cell(row, 0, rmu_class, kind="system")
            self._set_readonly_cell(row, 1, role)
            self._set_readonly_cell(row, 2, element_tag)
            self.standard_table.setCellWidget(row, 3, combo)
            for column in (4, 5, 6, 7):
                self._set_readonly_cell(row, column, "-")
            self._set_readonly_cell(row, 8, match_attr)
            self._set_readonly_cell(row, 9, match_value)
            self._set_readonly_cell(row, 10, "-")
            self._set_readonly_cell(row, 11, "未学习")
        fit_known_dense_table(self.standard_table)
        editor_layout.addWidget(self.standard_table)

        save_row = QHBoxLayout()
        self.save_button = QPushButton("保存当前标准")
        self.save_button.clicked.connect(self._save_profile)
        save_row.addWidget(self.save_button)
        self.profile_status = QLabel("")
        self.profile_status.setObjectName("mutedText")
        self.profile_status.setWordWrap(True)
        save_row.addWidget(self.profile_status, 1)
        editor_layout.addLayout(save_row)
        self.layout.addWidget(editor_box)

        source_box = QGroupBox("待检查 G 文件")
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(14, 18, 14, 12)
        source_layout.setSpacing(10)
        source_note = QLabel(
            "选择需要检查的 G 文件或目录。本模块只读，不修改源 G；输出目录只保存检查报告和日志。"
            "标准样本的维护请使用上方“标准管理”。"
        )
        source_note.setWordWrap(True)
        source_note.setObjectName("mutedText")
        source_layout.addWidget(source_note)
        self.source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一张用于学习图元标准或执行只读标准检查的 G 文件。",
            directory_tooltip="选择包含标准样本或待检查 G 文件的目录。",
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

        discovery_row = QHBoxLayout()
        self.discovery_status = QLabel("")
        self.discovery_status.setObjectName("mutedText")
        self.discovery_status.setVisible(False)
        discovery_row.addWidget(self.discovery_status)
        self.review_discovery_button = QPushButton("查看待确认图元")
        set_secondary(self.review_discovery_button)
        self.review_discovery_button.setVisible(False)
        self.review_discovery_button.clicked.connect(self._review_pending_discoveries)
        discovery_row.addWidget(self.review_discovery_button)
        discovery_row.addStretch(1)
        apply_layout.addLayout(discovery_row)

        self.task = TaskPanel()
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

        # Workflow order: choose G files/output -> review ACTIVE standard -> inspect standards -> read-only check -> reports.
        # Standard learning/update remains a low-frequency maintenance action in the Standard Management menu.
        for widget in (source_box, profile_box, editor_box, apply_box):
            self.layout.removeWidget(widget)
        self.layout.insertWidget(1, source_box)
        self.layout.insertWidget(2, profile_box)
        self.layout.insertWidget(3, editor_box)
        self.layout.insertWidget(4, apply_box)
        self.editor_box = editor_box
        self.editor_box.setVisible(False)

        self._reload_profiles()
        self._update_action_state()


    def _toggle_standard_editor(self, checked: bool) -> None:
        if not hasattr(self, "editor_box"):
            return
        visible = bool(checked)
        self.editor_box.setVisible(visible)
        self.edit_standard_button.setText("收起标准编辑" if visible else "编辑标准")

    def _toggle_log(self, checked: bool) -> None:
        visible = bool(checked)
        self.task.log_view.setVisible(visible)
        self.task.clear_button.setVisible(visible)
        self.toggle_log_button.setText("隐藏日志" if visible else "显示日志")

    def _refresh_discovery_status(self, profile: SiteSmartProfile | None = None) -> None:
        if profile is None:
            name, _version, active = self._selected_profile_key()
            profile = self.service.load_profiles().get(name) if name and active else None
        pending = []
        ignored = []
        if profile is not None:
            pending = [devref for devref, state in profile.discovery_decisions.items() if state == "pending"]
            ignored = [devref for devref, state in profile.discovery_decisions.items() if state == "ignored"]
        has_pending = bool(pending)
        self.discovery_status.setVisible(has_pending)
        self.review_discovery_button.setVisible(has_pending)
        if has_pending:
            self.discovery_status.setText(f"待确认图元：{len(pending)} 种（已提示过，不会在每次检查时重复弹窗）")
            self.review_discovery_button.setText(f"查看待确认图元（{len(pending)}）")
        self.review_discovery_action.setEnabled(has_pending and not self._task_busy)
        self.reset_ignored_action.setEnabled(bool(ignored) and not self._task_busy)

    @staticmethod
    def _discovery_role(meta: dict[str, object]) -> str:
        body_id = str(meta.get("element_id", "")).strip()
        tag = str(meta.get("element_tag", "")).strip()
        return body_id or tag or "自定义设备"

    def _handle_discovered_symbols(self, candidates: list[dict[str, object]]) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name) if name else None
        if profile is None or not active or version != profile.profile_version:
            return
        original = dict(profile.discovery_decisions)
        decisions = dict(original)
        catalog = dict(profile.discovery_catalog)
        new_rows: list[dict[str, object]] = []
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            devref = str(raw.get("devref", "")).strip()
            if not devref:
                continue
            catalog[devref] = dict(raw)
            if devref not in decisions:
                decisions[devref] = "pending"
                new_rows.append(dict(raw))
        self.service.update_discovery_metadata(name, catalog=catalog, decisions=decisions)
        profile = self.service.load_profiles().get(name)
        self._refresh_discovery_status(profile)
        if not new_rows:
            return
        answer = QMessageBox.question(
            self,
            "发现新的图元类型",
            f"本次检查发现 {len(new_rows)} 种尚未纳入当前图元标准的图元。\n\n"
            "它们不会自动判定为错误，也不会自动加入标准。是否现在逐个确认？\n"
            "如果选择“否”，这些图元会保留在“待确认图元”中，并且后续检查不会重复弹窗提醒。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._review_pending_discoveries(only_devrefs={str(row.get("devref", "")).strip() for row in new_rows})

    def _review_pending_discoveries(self, *_args, only_devrefs: set[str] | None = None) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name) if name else None
        if profile is None or not active or version != profile.profile_version:
            QMessageBox.information(self, "请选择当前标准", "请先选择一个 ACTIVE 图元标准。")
            return
        decisions = dict(profile.discovery_decisions)
        rows: list[dict[str, object]] = []
        for devref, state in decisions.items():
            if state != "pending":
                continue
            if only_devrefs is not None and devref not in only_devrefs:
                continue
            meta = dict(profile.discovery_catalog.get(devref, {}))
            meta.setdefault("devref", devref)
            rows.append(meta)
        rows.sort(key=lambda row: (-int(row.get("count", 0) or 0), str(row.get("devref", "")).casefold()))
        if not rows:
            QMessageBox.information(self, "没有待确认图元", "当前标准没有需要确认的新图元。")
            self._refresh_discovery_status(profile)
            return

        additions: list[dict[str, object]] = []
        ignored = 0
        existing_standard = {str(row.get("standard_devref", "")).strip() for row in profile.custom_symbols}
        for index, meta in enumerate(rows, 1):
            devref = str(meta.get("devref", "")).strip()
            tag = str(meta.get("element_tag", "")).strip() or "-"
            body_id = str(meta.get("element_id", "")).strip() or "-"
            count = int(meta.get("count", 0) or 0)
            source_file = str(meta.get("source_file", "")).strip() or "-"
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(f"确认新图元 {index}/{len(rows)}")
            box.setText(f"XML 元素：{tag}\n图元：{devref}")
            box.setInformativeText(
                f"主体 ID：{body_id}\n出现次数：{count}\n示例文件：{source_file}\n\n"
                "“加入当前标准”：作为一个新的自定义设备图元加入；\n"
                "“不纳入此标准”：以后不再提示这个 devref；\n"
                "“剩余稍后处理”：保留待确认状态并结束本次确认。"
            )
            add_button = box.addButton("加入当前标准", QMessageBox.ButtonRole.AcceptRole)
            ignore_button = box.addButton("不纳入此标准", QMessageBox.ButtonRole.DestructiveRole)
            later_button = box.addButton("剩余稍后处理", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is add_button:
                if devref not in existing_standard:
                    additions.append({
                        "uid": f"custom-{uuid4().hex[:10]}",
                        "scope": "ANY",
                        "role": self._discovery_role(meta),
                        "element_tag": "" if tag == "-" else tag,
                        "standard_devref": devref,
                        "match_attr": "devref",
                        "match_value": devref,
                        "enabled": True,
                        "source_file": "" if source_file == "-" else source_file,
                    })
                    existing_standard.add(devref)
                decisions.pop(devref, None)
            elif clicked is ignore_button:
                decisions[devref] = "ignored"
                ignored += 1
            else:
                break

        if additions:
            profile.custom_symbols = list(profile.custom_symbols) + additions
            merged_catalog = dict(profile.symbol_catalog)
            for row in rows:
                devref = str(row.get("devref", "")).strip()
                if devref in {str(item.get("standard_devref", "")).strip() for item in additions}:
                    merged_catalog[devref] = dict(row)
            profile.symbol_catalog = merged_catalog
            try:
                profile = self.service.upsert(profile)
            except ValueError as exc:
                QMessageBox.warning(self, "加入标准失败", str(exc))
                return
        self.service.update_discovery_metadata(name, catalog=profile.discovery_catalog, decisions=decisions)
        current = self.service.load_profiles().get(name)
        if current is not None:
            self._reload_profiles(current.profile_name, current.profile_version)
            self._refresh_discovery_status(current)
            if additions:
                self.activeProfileChanged.emit(current.profile_name)
        if additions or ignored:
            QMessageBox.information(
                self,
                "新图元已处理",
                f"加入当前标准：{len(additions)} 种；不纳入本标准：{ignored} 种。\n"
                "未处理的图元会保留在待确认列表中，不会在每次检查时重复弹窗。",
            )

    def _reset_ignored_discoveries(self, *_args) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name) if name else None
        if profile is None or not active or version != profile.profile_version:
            return
        decisions = dict(profile.discovery_decisions)
        ignored = [devref for devref, state in decisions.items() if state == "ignored"]
        if not ignored:
            QMessageBox.information(self, "没有已忽略图元", "当前标准没有已忽略的新图元。")
            return
        for devref in ignored:
            decisions[devref] = "pending"
        profile = self.service.update_discovery_metadata(name, decisions=decisions)
        self._refresh_discovery_status(profile)
        QMessageBox.information(self, "已恢复提示", f"已将 {len(ignored)} 种图元重新放回待确认列表。")

    def _selected_profile_key(self) -> tuple[str, int | None, bool]:
        row = self.profile_table.currentRow()
        if row < 0:
            return "", None, False
        name_item = self.profile_table.item(row, 1)
        version_item = self.profile_table.item(row, 2)
        state_item = self.profile_table.item(row, 3)
        name = str(name_item.data(Qt.ItemDataRole.UserRole) or "") if name_item else ""
        version = version_item.data(Qt.ItemDataRole.UserRole) if version_item else None
        try:
            version = int(version) if version is not None else None
        except (TypeError, ValueError):
            version = None
        active = bool(state_item and str(state_item.text()).upper() == "ACTIVE")
        return name, version, active

    def _selected_profile_name(self) -> str:
        return self._selected_profile_key()[0]

    def _reload_profiles(self, select_name: str = "", select_version: int | None = None) -> None:
        profiles = self.service.load_profiles()
        self.profile_table.blockSignals(True)
        self.profile_table.setRowCount(0)
        selected_row = -1
        for profile_name, current in sorted(profiles.items(), key=lambda row: row[0].casefold()):
            versions = self.service.load_profile_versions(profile_name) or [current]
            for profile in reversed(versions):
                row = self.profile_table.rowCount()
                self.profile_table.insertRow(row)
                is_active = profile.profile_version == current.profile_version
                confidences = [float(profile.lbs_confidence), float(profile.breaker_confidence)]
                if profile.smart_ground_devref:
                    confidences.append(float(profile.ground_confidence))
                if profile.normal_ready:
                    confidences.extend([float(profile.normal_lbs_confidence), float(profile.normal_breaker_confidence)])
                if profile.normal_ground_devref:
                    confidences.append(float(profile.normal_ground_confidence))
                confidence = min(confidences) if confidences else 0.0
                if profile.full_ready:
                    readiness = "Ready"
                elif profile.smart_ready and profile.normal_ready and not profile.ground_ready:
                    readiness = "Needs Ground"
                elif profile.smart_ready:
                    readiness = "SMART Only"
                else:
                    readiness = "Incomplete"
                builtins = [
                    profile.smart_lbs_devref,
                    profile.smart_breaker_devref,
                    profile.smart_ground_devref,
                    profile.normal_lbs_devref,
                    profile.normal_breaker_devref,
                    profile.normal_ground_devref,
                ]
                enabled_custom = [entry for entry in profile.custom_symbols if bool(entry.get("enabled", True))]
                values = [
                    profile.site_name,
                    profile_name,
                    f"V{profile.profile_version}",
                    "ACTIVE" if is_active else "ARCHIVED",
                    f"{sum(1 for value in builtins if value)}/6",
                    str(len(enabled_custom)),
                    str(len(profile.sample_files)),
                    f"{confidence:.0%}",
                    readiness,
                ]
                for column, text_value in enumerate(values):
                    item = QTableWidgetItem(text_value)
                    if column == 1:
                        item.setData(Qt.ItemDataRole.UserRole, profile_name)
                    if column == 2:
                        item.setData(Qt.ItemDataRole.UserRole, profile.profile_version)
                    if column == 4:
                        item.setToolTip(
                            "\n".join([
                                f"SMART LBS: {profile.smart_lbs_devref or '-'}",
                                f"SMART CB: {profile.smart_breaker_devref or '-'}",
                                f"SMART Ground: {profile.smart_ground_devref or '-'}",
                                f"NORMAL LBS: {profile.normal_lbs_devref or '-'}",
                                f"NORMAL CB: {profile.normal_breaker_devref or '-'}",
                                f"NORMAL Ground: {profile.normal_ground_devref or '-'}",
                            ])
                        )
                    if column == 5 and enabled_custom:
                        item.setToolTip("\n".join(
                            f"{entry.get('scope', 'ANY')} / {entry.get('role', '自定义')}: {entry.get('standard_devref', '-')}"
                            for entry in enabled_custom
                        ))
                    self.profile_table.setItem(row, column, item)
                target_version = select_version if select_version is not None else current.profile_version
                if profile_name == select_name and profile.profile_version == target_version:
                    selected_row = row
        fit_known_dense_table(self.profile_table)
        self.profile_table.blockSignals(False)

        if selected_row >= 0:
            self.profile_table.selectRow(selected_row)
            self._profile_selection_changed()
        elif self.profile_table.rowCount() > 0:
            # First row is the newest ACTIVE version of the alphabetically first profile.
            self.profile_table.selectRow(0)
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

    def _populate_custom_devref_combo(self, combo: WheelSafeComboBox, selected: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.setEditable(True)
        for devref, meta in sorted(
            self._symbol_catalog.items(),
            key=lambda item: (
                str(item[1].get("element_tag", "")).casefold(),
                str(item[1].get("element_id", "")).casefold(),
                item[0].casefold(),
            ),
        ):
            tag = str(meta.get("element_tag", "")).strip()
            body_id = str(meta.get("element_id", "")).strip()
            label = f"{devref}"
            if tag or body_id:
                label += f"   [{tag or '-'} / {body_id or '-'}]"
            combo.addItem(label, devref)
        if selected and combo.findData(selected) < 0:
            combo.addItem(selected, selected)
        index = combo.findData(selected)
        if index >= 0:
            combo.setCurrentIndex(index)
        elif selected:
            combo.setEditText(selected)
        combo.blockSignals(False)

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

        devref_combo = WheelSafeComboBox()
        devref_combo.setMinimumContentsLength(34)
        devref_combo.setMinimumHeight(34)
        selected_devref = str(entry.get("standard_devref", "")).strip()
        self._populate_custom_devref_combo(devref_combo, selected_devref)
        self.standard_table.setCellWidget(row, 3, devref_combo)

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

        def refresh_custom(*_args, target_row=row, combo=devref_combo) -> None:
            self._refresh_custom_standard_row(target_row, combo)

        devref_combo.currentIndexChanged.connect(refresh_custom)
        devref_combo.currentTextChanged.connect(refresh_custom)
        self._refresh_custom_standard_row(row, devref_combo)
        fit_known_dense_table(self.standard_table)
        return row

    def _refresh_custom_standard_row(self, row: int, combo: WheelSafeComboBox | None = None) -> None:
        if row < len(self._standard_specs) or row >= self.standard_table.rowCount():
            return
        combo = combo or self.standard_table.cellWidget(row, 3)
        if not isinstance(combo, WheelSafeComboBox):
            return
        devref = str(combo.currentData() or combo.currentText() or "").strip()
        meta = self._symbol_meta(devref)
        tag_item = self.standard_table.item(row, 2)
        if tag_item is not None and not tag_item.text().strip() and meta.get("element_tag"):
            tag_item.setText(str(meta.get("element_tag", "")))
        self._refresh_symbol_properties(row, devref)
        count = int(meta.get("count", 0) or 0)
        confidence_item = self.standard_table.item(row, 10) or self._set_readonly_cell(row, 10, "-")
        confidence_item.setText(f"样本 {count}" if count else ("已定义" if devref else "-"))
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
        if not self._symbol_catalog:
            QMessageBox.information(self, "没有扫描结果", "请先扫描标准 G 文件。程序会把 G 中识别到的 devref 与元素属性列出来。")
            return
        mapped = {
            str(combo.currentData() or "").strip()
            for _scope, _role, _tag, combo, _match_attr, _match_value in self._standard_specs
            if str(combo.currentData() or "").strip()
        }
        for row in self._custom_standard_rows():
            combo = self.standard_table.cellWidget(row, 3)
            if isinstance(combo, WheelSafeComboBox):
                value = str(combo.currentData() or combo.currentText() or "").strip()
                if value:
                    mapped.add(value)
        candidates = [(devref, meta) for devref, meta in self._symbol_catalog.items() if devref not in mapped]
        if not candidates:
            QMessageBox.information(self, "没有未映射图元", "扫描到的图元都已经存在于当前标准表中。")
            return
        if len(candidates) > 30:
            if QMessageBox.question(
                self,
                "批量添加未映射图元",
                f"当前扫描到 {len(candidates)} 个尚未映射的 devref。全部加入会产生较多自定义规则。\n\n确认全部加入吗？",
            ) != QMessageBox.StandardButton.Yes:
                return
        first_row = -1
        for devref, meta in sorted(candidates, key=lambda item: (str(item[1].get("element_tag", "")), item[0])):
            role = str(meta.get("element_id", "")).strip() or self._devref_short(devref) or "自定义设备"
            row = self._insert_custom_standard_row({
                "scope": "ANY",
                "role": role,
                "element_tag": str(meta.get("element_tag", "")).strip(),
                "standard_devref": devref,
                "match_attr": "devref",
                "match_value": devref,
                "source_file": str(meta.get("source_file", "")).strip(),
            })
            if first_row < 0:
                first_row = row
        if first_row >= 0:
            self.standard_table.selectRow(first_row)
            self.standard_table.scrollToItem(self.standard_table.item(first_row, 1))
        self.profile_status.setText(
            f"已加入 {len(candidates)} 个扫描到的未映射图元。若要把旧图元升级到该标准，请把“当前/旧图元匹配值”改成旧 devref，或改用 p_NameString / key_name / XML元素 作为匹配条件。"
        )
        self._update_action_state()

    def _collect_custom_symbols(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in self._custom_standard_rows():
            marker_item = self.standard_table.item(row, 0)
            scope_combo = self.standard_table.cellWidget(row, 0)
            devref_combo = self.standard_table.cellWidget(row, 3)
            match_combo = self.standard_table.cellWidget(row, 8)
            if not isinstance(scope_combo, WheelSafeComboBox) or not isinstance(devref_combo, WheelSafeComboBox) or not isinstance(match_combo, WheelSafeComboBox):
                continue
            devref = str(devref_combo.currentData() or devref_combo.currentText() or "").strip()
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
            for column in (0, 3, 8):
                widget = self.standard_table.cellWidget(row, column)
                if widget is not None:
                    widget.setEnabled(enabled)
        self.standard_table.setEditTriggers(
            (QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            if enabled else QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.add_custom_button.setEnabled(enabled)
        self.add_scanned_button.setEnabled(enabled)
        self.delete_custom_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)

    def _new_profile(self, *_args, clear_selection: bool = True) -> None:
        if hasattr(self, "edit_standard_button"):
            self.edit_standard_button.setChecked(True)
        if clear_selection:
            self.profile_table.clearSelection()
            self.profile_table.setCurrentCell(-1, -1)
        self._selected_version = None
        self._selected_is_active = False
        self._candidate_counts.clear()
        self._symbol_catalog.clear()
        self._clear_custom_standard_rows()
        self.site_name.clear()
        self.profile_name.clear()
        self.lbs_combo.clear()
        self.breaker_combo.clear()
        self.normal_lbs_combo.clear()
        self.normal_breaker_combo.clear()
        self.ground_combo.clear()
        self.normal_ground_combo.clear()
        self.scan_summary.setText("尚未扫描。")
        self.profile_status.setText("新建标准：填写适用范围 / 标准名称后扫描标准样本。")
        self.current_profile_label.setText("当前执行标准：未选择")
        self.active_profile_summary.setText("当前执行标准：尚未创建 Profile")
        self._last_scan = None
        self._set_editor_enabled(True)
        self.restore_action.setEnabled(False)
        self.delete_action.setEnabled(False)
        self._update_action_state()

    def _profile_selection_changed(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            return
        profile = self.service.get_profile_version(name, version)
        current = self.service.load_profiles().get(name)
        if profile is None or current is None:
            return
        self._selected_version = version
        self._selected_is_active = active
        self._symbol_catalog = {str(key): dict(value) for key, value in profile.symbol_catalog.items()}
        self._load_custom_symbols(profile.custom_symbols)
        self.site_name.setText(profile.site_name)
        self.profile_name.setText(profile.profile_name)
        self._fill_candidate_combo(self.lbs_combo, profile.lbs_candidates, profile.smart_lbs_devref)
        self._fill_candidate_combo(self.breaker_combo, profile.breaker_candidates, profile.smart_breaker_devref)
        self._fill_candidate_combo(self.ground_combo, profile.ground_candidates, profile.smart_ground_devref)
        self._fill_candidate_combo(self.normal_lbs_combo, profile.normal_lbs_candidates, profile.normal_lbs_devref)
        self._fill_candidate_combo(self.normal_breaker_combo, profile.normal_breaker_candidates, profile.normal_breaker_devref)
        self._fill_candidate_combo(self.normal_ground_combo, profile.normal_ground_candidates, profile.normal_ground_devref)
        self.scan_summary.setText(
            f"样本 {len(profile.sample_files)} 个，SMART RMU {profile.smart_rmu_count}，NORMAL RMU {profile.normal_rmu_count}；"
            f"SMART Y/Q/接地 {profile.lbs_confidence:.0%}/{profile.breaker_confidence:.0%}/{profile.ground_confidence:.0%}，"
            f"NORMAL Y/Q/接地 {profile.normal_lbs_confidence:.0%}/{profile.normal_breaker_confidence:.0%}/{profile.normal_ground_confidence:.0%}；"
            f"自定义设备图元 {len(profile.custom_symbols)} 项。"
        )
        if active:
            self.profile_status.setText(f"ACTIVE · Profile V{profile.profile_version} · 最后保存：{profile.updated_at or '-'}")
            self.current_profile_label.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
            self.active_profile_summary.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
        else:
            self.profile_status.setText(
                f"ARCHIVED · V{profile.profile_version} · 仅供查看。当前 ACTIVE 是 V{current.profile_version}；如需回滚请点击“恢复此版本”。"
            )
            self.current_profile_label.setText(
                f"当前执行标准仍为：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE"
            )
            self.active_profile_summary.setText(
                f"当前执行标准：{current.site_name} / {current.profile_name} / V{current.profile_version} · ACTIVE（当前查看 V{profile.profile_version} 历史版本）"
            )
        self._last_scan = None
        self._set_editor_enabled(active)
        self.restore_action.setEnabled(not active)
        self.delete_action.setEnabled(active)
        self._update_action_state()
        self._refresh_discovery_status(current if active else None)

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
        counts = self._candidate_counts.get(id(combo), {})
        total = sum(max(0, int(value)) for value in counts.values())
        count = max(0, int(counts.get(selected, 0))) if selected else 0
        confidence = (count / total) if total else 0.0
        self._refresh_symbol_properties(row, selected)
        confidence_item = self.standard_table.item(row, 10) or self._set_readonly_cell(row, 10, "-")
        status_item = self.standard_table.item(row, 11) or self._set_readonly_cell(row, 11, "未学习")
        confidence_item.setText(f"{confidence:.0%}" if selected and total else ("已定义" if selected else "-"))
        if not selected:
            status = "未学习"
        elif not total:
            status = "已保存"
        elif confidence >= 0.90:
            status = "就绪"
        else:
            status = "需确认"
        status_item.setText(status)
        fit_known_dense_table(self.standard_table)

    def _confirm_rescan_target(self) -> bool:
        name, version, active = self._selected_profile_key()
        current = self.service.load_profiles().get(name) if name else None
        if current is None or not current.smart_ready:
            return True
        if not active:
            QMessageBox.information(
                self,
                "历史版本只读",
                "当前选中的是 ARCHIVED 历史版本。请先选择 ACTIVE 版本，或者点击“恢复此版本”后再重新扫描。",
            )
            return False

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Profile 已有图元标准")
        box.setText(
            f"{current.profile_name} V{current.profile_version} 已经保存了图元 devref / 几何标准。\n\n"
            "如果图元名称、大小、旋转或连接锚点发生变化，应使用新的标准 G 样本重新扫描。"
        )
        box.setInformativeText(
            "选择“更新当前 Profile”继续扫描；保存时如果标准发生变化，会自动生成新的 ACTIVE 版本并保留旧版本。"
            "如果这批样本属于另一套标准，请新建标准，避免覆盖当前 ACTIVE 标准。"
        )
        update_button = box.addButton("更新当前 Profile", QMessageBox.ButtonRole.AcceptRole)
        new_button = box.addButton("新建标准", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is update_button:
            return True
        if clicked is new_button:
            self._new_profile()
            QMessageBox.information(self, "新建标准", "请填写新的适用范围 / 标准名称，然后重新点击扫描。")
        return False

    def _scan_samples(self) -> None:
        if hasattr(self, "edit_standard_button"):
            self.edit_standard_button.setChecked(True)
        if self._scan_worker is not None:
            return
        if not self.site_name.text().strip():
            QMessageBox.warning(self, "Site Name", "请先输入 Site Name，再扫描属于该现场的标准样本。")
            return
        if not self.profile_name.text().strip():
            QMessageBox.warning(self, "Profile Name", "请先输入 Profile Name。")
            return
        typed_name = self.profile_name.text().strip()
        selected_name, _version, _active = self._selected_profile_key()
        existing = self.service.load_profiles().get(typed_name)
        if existing is not None and selected_name != typed_name:
            QMessageBox.warning(
                self,
                "标准名称已存在",
                f"图元标准“{typed_name}”已存在。请在上方列表选择并维护该标准，或者使用新的标准名称。",
            )
            return
        if not self._confirm_rescan_target():
            return

        # Remote selection may need to be downloaded to the read-only local snapshot.
        # Show indeterminate progress immediately so the UI never looks frozen.
        self.scan_progress.setVisible(True)
        self.scan_progress.setRange(0, 0)
        self.scan_summary.setText("正在准备标准样本……")
        self.scan_action.setEnabled(False)
        self.save_button.setEnabled(False)
        try:
            if not validate_input_source(self, self.source, display_name="图元标准样本"):
                self.scan_progress.setRange(0, 100)
                self.scan_progress.setValue(0)
                self.scan_progress.setVisible(False)
                self._update_action_state()
                return
            self.source.persist_current()
            files = discover_g_inputs(self.source.path(), self.source.mode())
        except Exception as exc:
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(0)
            self.scan_progress.setVisible(False)
            self._update_action_state()
            QMessageBox.critical(self, "扫描失败", str(exc))
            return

        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_summary.setText(f"正在扫描 {len(files)} 个标准 G 文件……")

        def do_scan(*, log, progress):
            return scan_smart_profile_samples(files, progress=progress)

        worker = FunctionWorker(do_scan)
        self._scan_worker = worker
        worker.signals.progress.connect(self.scan_progress.setValue)
        worker.signals.result.connect(lambda scan, selected_files=files: self._on_scan_result(scan, selected_files))
        worker.signals.error.connect(self._on_scan_error)
        worker.signals.finished.connect(self._on_scan_finished)
        self._scan_pool.start(worker)

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
        current_fixed = {
            "lbs": str(self.lbs_combo.currentData() or "").strip(),
            "breaker": str(self.breaker_combo.currentData() or "").strip(),
            "ground": str(self.ground_combo.currentData() or "").strip(),
            "normal_lbs": str(self.normal_lbs_combo.currentData() or "").strip(),
            "normal_breaker": str(self.normal_breaker_combo.currentData() or "").strip(),
            "normal_ground": str(self.normal_ground_combo.currentData() or "").strip(),
        }
        self._fill_candidate_combo(self.lbs_combo, scan.lbs_counts, scan.suggested_lbs_devref or current_fixed["lbs"])
        self._fill_candidate_combo(self.breaker_combo, scan.breaker_counts, scan.suggested_breaker_devref or current_fixed["breaker"])
        self._fill_candidate_combo(self.ground_combo, scan.ground_counts, scan.suggested_ground_devref or current_fixed["ground"])
        self._fill_candidate_combo(self.normal_lbs_combo, scan.normal_lbs_counts, scan.suggested_normal_lbs_devref or current_fixed["normal_lbs"])
        self._fill_candidate_combo(self.normal_breaker_combo, scan.normal_breaker_counts, scan.suggested_normal_breaker_devref or current_fixed["normal_breaker"])
        self._fill_candidate_combo(self.normal_ground_combo, scan.normal_ground_counts, scan.suggested_normal_ground_devref or current_fixed["normal_ground"])
        for row in self._custom_standard_rows():
            combo = self.standard_table.cellWidget(row, 3)
            if isinstance(combo, WheelSafeComboBox):
                selected = str(combo.currentData() or combo.currentText() or "").strip()
                self._populate_custom_devref_combo(combo, selected)
                self._refresh_custom_standard_row(row, combo)
        lbs_conf = scan.lbs_candidates[0].confidence if scan.lbs_candidates else 0.0
        brk_conf = scan.breaker_candidates[0].confidence if scan.breaker_candidates else 0.0
        ground_conf = scan.ground_candidates[0].confidence if scan.ground_candidates else 0.0
        normal_lbs_conf = scan.normal_lbs_candidates[0].confidence if scan.normal_lbs_candidates else 0.0
        normal_brk_conf = scan.normal_breaker_candidates[0].confidence if scan.normal_breaker_candidates else 0.0
        normal_ground_conf = scan.normal_ground_candidates[0].confidence if scan.normal_ground_candidates else 0.0
        self.scan_summary.setText(
            f"扫描 {scan.parsed_file_count}/{len(files)} 个文件：SMART RMU {scan.smart_rmu_count}，NORMAL RMU {scan.normal_rmu_count}，特殊/SMR {scan.ignored_rmu_count}；"
            f"SMART Y/Q/接地 {lbs_conf:.0%}/{brk_conf:.0%}/{ground_conf:.0%}，NORMAL Y/Q/接地 {normal_lbs_conf:.0%}/{normal_brk_conf:.0%}/{normal_ground_conf:.0%}；"
            f"共识别 {len(scan.symbol_catalog)} 种带 devref 的图元，可在下方继续添加为自定义设备标准。"
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
            self.profile_status.setText("扫描完成。请确认内置 RMU 标准；还可以点击“添加设备图元”或“添加扫描到的未映射图元”，继续维护其他设备图元标准。")

    def _save_profile(self) -> None:
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
        if not site_name or not profile_name or not lbs or not breaker:
            QMessageBox.warning(self, "标准未完成", "适用范围、标准名称、SMART LBS 和 SMART Circuit Breaker 都必须确认。NORMAL 与接地刀闸图元可稍后用包含对应柜型的标准样本补充学习。")
            return

        scan = self._last_scan
        if scan is not None:
            lbs_rows = {row.devref: row for row in scan.lbs_candidates}
            breaker_rows = {row.devref: row for row in scan.breaker_candidates}
            sample_files = [path.name for path in scan.files]
            smart_rmu_count = scan.smart_rmu_count
            normal_rmu_count = scan.normal_rmu_count
            ignored_rmu_count = scan.ignored_rmu_count
            ground_rows = {row.devref: row for row in scan.ground_candidates}
            normal_lbs_rows = {row.devref: row for row in scan.normal_lbs_candidates}
            normal_breaker_rows = {row.devref: row for row in scan.normal_breaker_candidates}
            normal_ground_rows = {row.devref: row for row in scan.normal_ground_candidates}
            lbs_observations = sum(scan.lbs_counts.values())
            breaker_observations = sum(scan.breaker_counts.values())
            normal_lbs_observations = sum(scan.normal_lbs_counts.values())
            normal_breaker_observations = sum(scan.normal_breaker_counts.values())
            ground_observations = sum(scan.ground_counts.values())
            normal_ground_observations = sum(scan.normal_ground_counts.values())
            lbs_confidence = lbs_rows.get(lbs).confidence if lbs in lbs_rows else 0.0
            breaker_confidence = breaker_rows.get(breaker).confidence if breaker in breaker_rows else 0.0
            normal_lbs_confidence = normal_lbs_rows.get(normal_lbs).confidence if normal_lbs in normal_lbs_rows else 0.0
            normal_breaker_confidence = normal_breaker_rows.get(normal_breaker).confidence if normal_breaker in normal_breaker_rows else 0.0
            ground_confidence = ground_rows.get(ground).confidence if ground in ground_rows else 0.0
            normal_ground_confidence = normal_ground_rows.get(normal_ground).confidence if normal_ground in normal_ground_rows else 0.0
            lbs_candidates = dict(scan.lbs_counts)
            breaker_candidates = dict(scan.breaker_counts)
            normal_lbs_candidates = dict(scan.normal_lbs_counts)
            normal_breaker_candidates = dict(scan.normal_breaker_counts)
            ground_candidates = dict(scan.ground_counts)
            normal_ground_candidates = dict(scan.normal_ground_counts)
            selected_devrefs = {value for value in (lbs, breaker, ground, normal_lbs, normal_breaker, normal_ground) if value}
            selected_devrefs.update(
                str(entry.get("standard_devref", "")).strip()
                for entry in custom_symbols
                if str(entry.get("standard_devref", "")).strip()
            )
            geometry_templates = {key: list(value) for key, value in scan.geometry_templates.items() if key in selected_devrefs}
        else:
            old_name = self._selected_profile_name() or profile_name
            old = self.service.load_profiles().get(old_name)
            sample_files = list(old.sample_files) if old else []
            smart_rmu_count = old.smart_rmu_count if old else 0
            normal_rmu_count = old.normal_rmu_count if old else 0
            ignored_rmu_count = old.ignored_rmu_count if old else 0
            lbs_observations = old.lbs_observations if old else 0
            breaker_observations = old.breaker_observations if old else 0
            normal_lbs_observations = old.normal_lbs_observations if old else 0
            normal_breaker_observations = old.normal_breaker_observations if old else 0
            ground_observations = old.ground_observations if old else 0
            normal_ground_observations = old.normal_ground_observations if old else 0
            lbs_confidence = old.lbs_confidence if old else 0.0
            breaker_confidence = old.breaker_confidence if old else 0.0
            normal_lbs_confidence = old.normal_lbs_confidence if old else 0.0
            normal_breaker_confidence = old.normal_breaker_confidence if old else 0.0
            ground_confidence = old.ground_confidence if old else 0.0
            normal_ground_confidence = old.normal_ground_confidence if old else 0.0
            lbs_candidates = dict(old.lbs_candidates) if old else {lbs: 1}
            breaker_candidates = dict(old.breaker_candidates) if old else {breaker: 1}
            normal_lbs_candidates = dict(old.normal_lbs_candidates) if old else ({normal_lbs: 1} if normal_lbs else {})
            normal_breaker_candidates = dict(old.normal_breaker_candidates) if old else ({normal_breaker: 1} if normal_breaker else {})
            ground_candidates = dict(old.ground_candidates) if old else ({ground: 1} if ground else {})
            normal_ground_candidates = dict(old.normal_ground_candidates) if old else ({normal_ground: 1} if normal_ground else {})
            geometry_templates = dict(old.geometry_templates) if old else {}

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
        ).normalized()
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
        self.service.remove(name)
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
            QMessageBox.warning(self, "请选择标准", "请先在上方列表选择并保存一个图元标准。")
            return
        if not active or version != profile.profile_version:
            QMessageBox.information(
                self,
                "请选择 ACTIVE 版本",
                f"当前选中的是历史版本。实际 ACTIVE 是 {name} V{profile.profile_version}。请选中 ACTIVE 行后执行，或先恢复历史版本。",
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
        )
        processor = process_smart_profile_correction if correct else process_smart_profile_consistency
        self.task.start(lambda log, progress: processor(settings, log, progress), run_dir)

    def _update_action_state(self) -> None:
        name, version, active = self._selected_profile_key()
        profile = self.service.load_profiles().get(name) if name else None
        busy_scan = self._scan_worker is not None
        busy = busy_scan or self._task_busy
        ready = bool(profile and profile.smart_ready and active and version == profile.profile_version)
        self.check_button.setEnabled(ready and not busy)
        self.correct_button.setEnabled(ready and not busy)
        # New profiles and ACTIVE profiles may be scanned. Archived rows are immutable.
        allow_scan = (not name) or bool(active and profile is not None)
        self.scan_action.setEnabled(allow_scan and not busy)
        self.scan_action.setText("扫描标准样本 / 更新标准" if profile and active else "扫描标准样本 / 创建标准")
        can_edit = (not name) or bool(active and profile is not None)
        self.save_button.setEnabled(can_edit and not busy)
        self.add_custom_button.setEnabled(can_edit and not busy)
        self.add_scanned_button.setEnabled(can_edit and not busy)
        selected_standard_row = self.standard_table.currentRow()
        self.delete_custom_button.setEnabled(
            can_edit and not busy and selected_standard_row >= len(self._standard_specs)
        )
        self.restore_action.setEnabled(bool(name and profile and not active and not busy))
        self.delete_action.setEnabled(bool(name and profile and active and not busy))
        if hasattr(self, "review_discovery_action"):
            pending = bool(profile and any(state == "pending" for state in profile.discovery_decisions.values()))
            ignored = bool(profile and any(state == "ignored" for state in profile.discovery_decisions.values()))
            self.review_discovery_action.setEnabled(bool(active and pending and not busy))
            self.reset_ignored_action.setEnabled(bool(active and ignored and not busy))
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
        discovered = stats.get("_UnmappedSymbolCandidates", [])
        discovery_rows = [dict(row) for row in discovered if isinstance(row, dict)] if isinstance(discovered, list) else []
        mode = str(stats.get("Mode", getattr(self, "_last_run_mode", "CHECK")) or "CHECK").upper()
        bad = int(stats.get("Nonstandard Symbols", 0) or 0)
        if stats:
            new_unmapped = int(stats.get("New Unmapped Symbols", 0) or 0)
            pending_unmapped = int(stats.get("Pending Unmapped Symbols", 0) or 0)
            unmanaged = new_unmapped + pending_unmapped
            if mode == "CORRECT":
                corrected = int(stats.get("Corrected Elements", 0) or 0)
                changed_files = int(stats.get("Corrected Files", 0) or 0)
                geometry = int(stats.get("Geometry Corrections", 0) or 0)
                text = (
                    f"纠正完成：{changed_files} 个文件发生修改，共处理 {corrected} 个标准差异，"
                    f"其中连接锚点/几何纠正 {geometry} 个；自动复查后剩余 {bad} 个不符合项。"
                )
                if unmanaged:
                    text += f" 另有 {unmanaged} 种未纳入当前标准的图元未自动处理。"
                text += " 源 G 未覆盖；纠正副本位于本次结果目录的 corrected 文件夹。"
            else:
                if bad:
                    text = f"检查完成：发现 {bad} 个不符合当前标准的问题。"
                else:
                    text = "检查完成：已配置的图元标准全部通过。"
                if unmanaged:
                    text += f" 另发现 {unmanaged} 种尚未纳入当前标准的图元（不计为错误），可在“待确认图元”中决定是否加入。"
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
        if discovery_rows:
            self._handle_discovered_symbols(discovery_rows)

    def _open_report(self) -> None:
        path = self._last_report_path
        if path is None or not path.exists():
            QMessageBox.information(self, "报告不存在", "当前还没有检查报告，请先点击“检查图元标准”。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def save_state(self) -> None:
        self.source.persist_all_text()
        self.output_path.persist_current_text()
