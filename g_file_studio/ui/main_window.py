from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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
from g_file_studio.ui.pages import BasicPage, FramePage, HelpPage, MarginPage, MergePage
from g_file_studio.ui.theme import build_app_style


class MainWindow(QMainWindow):
    def __init__(
        self,
        user_settings: UserSettingsService,
    ) -> None:
        super().__init__()
        self.user_settings = user_settings
        self.setWindowTitle("G File Studio · 电网图形处理")
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

        self.statusBar().showMessage("电网图形工作台已就绪。鼠标停留在控件上可查看提示，按 F1 打开帮助中心。")
        self._install_help_shortcut()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
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
        subtitle = QLabel("电网 XML 图形处理工作台")
        subtitle.setObjectName("brandSubtitle")
        brand_text_layout.addWidget(title)
        brand_text_layout.addWidget(subtitle)
        brand_row.addWidget(badge)
        brand_row.addWidget(brand_text, 1)

        grid_badge = QLabel("GRID GRAPHICS · 电网图形")
        grid_badge.setObjectName("gridModeBadge")
        grid_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setSpacing(1)
        navigation = [
            ("基础处理", "执行通用规则、ID、环网柜及颜色处理"),
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

        version = QLabel(f"G File Studio {__version__}")
        version.setObjectName("sidebarVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        side_layout.addLayout(brand_row)
        side_layout.addSpacing(14)
        side_layout.addWidget(grid_badge)
        side_layout.addSpacing(12)
        side_layout.addWidget(self.nav, 1)
        side_layout.addSpacing(10)
        side_layout.addWidget(version)
        return sidebar

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
        action.triggered.connect(lambda: self.nav.setCurrentRow(4))
        self.addAction(action)
