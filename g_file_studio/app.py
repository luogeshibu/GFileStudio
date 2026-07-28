from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from g_file_studio import __version__
from g_file_studio.services.temp_workspace_service import TempWorkspaceService
from g_file_studio.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("G File Studio")
    app.setApplicationDisplayName("G File Studio")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("NARI")
    app.setStyle(QStyleFactory.create("Fusion"))

    temp_workspace = TempWorkspaceService()
    temp_workspace.startup_cleanup()
    app.aboutToQuit.connect(temp_workspace.cleanup)

    window = MainWindow(temp_workspace)
    window.show()
    return app.exec()
