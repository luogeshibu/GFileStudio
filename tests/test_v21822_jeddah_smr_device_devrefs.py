from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import ensure_jeddah_smart_rmu_devices, replace_jeddah_smr_with_smart


NON_SMART_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
NON_SMART_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"


def _smr_tree() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="220", h="220", lc="255,255,255", lcc="#ffffff")
    ET.SubElement(layer, "BusDis", id="38000001", x="205", y="145", w="8", h="130", key_name="6703_BUS")

    # The three Y devices are the rectangular/diamond LBS family in the source G.
    for idx, (name, x, y) in enumerate((("Y1", 140, 230), ("Y2", 245, 230), ("Y3", 140, 150)), start=1):
        ET.SubElement(
            layer,
            "CBreakerDis",
            id=f"11700000{idx}",
            x=str(x), y=str(y), w="28", h="30",
            p_NameString=name,
            key_name=f"{name}-6703",
            devref=NON_SMART_LBS,
            node_area=f"node-{name}",
        )

    # Q1 is the square Circuit Breaker family and must also be switched to SMART.
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000004",
        x="245", y="165", w="30", h="30",
        p_NameString="Q1",
        key_name="TR1",
        devref=NON_SMART_CB,
        node_area="node-Q1",
    )

    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="280", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="6703", x="150", y="45", w="120", h="50", lc="255,255,255", lcc="#ffffff")
    ET.SubElement(layer, "Text", id="8000002", ts="SMR", x="355", y="175", w="61", h="32", fs="30", lc="255,170,255", lcc="#ffaaff")
    # Reference SMART is outside the cabinet: style reference only, not the existing-SMART special case.
    ET.SubElement(layer, "Text", id="8000099", ts="SMART", x="600", y="600", w="63", h="21", fs="20", p_FontWidth="20", p_FontHeight="20", ff="Arial", lc="255,0,0", lcc="#ff0000")
    return ET.ElementTree(root)


def test_smr_conversion_switches_y_and_q_cbreakerdis_devrefs_only(tmp_path: Path):
    tree = _smr_tree()
    before = {
        e.get("id"): {
            "key_name": e.get("key_name"),
            "node_area": e.get("node_area"),
            "x": e.get("x"),
            "y": e.get("y"),
        }
        for e in tree.getroot().iter("CBreakerDis")
    }

    result = replace_jeddah_smr_with_smart(tree, tmp_path / "6703.g")
    audit = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "6703.g")
    devices = {e.get("p_NameString"): e for e in tree.getroot().iter("CBreakerDis")}

    assert result.replaced_count == 1
    assert result.cbreaker_smart_devref_changed_count == 0
    assert audit.cbreaker_smart_devref_changed_count == 4
    assert devices["Y1"].get("devref") == SMART_LBS
    assert devices["Y2"].get("devref") == SMART_LBS
    assert devices["Y3"].get("devref") == SMART_LBS
    assert devices["Q1"].get("devref") == SMART_CB

    # Only devref changes on the devices; identity/topology/geometry stays untouched.
    for device in devices.values():
        old = before[device.get("id")]
        assert device.get("key_name") == old["key_name"]
        assert device.get("node_area") == old["node_area"]
        assert device.get("x") == old["x"]
        assert device.get("y") == old["y"]


def test_jeddah_source_contains_both_exact_devref_mappings():
    source = Path("g_file_studio/jeddah/style_engine.py").read_text(encoding="utf-8")
    assert NON_SMART_LBS in source and SMART_LBS in source
    assert NON_SMART_CB in source and SMART_CB in source
