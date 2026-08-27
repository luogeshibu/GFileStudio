from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_icon_geometry import connected_anchor_points
from g_file_studio.jeddah.style_engine import ensure_jeddah_smart_rmu_devices

SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
NON_SMART_CB = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"


def _add_rmu(
    layer: ET.Element,
    *,
    base_id: int,
    left: int,
    name: str,
    q_devref: str,
    q_x: int,
    q_y: int,
    q_w: int,
    q_h: int,
    top_anchor: tuple[int, int],
    bottom_anchor: tuple[int, int],
) -> ET.Element:
    rect_id = str(2_000_000 + base_id)
    bus_id = str(38_000_000 + base_id)
    y_id = str(117_000_000 + base_id)
    q_id = str(117_100_000 + base_id)
    top_line_id = str(34_000_000 + base_id * 2)
    bottom_line_id = str(34_000_001 + base_id * 2)
    ET.SubElement(layer, "rect", id=rect_id, x=str(left), y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id=bus_id, x=str(left + 115), y="145", w="8", h="130", key_name=f"{name}_BUS")
    ET.SubElement(
        layer,
        "CBreakerDis",
        id=y_id,
        x=str(left + 40),
        y="150",
        w="28",
        h="30",
        p_NameString="Y1",
        key_name="Y1",
        devref=SMART_LBS,
    )
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id=str(188_000_000 + base_id), x=str(left + 180), y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id=str(800_000_000 + base_id), ts=name, x=str(left + 60), y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id=str(800_100_000 + base_id), ts="SMART", x=str(left + 85), y="103", w="70", h="22", fs="20")

    q = ET.SubElement(
        layer,
        "CBreakerDis",
        id=q_id,
        x=str(q_x),
        y=str(q_y),
        w=str(q_w),
        h=str(q_h),
        p_NameString="Q1",
        key_name="Q1",
        devref=q_devref,
        rotate="0",
        tfr="rotate(0) scale(1,1)",
        node_area=f"0,0,{top_line_id};1,0,{bottom_line_id}",
    )
    ET.SubElement(
        layer,
        "ConnectLine",
        id=top_line_id,
        x=str(top_anchor[0] - 3),
        y=str(top_anchor[1] - 34),
        w="6",
        h="40",
        d=f"{top_anchor[0]},{top_anchor[1]} {top_anchor[0]},{top_anchor[1] - 34}",
    )
    ET.SubElement(
        layer,
        "ConnectLine",
        id=bottom_line_id,
        x=str(bottom_anchor[0] - 3),
        y=str(bottom_anchor[1] - 3),
        w="6",
        h="32",
        d=f"{bottom_anchor[0]},{bottom_anchor[1]} {bottom_anchor[0]},{bottom_anchor[1] + 26}",
    )
    return q


def test_jeddah_smart_q_replacement_preserves_line_anchors(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")

    # Correct SMART Q sample: SMART icon uses 30x30 and local electrical ports
    # at (18,6) / (18,26).
    _add_rmu(
        layer,
        base_id=1,
        left=100,
        name="11111",
        q_devref=SMART_CB,
        q_x=170,
        q_y=158,
        q_w=30,
        q_h=30,
        top_anchor=(188, 164),
        bottom_anchor=(188, 184),
    )

    # Wrong SMART cabinet: NON-SMART Q is 28x28 with ports at (12,4)/(12,24).
    # The electrical line endpoints are fixed at x=582, y=164/184.
    wrong_q = _add_rmu(
        layer,
        base_id=2,
        left=500,
        name="30903",
        q_devref=NON_SMART_CB,
        q_x=570,
        q_y=160,
        q_w=28,
        q_h=28,
        top_anchor=(582, 164),
        bottom_anchor=(582, 184),
    )
    tree = ET.ElementTree(root)
    by_id = {element.get("id"): element for element in root.iter() if element.get("id")}
    before_anchors = connected_anchor_points(wrong_q, by_id)

    result = ensure_jeddah_smart_rmu_devices(tree, tmp_path / "anchor-preserve.g")

    after_anchors = connected_anchor_points(wrong_q, by_id)
    assert result.smart_rmu_count == 2
    assert result.cbreaker_smart_devref_changed_count == 1
    assert result.geometry_adjusted_count == 1
    assert wrong_q.get("devref") == SMART_CB
    assert (wrong_q.get("x"), wrong_q.get("y"), wrong_q.get("w"), wrong_q.get("h")) == ("564", "158", "30", "30")
    assert after_anchors == before_anchors == ((582.0, 164.0), (582.0, 184.0))


def test_real_jeddah_30903_q_keeps_original_connection_points_when_fixture_exists():
    source = Path("/mnt/data/JED-NTH-ABH-12.sln.pic(1).g")
    if not source.exists():
        return
    tree = ET.parse(source)
    root = tree.getroot()
    elements = list(root.iter())
    by_id = {element.get("id"): element for element in elements if element.get("id")}
    q = by_id["117000238"]
    before = connected_anchor_points(q, by_id)

    result = ensure_jeddah_smart_rmu_devices(tree, source)

    assert q.get("devref") == SMART_CB
    assert (q.get("x"), q.get("y"), q.get("w"), q.get("h")) == ("2064", "2158", "30", "30")
    assert connected_anchor_points(q, by_id) == before == ((2082.0, 2164.0), (2082.0, 2184.0))
    assert result.geometry_adjusted_count >= 1
