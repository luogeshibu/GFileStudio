from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.connection_engine import repair_tree_connections
from g_file_studio.models import (
    BasicOutputConflictAction,
    BasicSettings,
    ConnectionRepairSettings,
    InputMode,
)
from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.processors.connection_processor import process_connection_points

ROOT = Path(__file__).resolve().parents[1]
PROBLEM_FILE = ROOT / "tests/data/connection-problem.g"
GOOD_FILE = ROOT / "tests/data/no-connection-problem.g"
CONNECTION_ATTRS = {"node_area", "link"}


def _layer(tree: ET.ElementTree) -> ET.Element:
    return tree.getroot().find("Layer")


def _by_id(tree: ET.ElementTree) -> dict[str, ET.Element]:
    return {
        element.get("id"): element
        for element in list(_layer(tree))
        if element.get("id")
    }


def _groups(value: str | None) -> set[tuple[str, str, str]]:
    result: set[tuple[str, str, str]] = set()
    for group in (value or "").split(";"):
        parts = tuple(part.strip() for part in group.split(",", 2))
        if len(parts) == 3 and parts[2]:
            result.add(parts)
    return result


def test_problem_file_repairs_missing_ground_switch_and_q1_q2_connections_only():
    tree = ET.parse(PROBLEM_FILE)
    before = {
        element_id: dict(element.attrib)
        for element_id, element in _by_id(tree).items()
    }

    result = repair_tree_connections(tree, PROBLEM_FILE)
    after = _by_id(tree)

    assert result.added_reference_count == 24
    assert result.updated_reference_count == 0
    assert result.changed_element_count == 14

    expected_changed_ids = {
        "188000010",
        "188000011",
        "188000023",
        "188000026",
        "117000024",
        "117000027",
        "34000012",
        "34000014",
        "34000025",
        "34000028",
        "34000029",
        "34000030",
        "34000032",
        "34000033",
    }
    assert set(result.changed_element_ids) == expected_changed_ids

    # The four grounding switches now have green connection-point references.
    assert _groups(after["188000010"].get("node_area")) == {("0", "0", "34000012")}
    assert _groups(after["188000011"].get("node_area")) == {("0", "0", "34000014")}
    assert _groups(after["188000023"].get("node_area")) == {("0", "0", "34000029")}
    assert _groups(after["188000026"].get("node_area")) == {("0", "0", "34000032")}

    # Q1 and Q2 now have both left and right connection points.
    assert _groups(after["117000024"].get("node_area")) == {
        ("0", "1", "34000025"),
        ("1", "0", "34000030"),
    }
    assert _groups(after["117000027"].get("node_area")) == {
        ("0", "1", "34000028"),
        ("1", "0", "34000033"),
    }

    # Every non-connection attribute remains byte-for-byte equal at XML attribute level.
    for element_id, element in after.items():
        before_non_connection = {
            key: value for key, value in before[element_id].items() if key not in CONNECTION_ATTRS
        }
        after_non_connection = {
            key: value for key, value in element.attrib.items() if key not in CONNECTION_ATTRS
        }
        assert after_non_connection == before_non_connection

    assert "20000000" in after  # Existing Merge is preserved.


def test_repaired_problem_matches_reference_connection_sets():
    problem_tree = ET.parse(PROBLEM_FILE)
    good_tree = ET.parse(GOOD_FILE)
    repair_tree_connections(problem_tree, PROBLEM_FILE)
    problem = _by_id(problem_tree)
    good = _by_id(good_tree)

    for element_id in set(problem) & set(good):
        for attribute in CONNECTION_ATTRS:
            assert _groups(problem[element_id].get(attribute)) == _groups(
                good[element_id].get(attribute)
            )


def test_good_file_is_idempotent_and_receives_no_changes():
    tree = ET.parse(GOOD_FILE)
    result = repair_tree_connections(tree, GOOD_FILE)
    assert result.added_reference_count == 0
    assert result.updated_reference_count == 0
    assert result.changed_element_count == 0
    assert result.changed_attribute_count == 0


def test_connection_processor_writes_valid_output(tmp_path: Path):
    output_dir = tmp_path / "out"
    settings = ConnectionRepairSettings(
        source_path=PROBLEM_FILE,
        input_mode=InputMode.SINGLE_FILE,
        output_dir=output_dir,
        output_conflict_action=BasicOutputConflictAction.OVERWRITE,
    )
    logs: list[str] = []
    result = process_connection_points(settings, logs.append)

    assert result.success
    assert result.statistics["added_connection_reference_count"] == 24
    output = output_dir / PROBLEM_FILE.name
    assert output.is_file()
    ET.parse(output)
    assert any("只修复 node_area/link" in line for line in logs)


def test_basic_processor_repairs_connections_only_when_checkbox_setting_enabled(tmp_path: Path):
    disabled_out = tmp_path / "disabled"
    disabled = process_basic(
        BasicSettings(
            source_path=PROBLEM_FILE,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=disabled_out,
            repair_connection_points=False,
        )
    )
    assert disabled.success
    assert disabled.statistics["connection_repair_enabled"] is False
    assert disabled.statistics["added_connection_reference_count"] == 0
    disabled_tree = ET.parse(disabled_out / PROBLEM_FILE.name)
    assert _groups(_by_id(disabled_tree)["188000010"].get("node_area")) == set()

    enabled_out = tmp_path / "enabled"
    logs: list[str] = []
    enabled = process_basic(
        BasicSettings(
            source_path=PROBLEM_FILE,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=enabled_out,
            repair_connection_points=True,
        ),
        logs.append,
    )
    assert enabled.success
    assert enabled.statistics["connection_repair_enabled"] is True
    assert enabled.statistics["added_connection_reference_count"] == 24
    enabled_tree = ET.parse(enabled_out / PROBLEM_FILE.name)
    assert _groups(_by_id(enabled_tree)["188000010"].get("node_area")) == {
        ("0", "0", "34000012")
    }
    assert any("[连接点修复]" in line for line in logs)


def test_basic_page_no_longer_exposes_legacy_connection_repair_module():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("连接点修复")' not in source
    assert 'QCheckBox("修复连接点（补齐 node_area / link）")' not in source
    assert 'self._build_connection_repair()' not in source
    assert '"repair_connection_points": self.repair_connection_points.isChecked()' not in source
    assert '"basic/repair_connection_points"' not in source
    assert "process_connection_points" not in source
