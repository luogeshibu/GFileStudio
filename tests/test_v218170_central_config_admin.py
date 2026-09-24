from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from g_file_studio.services.classification_registry_service import (
    CLASSIFICATION_FILE_NAME,
    DATABASE_FILE_NAME,
    DEFAULT_CLASSIFICATION_PATH,
    DEFAULT_CONFIG_DIR,
    DEFAULT_DATABASE_PATH,
    DEFAULT_FILE_SERVER_PATH,
    DEFAULT_ID_RULES_PATH,
    DEFAULT_INSTANCE_PATH,
    FILE_SERVER_FILE_NAME,
    INSTANCE_FILE_NAME,
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
        return self.ip, 44444


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
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700)
        if path in self.files:
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o600)
        raise FileNotFoundError(path)

    def mkdir(self, path: str):
        self.dirs.add(path)

    def chmod(self, path: str, mode: int):
        del path, mode

    def open(self, path: str, mode: str):
        if "w" in mode or "x" in mode:
            if "x" in mode and path in self.files:
                raise FileExistsError(path)
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


def _service(monkeypatch, ip="172.16.22.229"):
    fake = _FakeSftp()
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(ip), fake)),
    )
    return ClassificationRegistryService(), fake


def test_server_layout_matches_shared_config_model() -> None:
    assert DEFAULT_CONFIG_DIR == "/home/up8000/nari-international/gfilestudio/config"
    assert INSTANCE_FILE_NAME == "instance.json"
    assert CLASSIFICATION_FILE_NAME == "symbol_classification.json"
    assert DATABASE_FILE_NAME == "database.json"
    assert FILE_SERVER_FILE_NAME == "file_server.json"
    assert DEFAULT_INSTANCE_PATH.endswith("/config/instance.json")
    assert DEFAULT_CLASSIFICATION_PATH.endswith("/config/symbol_classification.json")
    assert DEFAULT_DATABASE_PATH.endswith("/config/database.json")
    assert DEFAULT_FILE_SERVER_PATH.endswith("/config/file_server.json")


def test_instance_json_is_single_admin_source_of_truth(monkeypatch) -> None:
    service, fake = _service(monkeypatch)
    first = service.force_set_admin_password(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        new_admin_password="Admin-123", machine_id="NARI-LUOGESHIBU-fdc7d56f6402",
        machine_name="NARI-LUOGESHIBU", take_over=True,
    )
    assert first is not None
    instance = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode())
    assert instance["admin_status"] == "active"
    assert instance["admin_machine_id"] == "NARI-LUOGESHIBU-fdc7d56f6402"
    assert instance["admin_machine_name"] == "NARI-LUOGESHIBU"
    assert instance["admin_ip"] == "172.16.22.229"
    assert instance["config_version"] == 0
    assert instance["files"] == {
        "instance": "instance.json",
        "symbol_classification": "symbol_classification.json",
        "database": "database.json",
        "file_server": "file_server.json",
        "id_rules": "id_rules.json",
    }
    with pytest.raises(AdminLeaseBusyError):
        service.acquire_admin_lease(
            host="172.16.21.27", port=22, username="up8000", password="pw",
            machine_id="other-machine", machine_name="OTHER-PC",
            admin_password="Admin-123",
        )
    assert service.release_admin_lease(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        machine_id=first.machine_id, lease_id=first.lease_id,
    )
    released = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode())
    assert released["admin_status"] == "released"
    assert released["admin_machine_id"] == ""


def test_admin_publishes_database_file_server_and_classification(monkeypatch) -> None:
    service, fake = _service(monkeypatch)
    owner = service.force_set_admin_password(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        new_admin_password="Admin-123", machine_id="machine-a",
        machine_name="ADMIN-PC", take_over=True,
    )
    assert owner is not None
    result = service.publish_connection_configs(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        machine_id=owner.machine_id,
        database={"username":"d5000","password":"secret","host":"172.16.21.45","port":1521,"service_name":"jedup8000"},
        file_server={"host":"172.16.21.27","port":22,"username":"up8000","password":"ssh-secret","business_g_directory":"/home/up8000/data/graph/display/sln","symbol_library_root":"/home/up8000/data/graph/element"},
    )
    assert result["instance"]["config_version"] == 1
    assert DEFAULT_DATABASE_PATH in fake.files
    assert DEFAULT_FILE_SERVER_PATH in fake.files
    service.publish(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        payload={"markers":[{"file_name":"a.g","classification_marker":"FUSE"}]},
        publisher_machine="ADMIN-PC", publisher_ip="172.16.22.229",
        machine_id=owner.machine_id,
    )
    instance = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode())
    assert instance["config_version"] == 2
    assert DEFAULT_CLASSIFICATION_PATH in fake.files

    service.publish_id_rules(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        machine_id=owner.machine_id,
        machine_name="ADMIN-PC",
        payload={
            "version": 6,
            "rules": [
                {
                    "tag": "Text",
                    "prefix": "8",
                    "total_length": 7,
                    "enabled": True,
                    "verified": True,
                    "note": "central test",
                }
            ],
            "deleted_tags": [],
        },
    )
    instance = json.loads(fake.files[DEFAULT_INSTANCE_PATH].decode())
    assert instance["config_version"] == 3
    assert DEFAULT_ID_RULES_PATH in fake.files
    fetched = service.fetch_id_rules(
        host="172.16.21.27", port=22, username="up8000", password="pw"
    )
    assert fetched["id_rules"]["rules"][0]["tag"] == "Text"


def test_workstations_keep_local_config_until_manual_sync() -> None:
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    finish = page[page.index("def _finish_initial_load"):page.index("def _toggle_admin_mode")]
    assert "_auto_sync_central_classification_once" not in finish
    assert "item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)" in page
    assert "self.save_classification_button.setEnabled(not busy)" in page
    assert "self.central_publish_button.setEnabled(self._is_admin_mode" in page
    db_page = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("从中央同步")' in db_page
    assert 'QPushButton("发布到中央")' in db_page
    assert "fetch_connection_configs" in db_page
    assert "publish_connection_configs" in db_page
