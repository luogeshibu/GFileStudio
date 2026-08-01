from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree


def _layer(tree):
    return next(c for c in tree.getroot() if c.tag.rsplit("}", 1)[-1] == "Layer")


def _tag(e):
    return e.tag.rsplit("}", 1)[-1]


def test_only_smart_rmu_frame_changes_and_smart_text_is_untouched():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    smart_rect = ET.SubElement(
        layer, "rect", id="20000001", x="0", y="0", w="220", h="220",
        lc="1,1,1", lcc="#010101"
    )
    smart_text = ET.SubElement(
        layer, "Text", id="8000001", x="50", y="20", w="60", h="20",
        ts="SMART", lc="9,9,9", lcc="#090909"
    )
    normal_rect = ET.SubElement(
        layer, "rect", id="20000002", x="300", y="0", w="220", h="220",
        lc="2,2,2", lcc="#020202"
    )
    ET.SubElement(
        layer, "Text", id="8000002", x="350", y="20", w="60", h="20",
        ts="NORMAL", lc="8,8,8", lcc="#080808"
    )
    outside_smart = ET.SubElement(
        layer, "Text", id="8000003", x="600", y="20", w="60", h="20",
        ts="SMART", lc="7,7,7", lcc="#070707"
    )

    result = enhance_rmu_tree(
        ET.ElementTree(root),
        Path("x.g"),
        change_smart_frame_color=True,
        smart_frame_color="#00AA55",
    )

    assert result.smart_rmu_rect_count == 1
    assert result.smart_frame_color_changed == 1
    assert smart_rect.get("lcc") == "#00AA55"
    assert smart_rect.get("lc") == "0,170,85"
    assert normal_rect.get("lcc") == "#020202"
    assert smart_text.get("lcc") == "#090909"
    assert smart_text.get("lc") == "9,9,9"
    assert outside_smart.get("lcc") == "#070707"


def test_bus_rect_removed_and_nearest_business_title_centered():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    rect = ET.SubElement(layer, "rect", id="20000001", x="100", y="100", w="220", h="220")
    bus = ET.SubElement(layer, "Bus", id="30000001", x="150", y="130", w="120", h="6", x1="150", y1="133", x2="270", y2="133", d="150,133 270,133")
    title = ET.SubElement(layer, "Text", id="8000001", x="130", y="50", w="160", h="40", fs="40", ts="AJWD-07")
    ET.SubElement(layer, "Text", id="8000002", x="170", y="170", w="20", h="20", fs="20", ts="Y1")
    tree = ET.ElementTree(root)
    result = enhance_rmu_tree(tree, Path("x.g"), remove_bus_frame_and_reposition_title=True)
    assert result.bus_rect_removed == 1
    assert rect not in list(layer)
    assert float(title.get("y")) < float(bus.get("y"))
    title_center = float(title.get("x")) + float(title.get("w")) / 2
    bus_center = float(bus.get("x")) + float(bus.get("w")) / 2
    assert abs(title_center - bus_center) < 0.001


def test_busdis_spacing_moves_whole_cabinet_without_resizing():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    r1 = ET.SubElement(layer, "rect", id="20000001", x="100", y="100", w="220", h="220")
    ET.SubElement(
        layer, "BusDis", id="38000001", x="200", y="120", w="6", h="160",
        x1="203", y1="120", x2="203", y2="280", d="203,120 203,280"
    )
    r2 = ET.SubElement(layer, "rect", id="20000002", x="100", y="430", w="220", h="220")
    bus2 = ET.SubElement(
        layer, "BusDis", id="38000002", x="200", y="450", w="6", h="160",
        x1="203", y1="450", x2="203", y2="610", d="203,450 203,610"
    )
    title = ET.SubElement(
        layer, "Text", id="80000002", x="120", y="380", w="160", h="40", ts="CAB-2"
    )
    tree = ET.ElementTree(root)

    result = enhance_rmu_tree(
        tree, Path("x.g"),
        normalize_busdis_spacing=True,
        busdis_vertical_spacing=300,
    )

    assert result.busdis_spacing_changed == 1
    assert r1.get("y") == "100"
    assert r2.get("y") == "400"
    assert r2.get("h") == "220"
    assert r2.get("x") == "100"
    assert bus2.get("y") == "420"
    assert bus2.get("x") == "200"
    assert title.get("y") == "350"
