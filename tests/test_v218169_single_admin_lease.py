from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from g_file_studio.services.classification_registry_service import (
    ADMIN_LOCK_FILE_NAME,
    DEFAULT_ADMIN_LEASE_SECONDS,
    DEFAULT_ADMIN_LOCK_PATH,
    DEFAULT_CLASSIFICATION_PATH,
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
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o644)
        raise FileNotFoundError(path)

    def mkdir(self, path: str):
        self.dirs.add(path)

    def open(self, path: str, mode: str):
        if "x" in mode:
            if path in self.files:
                raise FileExistsError(path)
            return _WriteHandle(self.files, path)
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


def test_single_admin_lock_records_machine_and_ssh_source_ip(monkeypatch) -> None:
    fake = _FakeSftp()
    current_ip = {"value": "172.16.21.35"}

    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(current_ip["value"]), fake)),
    )
    service = ClassificationRegistryService()

    first = service.force_set_admin_password(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        new_admin_password="Admin-123", machine_id="machine-a",
        machine_name="JEDDAH-PC-01", take_over=True,
    )
    assert first is not None
    assert first.machine_name == "JEDDAH-PC-01"
    assert first.ip == "172.16.21.35"
    assert first.expired is False
    assert DEFAULT_ADMIN_LEASE_SECONDS == 180
    assert ADMIN_LOCK_FILE_NAME == "instance.json"
    assert DEFAULT_ADMIN_LOCK_PATH in fake.files

    current_ip["value"] = "172.16.21.36"
    with pytest.raises(AdminLeaseBusyError) as exc:
        service.acquire_admin_lease(
            host="172.16.21.27",
            port=22,
            username="up8000",
            password="pw",
            machine_id="machine-b",
            machine_name="JEDDAH-PC-02",
            admin_password="Admin-123",
        )
    assert exc.value.lease.machine_name == "JEDDAH-PC-01"
    assert exc.value.lease.ip == "172.16.21.35"

    assert service.release_admin_lease(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="pw",
        machine_id="machine-a",
        lease_id=first.lease_id,
    ) is True
    second = service.acquire_admin_lease(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="pw",
        machine_id="machine-b",
        machine_name="JEDDAH-PC-02",
        admin_password="Admin-123",
    )
    assert second.ip == "172.16.21.36"


def test_publish_requires_owned_lease_and_records_publisher(monkeypatch) -> None:
    fake = _FakeSftp()
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh("172.16.21.50"), fake)),
    )
    service = ClassificationRegistryService()
    lease = service.force_set_admin_password(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        new_admin_password="Admin-123", machine_id="machine-publisher",
        machine_name="MODEL-PC", take_over=True,
    )
    assert lease is not None
    service.publish(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="pw",
        payload={"markers": [{"file_name": "a.g", "classification_marker": "FUSE"}]},
        publisher_machine=lease.machine_name,
        publisher_ip=lease.ip,
        machine_id=lease.machine_id,
        lease_id=lease.lease_id,
    )
    payload = json.loads(fake.files[DEFAULT_CLASSIFICATION_PATH].decode("utf-8"))
    assert payload["published_by"]["machine_name"] == "MODEL-PC"
    assert payload["published_by"]["ip"] == "172.16.21.50"


def test_ui_is_compact_and_ordinary_mode_syncs_from_server() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self.access_mode_button.setText("释放管理员权限")' in source
    assert '中央 V{lease.config_version}' in source
    assert '_admin_heartbeat_timer.start()' not in source
    assert '_admin_status_timer.start()' not in source
    assert 'def _force_reset_admin_password' in source
    assert 'QTimer.singleShot(250, self._auto_sync_central_classification_once)' not in source
    assert 'QTimer.singleShot(0, self._auto_sync_central_classification)' not in source
    assert 'item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)' in source
    assert "同步服务器图元并维护图元分类。" in source
    assert "普通模式可以配置连接、同步/查看服务器图元" not in source
