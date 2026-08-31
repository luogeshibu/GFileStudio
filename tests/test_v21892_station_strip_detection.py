from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.station_poke_engine import apply_station_pokes, _STATION_JUMP_POKE_REFERENCE_ATTRS


def _empty_identification(path: Path) -> RmuIdentificationResult:
    return RmuIdentificationResult(file_path=path)


def _add_strip(layer: ET.Element, *, poke_id: int, text_id: int, x: float, y: float, w: float, label: str) -> None:
    ET.SubElement(layer, "poke", {
        "id": str(poke_id), "x": str(x), "y": str(y + 10), "w": str(w), "h": "43",
        "fc": "100,100,100", "fcc": "#646464", "RectStyle": "1", "p_RectStyle": "1", "fm": "1",
    })
    ET.SubElement(layer, "Text", {
        "id": str(text_id), "x": str(x), "y": str(y), "w": str(w), "h": "61", "ts": label,
        "fs": "55", "lc": "255,255,255", "lcc": "#ffffff",
    })


def test_ajwd_five_existing_station_strips_are_detected_and_long_design_label_is_not(tmp_path: Path) -> None:
    file_path = tmp_path / "JED-CTL-AJWD-15.sln.pic.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})

    # The five real station-jump shapes shown in the AJWD sample.
    labels = ["JM2-J2", "5MR-23", "FEL 03", "BWD2-49", "SALAB-12"]
    for idx, label in enumerate(labels):
        _add_strip(layer, poke_id=17001000 + idx, text_id=80001000 + idx, x=100 + idx * 220, y=800, w=170, label=label)

    # A nearby design/equipment label that used to enter the line-endpoint fallback.
    ET.SubElement(layer, "FeedLine", {"id": "35009999", "d": "10,100 20,100", "x": "10", "y": "97", "w": "16", "h": "6"})
    ET.SubElement(layer, "Text", {
        "id": "80009999", "x": "22", "y": "90", "w": "220", "h": "35", "ts": "V2-W-J-H-0017",
        "fs": "30", "lc": "255,85,0", "lcc": "#ff5500",
    })

    resolved = {
        "JM2": "JED-CTL-JM2",
        "5MR": "JED-CTL-5MR",
        "FEL": "JED-CTL-FEL",
        "BWD2": "JED-CTL-BWD2",
        "SALAB": "JED-CTL-SALAB",
    }

    result = apply_station_pokes(
        ET.ElementTree(root),
        file_path,
        _empty_identification(file_path),
        current_station_name="AJWD",
        station_resolver=lambda key: SimpleNamespace(station_full_name=resolved[key]),
    )

    assert result.candidate_count == 5
    assert result.eligible_count == 5
    assert result.updated_count == 5
    assert result.skipped_count == 0
    assert {record.label_text for record in result.records} == set(labels)
    assert {record.station_key for record in result.records} == {"JM2", "5MR", "FEL", "BWD2", "SALAB"}
    assert all(record.target_file.endswith(".sln.pic.g") for record in result.records)
    assert all(record.recognition_source == "existing_poke" for record in result.records)

    station_pokes = [e for e in list(layer) if e.tag == "poke"]
    assert len(station_pokes) == 5
    for poke in station_pokes:
        for key, value in _STATION_JUMP_POKE_REFERENCE_ATTRS.items():
            assert poke.get(key) == value, (poke.get("id"), key)
