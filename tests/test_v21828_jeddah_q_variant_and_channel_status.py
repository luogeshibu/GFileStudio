from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import (
    ensure_jeddah_smart_rmu_devices,
    remove_jeddah_channel_status_points,
)

NON_SMART_CB_ALT = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
CHANNEL_STATUS = "#channel_status.zt.icn.g:channel_status"


def _tree_with_bottom_smart_and_q_variant() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="30903_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="150",
        y="160",
        w="28",
        h="30",
        p_NameString="Y1",
        devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART",
    )
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000002",
        x="245",
        y="205",
        w="30",
        h="30",
        p_NameString="Q1",
        devref=NON_SMART_CB_ALT,
        key_name="Q1-30903",
        node_area="keep-this",
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="30903", x="155", y="45", w="120", h="50")
    # Valid Jeddah SMART labels can be in the lower-right portion of the cabinet.
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="250", y="285", w="70", h="22", fs="20")
    return ET.ElementTree(root)


def test_smart_audit_accepts_circuit_breaker_non_smart_variant_and_full_rmu_area(tmp_path: Path):
    tree = _tree_with_bottom_smart_and_q_variant()
    q1 = next(e for e in tree.getroot().iter("CBreakerDis") if e.get("p_NameString") == "Q1")
    before = (q1.get("id"), q1.get("key_name"), q1.get("node_area"), q1.get("x"), q1.get("y"))

    result = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "30903.g")

    assert result.smart_rmu_count == 1
    assert result.cbreaker_smart_devref_changed_count == 1
    assert q1.get("devref") == SMART_CB
    assert (q1.get("id"), q1.get("key_name"), q1.get("node_area"), q1.get("x"), q1.get("y")) == before


def test_jeddah_channel_status_removal_reuses_rmu_status_association(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="205", y="145", w="8", h="130", key_name="30881_BUS")
    target = ET.SubElement(layer, "Status", id="126000001", x="105", y="285", w="26", h="26", devref=CHANNEL_STATUS)
    # Same icon far away must not be deleted because it is not associated with this RMU.
    far = ET.SubElement(layer, "Status", id="126000002", x="800", y="800", w="26", h="26", devref=CHANNEL_STATUS)
    # A non-channel Status inside the RMU must also remain untouched.
    other = ET.SubElement(layer, "Status", id="126000003", x="140", y="285", w="26", h="26", devref="#other.zt.icn.g:other")
    tree = ET.ElementTree(root)

    result = remove_jeddah_channel_status_points(tree, tmp_path / "30881.g")
    remaining_ids = {e.get("id") for e in layer if e.tag == "Status"}

    assert result.scanned_rmu_count == 1
    assert result.matched_status_count == 1
    assert result.removed_status_count == 1
    assert target.get("id") not in remaining_ids
    assert far.get("id") in remaining_ids
    assert other.get("id") in remaining_ids


def test_jeddah_batch_ui_lists_channel_status_removal_and_q_smart_check():
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    style = Path("g_file_studio/jeddah/style_engine.py").read_text(encoding="utf-8")
    assert "删除 RMU 红色状态点（channel_status）" in page
    assert "Circuit_Breaker_NON-SMART" in style
    assert "Circuit_Breaker_SMART" in style
