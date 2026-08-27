from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree, scan_smart_profile_samples
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
MAK_LBS = "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S"
MAK_CB = "#RMU_BRK_S.zwk.icn.g:RMU_BRK_S"


def _tree(lbs: str = SMART_LBS, breaker: str = SMART_CB) -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="15953_BUS")
    for idx, (name, x, y) in enumerate((("Y1", 145, 235), ("Y2", 245, 150), ("Y3", 145, 150)), start=1):
        ET.SubElement(layer, "CBreakerDis", id=f"11700000{idx}", x=str(x), y=str(y), w="28", h="30", p_NameString=name, devref=lbs)
    ET.SubElement(layer, "CBreakerDis", id="117000004", x="245", y="205", w="30", h="30", p_NameString="Q1", devref=breaker)
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="15953", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    return ET.ElementTree(root)


def test_scan_profile_learns_site_specific_smart_devrefs(tmp_path: Path):
    path = tmp_path / "sample.g"
    _tree(MAK_LBS, MAK_CB).write(path, encoding="utf-8", xml_declaration=True)
    result = scan_smart_profile_samples([path])
    assert result.smart_rmu_count == 1
    assert result.suggested_lbs_devref == MAK_LBS
    assert result.suggested_breaker_devref == MAK_CB
    assert result.lbs_candidates[0].confidence == 1.0
    assert result.breaker_candidates[0].confidence == 1.0


def test_apply_profile_normalizes_all_devices_in_existing_smart_rmu(tmp_path: Path):
    tree = _tree(SMART_LBS, SMART_CB)
    before = {e.get("id"): (e.get("x"), e.get("y"), e.get("p_NameString")) for e in tree.getroot().iter("CBreakerDis")}
    result = apply_smart_profile_to_tree(tree, tmp_path / "target.g", smart_lbs_devref=MAK_LBS, smart_breaker_devref=MAK_CB)
    assert result.smart_rmu_count == 1
    assert result.lbs_changed_count == 3
    assert result.breaker_changed_count == 1
    for e in tree.getroot().iter("CBreakerDis"):
        if (e.get("p_NameString") or "").startswith("Y"):
            assert e.get("devref") == MAK_LBS
        else:
            assert e.get("devref") == MAK_CB
        assert (e.get("x"), e.get("y"), e.get("p_NameString")) == before[e.get("id")]


def test_profile_service_persists_user_confirmed_site(tmp_path: Path):
    service = SiteProfileService(tmp_path / "profiles.json")
    saved = service.upsert(SiteSmartProfile(profile_name="Makkah Standard", site_name="Makkah", smart_lbs_devref=MAK_LBS, smart_breaker_devref=MAK_CB, sample_files=["a.g"]))
    loaded = service.load_profiles()["Makkah Standard"]
    assert saved.site_name == "Makkah"
    assert loaded.smart_lbs_devref == MAK_LBS
    assert loaded.smart_breaker_devref == MAK_CB
