from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.station_poke_engine import (
    apply_station_pokes,
    build_station_target_file,
    extract_rmu_locate_label,
)


def test_rmu_locate_label_accepts_parenthesized_and_plain_forms() -> None:
    assert extract_rmu_locate_label("(14020)") == "14020"
    assert extract_rmu_locate_label("（14020）") == "14020"
    assert extract_rmu_locate_label("14020") == "14020"
    assert extract_rmu_locate_label("(42764 RMU)") == "42764"
    assert extract_rmu_locate_label("DHN-40") == ""
    assert extract_rmu_locate_label("5MR-23") == ""
    assert build_station_target_file("JED-CTL-DHN", "(14020)") == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=14020&&scaleFlag=true"
    )


def test_station_poke_appends_adjacent_rmu_locate_label(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "150,145 170,145", "node_area": "0,0,34000001",
    })
    ET.SubElement(layer, "ConnectLine", {
        "id": "34000001", "d": "150,145 170,145", "node_area": "0,0,35000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "76", "w": "64", "h": "21", "ts": "(14020)",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.updated_count == 1
    assert result.changes[0].locate_label == "14020"
    assert result.changes[0].target_file == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=14020&&scaleFlag=true"
    )
    poke = next(element for element in list(layer) if element.tag == "poke")
    assert poke.get("ahref") == result.changes[0].target_file


def test_station_poke_keeps_plain_target_without_adjacent_rmu_name(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "10,10 100,100", "link": "0,0,34000001",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "FRSH-44",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-NTH-FRSH"),
    )

    assert result.added_count == 1
    assert result.changes[0].target_file == "JED-NTH-FRSH.sln.pic.g"


def test_strict_mode_does_not_write_locate_label_without_explicit_topology(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "76", "w": "64", "h": "21", "ts": "(14020)",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.records[0].target_file == ""
    assert result.records[0].action == "skipped"
    assert any("拓扑末端" in warning for warning in result.warnings)


def test_same_station_existing_terminal_poke_is_updated_safely(tmp_path: Path) -> None:
    file_path = tmp_path / "JED-STH-ADEL.sln.pic.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "150,145 170,145", "node_area": "0,0,34000001",
    })
    ET.SubElement(layer, "ConnectLine", {
        "id": "34000001", "d": "150,145 170,145", "node_area": "0,0,35000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "ADEL-20",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "76", "w": "64", "h": "21", "ts": "(43204)",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000003", "x": "125", "y": "130", "w": "30", "h": "21",
        "ts": "240", "lcc": "#ffff7f",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ADEL",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-STH-ADEL"),
        allow_same_station_terminals=True,
    )

    assert result.updated_count == 1
    assert result.changes[0].target_file == (
        "JED-STH-ADEL.sln.pic.g?locateLabel=43204&&scaleFlag=true"
    )
    assert result.changes[0].locate_label == "43204"


def test_strict_mode_rejects_station_label_near_internal_branch(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "Node", {"id": "34000002"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "150,145 170,145",
        "link": "0,0,34000001;1,0,34000002",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.candidate_count == 1
    assert result.skipped_count == 1
    assert result.updated_count == 0
    assert "拓扑末端" in result.records[0].reason


def test_dtext_is_never_used_as_device_or_locate_name(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "150,145 170,145", "link": "0,0,34000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "DText", {
        "id": "33000001", "x": "118", "y": "76", "w": "64", "h": "21",
        "ts": "(99999)", "link": "0,0,34000001",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.updated_count == 1
    assert result.changes[0].target_file == "JED-CTL-DHN.sln.pic.g"
    assert result.changes[0].locate_label == ""
