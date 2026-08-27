from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import ensure_jeddah_smart_rmu_devices, replace_jeddah_smr_with_smart


NON_SMART = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
SMART = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"


def _tree(*, existing_smart_inside: bool) -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(
        layer,
        "rect",
        id="2000001",
        x="100",
        y="100",
        w="220",
        h="220",
        lc="255,255,255",
        lcc="#ffffff",
    )
    ET.SubElement(layer, "BusDis", id="38000001", x="205", y="145", w="8", h="130", key_name="1836_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="155",
        y="180",
        w="28",
        h="30",
        p_NameString="Y1",
        key_name="Y1-1836",
        devref=NON_SMART,
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="250", y="180", w="30", h="30")
    ET.SubElement(
        layer,
        "Text",
        id="8000001",
        ts="1836",
        x="155",
        y="50",
        w="110",
        h="50",
        lc="0,255,0",
        lcc="#00ff00",
    )
    ET.SubElement(
        layer,
        "Text",
        id="8000002",
        ts="SMR",
        x="355",
        y="175",
        w="61",
        h="32",
        fs="30",
        lc="255,170,255",
        lcc="#ffaaff",
    )
    if existing_smart_inside:
        ET.SubElement(
            layer,
            "Text",
            id="8000003",
            ts="SMART",
            x="178.5",
            y="105",
            w="63",
            h="21",
            fs="20",
            p_FontWidth="20",
            p_FontHeight="20",
            ff="Arial",
            lc="255,0,0",
            lcc="#ff0000",
        )
    else:
        # Reference SMART belongs to another cabinet / area and is only used for style.
        ET.SubElement(
            layer,
            "Text",
            id="8000099",
            ts="SMART",
            x="600",
            y="600",
            w="63",
            h="21",
            fs="20",
            p_FontWidth="20",
            p_FontHeight="20",
            ff="Arial",
            lc="255,0,0",
            lcc="#ff0000",
        )
    return ET.ElementTree(root)


def test_existing_smart_inside_rmu_only_removes_smr_and_sets_frame_red(tmp_path: Path):
    tree = _tree(existing_smart_inside=True)
    pre_audit = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "existing-smart.g")
    result = replace_jeddah_smr_with_smart(tree, tmp_path / "existing-smart.g")

    layer = next(e for e in tree.getroot() if e.tag == "Layer")
    texts = [e for e in layer if e.tag == "Text"]
    rect = next(e for e in layer if e.tag == "rect")
    breaker = next(e for e in layer if e.tag == "CBreakerDis")

    assert result.matched_rmu_count == 1
    assert result.existing_smart_cleanup_count == 1
    assert result.smr_text_removed_count == 1
    assert result.replaced_count == 0
    assert pre_audit.cbreaker_smart_devref_changed_count == 1
    assert result.cbreaker_smart_devref_changed_count == 0
    assert not any((e.get("ts") or "").strip().upper() == "SMR" for e in texts)
    smart_texts = [e for e in texts if (e.get("ts") or "").strip().upper() == "SMART"]
    assert len(smart_texts) == 1
    assert smart_texts[0].get("id") == "8000003"  # existing SMART stays untouched
    assert smart_texts[0].get("x") == "178.5"
    assert smart_texts[0].get("y") == "105"
    assert rect.get("lc") == "255,0,0"
    assert rect.get("lcc") == "#FF0000"
    assert breaker.get("devref") == SMART  # separate SMART-device audit corrects existing SMART cabinets


def test_no_smart_inside_creates_smart_and_switches_exact_lbs_devref(tmp_path: Path):
    tree = _tree(existing_smart_inside=False)
    result = replace_jeddah_smr_with_smart(tree, tmp_path / "no-smart.g")
    post_audit = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "no-smart.g")

    layer = next(e for e in tree.getroot() if e.tag == "Layer")
    converted = next(e for e in layer if e.tag == "Text" and e.get("id") == "8000002")
    breaker = next(e for e in layer if e.tag == "CBreakerDis")
    rect = next(e for e in layer if e.tag == "rect")

    assert result.replaced_count == 1
    assert result.existing_smart_cleanup_count == 0
    assert result.cbreaker_smart_devref_changed_count == 0
    assert post_audit.cbreaker_smart_devref_changed_count == 1
    assert converted.get("ts") == "SMART"
    assert converted.get("fs") == "20"
    assert converted.get("x") == "178.5"
    assert converted.get("y") == "100"
    assert breaker.get("devref") == SMART
    assert rect.get("lc") == "255,0,0"
    assert rect.get("lcc") == "#FF0000"
