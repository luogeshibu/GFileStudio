from __future__ import annotations

import copy
import json
import shutil
import zipfile
from pathlib import Path

import pytest

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


REMOTE_ROOT = "/home/up8000/data/graph/element"


def _icon(path: Path, *, body_id: str, width: int, height: int = 30, pin_y: int = 4) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><CBreakerDis id="{body_id}" w="{width}" h="{height}" AlignCenter="{width/2:g},{height/2:g}">'
        f'<pin id="p1" index="1" cx="{width/2:g}" cy="{pin_y}"/>'
        f'<pin id="p2" index="2" cx="{width/2:g}" cy="{height-pin_y}"/>'
        '</CBreakerDis></root>',
        encoding="utf-8",
    )
    return path


def _server_record(service: SiteProfileService, path: Path, relative: str) -> dict[str, object]:
    row = dict(service.prepare_standard_file_records([path])[0])
    row.update({
        "standard_source": "server",
        "remote_host": "172.16.21.27",
        "remote_root": REMOTE_ROOT,
        "remote_path": f"{REMOTE_ROOT}/{relative}",
        "remote_size": path.stat().st_size,
        "remote_mtime": 100,
        "cache_path": str(path),
        "original_source": str(path),
    })
    return row


def _profile(records: list[dict[str, object]]) -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="JEDDAH STANDARD",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        managed_standard_files=records,
        custom_symbols=[
            {
                "uid": f"row-{idx}",
                "scope": "ANY",
                "role": f"Symbol {idx}",
                "element_tag": str(row["element_tag"]),
                "standard_devref": str(row["devref"]),
                "source_file": str(row["original_name"]),
                "enabled": True,
            }
            for idx, row in enumerate(records, 1)
        ],
    )


def test_git_style_repository_freezes_same_name_revisions_and_rebuilds_element_tree(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    service = SiteProfileService(tmp_path / "profiles.json")

    same_name = "Circuit_Breaker_SMART.zwk.icn.g"
    cb = _icon(tmp_path / "server-cache" / same_name, body_id="Circuit_Breaker_SMART", width=30)
    ground = _icon(tmp_path / "server-cache" / "Ground.g", body_id="Ground", width=20)
    v1_records = [
        _server_record(service, cb, f"breaker_dis/{same_name}"),
        _server_record(service, ground, "grounddisconnector/Ground.g"),
    ]
    v1 = service.upsert(_profile(v1_records))
    assert v1.profile_version == 1
    v1_hash = next(row["sha256"] for row in v1.managed_standard_files if row["original_name"] == same_name)

    # The server overwrites the same basename with a new body geometry.  Same name,
    # different bytes/hash => a distinct immutable symbol revision.
    _icon(cb, body_id="Circuit_Breaker_SMART", width=36, pin_y=6)
    v2_cb = _server_record(service, cb, f"breaker_dis/{same_name}")
    v2_ground = _server_record(service, ground, "grounddisconnector/Ground.g")
    draft = _profile([v2_cb, v2_ground])
    v2 = service.upsert(draft)
    assert v2.profile_version == 2
    v2_hash = next(row["sha256"] for row in v2.managed_standard_files if row["original_name"] == same_name)
    assert v2_hash != v1_hash

    repo = service.repository
    assert repo.object_path(str(v1_hash)).is_file()
    assert repo.object_path(str(v2_hash)).is_file()
    m1 = repo.load_manifest("JEDDAH STANDARD", 1)
    m2 = repo.load_manifest("JEDDAH STANDARD", 2)
    assert m1 and m2
    assert {row["relative_path"] for row in m1["entries"]} == {
        f"breaker_dis/{same_name}", "grounddisconnector/Ground.g"
    }

    # Simulate the real risk: upstream/cache and legacy Standards copies disappear.
    shutil.rmtree(tmp_path / "server-cache")
    standards = user_data / "Standards"
    shutil.rmtree(standards, ignore_errors=True)

    old = service.get_profile_version("JEDDAH STANDARD", 1)
    new = service.get_profile_version("JEDDAH STANDARD", 2)
    assert old is not None and new is not None
    assert service.verify_version_repository("JEDDAH STANDARD", 1).ok
    assert service.verify_version_repository("JEDDAH STANDARD", 2).ok

    out_old = service.export_version_element("JEDDAH STANDARD", 1, tmp_path / "export-v1")
    out_new = service.export_version_element("JEDDAH STANDARD", 2, tmp_path / "export-v2")
    assert out_old == tmp_path / "export-v1" / "element"
    assert (out_old / "breaker_dis" / same_name).is_file()
    assert (out_old / "grounddisconnector" / "Ground.g").is_file()
    assert 'w="30"' in (out_old / "breaker_dis" / same_name).read_text(encoding="utf-8")
    assert 'w="36"' in (out_new / "breaker_dis" / same_name).read_text(encoding="utf-8")

    zip_path = service.export_version_element(
        "JEDDAH STANDARD", 1, tmp_path / "Jeddah_V1_element.zip", zip_output=True
    )
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert f"element/breaker_dis/{same_name}" in names
    assert "element/grounddisconnector/Ground.g" in names


def test_historical_export_never_substitutes_current_server_same_name(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    service = SiteProfileService(tmp_path / "profiles.json")
    name = "Load_Breaker_Switch_SMART.zwk.icn.g"
    source = _icon(tmp_path / "cache" / name, body_id="LBS", width=28)
    record = _server_record(service, source, f"breaker_dis/{name}")
    saved = service.upsert(_profile([record]))
    blob_hash = str(saved.managed_standard_files[0]["sha256"])
    blob = service.repository.object_path(blob_hash)
    assert blob.is_file()

    # Same server path now contains new bytes, but the frozen historical object is
    # deliberately removed to prove export refuses substitution instead of reading
    # upstream/current bytes.
    _icon(source, body_id="LBS", width=44)
    blob.unlink()
    result = service.verify_version_repository(saved.profile_name, 1)
    assert result.ok is False
    assert result.missing
    with pytest.raises(ValueError, match="完整性校验失败"):
        service.export_version_element(saved.profile_name, 1, tmp_path / "bad-export")
    assert not (tmp_path / "bad-export" / "element" / "breaker_dis" / name).exists()


def test_version_manifest_is_immutable_and_history_is_not_trimmed(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    service = SiteProfileService(tmp_path / "profiles.json")
    source = _icon(tmp_path / "cache" / "same.g", body_id="SAME", width=20)
    record = _server_record(service, source, "breaker_dis/same.g")
    current = service.upsert(_profile([record]))

    # Create >20 revisions; unlike the previous bounded history, Git-style history
    # must keep every formal version reachable.
    for width in range(21, 44):
        _icon(source, body_id="SAME", width=width)
        rec = _server_record(service, source, "breaker_dis/same.g")
        current = service.upsert(_profile([rec]))
    assert current.profile_version == 24
    versions = service.load_profile_versions(current.profile_name)
    assert [item.profile_version for item in versions] == list(range(1, 25))
    assert service.repository.load_manifest(current.profile_name, 1) is not None
    assert service.repository.load_manifest(current.profile_name, 24) is not None


def test_symbol_standard_ui_exposes_repository_integrity_and_full_element_export():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'addAction("查看版本库详情")' in source
    assert 'addAction("验证版本完整性")' in source
    assert 'addAction("导出该版本完整 element 目录")' in source
    assert 'addAction("导出该版本完整 element ZIP")' in source
    assert "历史版本导出/恢复只读取本地冻结对象" in source
