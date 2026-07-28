from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """可写项目根目录；打包后为 EXE 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """只读资源根目录；兼容 PyInstaller one-dir / one-file。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return project_root()


def default_workspace() -> Path:
    return project_root() / "workspace"


def default_template() -> Path:
    return resource_root() / "resources" / "templates" / "SLD-Drawing-Frame-Template.sln.pic.g"
