from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_engine import (
    infer_element_id_patterns,
    inspect_file_ids,
    repair_file_duplicate_ids,
)
from g_file_studio.models import IdAction, IdSettings, InputMode
from g_file_studio.processors.id_processor import process_ids
from g_file_studio.services.id_rule_service import IdRule, IdRuleService


def _write_duplicate_g(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800"><Layer>'
        '<Connector id="34000068" />'
        '<Connector id="34000068" />'
        '<Connector id="34000069" />'
        '<Text id="8000001" />'
        '<Text id="8000002" />'
        '<ConnectLine id="99" link="0,0,34000068" />'
        '</Layer></G>',
        encoding="utf-8",
    )


def test_direct_layer_duplicate_repair_uses_same_type_format(tmp_path: Path):
    source = tmp_path / "duplicate.sln.pic.g"
    output = tmp_path / "fixed.sln.pic.g"
    _write_duplicate_g(source)

    before = inspect_file_ids(source)
    assert len(before.duplicate_groups) == 1
    assert before.duplicate_element_count == 1

    result = repair_file_duplicate_ids(source, output)
    assert result.changed_element_ids == 1
    assert result.final_duplicate_count == 0
    assert result.changes == [("Connector", "34000068", "34000070")]

    root = ET.parse(output).getroot()
    layer = next(child for child in root if child.tag == "Layer")
    ids = [child.get("id") for child in list(layer)]
    assert ids[:3] == ["34000068", "34000070", "34000069"]
    assert list(layer)[-1].get("link") == "0,0,34000068"


def test_short_duplicate_recovers_majority_prefix_and_length(tmp_path: Path):
    source = tmp_path / "short.sln.pic.g"
    output = tmp_path / "short-fixed.sln.pic.g"
    source.write_text(
        '<G><Layer>'
        '<Connector id="34000070" />'
        '<Connector id="34000071" />'
        '<Connector id="34000125" />'
        '<Connector id="130" />'
        '<Connector id="130" />'
        '</Layer></G>',
        encoding="utf-8",
    )

    result = repair_file_duplicate_ids(source, output)
    assert result.changes == [("Connector", "130", "34000130")]
    ids = [item.get("id") for item in list(ET.parse(output).getroot().find("Layer"))]
    assert ids[-2:] == ["130", "34000130"]


def test_pattern_build_keeps_fixed_total_length():
    elements = [
        ET.Element("Connector", id=value)
        for value in ("34000001", "34000068", "34000999", "34001000", "34010000")
    ]
    pattern = infer_element_id_patterns(elements)["Connector"]
    assert pattern.prefix == "34"
    assert pattern.total_length == 8
    assert pattern.build(1) == "34000001"
    assert pattern.build(68) == "34000068"
    assert pattern.build(999) == "34000999"
    assert pattern.build(1000) == "34001000"
    assert pattern.build(10000) == "34010000"


def test_independent_id_processor_checks_or_repairs_ids_without_csv(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "input"
    check_output = tmp_path / "check"
    repair_output = tmp_path / "repair"
    source_dir.mkdir(); check_output.mkdir(); repair_output.mkdir()
    _write_duplicate_g(source_dir / "a.sln.pic.g")
    (source_dir / "b.sln.pic.g").write_text(
        '<G><Layer><Connector id="34000068" /></Layer></G>', encoding="utf-8"
    )

    rule_file = tmp_path / "id_rules.json"
    service = IdRuleService(rule_file)
    service.save_rules([IdRule("Connector", "34", 8), IdRule("Text", "8", 7), IdRule("ConnectLine", "9", 2)])
    import g_file_studio.processors.id_processor as processor
    monkeypatch.setattr(processor, "IdRuleService", lambda: service)

    check_logs = []
    checked = process_ids(IdSettings(source_path=source_dir, input_mode=InputMode.DIRECTORY, output_dir=check_output, action=IdAction.CHECK), check_logs.append, None)
    assert checked.statistics["duplicate_id_kind_count"] == 1
    assert checked.statistics["repaired_id_count"] == 0

    repair_logs = []
    repaired = process_ids(IdSettings(source_path=source_dir, input_mode=InputMode.DIRECTORY, output_dir=repair_output, action=IdAction.REPAIR), repair_logs.append, None)
    assert repaired.statistics["repaired_id_count"] == 1
    fixed = inspect_file_ids(repair_output / "a.sln.pic.g")
    assert not fixed.has_duplicates
    assert any("34000068 → 34000070" in line for line in repair_logs)
