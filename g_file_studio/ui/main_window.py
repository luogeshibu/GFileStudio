from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QToolButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from g_file_studio import __version__
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.services.run_history import cleanup_expired_runs
from g_file_studio.i18n import LANG_EN, LANG_ZH, LanguageManager
from g_file_studio.ui.pages import BasicPage, FramePage, HelpPage, IdPage, MarginPage, MergePage, RmuPage, SmallElementPage
from g_file_studio.ui.pages.poke_page import PokePage
from g_file_studio.ui.pages.database_page import DatabasePage
from g_file_studio.ui.pages.site_profile_page import SiteProfilePage
from g_file_studio.ui.pages.jeddah_batch_page import JeddahBatchPage
from g_file_studio.ui.pages.orthogonalize_page import OrthogonalizePage
from g_file_studio.ui.theme import build_app_style
from g_file_studio.ui.widgets import WheelSafeComboBox
from g_file_studio.ui.widgets.remote_g_source import RemoteGSourceWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        user_settings: UserSettingsService,
    ) -> None:
        super().__init__()
        self.user_settings = user_settings
        self.language_manager = LanguageManager(user_settings, self)
        cleanup_expired_runs()
        self._clear_legacy_managed_output_paths()
        self.setWindowTitle("G File Studio · NARI 国际业务部")
        self.resize(1280, 860)
        self.setMinimumSize(1040, 720)

        central = QWidget()
        central.setObjectName("contentRoot")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentRoot")
        self.database_page = DatabasePage(self.user_settings)
        self.site_profile_page = SiteProfilePage(self.user_settings)
        self.jeddah_batch_page = JeddahBatchPage(self.user_settings)
        self.orthogonalize_page = OrthogonalizePage(self.user_settings)
        self.pages = [
            self.database_page,
            SmallElementPage(self.user_settings),
            IdPage(self.user_settings),
            self.site_profile_page,
            RmuPage(self.user_settings),
            PokePage(self.user_settings),
            BasicPage(self.user_settings),
            MergePage(self.user_settings),
            MarginPage(self.user_settings),
            FramePage(self.user_settings),
            self.jeddah_batch_page,
            self.orthogonalize_page,
            HelpPage(),
        ]
        # Presentation-only rename: keep the protected BasicPage implementation and
        # all settings/processor keys unchanged while exposing the clearer module name.
        basic_title = self.pages[6].findChild(QLabel, "pageTitle")
        if basic_title is not None:
            basic_title.setText("通用基础处理")
        # Symbol standards are shared state.  Saving/restoring/deleting an ACTIVE
        # standard must update the already-created Jeddah page immediately instead
        # of leaving the profile combo with startup-time cached contents.
        self.site_profile_page.activeProfileChanged.connect(self.jeddah_batch_page.refresh_profiles)
        self.site_profile_page.orthogonalizeRequested.connect(lambda: self._select_page(11))
        self.site_profile_page.connectionSettingsRequested.connect(lambda: self._select_page(0))
        for page in self.pages:
            self.stack.addWidget(page)
        # All business-page SSH sources consume the same global connection environment.
        # Their compact “连接设置” buttons jump to page 0; environment changes refresh
        # already-created widgets without duplicating credentials across modules.
        remote_widgets: list[RemoteGSourceWidget] = []
        for page in self.pages:
            remote_widgets.extend(page.findChildren(RemoteGSourceWidget))
        for remote_widget in remote_widgets:
            remote_widget.connectionSettingsRequested.connect(lambda: self._select_page(0))
            self.database_page.environmentChanged.connect(lambda _uid, w=remote_widget: w.refresh_shared_settings())
        self.database_page.environmentChanged.connect(lambda _uid: self.site_profile_page._refresh_global_connection_settings())

        self.nav.currentRowChanged.connect(self._change_page)
        # Restore the last business module the operator actually used. Utility pages
        # such as Connections/Help do not overwrite this preference; on first launch
        # 图元标准检查 remains the safe default business landing page.
        self._restore_last_business_page()

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.setStyleSheet(build_app_style())
        from PySide6.QtWidgets import QApplication
        qt_app = QApplication.instance()
        if qt_app is not None:
            qt_app.installEventFilter(self.language_manager)
        self.language_manager.languageChanged.connect(self._apply_language)
        # English runtime translation is event-driven. Do not periodically walk the
        # entire application tree: pages may contain thousands of table cells, and a
        # 300 ms full-tree refresh causes visible lag when switching modules.
        self.statusBar().showMessage("NARI 国际业务部 · G 文件处理工具已就绪。鼠标停留在控件上可查看提示，按 F1 打开帮助中心。")
        self._apply_language(self.language_manager.language)
        self._install_help_shortcut()


    def _clear_legacy_managed_output_paths(self) -> None:
        """清除旧版本保存的 workspace 托管输出路径。

        这些输出目录由程序按模块和运行批次统一生成，历史 run 目录可能被
        定期清理，因此不属于需要用户重新选择的路径。必须在各页面 PathRow
        构造前清理，避免它们把已经删除的旧 run 目录当成用户路径失效并弹窗。
        """
        managed_keys = (
            "small_elements/output_directory",
            "recent_paths/small_elements/output_directory",
            "id_rules/output_directory",
            "recent_paths/id_rules/output_directory",
            "site_profile/output_directory",
            "recent_paths/site_profile/output_directory",
            "symbol_inventory/output_directory",
            "recent_paths/symbol_inventory/output_directory",
            "rmu/output_directory",
            "recent_paths/rmu/output_directory",
            "poke/output_directory",
            "recent_paths/poke/output_directory",
            "basic/output_directory",
            "recent_paths/basic/output_directory",
            "merge/output_directory",
            "recent_paths/merge/output_directory",
            "margin/output_directory",
            "recent_paths/margin/output_directory",
            "frame/output_directory",
            "recent_paths/frame/output_directory",
            "jeddah_batch/output_directory",
            "recent_paths/jeddah_batch/output_directory",
            "orthogonalize/output_directory",
            "recent_paths/orthogonalize/output_directory",
        )
        for key in managed_keys:
            if self.user_settings.get_value(key).strip():
                self.user_settings.clear(key)

    NAV_PAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 20
    NAV_SECTION_ROLE = int(Qt.ItemDataRole.UserRole) + 21
    LAST_BUSINESS_PAGE_KEY = "navigation/last_business_page"
    BUSINESS_PAGE_IDS = {
        1: "small_elements",
        2: "id_rules",
        3: "symbol_standard",
        4: "rmu",
        5: "poke",
        6: "basic",
        7: "merge",
        8: "margin",
        9: "frame",
        10: "jeddah_batch",
        11: "orthogonalize",
    }

    def _restore_last_business_page(self) -> None:
        page_id = self.user_settings.get_value(self.LAST_BUSINESS_PAGE_KEY).strip()
        page_index = next(
            (index for index, stable_id in self.BUSINESS_PAGE_IDS.items() if stable_id == page_id),
            3,
        )
        if page_index == 3 and page_id not in self.BUSINESS_PAGE_IDS.values():
            # First launch / stale setting: 图元标准检查 remains the default.
            self._select_page(3)
            return
        self._select_page(page_index)

    def _remember_business_page(self, page_index: int) -> None:
        stable_id = self.BUSINESS_PAGE_IDS.get(int(page_index))
        if not stable_id:
            return
        if self.user_settings.get_value(self.LAST_BUSINESS_PAGE_KEY).strip() != stable_id:
            self.user_settings.set_value(self.LAST_BUSINESS_PAGE_KEY, stable_id)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        self.sidebar = sidebar
        sidebar.setFixedWidth(270)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 20, 18, 18)
        side_layout.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        badge = QFrame()
        badge.setObjectName("brandBadge")
        badge.setFixedSize(44, 44)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_letter = QLabel("G")
        badge_letter.setObjectName("brandLetter")
        badge_letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(badge_letter)

        brand_text = QWidget()
        brand_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        brand_text_layout = QVBoxLayout(brand_text)
        brand_text_layout.setContentsMargins(0, 1, 0, 0)
        brand_text_layout.setSpacing(1)
        title = QLabel("G File Studio")
        title.setObjectName("brandTitle")
        subtitle = QLabel("NARI 国际业务部")
        subtitle.setObjectName("brandSubtitle")
        brand_text_layout.addWidget(title)
        brand_text_layout.addWidget(subtitle)
        brand_row.addWidget(badge)
        brand_row.addWidget(brand_text, 1)

        grid_badge = QLabel("G 文件处理工具")
        grid_badge.setObjectName("gridModeBadge")
        grid_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_badge.setFixedHeight(32)
        grid_badge.setStyleSheet("font-size: 11px; font-weight: 700;")

        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setSpacing(2)
        # 分组标题和业务项共用一个可滚动导航列表；业务项始终单行完整显示。
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setWordWrap(False)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.nav.setUniformItemSizes(False)
        self.nav.setResizeMode(QListView.ResizeMode.Adjust)
        # v2.18.112：继续优化侧栏大标题显示。分组标题行预留足够内容区，避免 QListWidget item 的 padding 在高 DPI 下裁掉按钮下边框/文字；同时统一提升分组标题与顶部工具标题的可读性。仅调整导航展示。
        self.nav.setStyleSheet(
            "QListWidget#navigation { background: transparent; border: none; color: #d4e2e2; "
            "outline: none; padding: 0; font-size: 14px; }"
            "QListWidget#navigation::item { background: transparent; border: none; "
            "border-left: 3px solid transparent; border-radius: 8px; margin: 2px 0; "
            "padding: 11px 14px 11px 18px; font-size: 14px; font-weight: 560; }"
            "QListWidget#navigation::item:hover { background: #123440; color: #ffffff; "
            "border-left-color: #2fa889; }"
            "QListWidget#navigation::item:selected { background: #0b7a5a; color: #ffffff; "
            "border-left-color: #84e2c3; }"
        )
        self._page_to_nav_row: dict[int, int] = {}
        self._nav_section_rows: dict[str, list[int]] = {}
        self._nav_section_buttons: dict[str, QToolButton] = {}

        # 页面索引保持 self.pages 的既有稳定顺序，只调整左侧展示层级；
        # 不修改任何页面/处理器的业务调用关系。
        navigation_sections = [
            (
                "检查与标准",
                "validation_standard",
                [
                    ("异常小尺寸图元检测", "检测 ConnectLine、FeedLine、Bus、BusDis 中 w/h 同时过小的疑似残留短线图元；通过首列勾选单选/多选/全选后统一执行处理", 1),
                    ("ID 检查与修复", "全局 ID 规则中心：维护模板、扫描覆盖并强制修复格式异常或重复 ID", 2),
                    ("图元标准检查", "只检查服务器标准图元与业务 G 的标准一致性；纠正仅生成 workspace 标准纠正副本，不负责全图拓扑或线路重画", 3),
                ],
            ),
            (
                "图形处理",
                "graphic_processing",
                [
                    ("环网柜处理", "独立处理环网柜组合/取消组合、增强操作，以及柜名与柜型识别", 4),
                    ("Poke 跳转处理", "独立生成/修复 RMU 与站点跳转 Poke；复用公共 RMU 识别、Oracle 数据库及站点 Poke 参考属性", 5),
                    ("通用基础处理", "执行通用属性、同类图元版本升级、馈线标题、连接点和线路/母线颜色处理；涉及 ID 时强制使用全局模板", 6),
                    ("馈线图合并", "按用户选择顺序合并多个馈线 G 图", 7),
                    ("图形边距调整", "调整主体四边距，并同步适配内置图框", 8),
                    ("图框添加", "添加 SLD 外框、标题和签字栏", 9),
                    ("线路正交化", "按单个 G 文件的线路结构处理连接点对齐、线路横平竖直和安全重画", 11),
                ],
            ),
            (
                "现场批处理",
                "site_batch",
                [
                    ("吉达馈线批处理", "Jeddah 专用：第一步彻底取消图形组合（删除全部 <Merge>、RMU 外框置底），再批量删除异常小元素、SMART/SMR 红框、SMART 图元校正 + SMR 智能清理/转换 + 转换后图元复检、RMU 柜名严格按外框内三类组成并只从上方识别 + 白色 + 字号50 + 上边框上方10居中、删除 RMU channel_status 红色状态点、Bus 外框清理、馈线名称上移、FeedLine 统一实线、删除 H.T、清理同柜重复 SMART、相邻 2000.00 + UPDATED_MEASURMENT 成对删除、ID 检查与修复、图形边距调整并添加图框", 10),
                ],
            ),
        ]

        for section_title, section_key, entries in navigation_sections:
            header_item = QListWidgetItem()
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            header_item.setSizeHint(QSize(0, 74))
            self.nav.addItem(header_item)

            section_button = QToolButton()
            section_button.setObjectName("navSectionButton")
            section_button.setText(section_title)
            section_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            section_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            section_button.setFixedHeight(40)
            section_button.setStyleSheet(
                "QToolButton { background: #0e2a34; color: #9fc4c1; "
                "border: 1px solid #173d48; border-radius: 8px; "
                "padding: 7px 10px; text-align: left; font-size: 14px; font-weight: 750; }"
                "QToolButton:hover { color: #e1f5f0; background: #12343f; border-color: #286071; }"
                "QToolButton:checked { color: #dff8ef; background: #10313b; border-color: #1e5663; }"
            )
            section_button.setCheckable(True)
            expanded = self.user_settings.get_bool(f"navigation/{section_key}_expanded", True)
            section_button.setChecked(expanded)
            section_button.setArrowType(
                Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
            )
            # Header rows use a dedicated container with vertical breathing room.
            # This prevents the section card from visually colliding with the first child row
            # under Windows display scaling and keeps the child titles clearly subordinate.
            header_container = QWidget()
            header_container.setObjectName("navSectionContainer")
            header_layout = QVBoxLayout(header_container)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(0)
            header_layout.addWidget(section_button)
            self.nav.setItemWidget(header_item, header_container)
            self._nav_section_buttons[section_key] = section_button
            self._nav_section_rows[section_key] = []

            for name, tip, page_index in entries:
                item = QListWidgetItem(name)
                item.setToolTip(tip)
                item.setStatusTip(tip)
                item.setData(self.NAV_PAGE_ROLE, page_index)
                item.setData(self.NAV_SECTION_ROLE, section_key)
                self.nav.addItem(item)
                row = self.nav.row(item)
                self._page_to_nav_row[page_index] = row
                self._nav_section_rows[section_key].append(row)
                item.setHidden(not expanded)

            section_button.toggled.connect(
                lambda checked, key=section_key: self._set_navigation_section_expanded(key, checked)
            )

        self.connection_button = QPushButton("连接与环境")
        self.connection_button.setObjectName("sidebarConnectionButton")
        self.connection_button.setCheckable(True)
        self.connection_button.setStyleSheet(
            "QPushButton { background: transparent; color: #d4e2e2; border: none; "
            "border-left: 3px solid transparent; border-radius: 8px; padding: 12px 16px; "
            "text-align: left; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #123440; color: #ffffff; border-left-color: #2fa889; }"
            "QPushButton:checked { background: #0b7a5a; color: #ffffff; border-left-color: #84e2c3; }"
        )
        self.connection_button.setToolTip("统一管理当前环境的只读文件服务器、资源目录和 Oracle 数据库连接")
        self.connection_button.setStatusTip("统一管理当前环境的只读文件服务器、资源目录和 Oracle 数据库连接")
        self.connection_button.clicked.connect(lambda: self._select_page(0))

        self.help_button = QPushButton("帮助中心")
        self.help_button.setObjectName("sidebarHelpButton")
        self.help_button.setCheckable(True)
        self.help_button.setStyleSheet(
            "QPushButton { background: transparent; color: #d4e2e2; border: none; "
            "border-left: 3px solid transparent; border-radius: 8px; padding: 12px 16px; "
            "text-align: left; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #123440; color: #ffffff; border-left-color: #2fa889; }"
            "QPushButton:checked { background: #0b7a5a; color: #ffffff; border-left-color: #84e2c3; }"
        )
        self.help_button.setToolTip("查看使用说明和目录建议")
        self.help_button.setStatusTip("查看使用说明和目录建议")
        self.help_button.clicked.connect(lambda: self._select_page(12))

        language_label = QLabel("语言 / Language")
        language_label.setObjectName("sidebarLanguageLabel")
        language_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.language_combo = WheelSafeComboBox()
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.addItem("中文", LANG_ZH)
        self.language_combo.addItem("English", LANG_EN)
        current_language = self.language_manager.language
        current_index = self.language_combo.findData(current_language)
        self.language_combo.setCurrentIndex(max(0, current_index))
        self.language_combo.setToolTip("切换界面语言；选择会自动保存，下次启动继续使用。")
        self.language_combo.currentIndexChanged.connect(self._language_combo_changed)

        version = QLabel(f"G File Studio {__version__}")
        version.setObjectName("sidebarVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        side_layout.addLayout(brand_row)
        side_layout.addSpacing(14)
        side_layout.addWidget(grid_badge)
        side_layout.addSpacing(10)
        side_layout.addWidget(self.nav, 1)
        side_layout.addSpacing(8)
        side_layout.addWidget(self.connection_button)
        side_layout.addSpacing(4)
        side_layout.addWidget(self.help_button)
        side_layout.addSpacing(12)
        side_layout.addWidget(language_label)
        side_layout.addSpacing(5)
        side_layout.addWidget(self.language_combo)
        side_layout.addSpacing(10)
        side_layout.addWidget(version)
        return sidebar

    def _set_navigation_section_expanded(self, section_key: str, expanded: bool) -> None:
        button = self._nav_section_buttons.get(section_key)
        if button is not None:
            button.setArrowType(
                Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
            )
        for row in self._nav_section_rows.get(section_key, []):
            item = self.nav.item(row)
            if item is not None:
                item.setHidden(not expanded)
        self.user_settings.set_value(
            f"navigation/{section_key}_expanded", "true" if expanded else "false"
        )

    def _select_page(self, page_index: int) -> None:
        if not hasattr(self, "pages"):
            return
        help_index = next((i for i, page in enumerate(self.pages) if isinstance(page, HelpPage)), -1)
        if page_index == 0:
            self.nav.setCurrentRow(-1)
            self.stack.setCurrentIndex(0)
            self.connection_button.setChecked(True)
            self.help_button.setChecked(False)
            page = self.pages[0]
            on_page_activated = getattr(page, "on_page_activated", None)
            if callable(on_page_activated):
                on_page_activated()
            self.statusBar().showMessage(self.connection_button.statusTip() or self.connection_button.toolTip())
            return
        if page_index == help_index:
            self.nav.setCurrentRow(-1)
            self.stack.setCurrentIndex(help_index)
            self.connection_button.setChecked(False)
            self.help_button.setChecked(True)
            page = self.pages[help_index]
            on_page_activated = getattr(page, "on_page_activated", None)
            if callable(on_page_activated):
                on_page_activated()
            self.statusBar().showMessage(self.help_button.statusTip() or self.help_button.toolTip())
            return

        row = self._page_to_nav_row.get(page_index)
        if row is None:
            return
        item = self.nav.item(row)
        section_key = str(item.data(self.NAV_SECTION_ROLE) or "")
        if section_key:
            section_button = self._nav_section_buttons.get(section_key)
            if section_button is not None and not section_button.isChecked():
                section_button.setChecked(True)
        self.connection_button.setChecked(False)
        self.help_button.setChecked(False)
        if self.nav.currentRow() == row:
            self._change_page(row)
        else:
            self.nav.setCurrentRow(row)


    def _language_combo_changed(self, index: int) -> None:
        language = self.language_combo.itemData(index)
        if language:
            self.language_manager.set_language(str(language))

    def _apply_language(self, language: str) -> None:
        del language
        self.language_manager.translate_widget_tree(self)
        if hasattr(self, "nav"):
            # Keep child-page titles visually subordinate to the group heading.
            # The i18n layer stores the clean source text in Qt.UserRole, so this
            # presentation-only indent can be re-applied safely after every language switch.
            self._apply_navigation_child_indent()
            # English module/group names are longer. Grow the sidebar so every
            # visible label remains complete on one line.
            self._adjust_sidebar_width()
            QTimer.singleShot(0, self._adjust_sidebar_width)
            if hasattr(self, "connection_button") and self.connection_button.isChecked():
                self.statusBar().showMessage(self.connection_button.statusTip() or self.connection_button.toolTip())
            elif hasattr(self, "help_button") and self.help_button.isChecked():
                self.statusBar().showMessage(self.help_button.statusTip() or self.help_button.toolTip())
            else:
                item = self.nav.currentItem()
                if item and item.data(self.NAV_PAGE_ROLE) is not None:
                    self.statusBar().showMessage(item.statusTip() or item.toolTip())

    def _apply_navigation_child_indent(self) -> None:
        """Indent business page labels without changing their stored i18n source text."""
        indent = "\u2003\u2003"
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            if item is None or item.data(self.NAV_PAGE_ROLE) is None:
                continue
            clean_text = item.text().lstrip(" \t\u2002\u2003")
            item.setText(indent + clean_text)

    def _adjust_sidebar_width(self) -> None:
        """Keep grouped navigation labels fully visible on one line."""
        if not hasattr(self, "nav") or not hasattr(self, "sidebar"):
            return
        metrics = self.nav.fontMetrics()
        widest = 0
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            if item is not None and item.text():
                source_text = item.data(int(Qt.ItemDataRole.UserRole))
                display_text = str(source_text) if source_text else item.text().lstrip(" \t\u2002\u2003")
                widest = max(widest, metrics.horizontalAdvance(display_text))
        for button in getattr(self, "_nav_section_buttons", {}).values():
            widest = max(widest, button.fontMetrics().horizontalAdvance(button.text()) + 22)
        if hasattr(self, "connection_button"):
            widest = max(widest, self.connection_button.fontMetrics().horizontalAdvance(self.connection_button.text()))
        if hasattr(self, "help_button"):
            widest = max(widest, self.help_button.fontMetrics().horizontalAdvance(self.help_button.text()))
        # Business items keep their original width budget; visual child indentation is added after translation and is not allowed to inflate the sidebar.
        width = max(270, min(420, widest + 88))
        self.sidebar.setFixedWidth(width)

    def _change_page(self, nav_row: int) -> None:
        if nav_row < 0 or nav_row >= self.nav.count():
            return
        item = self.nav.item(nav_row)
        if item is None:
            return
        page_index = item.data(self.NAV_PAGE_ROLE)
        if not isinstance(page_index, int) or not (0 <= page_index < self.stack.count()):
            return
        self.connection_button.setChecked(False)
        self.help_button.setChecked(False)
        self.stack.setCurrentIndex(page_index)
        self._remember_business_page(page_index)
        page = self.pages[page_index]
        on_page_activated = getattr(page, "on_page_activated", None)
        if callable(on_page_activated):
            on_page_activated()
        self.statusBar().showMessage(item.statusTip() or item.toolTip())


    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        for page in self.pages:
            save_state = getattr(page, "save_state", None)
            if callable(save_state):
                save_state()
        super().closeEvent(event)

    def _install_help_shortcut(self) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_index = next((i for i, page in enumerate(self.pages) if isinstance(page, HelpPage)), 0)
        action.triggered.connect(lambda: self._select_page(help_index))
        self.addAction(action)
