from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from platformdirs import user_cache_dir


class TempWorkspaceService:
    """管理一键处理使用的隐藏中间目录。

    - 程序启动时清理上次异常退出残留；
    - 每次开始一键任务前重置当前会话目录；
    - 程序正常关闭时清理当前会话；
    - 最终输出文件永远不放在这里。
    """

    def __init__(self) -> None:
        self.cache_root = Path(user_cache_dir("GFileStudio", "NARI")) / "Cache"
        self.session_dir: Path | None = None

    def startup_cleanup(self) -> None:
        if self.cache_root.exists():
            shutil.rmtree(self.cache_root, ignore_errors=True)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self._create_session()

    def _create_session(self) -> Path:
        self.session_dir = self.cache_root / f"session_{uuid.uuid4().hex}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def reset_task_workspace(self) -> Path:
        if self.session_dir is None:
            self._create_session()
        assert self.session_dir is not None
        if self.session_dir.exists():
            for child in self.session_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def cleanup(self) -> None:
        if self.session_dir is not None:
            shutil.rmtree(self.session_dir, ignore_errors=True)
            self.session_dir = None
        # 若没有其他会话，顺便移除空的 Cache 根目录。
        try:
            self.cache_root.rmdir()
        except OSError:
            pass
