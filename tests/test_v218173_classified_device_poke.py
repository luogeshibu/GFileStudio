from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.classified_device_poke_engine import (
    DEVICE_NAME_MAX_DISTANCE,
    apply_classified_device_pokes,
    assign_device_names,
    find_classified_devices,
)


def _tree_with_two_same_names() -> tuple[ET.ElementTree, ET.Element]:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "CBreakerDis", {
        "id": "41000001", "x": "100", "y": "100", "w": "30", "h": "30",
        "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
    })
    ET.SubElement(layer, "CBreakerDis", {
        "id": "41000002", "x": "500", "y": "100", "w": "30", "h": "30",
        "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000001", "x": "110", "y": "40", "w": "100", "h": "25", "ts": "AR-1001",
        "lc": "255,0,0", "lcc": "#ff0000",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000002", "x": "510", "y": "40", "w": "100", "h": "25", "ts": "AR-1001",
        "lc": "255,0,0", "lcc": "#ff0000",
    })
    return ET.ElementTree(root), layer


ENTRIES = (
    ("Auto_Recloser_SMART.zwk.icn.g", "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART", "AR"),
    ("Load_Breaker_Switch_SMART.zwk.icn.g", "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART", "LBS"),
    ("Sectionalizer_Smart.zwk.icn.g", "#Sectionalizer_Smart.zwk.icn.g:Sectionalizer_Smart", "SEC"),
)


def test_equal_text_content_with_different_text_ids_is_assigned_to_different_devices() -> None:
    tree, _layer = _tree_with_two_same_names()
    devices = find_classified_devices(tree.getroot(), ENTRIES)
    assignments = assign_device_names(devices)
    assert len(devices) == 2
    assert len(assignments) == 2
    assert {item.device_id for item in assignments} == {"41000001", "41000002"}
    assert {item.text_id for item in assignments} == {"81000001", "81000002"}
    assert [item.name for item in assignments] == ["AR-1001", "AR-1001"]


def test_one_text_instance_can_only_belong_to_one_device() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    for index, x in enumerate((100, 160), 1):
        ET.SubElement(layer, "CBreakerDis", {
            "id": f"4100000{index}", "x": str(x), "y": "100", "w": "30", "h": "30",
            "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
        })
    ET.SubElement(layer, "Text", {
        "id": "81000001", "x": "130", "y": "60", "w": "80", "h": "25", "ts": "AR-2001",
        "lc": "255,0,0", "lcc": "#ff0000",
    })
    assignments = assign_device_names(find_classified_devices(root, ENTRIES))
    assert len(assignments) == 1
    assert assignments[0].text_id == "81000001"


def test_name_farther_than_300_is_not_assigned() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "CBreakerDis", {
        "id": "41000001", "x": "100", "y": "100", "w": "30", "h": "30",
        "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000001", "x": str(100 + DEVICE_NAME_MAX_DISTANCE + 100), "y": "100",
        "w": "80", "h": "25", "ts": "AR-3001", "lc": "255,0,0", "lcc": "#ff0000",
    })
    assignments = assign_device_names(find_classified_devices(root, ENTRIES))
    assert assignments == []


def test_device_poke_uses_same_detail_target_rule_and_keeps_duplicate_name_instances(tmp_path: Path) -> None:
    tree, layer = _tree_with_two_same_names()
    result = apply_classified_device_pokes(
        tree,
        tmp_path / "overview.sln.pic.g",
        classification_marker_entries=ENTRIES,
        database_prefixes={"ar-1001": "JED-CTL-TEST-AH301"},
    )
    assert result.device_count == 2
    assert result.assigned_name_count == 2
    assert result.added_count == 2
    pokes = [e for e in list(layer) if e.tag == "poke" and e.get("gfs_device_poke") == "1"]
    assert len(pokes) == 2
    assert {poke.get("gfs_device_text_id") for poke in pokes} == {"81000001", "81000002"}
    assert {poke.get("gfs_device_element_id") for poke in pokes} == {"41000001", "41000002"}
    assert {poke.get("ahref") for poke in pokes} == {"JED-CTL-TEST-AH301-AR-1001.com.pic.g"}


def test_exact_ar_lbs_sec_classifications_select_only_those_devices() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    rows = (
        ("AR", "ar.g", "AR_BODY", "41000001", 100),
        ("LBS", "lbs.g", "LBS_BODY", "41000002", 300),
        ("SEC", "sec.g", "SEC_BODY", "41000003", 500),
        ("FUSE", "fuse.g", "FUSE_BODY", "41000004", 700),
    )
    entries = []
    for marker, file_name, body, element_id, x in rows:
        ET.SubElement(layer, "CBreakerDis", {
            "id": element_id, "x": str(x), "y": "100", "w": "30", "h": "30",
            "devref": f"#{file_name}:{body}",
        })
        entries.append((file_name, f"#{file_name}:{body}", marker))

    devices = find_classified_devices(root, tuple(entries))
    assert [item.marker for item in devices] == ["AR", "LBS", "SEC"]
    assert [item.element_id for item in devices] == ["41000001", "41000002", "41000003"]


def test_device_poke_does_not_convert_existing_rmu_poke(tmp_path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "CBreakerDis", {
        "id": "41000001", "x": "100", "y": "100", "w": "30", "h": "30",
        "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000001", "x": "105", "y": "60", "w": "100", "h": "25", "ts": "AR-9001",
        "lc": "255,0,0", "lcc": "#ff0000",
    })
    legacy_rmu = ET.SubElement(layer, "poke", {
        "id": "91000001", "x": "105", "y": "60", "w": "100", "h": "25",
        "ahref": "OLD-RMU.com.pic.g", "gfs_rmu_poke": "1", "gfs_rmu_name": "SOME-RMU",
    })

    result = apply_classified_device_pokes(
        ET.ElementTree(root),
        tmp_path / "overview.sln.pic.g",
        classification_marker_entries=ENTRIES,
        database_prefixes={"ar-9001": "JED-CTL-TEST-AH301"},
    )
    assert result.added_count == 1
    assert legacy_rmu.get("gfs_rmu_poke") == "1"
    assert legacy_rmu.get("gfs_device_poke") is None
    device_pokes = [e for e in layer if e.tag == "poke" and e.get("gfs_device_poke") == "1"]
    assert len(device_pokes) == 1


def test_classified_device_name_must_be_red_and_top_or_right() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "CBreakerDis", {
        "id": "117000292", "x": "1358", "y": "3046", "w": "40", "h": "40",
        "devref": "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S",
    })
    # This is the exact failure mode from JED-STH-ADEL-06: the nearer-looking
    # numeric label is white and therefore must never become the LBS name.
    ET.SubElement(layer, "Text", {
        "id": "8000229", "x": "1226", "y": "2992", "w": "125", "h": "50",
        "ts": "96566", "lc": "255,255,255", "lcc": "#ffffff",
    })
    ET.SubElement(layer, "Text", {
        "id": "8000295", "x": "1404", "y": "3049", "w": "182", "h": "50",
        "ts": "LBS1197", "lc": "255,0,0", "lcc": "#ff0000",
    })
    entries = (("RMU_LBS_S.zwk.icn.g", "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S", "LBS"),)
    assignments = assign_device_names(find_classified_devices(root, entries))
    assert len(assignments) == 1
    assert assignments[0].name == "LBS1197"
    assert assignments[0].text_id == "8000295"
    assert assignments[0].direction == "right"


def test_red_name_on_left_or_below_is_rejected() -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "CBreakerDis", {
        "id": "41000001", "x": "100", "y": "100", "w": "40", "h": "40",
        "devref": "#Auto_Recloser_SMART.zwk.icn.g:Auto_Recloser_SMART",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000001", "x": "0", "y": "105", "w": "80", "h": "25",
        "ts": "AR-LEFT", "lc": "255,0,0", "lcc": "#ff0000",
    })
    ET.SubElement(layer, "Text", {
        "id": "81000002", "x": "105", "y": "160", "w": "80", "h": "25",
        "ts": "AR-BELOW", "lc": "255,0,0", "lcc": "#ff0000",
    })
    assignments = assign_device_names(find_classified_devices(root, ENTRIES))
    assert assignments == []
