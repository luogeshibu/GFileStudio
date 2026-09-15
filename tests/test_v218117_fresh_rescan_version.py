from pathlib import Path

from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _profile(name: str = "Jeddah Site", *, devref: str = "#old.g:Old") -> SiteSmartProfile:
    return SiteSmartProfile(
        profile_name=name,
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        custom_symbols=[{
            "uid": "row-1",
            "scope": "ANY",
            "role": "Circuit Breaker",
            "device_type": "Circuit Breaker",
            "element_tag": "CBreakerDis",
            "standard_devref": devref,
            "match_attr": "devref",
            "match_value": devref,
            "enabled": True,
        }],
        managed_standard_files=[{
            "devref": devref,
            "element_tag": "CBreakerDis",
            "element_id": "Old",
            "original_name": "old.g",
            "width": 30.0,
            "height": 30.0,
            "align_center": [15.0, 15.0],
            "pins": [],
        }],
        discovery_catalog={devref: {
            "observed_devref": devref,
            "observed_symbol_file": "old.g",
            "count": 3,
        }},
    ).normalized()


def test_fresh_rescan_ui_is_explicit_and_draft_isolated():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("全量重新扫描 → 新版本草稿")' in source
    assert 'QPushButton("取消新版本草稿")' in source
    assert 'def _prepare_fresh_rescan_version(self)' in source
    assert 'def _enter_fresh_rescan_draft(self, catalog:' in source
    assert 'self._rescan_draft_mode = True' in source
    assert 'self.service.save_as_next_version(candidate_profile)' in source
    assert 'self.service.update_discovery_metadata(name, catalog=catalog)' in source
    assert 'fresh_rescan = bool(self._rescan_prepare_mode or self._rescan_draft_mode)' in source
    assert 'if fresh_rescan:' in source  # fresh draft skips persisted discovery mutation branch
    assert '本次已不出现' in source
    assert 'GLOBAL 不会自动切换' in source


def test_service_can_force_next_version_from_locked_active_without_moving_global(tmp_path, monkeypatch):
    import g_file_studio.services.site_profile_service as mod
    monkeypatch.setattr(mod, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    service = SiteProfileService(tmp_path / "profiles.json")

    icon = tmp_path / "upload" / "old.g"
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_text('<root><CBreakerDis id="Old" w="30" h="30" AlignCenter="15,15"/></root>', encoding="utf-8")
    records = service.prepare_standard_file_records([icon])
    devref = str(records[0]["devref"])
    base = _profile(devref=devref)
    base.managed_standard_files = records
    base.custom_symbols[0]["standard_devref"] = devref
    base.custom_symbols[0]["match_value"] = devref
    base.discovery_catalog = {devref: {"observed_devref": devref, "observed_symbol_file": "old.g", "count": 3}}
    v1 = service.upsert(base)
    service.set_global_profile_version(v1.profile_name, v1.profile_version)
    locked = service.set_locked(v1.profile_name, True)
    assert locked.locked

    new_icon = tmp_path / "upload" / "new.g"
    new_icon.write_text('<root><CBreakerDis id="New" w="32" h="30" AlignCenter="16,15"/></root>', encoding="utf-8")
    new_records = service.prepare_standard_file_records([new_icon])
    new_devref = str(new_records[0]["devref"])
    draft = _profile(devref=new_devref)
    draft.managed_standard_files = new_records
    draft.custom_symbols[0]["standard_devref"] = new_devref
    draft.custom_symbols[0]["match_value"] = new_devref
    draft.discovery_catalog = {
        new_devref: {"observed_devref": new_devref, "observed_symbol_file": "new.g", "count": 5}
    }
    v2 = service.save_as_next_version(draft)

    assert v2.profile_version == locked.profile_version + 1
    assert not v2.locked
    versions = service.load_profile_versions(v2.profile_name)
    assert any(item.profile_version == locked.profile_version and item.locked for item in versions)
    assert service.get_global_profile_selection() == (locked.profile_name, locked.profile_version)


def test_release_is_218118():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
