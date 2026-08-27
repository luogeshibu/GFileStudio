from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree, scan_smart_profile_samples
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NORMAL_CB = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
NEW_SMART_LBS = "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S"
NEW_SMART_CB = "#RMU_BRK_S.zwk.icn.g:RMU_BRK_S"


def _add_rmu(layer: ET.Element, *, x: int, name: str, smart: bool, lbs: str, cb: str) -> None:
    ET.SubElement(layer, "rect", id=str(2000000 + x), x=str(x), y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id=str(38000000 + x), x=str(x + 115), y="145", w="8", h="130", key_name=f"{name}_BUS")
    line1 = str(34000000 + x)
    line2 = str(34010000 + x)
    line3 = str(34020000 + x)
    ET.SubElement(layer, "ConnectLine", id=line1, d=f"{x + 45},165 {x + 20},165", x=str(x + 20), y="165", w="25", h="1")
    ET.SubElement(layer, "ConnectLine", id=line2, d=f"{x + 173},165 {x + 200},165", x=str(x + 173), y="165", w="27", h="1")
    ET.SubElement(layer, "ConnectLine", id=line3, d=f"{x + 160},235 {x + 160},260", x=str(x + 160), y="235", w="1", h="25")
    ET.SubElement(layer, "CBreakerDis", id=str(11700000 + x), x=str(x + 45), y="150", w="28", h="30", p_NameString="Y1", devref=lbs, node_area=f"0,1,{line1}")
    ET.SubElement(layer, "CBreakerDis", id=str(11710000 + x), x=str(x + 145), y="150", w="28", h="30", p_NameString="Y2", devref=lbs, node_area=f"0,1,{line2}")
    ET.SubElement(layer, "CBreakerDis", id=str(11720000 + x), x=str(x + 145), y="205", w="30", h="30", p_NameString="Q1", devref=cb, node_area=f"0,1,{line3}")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id=str(18800000 + x), x=str(x + 185), y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id=str(8000000 + x), ts=name, x=str(x + 55), y="45", w="120", h="50")
    if smart:
        ET.SubElement(layer, "Text", id=str(8100000 + x), ts="SMART", x=str(x + 85), y="103", w="70", h="22", fs="20")


def _sample_tree() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    _add_rmu(layer, x=100, name="1001", smart=True, lbs=SMART_LBS, cb=SMART_CB)
    _add_rmu(layer, x=500, name="1002", smart=False, lbs=NORMAL_LBS, cb=NORMAL_CB)
    return ET.ElementTree(root)


def test_scan_learns_smart_and_normal_in_one_pass(tmp_path: Path):
    path = tmp_path / "standard.g"
    _sample_tree().write(path, encoding="utf-8", xml_declaration=True)
    scan = scan_smart_profile_samples([path])
    assert scan.smart_rmu_count == 1
    assert scan.normal_rmu_count == 1
    assert scan.suggested_lbs_devref == SMART_LBS
    assert scan.suggested_breaker_devref == SMART_CB
    assert scan.suggested_normal_lbs_devref == NORMAL_LBS
    assert scan.suggested_normal_breaker_devref == NORMAL_CB
    assert SMART_LBS in scan.geometry_templates
    assert NORMAL_LBS in scan.geometry_templates


def test_apply_profile_repairs_both_smart_and_normal_by_label(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    # SMART cabinet deliberately contains NORMAL devices.
    _add_rmu(layer, x=100, name="1001", smart=True, lbs=NORMAL_LBS, cb=NORMAL_CB)
    # NORMAL cabinet deliberately contains SMART devices; absence of SMART text keeps it NORMAL.
    _add_rmu(layer, x=500, name="1002", smart=False, lbs=SMART_LBS, cb=SMART_CB)
    tree = ET.ElementTree(root)
    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "target.g",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    )
    assert result.smart_rmu_count == 1
    assert result.normal_rmu_count == 1
    assert result.lbs_changed_count == 2
    assert result.breaker_changed_count == 1
    assert result.normal_lbs_changed_count == 2
    assert result.normal_breaker_changed_count == 1


def test_relearning_changed_symbols_increments_profile_version_and_keeps_history(tmp_path: Path):
    service = SiteProfileService(tmp_path / "profiles.json")
    first = service.upsert(SiteSmartProfile(
        profile_name="Site A",
        site_name="Site A",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    ))
    assert first.profile_version == 1
    same = service.upsert(SiteSmartProfile(
        profile_name="Site A",
        site_name="Site A",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    ))
    assert same.profile_version == 1
    changed = service.upsert(SiteSmartProfile(
        profile_name="Site A",
        site_name="Site A",
        smart_lbs_devref=NEW_SMART_LBS,
        smart_breaker_devref=NEW_SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
    ))
    assert changed.profile_version == 2
    assert changed.history[-1]["smart_lbs_devref"] == SMART_LBS
    assert service.load_profiles()["Site A"].profile_version == 2
