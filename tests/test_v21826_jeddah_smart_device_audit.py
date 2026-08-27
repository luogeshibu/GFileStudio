from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import ensure_jeddah_smart_rmu_devices

NON_SMART_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
NON_SMART_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"


def _smart_rmu_tree() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="15953_BUS")
    for idx, (name, x, y) in enumerate((("Y1", 145, 235), ("Y2", 245, 150), ("Y3", 145, 150)), start=1):
        ET.SubElement(
            layer, "CBreakerDis", id=f"11700000{idx}", x=str(x), y=str(y), w="28", h="30",
            p_NameString=name, key_name=f"{name}-15953", devref=NON_SMART_LBS,
            node_area=f"node-{name}", rotate="270",
        )
    ET.SubElement(
        layer, "CBreakerDis", id="117000004", x="245", y="205", w="30", h="30",
        p_NameString="Q1", key_name="Q1-15953", devref=NON_SMART_CB,
        node_area="node-Q1", rotate="0",
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="15953", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    return ET.ElementTree(root)


def test_existing_smart_rmu_corrects_both_lbs_and_circuit_breaker_devrefs(tmp_path: Path):
    tree = _smart_rmu_tree()
    before = {
        e.get("id"): (e.get("key_name"), e.get("node_area"), e.get("x"), e.get("y"), e.get("rotate"))
        for e in tree.getroot().iter("CBreakerDis")
    }

    result = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "smart-existing.g")
    devices = {e.get("p_NameString"): e for e in tree.getroot().iter("CBreakerDis")}

    assert result.smart_rmu_count == 1
    assert result.cbreaker_smart_devref_changed_count == 4
    assert devices["Y1"].get("devref") == SMART_LBS
    assert devices["Y2"].get("devref") == SMART_LBS
    assert devices["Y3"].get("devref") == SMART_LBS
    assert devices["Q1"].get("devref") == SMART_CB

    for e in devices.values():
        assert (e.get("key_name"), e.get("node_area"), e.get("x"), e.get("y"), e.get("rotate")) == before[e.get("id")]


def test_audit_is_idempotent_after_first_correction(tmp_path: Path):
    tree = _smart_rmu_tree()
    first = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "smart-existing.g")
    second = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "smart-existing.g")
    assert first.cbreaker_smart_devref_changed_count == 4
    assert second.cbreaker_smart_devref_changed_count == 0
