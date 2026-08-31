from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_poke_engine import _Box, _ensure_jump_attributes, _new_poke


def test_reused_rmu_poke_normalizes_rectangular_appearance_to_invisible() -> None:
    poke = ET.Element("poke", {"RectStyle": "1", "p_RectStyle": "2", "lc": "1,2,3"})
    changed = _ensure_jump_attributes(
        poke,
        target_file="JED-NTH-ABH-AH303-34661.sln.pic.g",
        rmu_name="34661",
        box=_Box(10, 20, 110, 50),
    )
    assert changed
    assert poke.get("RectStyle") == "0"
    assert poke.get("p_RectStyle") == "0"
    assert poke.get("lc") == "0,0,255"
    assert poke.get("lcc") == "#0000ff"


def test_new_poke_overrides_template_rect_style_to_invisible() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "poke", {
        "id": "17000001", "fm": "0", "ls": "0",
        "RectStyle": "2", "p_RectStyle": "2", "fc": "0,255,0",
    })
    poke = _new_poke(root, "17000002")
    assert poke.get("RectStyle") == "0"
    assert poke.get("p_RectStyle") == "0"
    assert poke.get("fm") == "0"
    assert poke.get("ls") == "0"
