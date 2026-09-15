from __future__ import annotations

from pathlib import Path

import pytest

import g_file_studio.services.site_profile_service as service_module
import g_file_studio.services.symbol_standard_repository as repository_module
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


REMOTE_ROOT = "/home/up8000/data/graph/element"


def _icon(path: Path, *, width: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><CBreakerDis id="CB" w="{width}" h="30" AlignCenter="{width/2:g},15">'
        f'<pin id="p1" index="1" cx="{width/2:g}" cy="4"/>'
        f'<pin id="p2" index="2" cx="{width/2:g}" cy="26"/>'
        '</CBreakerDis></root>',
        encoding="utf-8",
    )
    return path


def _record(service: SiteProfileService, source: Path) -> dict[str, object]:
    row = dict(service.prepare_standard_file_records([source])[0])
    row.update(
        {
            "standard_source": "server",
            "remote_host": "172.16.21.27",
            "remote_root": REMOTE_ROOT,
            "remote_path": f"{REMOTE_ROOT}/breaker_dis/{source.name}",
            "remote_size": source.stat().st_size,
            "remote_mtime": 100,
            "cache_path": str(source),
            "original_source": str(source),
        }
    )
    return row


def _profile(record: dict[str, object]) -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name="JEDDAH",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        managed_standard_files=[record],
        custom_symbols=[
            {
                "uid": "cb",
                "scope": "ANY",
                "role": "Circuit Breaker",
                "element_tag": str(record["element_tag"]),
                "standard_devref": str(record["devref"]),
                "source_file": str(record["original_name"]),
                "enabled": True,
            }
        ],
    )


def test_delete_one_archived_version_preserves_other_versions_and_objects(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    service = SiteProfileService(tmp_path / "profiles.json")
    source = _icon(tmp_path / "cache" / "same.g", width=20)

    v1 = service.upsert(_profile(_record(service, source)))
    service.set_global_profile_version("JEDDAH", 1, validate=False)
    v1_hash = str(v1.managed_standard_files[0]["sha256"])
    _icon(source, width=22)
    v2 = service.upsert(_profile(_record(service, source)))
    v2_hash = str(v2.managed_standard_files[0]["sha256"])
    _icon(source, width=24)
    v3 = service.upsert(_profile(_record(service, source)))

    # The initial auto GLOBAL points at V1, so it is deliberately protected.
    with pytest.raises(ValueError, match="GLOBAL"):
        service.delete_archived_version("JEDDAH", 1)

    service.set_global_profile_version("JEDDAH", 3, validate=False)
    service.delete_archived_version("JEDDAH", 1)

    assert [item.profile_version for item in service.load_profile_versions("JEDDAH")] == [2, 3]
    assert service.get_profile_version("JEDDAH", 2) is not None
    assert service.get_profile_version("JEDDAH", 3) is not None
    assert service.repository.load_manifest("JEDDAH", 1) is None
    assert service.repository.load_manifest("JEDDAH", 2) is not None
    assert service.repository.object_path(v1_hash).is_file()
    assert service.repository.object_path(v2_hash).is_file()
    deleted = list((service.repository.deleted_manifests_root / "JEDDAH").glob("V1.*.json"))
    assert deleted

    with pytest.raises(ValueError, match="ACTIVE"):
        service.delete_archived_version("JEDDAH", 3)


def test_normal_version_checkout_does_not_rehash_every_frozen_blob(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    service = SiteProfileService(tmp_path / "profiles.json")
    source = _icon(tmp_path / "cache" / "same.g", width=20)
    service.upsert(_profile(_record(service, source)))
    _icon(source, width=22)
    service.upsert(_profile(_record(service, source)))

    def fail_hash(_path):
        raise AssertionError("normal checkout must not SHA256 every object")

    monkeypatch.setattr(repository_module, "_sha256", fail_hash)
    old = service.get_profile_version("JEDDAH", 1)
    assert old is not None
    assert old.profile_version == 1
    assert Path(str(old.managed_standard_files[0]["managed_path"])).is_file()


def test_ui_has_version_switch_feedback_and_separate_history_delete_action():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'addAction("删除选中历史版本")' in source
    assert 'addAction("删除整个标准（全部版本）")' in source
    assert "正在切换标准版本" in source
    assert "version_switch_progress" in source
    assert "软件升级不会自动清理" in source
    assert "delete_archived_version" in source
