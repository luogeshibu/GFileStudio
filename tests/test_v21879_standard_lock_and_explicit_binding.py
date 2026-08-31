from __future__ import annotations

from pathlib import Path

import pytest

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _icon(path: Path, tag: str, element_id: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><{tag} id="{element_id}" w="30" h="28" AlignCenter="15,14">'
        '<pin id="p1" index="1" cx="15" cy="4"/>'
        '<pin id="p2" index="2" cx="15" cy="24"/>'
        f'</{tag}></root>',
        encoding="utf-8",
    )
    return path


def test_user_selected_role_is_authoritative_even_if_uploaded_xml_tag_differs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    service = SiteProfileService(tmp_path / "profiles.json")
    # Deliberately bind a grounding-symbol XML body to the SMART/LBS role. The UI
    # must not infer/reject the role; explicit user mapping is authoritative.
    icon = _icon(tmp_path / "manual-standard.g", "ZhaiWaiJieDiDaoZha", "MANUAL_ROLE")
    record = service.prepare_standard_file_records([icon])[0]
    devref = str(record["devref"])
    saved = service.upsert(SiteSmartProfile(
        profile_name="MANUAL",
        site_name="Jeddah",
        smart_lbs_devref=devref,
        smart_breaker_devref="",
        managed_standard_files=[record],
    ))
    ready, issues = service.validate_authoritative_standard(saved)
    assert ready, issues
    assert saved.smart_lbs_devref == devref


def test_lock_persists_without_version_bump_and_blocks_standard_mutation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    service = SiteProfileService(tmp_path / "profiles.json")
    first = service.prepare_standard_file_records([_icon(tmp_path / "first.g", "CBreakerDis", "FIRST")])[0]
    saved = service.upsert(SiteSmartProfile(
        profile_name="LOCKED",
        site_name="Jeddah",
        smart_lbs_devref=str(first["devref"]),
        smart_breaker_devref="",
        managed_standard_files=[first],
    ))
    assert saved.profile_version == 1
    locked = service.set_locked("LOCKED", True)
    assert locked.locked is True
    assert locked.profile_version == 1

    second = service.prepare_standard_file_records([_icon(tmp_path / "second.g", "CBreakerDis", "SECOND")])[0]
    with pytest.raises(ValueError, match="已锁定"):
        service.upsert(SiteSmartProfile(
            profile_name="LOCKED",
            site_name="Jeddah",
            smart_lbs_devref=str(second["devref"]),
            smart_breaker_devref="",
            managed_standard_files=[second],
        ))
    with pytest.raises(ValueError, match="已锁定"):
        service.remove("LOCKED")

    unlocked = service.set_locked("LOCKED", False)
    assert unlocked.locked is False
    updated = service.upsert(SiteSmartProfile(
        profile_name="LOCKED",
        site_name="Jeddah",
        smart_lbs_devref=str(second["devref"]),
        smart_breaker_devref="",
        managed_standard_files=[second],
    ))
    assert updated.profile_version == 2


def test_ui_has_lock_and_no_hard_type_mismatch_or_business_learning():
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    processor = Path("g_file_studio/processors/smart_profile_processor.py").read_text(encoding="utf-8")
    assert 'QPushButton("锁定当前版本")' in page
    assert 'self.service.set_locked(name, locked)' in page
    assert '"图元类型不匹配"' not in page
    assert 'infer_builtin_standard_role(record)' not in page
    assert '绑定依据：用户明确选择当前设备角色' in page
    assert 'collect_symbol_catalog_from_tree' not in processor
    assert '"_UnmappedSymbolCandidates": []' in processor
