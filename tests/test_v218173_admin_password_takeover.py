from __future__ import annotations

import io
import json
import stat
from types import SimpleNamespace

import pytest

from g_file_studio.services.classification_registry_service import (
    DEFAULT_INSTANCE_PATH,
    AdminLeaseBusyError,
    ClassificationRegistryService,
)


class _WriteHandle(io.BytesIO):
    def __init__(self, files: dict[str, bytes], path: str):
        super().__init__()
        self._files = files
        self._path = path

    def close(self) -> None:
        if not self.closed:
            self._files[self._path] = self.getvalue()
        super().close()


class _FakeSock:
    def __init__(self, ip: str):
        self.ip = ip

    def getsockname(self):
        return self.ip, 54321


class _FakeTransport:
    def __init__(self, ip: str):
        self.sock = _FakeSock(ip)


class _FakeSsh:
    def __init__(self, ip: str):
        self._transport = _FakeTransport(ip)

    def get_transport(self):
        return self._transport

    def close(self):
        pass


class _FakeSftp:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.dirs = {"/", "/home", "/home/up8000", "/home/up8000/nari-international"}

    def stat(self, path: str):
        if path in self.dirs:
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)
        if path in self.files:
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o600)
        raise FileNotFoundError(path)

    def mkdir(self, path: str):
        self.dirs.add(path)

    def chmod(self, _path: str, _mode: int):
        pass

    def open(self, path: str, mode: str):
        if "w" in mode:
            return _WriteHandle(self.files, path)
        if path not in self.files:
            raise FileNotFoundError(path)
        return io.BytesIO(self.files[path])

    def posix_rename(self, source: str, target: str):
        self.files[target] = self.files.pop(source)

    def rename(self, source: str, target: str):
        self.files[target] = self.files.pop(source)

    def remove(self, path: str):
        if path not in self.files:
            raise FileNotFoundError(path)
        del self.files[path]

    def close(self):
        pass


def test_central_admin_password_is_hashed_and_can_force_takeover(monkeypatch) -> None:
    fake = _FakeSftp()
    current_ip = {"value": "172.16.22.10"}
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(current_ip["value"]), fake)),
    )
    service = ClassificationRegistryService()

    lease = service.force_set_admin_password(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="ssh-password",
        new_admin_password="Admin-123",
        machine_id="machine-a",
        machine_name="PC-A",
        take_over=True,
    )
    assert lease is not None
    assert lease.machine_id == "machine-a"

    raw_instance = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode("utf-8"))
    assert raw_instance["admin_auth"]["initialized"] is True
    assert raw_instance["admin_auth"]["password_hash"]
    assert raw_instance["admin_auth"]["salt"]
    assert "Admin-123" not in fake.files[DEFAULT_INSTANCE_PATH].decode("utf-8")

    current_ip["value"] = "172.16.22.20"
    with pytest.raises(AdminLeaseBusyError):
        service.acquire_admin_lease(
            host="172.16.21.27", port=22, username="up8000", password="ssh-password",
            machine_id="machine-b", machine_name="PC-B", admin_password="Admin-123",
            force_takeover=False,
        )

    takeover = service.acquire_admin_lease(
        host="172.16.21.27", port=22, username="up8000", password="ssh-password",
        machine_id="machine-b", machine_name="PC-B", admin_password="Admin-123",
        force_takeover=True,
    )
    assert takeover.machine_id == "machine-b"
    assert takeover.ip == "172.16.22.20"

    with pytest.raises(PermissionError):
        service.acquire_admin_lease(
            host="172.16.21.27", port=22, username="up8000", password="ssh-password",
            machine_id="machine-c", machine_name="PC-C", admin_password="wrong-password",
            force_takeover=True,
        )


def test_admin_ui_uses_explicit_passwordless_takeover_and_lightweight_owner_check() -> None:
    page = open("g_file_studio/ui/pages/site_profile_page.py", encoding="utf-8").read()
    main = open("g_file_studio/ui/main_window.py", encoding="utf-8").read()
    assert "ClassificationRegistryService().takeover_admin(" in page
    assert "_admin_ownership_timer.setInterval(10_000)" in page
    assert "_admin_ownership_timer.start()" in page
    assert "抢占 Admin 权限" in main
    assert "强制设置管理员密码" not in main
    assert "不会自动同步或发布" in main
