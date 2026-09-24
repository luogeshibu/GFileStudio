from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.station_poke_engine import (
    apply_station_pokes,
    build_station_target_file,
    extract_interval_locate_label,
    extract_rmu_locate_label,
)


def test_rmu_locate_label_requires_parenthesized_pure_digits() -> None:
    assert extract_rmu_locate_label("(14020)") == "14020"
    assert extract_rmu_locate_label("（14020）") == "14020"
    assert extract_rmu_locate_label("14020") == ""
    assert extract_rmu_locate_label("(42764 RMU)") == ""
    assert extract_rmu_locate_label("DHN-40") == ""
    assert extract_rmu_locate_label("5MR-23") == ""
    assert build_station_target_file("JED-CTL-DHN", "(14020)") == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=14020&&scaleFlag=true"
    )
    assert build_station_target_file("JED-CTL-DHN", "14020") == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=14020&&scaleFlag=true"
    )
    assert extract_interval_locate_label("RDS-09") == "AH309"
    assert extract_interval_locate_label("DHN-40") == "AH340"
    assert extract_interval_locate_label("JM2-J2") == ""
    assert build_station_target_file("JED-CTL-RDS", "AH309") == (
        "JED-CTL-RDS.sln.pic.g?locateLabel=AH309&&scaleFlag=true"
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
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
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


def test_pure_numeric_text_is_not_a_station_candidate(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "10,10 100,100", "link": "0,0,34000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "35033",
    })

    resolver_called = False

    def resolver(_key: str) -> SimpleNamespace:
        nonlocal resolver_called
        resolver_called = True
        return SimpleNamespace(station_full_name="JED-NTH-ABN")

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=resolver,
    )

    assert result.candidate_count == 0
    assert result.updated_count == 0
    assert not resolver_called
    assert not any(element.tag == "poke" and element.get("ahref") for element in list(layer))


def test_ambiguous_parenthesized_numbers_do_not_guess_locate_label(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "150,145 170,145", "node_area": "0,0,34000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "76", "w": "64", "h": "21", "ts": "(14020)",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000003", "x": "118", "y": "130", "w": "64", "h": "21", "ts": "(14021)",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.candidate_count == 1
    assert result.updated_count == 0
    assert result.skipped_count == 1
    assert "不唯一" in result.records[0].reason


def test_station_poke_uses_interval_target_without_adjacent_rmu_label(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "Node", {"id": "34000001"})
    ET.SubElement(layer, "FeedLine", {
        "id": "35000001", "d": "10,10 100,100", "link": "0,0,34000001",
    })
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "FRSH-44",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "76", "w": "64", "h": "21", "ts": "14020",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-NTH-FRSH"),
    )

    assert result.updated_count == 1
    assert result.changes[0].target_file == (
        "JED-NTH-FRSH.sln.pic.g?locateLabel=AH344&&scaleFlag=true"
    )
    assert result.changes[0].locate_label == "AH344"


def test_station_poke_does_not_require_explicit_topology(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
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
    assert result.changes[0].target_file == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=14020&&scaleFlag=true"
    )


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
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
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


def test_station_poke_ignores_line_branch_shape(tmp_path: Path) -> None:
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
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
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
    assert result.skipped_count == 0
    assert result.updated_count == 1
    assert result.changes[0].target_file == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=AH340&&scaleFlag=true"
    )


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
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
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
    assert result.changes[0].target_file == (
        "JED-CTL-DHN.sln.pic.g?locateLabel=AH340&&scaleFlag=true"
    )
    assert result.changes[0].locate_label == "AH340"


def test_station_name_near_classified_device_is_not_excluded(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Rect", {
        "id": "90000001", "x": "300", "y": "105", "w": "30", "h": "30",
        "devref": "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
        classification_marker_entries=(
            ("Fuse_NON_SMART.zwk.icn.g", "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART", "FUSE"),
        ),
    )

    assert result.classification_excluded_count == 0
    assert result.skipped_count == 0
    assert result.updated_count == 1


def test_station_name_with_distant_classified_device_is_allowed(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Rect", {
        "id": "90000001", "x": "500", "y": "105", "w": "30", "h": "30",
        "devref": "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
        classification_marker_entries=(
            ("Fuse_NON_SMART.zwk.icn.g", "#Fuse_NON_SMART.zwk.icn.g:Fuse_NON_SMART", "FUSE"),
        ),
    )

    assert result.classification_excluded_count == 0
    assert result.updated_count == 1


def test_rmu_locate_label_between_200_and_300_is_used(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "-105", "w": "64", "h": "21", "ts": "(14020)",
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


def test_rmu_locate_label_over_300_is_not_used(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "100", "y": "100", "w": "100", "h": "31",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000001", "x": "115", "y": "105", "w": "70", "h": "21", "ts": "DHN-40",
    })
    ET.SubElement(layer, "Text", {
        "id": "80000002", "x": "118", "y": "-240", "w": "64", "h": "21", "ts": "(14020)",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-DHN"),
    )

    assert result.updated_count == 1
    assert result.changes[0].locate_label == "AH340"


def test_station_candidate_rule_is_text_plus_colored_background_not_device_marker(tmp_path: Path) -> None:
    file_path = tmp_path / "source.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "poke", {
        "id": "17000001", "x": "1200.5", "y": "1526.5", "w": "150", "h": "50",
        "fc": "100,100,100", "fcc": "#646464", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": "8000253", "x": "1226", "y": "1536", "w": "112", "h": "32", "ts": "QWZ2-32",
    })
    ET.SubElement(layer, "Text", {
        "id": "8000254", "x": "1228", "y": "1578", "w": "93", "h": "32", "ts": "(96432)",
    })
    ET.SubElement(layer, "Rect", {
        "id": "90000001", "x": "1380", "y": "1536", "w": "30", "h": "30",
        "devref": "#Transformer_OH.icn.g:Transformer_OH",
    })

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        RmuIdentificationResult(file_path=file_path),
        current_station_name="ABH",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-QWZ2"),
        classification_marker_entries=(
            ("Transformer_OH.icn.g", "#Transformer_OH.icn.g:Transformer_OH", "Transformer_OH"),
        ),
    )

    assert result.updated_count == 1
    assert result.classification_excluded_count == 0
    assert result.changes[0].locate_label == "96432"
    assert result.changes[0].target_file == (
        "JED-CTL-QWZ2.sln.pic.g?locateLabel=96432&&scaleFlag=true"
    )
