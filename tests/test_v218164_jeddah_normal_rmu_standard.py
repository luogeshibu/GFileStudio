from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.smart_profile_engine import apply_smart_profile_to_tree
from g_file_studio.jeddah.style_engine import (
    ensure_jeddah_normal_rmu_frames_white,
    ensure_jeddah_smart_rmu_frames_red,
)

SMART_LBS = "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"
SMART_CB = "#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"
OLD_NORMAL_LBS = "#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART"
OLD_NORMAL_CB = "#Circuit_Breaker_NON-SMART.zwk.icn.g:Circuit_Breaker_NON-SMART"
NEW_NORMAL_LBS = "#Load_Breaker_Switch_NO-SMART.zwk.icn.g:Load_Breaker_Switch_NO-SMART"
NEW_NORMAL_CB = "#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART"


def _add_rmu(
    layer: ET.Element,
    *,
    x: int,
    name: str,
    smart: bool,
    lbs: str,
    cb: str,
    frame_color: str = "255,0,0",
    frame_hex: str = "#FF0000",
) -> ET.Element:
    rect = ET.SubElement(
        layer,
        "rect",
        id=str(2_000_000 + x),
        x=str(x),
        y="100",
        w="240",
        h="220",
        lc=frame_color,
        lcc=frame_hex,
    )
    ET.SubElement(layer, "BusDis", id=str(38_000_000 + x), x=str(x + 115), y="145", w="8", h="130", key_name=f"{name}_BUS")
    ET.SubElement(layer, "CBreakerDis", id=str(11_700_000 + x), x=str(x + 45), y="150", w="28", h="30", p_NameString="Y1", devref=lbs)
    ET.SubElement(layer, "CBreakerDis", id=str(11_710_000 + x), x=str(x + 145), y="150", w="28", h="30", p_NameString="Y2", devref=lbs)
    ET.SubElement(layer, "CBreakerDis", id=str(11_720_000 + x), x=str(x + 145), y="205", w="30", h="30", p_NameString="Q1", devref=cb)
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id=str(18_800_000 + x), x=str(x + 185), y="180", w="20", h="20")
    ET.SubElement(layer, "Text", id=str(8_000_000 + x), ts=name, x=str(x + 55), y="45", w="120", h="50")
    if smart:
        ET.SubElement(layer, "Text", id=str(8_100_000 + x), ts="SMART", x=str(x + 85), y="103", w="70", h="22", fs="20")
    return rect


def test_jeddah_rmu_without_smart_is_forced_white_while_smart_stays_red(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    normal_rect = _add_rmu(
        layer,
        x=100,
        name="22545",
        smart=False,
        lbs=SMART_LBS,
        cb=SMART_CB,
    )
    smart_rect = _add_rmu(
        layer,
        x=500,
        name="22546",
        smart=True,
        lbs=SMART_LBS,
        cb=SMART_CB,
        frame_color="255,255,255",
        frame_hex="#FFFFFF",
    )
    tree = ET.ElementTree(root)

    normal = ensure_jeddah_normal_rmu_frames_white(tree, tmp_path / "JED.g")
    smart = ensure_jeddah_smart_rmu_frames_red(tree, tmp_path / "JED.g")

    assert normal.scanned_rmu_count == 2
    assert normal.normal_rmu_count == 1
    assert normal.frame_white_changed_count == 1
    assert normal_rect.get("lc") == "255,255,255"
    assert normal_rect.get("lcc") == "#FFFFFF"

    assert smart.smart_rmu_count == 1
    assert smart.frame_red_changed_count == 1
    assert smart_rect.get("lc") == "255,0,0"
    assert smart_rect.get("lcc") == "#FF0000"


def test_jeddah_normal_symbols_learn_unique_server_known_peer_variant(tmp_path: Path):
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    # Two existing NORMAL cabinets establish the actual NO-SMART revision used by
    # this drawing.  The third NORMAL cabinet is wrong and still uses SMART symbols.
    _add_rmu(layer, x=100, name="22541", smart=False, lbs=NEW_NORMAL_LBS, cb=NEW_NORMAL_CB)
    _add_rmu(layer, x=500, name="22542", smart=False, lbs=NEW_NORMAL_LBS, cb=NEW_NORMAL_CB)
    _add_rmu(layer, x=900, name="22545", smart=False, lbs=SMART_LBS, cb=SMART_CB)
    tree = ET.ElementTree(root)

    result = apply_smart_profile_to_tree(
        tree,
        tmp_path / "JED.g",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        # Deliberately stale GLOBAL role bindings. Peer NORMAL cabinets should select
        # the unique dominant server-known NO-SMART revision instead.
        normal_lbs_devref=OLD_NORMAL_LBS,
        normal_breaker_devref=OLD_NORMAL_CB,
        authoritative_standard_devrefs={
            SMART_LBS,
            SMART_CB,
            OLD_NORMAL_LBS,
            OLD_NORMAL_CB,
            NEW_NORMAL_LBS,
            NEW_NORMAL_CB,
        },
        profile_geometry_templates={},
        allow_source_geometry_fallback=False,
        jeddah_variant_only=True,
    )

    wrong_cabinet = [
        element
        for element in layer
        if element.tag == "CBreakerDis" and 900 <= float(element.get("x", "0")) < 1140
    ]
    y_devices = [element for element in wrong_cabinet if (element.get("p_NameString") or "").startswith("Y")]
    q_devices = [element for element in wrong_cabinet if (element.get("p_NameString") or "").startswith("Q")]

    assert y_devices and all(element.get("devref") == NEW_NORMAL_LBS for element in y_devices)
    assert q_devices and all(element.get("devref") == NEW_NORMAL_CB for element in q_devices)
    assert result.normal_lbs_changed_count >= 2
    assert result.normal_breaker_changed_count >= 1


def test_jeddah_batch_runs_normal_frame_white_pass_after_smr_conversion():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "ensure_jeddah_normal_rmu_frames_white" in source
    assert source.index("replace_jeddah_smr_with_smart") < source.rindex("ensure_jeddah_normal_rmu_frames_white")
