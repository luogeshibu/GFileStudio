from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    QWidget,
)

from g_file_studio.models import InputMode
from g_file_studio.processors.smart_profile_processor import (
    SmartProfileProcessingSettings,
    process_smart_profile_consistency,
    process_smart_profile_correction,
)
from g_file_studio.services.paths import default_workspace
from g_file_studio.services.remote_g_source import download_stable_files
from g_file_studio.services.remote_symbol_library import (
    DEFAULT_REMOTE_SYMBOL_ROOT,
    RemoteSymbolLibraryService,
)
from g_file_studio.services.run_history import begin_managed_run, configure_managed_output
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile
from g_file_studio.services.symbol_inventory_service import (
    DEVICE_LEVEL_VALUES,
    SYMBOL_USAGE_VALUES,
    default_device_level,
    infer_device_type,
    infer_symbol_usage,
)
from g_file_studio.services.symbol_discovery_service import discover_graphic_symbols
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.help_content import APP_HELP
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.path_validation import validate_input_source
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
    connectionSettingsRequested = Signal()

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.service = SiteProfileService()
        self._last_scan = None
        self._last_report_path: Path | None = None
        self._scan_worker: FunctionWorker | None = None
        self._server_sync_worker: FunctionWorker | None = None
        self._last_server_sync_payload: dict[str, object] = {}
        self._scan_pool = QThreadPool.globalInstance()
        self._selected_version: int | None = None
        self._selected_is_active = False
        self._task_busy = False
        self._candidate_counts: dict[int, dict[str, int]] = {}
        self._symbol_catalog: dict[str, dict[str, object]] = {}
        self._graphic_discovery_catalog: dict[str, dict[str, object]] = {}
        # v2.18.115: remember explicit user removals from the discovery queue so a
        # save/reload cannot resurrect rows merely because old discovery metadata is
        # still attached to the Profile.  "ignored" is persisted by the existing
        # discovery_decisions schema and is only a local/Profile decision; it never
        # changes any remote business G or server symbol-library file.
        self._discovery_decisions: dict[str, str] = {}
        self._pending_standard_file_records: list[dict[str, object]] = []
        # v2.18.119: a fresh-rescan draft is isolated from the saved ACTIVE/GLOBAL
        # version until the operator explicitly saves it as V(N+1).  The saved
        # profile is never mutated merely by scanning business G files.
        self._rescan_prepare_mode = False
        self._rescan_draft_mode = False
        self._rescan_draft_base_name = ""
        self._rescan_draft_base_version: int | None = None
        self._rescan_draft_target_version: int | None = None
        help_title, help_html = APP_HELP["site_profile"]
        super().__init__(
            "图元标准检查",
            "维护图元标准版本并检查业务 G；详细规则请查看“页面帮助”。",
            help_title,
            help_html,
            parent,
        )
        self.layout.addWidget(
            InfoBanner(
                "业务 G 只用于发现和检查；标准 G 来自只读服务器或人工上传。正式版本会冻结到本地版本库，源 G 不覆盖。"
            )
        )
        # Detailed rules intentionally live in Page Help/tooltips instead of the main
        # operator surface. Keep these established semantics explicit for maintenance:
        # - 先扫描图形 G 自动发现实际使用的图元候选；候选本身不是标准。
        # - w×h、AlignCenter、Pins 会自动从标准图元读取。
        # - 业务单线图不会参与 devref、尺寸、AlignCenter 或 pin 标准的生成。
        # - “检查图元标准”不修改 G；纠正仅生成 workspace 副本。
        # - 历史版本导出/恢复只读取本地冻结对象，绝不以服务器当前同名文件替代。

        standard_box = QGroupBox("图元标准")
        standard_layout = QVBoxLayout(standard_box)
        standard_layout.setContentsMargins(14, 18, 14, 12)
        standard_layout.setSpacing(10)

        self.active_profile_summary = QLabel("当前全局执行标准：尚未创建标准")
        self.active_profile_summary.setObjectName("sectionCaption")
        self.active_profile_summary.setWordWrap(True)
        standard_layout.addWidget(self.active_profile_summary)

        intro = QLabel(
            "流程：扫描候选 → 匹配/上传标准 G → 确认分类 → 保存版本。"
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
        self.set_global_button = QPushButton("设为全局版本")
        set_secondary(self.set_global_button)
        self.set_global_button.setToolTip("将下拉框当前选中的已保存版本设为整个 G File Studio 的全局执行标准。保存新版本不会自动改变这个选择。")
        self.set_global_button.clicked.connect(self._set_selected_global_version)
        manage_row.addWidget(self.set_global_button)
        self.profile_manage_button = QPushButton("标准管理")
        set_secondary(self.profile_manage_button)
        self.profile_menu = QMenu(self.profile_manage_button)
        self.new_action = self.profile_menu.addAction("新建标准")
        self.scan_action = self.profile_menu.addAction("为选中图元上传标准图元 G")
        self.profile_menu.addSeparator()
        self.version_details_action = self.profile_menu.addAction("查看版本库详情")
        self.verify_version_action = self.profile_menu.addAction("验证版本完整性")
        self.export_version_action = self.profile_menu.addAction("导出该版本完整 element 目录")
        self.export_version_zip_action = self.profile_menu.addAction("导出该版本完整 element ZIP")
        self.profile_menu.addSeparator()
        self.restore_action = self.profile_menu.addAction("恢复为新的编辑版本")
        self.delete_history_action = self.profile_menu.addAction("删除选中历史版本")
        self.delete_action = self.profile_menu.addAction("删除整个标准（全部版本）")
        self.new_action.triggered.connect(self._new_profile)
        self.scan_action.triggered.connect(self._scan_samples)
        self.version_details_action.triggered.connect(self._show_version_repository_details)
        self.verify_version_action.triggered.connect(self._verify_selected_version_repository)
        self.export_version_action.triggered.connect(lambda: self._export_selected_version_repository(zip_output=False))
        self.export_version_zip_action.triggered.connect(lambda: self._export_selected_version_repository(zip_output=True))
        self.restore_action.triggered.connect(self._restore_selected_version)
        self.delete_history_action.triggered.connect(self._delete_selected_history_version)
        self.delete_action.triggered.connect(self._delete_profile)
        self.profile_manage_button.setMenu(self.profile_menu)
        manage_row.addWidget(self.profile_manage_button)
        standard_layout.addLayout(manage_row)
        global_note = QLabel(
            "GLOBAL 仅手动切换；保存新的 ACTIVE 不会改变全局版本。"
        )
        global_note.setObjectName("mutedText")
        global_note.setWordWrap(True)
        standard_layout.addWidget(global_note)

        self.version_switch_status = QLabel("")
        self.version_switch_status.setObjectName("infoBanner")
        self.version_switch_status.setWordWrap(True)
        self.version_switch_status.setVisible(False)
        standard_layout.addWidget(self.version_switch_status)
        self.version_switch_progress = QProgressBar()
        self.version_switch_progress.setRange(0, 0)
        self.version_switch_progress.setTextVisible(False)
        self.version_switch_progress.setFixedHeight(8)
        self.version_switch_progress.setVisible(False)
        standard_layout.addWidget(self.version_switch_progress)

        repository_note = QLabel(
            "历史版本和图元文件冻结在本地版本库，软件升级不会自动清理；可在“标准管理”中验证、恢复或导出。"
        )
        repository_note.setObjectName("infoBanner")
        repository_note.setWordWrap(True)
        standard_layout.addWidget(repository_note)

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
            "w×h、AlignCenter、Pins 只从标准 G 读取；业务 G 仅提供候选和使用位置。"
        )
        standard_note.setWordWrap(True)
        standard_note.setObjectName("mutedText")
        standard_layout.addWidget(standard_note)

        # v2.18.113: authoritative symbol files can be discovered from the shared
        # read-only server library. Manual upload remains a fallback for unmatched
        # or deliberately local standards. The remote library is never written to.
        server_box = QGroupBox("服务器标准图元库（只读自动同步）")
        server_layout = QVBoxLayout(server_box)
        server_layout.setContentsMargins(12, 16, 12, 10)
        server_layout.setSpacing(8)
        self.server_standard_enabled = QCheckBox("自动从服务器图元库匹配标准 G（推荐）")
        self.server_standard_enabled.setChecked(
            self.user_settings.get_bool("site_profile/remote_symbol_library_enabled", True)
        )
        self.server_standard_enabled.toggled.connect(self._server_library_enabled_changed)
        server_layout.addWidget(self.server_standard_enabled)

        server_root_row = QHBoxLayout()
        server_root_row.addWidget(QLabel("图元库根目录"))
        self.server_symbol_root = QLineEdit(
            self.user_settings.get_value("site_profile/remote_symbol_library_root", DEFAULT_REMOTE_SYMBOL_ROOT)
            or DEFAULT_REMOTE_SYMBOL_ROOT
        )
        self.server_symbol_root.setPlaceholderText(DEFAULT_REMOTE_SYMBOL_ROOT)
        self.server_symbol_root.setToolTip("标准图元库目录由“连接与环境”统一管理；本页只读显示并使用该目录。")
        self.server_symbol_root.setReadOnly(True)
        server_root_row.addWidget(self.server_symbol_root, 1)
        self.server_connection_button = QPushButton("连接设置")
        set_secondary(self.server_connection_button)
        self.server_connection_button.clicked.connect(self.connectionSettingsRequested.emit)
        server_root_row.addWidget(self.server_connection_button)
        self.server_sync_button = QPushButton("检查 / 同步服务器图元库")
        set_secondary(self.server_sync_button)
        self.server_sync_button.clicked.connect(lambda: self._start_server_symbol_sync(background=False, auto_bind=True))
        server_root_row.addWidget(self.server_sync_button)
        self.server_new_version_button = QPushButton("基于当前版本创建新版本")
        set_secondary(self.server_new_version_button)
        self.server_new_version_button.setVisible(False)
        self.server_new_version_button.setEnabled(False)
        self.server_new_version_button.clicked.connect(self._create_next_version_from_server)
        server_root_row.addWidget(self.server_new_version_button)
        self.server_cache_button = QPushButton("打开本地缓存")
        set_secondary(self.server_cache_button)
        self.server_cache_button.clicked.connect(self._open_server_symbol_cache)
        server_root_row.addWidget(self.server_cache_button)
        server_layout.addLayout(server_root_row)

        self.server_library_progress = QProgressBar()
        self.server_library_progress.setRange(0, 100)
        self.server_library_progress.setValue(0)
        self.server_library_progress.setFormat("服务器图元库同步 %p%")
        self.server_library_progress.setVisible(False)
        server_layout.addWidget(self.server_library_progress)
        self.server_library_status = QLabel(
            "尚未检查服务器图元库。扫描候选后可自动匹配标准 G。"
        )
        self.server_library_status.setWordWrap(True)
        self.server_library_status.setObjectName("mutedText")
        server_layout.addWidget(self.server_library_status)
        server_notice = QLabel(
            "服务器严格只读；匹配文件仅下载到本地缓存，不会修改服务器。"
        )
        server_notice.setWordWrap(True)
        server_notice.setObjectName("infoBanner")
        server_layout.addWidget(server_notice)
        standard_layout.addWidget(server_box)

        self._server_library_timer = QTimer(self)
        self._server_library_timer.setInterval(5 * 60 * 1000)
        self._server_library_timer.timeout.connect(
            lambda: self._start_server_symbol_sync(background=True, auto_bind=True)
        )

        discovery_box = QGroupBox("图形 G 图元发现（只发现候选，不生成标准）")
        discovery_layout = QVBoxLayout(discovery_box)
        discovery_layout.setContentsMargins(12, 16, 12, 10)
        discovery_layout.setSpacing(8)
        discovery_note = QLabel(
            "选择业务 G 后扫描候选；需要重新建立下一版本时使用“全量重新扫描 → 新版本草稿”。"
        )
        discovery_note.setWordWrap(True)
        discovery_note.setObjectName("mutedText")
        discovery_layout.addWidget(discovery_note)

        # v2.18.119: two distinct workflows are intentionally exposed.  Ordinary
        # scan updates the current editable discovery draft; fresh rescan creates an
        # isolated V(N+1) DRAFT from the selected business G set, using the scan as
        # the source of truth while inheriting only matching prior classifications /
        # authoritative bindings.  GLOBAL never moves automatically.
        rescan_version_row = QHBoxLayout()
        self.rescan_new_version_button = QPushButton("全量重新扫描 → 新版本草稿")
        set_secondary(self.rescan_new_version_button)
        self.rescan_new_version_button.setToolTip(
            "从当前 ACTIVE 标准创建下一版本草稿：重新读取所选业务 G；本次扫描不存在的旧候选不会带入。"
            "匹配到的旧图元可继承人工分类/标准绑定，保存后才生成新的 ACTIVE；GLOBAL 不自动切换。"
        )
        self.rescan_new_version_button.clicked.connect(self._prepare_fresh_rescan_version)
        self.cancel_rescan_draft_button = QPushButton("取消新版本草稿")
        set_secondary(self.cancel_rescan_draft_button)
        self.cancel_rescan_draft_button.setVisible(False)
        self.cancel_rescan_draft_button.clicked.connect(self._cancel_fresh_rescan_draft)
        rescan_version_row.addWidget(self.cancel_rescan_draft_button)
        self.rescan_version_hint = QLabel(
            "普通扫描更新当前候选；全量重扫创建下一版本草稿。"
        )
        self.rescan_version_hint.setObjectName("mutedText")
        self.rescan_version_hint.setWordWrap(True)
        rescan_version_row.addWidget(self.rescan_version_hint, 1)
        discovery_layout.addLayout(rescan_version_row)

        # v2.18.107: the whole graphic-G discovery input area is one visibility unit.
        # When the ACTIVE standard is locked, hide the source mode/SSH/file list as
        # well as its scan/filter actions. Unlocking restores this panel immediately.
        self.discovery_input_panel = QWidget()
        discovery_input_layout = QVBoxLayout(self.discovery_input_panel)
        discovery_input_layout.setContentsMargins(0, 0, 0, 0)
        discovery_input_layout.setSpacing(8)
        self.discovery_source = InputSourceSelector(
            default_directory=default_workspace() / "input",
            file_filter="G Files (*.sln.pic.g *.g)",
            file_tooltip="选择一张用于发现图元候选的图形 G 文件。",
            directory_tooltip="选择包含大量图形 G 的目录，批量统计其中使用到的图元。",
            settings_prefix="site_profile_discovery_source",
            settings_service=self.user_settings,
        )
        discovery_input_layout.addWidget(self.discovery_source)
        discovery_actions = QHBoxLayout()
        self.discovery_scan_button = QPushButton("扫描当前版本候选")
        self.discovery_scan_button.setToolTip(
            "普通模式：更新当前可编辑候选；新版本草稿模式：重新读取所选业务 G 并生成 V(N+1) DRAFT。"
            "两种模式都只读业务 G，不会把业务 G 当作标准图元。"
        )
        self.discovery_scan_button.clicked.connect(self._scan_graphic_symbol_candidates)
        discovery_actions.addWidget(self.discovery_scan_button)
        # v2.18.119: keep the full-rescan/new-version action beside the ordinary scan.
        # The previous placement above the source list was easy to miss once the page
        # was scrolled to the selected G files/table, which made users accidentally
        # run an ordinary scan and wonder why the saved candidate set stayed unchanged.
        discovery_actions.addWidget(self.rescan_new_version_button)
        self.discovery_filter = QLineEdit()
        self.discovery_filter.setPlaceholderText("筛选表格：设备类型 / XML / devref / 文件名")
        self.discovery_filter.textChanged.connect(self._apply_standard_table_filter)
        discovery_actions.addWidget(self.discovery_filter, 1)
        self.pending_only_checkbox = QCheckBox("只看待上传候选")
        self.pending_only_checkbox.toggled.connect(self._apply_standard_table_filter)
        discovery_actions.addWidget(self.pending_only_checkbox)
        discovery_input_layout.addLayout(discovery_actions)
        # v2.18.112: discovery progress lives directly under the scan action so it
        # is visible immediately when scanning starts, rather than below the wide
        # standard table where the user may not see it until much later.
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setFormat("扫描图形 G 图元 %p%")
        self.scan_progress.setToolTip("扫描业务/图形 G 并统计图元候选；SSH 下载与本地解析都在后台线程执行。")
        self.scan_progress.setVisible(False)
        discovery_input_layout.addWidget(self.scan_progress)
        discovery_layout.addWidget(self.discovery_input_panel)
        self.discovery_locked_note = QLabel("当前 ACTIVE 标准已锁定：图形 G 图元发现输入已隐藏。点击“解锁当前版本”后会自动恢复输入方式、SSH/本地文件选择及扫描操作。")
        self.discovery_locked_note.setWordWrap(True)
        self.discovery_locked_note.setObjectName("mutedText")
        self.discovery_locked_note.setVisible(False)
        discovery_layout.addWidget(self.discovery_locked_note)
        standard_layout.addWidget(discovery_box)

        custom_actions = QHBoxLayout()
        self.upload_standard_button = QPushButton("为选中图元上传 / 更新标准 G")
        self.upload_standard_button.clicked.connect(self._scan_samples)
        custom_actions.addWidget(self.upload_standard_button)
        # v2.18.105: no fixed SMART/NORMAL role pairs are pre-created. Scope is
        # learned/suggested from the graphic G candidate itself, then confirmed on
        # that generic row. Keep a hidden compatibility object so archived profile
        # code paths remain harmless without exposing the obsolete pairing control.
        self.share_pair_checkbox = QCheckBox("SMART / NORMAL 共用此标准")
        self.share_pair_checkbox.setVisible(False)
        self.share_pair_checkbox.toggled.connect(self._share_pair_toggled)
        self.add_custom_button = QPushButton("手动添加图元（可选）")
        set_secondary(self.add_custom_button)
        self.add_custom_button.clicked.connect(self._add_custom_standard)
        custom_actions.addWidget(self.add_custom_button)
        self.delete_custom_button = QPushButton("删除选中图元")
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

        self.standard_table_overview = QLabel("图元标准表（左侧为序号）：共 0 项图元")
        self.standard_table_overview.setObjectName("sectionCaption")
        self.standard_table_overview.setWordWrap(True)
        self.standard_table_overview.setToolTip("统计当前标准表中的图元种类、当前显示项、已配置标准、待配置标准以及扫描到的实例总数。")
        standard_layout.addWidget(self.standard_table_overview)

        self.standard_table = QTableWidget(0, 17)
        self.standard_table.setHorizontalHeaderLabels(
            [
                "检查范围", "业务类型 / 设备类型", "检查对象 XML", "标准图元文件",
                "主体 ID", "w×h", "AlignCenter", "Pins", "标准来源", "状态",
                "图元用途", "设备子类型", "设备层级", "扫描图元 G 文件全名",
                "图形 G 发现 devref", "发现次数", "样本位置",
            ]
        )
        self.standard_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.standard_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.standard_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        # v2.18.112: use the vertical header as the explicit row serial-number
        # gutter.  This avoids shifting the mature 17-column business schema while
        # still giving every displayed symbol a stable, easy-to-read sequence.
        vertical_header = self.standard_table.verticalHeader()
        vertical_header.setVisible(True)
        vertical_header.setMinimumWidth(50)
        vertical_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.standard_table.setObjectName("symbolStandardTable")
        self.standard_table.setShowGrid(True)
        self.standard_table.setAlternatingRowColors(True)
        # v2.18.105: locating is no longer user-configured.  The candidate discovered
        # from the business G and the authoritative uploaded symbol G provide enough
        # information for the program to derive the internal locator automatically.
        # Keep every visible column content-sized so long symbol-G filenames/devrefs
        # are shown in full; users can inspect the wide table with horizontal scroll.
        self.standard_table.setStyleSheet(
            "QTableWidget#symbolStandardTable { padding: 0px; }"
            "QTableWidget#symbolStandardTable QComboBox { margin: 0px; border: none; border-radius: 0px; padding: 3px 24px 3px 6px; }"
            "QTableWidget#symbolStandardTable QComboBox::drop-down { border: none; width: 22px; }"
        )
        self.standard_table.itemSelectionChanged.connect(self._standard_row_selection_changed)
        header = self.standard_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionsMovable(False)
        header.setTextElideMode(Qt.TextElideMode.ElideNone)
        header.setMinimumSectionSize(72)
        for column in range(self.standard_table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.standard_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.standard_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.standard_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.standard_table.setMinimumHeight(380)
        # v2.18.105 continues the discovery-driven standard library.  There are no
        # built-in/system rows and no user-entered locator rule/condition columns.
        self._standard_specs = []
        self._fit_standard_table_columns()
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

        self.scan_summary = QLabel("尚未配置标准图元。")
        self.scan_summary.setObjectName("mutedText")
        self.scan_summary.setWordWrap(True)
        standard_layout.addWidget(self.scan_summary)

        self.layout.addWidget(standard_box)

        source_box = QGroupBox("待检查 G 文件")
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(14, 18, 14, 12)
        source_layout.setSpacing(10)
        source_note = QLabel(
            "选择待检查业务 G；源文件只读，结果写入 workspace。"
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

        self.current_profile_label = QLabel("当前全局执行标准：未选择")
        self.current_profile_label.setObjectName("sectionCaption")
        self.current_profile_label.setWordWrap(True)
        self.current_profile_label.setVisible(False)
        apply_layout.addWidget(self.current_profile_label)

        execute_note = QLabel(
            "检查只读；纠正仅生成 workspace 副本，不覆盖源 G；连接修复会按 ACTIVE 标准 Pin 计算设备真实断点：双 Pin 两侧线已到 Pin 时删除旁路贯穿 ConnectLine，并补齐 link/node_area；单 Pin 轻微斜线自动做水平/垂直正交修复。"
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

        global_name, global_version = self.service.get_global_profile_selection()
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        selected_index = -1
        for profile_name, current in sorted(profiles.items(), key=lambda row: row[0].casefold()):
            versions = self.service.load_profile_versions(profile_name) or [current]
            for profile in reversed(versions):
                is_active = profile.profile_version == current.profile_version
                ready, _issues = self.service.validate_authoritative_standard(profile)
                standard_rows = self._profile_standard_rows(profile)
                configured = sum(
                    1 for row in standard_rows
                    if bool(row.get("enabled", True)) and str(row.get("standard_devref", "")).strip()
                )
                unique_files = len({
                    str(row.get("standard_devref", "")).strip().casefold()
                    for row in standard_rows if str(row.get("standard_devref", "")).strip()
                })
                state = "ACTIVE" if is_active else "ARCHIVED"
                readiness = "READY" if ready else "NOT READY"
                lock_label = " · LOCKED" if profile.locked else ""
                global_label = " · GLOBAL" if profile_name == global_name and profile.profile_version == global_version else ""
                label = (
                    f"{profile.site_name} / {profile_name} / V{profile.profile_version} · {state}{global_label} · {readiness}{lock_label}"
                    f" · 标准图元 {configured} · 标准文件 {unique_files}"
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

    def _fit_standard_table_columns(self) -> None:
        """Size the symbol-standard table from its actual visible content.

        Unlike the generic dense-table helper, this table intentionally does not
        clamp long filenames/devrefs.  The user asked to see the complete scanned
        symbol-G filename, so horizontal scrolling is preferred over ellipsis.
        """
        if not hasattr(self, "standard_table"):
            return
        table = self.standard_table
        header = table.horizontalHeader()
        table.resizeColumnsToContents()
        for column in range(table.columnCount()):
            # sectionSizeHint covers the full header text while columnWidth after
            # resizeColumnsToContents covers the longest current cell/widget.
            width = max(table.columnWidth(column), header.sectionSizeHint(column), 72)
            table.setColumnWidth(column, width + 16)

        # Preserve the readable cell-widget height that the generic dense-table
        # helper provides to its fixed schemas.  This table is discovery-driven,
        # so its schema is intentionally not registered in that clamping helper.
        for row in range(table.rowCount()):
            row_height = 40
            for column in range(table.columnCount()):
                cell_widget = table.cellWidget(row, column)
                if cell_widget is None:
                    continue
                row_height = max(
                    row_height,
                    cell_widget.sizeHint().height() + 8,
                    cell_widget.minimumSizeHint().height() + 8,
                )
            table.setRowHeight(row, row_height)
        self._refresh_standard_table_overview()

    def _refresh_standard_table_overview(self) -> None:
        """Refresh row serial numbers and a compact symbol-count summary."""
        if not hasattr(self, "standard_table"):
            return
        table = self.standard_table
        total = table.rowCount()
        visible = 0
        configured = 0
        pending = 0
        instances = 0
        labels: list[str] = []
        for row in range(total):
            labels.append(str(row + 1))
            if not table.isRowHidden(row):
                visible += 1
            if self._standard_file_devref(row):
                configured += 1
            marker = table.item(row, 0)
            if marker is not None and marker.data(Qt.ItemDataRole.UserRole) == "custom":
                try:
                    instances += max(0, int(marker.data(Qt.ItemDataRole.UserRole + 5) or 0))
                except (TypeError, ValueError):
                    pass
                if bool(marker.data(Qt.ItemDataRole.UserRole + 3)) and not self._standard_file_devref(row):
                    pending += 1
        if labels:
            table.setVerticalHeaderLabels(labels)
        text = (
            f"图元标准表（左侧为序号）：共 {total} 项图元 | 当前显示 {visible} 项 | "
            f"已配置标准 {configured} 项 | 待配置标准 {pending} 项"
        )
        if instances:
            text += f" | 扫描实例 {instances} 个"
        if hasattr(self, "standard_table_overview"):
            self.standard_table_overview.setText(text)

    @staticmethod
    def _observed_symbol_g_filename(devref: str) -> str:
        """Return the complete symbol-G filename encoded in a business-G devref."""
        value = str(devref or "").strip().lstrip("#")
        return value.split(":", 1)[0].strip() if value else ""

    @staticmethod
    def _same_symbol_g_filename(expected: str, actual: str) -> bool:
        """Return True only when two symbol-G basenames are the same."""
        expected_name = Path(str(expected or "").strip()).name
        actual_name = Path(str(actual or "").strip()).name
        return bool(expected_name and actual_name and expected_name.casefold() == actual_name.casefold())

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
                "standard_source": str(row.get("standard_source", "manual") or "manual").strip().lower(),
                "remote_host": str(row.get("remote_host", "")).strip(),
                "remote_root": str(row.get("remote_root", "")).strip(),
                "remote_path": str(row.get("remote_path", "")).strip(),
                "remote_size": int(row.get("remote_size", 0) or 0),
                "remote_mtime": int(row.get("remote_mtime", 0) or 0),
                "cache_path": str(row.get("cache_path", "")).strip(),
                "synced_at": str(row.get("synced_at", "")).strip(),
                "p_NameString": "",
                "key_name": "",
            }
        return catalog

    def _editor_standard_records(self) -> list[dict[str, object]]:
        """Return current ACTIVE files plus pending uploads, with pending files winning.

        This makes partial updates safe: replacing one learned symbol standard does not
        force the user to re-upload any other standard files.
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

    @staticmethod
    def _profile_standard_rows(profile: SiteSmartProfile) -> list[dict[str, object]]:
        """Return generic standard rows, migrating legacy fixed RMU roles for display/save.

        v2.18.105 keeps the six pre-created SMART/NORMAL system rows. Old profiles
        remain readable: any legacy role that already has an authoritative uploaded
        devref is represented as a normal generic row. Once the user saves again,
        the profile is persisted using ``custom_symbols`` only.
        """
        rows = [dict(item) for item in profile.custom_symbols if isinstance(item, dict)]
        legacy = [
            ("legacy-smart-lbs", "SMART", "LBS", "CBreakerDis", profile.smart_lbs_devref),
            ("legacy-smart-breaker", "SMART", "Circuit Breaker", "CBreakerDis", profile.smart_breaker_devref),
            ("legacy-smart-ground", "SMART", "接地刀闸", "ZhaiWaiJieDiDaoZha", profile.smart_ground_devref),
            ("legacy-normal-lbs", "NORMAL", "LBS", "CBreakerDis", profile.normal_lbs_devref),
            ("legacy-normal-breaker", "NORMAL", "Circuit Breaker", "CBreakerDis", profile.normal_breaker_devref),
            ("legacy-normal-ground", "NORMAL", "接地刀闸", "ZhaiWaiJieDiDaoZha", profile.normal_ground_devref),
        ]

        # Index existing generic definitions. If the same uploaded symbol was used
        # by SMART and NORMAL legacy rows, collapse it to one ANY row rather than
        # recreating the old paired-row UI.
        indexed: dict[tuple[str, str, str], int] = {}
        for idx, row in enumerate(rows):
            devref = str(row.get("standard_devref", "")).strip().casefold()
            role = str(row.get("role", row.get("device_type", ""))).strip().casefold()
            tag = str(row.get("element_tag", "")).strip().casefold()
            if devref:
                indexed[(devref, role, tag)] = idx

        catalog = profile.symbol_catalog if isinstance(profile.symbol_catalog, dict) else {}
        for uid, scope, role, default_tag, devref_raw in legacy:
            devref = str(devref_raw or "").strip()
            if not devref:
                continue
            meta = dict(catalog.get(devref, {})) if isinstance(catalog.get(devref, {}), dict) else {}
            element_tag = str(meta.get("element_tag", "")).strip() or default_tag
            key = (devref.casefold(), role.casefold(), element_tag.casefold())
            if key in indexed:
                existing = rows[indexed[key]]
                prior_scope = str(existing.get("scope", "ANY")).strip().upper() or "ANY"
                if prior_scope != scope:
                    existing["scope"] = "ANY"
                continue
            indexed[key] = len(rows)
            rows.append({
                "uid": uid,
                "scope": scope,
                "role": role,
                "device_type": role,
                "device_subtype": "",
                "device_level": "设备内部部件",
                "symbol_usage": "设备组成图元",
                "element_tag": element_tag,
                "standard_devref": devref,
                "match_attr": "devref",
                "match_value": devref,
                "enabled": True,
                "source_file": str(meta.get("source_file", "")).strip(),
                "observed_devref": devref,
                "observed_count": 0,
                "observed_files": [],
                "observed_examples": [],
            })
        return rows

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
                "绑定方式：从图形 G 发现候选后，优先按完整文件名从只读服务器图元库自动匹配；服务器未找到/冲突时可人工上传。",
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

        candidate_only = bool(entry.get("candidate_only", False)) and not str(entry.get("standard_devref", "")).strip()
        observed_devref = str(entry.get("observed_devref", "")).strip()
        # Compatibility: only a legacy devref locator can safely stand in for
        # discovery evidence. Old p_NameString/key_name values must never be
        # rendered as if they were scanned symbol-G filenames.
        legacy_match_attr = str(entry.get("match_attr", "devref")).strip() or "devref"
        if not observed_devref and legacy_match_attr == "devref":
            observed_devref = str(entry.get("match_value", "")).strip()
        observed_symbol_file = str(entry.get("observed_symbol_file", "")).strip() or self._observed_symbol_g_filename(observed_devref)
        observed_count = max(0, int(entry.get("observed_count", entry.get("count", 0)) or 0))
        observed_files = [str(item) for item in entry.get("observed_files", entry.get("files", [])) if str(item).strip()] if isinstance(entry.get("observed_files", entry.get("files", [])), list) else []
        observed_examples = [dict(item) for item in entry.get("observed_examples", entry.get("sample_positions", [])) if isinstance(item, dict)] if isinstance(entry.get("observed_examples", entry.get("sample_positions", [])), list) else []

        scope_combo = WheelSafeComboBox()
        scope_combo.addItems(["ANY", "SMART", "NORMAL"])
        scope = str(entry.get("scope", entry.get("suggested_scope", "ANY"))).strip().upper() or "ANY"
        scope_combo.setCurrentText(scope if scope in {"ANY", "SMART", "NORMAL"} else "ANY")
        self.standard_table.setCellWidget(row, 0, scope_combo)
        marker = QTableWidgetItem("")
        marker.setData(Qt.ItemDataRole.UserRole, "custom")
        marker.setData(Qt.ItemDataRole.UserRole + 1, str(entry.get("uid", "")).strip() or uuid4().hex)
        marker.setData(Qt.ItemDataRole.UserRole + 3, candidate_only)
        marker.setData(Qt.ItemDataRole.UserRole + 4, observed_devref)
        marker.setData(Qt.ItemDataRole.UserRole + 5, observed_count)
        marker.setData(Qt.ItemDataRole.UserRole + 6, observed_files)
        marker.setData(Qt.ItemDataRole.UserRole + 7, observed_examples)
        self.standard_table.setItem(row, 0, marker)

        role_default = str(entry.get("role", entry.get("device_type", entry.get("suggested_device_type", "")))).strip()
        if not role_default and observed_devref:
            observed_file = str(entry.get("observed_symbol_file", "")).strip()
            observed_subject = str(entry.get("observed_subject", "")).strip()
            role_default = infer_device_type(
                role=observed_subject, source_file=observed_file,
                element_tag=str(entry.get("element_tag", "")).strip(), element_id=observed_subject,
            )
        role_item = QTableWidgetItem(role_default or "自定义图元")
        self.standard_table.setItem(row, 1, role_item)
        tag_item = QTableWidgetItem(str(entry.get("element_tag", "")).strip())
        self.standard_table.setItem(row, 2, tag_item)

        selected_devref = str(entry.get("standard_devref", "")).strip()
        self._set_standard_file_cell(row, selected_devref)

        # Columns 4~7 are authoritative standard properties and deliberately stay
        # blank until the user uploads the real symbol-definition G. Business G
        # observations must never become the standard geometry.
        for column in (4, 5, 6, 7):
            self._set_readonly_cell(row, column, "-")

        # Locator rule/condition are intentionally not user-editable anymore.
        # Internally the row is matched by the devref observed during discovery;
        # after upload, the authoritative devref is also accepted by the engine so
        # repeated checks validate the corrected/new symbol as well.
        self._set_readonly_cell(row, 8, "图形 G 发现" if candidate_only else "-")
        self._set_readonly_cell(row, 9, "待匹配/上传标准 G" if candidate_only else "待确认")

        meta = self._symbol_meta(selected_devref)
        auto_usage = not str(entry.get("symbol_usage", entry.get("suggested_usage", ""))).strip()
        usage = str(entry.get("symbol_usage", entry.get("suggested_usage", ""))).strip()
        if usage not in SYMBOL_USAGE_VALUES:
            usage = infer_symbol_usage(
                role=role_item.text(),
                source_file=str(meta.get("source_file", entry.get("observed_symbol_file", "")) or ""),
                element_tag=tag_item.text(),
            )
        usage_combo = WheelSafeComboBox()
        usage_combo.addItems(list(SYMBOL_USAGE_VALUES))
        usage_combo.setCurrentText(usage)
        self.standard_table.setCellWidget(row, 10, usage_combo)
        self.standard_table.setItem(row, 11, QTableWidgetItem(str(entry.get("device_subtype", "")).strip()))

        level = str(entry.get("device_level", "")).strip()
        if level not in DEVICE_LEVEL_VALUES:
            level = default_device_level(usage)
        level_combo = WheelSafeComboBox()
        level_combo.addItems(list(DEVICE_LEVEL_VALUES))
        level_combo.setCurrentText(level)
        self.standard_table.setCellWidget(row, 12, level_combo)
        marker.setData(Qt.ItemDataRole.UserRole + 2, auto_usage)

        self._set_readonly_cell(row, 13, observed_symbol_file or "-")
        self._set_readonly_cell(row, 14, observed_devref or "-")
        self._set_readonly_cell(row, 15, str(observed_count))
        example_text = self._discovery_example_text(observed_examples, observed_files)
        self._set_readonly_cell(row, 16, example_text or "-")
        if observed_devref:
            tooltip = self._discovery_tooltip(entry, observed_devref, observed_count, observed_files, observed_examples)
            for column in (13, 14, 15, 16):
                item = self.standard_table.item(row, column)
                if item is not None:
                    item.setToolTip(tooltip)

        def usage_changed(_index: int, m=marker, u=usage_combo, lv=level_combo) -> None:
            m.setData(Qt.ItemDataRole.UserRole + 2, False)
            lv.setCurrentText(default_device_level(u.currentText()))

        usage_combo.activated.connect(usage_changed)

        self._refresh_custom_standard_row(row)
        self._fit_standard_table_columns()
        return row

    @staticmethod
    def _discovery_example_text(examples: list[dict[str, object]], files: list[str]) -> str:
        if examples:
            first = examples[0]
            file_name = str(first.get("file", "")).strip()
            element_id = str(first.get("element_id", "")).strip()
            try:
                x = float(first.get("x", 0.0) or 0.0)
                y = float(first.get("y", 0.0) or 0.0)
                pos = f"({x:g}, {y:g})"
            except (TypeError, ValueError):
                pos = ""
            bits = [value for value in (file_name, f"id={element_id}" if element_id else "", pos) if value]
            return " · ".join(bits)
        if files:
            return files[0]
        return ""

    @staticmethod
    def _discovery_tooltip(
        entry: dict[str, object],
        observed_devref: str,
        observed_count: int,
        observed_files: list[str],
        observed_examples: list[dict[str, object]],
    ) -> str:
        names = [str(item) for item in entry.get("sample_names", []) if str(item).strip()] if isinstance(entry.get("sample_names", []), list) else []
        symbol_file = str(entry.get("observed_symbol_file", "")).strip()
        if not symbol_file:
            value = str(observed_devref or "").strip().lstrip("#")
            symbol_file = value.split(":", 1)[0].strip() if value else ""
        lines = [
            "业务图形 G 发现信息（仅作候选，不是标准）：",
            f"扫描图元 G 文件全名：{symbol_file or '-'}",
            f"devref：{observed_devref or '-'}",
            f"出现次数：{observed_count}",
            f"图形 G 文件：{', '.join(observed_files[:12]) or '-'}",
        ]
        if names:
            lines.append(f"实例名称样本：{', '.join(names[:8])}")
        if observed_examples:
            formatted = []
            for item in observed_examples[:5]:
                formatted.append(
                    f"{item.get('file', '-')} / id={item.get('element_id', '-') or '-'} / "
                    f"x={item.get('x', '-')}, y={item.get('y', '-')}"
                )
            lines.append("位置样本：" + "；".join(formatted))
        lines.append("w×h / AlignCenter / Pins 必须以后续上传的权威图元 G 为准。")
        return "\n".join(lines)

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
        marker_item = self.standard_table.item(row, 0)
        usage_combo = self.standard_table.cellWidget(row, 10)
        level_combo = self.standard_table.cellWidget(row, 12)
        if (
            marker_item is not None
            and bool(marker_item.data(Qt.ItemDataRole.UserRole + 2))
            and isinstance(usage_combo, WheelSafeComboBox)
        ):
            inferred = infer_symbol_usage(
                role=(self.standard_table.item(row, 1).text() if self.standard_table.item(row, 1) else ""),
                source_file=str(meta.get("source_file", "") or ""),
                element_tag=(self.standard_table.item(row, 2).text() if self.standard_table.item(row, 2) else ""),
            )
            # A discovery row may carry a stronger usage suggestion (for example a
            # .zt.icn.g status symbol) even before an authoritative standard exists.
            if not devref and marker_item is not None:
                observed = str(marker_item.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
                discovery = self._graphic_discovery_catalog.get(observed, {})
                suggested = str(discovery.get("suggested_usage", "")).strip()
                if suggested in SYMBOL_USAGE_VALUES:
                    inferred = suggested
            usage_combo.blockSignals(True)
            usage_combo.setCurrentText(inferred)
            usage_combo.blockSignals(False)
            if isinstance(level_combo, WheelSafeComboBox):
                level_combo.setCurrentText(default_device_level(inferred))
        source_item = self.standard_table.item(row, 8) or self._set_readonly_cell(row, 8, "-")
        source_file = Path(str(meta.get("source_file", "")).strip()).name
        standard_source = str(meta.get("standard_source", "manual") or "manual").strip().lower()
        candidate_only = bool(marker_item.data(Qt.ItemDataRole.UserRole + 3)) if marker_item is not None else False
        observed_count = int(marker_item.data(Qt.ItemDataRole.UserRole + 5) or 0) if marker_item is not None else 0
        observed_devref = str(marker_item.data(Qt.ItemDataRole.UserRole + 4) or "").strip() if marker_item is not None else ""
        observed_file_item = self.standard_table.item(row, 13) or self._set_readonly_cell(row, 13, "-")
        observed_file_item.setText(self._observed_symbol_g_filename(observed_devref) or "-")
        if devref and source_file and standard_source == "server":
            remote_path = str(meta.get("remote_path", "")).strip()
            remote_mtime = int(meta.get("remote_mtime", 0) or 0)
            synced_at = str(meta.get("synced_at", "")).strip()
            source_item.setText("服务器图元库")
            source_item.setToolTip(
                "\n".join([
                    f"文件：{source_file}",
                    f"服务器：{meta.get('remote_host', '-') or '-'}",
                    f"远程路径：{remote_path or '-'}",
                    f"服务器 mtime：{remote_mtime or '-'}",
                    f"最后同步：{synced_at or '-'}",
                ])
            )
        elif devref and source_file:
            source_item.setText("用户上传")
            source_item.setToolTip(source_file)
        elif candidate_only:
            source_item.setText("图形 G 发现")
            source_item.setToolTip("候选来自业务/图形 G；服务器未自动匹配时可人工上传权威标准图元 G。")
        else:
            source_item.setText("未上传" if not devref else "-")
            source_item.setToolTip(source_file or "未上传")
        status_item = self.standard_table.item(row, 9) or self._set_readonly_cell(row, 9, "待确认")
        if not devref:
            status_item.setText(f"发现 {observed_count} 次 · 待匹配/上传标准 G" if candidate_only else "缺少标准图元")
        elif not (self.standard_table.item(row, 2) and self.standard_table.item(row, 2).text().strip()):
            status_item.setText("缺少 XML 元素")
        elif standard_source == "server" and observed_count:
            status_item.setText(f"READY · 服务器已同步 · 业务G发现 {observed_count} 次")
        elif standard_source == "server":
            status_item.setText("READY · 服务器已同步")
        elif observed_count:
            status_item.setText(f"READY · 业务G发现 {observed_count} 次")
        else:
            status_item.setText("就绪")

    def _add_custom_standard(self) -> None:
        row = self._insert_custom_standard_row()
        self.standard_table.selectRow(row)
        self.standard_table.scrollToItem(self.standard_table.item(row, 1))
        self._update_action_state()

    def _delete_selected_custom_standard(self) -> None:
        row = self.standard_table.currentRow()
        if row >= 0:
            marker = self.standard_table.item(row, 0)
            observed_devref = (
                str(marker.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
                if marker is not None else ""
            )
            # A row discovered from business G is a separate piece of metadata from
            # the authoritative standard itself.  Before v2.18.115, deleting the row
            # removed it only from the visible table; Save -> reload then replayed the
            # still-persisted discovery_catalog and the row appeared again even though
            # the user had not rescanned.  Treat Delete as an explicit Profile-level
            # ignore decision and remove the current in-memory discovery entry too.
            if observed_devref:
                self._discovery_decisions[observed_devref] = "ignored"
                self._graphic_discovery_catalog.pop(observed_devref, None)
            self.standard_table.removeRow(row)
        self._apply_standard_table_filter()
        self._update_action_state()

    def _add_unmapped_scanned_symbols(self) -> None:
        """Legacy entry retained for compatibility; business G can no longer become a standard."""
        QMessageBox.information(
            self,
            "必须上传标准图元",
            "业务单线图中发现的 devref 只能作为检查线索，不能直接加入图元标准。\n"
            "请通过“标准管理 → 上传标准图元 G”上传对应的真实图元定义文件，再将其绑定到业务类型/图元角色。",
        )

    def _collect_custom_symbols(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in self._custom_standard_rows():
            marker_item = self.standard_table.item(row, 0)
            scope_combo = self.standard_table.cellWidget(row, 0)
            usage_combo = self.standard_table.cellWidget(row, 10)
            level_combo = self.standard_table.cellWidget(row, 12)
            if (
                not isinstance(scope_combo, WheelSafeComboBox)
                or not isinstance(usage_combo, WheelSafeComboBox)
                or not isinstance(level_combo, WheelSafeComboBox)
            ):
                continue
            devref = self._standard_file_devref(row)
            role = (self.standard_table.item(row, 1).text() if self.standard_table.item(row, 1) else "").strip()
            element_tag = (self.standard_table.item(row, 2).text() if self.standard_table.item(row, 2) else "").strip()
            candidate_only = bool(marker_item.data(Qt.ItemDataRole.UserRole + 3)) if marker_item else False
            # A discovered business-G row is intentionally allowed to stay pending.
            # It is not part of the authoritative standard until the user uploads
            # a real icon-definition G into the row.
            if candidate_only and not devref:
                continue
            if not devref and not role and not element_tag:
                continue
            meta = self._symbol_meta(devref)
            observed_devref = str(marker_item.data(Qt.ItemDataRole.UserRole + 4) or "").strip() if marker_item else ""
            observed_count = max(0, int(marker_item.data(Qt.ItemDataRole.UserRole + 5) or 0)) if marker_item else 0
            observed_files = marker_item.data(Qt.ItemDataRole.UserRole + 6) if marker_item else []
            observed_examples = marker_item.data(Qt.ItemDataRole.UserRole + 7) if marker_item else []
            result.append({
                "uid": str(marker_item.data(Qt.ItemDataRole.UserRole + 1) or uuid4().hex) if marker_item else uuid4().hex,
                "scope": scope_combo.currentText().strip().upper() or "ANY",
                "role": role or self._devref_short(devref) or "自定义图元",
                "device_type": role or self._devref_short(devref) or "自定义图元",
                "device_subtype": (self.standard_table.item(row, 11).text() if self.standard_table.item(row, 11) else "").strip(),
                "device_level": level_combo.currentText().strip() or default_device_level(usage_combo.currentText()),
                "symbol_usage": usage_combo.currentText().strip() or "其他",
                "element_tag": element_tag,
                "standard_devref": devref,
                # Internal locator is learned from discovery + uploaded standard;
                # the user no longer specifies a locator rule or condition.
                "match_attr": "devref",
                "match_value": observed_devref or devref,
                "enabled": True,
                "source_file": str(meta.get("source_file", "")).strip(),
                "observed_devref": observed_devref,
                "observed_symbol_file": self._observed_symbol_g_filename(observed_devref),
                "observed_count": observed_count,
                "observed_files": list(observed_files) if isinstance(observed_files, list) else [],
                "observed_examples": list(observed_examples) if isinstance(observed_examples, list) else [],
            })
        return result

    def _load_custom_symbols(self, entries: list[dict[str, object]]) -> None:
        self._clear_custom_standard_rows()
        for entry in entries:
            self._insert_custom_standard_row(entry)

    @staticmethod
    def _discovery_entry(meta: dict[str, object]) -> dict[str, object]:
        observed_devref = str(meta.get("observed_devref", meta.get("devref", ""))).strip()
        role = str(meta.get("suggested_device_type", "")).strip()
        if not role:
            role = infer_device_type(
                role=str(meta.get("observed_subject", meta.get("element_id", ""))).strip(),
                source_file=str(meta.get("observed_symbol_file", meta.get("source_file", ""))).strip(),
                element_tag=str(meta.get("element_tag", "")).strip(),
                element_id=str(meta.get("observed_subject", meta.get("element_id", ""))).strip(),
            )
        usage = str(meta.get("suggested_usage", "")).strip()
        if usage not in SYMBOL_USAGE_VALUES:
            usage = infer_symbol_usage(
                role=role,
                source_file=str(meta.get("observed_symbol_file", meta.get("source_file", ""))).strip(),
                element_tag=str(meta.get("element_tag", "")).strip(),
            )
        scope = str(meta.get("suggested_scope", "ANY")).strip().upper() or "ANY"
        if scope not in {"ANY", "SMART", "NORMAL"}:
            scope = "ANY"
        return {
            "uid": "discovery-" + uuid4().hex,
            "candidate_only": True,
            "scope": scope,
            "role": role or "待分类图元",
            "device_type": role or "待分类图元",
            "device_subtype": "",
            "device_level": default_device_level(usage),
            "symbol_usage": usage,
            "element_tag": str(meta.get("element_tag", "")).strip(),
            "standard_devref": "",
            "match_attr": "devref",
            "match_value": observed_devref,
            "observed_devref": observed_devref,
            "observed_count": max(0, int(meta.get("count", 0) or 0)),
            "observed_files": [str(item) for item in meta.get("files", []) if str(item).strip()] if isinstance(meta.get("files", []), list) else [],
            "observed_examples": [dict(item) for item in meta.get("sample_positions", []) if isinstance(item, dict)] if isinstance(meta.get("sample_positions", []), list) else [],
            "sample_names": [str(item) for item in meta.get("sample_names", []) if str(item).strip()] if isinstance(meta.get("sample_names", []), list) else [],
            "observed_symbol_file": str(meta.get("observed_symbol_file", "")).strip(),
            "observed_subject": str(meta.get("observed_subject", "")).strip(),
            "suggested_usage": usage,
            "suggested_scope": scope,
            "suggested_device_type": role,
        }

    def _apply_discovery_to_rows(self) -> None:
        """Merge business-G discovery into generic rows only.

        v2.18.105 deliberately has no privileged/system device slots.  Every
        observed ``XML + devref`` is represented as the same kind of candidate row;
        the user then chooses which candidates to promote by uploading the real
        authoritative symbol G.
        """
        represented: set[str] = set()
        row_by_ref: dict[str, int] = {}
        for row in self._custom_standard_rows():
            marker = self.standard_table.item(row, 0)
            if marker is None:
                continue
            observed = str(marker.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
            standard = self._standard_file_devref(row)
            for value in (observed, standard):
                if value:
                    represented.add(value)
                    row_by_ref.setdefault(value, row)

        for observed_devref, meta in sorted(
            self._graphic_discovery_catalog.items(),
            key=lambda item: (-int(item[1].get("count", 0) or 0), item[0].casefold()),
        ):
            if self._discovery_decisions.get(observed_devref, "").strip().lower() == "ignored":
                continue
            meta = dict(meta)
            meta.setdefault("observed_devref", observed_devref)
            existing_row = row_by_ref.get(observed_devref)
            if existing_row is not None:
                count = max(0, int(meta.get("count", 0) or 0))
                files = [str(item) for item in meta.get("files", []) if str(item).strip()] if isinstance(meta.get("files", []), list) else []
                examples = [dict(item) for item in meta.get("sample_positions", []) if isinstance(item, dict)] if isinstance(meta.get("sample_positions", []), list) else []
                marker = self.standard_table.item(existing_row, 0)
                if marker is not None:
                    marker.setData(Qt.ItemDataRole.UserRole + 4, observed_devref)
                    marker.setData(Qt.ItemDataRole.UserRole + 5, count)
                    marker.setData(Qt.ItemDataRole.UserRole + 6, files)
                    marker.setData(Qt.ItemDataRole.UserRole + 7, examples)
                symbol_file = str(meta.get("observed_symbol_file", "")).strip() or self._observed_symbol_g_filename(observed_devref)
                self.standard_table.item(existing_row, 13).setText(symbol_file or "-")
                self.standard_table.item(existing_row, 14).setText(observed_devref)
                self.standard_table.item(existing_row, 15).setText(str(count))
                self.standard_table.item(existing_row, 16).setText(self._discovery_example_text(examples, files) or "-")
                tip = self._discovery_tooltip(meta, observed_devref, count, files, examples)
                for column in (13, 14, 15, 16):
                    self.standard_table.item(existing_row, column).setToolTip(tip)
                self._refresh_custom_standard_row(existing_row)
                continue

            if observed_devref in represented:
                continue
            new_row = self._insert_custom_standard_row(self._discovery_entry(meta))
            row_by_ref[observed_devref] = new_row
            represented.add(observed_devref)

        self._apply_standard_table_filter()
        self._fit_standard_table_columns()

    def _apply_standard_table_filter(self, *_args) -> None:
        query = self.discovery_filter.text().strip().casefold() if hasattr(self, "discovery_filter") else ""
        pending_only = bool(self.pending_only_checkbox.isChecked()) if hasattr(self, "pending_only_checkbox") else False
        for row in range(self.standard_table.rowCount()):
            marker = self.standard_table.item(row, 0)
            is_candidate = bool(
                row >= len(self._standard_specs)
                and marker is not None
                and marker.data(Qt.ItemDataRole.UserRole) == "custom"
                and bool(marker.data(Qt.ItemDataRole.UserRole + 3))
                and not self._standard_file_devref(row)
            )
            if pending_only and not is_candidate:
                self.standard_table.setRowHidden(row, True)
                continue
            if query:
                values: list[str] = []
                for column in range(self.standard_table.columnCount()):
                    item = self.standard_table.item(row, column)
                    if item is not None:
                        values.append(item.text())
                    widget = self.standard_table.cellWidget(row, column)
                    if isinstance(widget, WheelSafeComboBox):
                        values.append(widget.currentText())
                haystack = " ".join(values).casefold()
                self.standard_table.setRowHidden(row, query not in haystack)
            else:
                self.standard_table.setRowHidden(row, False)
        self._refresh_standard_table_overview()

    def _refresh_global_connection_settings(self) -> None:
        """Refresh shared environment paths without allowing this business page to edit them."""
        root = self.user_settings.get_value(
            "site_profile/remote_symbol_library_root", DEFAULT_REMOTE_SYMBOL_ROOT
        ).strip() or DEFAULT_REMOTE_SYMBOL_ROOT
        self.server_symbol_root.setText(root)
        if hasattr(self, "discovery_source"):
            self.discovery_source.remote.refresh_shared_settings()

    def _persist_server_library_settings(self) -> None:
        self.user_settings.set_value(
            "site_profile/remote_symbol_library_enabled",
            "true" if self.server_standard_enabled.isChecked() else "false",
        )
        # The root path is a global environment setting and is intentionally not
        # editable/persisted from this business page.
        self._refresh_global_connection_settings()

    def _server_library_enabled_changed(self, enabled: bool) -> None:
        self._persist_server_library_settings()
        self.server_symbol_root.setEnabled(bool(enabled))
        self.server_sync_button.setEnabled(bool(enabled) and self._server_sync_worker is None and self._scan_worker is None)
        if not enabled:
            self._server_library_timer.stop()
            self.server_library_status.setText("服务器图元库自动匹配已关闭；仍可使用人工上传标准 G。")
        elif self.isVisible():
            self._server_library_timer.start()
            QTimer.singleShot(250, lambda: self._start_server_symbol_sync(background=True, auto_bind=True))

    def _server_library_config(self) -> dict[str, object]:
        # Reuse the application's shared SSH credentials. The symbol library only
        # has its own root directory; credentials stay centralized in the SSH widget.
        cfg = dict(self.discovery_source.remote.config())
        cfg["root"] = self.server_symbol_root.text().strip() or DEFAULT_REMOTE_SYMBOL_ROOT
        return cfg

    def _expected_server_symbol_names(self) -> list[str]:
        names: set[str] = set()
        if hasattr(self, "standard_table"):
            for row in range(self.standard_table.rowCount()):
                item = self.standard_table.item(row, 13)
                name = Path(item.text().strip()).name if item is not None else ""
                if name and name != "-":
                    names.add(name)
        profile = self._current_active_profile() if hasattr(self, "profile_selector") else None
        if profile is not None:
            for raw in profile.managed_standard_files:
                row = dict(raw)
                name = Path(str(row.get("original_name", "")).strip()).name
                if name and str(row.get("standard_source", "manual")).strip().lower() == "server":
                    names.add(name)
        return sorted(names, key=str.casefold)

    def _open_server_symbol_cache(self) -> None:
        try:
            cfg = self._server_library_config()
            directory = RemoteSymbolLibraryService().library_dir(str(cfg["host"]), str(cfg["root"]))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
        except Exception as exc:
            QMessageBox.warning(self, "打开缓存失败", str(exc))

    def _server_profile_changed_names(self, payload: dict[str, object]) -> set[str]:
        changed = {str(item) for item in payload.get("changed_names", []) if str(item).strip()} if isinstance(payload.get("changed_names", []), list) else set()
        matched = payload.get("matched_records", {})
        if not isinstance(matched, dict):
            return changed
        profile = self._current_active_profile()
        if profile is None:
            return changed
        current_by_name = {
            Path(str(row.get("original_name", "")).strip()).name.casefold(): dict(row)
            for row in profile.managed_standard_files
            if Path(str(row.get("original_name", "")).strip()).name
        }
        for name, raw in matched.items():
            if not isinstance(raw, dict):
                continue
            current = current_by_name.get(Path(str(name)).name.casefold())
            if current is None:
                continue
            old_hash = str(current.get("sha256", "")).strip().lower()
            new_hash = str(raw.get("sha256", "")).strip().lower()
            if old_hash and new_hash and old_hash != new_hash:
                changed.add(Path(str(name)).name)
        return changed

    def _apply_server_library_payload(self, payload: dict[str, object], *, auto_bind: bool) -> None:
        self._last_server_sync_payload = dict(payload)
        matched_raw = payload.get("matched_records", {})
        matched = {
            Path(str(name)).name.casefold(): dict(record)
            for name, record in matched_raw.items()
            if isinstance(record, dict)
        } if isinstance(matched_raw, dict) else {}
        conflicts = payload.get("conflicts", {}) if isinstance(payload.get("conflicts", {}), dict) else {}
        errors = payload.get("errors", {}) if isinstance(payload.get("errors", {}), dict) else {}
        conflict_keys = {Path(str(name)).name.casefold() for name in conflicts}
        error_keys = {Path(str(name)).name.casefold() for name in errors}
        unmatched = [str(item) for item in payload.get("unmatched_names", []) if str(item).strip()] if isinstance(payload.get("unmatched_names", []), list) else []
        changed = self._server_profile_changed_names(payload)
        # Persist the comparison result in the last payload so the explicit
        # "create next version" action can use exactly the same server snapshot
        # the operator has just reviewed.
        self._last_server_sync_payload["profile_changed_names"] = sorted(changed, key=str.casefold)
        profile = self._current_active_profile()
        # A fresh-rescan DRAFT is a new local working copy, not an edit of the
        # locked base version.  Therefore server GET/cache results may bind into
        # the draft while the saved locked ACTIVE remains byte-for-byte untouched.
        locked = bool(profile.locked) if profile is not None and not self._rescan_draft_mode else False

        if hasattr(self, "server_new_version_button"):
            has_server_replacements = bool(
                locked
                and changed
                and any(
                    Path(str(name)).name.casefold() in {item.casefold() for item in changed}
                    and isinstance(record, dict)
                    for name, record in (matched_raw.items() if isinstance(matched_raw, dict) else [])
                )
            )
            self.server_new_version_button.setVisible(has_server_replacements)
            self.server_new_version_button.setEnabled(has_server_replacements and self._server_sync_worker is None and self._scan_worker is None and not self._task_busy)

        bound = 0
        if auto_bind and not locked and matched:
            # A deliberate manual upload wins until the user explicitly removes it.
            # Exclude those filenames before pending server records are merged, so a
            # same-devref server record cannot silently replace manual metadata.
            protected_manual_names: set[str] = set()
            for existing_row in self._custom_standard_rows():
                current_devref = self._standard_file_devref(existing_row)
                if not current_devref:
                    continue
                current_meta = self._symbol_meta(current_devref)
                current_source = str(current_meta.get("standard_source", "manual") or "manual").strip().lower()
                if current_source != "server":
                    observed_item = self.standard_table.item(existing_row, 13)
                    expected_name = Path(observed_item.text().strip()).name if observed_item is not None else ""
                    if expected_name and expected_name != "-":
                        protected_manual_names.add(expected_name.casefold())

            effective_matched = {key: row for key, row in matched.items() if key not in protected_manual_names}
            # Replace pending server records by filename first. This handles a remote
            # update whose body ID/devref changed while the authoritative filename
            # remained stable.
            incoming_names = {Path(str(row.get("original_name", "")).strip()).name.casefold() for row in effective_matched.values()}
            retained = [
                dict(row) for row in self._pending_standard_file_records
                if Path(str(row.get("original_name", "")).strip()).name.casefold() not in incoming_names
            ]
            retained.extend(dict(row) for row in effective_matched.values())
            self._pending_standard_file_records = retained
            self._symbol_catalog = self._catalog_from_standard_records(self._editor_standard_records())

            for row in self._custom_standard_rows():
                observed_item = self.standard_table.item(row, 13)
                expected_name = Path(observed_item.text().strip()).name if observed_item is not None else ""
                key = expected_name.casefold()
                if not key or key in conflict_keys or key in error_keys or key not in effective_matched:
                    continue
                current_devref = self._standard_file_devref(row)
                current_meta = self._symbol_meta(current_devref) if current_devref else {}
                current_source = str(current_meta.get("standard_source", "manual") or "manual").strip().lower()
                if current_devref and current_source != "server":
                    continue
                record = effective_matched[key]
                devref = str(record.get("devref", "")).strip()
                if not devref:
                    continue
                self._set_standard_file_cell(row, devref)
                tag_item = self.standard_table.item(row, 2)
                if tag_item is not None and not tag_item.text().strip():
                    tag_item.setText(str(record.get("element_tag", "")).strip())
                self._refresh_custom_standard_row(row)
                bound += 1

        remote_total = int(payload.get("scanned_remote_files", 0) or 0)
        downloaded = int(payload.get("downloaded", 0) or 0)
        reused = int(payload.get("reused", 0) or 0)
        checked_at = str(payload.get("checked_at", "")).strip()
        parts = [
            f"服务器图元库已检查：远程 {remote_total} 个 .g",
            f"精确匹配 {len(matched)}",
            f"缓存复用 {reused}",
            f"本次下载 {downloaded}",
        ]
        if bound:
            parts.append(f"自动绑定 {bound}")
        if unmatched:
            parts.append(f"未找到 {len(unmatched)}")
        if conflicts:
            parts.append(f"同名冲突 {len(conflicts)}")
        if errors:
            parts.append(f"读取/解析失败 {len(errors)}")
        if changed:
            parts.append(f"服务器变化 {len(changed)}")
        if checked_at:
            parts.append(f"检查时间 {checked_at}")
        text = " | ".join(parts)
        if locked and changed:
            text += "。当前 ACTIVE 已锁定：新文件只更新本地缓存并提示变化，不会修改已锁定标准。可点击“基于当前版本创建新版本”生成新的未锁定 ACTIVE 版本。"
        elif changed and not locked:
            text += "。服务器新版本已拉取到编辑区；保存当前标准时会按现有版本机制创建新的 ACTIVE 版本。"
        elif conflicts:
            text += "。同名但内容不同的服务器 G 不会自动选择，请人工确认。"
        elif errors:
            text += "。部分服务器 G 无法安全下载或解析，不会自动绑定；请查看执行日志并在需要时使用人工上传兜底。"
        elif unmatched:
            text += "。服务器未找到的候选仍可使用“为选中图元上传 / 更新标准 G”人工补充。"
        self.server_library_status.setText(text)
        self._fit_standard_table_columns()
        self._update_action_state()

    def _create_next_version_from_server(self) -> None:
        """Create an unlocked ACTIVE version from changed server-cached symbols.

        This is intentionally explicit for a locked standard. The locked ACTIVE
        snapshot is kept intact in history; only the new V(N+1) receives the
        changed authoritative server files already cached by the last sync.
        """
        profile = self._current_active_profile()
        if profile is None or not profile.locked:
            QMessageBox.information(
                self,
                "无需创建新版本",
                "只有当前 ACTIVE 标准已锁定，并且服务器图元库检测到标准文件变化时，才需要使用此操作。",
            )
            return

        payload = dict(self._last_server_sync_payload)
        matched_raw = payload.get("matched_records", {})
        if not isinstance(matched_raw, dict):
            matched_raw = {}
        changed_raw = payload.get("profile_changed_names", [])
        if isinstance(changed_raw, list):
            changed = {Path(str(item)).name.casefold() for item in changed_raw if Path(str(item)).name}
        else:
            changed = {item.casefold() for item in self._server_profile_changed_names(payload)}

        replacements: list[dict[str, object]] = []
        display_names: list[str] = []
        for name, record in matched_raw.items():
            basename = Path(str(name)).name
            if basename and basename.casefold() in changed and isinstance(record, dict):
                replacements.append(dict(record))
                display_names.append(basename)
        if not replacements:
            QMessageBox.information(
                self,
                "没有可应用的服务器更新",
                "当前缓存快照中没有检测到与已锁定标准内容不同、且可安全精确匹配的服务器图元。请先点击“检查 / 同步服务器图元库”。",
            )
            return

        next_version = int(profile.profile_version) + 1
        preview = "\n".join(f"• {name}" for name in sorted(set(display_names), key=str.casefold)[:12])
        extra = max(0, len(set(display_names)) - 12)
        if extra:
            preview += f"\n• ……另外 {extra} 项"
        if QMessageBox.question(
            self,
            "基于服务器更新创建新版本",
            f"当前 {profile.profile_name} V{profile.profile_version} 已锁定。\n\n"
            f"将保留 V{profile.profile_version} 的锁定内容不变，并创建新的 ACTIVE V{next_version}（未锁定），"
            "把下面这些服务器图元更新应用到新版本。全局执行版本不会自动切换：\n\n"
            f"{preview}\n\n继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        try:
            saved = self.service.create_next_version_from_server_records(profile.profile_name, replacements)
        except ValueError as exc:
            QMessageBox.warning(self, "创建新版本失败", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "创建新版本失败", str(exc))
            return

        self._pending_standard_file_records = []
        self._reload_profiles(saved.profile_name, saved.profile_version)
        self.activeProfileChanged.emit(saved.profile_name)
        self.server_new_version_button.setVisible(False)
        self.server_new_version_button.setEnabled(False)
        QMessageBox.information(
            self,
            "新标准版本已创建",
            f"已保留原锁定 V{profile.profile_version}，并创建 ACTIVE V{saved.profile_version}（未锁定）。\n"
            "服务器更新已写入新版本；全局执行版本保持原选择。确认后如需启用新版本，请点击“设为全局版本”。",
        )

    def _start_server_symbol_sync(self, *, background: bool, auto_bind: bool) -> None:
        if not hasattr(self, "server_standard_enabled") or not self.server_standard_enabled.isChecked():
            return
        if self._server_sync_worker is not None or self._scan_worker is not None or self._task_busy:
            return
        expected = self._expected_server_symbol_names()
        if not expected:
            if not background:
                self.server_library_status.setText("当前还没有可匹配的图元文件名。请先扫描业务 G，或选择一个已有服务器标准版本。")
            return
        try:
            self._persist_server_library_settings()
            cfg = self._server_library_config()
        except Exception as exc:
            if not background:
                QMessageBox.warning(self, "服务器图元库配置无效", str(exc))
            return

        self.server_library_progress.setRange(0, 0)
        self.server_library_progress.setVisible(not background)
        if not background:
            self.server_library_status.setText("正在后台递归检查服务器图元库并增量同步匹配文件……界面仍可操作。")

        def run_sync(log, progress):
            service = RemoteSymbolLibraryService()
            result = service.sync_expected(
                host=str(cfg["host"]),
                port=int(cfg["port"]),
                username=str(cfg["username"]),
                password=str(cfg["password"]),
                root=str(cfg["root"]),
                expected_names=expected,
                log=log,
                progress=progress,
            )
            return result.to_payload()

        worker = FunctionWorker(run_sync)
        self._server_sync_worker = worker
        worker.signals.progress.connect(self._on_server_sync_progress)
        worker.signals.result.connect(lambda result, a=auto_bind: self._on_server_sync_result(result, auto_bind=a))
        worker.signals.error.connect(lambda details, b=background: self._on_server_sync_error(details, background=b))
        worker.signals.finished.connect(self._on_server_sync_finished)
        self._update_action_state()
        QTimer.singleShot(0, lambda w=worker: self._scan_pool.start(w))

    def _on_server_sync_progress(self, value: int) -> None:
        if self.server_library_progress.maximum() == 0:
            self.server_library_progress.setRange(0, 100)
        self.server_library_progress.setValue(max(0, min(100, int(value))))

    def _on_server_sync_result(self, result: object, *, auto_bind: bool) -> None:
        payload = dict(result) if isinstance(result, dict) else {}
        self.server_library_progress.setRange(0, 100)
        self.server_library_progress.setValue(100)
        self._apply_server_library_payload(payload, auto_bind=auto_bind)

    def _on_server_sync_error(self, details: str, *, background: bool) -> None:
        message = str(details).split("\n\n---TRACEBACK---", 1)[0].strip()
        self.server_library_status.setText(f"服务器图元库检查失败：{message or details}")
        if not background:
            QMessageBox.warning(self, "服务器图元库同步失败", message or str(details))

    def _on_server_sync_finished(self) -> None:
        self._server_sync_worker = None
        if self.server_library_progress.maximum() == 0:
            self.server_library_progress.setRange(0, 100)
        self._update_action_state()
        QTimer.singleShot(500, lambda: self.server_library_progress.setVisible(False) if self._server_sync_worker is None else None)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API naming
        self._refresh_global_connection_settings()
        super().showEvent(event)
        if hasattr(self, "server_standard_enabled") and self.server_standard_enabled.isChecked():
            self._server_library_timer.start()
            QTimer.singleShot(800, lambda: self._start_server_symbol_sync(background=True, auto_bind=True))

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API naming
        if hasattr(self, "_server_library_timer"):
            self._server_library_timer.stop()
        super().hideEvent(event)

    @staticmethod
    def _profile_observed_refs(profile: SiteSmartProfile | None) -> set[str]:
        if profile is None:
            return set()
        decisions = {str(key): str(value).strip().lower() for key, value in profile.discovery_decisions.items()}
        return {
            str(key).strip()
            for key in profile.discovery_catalog
            if str(key).strip() and decisions.get(str(key), "") != "ignored"
        }

    def _reset_fresh_rescan_state(self) -> None:
        self._rescan_prepare_mode = False
        self._rescan_draft_mode = False
        self._rescan_draft_base_name = ""
        self._rescan_draft_base_version = None
        self._rescan_draft_target_version = None
        if hasattr(self, "cancel_rescan_draft_button"):
            self.cancel_rescan_draft_button.setVisible(False)
        if hasattr(self, "rescan_version_hint"):
            self.rescan_version_hint.setText(
                "普通扫描更新当前候选；全量重扫创建下一版本草稿。"
            )

    def _prepare_fresh_rescan_version(self) -> None:
        """Arm or start a full business-G rescan for the next local standard version."""
        if self._scan_worker is not None or self._server_sync_worker is not None or self._task_busy:
            return
        name, version, active = self._selected_profile_key()
        if not name or version is None or not active:
            QMessageBox.information(
                self, "请选择当前 ACTIVE 标准",
                "重新扫描创建新版本需要以当前 ACTIVE 标准为基准。历史版本仍可查看/恢复，但不会直接作为重新扫描分支。",
            )
            return
        current = self.service.load_profiles().get(name)
        if current is None:
            return

        if self._rescan_prepare_mode:
            # Second click is a convenience start action after the operator has
            # selected the fresh business-G set in the now-visible input panel.
            self._scan_graphic_symbol_candidates()
            return

        if QMessageBox.question(
            self,
            "全量重新扫描 → 新版本草稿",
            f"将以 {name} V{current.profile_version} 为比较基准，重新读取你接下来选择的业务 G。\n\n"
            f"扫描结果会进入 V{current.profile_version + 1} DRAFT：\n"
            "- 本次扫描结果是新草稿的候选来源；本次已不出现的旧候选不会自动带入；\n"
            "- 仍存在的旧图元会尽量继承人工分类和已验证的标准 G 绑定；\n"
            "- 新出现的图元会自动加入并优先从只读服务器图元库匹配；\n"
            "- 当前 ACTIVE / LOCKED / GLOBAL 都不会因扫描而改变；只有点击“保存为新版本”才生成新的 ACTIVE；\n"
            "- GLOBAL 仍需你之后手动选择。\n\n继续进入重新扫描模式吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) != QMessageBox.StandardButton.Yes:
            return

        self._rescan_prepare_mode = True
        self._rescan_draft_mode = False
        self._rescan_draft_base_name = name
        self._rescan_draft_base_version = int(current.profile_version)
        self._rescan_draft_target_version = int(current.profile_version) + 1
        self._set_discovery_input_visible(True)
        self.rescan_version_hint.setText(
            f"已进入 V{self._rescan_draft_target_version} 全量重新扫描模式。本次所选业务 G 将作为新草稿候选集合的唯一来源；"
            "旧版中本次未扫描到的候选不会自动带入。"
        )
        self.profile_status.setText(
            f"准备创建 V{self._rescan_draft_target_version} DRAFT：正在使用当前勾选的业务 G 全量重新扫描；"
            f"基准为 V{self._rescan_draft_base_version}，全局执行版本保持不变。"
        )
        self._update_action_state()
        # v2.18.119: one click now both arms the isolated next-version workflow
        # and starts the scan using the G files already selected by the operator.
        # If nothing is selected, the existing scan validation shows the warning and
        # leaves prepare mode armed so the operator can select files and retry.
        QTimer.singleShot(0, self._scan_graphic_symbol_candidates)

    def _cancel_fresh_rescan_draft(self) -> None:
        if not (self._rescan_prepare_mode or self._rescan_draft_mode):
            return
        base_name = self._rescan_draft_base_name
        base_version = self._rescan_draft_base_version
        if self._rescan_draft_mode and QMessageBox.question(
            self,
            "取消新版本草稿",
            "当前重新扫描草稿中的分类、绑定和修改尚未保存。确认放弃并返回已保存版本吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._reset_fresh_rescan_state()
        if base_name and base_version is not None:
            self._reload_profiles(base_name, base_version)
        else:
            self._update_action_state()

    def _collect_draft_rows_for_inheritance(self) -> list[dict[str, object]]:
        """Collect every visible draft row, including still-pending discovery rows."""
        configured = self._collect_custom_symbols()
        by_observed = {
            str(row.get("observed_devref", row.get("match_value", ""))).strip().casefold(): dict(row)
            for row in configured
            if str(row.get("observed_devref", row.get("match_value", ""))).strip()
        }
        rows = list(configured)
        for row_index in self._custom_standard_rows():
            marker = self.standard_table.item(row_index, 0)
            if marker is None:
                continue
            observed = str(marker.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
            if not observed or observed.casefold() in by_observed:
                continue
            scope_combo = self.standard_table.cellWidget(row_index, 0)
            usage_combo = self.standard_table.cellWidget(row_index, 10)
            level_combo = self.standard_table.cellWidget(row_index, 12)
            meta = dict(self._graphic_discovery_catalog.get(observed, {}))
            meta.setdefault("observed_devref", observed)
            entry = self._discovery_entry(meta)
            if isinstance(scope_combo, WheelSafeComboBox):
                entry["scope"] = scope_combo.currentText().strip().upper() or "ANY"
            role_item = self.standard_table.item(row_index, 1)
            tag_item = self.standard_table.item(row_index, 2)
            subtype_item = self.standard_table.item(row_index, 11)
            if role_item is not None:
                entry["role"] = entry["device_type"] = role_item.text().strip()
            if tag_item is not None:
                entry["element_tag"] = tag_item.text().strip()
            if subtype_item is not None:
                entry["device_subtype"] = subtype_item.text().strip()
            if isinstance(usage_combo, WheelSafeComboBox):
                entry["symbol_usage"] = usage_combo.currentText().strip()
            if isinstance(level_combo, WheelSafeComboBox):
                entry["device_level"] = level_combo.currentText().strip()
            rows.append(entry)
        return rows

    def _enter_fresh_rescan_draft(self, catalog: dict[str, dict[str, object]]) -> None:
        """Replace the editor with a scan-source-of-truth V(N+1) draft."""
        base = self.service.get_profile_version(
            self._rescan_draft_base_name, self._rescan_draft_base_version
        )
        if base is None:
            # The selected base disappeared unexpectedly; keep the scan visible as a
            # normal discovery result rather than risking a write to the wrong profile.
            self._rescan_prepare_mode = False
            self._rescan_draft_mode = False
            self._discovery_decisions = {}
            self._load_custom_symbols([])
            self._apply_discovery_to_rows()
            return

        was_draft = bool(self._rescan_draft_mode)
        base_rows = self._collect_draft_rows_for_inheritance() if was_draft else self._profile_standard_rows(base)
        by_observed: dict[str, dict[str, object]] = {}
        by_filename: dict[str, dict[str, object]] = {}
        for raw in base_rows:
            row = dict(raw)
            observed = str(row.get("observed_devref", row.get("match_value", ""))).strip()
            if observed:
                by_observed.setdefault(observed.casefold(), row)
            filename = Path(str(row.get("observed_symbol_file", row.get("source_file", ""))).strip()).name
            if filename:
                by_filename.setdefault(filename.casefold(), row)

        draft_rows: list[dict[str, object]] = []
        inherited = 0
        for observed_devref, meta_raw in sorted(
            catalog.items(), key=lambda item: (-int(item[1].get("count", 0) or 0), item[0].casefold())
        ):
            meta = dict(meta_raw)
            symbol_file = Path(str(meta.get("observed_symbol_file", "")).strip()).name
            prior = by_observed.get(observed_devref.casefold())
            if prior is None and symbol_file:
                prior = by_filename.get(symbol_file.casefold())
            if prior is None:
                draft_rows.append(self._discovery_entry(meta))
                continue
            row = dict(prior)
            row["candidate_only"] = not bool(str(row.get("standard_devref", "")).strip())
            row["observed_devref"] = observed_devref
            row["match_attr"] = "devref"
            row["match_value"] = observed_devref
            row["observed_symbol_file"] = str(meta.get("observed_symbol_file", "")).strip()
            row["observed_count"] = max(0, int(meta.get("count", 0) or 0))
            row["observed_files"] = [str(item) for item in meta.get("files", []) if str(item).strip()] if isinstance(meta.get("files", []), list) else []
            row["observed_examples"] = [dict(item) for item in meta.get("sample_positions", []) if isinstance(item, dict)] if isinstance(meta.get("sample_positions", []), list) else []
            row["sample_names"] = [str(item) for item in meta.get("sample_names", []) if str(item).strip()] if isinstance(meta.get("sample_names", []), list) else []
            draft_rows.append(row)
            inherited += 1

        self._rescan_prepare_mode = False
        self._rescan_draft_mode = True
        self._discovery_decisions = {}  # a fresh scan re-evaluates formerly ignored candidates
        self._graphic_discovery_catalog = {str(key): dict(value) for key, value in catalog.items()}
        if not was_draft:
            self._pending_standard_file_records = []
            self._symbol_catalog = self._catalog_from_standard_records([dict(row) for row in base.managed_standard_files])
        self._load_custom_symbols(draft_rows)
        self._apply_discovery_to_rows()
        self.site_name.setText(base.site_name)
        self.profile_name.setText(base.profile_name)
        self._set_editor_enabled(True)
        self._set_discovery_input_visible(True)
        global_text = self._global_profile_summary()
        self.current_profile_label.setText(global_text)
        self.active_profile_summary.setText(
            f"{global_text}（正在编辑 V{self._rescan_draft_target_version} DRAFT；基准 V{self._rescan_draft_base_version}）"
        )
        self.profile_status.setText(
            f"DRAFT · V{self._rescan_draft_target_version} · 来源：重新扫描业务 G · "
            f"已继承 {inherited} 个仍存在图元的分类/标准绑定；保存前不会修改任何已保存版本。"
        )
        self.rescan_version_hint.setText(
            f"当前为 V{self._rescan_draft_target_version} DRAFT。可继续重新扫描更新草稿、修改分类、删除候选或补标准；"
            "确认后点击“保存为新版本”。GLOBAL 不会自动切换。"
        )
        self._update_action_state()

    def _scan_graphic_symbol_candidates(self) -> None:
        """Discover business-G symbols and auto-resolve matching server standards in one worker."""
        if self._scan_worker is not None or self._server_sync_worker is not None:
            return

        input_mode = self.discovery_source.mode()
        remote_job: tuple[dict[str, object], list[object], Path] | None = None
        prepared_source: Path | None = None
        server_job: dict[str, object] | None = None

        # Snapshot only lightweight UI values. All SFTP work happens in FunctionWorker.
        if input_mode == InputMode.REMOTE_SSH:
            remote = self.discovery_source.remote
            selected_files = list(remote.selected_files())
            if not selected_files:
                QMessageBox.warning(self, "图形 G 图元发现输入", "请先在 SSH G 文件列表中选择一个或多个文件。")
                return
            try:
                remote.persist()
                remote_job = (dict(remote.config()), selected_files, remote._processing_snapshot_dir())
            except Exception as exc:
                QMessageBox.warning(self, "SSH 远程输入准备失败", str(exc))
                return
        else:
            if not validate_input_source(self, self.discovery_source, display_name="图形 G 图元发现输入"):
                return
            self.discovery_source.persist_current()
            prepared_source = self.discovery_source.path()

        if self.server_standard_enabled.isChecked():
            try:
                self._persist_server_library_settings()
                server_job = self._server_library_config()
            except Exception as exc:
                # Business discovery remains usable even when the optional server
                # library is temporarily unavailable/misconfigured.
                self.server_library_status.setText(f"服务器图元库配置无效，本次只扫描业务 G：{exc}")
                server_job = None

        if input_mode == InputMode.REMOTE_SSH:
            self.scan_progress.setRange(0, 0)
            self.scan_summary.setText("正在后台下载 SSH 只读业务 G 快照……随后自动解析图元并匹配服务器标准库。")
        else:
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setFormat("准备扫描图形 G %p%")
            self.scan_progress.setValue(1)
            self.scan_summary.setText("正在准备扫描……完成业务图元发现后会自动匹配服务器标准图元库。")
        self.scan_progress.setVisible(True)
        self._update_action_state()

        def run_discovery(log, progress):
            parse_end = 70 if server_job is not None else 100
            if remote_job is not None:
                cfg, selected, snapshot_dir = remote_job
                log(f"[SSH只读] 后台准备 {len(selected)} 个服务器 G 文件，本地快照：{snapshot_dir}")
                progress(2)
                download_stable_files(
                    host=str(cfg["host"]),
                    port=int(cfg["port"]),
                    username=str(cfg["username"]),
                    password=str(cfg["password"]),
                    selected_files=selected,
                    target_dir=snapshot_dir,
                    log=log,
                )
                progress(25)
                payload = discover_graphic_symbols(
                    snapshot_dir,
                    InputMode.DIRECTORY,
                    log=log,
                    progress=lambda value: progress(25 + round(int(value) * (parse_end - 25) / 100)),
                )
            else:
                assert prepared_source is not None
                progress(2)
                payload = discover_graphic_symbols(
                    prepared_source,
                    input_mode,
                    log=log,
                    progress=lambda value: progress(2 + round(int(value) * (parse_end - 2) / 100)),
                )

            if server_job is not None:
                expected_names = [
                    str(row.get("observed_symbol_file", "")).strip()
                    for row in payload.get("candidates", [])
                    if isinstance(row, dict) and str(row.get("observed_symbol_file", "")).strip()
                ]
                try:
                    service = RemoteSymbolLibraryService()
                    sync_result = service.sync_expected(
                        host=str(server_job["host"]),
                        port=int(server_job["port"]),
                        username=str(server_job["username"]),
                        password=str(server_job["password"]),
                        root=str(server_job["root"]),
                        expected_names=expected_names,
                        log=log,
                        progress=lambda value: progress(70 + round(int(value) * 30 / 100)),
                    )
                    payload["server_library"] = sync_result.to_payload()
                except Exception as exc:
                    log(f"[服务器图元库] 自动同步失败，但业务 G 发现结果保留：{exc}")
                    payload["server_library_error"] = str(exc)
                    progress(100)
            return payload

        # Create/connect the worker now so the scan button is disabled immediately,
        # but defer pool.start() one event-loop turn so Qt can paint the progress bar.
        worker = FunctionWorker(run_discovery)
        self._scan_worker = worker
        worker.signals.progress.connect(self._on_discovery_progress)
        worker.signals.result.connect(self._on_graphic_discovery_result)
        worker.signals.error.connect(self._on_scan_error)
        worker.signals.finished.connect(self._on_scan_finished)
        self._update_action_state()
        QTimer.singleShot(0, lambda w=worker: self._scan_pool.start(w))

    def _on_discovery_progress(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if self.discovery_source.mode() == InputMode.REMOTE_SSH and value < 25:
            if self.scan_progress.maximum() != 0:
                self.scan_progress.setRange(0, 0)
            return
        if self.scan_progress.maximum() == 0:
            self.scan_progress.setRange(0, 100)
        if self.server_standard_enabled.isChecked() and value >= 70:
            self.scan_progress.setFormat("匹配 / 同步服务器标准图元 %p%")
        else:
            self.scan_progress.setFormat("扫描图形 G 图元 %p%")
        self.scan_progress.setValue(value)

    def _on_graphic_discovery_result(self, result: object) -> None:
        payload = dict(result) if isinstance(result, dict) else {}
        candidates = payload.get("candidates", [])
        catalog: dict[str, dict[str, object]] = {}
        if isinstance(candidates, list):
            for raw in candidates:
                if not isinstance(raw, dict):
                    continue
                observed = str(raw.get("observed_devref", "")).strip()
                if not observed:
                    continue
                row = dict(raw)
                row["devref"] = observed
                row["element_id"] = str(raw.get("observed_subject", "")).strip()
                row["source_file"] = str(raw.get("observed_symbol_file", "")).strip()
                # Geometry fields in discovery metadata are deliberately zero/empty.
                # Business-G observed sizes remain under observed_sizes only.
                row["width"] = 0.0
                row["height"] = 0.0
                row["align_center"] = []
                row["pins"] = []
                catalog[observed] = row
        self._graphic_discovery_catalog = catalog

        fresh_rescan = bool(self._rescan_prepare_mode or self._rescan_draft_mode)
        if fresh_rescan:
            self._enter_fresh_rescan_draft(catalog)
        else:
            # Preserve current authoritative custom rows while rebuilding candidate rows.
            saved_rows = self._collect_custom_symbols()
            self._load_custom_symbols(saved_rows)
            self._apply_discovery_to_rows()

            name, _version, active = self._selected_profile_key()
            if name and active:
                updated = self.service.update_discovery_metadata(name, catalog=catalog)
                if updated is not None:
                    self._graphic_discovery_catalog = {str(key): dict(value) for key, value in updated.discovery_catalog.items()}
                    saved_rows = self._collect_custom_symbols()
                    self._load_custom_symbols(saved_rows)
                    self._apply_discovery_to_rows()

        server_payload = payload.get("server_library", {})
        if isinstance(server_payload, dict) and server_payload:
            self._apply_server_library_payload(server_payload, auto_bind=True)
        else:
            server_error = str(payload.get("server_library_error", "")).strip()
            if server_error:
                self.server_library_status.setText(
                    f"业务 G 扫描成功，但服务器图元库自动匹配失败：{server_error}。可稍后点击“检查 / 同步服务器图元库”重试。"
                )

        file_count = int(payload.get("file_count", 0) or 0)
        candidate_count = int(payload.get("candidate_count", 0) or 0)
        instance_count = int(payload.get("instance_count", 0) or 0)
        pending = sum(
            1 for row in self._custom_standard_rows()
            if (self.standard_table.item(row, 0) is not None
                and bool(self.standard_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 3))
                and not self._standard_file_devref(row))
        )
        self.scan_progress.setValue(100)
        matched_count = 0
        if isinstance(server_payload, dict):
            matched_records = server_payload.get("matched_records", {})
            matched_count = len(matched_records) if isinstance(matched_records, dict) else 0
        if self._rescan_draft_mode:
            base_profile = self.service.get_profile_version(self._rescan_draft_base_name, self._rescan_draft_base_version)
            old_refs = self._profile_observed_refs(base_profile) if base_profile is not None else set()
            new_refs = set(self._graphic_discovery_catalog)
            added = len(new_refs - old_refs)
            removed = len(old_refs - new_refs)
            retained = len(new_refs & old_refs)
            self.scan_summary.setText(
                f"V{self._rescan_draft_target_version or '?'} DRAFT 重新扫描完成：{file_count} 个文件，"
                f"发现 {candidate_count} 种 devref / {instance_count} 个图元实例；相对基准 V{self._rescan_draft_base_version or '?'}："
                f"新增 {added}、仍存在 {retained}、本次已不出现 {removed}；服务器自动匹配 {matched_count} 项，"
                f"仍待匹配/人工上传 {pending} 项。"
            )
        else:
            ignored_count = sum(
                1 for key in self._graphic_discovery_catalog
                if str(self._discovery_decisions.get(str(key), "")).strip().lower() == "ignored"
            )
            ignored_note = (
                f" 当前版本还保留 {ignored_count} 个“已忽略”候选决定，因此普通扫描不会把它们重新加入表格；"
                "如需让本次业务 G 重新决定新版本的候选集合，请点击“全量重新扫描 → 新版本草稿”。"
                if ignored_count else
                " 普通扫描只更新当前版本候选，不会自动创建下一版本；如需建立下一版本，请点击“全量重新扫描 → 新版本草稿”。"
            )
            self.scan_summary.setText(
                f"当前版本候选扫描完成：{file_count} 个文件，发现 {candidate_count} 种 devref / {instance_count} 个图元实例；"
                f"服务器自动匹配 {matched_count} 项，当前仍待匹配/人工上传 {pending} 项。" + ignored_note
            )
        warnings = payload.get("warnings", [])
        if self._rescan_draft_mode:
            warning_text = "；".join(str(item) for item in warnings[:3]) if isinstance(warnings, list) and warnings else ""
            self.profile_status.setText(
                f"DRAFT · V{self._rescan_draft_target_version or '?'} · 基准 V{self._rescan_draft_base_version or '?'} · "
                f"重新扫描结果尚未保存；可继续调整/补标准后点击“保存为新版本”。"
                + (f" 警告：{warning_text}" if warning_text else "")
            )
        elif isinstance(warnings, list) and warnings:
            self.profile_status.setText("；".join(str(item) for item in warnings[:3]))
        elif pending:
            self.profile_status.setText("候选已自动分类；服务器能精确找到同名图元时会自动拉取并读取标准属性，剩余候选再人工上传。")
        elif matched_count:
            self.profile_status.setText("候选已自动分类并从服务器图元库匹配标准 G；请确认分类后保存当前标准。")
        self._update_action_state()

    def _set_discovery_input_visible(self, visible: bool) -> None:
        """Show discovery source controls only while the selected ACTIVE version is unlocked."""
        visible = bool(visible)
        if hasattr(self, "discovery_input_panel"):
            self.discovery_input_panel.setVisible(visible)
        if hasattr(self, "discovery_locked_note"):
            self.discovery_locked_note.setVisible(not visible)

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.site_name.setReadOnly(not enabled)
        self.profile_name.setReadOnly(not enabled)
        for combo in (self.lbs_combo, self.breaker_combo, self.ground_combo, self.normal_lbs_combo, self.normal_breaker_combo, self.normal_ground_combo):
            combo.setEnabled(enabled)
        for row in self._custom_standard_rows():
            for column in (0, 10, 12):
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
        self._reset_fresh_rescan_state()
        if clear_selection and hasattr(self, "profile_selector"):
            self.profile_selector.blockSignals(True)
            self.profile_selector.setCurrentIndex(-1)
            self.profile_selector.blockSignals(False)
        self._selected_version = None
        self._selected_is_active = False
        self._candidate_counts.clear()
        self._symbol_catalog.clear()
        self._graphic_discovery_catalog.clear()
        self._discovery_decisions.clear()
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
        self.scan_summary.setText("尚未配置标准图元。")
        self.profile_status.setText("新建标准：填写适用范围 / 标准名称，扫描业务 G 后优先从服务器图元库自动匹配；未找到时再人工上传标准 G。")
        self.current_profile_label.setText("当前全局执行标准：未选择")
        self.active_profile_summary.setText("当前全局执行标准：尚未创建 Profile")
        self._last_scan = None
        self._set_editor_enabled(True)
        self._set_discovery_input_visible(True)
        if hasattr(self, "lock_standard_button"):
            self.lock_standard_button.setText("锁定当前版本")
            self.lock_standard_button.setEnabled(False)
        if hasattr(self, "server_new_version_button"):
            self.server_new_version_button.setVisible(False)
            self.server_new_version_button.setEnabled(False)
        self._last_server_sync_payload = {}
        self.restore_action.setEnabled(False)
        self.delete_action.setEnabled(False)
        self._update_action_state()

    def _global_profile_summary(self) -> str:
        name, version = self.service.get_global_profile_selection()
        profile = self.service.get_profile_version(name, version) if name and version is not None else None
        if profile is None:
            return "当前全局执行标准：尚未设置"
        lock_text = " · LOCKED" if profile.locked else ""
        return (
            f"当前全局执行标准：{profile.site_name} / {profile.profile_name} / "
            f"V{profile.profile_version} · GLOBAL{lock_text}"
        )

    def _set_selected_global_version(self) -> None:
        name, version, _active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择版本", "请先在“标准版本”下拉框中选择一个已保存版本。")
            return
        profile = self.service.get_profile_version(name, version)
        if profile is None:
            QMessageBox.warning(self, "版本不存在", f"未找到 {name} V{version}。")
            return
        ready, issues = self.service.validate_authoritative_standard(profile)
        if not ready:
            QMessageBox.warning(
                self, "版本不可执行",
                "该版本不能设为全局执行标准：\n" + "\n".join(f"- {item}" for item in issues[:8]),
            )
            return
        try:
            self.service.set_global_profile_version(name, version)
        except ValueError as exc:
            QMessageBox.warning(self, "设置失败", str(exc))
            return
        self._reload_profiles(name, version)
        self.activeProfileChanged.emit(name)
        QMessageBox.information(
            self, "全局版本已更新",
            f"已将 {profile.site_name} / {profile.profile_name} / V{profile.profile_version} 设为全局执行标准。\n"
            "后续模块会固定使用这个版本，直到你再次手动选择其他版本。",
        )

    def _set_version_switch_busy(self, busy: bool, *, name: str = "", version: int | None = None) -> None:
        """Show immediate checkout feedback for slower historical-version switches."""
        if not hasattr(self, "version_switch_status"):
            return
        self.version_switch_status.setVisible(bool(busy))
        self.version_switch_progress.setVisible(bool(busy))
        if busy:
            suffix = f" V{version}" if version is not None else ""
            self.version_switch_status.setText(
                f"正在切换标准版本：{name}{suffix}，正在从本地图元版本库加载冻结配置，请稍候……"
            )
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
        else:
            self.version_switch_status.clear()
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

    def _profile_selection_changed(self, *_args) -> None:
        # Selecting a saved version abandons any unsaved fresh-rescan DRAFT.
        if self._rescan_prepare_mode or self._rescan_draft_mode:
            self._reset_fresh_rescan_state()
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            return
        self._set_version_switch_busy(True, name=name, version=version)
        try:
            profile = self.service.get_profile_version(name, version)
            current = self.service.load_profiles().get(name)
            if profile is None or current is None:
                return
            self._selected_version = version
            self._selected_is_active = active
            self._pending_standard_file_records = []
            self._last_server_sync_payload = {}
            if hasattr(self, "server_new_version_button"):
                self.server_new_version_button.setVisible(False)
                self.server_new_version_button.setEnabled(False)
            records = [dict(row) for row in profile.managed_standard_files]
            self._symbol_catalog = self._catalog_from_standard_records(records)
            self._graphic_discovery_catalog = {str(key): dict(value) for key, value in profile.discovery_catalog.items()}
            self._discovery_decisions = {str(key): str(value) for key, value in profile.discovery_decisions.items()}
            display_rows = self._profile_standard_rows(profile)
            self._load_custom_symbols(display_rows)
            self._apply_discovery_to_rows()
            self.site_name.setText(profile.site_name)
            self.profile_name.setText(profile.profile_name)
            # Legacy fixed-role fields are intentionally not rendered as special rows.
            # _profile_standard_rows() converts them to ordinary generic definitions for
            # backward compatibility; saving the profile again completes the migration.
            for combo in (self.lbs_combo, self.breaker_combo, self.ground_combo, self.normal_lbs_combo, self.normal_breaker_combo, self.normal_ground_combo):
                combo.clear()
            configured = sum(
                1 for row in display_rows
                if bool(row.get("enabled", True)) and str(row.get("standard_devref", "")).strip()
            )
            ignored_count = sum(
                1 for devref in profile.discovery_catalog
                if str(profile.discovery_decisions.get(devref, "")).strip().lower() == "ignored"
            )
            active_discovery_count = max(0, len(profile.discovery_catalog) - ignored_count)
            ignored_text = f"，已忽略 {ignored_count} 种" if ignored_count else ""
            self.scan_summary.setText(
                f"标准文件 {len(profile.managed_standard_files)} 个；已定义标准图元 {configured} 项；"
                f"有效图形G发现候选 {active_discovery_count} 种{ignored_text}；标准指纹 {(profile.standard_fingerprint or '-')[:16]}。"
            )
            global_name, global_version = self.service.get_global_profile_selection()
            is_global = profile.profile_name == global_name and profile.profile_version == global_version
            if active:
                self.user_settings.set_value("site_profile/last_profile_name", profile.profile_name)
                ready_ok, ready_issues = self.service.validate_authoritative_standard(profile)
                fingerprint = (profile.standard_fingerprint or "-")[:16]
                lock_state = "LOCKED" if profile.locked else "UNLOCKED"
                global_state = " · GLOBAL" if is_global else ""
                self.profile_status.setText(
                    f"ACTIVE{global_state} · V{profile.profile_version} · {'READY' if ready_ok else 'NOT READY'} · {lock_state} · 标准指纹 {fingerprint} · 最后保存：{profile.updated_at or '-'}"
                )
                if not ready_ok:
                    self.scan_summary.setText("当前标准不可执行：" + "；".join(ready_issues[:3]))
            else:
                global_state = " · GLOBAL" if is_global else ""
                self.profile_status.setText(
                    f"ARCHIVED{global_state} · V{profile.profile_version} · {'LOCKED · ' if profile.locked else ''}历史版本只读。"
                    f"当前可编辑 ACTIVE 是 V{current.profile_version}；需要重新编辑时可选择“恢复为新的编辑版本”。"
                )
            global_text = self._global_profile_summary()
            self.current_profile_label.setText(global_text)
            self.active_profile_summary.setText(
                global_text + (f"（当前查看 V{profile.profile_version} {'ACTIVE' if active else '历史版本'}）" if not is_global else "")
            )
            self._last_scan = None
            editable = bool(active and not profile.locked)
            self._set_editor_enabled(editable)
            # Only a locked ACTIVE version hides the Graphic-G discovery input.
            # Archived versions keep the input area visible for context, but their scan
            # action stays disabled because they are view-only.
            self._set_discovery_input_visible(not bool(active and profile.locked))
            if hasattr(self, "lock_standard_button"):
                self.lock_standard_button.setText("解锁当前版本" if active and profile.locked else "锁定当前版本")
                self.lock_standard_button.setEnabled(bool(active and not self._task_busy))
            self.restore_action.setEnabled(bool(not active and not current.locked))
            global_name, global_version = self.service.get_global_profile_selection(auto_initialize=False)
            selected_is_global = profile.profile_name == global_name and profile.profile_version == global_version
            self.delete_history_action.setEnabled(bool(not active and not selected_is_global))
            self.delete_action.setEnabled(bool(active and not profile.locked))
            self._update_action_state()
            self._standard_row_selection_changed()
            if active and self.server_standard_enabled.isChecked():
                QTimer.singleShot(350, lambda: self._start_server_symbol_sync(background=True, auto_bind=True))
        finally:
            self._set_version_switch_busy(False)

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
        source_item = self.standard_table.item(row, 8) or self._set_readonly_cell(row, 8, "-")
        status_item = self.standard_table.item(row, 9) or self._set_readonly_cell(row, 9, "未上传")
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
        self._fit_standard_table_columns()


    def _scan_samples(self) -> None:
        """Upload one authoritative symbol G into the currently selected generic row."""
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
                "先选择图元候选",
                "请先扫描图形 G，并在表格中选中需要纳入标准管理的图元候选，然后上传对应的权威图元 G。"
                "一个图元 G 只绑定当前选中行。",
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

        scope_widget = self.standard_table.cellWidget(row, 0)
        scope = scope_widget.currentText().strip().upper() if isinstance(scope_widget, WheelSafeComboBox) else "ANY"
        role_label = (self.standard_table.item(row, 1).text() if self.standard_table.item(row, 1) else "").strip() or "待分类图元"
        expected_tag = (self.standard_table.item(row, 2).text() if self.standard_table.item(row, 2) else "").strip()
        role_display = f"{scope} / {role_label}"

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

        # v2.18.106: a discovered candidate can only be bound to the exact
        # symbol-G filename seen in the business/graphic G.  Check the selected
        # basename before parsing or adding anything to the pending standard set,
        # so a wrong-but-valid G can never be accidentally attached to this row.
        # Comparison is case-insensitive to match Windows filesystem semantics.
        # Manually-added rows without discovery evidence keep the existing flow.
        expected_symbol_file = ""
        observed_file_item = self.standard_table.item(row, 13)
        if observed_file_item is not None:
            expected_symbol_file = observed_file_item.text().strip()
        if not expected_symbol_file or expected_symbol_file == "-":
            marker = self.standard_table.item(row, 0)
            if marker is not None:
                observed_devref = str(marker.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
                expected_symbol_file = self._observed_symbol_g_filename(observed_devref)
        actual_symbol_file = path.name
        if expected_symbol_file and not self._same_symbol_g_filename(expected_symbol_file, actual_symbol_file):
            QMessageBox.warning(
                self,
                "禁止上传：图元文件名不匹配",
                "当前候选是从业务/图形 G 自动扫描出来的，上传的标准图元 G 必须与扫描图元文件名一致。\n\n"
                f"扫描检测到：{expected_symbol_file}\n"
                f"当前选择：{actual_symbol_file}\n\n"
                "请重新选择与“扫描图元 G 文件全名”完全对应的标准图元 G。",
            )
            return

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
        for custom_row in self._custom_standard_rows():
            self._refresh_custom_standard_row(custom_row)

        # Bind the uploaded authoritative symbol only to the selected learned row.
        # XML/devref discovery identifies the candidate; w×h, AlignCenter and Pins
        # come exclusively from this uploaded symbol G.
        if not expected_tag:
            tag_item = self.standard_table.item(row, 2)
            if tag_item is not None:
                tag_item.setText(actual_tag)
        self._set_standard_file_cell(row, devref)
        self._refresh_custom_standard_row(row)

        self._last_scan = None
        shared_text = "绑定当前图元定义"
        reference_note = (
            f" 上传 G 解析 XML={actual_tag or '-'}；当前行扫描 XML={expected_tag or '-'}。定位关系由扫描 XML/devref 与上传标准自动计算，无需人工指定。"
            if expected_tag and actual_tag and actual_tag != expected_tag else ""
        )
        self.scan_summary.setText(
            f"已将 {path.name} 作为 {role_display} 的权威标准图元，{shared_text}。"
            "保存后，只要该图元仍在标准表中，就会参与业务 G 的实例发现、统计与标准校验；设备类还会进入设备导出。" + reference_note
        )
        self.profile_status.setText(
            f"待保存：{role_display} → {devref}。devref、w/h、AlignCenter、pin/连接锚点均以这个上传 G 为准。"
        )
        self._update_action_state()

    def _on_scan_error(self, details: str) -> None:
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        message = str(details).split("\n\n---TRACEBACK---", 1)[0].strip()
        QMessageBox.critical(self, "扫描失败", message or str(details))

    def _on_scan_finished(self) -> None:
        self._scan_worker = None
        if self.scan_progress.maximum() == 0:
            self.scan_progress.setRange(0, 100)
        self._update_action_state()
        # Keep 100% visible very briefly so completion is perceptible; the bar is
        # already next to the scan button and appears immediately at scan start.
        QTimer.singleShot(450, lambda: self.scan_progress.setVisible(False) if self._scan_worker is None else None)

    def _save_profile(self) -> None:
        selected_name, selected_version, selected_active = self._selected_profile_key()
        selected_profile = self.service.load_profiles().get(selected_name) if selected_name and selected_active else None
        if selected_profile is not None and selected_profile.locked and not self._rescan_draft_mode:
            QMessageBox.information(
                self, "当前标准已锁定",
                f"{selected_name} V{selected_version} 已锁定，当前版本不能修改或保存。请先解锁；"
                "如需基于最新业务 G 建立下一版本，请使用“全量重新扫描 → 新版本草稿”。",
            )
            return
        site_name = self.site_name.text().strip()
        profile_name = self.profile_name.text().strip()
        # v2.18.105 no longer persists six special RMU role fields from the UI.
        # Every authoritative definition is a generic discovery-driven standard row.
        lbs = breaker = normal_lbs = normal_breaker = ground = normal_ground = ""
        custom_symbols = self._collect_custom_symbols()
        invalid_custom = [
            entry for entry in custom_symbols
            if not str(entry.get("element_tag", "")).strip() or not str(entry.get("standard_devref", "")).strip()
        ]
        if invalid_custom:
            QMessageBox.warning(self, "图元标准未完成", "已纳入标准管理的图元必须至少具备“XML 元素”和已上传的“标准图元 G”。请补充后再保存。")
            return
        if not site_name or not profile_name:
            QMessageBox.warning(self, "标准未完成", "适用范围和标准名称不能为空。")
            return
        if not custom_symbols:
            QMessageBox.warning(
                self, "标准未完成",
                "请先扫描图形 G 发现图元候选，并至少为 1 个需要管理的候选上传权威标准图元 G。",
            )
            return

        # v2.18.76: the saved standard is built only from user-uploaded icon G
        # files. Historical business-scan observations/confidence never participate
        # in a new authoritative Profile version.
        all_records = self._editor_standard_records()
        selected_devrefs = {
            str(entry.get("standard_devref", "")).strip()
            for entry in custom_symbols
            if str(entry.get("standard_devref", "")).strip()
        }
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
        lbs_candidates = {}
        breaker_candidates = {}
        normal_lbs_candidates = {}
        normal_breaker_candidates = {}
        ground_candidates = {}
        normal_ground_candidates = {}

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
            discovery_catalog=self._graphic_discovery_catalog,
            discovery_decisions=self._discovery_decisions,
        ).normalized()
        # Every required ACTIVE role must resolve to exactly one user-uploaded icon file.
        records_by_devref: dict[str, list[dict[str, object]]] = {}
        for row in candidate_profile.managed_standard_files:
            records_by_devref.setdefault(str(row.get("devref", "")).casefold(), []).append(row)
        role_errors: list[str] = []
        for entry in custom_symbols:
            if not bool(entry.get("enabled", True)):
                continue
            devref = str(entry.get("standard_devref", "")).strip()
            label = str(entry.get("role", "自定义图元")).strip() or "自定义图元"
            rows = records_by_devref.get(devref.casefold(), []) if devref else []
            if len(rows) != 1:
                role_errors.append(f"图元 {label}: 必须且只能绑定 1 个用户上传的标准图元 G。")
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
                changes.append("自定义图元")
            if old.symbol_catalog != candidate_profile.symbol_catalog:
                changes.append("图元属性目录")
            if QMessageBox.question(
                self,
                "更新图元标准",
                f"当前 ACTIVE 是 {profile_name} V{old.profile_version}。\n"
                f"检测到标准变化：{', '.join(changes) or '图元标准'}。\n\n"
                f"保存后将创建 V{old.profile_version + 1} 作为新的可编辑 ACTIVE；V{old.profile_version} 会保留为 ARCHIVED。\n"
                "全局执行版本不会自动切换；如要让其他模块使用新版本，请保存后选中它并点击“设为全局版本”。\n\n继续吗？",
            ) != QMessageBox.StandardButton.Yes:
                return

        try:
            if self._rescan_draft_mode:
                profile = self.service.save_as_next_version(candidate_profile)
            else:
                profile = self.service.upsert(candidate_profile)
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.user_settings.set_value("site_profile/last_profile_name", profile.profile_name)
        saved_from_fresh_rescan = bool(self._rescan_draft_mode)
        self._pending_standard_file_records = []
        self._reset_fresh_rescan_state()
        self._reload_profiles(profile.profile_name, profile.profile_version)
        self.activeProfileChanged.emit(profile.profile_name)
        global_name, global_version = self.service.get_global_profile_selection()
        global_note = (
            f"\n当前全局执行版本仍为 {global_name} V{global_version}。"
            if global_name and global_version is not None and (global_name != profile.profile_name or global_version != profile.profile_version)
            else "\n该版本当前也是全局执行版本。"
        )
        QMessageBox.information(
            self, "标准已保存",
            f"已保存 {profile.profile_name}（适用范围：{profile.site_name}）V{profile.profile_version}。"
            + ("\n该版本来自本次业务 G 全量重新扫描草稿；旧 ACTIVE 已保留为历史版本。" if saved_from_fresh_rescan else "")
            + global_note,
        )

    def _show_version_repository_details(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择版本", "请先在“标准版本”下拉框中选择一个已保存版本。")
            return
        try:
            details = self.service.version_repository_details(name, version)
            integrity = self.service.verify_version_repository(name, version)
        except ValueError as exc:
            QMessageBox.warning(self, "版本库读取失败", str(exc))
            return
        status = "完整" if integrity.ok else "完整性异常"
        fingerprint = str(details.get("repository_fingerprint", ""))
        QMessageBox.information(
            self,
            f"{name} V{version} · 图元版本库",
            f"状态：{'ACTIVE' if active else 'ARCHIVED'} / {status}\n"
            f"冻结图元：{details.get('entry_count', 0)} 个（服务器来源 {details.get('server_backed', 0)}，人工来源 {details.get('manual', 0)}）\n"
            f"已验证：{integrity.verified}/{integrity.total}\n"
            f"历史中发生过内容修订的相对路径：{details.get('paths_with_history', 0)}\n"
            f"版本库指纹：{fingerprint or '-'}\n\n"
            f"Manifest：{details.get('manifest_path', '-')}\n"
            f"本地对象库：{details.get('repository_root', '-')}\n\n"
            "历史版本完全依赖本地冻结对象；服务器当前同名文件不会覆盖或替代该版本。",
        )

    def _verify_selected_version_repository(self) -> None:
        name, version, _active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择版本", "请先选择需要验证的已保存版本。")
            return
        try:
            result = self.service.verify_version_repository(name, version)
        except ValueError as exc:
            QMessageBox.warning(self, "验证失败", str(exc))
            return
        if result.ok:
            QMessageBox.information(
                self,
                "版本完整性验证通过",
                f"{name} V{version}：{result.verified}/{result.total} 个冻结图元均存在，SHA256 与 w×h / AlignCenter / Pins 等解析属性一致。\n\n"
                "即使服务器上的旧图元已被覆盖或删除，该版本仍可离线恢复和导出。",
            )
            return
        issues = []
        issues.extend(f"缺失：{item}" for item in result.missing[:8])
        issues.extend(f"SHA256 不一致：{item}" for item in result.hash_mismatch[:8])
        issues.extend(f"解析属性不一致：{item}" for item in result.metadata_mismatch[:8])
        QMessageBox.warning(
            self,
            "版本完整性异常",
            f"{name} V{version} 仅验证通过 {result.verified}/{result.total}。\n" + "\n".join(issues[:16]) +
            "\n\n不会使用服务器当前同名文件自动补位；请从可信备份恢复对应 SHA256 的历史对象。",
        )

    def _export_selected_version_repository(self, *, zip_output: bool) -> None:
        name, version, _active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择版本", "请先选择需要导出的已保存版本。")
            return
        safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name).strip("._") or "standard"
        if zip_output:
            default_path = str(default_workspace() / f"{safe_name}_V{version}_element.zip")
            selected, _filter = QFileDialog.getSaveFileName(self, "导出完整 element ZIP", default_path, "ZIP (*.zip)")
            if not selected:
                return
            destination = Path(selected)
        else:
            selected = QFileDialog.getExistingDirectory(self, "选择空目录用于导出该版本 element", str(default_workspace()))
            if not selected:
                return
            destination = Path(selected)
        try:
            output = self.service.export_version_element(name, version, destination, zip_output=zip_output)
        except ValueError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(
            self,
            "版本图元库导出完成",
            f"已从本地冻结对象恢复 {name} V{version} 的完整图元树：\n{output}\n\n"
            "目录结构按保存时相对 /home/up8000/data/graph/element 的路径重建；导出过程不访问也不修改服务器。",
        )
        target = output.parent if output.is_file() else output
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _delete_selected_history_version(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name or version is None:
            QMessageBox.information(self, "请选择历史版本", "请先选择需要删除的 ARCHIVED 历史版本。")
            return
        if active:
            QMessageBox.information(
                self,
                "不能删除 ACTIVE",
                "当前 ACTIVE 版本不能直接删除。若确实不再需要整个标准，请使用“删除整个标准（全部版本）”。",
            )
            return
        global_name, global_version = self.service.get_global_profile_selection(auto_initialize=False)
        if name == global_name and version == global_version:
            QMessageBox.information(
                self,
                "不能删除 GLOBAL",
                "当前版本正在作为全局执行标准。请先将另一个版本设为全局版本，再删除该历史版本。",
            )
            return
        if QMessageBox.question(
            self,
            "删除历史版本",
            f"确认删除 {name} / V{version} 这个 ARCHIVED 历史版本？\n\n"
            "只删除这个版本的配置快照和可达 Manifest；ACTIVE、GLOBAL 及其他历史版本全部保留。\n"
            "SHA256 对象不会自动垃圾回收，避免误删其他版本共享的图元文件。此操作不会访问或修改服务器。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            current = self.service.delete_archived_version(name, version)
        except ValueError as exc:
            QMessageBox.warning(self, "删除历史版本失败", str(exc))
            return
        self._reload_profiles(name, current.profile_version)
        QMessageBox.information(
            self,
            "历史版本已删除",
            f"{name} / V{version} 已从可用版本历史中删除。其他版本及其图元配置没有变化。\n"
            "本地图元对象库不会自动清理未引用 SHA256 对象；后续如需释放空间，可单独提供安全的未引用对象清理功能。",
        )

    def _delete_profile(self) -> None:
        name, version, active = self._selected_profile_key()
        if not name:
            QMessageBox.information(self, "请选择标准", "请先选择需要删除的已保存图元标准。")
            return
        if not active:
            QMessageBox.information(
                self,
                "请选择删除方式",
                "当前选中的是 ARCHIVED 历史版本。若只删除这一版，请使用“删除选中历史版本”；"
                "若要删除整个 Profile，请选择其 ACTIVE 版本后使用“删除整个标准（全部版本）”。",
            )
            return
        current = self.service.load_profiles().get(name)
        if current is None:
            return
        if QMessageBox.question(
            self,
            "删除整个标准",
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
            "将按当前全局图元标准纠正已定义图元的变体/devref，以及可可靠计算的 pin/ConnectLine 连接锚点位置。\n"
            "同时会删除能够证明为重复的设备贯穿 ConnectLine；对权威标准确认只有一个电气 Pin 的设备，若连接线只是轻微偏斜，则自动吸附为水平或垂直并同步平移设备。\n\n"
            "源 G 文件不会覆盖；纠正后的 G 会写入本次 workspace 运行目录的 corrected 文件夹，并自动执行一次复查。\n"
            "未纳入当前标准、连接关系不明确、偏移过大或无法可靠拟合的对象不会猜测修改。\n\n继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._start_profile_run(correct=True)

    def _start_profile_run(self, *, correct: bool = False) -> None:
        name, version = self.service.get_global_profile_selection()
        profile = self.service.get_profile_version(name, version) if name and version is not None else None
        if profile is None:
            QMessageBox.warning(self, "尚未设置全局标准", "请先在“标准版本”下拉框中选择已保存版本，并点击“设为全局版本”。")
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
            self.result_summary.setText(f"正在按全局 V{profile.profile_version} 标准生成纠正副本……源 G 文件不会覆盖。")
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
        busy_server = self._server_sync_worker is not None
        busy = busy_scan or busy_server or self._task_busy
        global_name, global_version = self.service.get_global_profile_selection()
        global_profile = self.service.get_profile_version(global_name, global_version) if global_name and global_version is not None else None
        authoritative_ready, _issues = self.service.validate_authoritative_standard(global_profile)
        ready = bool(global_profile and authoritative_ready)
        self.check_button.setEnabled(ready and not busy)
        self.correct_button.setEnabled(ready and not busy)
        if hasattr(self, "set_global_button"):
            selected_profile = self.service.get_profile_version(name, version) if name and version is not None else None
            selected_ready, _selected_issues = self.service.validate_authoritative_standard(selected_profile)
            already_global = bool(name == global_name and version == global_version)
            self.set_global_button.setEnabled(bool(selected_profile and selected_ready and not already_global and not busy))
            self.set_global_button.setText("当前全局版本" if already_global else "设为全局版本")
        # New profiles and ACTIVE profiles may be scanned. Archived rows are immutable.
        allow_scan = (not name) or bool(active and profile is not None and not profile.locked)
        self.scan_action.setEnabled(allow_scan and not busy)
        self.scan_action.setText("为选中图元上传 / 更新标准 G")
        if hasattr(self, "upload_standard_button"):
            self.upload_standard_button.setEnabled(allow_scan and not busy)
            self.upload_standard_button.setText("为选中图元上传 / 更新标准 G")
        locked = bool(profile.locked) if profile is not None and active else False
        rescan_working = bool(self._rescan_prepare_mode or self._rescan_draft_mode)
        if hasattr(self, "discovery_scan_button"):
            # Locked saved standards stay immutable.  The only exception is an
            # explicitly armed fresh-rescan workflow, whose input/output live in an
            # isolated local DRAFT and therefore cannot modify the locked snapshot.
            allow_discovery = (not name) or bool(active and profile is not None and not locked)
            allow_discovery = bool(rescan_working or allow_discovery)
            self.discovery_scan_button.setEnabled(allow_discovery and not busy)
            self._set_discovery_input_visible(rescan_working or not locked)
            self.discovery_scan_button.setText(
                f"重新扫描生成 V{self._rescan_draft_target_version or '?'} 草稿"
                if self._rescan_prepare_mode else
                ("重新扫描 / 更新当前新版本草稿" if self._rescan_draft_mode else "扫描当前版本候选")
            )
        can_edit = self._rescan_draft_mode or (
            not self._rescan_prepare_mode
            and ((not name) or bool(active and profile is not None and not locked))
        )
        self.save_button.setEnabled(can_edit and not busy)
        self.save_button.setText("保存为新版本" if self._rescan_draft_mode else "保存当前标准")
        self.add_custom_button.setEnabled(can_edit and not busy)
        selected_standard_row = self.standard_table.currentRow()
        self.delete_custom_button.setEnabled(
            can_edit and not busy and selected_standard_row >= len(self._standard_specs)
        )
        if hasattr(self, "share_pair_checkbox"):
            self.share_pair_checkbox.setEnabled(
                can_edit and not busy and 0 <= selected_standard_row < len(self._standard_specs)
            )
        if hasattr(self, "server_sync_button"):
            server_enabled = bool(self.server_standard_enabled.isChecked())
            self.server_sync_button.setEnabled(server_enabled and not busy)
            self.server_symbol_root.setEnabled(server_enabled and not busy_server)
            if hasattr(self, "server_connection_button"):
                self.server_connection_button.setEnabled(not busy_server)
            self.server_cache_button.setEnabled(not busy_server)
            if hasattr(self, "server_new_version_button"):
                changed_names = self._last_server_sync_payload.get("profile_changed_names", [])
                matched_records = self._last_server_sync_payload.get("matched_records", {})
                changed_keys = {Path(str(item)).name.casefold() for item in changed_names if Path(str(item)).name} if isinstance(changed_names, list) else set()
                has_replacements = bool(
                    locked
                    and changed_keys
                    and isinstance(matched_records, dict)
                    and any(Path(str(name)).name.casefold() in changed_keys and isinstance(record, dict) for name, record in matched_records.items())
                )
                self.server_new_version_button.setVisible(has_replacements)
                self.server_new_version_button.setEnabled(has_replacements and not busy)
        if hasattr(self, "rescan_new_version_button"):
            can_start_fresh = bool(name and profile and active and not busy and not self._rescan_draft_mode)
            self.rescan_new_version_button.setEnabled(can_start_fresh)
            self.rescan_new_version_button.setText(
                f"开始重新扫描 V{self._rescan_draft_target_version or '?'} 草稿"
                if self._rescan_prepare_mode else "全量重新扫描 → 新版本草稿"
            )
            self.cancel_rescan_draft_button.setVisible(bool(self._rescan_prepare_mode or self._rescan_draft_mode))
            self.cancel_rescan_draft_button.setEnabled(not busy)
        if hasattr(self, "lock_standard_button"):
            self.lock_standard_button.setEnabled(bool(name and profile and active and not busy and not rescan_working))
            self.lock_standard_button.setText("解锁当前版本" if locked else "锁定当前版本")
        current_profile = self.service.load_profiles().get(name) if name else None
        current_locked = bool(current_profile.locked) if current_profile is not None else False
        has_saved_version = bool(name and version is not None and self.service.get_profile_version(name, version) is not None)
        if hasattr(self, "version_details_action"):
            self.version_details_action.setEnabled(has_saved_version and not busy)
            self.verify_version_action.setEnabled(has_saved_version and not busy)
            self.export_version_action.setEnabled(has_saved_version and not busy)
            self.export_version_zip_action.setEnabled(has_saved_version and not busy)
        self.restore_action.setEnabled(bool(name and profile and not active and not busy and not current_locked))
        self.delete_action.setEnabled(bool(name and profile and active and not busy and not locked))
        self.new_action.setEnabled(not busy)
        self._refresh_standard_table_overview()

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
        if hasattr(self, "discovery_source"):
            self.discovery_source.persist_all_text()
        self.output_path.persist_current_text()
