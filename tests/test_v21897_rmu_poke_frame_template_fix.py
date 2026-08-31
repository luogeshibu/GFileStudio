from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_poke_engine import _Box, _ensure_jump_attributes, _new_poke


def test_new_rmu_poke_never_inherits_title_block_metadata() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(
        layer,
        "poke",
        {
            "id": "17000001",
            "fm": "0",
            "ls": "0",
            "Pos": "2",
            "gfs_frame_role": "title_block",
            "gfs_frame_component": "24",
            "gfs_frame_type": "builtin",
            "switchapp": "1",
        },
    )

    poke = _new_poke(root, "17000002")

    assert poke.get("id") == "17000002"
    assert poke.get("Pos") == "0"
    assert poke.get("RectStyle") == "0"
    assert poke.get("p_RectStyle") == "0"
    assert poke.get("lc") == "0,0,255"
    assert poke.get("lcc") == "#0000ff"
    assert poke.get("app") == ""
    assert poke.get("domain") == ""
    assert "gfs_frame_role" not in poke.attrib
    assert "gfs_frame_component" not in poke.attrib
    assert "gfs_frame_type" not in poke.attrib


def test_existing_bad_rmu_poke_is_repaired_when_processing_is_rerun() -> None:
    poke = ET.Element(
        "poke",
        {
            "id": "17000004",
            "ahref": "JED-NTH-ABH-AH322-33390.sln.pic.g",
            "x": "661.0732",
            "y": "3661.1221",
            "w": "115",
            "h": "55",
            "Pos": "2",
            "fm": "0",
            "ls": "0",
            "RectStyle": "0",
            "p_RectStyle": "0",
            "lc": "0,0,255",
            "lcc": "#0000ff",
            "gfs_frame_role": "title_block",
            "gfs_frame_component": "24",
            "gfs_frame_type": "builtin",
            "gfs_rmu_poke": "1",
            "gfs_rmu_name": "33390",
        },
    )

    changed = _ensure_jump_attributes(
        poke,
        target_file="JED-NTH-ABH-AH322-33390.sln.pic.g",
        rmu_name="33390",
        box=_Box(661.0732, 3661.1221, 776.0732, 3716.1221),
    )

    assert changed is True
    assert poke.get("Pos") == "0"
    assert poke.get("app") == ""
    assert poke.get("domain") == ""
    assert poke.get("gfs_rmu_poke") == "1"
    assert poke.get("gfs_rmu_name") == "33390"
    assert poke.get("ahref") == "JED-NTH-ABH-AH322-33390.sln.pic.g"
    assert "gfs_frame_role" not in poke.attrib
    assert "gfs_frame_component" not in poke.attrib
    assert "gfs_frame_type" not in poke.attrib
