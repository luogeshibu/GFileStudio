from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Callable

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
    """返回可在 stdout/stderr 重定向期间安全调用的日志回调。

    Engine 中仍有少量 print 输出。Processor 会把 stdout/stderr 重定向到
    CallbackWriter。若外部传入的 callback 内部再次使用 print，直接调用会
    形成递归。这里在回调执行期间临时恢复原始输出流，兼容 GUI 信号、print
    和自定义日志函数。
    """

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    def safe(line: str) -> None:
        with contextlib.redirect_stdout(original_stdout), contextlib.redirect_stderr(
            original_stderr
        ):
            callback(line)

    return safe
