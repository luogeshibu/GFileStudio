from pathlib import Path
import re
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree

ROOT = Path(__file__).resolve().parents[1]
_COORD = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _layer(tree):
    return next(child for child in tree.getroot() if _tag(child) == "Layer")


def _by_id(layer, value):
    return next(element for element in list(layer) if element.get("id") == value)


def _x_snapshot(layer):
    snapshot = {}
    for element in list(layer):
        values = []
        for node in element.iter():
            values.append(tuple(node.get(name) for name in ("x", "x1", "x2", "cx", "mergex", "w", "width", "rx")))
            values.append(tuple(match.group(1) for match in _COORD.finditer(node.get("d", ""))))
        snapshot[element.get("id") or f"anon-{id(element)}"] = tuple(values)
    return snapshot


def test_real_adf16_busdis_rmus_use_equal_top_y_spacing_and_move_surroundings():
    tree = ET.parse(ROOT / "tests/data/JED-CTL-ADF-16-spacing.g")
    layer = _layer(tree)
    before_x = _x_snapshot(layer)
    rect_heights = {
        element.get("id"): element.get("h")
        for element in list(layer)
        if _tag(element) == "rect"
    }

    result = enhance_rmu_tree(
        tree,
        Path("JED-CTL-ADF-16-spacing.g"),
        normalize_busdis_spacing=True,
        busdis_vertical_spacing=300,
    )

    rects = sorted(
        [element for element in list(layer) if _tag(element) == "rect"],
        key=lambda element: float(element.get("y")),
    )
    assert [float(element.get("y")) for element in rects] == [480, 780, 1080, 1380, 1680]
    assert all(float(b.get("y")) - float(a.get("y")) == 300 for a, b in zip(rects, rects[1:]))
    assert {element.get("id"): element.get("h") for element in rects} == rect_heights
    assert _x_snapshot(layer) == before_x

    # 26860 柜及其周边标题、SMR、H.T 整体上移 20；柜间 FeedLine 端点同步缩短。
    assert _by_id(layer, "8000145").get("y") == "1314"
    assert _by_id(layer, "8000189").get("y") == "1444"
    assert _by_id(layer, "8000205").get("y") == "1488"
    assert _by_id(layer, "35000200").get("d") == "700,1245 700,1430"
    assert result.busdis_rect_count == 5
    assert result.busdis_column_count == 1
    assert result.busdis_spacing_changed == 2
    assert result.busdis_moved_element_count > 2


def test_separate_x_columns_keep_each_topmost_cabinet_as_its_own_reference():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    for index, (x, y) in enumerate(((100, 100), (100, 460), (700, 250), (700, 620)), 1):
        ET.SubElement(layer, "rect", id=f"2{index:07d}", x=str(x), y=str(y), w="220", h="220")
        ET.SubElement(
            layer, "BusDis", id=f"38{index:06d}", x=str(x + 100), y=str(y + 20),
            w="6", h="160", d=f"{x + 103},{y + 20} {x + 103},{y + 180}"
        )

    result = enhance_rmu_tree(
        ET.ElementTree(root), Path("columns.g"),
        normalize_busdis_spacing=True, busdis_vertical_spacing=300,
    )
    rects = [element for element in list(layer) if _tag(element) == "rect"]
    left = sorted(float(element.get("y")) for element in rects if element.get("x") == "100")
    right = sorted(float(element.get("y")) for element in rects if element.get("x") == "700")
    assert left == [100, 400]
    assert right == [250, 550]
    assert result.busdis_column_count == 2


def test_canvas_height_expands_when_larger_spacing_pushes_content_downward():
    tree = ET.parse(ROOT / "tests/data/JED-CTL-ADF-16-spacing.g")
    original_height = float(tree.getroot().get("height"))
    result = enhance_rmu_tree(
        tree,
        Path("JED-CTL-ADF-16-spacing.g"),
        normalize_busdis_spacing=True,
        busdis_vertical_spacing=500,
    )
    assert float(tree.getroot().get("height")) > original_height
    assert tree.getroot().get("h") == tree.getroot().get("height")
    assert result.canvas_height_expanded_to == float(tree.getroot().get("height"))
