from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree
from g_file_studio.services.site_profile_service import (
    SiteProfileService,
    SiteSmartProfile,
    infer_builtin_standard_role,
)


def _icon(path: Path, body_id: str, *, tag: str = "CBreakerDis") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<G><{tag} id="{body_id}" w="30" h="30" AlignCenter="15,15">'
        '<pin id="p1" index="1" cx="15" cy="5"/>'
        '<pin id="p2" index="2" cx="15" cy="25"/>'
        f'</{tag}></G>',
        encoding="utf-8",
    )
    return path


def test_uploaded_icon_role_inference_distinguishes_smart_and_normal():
    rows = [
        ({"element_tag": "CBreakerDis", "original_name": "Circuit_Breaker_NON-SMART.zwk.icn.g", "element_id": "Circuit_Breaker_NON-SMART"}, ("NORMAL", "BREAKER")),
        ({"element_tag": "CBreakerDis", "original_name": "Circuit_Breaker_SMART.zwk.icn.g", "element_id": "Circuit_Breaker_SMART"}, ("SMART", "BREAKER")),
        ({"element_tag": "CBreakerDis", "original_name": "Load_Breaker_Switch_NON-SMART.zwk.icn.g", "element_id": "Load_Breaker_Switch_NON-SMART"}, ("NORMAL", "LBS")),
        ({"element_tag": "CBreakerDis", "original_name": "Load_Breaker_Switch_SMART.zwk.icn.g", "element_id": "Load_Breaker_Switch_SMART"}, ("SMART", "LBS")),
    ]
    for record, expected in rows:
        assert infer_builtin_standard_role(record) == expected


def test_partial_profile_with_one_uploaded_role_is_ready(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    icon = _icon(tmp_path / "Circuit_Breaker_NON-SMART.zwk.icn.g", "Circuit_Breaker_NON-SMART")
    service = SiteProfileService(tmp_path / "profiles.json")
    record = service.prepare_standard_file_records([icon])[0]
    profile = service.upsert(SiteSmartProfile(
        profile_name="ONE-ROLE",
        site_name="Jeddah",
        smart_lbs_devref="",
        smart_breaker_devref="",
        normal_breaker_devref=str(record["devref"]),
        managed_standard_files=[record],
    ))
    ready, issues = service.validate_authoritative_standard(profile)
    assert ready is True, issues
    assert profile.configured_builtin_role_count == 1
    assert profile.full_ready is False


def test_partial_engine_checks_only_configured_normal_breaker(tmp_path: Path):
    standard = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="9200_BUS")
    ET.SubElement(layer, "CBreakerDis", id="117000001", x="145", y="150", w="28", h="30", p_NameString="Y1", devref="#Some_LBS.g:Some_LBS")
    q = ET.SubElement(layer, "CBreakerDis", id="117000002", x="245", y="205", w="30", h="30", p_NameString="Q1", devref="#Wrong_CB.g:Wrong_CB")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="9200", x="155", y="45", w="120", h="50")
    tree = ET.ElementTree(root)

    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "business.g",
        smart_lbs_devref="",
        smart_breaker_devref="",
        normal_breaker_devref=standard,
    )
    assert result.normal_rmu_count == 1
    assert result.normal_lbs_checked_count == 0
    assert result.normal_breaker_checked_count == 1
    assert result.normal_breaker_changed_count == 1
    assert q.get("devref") == standard


def test_ui_upload_is_single_file_and_can_explicitly_share_same_role_across_scopes():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QFileDialog.getOpenFileName(' in source
    assert 'QFileDialog.getOpenFileNames(' not in source
    assert 'SMART / NORMAL 共用此标准' in source
    assert 'self._paired_builtin_row(row)' in source
    assert 'if share_pair:' in source
    assert 'len(eligible) == 1' not in source
    assert 'def _confirm_rescan_target' not in source
    assert '可以只配置当前需要检查的设备角色' in source
