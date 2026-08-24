from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
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
from g_file_studio.ui.theme import build_app_style


class MainWindow(QMainWindow):
    def __init__(
        self,
        user_settings: UserSettingsService,
    ) -> None:
        super().__init__()
        self.user_settings = user_settings
        self.language_manager = LanguageManager(user_settings, self)
        cleanup_expired_runs()
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
        self.pages = [
            SmallElementPage(self.user_settings),
            IdPage(self.user_settings),
            RmuPage(self.user_settings),
            BasicPage(self.user_settings),
            MergePage(self.user_settings),
            MarginPage(self.user_settings),
            FramePage(self.user_settings),
            HelpPage(),
        ]
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
            ("异常小尺寸图元检测", "检测 ConnectLine、FeedLine、Bus、BusDis 中 w/h 同时过小的疑似残留短线图元；通过首列勾选单选/多选/全选后统一执行处理"),
            ("ID 检查与修复", "全局 ID 规则中心：维护模板、扫描覆盖并强制修复格式异常或重复 ID"),
            ("环网柜处理", "独立处理环网柜组合/取消组合、增强操作，以及柜名与柜型识别"),
            ("基础处理", "执行通用属性、图元升级、馈线标题、连接点和线路/母线颜色处理；涉及 ID 时强制使用全局模板"),
            ("馈线图合并", "按用户选择顺序合并多个馈线 G 图"),
            ("图形边距调整", "调整主体四边距，并同步适配内置图框"),
            ("图框添加", "添加 SLD 外框、标题和签字栏"),
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

        self.language_combo = QComboBox()
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
        action.triggered.connect(lambda: self.nav.setCurrentRow(7))
        self.addAction(action)
