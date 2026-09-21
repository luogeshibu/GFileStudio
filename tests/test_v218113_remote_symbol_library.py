from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import g_file_studio.services.remote_symbol_library as remote_library_module
import g_file_studio.services.site_profile_service as site_profile_service_module
from g_file_studio.services.remote_g_source import RemoteGFile
from g_file_studio.services.remote_symbol_library import (
    DEFAULT_REMOTE_SYMBOL_ROOT,
    RemoteSymbolLibraryService,
)
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _icon(path: Path, *, width: int = 30, pin_y: int = 4, body_id: str = "CB") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><CBreakerDis id="{body_id}" w="{width}" h="30" AlignCenter="15,15">'
        f'<pin id="p1" index="1" cx="15" cy="{pin_y}"/>'
        '<pin id="p2" index="2" cx="15" cy="26"/>'
        '</CBreakerDis></root>',
        encoding="utf-8",
    )
    return path


class _FakeReadOnlySshClient:
    records: dict[str, tuple[Path, int]] = {}

    def __init__(self, host: str, port: int, username: str, password: str, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @classmethod
    def _remote(cls, remote_path: str) -> RemoteGFile:
        source, mtime = cls.records[remote_path]
        return RemoteGFile(
            name=Path(remote_path).name,
            remote_path=remote_path,
            size=source.stat().st_size,
            mtime_epoch=int(mtime),
        )

    def list_g_files_recursive(self, root: str, *, max_files: int = 20000) -> list[RemoteGFile]:
        prefix = root.rstrip("/") + "/"
        return [self._remote(path) for path in sorted(self.records) if path.startswith(prefix)][:max_files]

    def stat_file(self, remote_path: str) -> RemoteGFile:
        return self._remote(remote_path)

    def download_file(self, remote_path: str, local_path: str) -> None:
        source, _mtime = self.records[remote_path]
        shutil.copyfile(source, local_path)


def test_remote_symbol_library_exact_match_incremental_cache_and_change(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    name = "Circuit_Breaker_SMART.zwk.icn.g"
    remote_path = f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{name}"
    source = _icon(tmp_path / "remote" / name, width=30, pin_y=4, body_id="Circuit_Breaker_SMART")
    _FakeReadOnlySshClient.records = {remote_path: (source, 100)}

    service = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    first = service.sync_expected(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="secret",
        expected_names=[name],
    )
    assert first.downloaded == 1
    assert first.reused == 0
    assert first.unmatched_names == []
    assert first.conflicts == {}
    record = first.matched_records[name]
    assert record["standard_source"] == "server"
    assert record["original_name"] == name
    assert record["remote_path"] == remote_path
    assert record["devref"] == f"#{name}:Circuit_Breaker_SMART"
    assert Path(str(record["cache_path"])).is_file()

    second = service.sync_expected(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="secret",
        expected_names=[name],
    )
    assert second.downloaded == 0
    assert second.reused == 1
    assert second.changed_names == []
    old_hash = str(second.matched_records[name]["sha256"])

    # A metadata-only touch is irrelevant to this catalog manager. The filename
    # still exists, so the cached definition and its classification are reused.
    _FakeReadOnlySshClient.records[remote_path] = (source, 101)
    touched = service.sync_expected(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="secret",
        expected_names=[name],
    )
    assert touched.downloaded == 0
    assert touched.reused == 1
    assert touched.changed_names == []
    assert touched.updated_files[0]["name"] == name
    assert touched.updated_files[0]["mtime_epoch"] == 101
    assert str(touched.matched_records[name]["sha256"]) == old_hash

    _icon(source, width=36, pin_y=6, body_id="Circuit_Breaker_SMART")
    _FakeReadOnlySshClient.records[remote_path] = (source, 102)
    third = service.sync_expected(
        host="172.16.21.27",
        port=22,
        username="up8000",
        password="secret",
        expected_names=[name],
    )
    assert third.downloaded == 0
    assert third.reused == 1
    assert third.changed_names == []
    assert third.updated_files[0]["mtime_epoch"] == 102
    assert str(third.matched_records[name]["sha256"]) == old_hash
    assert third.matched_records[name]["width"] == 30


def test_remote_symbol_library_rejects_different_content_duplicate_basename(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    name = "Load_Breaker_Switch_SMART.zwk.icn.g"
    left = _icon(tmp_path / "left" / name, width=28, body_id="LBS")
    right = _icon(tmp_path / "right" / name, width=40, body_id="LBS")
    left_path = f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{name}"
    right_path = f"{DEFAULT_REMOTE_SYMBOL_ROOT}/backup/{name}"
    _FakeReadOnlySshClient.records = {left_path: (left, 200), right_path: (right, 200)}

    service = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    result = service.sync_expected(
        host="server",
        port=22,
        username="user",
        password="pass",
        expected_names=[name],
    )
    assert name in result.conflicts
    assert name not in result.matched_records
    assert len(result.conflicts[name]) == 2
    assert len({row["sha256"] for row in result.conflicts[name]}) == 2


def test_remote_symbol_library_parse_failure_is_isolated_and_not_auto_matched(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    bad_name = "Broken_Status.zt.icn.g"
    good_name = "Circuit_Breaker_SMART.zwk.icn.g"
    bad = tmp_path / "remote" / bad_name
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("<not-a-valid-icon>", encoding="utf-8")
    good = _icon(tmp_path / "remote" / good_name, body_id="Circuit_Breaker_SMART")
    _FakeReadOnlySshClient.records = {
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/status/{bad_name}": (bad, 400),
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{good_name}": (good, 400),
    }
    service = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    result = service.sync_expected(
        host="server", port=22, username="user", password="pass", expected_names=[bad_name, good_name]
    )
    assert bad_name in result.errors
    assert bad_name not in result.matched_records
    assert good_name in result.matched_records


def test_remote_symbol_library_restores_complete_inventory_after_restart(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    bad_name = "Broken_Status.zt.icn.g"
    good_name = "Circuit_Breaker_SMART.zwk.icn.g"
    bad = tmp_path / "remote" / bad_name
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("<not-a-valid-icon>", encoding="utf-8")
    good = _icon(tmp_path / "remote" / good_name, body_id="Circuit_Breaker_SMART")
    _FakeReadOnlySshClient.records = {
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/status/{bad_name}": (bad, 500),
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{good_name}": (good, 500),
    }
    service = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    result = service.sync_all(
        host="server", port=22, username="user", password="pass"
    )
    assert result.scanned_remote_files == 2
    assert len(result.server_file_records) == 2
    assert len(result.matched_records) == 1

    restarted = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    snapshot = restarted.load_cached_sync_snapshot(
        host="server", root=DEFAULT_REMOTE_SYMBOL_ROOT
    )
    assert int(snapshot["scanned_remote_files"]) == 2
    assert len(snapshot["server_file_records"]) == 2
    assert len(snapshot["matched_records"]) == 1
    assert any(
        row.get("name") == bad_name and row.get("sync_status") == "ERROR"
        for row in snapshot["server_file_records"]
    )


def test_remote_symbol_library_restores_classification_marker_after_restart(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    name = "Fuse_NON_SMART.zwk.icn.g"
    remote_path = f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{name}"
    source = _icon(tmp_path / "remote" / name, body_id="Fuse_NON_SMART")
    _FakeReadOnlySshClient.records = {remote_path: (source, 550)}

    service = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    service.sync_all(host="server", port=22, username="user", password="pass")
    assert service.update_classification_marker(
        host="server",
        root=DEFAULT_REMOTE_SYMBOL_ROOT,
        remote_path=remote_path,
        marker="FUSE",
    )

    restarted = RemoteSymbolLibraryService(cache_root=tmp_path / "cache")
    snapshot = restarted.load_cached_sync_snapshot(
        host="server", root=DEFAULT_REMOTE_SYMBOL_ROOT
    )
    row = next(item for item in snapshot["server_file_records"] if item["name"] == name)
    assert row["classification_marker"] == "FUSE"
    assert snapshot["matched_records"][name]["classification_marker"] == "FUSE"


def test_remote_symbol_library_counts_only_files_with_exact_g_extension(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(remote_library_module, "ReadOnlySshClient", _FakeReadOnlySshClient)
    good_name = "Circuit_Breaker_SMART.zwk.icn.g"
    preview_name = good_name + ".png"
    good = _icon(tmp_path / "remote" / good_name, body_id="Circuit_Breaker_SMART")
    preview = tmp_path / "remote" / preview_name
    preview.write_bytes(b"preview")
    _FakeReadOnlySshClient.records = {
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{good_name}": (good, 600),
        f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{preview_name}": (preview, 600),
    }
    result = RemoteSymbolLibraryService(cache_root=tmp_path / "cache").sync_all(
        host="server", port=22, username="user", password="pass"
    )
    assert result.scanned_remote_files == 1
    assert [row["name"] for row in result.server_file_records] == [good_name]


def test_locked_profile_server_update_creates_unlocked_next_version_and_preserves_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(site_profile_service_module, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    service = SiteProfileService(tmp_path / "profiles.json")
    name = "Circuit_Breaker_SMART.zwk.icn.g"
    old_icon = _icon(tmp_path / "old" / name, width=30, body_id="Circuit_Breaker_SMART")
    new_icon = _icon(tmp_path / "new" / name, width=42, body_id="Circuit_Breaker_SMART")
    old_record = service.prepare_standard_file_records([old_icon])[0]
    new_record = dict(service.prepare_standard_file_records([new_icon])[0])
    new_record.update({
        "standard_source": "server",
        "remote_host": "172.16.21.27",
        "remote_root": DEFAULT_REMOTE_SYMBOL_ROOT,
        "remote_path": f"{DEFAULT_REMOTE_SYMBOL_ROOT}/breaker_dis/{name}",
        "remote_mtime": 300,
    })
    saved = service.upsert(SiteSmartProfile(
        profile_name="JEDDAH",
        site_name="Jeddah",
        smart_breaker_devref=str(old_record["devref"]),
        smart_lbs_devref="",
        managed_standard_files=[old_record],
    ))
    locked = service.set_locked(saved.profile_name, True)
    assert locked.profile_version == 1 and locked.locked is True

    next_profile = service.create_next_version_from_server_records("JEDDAH", [new_record])
    assert next_profile.profile_version == 2
    assert next_profile.locked is False
    assert len(next_profile.managed_standard_files) == 1
    current_record = next_profile.managed_standard_files[0]
    assert current_record["standard_source"] == "server"
    assert current_record["sha256"] == new_record["sha256"]
    assert current_record["width"] == 42

    archived = service.get_profile_version("JEDDAH", 1)
    assert archived is not None
    assert archived.locked is True
    assert archived.managed_standard_files[0]["sha256"] == old_record["sha256"]


def test_v218113_ui_wires_read_only_server_library_and_locked_version_fork():
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    remote = Path("g_file_studio/services/remote_symbol_library.py").read_text(encoding="utf-8")
    ssh = Path("g_file_studio/services/remote_g_source.py").read_text(encoding="utf-8")
    assert 'DEFAULT_REMOTE_SYMBOL_ROOT = "/home/up8000/data/graph/element"' in remote
    assert "_list_g_files_recursive" in remote
    assert "listdir_attr" in remote
    assert 'QGroupBox("服务器标准图元库（只读自动同步）")' in page
    assert 'QPushButton("检查 / 同步服务器图元库")' in page
    assert 'QPushButton("基于当前版本创建新版本")' in page
    assert "5 * 60 * 1000" in page
    assert "create_next_version_from_server_records" in page
    assert "当前 ACTIVE 已锁定" in page
    assert "standard_source" in remote
    assert "download_file" in remote
    # The server client exposed to this feature remains read-only: it lists/stats/downloads only.
    assert ".put(" not in remote
    assert ".remove(" not in remote
    assert ".rename(" not in remote
