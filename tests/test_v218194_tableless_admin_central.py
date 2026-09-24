from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.services.classification_registry_service import (
    DEFAULT_INSTANCE_PATH,
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


def test_takeover_is_passwordless_and_increments_admin_epoch(monkeypatch) -> None:
    fake = _FakeSftp()
    ip = {"value": "172.16.21.31"}
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(ip["value"]), fake)),
    )
    service = ClassificationRegistryService()

    first = service.takeover_admin(
        host="172.16.21.27", port=22, username="up8000", password="ssh",
        machine_id="machine-a", machine_name="PC-A",
    )
    assert first.machine_id == "machine-a"
    assert first.admin_epoch == 1

    ip["value"] = "172.16.21.32"
    second = service.takeover_admin(
        host="172.16.21.27", port=22, username="up8000", password="ssh",
        machine_id="machine-b", machine_name="PC-B",
    )
    assert second.machine_id == "machine-b"
    assert second.admin_epoch == 2
    instance = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode("utf-8"))
    assert instance["last_admin"]["machine_id"] == "machine-a"


def test_stale_admin_epoch_cannot_release_new_owner(monkeypatch) -> None:
    fake = _FakeSftp()
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh("172.16.21.31"), fake)),
    )
    service = ClassificationRegistryService()
    first = service.takeover_admin(
        host="h", port=22, username="u", password="p", machine_id="same-machine", machine_name="PC"
    )
    second = service.takeover_admin(
        host="h", port=22, username="u", password="p", machine_id="same-machine", machine_name="PC"
    )
    assert second.admin_epoch == first.admin_epoch + 1
    assert service.release_admin_lease(
        host="h", port=22, username="u", password="p",
        machine_id="same-machine", lease_id=first.lease_id,
        expected_admin_epoch=first.admin_epoch,
    ) is False


def test_server_inventory_table_is_visible_but_xml_element_column_is_hidden() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self._server_inventory_table_enabled = True" in source
    assert "self.standard_table.setVisible(True)" in source
    assert "self._hidden_standard_columns = {0, 1, 2, 4, 10, 11, 12, 13, 14, 15, 16, 17, 19}" in source
    assert '"图元定义文件"' in source
    apply_start = source.index("def _apply_server_library_payload")
    apply_end = source.index("def _create_next_version_from_server", apply_start)
    apply_method = source[apply_start:apply_end]
    assert "self._server_inventory_table_enabled" in apply_method
    assert "_apply_fast_inventory_column_widths" in apply_method
    assert "auto_bind" in apply_method  # legacy business scan path is retained


def test_shutdown_does_not_release_persistent_central_admin() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = source.index("def _release_admin_lease_on_shutdown")
    end = source.index("def _require_admin_mode", start)
    method = source[start:end]
    assert "release_admin_lease(" not in method
    assert "instance.json" in method


def test_ordinary_clients_can_sync_but_central_publish_buttons_require_process_admin() -> None:
    database = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    id_page = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "def set_admin_mode(self, is_admin: bool, admin_epoch: int | None = None)" in database
    assert "self.central_publish_button.setEnabled(False)" in database
    assert "self.central_sync_button.setEnabled(True)" in database
    assert "expected_admin_epoch=self._admin_epoch" in database
    assert "def set_admin_mode(self, is_admin: bool, admin_epoch: int | None = None)" in id_page
    assert "self.central_rule_publish_button.setEnabled(False)" in id_page
    assert "expected_admin_epoch=self._admin_epoch" in id_page
    assert 'self.config_access_button = QPushButton("配置权限：普通客户端")' in main
    assert 'getattr(page, "set_admin_mode", None)' in main
