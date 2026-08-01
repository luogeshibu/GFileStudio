from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree
from g_file_studio.models import BasicSettings, InputMode, RmuStatusPosition

ROOT = Path(__file__).resolve().parents[1]
REAL_FILE = ROOT / "tests/data/MAK-channel-status.g"


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _layer(tree):
    return next(child for child in tree.getroot() if _tag(child) == "Layer")


def _make_tree():
    root = ET.Element("G", w="1000", h="1000", width="1000", height="1000")
    layer = ET.SubElement(root, "Layer")
    rect = ET.SubElement(layer, "rect", id="20000001", x="100", y="200", w="220", h="220")
    bus = ET.SubElement(
        layer, "BusDis", id="38000001", x="135", y="309", w="154", h="0",
        x1="135", y1="309", x2="289", y2="309", d="135,309 289,309"
    )
    status = ET.SubElement(
        layer, "Status", id="12600001", x="101", y="296", w="26", h="26",
        devref="#channel_status.zt.icn.g:channel_status",
        tfr="rotate(0) scale(1,1)", af="2147483647"
    )
    other = ET.SubElement(
        layer, "Status", id="12600002", x="180", y="250", w="26", h="26",
        devref="#NariPd_Generator.zt.icn.g:NariPd_Generator"
    )
    return ET.ElementTree(root), rect, bus, status, other


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ("top_left", (105, 205)),
        ("top_center", (197, 205)),
        ("top_right", (289, 205)),
        ("middle_left", (105, 297)),
        ("middle_right", (289, 297)),
        ("bottom_left", (105, 389)),
        ("bottom_center", (197, 389)),
        ("bottom_right", (289, 389)),
    ],
)
def test_channel_status_supports_eight_rect_anchors(position, expected):
    tree, rect, bus, status, other = _make_tree()
    rect_snapshot = dict(rect.attrib)
    bus_snapshot = dict(bus.attrib)
    other_snapshot = dict(other.attrib)

    result = enhance_rmu_tree(
        tree,
        Path("sample.g"),
        reposition_channel_status=True,
        channel_status_position=position,
        channel_status_inner_margin=5,
    )

    assert (float(status.get("x")), float(status.get("y"))) == expected
    assert dict(rect.attrib) == rect_snapshot
    assert dict(bus.attrib) == bus_snapshot
    assert dict(other.attrib) == other_snapshot
    assert status.get("w") == "26"
    assert status.get("h") == "26"
    assert status.get("devref") == "#channel_status.zt.icn.g:channel_status"
    assert result.channel_status_rect_count == 1
    assert result.channel_status_found_count == 1
    assert result.channel_status_moved_count == 1
    assert result.channel_status_missing_count == 0


def test_real_mak_file_moves_all_17_red_points_to_bottom_left_without_moving_cabinets():
    tree = ET.parse(REAL_FILE)
    layer = _layer(tree)
    before_rects = {
        element.get("id"): dict(element.attrib)
        for element in list(layer)
        if _tag(element) == "rect"
    }
    before_busdis = {
        element.get("id"): dict(element.attrib)
        for element in list(layer)
        if _tag(element) == "BusDis"
    }

    result = enhance_rmu_tree(
        tree,
        REAL_FILE,
        reposition_channel_status=True,
        channel_status_position="bottom_left",
        channel_status_inner_margin=5,
    )

    assert result.channel_status_rect_count == 17
    assert result.channel_status_found_count == 17
    assert result.channel_status_moved_count == 17
    assert result.channel_status_missing_count == 0
    assert {
        element.get("id"): dict(element.attrib)
        for element in list(layer)
        if _tag(element) == "rect"
    } == before_rects
    assert {
        element.get("id"): dict(element.attrib)
        for element in list(layer)
        if _tag(element) == "BusDis"
    } == before_busdis

    rects = [element for element in list(layer) if _tag(element) == "rect"]
    statuses = [
        element for element in list(layer)
        if _tag(element) == "Status" and "channel_status.zt.icn.g:channel_status" in (element.get("devref") or "").lower()
    ]
    assert len(statuses) == 17
    for status in statuses:
        sx = float(status.get("x"))
        sy = float(status.get("y"))
        sw = float(status.get("w"))
        sh = float(status.get("h"))
        owners = [
            rect for rect in rects
            if float(rect.get("x")) - 0.5 <= sx <= float(rect.get("x")) + float(rect.get("w")) + 0.5
            and float(rect.get("y")) - 0.5 <= sy <= float(rect.get("y")) + float(rect.get("h")) + 0.5
        ]
        assert len(owners) == 1
        rect = owners[0]
        assert sx == float(rect.get("x")) + 5
        assert sy == float(rect.get("y")) + float(rect.get("h")) - sh - 5
        assert sw == 26


def test_model_uses_channel_status_options_and_has_no_busdis_spacing_fields():
    settings = BasicSettings(
        source_path=Path("in.g"),
        input_mode=InputMode.SINGLE_FILE,
        output_dir=Path("out"),
        reposition_channel_status=True,
        channel_status_position=RmuStatusPosition.BOTTOM_LEFT,
        channel_status_inner_margin=8,
    )
    assert settings.channel_status_position is RmuStatusPosition.BOTTOM_LEFT
    assert settings.channel_status_inner_margin == 8
    assert not hasattr(settings, "normalize_busdis_rmu_spacing")
    assert not hasattr(settings, "busdis_rmu_vertical_spacing")


def test_ui_removed_spacing_and_added_status_position_controls():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    assert "统一带 BusDis 的环网柜垂直间距" not in source
    assert "busdis_vertical_spacing" not in source
    assert "normalize_busdis_spacing" not in source
    assert "移动环网柜红色状态点（channel_status）" in source
    assert "WheelSafeComboBox" in source
    assert "channel_status_inner_margin" in source
