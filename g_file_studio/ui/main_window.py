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
from g_file_studio.services.temp_workspace_service import TempWorkspaceService
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.pages import BasicPage, FramePage, HelpPage, MergePage, PipelinePage
from g_file_studio.ui.theme import build_app_style


class MainWindow(QMainWindow):
    def __init__(
        self,
        temp_workspace: TempWorkspaceService,
        user_settings: UserSettingsService,
    ) -> None:
        super().__init__()
        self.temp_workspace = temp_workspace
        self.user_settings = user_settings
        self.setWindowTitle("G File Studio")
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
            PipelinePage(self.temp_workspace, self.user_settings),
            BasicPage(self.user_settings),
            MergePage(self.user_settings),
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

        self.statusBar().showMessage("就绪。鼠标停留在控件上可查看提示，按 F1 打开帮助中心。")
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
        subtitle = QLabel("XML 图形处理工作台")
        subtitle.setObjectName("brandSubtitle")
        brand_text_layout.addWidget(title)
        brand_text_layout.addWidget(subtitle)
        brand_row.addWidget(badge)
        brand_row.addWidget(brand_text, 1)

        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setSpacing(1)
        navigation = [
            ("一键处理", "运行完整或自定义处理流程"),
            ("基础处理", "执行通用属性替换和元素删除规则"),
            ("G 文件合并", "合并任意命名的未加外框 .sln.pic.g 文件"),
            ("添加图框", "添加 SLD 外框、标题和签字栏"),
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
        side_layout.addSpacing(24)
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
        self.temp_workspace.cleanup()
        super().closeEvent(event)

    def _install_help_shortcut(self) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence.StandardKey.HelpContents)
        action.triggered.connect(lambda: self.nav.setCurrentRow(4))
        self.addAction(action)
