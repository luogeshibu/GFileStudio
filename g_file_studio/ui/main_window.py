from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
from g_file_studio.ui.theme import build_app_style
from g_file_studio.ui.widgets import WheelSafeComboBox


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
        self.site_profile_page = SiteProfilePage(self.user_settings)
        self.jeddah_batch_page = JeddahBatchPage(self.user_settings)
        self.pages = [
            DatabasePage(self.user_settings),
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
            HelpPage(),
        ]
        # Symbol standards are shared state.  Saving/restoring/deleting an ACTIVE
        # standard must update the already-created Jeddah page immediately instead
        # of leaving the profile combo with startup-time cached contents.
        self.site_profile_page.activeProfileChanged.connect(self.jeddah_batch_page.refresh_profiles)
        for page in self.pages:
            self.stack.addWidget(page)

        self.nav.currentRowChanged.connect(self._change_page)
        self.nav.setCurrentRow(0)

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
        )
        for key in managed_keys:
            if self.user_settings.get_value(key).strip():
                self.user_settings.clear(key)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        self.sidebar = sidebar
        sidebar.setFixedWidth(250)
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

        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setSpacing(1)
        # Navigation module names are always shown in full on one line.
        # English labels are longer, so the whole sidebar grows instead of
        # wrapping, eliding with "...", or exposing a horizontal scrollbar.
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setWordWrap(False)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.nav.setUniformItemSizes(True)
        self.nav.setResizeMode(QListView.ResizeMode.Fixed)
        navigation = [
            ("数据库", "公共 Oracle 数据库连接配置与只读访问入口；后续需要数据库的业务模块统一复用该配置"),
            ("异常小尺寸图元检测", "检测 ConnectLine、FeedLine、Bus、BusDis 中 w/h 同时过小的疑似残留短线图元；通过首列勾选单选/多选/全选后统一执行处理"),
            ("ID 检查与修复", "全局 ID 规则中心：维护模板、扫描覆盖并强制修复格式异常或重复 ID"),
            ("图元标准检查", "通用图元标准检查与安全纠正：检查模式只读；纠正模式仅对 ACTIVE 标准已定义图元生成 workspace 副本，并保持可可靠解析的 ConnectLine 电气锚点不动"),
            ("环网柜处理", "独立处理环网柜组合/取消组合、增强操作，以及柜名与柜型识别"),
            ("Poke 跳转处理", "独立生成/修复 RMU 与站点跳转 Poke；复用公共 RMU 识别、Oracle 数据库及站点 Poke 参考属性"),
            ("基础处理", "执行通用属性、同类图元版本升级、馈线标题、连接点和线路/母线颜色处理；涉及 ID 时强制使用全局模板"),
            ("馈线图合并", "按用户选择顺序合并多个馈线 G 图"),
            ("图形边距调整", "调整主体四边距，并同步适配内置图框"),
            ("图框添加", "添加 SLD 外框、标题和签字栏"),
            ("吉达馈线批处理", "Jeddah 专用：第一步彻底取消图形组合（删除全部 <Merge>、RMU 外框置底），再批量删除异常小元素、SMART/SMR 红框、SMART 图元校正 + SMR 智能清理/转换 + 转换后图元复检、RMU 柜名白色 + 字号50 + 上边框上方10居中、删除 RMU channel_status 红色状态点、Bus 外框清理、馈线名称上移、FeedLine 统一实线、删除 H.T、清理同柜重复 SMART、相邻 2000.00 + UPDATED_MEASURMENT 成对删除、ID 检查与修复、图形边距调整并添加图框"),
            ("帮助中心", "查看使用说明和目录建议"),
        ]
        for name, tip in navigation:
            item = QListWidgetItem(name)
            item.setToolTip(tip)
            item.setStatusTip(tip)
            self.nav.addItem(item)

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
        side_layout.addSpacing(12)
        side_layout.addWidget(self.nav, 1)
        side_layout.addSpacing(10)
        side_layout.addWidget(language_label)
        side_layout.addSpacing(5)
        side_layout.addWidget(self.language_combo)
        side_layout.addSpacing(10)
        side_layout.addWidget(version)
        return sidebar


    def _language_combo_changed(self, index: int) -> None:
        language = self.language_combo.itemData(index)
        if language:
            self.language_manager.set_language(str(language))

    def _apply_language(self, language: str) -> None:
        del language
        self.language_manager.translate_widget_tree(self)
        if hasattr(self, "nav"):
            # English module names are longer. Grow the sidebar so every module
            # name remains fully visible on one line, with no wrap/ellipsis.
            self._adjust_sidebar_width()
            QTimer.singleShot(0, self._adjust_sidebar_width)
            item = self.nav.currentItem()
            if item:
                self.statusBar().showMessage(item.statusTip() or item.toolTip())

    def _adjust_sidebar_width(self) -> None:
        """Keep every navigation module name fully visible on one line."""
        if not hasattr(self, "nav") or not hasattr(self, "sidebar"):
            return
        metrics = self.nav.fontMetrics()
        widest = 0
        for row in range(self.nav.count()):
            widest = max(widest, metrics.horizontalAdvance(self.nav.item(row).text()))
        # 36 px QList item horizontal padding + sidebar layout margins and a
        # small reserve for selection decoration. Keep Chinese compact while
        # allowing long English module names to remain unabridged.
        width = max(250, min(380, widest + 78))
        self.sidebar.setFixedWidth(width)

    def _change_page(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            page = self.pages[index]
            on_page_activated = getattr(page, "on_page_activated", None)
            if callable(on_page_activated):
                on_page_activated()
            item = self.nav.item(index)
            if item:
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
        action.triggered.connect(lambda: self.nav.setCurrentRow(help_index))
        self.addAction(action)
