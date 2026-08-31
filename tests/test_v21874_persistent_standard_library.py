from __future__ import annotations

from pathlib import Path

import pytest

import g_file_studio.services.site_profile_service as site_profile_service_module
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _icon(path: Path, tag: str, element_id: str, *, shift: int = 0) -> Path:
    xml = (
        f'<root><{tag} id="{element_id}" w="30" h="28" AlignCenter="15,14">'
        f'<pin id="p1" index="1" cx="15" cy="{4 + shift}"/>'
        f'<pin id="p2" index="2" cx="15" cy="{24 + shift}"/>'
        f'</{tag}></root>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return path


def test_uploaded_standard_icons_are_copied_outside_release_and_survive_source_delete(tmp_path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(site_profile_service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))

    source = tmp_path / "upload"
    smart_lbs = _icon(source / "smart_lbs.g", "CBreakerDis", "SMART_LBS")
    smart_cb = _icon(source / "smart_cb.g", "CBreakerDis", "SMART_CB")
    smart_ground = _icon(source / "smart_ground.g", "ZhaiWaiJieDiDaoZha", "SMART_GROUND")
    normal_lbs = _icon(source / "normal_lbs.g", "CBreakerDis", "NORMAL_LBS")
    normal_cb = _icon(source / "normal_cb.g", "CBreakerDis", "NORMAL_CB")
    normal_ground = _icon(source / "normal_ground.g", "ZhaiWaiJieDiDaoZha", "NORMAL_GROUND")
    files = [smart_lbs, smart_cb, smart_ground, normal_lbs, normal_cb, normal_ground]

    service = SiteProfileService(tmp_path / "config" / "profiles.json")
    records = service.prepare_standard_file_records(files)
    by_name = {row["original_name"]: row["devref"] for row in records}
    profile = SiteSmartProfile(
        profile_name="TEST STANDARD",
        site_name="Test Site",
        smart_lbs_devref=by_name["smart_lbs.g"],
        smart_breaker_devref=by_name["smart_cb.g"],
        smart_ground_devref=by_name["smart_ground.g"],
        normal_lbs_devref=by_name["normal_lbs.g"],
        normal_breaker_devref=by_name["normal_cb.g"],
        normal_ground_devref=by_name["normal_ground.g"],
        managed_standard_files=records,
    )
    saved = service.upsert(profile)
    assert saved.standard_fingerprint
    assert len(saved.managed_standard_files) == 6
    for row in saved.managed_standard_files:
        managed = Path(str(row["managed_path"]))
        assert managed.is_file()
        assert user_data in managed.parents
        assert "GFileStudio_v2.18.97" not in str(managed)

    for file in files:
        file.unlink()
    ready, issues = service.validate_authoritative_standard(saved)
    assert ready is True, issues


def test_business_sld_cannot_be_uploaded_as_authoritative_standard(tmp_path):
    business = tmp_path / "main.sln.pic.g"
    business.write_text('<root><Layer><CBreakerDis id="1" devref="#x:y" w="30" h="30"/></Layer></root>', encoding="utf-8")
    service = SiteProfileService(tmp_path / "profiles.json")
    with pytest.raises(ValueError, match="业务单线图不能作为标准"):
        service.prepare_standard_file_records([business])


def test_same_active_devref_cannot_have_two_different_uploaded_files(tmp_path):
    left = _icon(tmp_path / "a" / "same.g", "CBreakerDis", "X", shift=0)
    right = _icon(tmp_path / "b" / "same.g", "CBreakerDis", "X", shift=1)
    service = SiteProfileService(tmp_path / "profiles.json")
    with pytest.raises(ValueError, match="同一个图元"):
        service.prepare_standard_file_records([left, right])
