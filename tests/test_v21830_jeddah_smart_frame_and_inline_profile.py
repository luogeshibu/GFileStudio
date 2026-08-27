from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import ensure_jeddah_smart_rmu_frames_red


def _edge_smart_tree() -> ET.ElementTree:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    rect = ET.SubElement(
        layer,
        "rect",
        id="2000643",
        x="100",
        y="100",
        w="220",
        h="220",
        lc="255,255,255",
        lcc="#ffffff",
    )
    ET.SubElement(layer, "BusDis", id="38000643", x="205", y="145", w="8", h="130", key_name="30834_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id="117000001",
        x="150",
        y="165",
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
        devref="#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART",
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", ts="30834", x="155", y="45", w="120", h="50")
    # RMU right edge = 320; SMART right edge = 321.  Its center is still inside the
    # cabinet, matching the real Jeddah edge case that used to miss red-frame coloring.
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="260", y="298", w="61", h="21", fs="20")
    assert rect.get("lcc") == "#ffffff"
    return ET.ElementTree(root)


def test_jeddah_final_smart_frame_uses_text_center_and_forces_red(tmp_path: Path):
    tree = _edge_smart_tree()
    rect = next(tree.getroot().iter("rect"))

    first = ensure_jeddah_smart_rmu_frames_red(tree, tmp_path / "30834.g")
    second = ensure_jeddah_smart_rmu_frames_red(tree, tmp_path / "30834.g")

    assert first.smart_rmu_count == 1
    assert first.frame_red_changed_count == 1
    assert rect.get("lc") == "255,0,0"
    assert rect.get("lcc") == "#FF0000"
    assert second.smart_rmu_count == 1
    assert second.frame_red_changed_count == 0


def test_jeddah_batch_uses_final_smart_frame_consistency_pass():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "ensure_jeddah_smart_rmu_frames_red" in source
    assert "change_smart_frame_color=False" in source


def test_site_profile_management_is_inline_table_not_popup_dialog():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "QTableWidget" in source
    assert "当前图元标准" in source
    assert "图元标准" in source
    assert "待检查 G 文件" in source
    assert "SiteProfileDialog" not in source
