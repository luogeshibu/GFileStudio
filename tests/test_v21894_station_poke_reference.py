from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.station_poke_engine import (
    _STATION_JUMP_POKE_REFERENCE_ATTRS,
    apply_station_pokes,
)


EXPECTED_JM2_J2_NON_GEOMETRIC_ATTRS = {'PlaneState19': '0', 'PlaneState42': '0', 'clip': 'false', 'PlaneState7': '0', 'af': '2147483647', 'PlaneState8': '0', 'PlaneState45': '0', 'PlaneState40': '0', 'fc': '100,100,100', 'ShadowType': '0', 'isDisplay': '1', 'PlaneState9': '0', 'PlaneState23': '0', 'p_FatherObjId': '', 'PlaneState30': '0', 'PlaneState14': '0', 'PlaneState48': '0', 'lw': '1', 'ls': '1', 'PlaneState38': '0', 'PlaneState36': '0', 'PlaneState0': '1', 'PlaneState37': '0', 'p_EngcodeString': '', 'lcc': '#000000', 'PlaneState33': '0', 'af4': '2147483647', 'tfr': 'rotate(0) scale(1,1)', 'p_RectStyle': '1', 'onMouseLeftDoubleClickAciton': '', 'PlaneState32': '0', 'PlaneState6': '0', 'PlaneState44': '0', 'RectStyle': '1', 'onMouseRightOneClickAction': '', 'PlaneState49': '0', 'PlaneState31': '0', 'lc': '0,0,0', 'switchapp': '1', 'PlaneState25': '0', 'PlaneState4': '0', 'PlaneState17': '0', 'fm': '1', 'PlaneState12': '0', 'aliasType': '', 'onMouseHoverLeaveAction': '', 'PlaneState47': '0', 'PlaneState39': '0', 'PlaneState46': '0', 'LevelEnd': '16', 'p_DyColorFlag': '0', 'onMouseLeftOneClickAction': '', 'PlaneState20': '0', 'onMouseHoverEnterAction': '', 'PlaneState27': '0', 'p_ShowModeMask': '3', 'rotate': '0', 'PlaneState15': '0', 'PlaneState21': '0', 'PlaneState3': '0', 'eventRegister': '', 'PlaneState5': '0', 'switchappflag': '1', 'p_SelfDefString': '', 'fcc': '#646464', 'PlaneState29': '0', 'af3': '2147483647', 'trend_color': '0', 'PlaneState10': '0', 'PlaneState28': '0', 'onMouseRightDoubleClickAction': '', 'PlaneState41': '0', 'PlaneState34': '0', 'opacity': '1', 'af2': '2147483647', 'PlaneState1': '0', 'PlaneState16': '0', 'PlaneState18': '0', 'PlaneState26': '0', 'p_AssFlag': '128', 'PlaneState24': '0', 'rain_bow': '0', 'PlaneState2': '0', 'PlaneState11': '0', 'PlaneState13': '0', 'LevelStart': '0', 'PlaneState35': '0', 'PlaneState43': '0', 'PlaneState22': '0', 'devref': ''}


def test_jm2_j2_reference_property_template_is_exact() -> None:
    assert _STATION_JUMP_POKE_REFERENCE_ATTRS == EXPECTED_JM2_J2_NON_GEOMETRIC_ATTRS


def test_station_jump_poke_uses_reference_properties_but_keeps_dynamic_geometry(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "10", "y": "20", "w": "160", "h": "43",
        "fc": "1,2,3", "fcc": "#010203", "lc": "0,0,255", "lcc": "#0000ff",
        "RectStyle": "0", "p_RectStyle": "0", "fm": "0", "ls": "0",
        "unexpected": "remove-me",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "12", "y": "16", "w": "155", "h": "61",
        "ts": "JM2-J2", "fs": "55", "lc": "255,255,255",
    })
    tree = ET.ElementTree(root)
    identification = RmuIdentificationResult(file_path=file_path)

    result = apply_station_pokes(
        tree,
        file_path,
        identification,
        current_station_name="AJWD",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-JM2"),
    )
    assert result.updated_count == 1
    poke = next(e for e in list(layer) if e.tag == "poke")
    for key, value in EXPECTED_JM2_J2_NON_GEOMETRIC_ATTRS.items():
        assert poke.get(key) == value, key
    assert poke.get("id") == "17000001"
    assert poke.get("x") == "10"
    assert poke.get("y") == "20"
    assert poke.get("w") == "160"
    assert poke.get("h") == "43"
    assert poke.get("ahref") == "JED-CTL-JM2.sln.pic.g"
    assert poke.get("gfs_station_name") == "JM2"
    assert poke.get("gfs_station_text_id") == "80000001"
    assert "unexpected" not in poke.attrib


def test_report_and_ui_no_longer_use_station_strip_wording() -> None:
    report = Path("g_file_studio/services/poke_report_service.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/poke_page.py").read_text(encoding="utf-8")
    help_text = Path("g_file_studio/ui/help_content.py").read_text(encoding="utf-8")
    combined = report + page + help_text
    assert "站点条状" not in combined
    assert "站点跳转 Poke" in combined
