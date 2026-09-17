from __future__ import annotations

from pathlib import Path

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.services.site_profile_service import (
    SiteProfileService,
    SiteSmartProfile,
    jeddah_role_issues,
    resolve_jeddah_role_devrefs,
)


def _icon(path: Path, *, width: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><CBreakerDis id="Circuit_Breaker_SMART" w="{width}" h="30" AlignCenter="15,15">'
        '<pin id="p1" index="1" cx="15" cy="5"/>'
        '<pin id="p2" index="2" cx="15" cy="25"/>'
        '</CBreakerDis></root>',
        encoding="utf-8",
    )
    return path


def _generic_profile(service: SiteProfileService, icon: Path) -> SiteSmartProfile:
    records = service.prepare_standard_file_records([icon])
    devref = str(records[0]["devref"])
    return SiteSmartProfile(
        profile_name="Jeddah Site",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        custom_symbols=[{
            "uid": "smart-cb",
            "scope": "SMART",
            "role": "Circuit Breaker",
            "device_type": "Circuit Breaker",
            "device_subtype": "",
            "device_level": "设备内部部件",
            "symbol_usage": "设备组成图元",
            "element_tag": "CBreakerDis",
            "standard_devref": devref,
            "match_attr": "devref",
            "match_value": devref,
            "enabled": True,
            "source_file": icon.name,
        }],
        managed_standard_files=records,
    )


def test_global_execution_version_stays_on_user_selection_when_newer_versions_are_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    service = SiteProfileService(tmp_path / "profiles.json")
    icon = tmp_path / "upload" / "Circuit_Breaker_SMART.zwk.icn.g"

    v1 = service.upsert(_generic_profile(service, _icon(icon, width=30)))
    v2 = service.upsert(_generic_profile(service, _icon(icon, width=32)))
    assert (v1.profile_version, v2.profile_version) == (1, 2)

    selected = service.set_global_profile_version("Jeddah Site", 1)
    assert selected.profile_version == 1
    assert service.get_global_profile_selection() == ("Jeddah Site", 1)
    assert service.get_global_profile().profile_version == 1

    v3 = service.upsert(_generic_profile(service, _icon(icon, width=34)))
    assert v3.profile_version == 3
    assert service.get_global_profile_selection() == ("Jeddah Site", 1)
    assert service.get_global_profile().profile_version == 1


def test_generic_standard_rows_resolve_jeddah_roles_without_legacy_learning_fields():
    profile = SiteSmartProfile(
        profile_name="Jeddah Site",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        normal_lbs_devref="",
        normal_breaker_devref="",
        smart_ground_devref="",
        normal_ground_devref="",
        custom_symbols=[
            {"scope": "SMART", "role": "LBS", "element_tag": "CBreakerDis", "standard_devref": "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"},
            {"scope": "NORMAL", "role": "LBS", "element_tag": "CBreakerDis", "standard_devref": "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"},
            {"scope": "SMART", "role": "Circuit Breaker", "element_tag": "CBreakerDis", "standard_devref": "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"},
            {"scope": "NORMAL", "role": "Circuit Breaker", "element_tag": "CBreakerDis", "standard_devref": "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"},
            {"scope": "ANY", "role": "Ground Disconnector", "element_tag": "ZhaiWaiJieDiDaoZha", "standard_devref": "#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new"},
        ],
    )
    roles = resolve_jeddah_role_devrefs(profile)
    assert roles["smart_lbs"].endswith(":Load_Breaker_Switch_SMART")
    assert roles["normal_lbs"].endswith(":Load_Breaker_Switch_NON-SMART")
    assert roles["smart_breaker"].endswith(":Circuit_Breaker_SMART")
    assert roles["normal_breaker"].endswith(":Circuit_Breaker_NON-SMART")
    assert roles["smart_ground"] == roles["normal_ground"]
    assert jeddah_role_issues(profile) == []


def test_ui_exposes_explicit_global_version_selection_and_jeddah_uses_it():
    standard_page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    jeddah_page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("设为全局版本")' in standard_page
    assert "set_global_profile_version" in standard_page
    assert "get_global_profile_selection" in jeddah_page
    assert "jeddah_role_issues" in jeddah_page
    assert "标准学习未完整" not in jeddah_page
    assert not Path("g_file_studio/ui/pages/symbol_inventory_page.py").exists()
