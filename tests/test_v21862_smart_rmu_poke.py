from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes, build_rmu_detail_filename


def _tree() -> ET.ElementTree:
    root = ET.Element("G", {"facName": "AH303"})
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "rect", {"id": "2000001", "x": "100", "y": "100", "w": "220", "h": "220"})
    ET.SubElement(layer, "BusDis", {"id": "38000001", "x": "140", "y": "170", "w": "140", "h": "8"})
    ET.SubElement(layer, "CBreakerDis", {
        "id": "117000001", "x": "175", "y": "190", "w": "28", "h": "28",
        "devref": "Load_Breaker_Switch_SMART.zwk.icn.g", "p_NameString": "Y1",
    })
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", {"id": "188000001", "x": "180", "y": "250", "w": "30", "h": "28"})
    ET.SubElement(layer, "Text", {"id": "8000001", "x": "130", "y": "110", "w": "60", "h": "20", "ts": "SMART"})
    ET.SubElement(layer, "Text", {"id": "8000002", "x": "145", "y": "40", "w": "125", "h": "50", "ts": "34661"})
    return ET.ElementTree(root)


def test_detail_filename_uses_main_prefix_facname_and_rmu_name():
    assert build_rmu_detail_filename(
        Path("JED-NTH-ABH-03.sln.pic.g"), "AH303", "34661"
    ) == "JED-NTH-ABH-AH303-34661.sln.pic.g"
    # Uploaded/copied filenames must not leak the copy suffix into ahref.
    assert build_rmu_detail_filename(
        Path("JED-NTH-ABH-03.sln.pic(6).g"), "AH303", "40597"
    ) == "JED-NTH-ABH-AH303-40597.sln.pic.g"


def test_smart_rmu_poke_reuses_identification_and_is_idempotent():
    tree = _tree()
    source = Path("JED-NTH-ABH-03.sln.pic.g")
    identification = identify_rmus(tree, source, name_positions=("top",), smart_in_type=True)
    assert identification.cabinet_count == 1
    assert identification.items[0].name == "34661"
    assert identification.items[0].smart_count == 1

    first = apply_smart_rmu_pokes(tree, source, identification)
    assert first.intelligent_rmu_count == 1
    assert first.added_count == 1
    assert first.skipped_count == 0

    layer = list(tree.getroot())[0]
    pokes = [e for e in list(layer) if e.tag == "poke"]
    assert len(pokes) == 1
    poke = pokes[0]
    assert list(layer)[0] is poke  # background layer: behind RMU/name graphics
    assert poke.get("id") == "17000001"
    assert poke.get("ahref") == "JED-NTH-ABH-AH303-34661.sln.pic.g"
    assert poke.get("switchapp") == "1"
    assert poke.get("switchappflag") == "1"
    assert poke.get("fm") == "0"
    assert poke.get("ls") == "0"
    # v2.18.63+: hit area precisely wraps the identified RMU name Text only.
    assert poke.get("x") == "145"
    assert poke.get("y") == "40"
    assert poke.get("w") == "125"
    assert poke.get("h") == "50"

    second = apply_smart_rmu_pokes(tree, source, identification)
    assert second.added_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count == 1
    assert len([e for e in list(layer) if e.tag == "poke"]) == 1


def test_non_intelligent_rmu_gets_no_poke():
    tree = _tree()
    for element in tree.getroot().iter():
        if element.tag == "Text" and element.get("ts") == "SMART":
            element.set("ts", "NORMAL")
        if element.tag == "CBreakerDis":
            element.set("devref", "Load_Breaker_Switch_NON-SMART.zwk.icn.g")
    source = Path("JED-NTH-ABH-03.sln.pic.g")
    identification = identify_rmus(tree, source, name_positions=("top",), smart_in_type=True)
    result = apply_smart_rmu_pokes(tree, source, identification)
    assert result.intelligent_rmu_count == 0
    assert not any(e.tag == "poke" for e in tree.getroot().iter())
