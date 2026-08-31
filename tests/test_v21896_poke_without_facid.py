from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes
from g_file_studio.models import InputMode
from g_file_studio.processors.poke_processor import PokeProcessingSettings, process_pokes
from g_file_studio.services.database_service import OracleDatabaseService


def _item(name: str, rect_id: str, x: float) -> RmuIdentification:
    return RmuIdentification(
        rect_id=rect_id,
        name=name,
        name_position="top",
        rmu_type="2L1T",
        l_count=2,
        t_count=1,
        smart_count=1,
        confidence="HIGH",
        rect_x=x,
        rect_y=100,
        rect_w=220,
        rect_h=220,
    )


def test_rmu_database_lookup_uses_combined_device_name_to_feeder_chain() -> None:
    service = object.__new__(OracleDatabaseService)
    captured = {}

    def fake_query(sql, params, **kwargs):
        captured["sql"] = sql
        captured["params"] = params
        return [], [
            (3800193660570625893, "16781", 501, 501, "AH303", 601, 601, "ABH", 701, 701, "JED-NTH"),
            (3800193660570625891, "15953", 502, 502, "AH306", 601, 601, "ABH", 701, 701, "JED-NTH"),
        ]

    service.query = fake_query
    contexts, issues = service.resolve_rmu_contexts(["16781", "15953"])
    assert not issues
    assert contexts["16781"].feeder_id == "501"
    assert contexts["16781"].feeder_full_name == "JED-NTH-ABH-AH303"
    assert contexts["15953"].feeder_full_name == "JED-NTH-ABH-AH306"
    sql = captured["sql"].upper()
    assert "DMS_COMBINED_DEVICE" in sql
    assert "C.FEEDER_ID" in sql
    assert "DMS_FEEDER_DEVICE" in sql
    assert "SUBSTATION" in sql
    assert "SUBCONTROLAREA" in sql
    assert "GRAPH_NAME" not in sql


def test_rmu_poke_can_use_different_database_feeder_prefix_per_rmu(tmp_path: Path) -> None:
    path = tmp_path / "station-overview.g"
    root = ET.Element("G")  # deliberately no facID
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    for name, rect_id, x in (("16781", "20000001", 100), ("15953", "20000002", 500)):
        ET.SubElement(layer, "rect", {"id": rect_id, "x": str(x), "y": "100", "w": "220", "h": "220"})
        ET.SubElement(layer, "Text", {"id": f"8{rect_id[1:]}", "x": str(x + 40), "y": "40", "w": "125", "h": "50", "ts": name})
    tree = ET.ElementTree(root)
    identification = RmuIdentificationResult(
        file_path=path,
        cabinet_count=2,
        named_count=2,
        typed_count=2,
        items=[_item("16781", "20000001", 100), _item("15953", "20000002", 500)],
    )

    result = apply_smart_rmu_pokes(
        tree,
        path,
        identification,
        naming_mode="database_rmu_name",
        database_prefixes={
            "16781": "JED-NTH-ABH-AH303",
            "15953": "JED-NTH-ABH-AH306",
        },
    )
    assert result.added_count == 2
    targets = sorted(r.target_file for r in result.records)
    assert targets == [
        "JED-NTH-ABH-AH303-16781.sln.pic.g",
        "JED-NTH-ABH-AH306-15953.sln.pic.g",
    ]


def test_blank_facid_no_longer_blocks_station_poke(tmp_path: Path) -> None:
    source = tmp_path / "blank-facid.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "FeedLine", {"id": "35000001", "d": "10,10 100,100", "x": "10", "y": "10", "w": "90", "h": "90"})
    ET.SubElement(layer, "Text", {"id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "DHN-40"})
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)

    class FakeDb:
        def resolve_station_context(self, station_name: str):
            assert station_name == "DHN"
            return SimpleNamespace(station_full_name="JED-CTL-DHN")

    out = tmp_path / "out"
    result = process_pokes(
        PokeProcessingSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=out,
            enable_rmu_poke=False,
            enable_station_poke=True,
        ),
        FakeDb(),
        log=lambda _msg: None,
    )
    assert result.success
    assert result.statistics["processed_count"] == 1
    tree = ET.parse(out / source.name)
    poke = next(e for e in tree.getroot().iter() if e.tag == "poke")
    assert poke.get("ahref") == "JED-CTL-DHN.sln.pic.g"


def test_process_rmu_pokes_blank_facid_resolves_each_rmu_name(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "station-overview.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "rect", {"id": "20000001", "x": "100", "y": "100", "w": "220", "h": "220"})
    ET.SubElement(layer, "Text", {"id": "80000001", "x": "140", "y": "40", "w": "125", "h": "50", "ts": "16781"})
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)

    identification = RmuIdentificationResult(
        file_path=source,
        cabinet_count=1,
        named_count=1,
        typed_count=1,
        items=[_item("16781", "20000001", 100)],
    )
    monkeypatch.setattr("g_file_studio.processors.poke_processor.identify_rmus", lambda *a, **k: identification)

    class FakeDb:
        def resolve_rmu_contexts(self, names):
            assert list(names) == ["16781"]
            return {
                "16781": SimpleNamespace(
                    rmu_name="16781",
                    feeder_id="501",
                    feeder_full_name="JED-NTH-ABH-AH303",
                    station_name="ABH",
                )
            }, {}

        def resolve_station_context(self, station_name: str):
            raise AssertionError("station resolver not expected")

    out = tmp_path / "out"
    result = process_pokes(
        PokeProcessingSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=out,
            enable_rmu_poke=True,
            enable_station_poke=False,
        ),
        FakeDb(),
        log=lambda _msg: None,
    )
    assert result.success
    assert result.statistics["rmu_database_resolved"] == 1
    assert result.statistics["rmu_added"] == 1
    tree = ET.parse(out / source.name)
    poke = next(e for e in tree.getroot().iter() if e.tag == "poke" and e.get("gfs_rmu_poke") == "1")
    assert poke.get("ahref") == "JED-NTH-ABH-AH303-16781.sln.pic.g"


def test_station_poke_without_facid_does_not_create_self_jump_from_local_title(tmp_path: Path) -> None:
    source = tmp_path / "JED-CTL-AJWD-16.sln.pic.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "ConnectLine", {"id": "34000011", "d": "565,347 565,262", "x": "562", "y": "259", "w": "6", "h": "91"})
    ET.SubElement(layer, "Text", {"id": "8000012", "x": "514", "y": "225", "w": "101", "h": "26", "ts": "AJWD-16"})
    tree = ET.ElementTree(root)

    from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
    from g_file_studio.engines.station_poke_engine import apply_station_pokes
    result = apply_station_pokes(
        tree,
        source,
        RmuIdentificationResult(file_path=source),
        current_station_name="",
        station_resolver=lambda key: SimpleNamespace(station_full_name="JED-CTL-AJWD"),
    )
    assert result.candidate_count == 1
    assert result.added_count == 0
    assert result.skipped_count == 1
    assert "本图当前变电站" in result.records[0].reason
    assert not any(e.tag == "poke" for e in root.iter())
