from __future__ import annotations

from pathlib import Path

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile


def _icon(path: Path, tag: str, element_id: str) -> Path:
    path.write_text(
        f'<root><{tag} id="{element_id}" w="30" h="28" AlignCenter="15,14">'
        '<pin id="p1" index="1" cx="15" cy="4"/>'
        '<pin id="p2" index="2" cx="15" cy="24"/>'
        f'</{tag}></root>',
        encoding="utf-8",
    )
    return path


def test_same_uploaded_standard_can_cover_smart_and_normal_without_duplicate_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(tmp_path / "user-data"))
    ground_file = _icon(tmp_path / "External_grounddisconnector_new.g", "ZhaiWaiJieDiDaoZha", "GROUND_SHARED")
    service = SiteProfileService(tmp_path / "profiles.json")
    record = service.prepare_standard_file_records([ground_file])[0]
    devref = str(record["devref"])

    saved = service.upsert(SiteSmartProfile(
        profile_name="SHARED",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        smart_ground_devref=devref,
        normal_ground_devref=devref,
        managed_standard_files=[record],
    ))

    ready, issues = service.validate_authoritative_standard(saved)
    assert ready, issues
    assert saved.smart_ground_devref == saved.normal_ground_devref == devref
    assert len(saved.managed_standard_files) == 1


def test_symbol_standard_ui_is_one_table_and_explicit_shared_scope():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("图元标准")' in source
    assert 'self.profile_selector = WheelSafeComboBox()' in source
    assert 'self.profile_table' not in source
    assert 'QGroupBox("当前图元标准")' not in source
    assert 'QGroupBox("标准定义")' not in source
    assert 'self.share_pair_checkbox = QCheckBox("SMART / NORMAL 共用此标准")' in source
    assert 'pair_row = self._paired_builtin_row(row)' in source
    assert 'if inferred_scope and inferred_scope != scope and not share_pair' not in source
    assert '绑定依据：用户明确选择当前设备角色' in source
