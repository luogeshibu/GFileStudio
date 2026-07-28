from __future__ import annotations

import ctypes
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from g_file_studio import __version__
from g_file_studio.services.paths import app_icon_ico, app_icon_png, ensure_default_workspace
from g_file_studio.services.temp_workspace_service import TempWorkspaceService
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.main_window import MainWindow


def _set_windows_app_id() -> None:
    """让 Windows 任务栏按本程序身份显示自定义图标。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            "NARI.GFileStudio"
        )
    except (AttributeError, OSError):
        pass


def _load_app_icon() -> QIcon:
    for path in (app_icon_ico(), app_icon_png()):
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


def main() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("GFileStudio")
    app.setApplicationDisplayName("G File Studio")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("NARI")
    app.setOrganizationDomain("nari.com")
    app.setStyle(QStyleFactory.create("Fusion"))

    ensure_default_workspace()

    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    user_settings = UserSettingsService()
    temp_workspace = TempWorkspaceService()
    temp_workspace.startup_cleanup()
    app.aboutToQuit.connect(temp_workspace.cleanup)

    window = MainWindow(temp_workspace, user_settings)
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    return app.exec()
