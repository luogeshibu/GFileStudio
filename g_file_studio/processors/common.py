from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Callable
from pathlib import Path

from g_file_studio.models import InputMode

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int], None]


class CallbackWriter(io.TextIOBase):
    def __init__(self, callback: LogCallback) -> None:
        self.callback = callback
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.callback(line)
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            self.callback(self._buffer.rstrip())
        self._buffer = ""


def redirect_safe_callback(callback: LogCallback) -> LogCallback:
    """返回可在 stdout/stderr 重定向期间安全调用的日志回调。"""

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    def safe(line: str) -> None:
        with contextlib.redirect_stdout(original_stdout), contextlib.redirect_stderr(
            original_stderr
        ):
            callback(line)

    return safe


def discover_g_inputs(
    source_path: Path,
    input_mode: InputMode,
    *,
    compound_suffix_only: bool = False,
) -> list[Path]:
    """按输入模式发现 G 文件。

    单文件模式只处理用户选择的那个文件；目录模式只扫描目录第一层，不递归。
    compound_suffix_only=True 时要求文件名以 .sln.pic.g 结尾，否则只要求 .g。
    """

    source_path = Path(source_path)

    def valid(path: Path) -> bool:
        if not path.is_file():
            return False
        if compound_suffix_only:
            return path.name.lower().endswith(".sln.pic.g")
        return path.suffix.lower() == ".g"

    if input_mode == InputMode.SINGLE_FILE:
        if not source_path.is_file():
            raise FileNotFoundError(f"输入文件不存在：{source_path}")
        if not valid(source_path):
            expected = ".sln.pic.g" if compound_suffix_only else ".g"
            raise ValueError(f"输入文件必须以 {expected} 结尾：{source_path.name}")
        return [source_path]

    if not source_path.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{source_path}")

    files = sorted(
        (path for path in source_path.iterdir() if valid(path)),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        expected = ".sln.pic.g" if compound_suffix_only else ".g"
        raise FileNotFoundError(f"输入目录中没有以 {expected} 结尾的文件：{source_path}")
    return files
