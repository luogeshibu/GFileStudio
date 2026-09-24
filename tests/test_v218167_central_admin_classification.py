from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from g_file_studio.services.classification_registry_service import (
    CLASSIFICATION_FILE_NAME,
    DEFAULT_CLASSIFICATION_PATH,
    DEFAULT_ADMIN_LOCK_PATH,
    ClassificationRegistryService,
)
from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


class _WriteHandle(io.BytesIO):
    def __init__(self, files: dict[str, bytes], path: str):
        super().__init__()
        self._files = files
        self._path = path

    def close(self) -> None:
        if not self.closed:
            self._files[self._path] = self.getvalue()
        super().close()


class _ReadHandle(io.BytesIO):
    pass


class _FakeSftp:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.dirs = {"/", "/home", "/home/up8000", "/home/up8000/nari-international"}
        self.renames: list[tuple[str, str]] = []

    def stat(self, path: str):
        if path in self.dirs:
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)
        if path in self.files:
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o644)
        raise FileNotFoundError(path)

    def mkdir(self, path: str):
        self.dirs.add(path)

    def open(self, path: str, mode: str):
        if "w" in mode:
            return _WriteHandle(self.files, path)
        if path not in self.files:
            raise FileNotFoundError(path)
        return _ReadHandle(self.files[path])

    def posix_rename(self, source: str, target: str):
        self.files[target] = self.files.pop(source)
        self.renames.append((source, target))

    def rename(self, source: str, target: str):
        self.files[target] = self.files.pop(source)
        self.renames.append((source, target))

    def remove(self, path: str):
        if path not in self.files:
            raise FileNotFoundError(path)
        del self.files[path]

    def close(self):
        pass


class _FakeSsh:
    def close(self):
        pass


def test_central_registry_has_one_unambiguous_symbol_classification_file() -> None:
    assert CLASSIFICATION_FILE_NAME == "symbol_classification.json"
    assert DEFAULT_CLASSIFICATION_PATH == (
        "/home/up8000/nari-international/gfilestudio/config/symbol_classification.json"
    )
    assert "history" not in DEFAULT_CLASSIFICATION_PATH.lower()
    assert "v000" not in DEFAULT_CLASSIFICATION_PATH.lower()


def test_publish_replaces_only_symbol_classification_json(monkeypatch) -> None:
    fake = _FakeSftp()
    service = ClassificationRegistryService()
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(), fake)),
    )
    payload = {
        "markers": [
            {
                "relative_path": "breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                "file_name": "Circuit_Breaker_SMART.zwk.icn.g",
                "devref": "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART",
                "classification_marker": "CIRCUIT_BREAKER_SMART",
            }
        ]
    }
    owner = service.force_set_admin_password(
        host="172.16.21.27", port=22, username="up8000", password="pw",
        new_admin_password="Admin-123", machine_id="test-machine",
        machine_name="TEST-PC", take_over=True,
    )
    assert owner is not None
    result = service.publish(
        host="172.16.21.27", port=22, username="up8000", password="pw", payload=payload,
        machine_id=owner.machine_id,
    )
    assert result.remote_path == DEFAULT_CLASSIFICATION_PATH
    assert result.marker_count == 1
    assert set(fake.files) == {DEFAULT_CLASSIFICATION_PATH, DEFAULT_ADMIN_LOCK_PATH}
    saved = json.loads(fake.files[DEFAULT_CLASSIFICATION_PATH].decode("utf-8"))
    assert saved["owner"] == "GFileStudio"
    assert saved["markers"][0]["classification_marker"] == "CIRCUIT_BREAKER_SMART"
    assert all("v000" not in path.lower() for path in fake.files)


def test_fetch_missing_symbol_classification_has_first_deployment_message(monkeypatch) -> None:
    fake = _FakeSftp()
    monkeypatch.setattr(
        ClassificationRegistryService,
        "_connect",
        staticmethod(lambda **_kwargs: (_FakeSsh(), fake)),
    )
    with pytest.raises(FileNotFoundError, match="请由管理员首次上传"):
        ClassificationRegistryService().fetch(
            host="172.16.21.27", port=22, username="up8000", password="pw"
        )


def test_central_replace_removes_markers_missing_from_admin_payload(tmp_path: Path) -> None:
    service = RemoteSymbolLibraryService(cache_root=tmp_path)
    host = "172.16.21.27"
    root = "/home/up8000/data/graph/element"
    records = {
        "/home/up8000/data/graph/element/breaker_dis/a.g": {
            "name": "a.g",
            "remote_path": "/home/up8000/data/graph/element/breaker_dis/a.g",
            "standard_record": {"devref": "#a.g:A", "original_name": "a.g"},
            "classification_marker": "OLD_A",
        },
        "/home/up8000/data/graph/element/breaker_dis/b.g": {
            "name": "b.g",
            "remote_path": "/home/up8000/data/graph/element/breaker_dis/b.g",
            "standard_record": {"devref": "#b.g:B", "original_name": "b.g"},
            "classification_marker": "OLD_B",
        },
    }
    service._write_manifest(host, root, records)
    service._write_marker_overrides(host, root, [
        {"relative_path": "breaker_dis/a.g", "file_name": "a.g", "devref": "#a.g:A", "classification_marker": "OLD_A"},
        {"relative_path": "breaker_dis/b.g", "file_name": "b.g", "devref": "#b.g:B", "classification_marker": "OLD_B"},
    ])

    result = service.replace_classification_marker_payload(
        host=host,
        root=root,
        payload={
            "markers": [
                {
                    "relative_path": "breaker_dis/a.g",
                    "file_name": "a.g",
                    "devref": "#a.g:A",
                    "classification_marker": "NEW_A",
                }
            ]
        },
    )
    assert result == {"imported": 1, "matched": 1, "pending": 0}
    assert service.load_classification_markers(host=host, root=root) == {
        "/home/up8000/data/graph/element/breaker_dis/a.g": "NEW_A"
    }
    entries = service.load_classification_marker_entries(host=host, root=root)
    assert [row["classification_marker"] for row in entries] == ["NEW_A"]


def test_site_profile_ui_enforces_admin_publish_but_allows_central_sync() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("从服务器同步")' in source
    assert 'QPushButton("上传到服务器")' in source
    assert 'if not self._require_admin_mode("上传到服务器")' in source
    assert 'self.central_sync_button.setEnabled(not busy)' in source
    assert 'self.central_publish_button.setEnabled(self._is_admin_mode and not busy)' in source
    assert "DEFAULT_CLASSIFICATION_PATH" in source
    assert "symbol_classification.json" in source


def test_release_version_is_consistent_for_central_registry() -> None:
    import re

    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert init_match and project_match
    assert init_match.group(1) == project_match.group(1)
