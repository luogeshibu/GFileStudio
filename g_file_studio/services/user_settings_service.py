from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths


@dataclass(frozen=True)
class ResolvedDirectory:
    """文件对话框初始目录及失效目录信息。"""

    directory: Path
    missing_saved_directory: Path | None = None


class UserSettingsService:
    """保存跨页面、跨程序启动周期的最近使用目录。

    每一个页面和用途使用独立 key，例如：
    - basic/input_file_directory
    - basic/input_directory
    - basic/output_directory
    - frame/custom_template_directory
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    @staticmethod
    def fallback_directory() -> Path:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        candidates = [Path(documents) if documents else None, Path.home(), Path.cwd()]
        for candidate in candidates:
            if candidate is not None and candidate.exists() and candidate.is_dir():
                return candidate
        return Path.cwd()

    def get_directory(self, key: str) -> Path | None:
        value = str(self._settings.value(key, "") or "").strip()
        return Path(value).expanduser() if value else None

    def set_directory(self, key: str, directory: str | Path) -> None:
        if not key:
            return
        path = Path(directory).expanduser()
        self._settings.setValue(key, str(path))
        self._settings.sync()

    def clear(self, key: str) -> None:
        if key:
            self._settings.remove(key)
            self._settings.sync()

    def resolve_directory(
        self,
        key: str,
        *,
        fallback: str | Path | None = None,
    ) -> ResolvedDirectory:
        saved = self.get_directory(key)
        if saved is not None:
            if saved.exists() and saved.is_dir():
                return ResolvedDirectory(saved)
            self.clear(key)
            fallback_dir = self._valid_fallback(fallback)
            return ResolvedDirectory(fallback_dir, saved)
        return ResolvedDirectory(self._valid_fallback(fallback))

    def _valid_fallback(self, fallback: str | Path | None) -> Path:
        if fallback is not None:
            path = Path(fallback).expanduser()
            if path.is_file():
                path = path.parent
            if path.exists() and path.is_dir():
                return path
            parent = path.parent
            if parent.exists() and parent.is_dir():
                return parent
        return self.fallback_directory()
