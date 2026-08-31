from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.station_poke_engine import apply_station_pokes
from g_file_studio.models import InputMode
from g_file_studio.processors.poke_processor import PokeProcessingSettings, process_pokes
from g_file_studio.services.poke_report_service import write_poke_reports


def test_station_result_records_skip_reason_for_database_failure(tmp_path: Path) -> None:
    path = tmp_path / "sample.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "FeedLine", {"id": "35000001", "d": "10,10 100,100", "x": "10", "y": "10", "w": "90", "h": "90"})
    ET.SubElement(layer, "Text", {"id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "FRSH-44"})
    tree = ET.ElementTree(root)
    identification = RmuIdentificationResult(file_path=path)

    def resolver(_key: str):
        raise ValueError("数据库未找到 SUBSTATION.NAME='FRSH' 的变电站记录")

    result = apply_station_pokes(
        tree,
        path,
        identification,
        current_station_name="ABH",
        station_resolver=resolver,
    )
    assert result.skipped_count == 1
    assert len(result.records) == 1
    assert result.records[0].label_text == "FRSH-44"
    assert result.records[0].station_key == "FRSH"
    assert result.records[0].action == "skipped"
    assert "数据库" in result.records[0].reason


def test_poke_report_contains_summary_target_and_skip_reason(tmp_path: Path) -> None:
    stats = {
        "input_count": 1,
        "processed_count": 1,
        "rmu_identified_total": 8,
        "smart_rmu_identified_total": 3,
        "rmu_added": 2,
        "rmu_updated": 1,
        "rmu_skipped": 0,
        "station_candidates": 4,
        "station_resolved_count": 3,
        "station_added": 2,
        "station_updated": 1,
        "station_skipped": 1,
        "station_duplicate_removed": 1,
    }
    file_summaries = [{
        "File": "JED-CTL-AJWD-15.sln.pic.g",
        "FacID": "123",
        "FeederBusinessName": "JED-CTL-AJWD-AJWD15",
        "RMURecognized": 8,
        "SmartRMU": 3,
        "RMUAdded": 2,
        "RMUUpdated": 1,
        "RMUSkipped": 0,
        "StationCandidates": 4,
        "StationResolved": 3,
        "StationAdded": 2,
        "StationUpdated": 1,
        "StationSkipped": 1,
        "DuplicatesRemoved": 1,
        "Status": "WARNING",
        "Reason": "部分 Poke 未加跳转",
    }]
    rows = [
        {
            "File": "JED-CTL-AJWD-15.sln.pic.g",
            "Type": "rmu",
            "SourceName": "34661",
            "StationKey": "",
            "ResolvedBusinessName": "JED-NTH-ABH-AH303",
            "Action": "added",
            "PokeID": "17000001",
            "TargetAhref": "JED-NTH-ABH-AH303-34661.sln.pic.g",
            "Confidence": "HIGH",
            "RecognitionSource": "rmu_identification",
            "Reason": "公共 RMU 识别成功，已新增。",
        },
        {
            "File": "JED-CTL-AJWD-15.sln.pic.g",
            "Type": "station",
            "SourceName": "SALAB-12",
            "StationKey": "SALAB",
            "ResolvedBusinessName": "",
            "Action": "skipped",
            "PokeID": "",
            "TargetAhref": "",
            "Confidence": "MEDIUM",
            "RecognitionSource": "line_endpoint",
            "Reason": "数据库未找到 SUBSTATION.NAME='SALAB' 的变电站记录",
        },
    ]
    csv_path, html_path = write_poke_reports(tmp_path, statistics=stats, file_summaries=file_summaries, detail_rows=rows)
    assert csv_path.is_file()
    assert html_path.is_file()
    text = html_path.read_text(encoding="utf-8")
    assert "识别 RMU 总数" in text
    assert "新增 RMU Poke" in text
    assert "成功解析站点跳转" in text
    assert "JED-NTH-ABH-AH303-34661.sln.pic.g" in text
    assert "SALAB-12" in text
    assert "数据库未找到 SUBSTATION.NAME=&#x27;SALAB&#x27;" in text


def test_process_pokes_generates_report_and_exposes_report_paths(tmp_path: Path) -> None:
    source = tmp_path / "source.g"
    root = ET.Element("G", {"facID": "123"})
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "FeedLine", {"id": "35000001", "d": "10,10 100,100", "x": "10", "y": "10", "w": "90", "h": "90"})
    ET.SubElement(layer, "Text", {"id": "80000001", "x": "105", "y": "95", "w": "90", "h": "25", "ts": "DHN-40"})
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)

    class FakeDb:
        def resolve_g_file_context(self, fac_id: str):
            assert fac_id == "123"
            return SimpleNamespace(
                feeder_full_name="JED-NTH-ABH-AH303",
                station_name="ABH",
            )

        def resolve_station_context(self, station_name: str):
            assert station_name == "DHN"
            return SimpleNamespace(station_full_name="JED-CTL-DHN")

    out = tmp_path / "out"
    settings = PokeProcessingSettings(
        source_path=source,
        input_mode=InputMode.SINGLE_FILE,
        output_dir=out,
        enable_rmu_poke=False,
        enable_station_poke=True,
    )
    result = process_pokes(settings, FakeDb(), log=lambda _msg: None)
    assert Path(result.statistics["html_report_path"]).is_file()
    assert Path(result.statistics["csv_report_path"]).is_file()
    assert result.statistics["station_candidates"] == 1
    assert result.statistics["station_resolved_count"] == 1
    assert result.statistics["station_added"] == 1
    report = Path(result.statistics["html_report_path"]).read_text(encoding="utf-8")
    assert "DHN-40" in report
    assert "JED-CTL-DHN.sln.pic.g" in report


def test_poke_page_has_open_report_button() -> None:
    source = Path("g_file_studio/ui/pages/poke_page.py").read_text(encoding="utf-8")
    assert "打开 Poke 报告" in source
    assert 'result.statistics.get("html_report_path"' in source
