from __future__ import annotations

import configparser
import threading
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir


@dataclass(frozen=True)
class ResolvedDirectory:
    """文件对话框初始目录及失效目录信息。"""

    directory: Path
    missing_saved_directory: Path | None = None


@dataclass(frozen=True)
class RestoredPath:
    """从 INI 恢复的完整路径及其有效性。"""

    path: Path | None
    missing_path: Path | None = None


class UserSettingsService:
    """使用独立 INI 文件保存跨页面、跨启动周期的用户路径。

    默认配置文件：
    ``AppData/Local/NARI/GFileStudio/Config/user_settings.ini``

    key 使用 ``section/name`` 形式，例如：
    - ``basic/input_mode``
    - ``basic/single_file_path``
    - ``basic/output_directory``
    """

    def __init__(self, ini_path: str | Path | None = None) -> None:
        base = Path(user_config_dir("GFileStudio", "NARI")) / "Config"
        self.ini_path = Path(ini_path) if ini_path is not None else base / "user_settings.ini"
        self.ini_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._config = configparser.ConfigParser(interpolation=None)
        self._config.optionxform = str
        self._load()

    def _load(self) -> None:
        with self._lock:
            self._config.clear()
            if self.ini_path.is_file():
                self._config.read(self.ini_path, encoding="utf-8")

    @staticmethod
    def _split_key(key: str) -> tuple[str, str]:
        text = str(key).strip().strip("/")
        if not text:
            raise ValueError("设置 key 不能为空。")
        if "/" in text:
            section, option = text.split("/", 1)
        else:
            section, option = "general", text
        return section or "general", option

    def sync(self) -> None:
        with self._lock:
            self.ini_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.ini_path.with_suffix(self.ini_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as file:
                self._config.write(file)
            tmp.replace(self.ini_path)

    def get_value(self, key: str, default: str = "") -> str:
        section, option = self._split_key(key)
        with self._lock:
            return self._config.get(section, option, fallback=default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get_value(key, "true" if default else "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int = 0) -> int:
        """读取整数设置；内容损坏或为空时安全回退到默认值。"""
        try:
            return int(self.get_value(key, str(default)).strip())
        except (TypeError, ValueError):
            return default

    def set_value(self, key: str, value: object) -> None:
        section, option = self._split_key(key)
        with self._lock:
            if not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, option, str(value))
            self.sync()

    def clear(self, key: str) -> None:
        section, option = self._split_key(key)
        with self._lock:
            if self._config.has_section(section):
                self._config.remove_option(section, option)
                if not self._config.items(section):
                    self._config.remove_section(section)
                self.sync()

    def get_path(self, key: str) -> Path | None:
        value = self.get_value(key).strip()
        return Path(value).expanduser() if value else None

    def set_path(self, key: str, path: str | Path) -> None:
        self.set_value(key, str(Path(path).expanduser()))

    # 兼容旧调用名称。
    get_directory = get_path
    set_directory = set_path

    @staticmethod
    def fallback_directory() -> Path:
        candidates = [Path.home() / "Documents", Path.home(), Path.cwd()]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return Path.cwd()

    @classmethod
    def closest_existing_directory(cls, path: str | Path | None) -> Path:
        if path is None:
            return cls.fallback_directory()
        candidate = Path(path).expanduser()
        if candidate.is_file():
            candidate = candidate.parent
        elif candidate.suffix and not candidate.exists():
            candidate = candidate.parent
        while True:
            if candidate.exists() and candidate.is_dir():
                return candidate
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
        return cls.fallback_directory()

    def restore_path(self, key: str, *, expect: str) -> RestoredPath:
        """恢复完整路径。

        expect 可取 ``file`` 或 ``directory``。路径失效时会删除该完整路径记录，
        但不会删除单独保存的最近浏览目录，便于文件对话框回退到仍存在的父目录。
        """
        path = self.get_path(key)
        if path is None:
            return RestoredPath(None)
        valid = path.is_file() if expect == "file" else path.is_dir()
        if valid:
            return RestoredPath(path)
        self.clear(key)
        return RestoredPath(None, path)

    def resolve_directory(
        self,
        key: str,
        *,
        fallback: str | Path | None = None,
    ) -> ResolvedDirectory:
        saved = self.get_path(key)
        if saved is not None:
            if saved.exists() and saved.is_dir():
                return ResolvedDirectory(saved)
            self.clear(key)
            return ResolvedDirectory(
                self.closest_existing_directory(fallback or saved),
                saved,
            )
        return ResolvedDirectory(self.closest_existing_directory(fallback))
