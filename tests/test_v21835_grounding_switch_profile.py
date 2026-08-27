from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_icon_geometry import connected_anchor_points
from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree, scan_smart_profile_samples
from g_file_studio.services.site_profile_service import SiteProfileService, SiteSmartProfile

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"
GROUND_V1 = "#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new"
GROUND_V2 = "#External_grounddisconnector_v2.zwjddz.icn.g:External_grounddisconnector_v2"


def _add_rmu(layer: ET.Element, *, x: int, smart: bool, ground: str, ground_w: int = 30, ground_h: int = 28) -> ET.Element:
    ET.SubElement(layer, "rect", id=str(2000 + x), x=str(x), y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id=str(3000 + x), x=str(x + 115), y="145", w="8", h="130", key_name=f"{x}_BUS")
    y_line = str(4000 + x)
    q_line = str(5000 + x)
    g_line = str(6000 + x)
    ET.SubElement(layer, "ConnectLine", id=y_line, d=f"{x+45},165 {x+20},165", x=str(x+20), y="165", w="25", h="1")
    ET.SubElement(layer, "ConnectLine", id=q_line, d=f"{x+160},235 {x+160},260", x=str(x+160), y="235", w="1", h="25")
    # Grounding switch uses one electrical anchor at the left endpoint.
    ET.SubElement(layer, "ConnectLine", id=g_line, d=f"{x+205},204 {x+225},204", x=str(x+205), y="204", w="20", h="1")
    ET.SubElement(layer, "CBreakerDis", id=str(7000 + x), x=str(x+45), y="150", w="28", h="30", p_NameString="Y1", devref=SMART_LBS if smart else NORMAL_LBS, node_area=f"0,1,{y_line}")
    ET.SubElement(layer, "CBreakerDis", id=str(8000 + x), x=str(x+145), y="205", w="30", h="30", p_NameString="Q1", devref=SMART_CB if smart else NORMAL_CB, node_area=f"0,1,{q_line}")
    ground_el = ET.SubElement(
        layer,
        "ZhaiWaiJieDiDaoZha",
        id=str(9000 + x),
        x=str(x + 185),
        y="190",
        w=str(ground_w),
        h=str(ground_h),
        rotate="0",
        tfr="rotate(0) scale(1,1)",
        p_NameString="Y1D",
        devref=ground,
        node_area=f"0,0,{g_line}",
    )
    ET.SubElement(layer, "Text", id=str(10000 + x), ts=str(x), x=str(x+55), y="45", w="120", h="50")
    if smart:
        ET.SubElement(layer, "Text", id=str(11000 + x), ts="SMART", x=str(x+85), y="103", w="70", h="22", fs="20")
    return ground_el


def test_scan_learns_zhaiwaijiedidaozha_for_smart_and_normal(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    _add_rmu(layer, x=100, smart=True, ground=GROUND_V1)
    _add_rmu(layer, x=500, smart=False, ground=GROUND_V1)
    path = tmp_path / "standard.g"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    scan = scan_smart_profile_samples([path])
    assert scan.suggested_ground_devref == GROUND_V1
    assert scan.suggested_normal_ground_devref == GROUND_V1
    assert scan.ground_counts == {GROUND_V1: 1}
    assert scan.normal_ground_counts == {GROUND_V1: 1}
    assert GROUND_V1 in scan.geometry_templates


def test_apply_upgrades_ground_symbol_and_preserves_anchor(tmp_path: Path):
    # Standard geometry bank for V2: same electrical anchor, different icon size/offset.
    standard_root = ET.Element("G")
    standard_layer = ET.SubElement(standard_root, "Layer")
    _add_rmu(standard_layer, x=100, smart=True, ground=GROUND_V2, ground_w=36, ground_h=32)
    standard_path = tmp_path / "standard-v2.g"
    ET.ElementTree(standard_root).write(standard_path, encoding="utf-8", xml_declaration=True)
    scan = scan_smart_profile_samples([standard_path])

    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ground = _add_rmu(layer, x=100, smart=True, ground=GROUND_V1, ground_w=30, ground_h=28)
    tree = ET.ElementTree(root)
    elements = list(root.iter())
    by_id = {element.get("id"): element for element in elements if element.get("id")}
    before = connected_anchor_points(ground, by_id)

    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "target.g",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
        smart_ground_devref=GROUND_V2,
        normal_ground_devref=GROUND_V2,
        profile_geometry_templates=scan.geometry_templates,
    )

    assert result.ground_checked_count == 1
    assert result.ground_changed_count == 1
    assert ground.get("devref") == GROUND_V2
    assert connected_anchor_points(ground, by_id) == before


def test_ground_symbol_change_creates_new_profile_version(tmp_path: Path):
    service = SiteProfileService(tmp_path / "profiles.json")
    v1 = service.upsert(SiteSmartProfile(
        profile_name="Jeddah",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
        smart_ground_devref=GROUND_V1,
        normal_ground_devref=GROUND_V1,
    ))
    v2 = service.upsert(SiteSmartProfile(
        profile_name="Jeddah",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
        smart_ground_devref=GROUND_V2,
        normal_ground_devref=GROUND_V2,
    ))
    assert v1.profile_version == 1
    assert v2.profile_version == 2
    assert v2.history[-1]["smart_ground_devref"] == GROUND_V1


def test_jeddah_batch_ui_requires_active_profile_with_grounding_switch():
    source = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert "ZhaiWaiJieDiDaoZha" in source
    assert "active_profile.ground_ready" in source
    processor = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "smart_ground_devref=active_rmu_profile.smart_ground_devref" in processor
    assert "normal_ground_devref=active_rmu_profile.normal_ground_devref" in processor
