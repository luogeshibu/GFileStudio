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


def resource_path(relative_path: str | Path) -> Path:
    """返回源码运行或 PyInstaller 打包后的资源绝对路径。"""
    return resource_root() / Path(relative_path)


def default_workspace() -> Path:
    return project_root() / "workspace"


def ensure_default_workspace() -> Path:
    """创建程序默认使用的输入、输出与日志目录。"""
    root = default_workspace()
    for name in ("input", "processed", "merged", "work", "output", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def default_template() -> Path:
    return resource_path("resources/templates/SLD-Drawing-Frame-Template.sln.pic.g")


def app_icon_ico() -> Path:
    return resource_path("resources/icons/app.ico")


def app_icon_png() -> Path:
    return resource_path("resources/icons/app.png")
