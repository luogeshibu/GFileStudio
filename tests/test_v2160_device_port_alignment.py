from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.connection_engine import repair_tree_connections
from g_file_studio.models import BasicSettings, InputMode
from g_file_studio.processors.basic_processor import process_basic

ROOT = Path(__file__).resolve().parents[1]
PROBLEM_FILE = ROOT / "tests/data/connection-alignment-problem.g"
REFERENCE_FILE = ROOT / "tests/data/connection-alignment-reference.g"
LINE_TAGS = {"ConnectLine", "FeedLine"}


def _by_id(tree: ET.ElementTree) -> dict[str, ET.Element]:
    return {
        element.get("id"): element
        for element in list(tree.getroot().find("Layer"))
        if element.get("id")
    }


def _groups(value: str | None) -> list[tuple[str, str, str]]:
    groups: list[tuple[str, str, str]] = []
    for raw in (value or "").split(";"):
        parts = tuple(part.strip() for part in raw.split(",", 2))
        if len(parts) == 3 and parts[2]:
            groups.append(parts)
    return groups


def test_conservative_alignment_moves_only_verified_half_pixel_devices():
    tree = ET.parse(PROBLEM_FILE)
    original = _by_id(tree)
    before_x = {element_id: element.get("x") for element_id, element in original.items()}
    before_paths = {
        element_id: element.get("d")
        for element_id, element in original.items()
        if element.tag in LINE_TAGS
    }
    before_groups = {
        (element_id, attribute): _groups(element.get(attribute))
        for element_id, element in original.items()
        for attribute in ("node_area", "link")
    }
    reference = _by_id(ET.parse(REFERENCE_FILE))

    result = repair_tree_connections(tree, PROBLEM_FILE)
    actual = _by_id(tree)

    assert result.aligned_device_count == 41
    assert result.adjusted_line_endpoint_count == 0
    assert result.updated_reference_count == 0
    assert result.removed_reference_count == 0

    # Every moved device is a positive half-pixel coordinate normalized to the lower integer and
    # agrees with the user's manually nudged reference file.
    for element_id in result.aligned_device_ids:
        old_x = float(before_x[element_id])
        assert old_x % 1 == 0.5
        assert float(actual[element_id].get("x")) == int(old_x)
        assert actual[element_id].get("x") == reference[element_id].get("x")

    # Line geometry is frozen in conservative mode.
    for element_id, path in before_paths.items():
        assert actual[element_id].get("d") == path

    # No original connection tuple may be removed or renumbered.
    for (element_id, attribute), groups in before_groups.items():
        current = _groups(actual[element_id].get(attribute))
        for group in groups:
            assert group in current


def test_alignment_changes_only_device_x_and_missing_connection_attributes():
    tree = ET.parse(PROBLEM_FILE)
    before = {element_id: dict(element.attrib) for element_id, element in _by_id(tree).items()}
    repair_tree_connections(tree, PROBLEM_FILE)
    after = _by_id(tree)

    allowed_by_tag = {
        "CBreakerDis": {"x", "node_area"},
        "ZhaiWaiJieDiDaoZha": {"x", "node_area"},
        "Disconnector": {"x", "node_area"},
        "CBreaker": {"x", "node_area"},
        "ConnectLine": {"node_area", "link"},
        "FeedLine": {"node_area", "link"},
        "Bus": {"node_area"},
        "BusDis": {"node_area"},
    }
    for element_id, element in after.items():
        changed = {
            key
            for key in set(before[element_id]) | set(element.attrib)
            if before[element_id].get(key) != element.get(key)
        }
        allowed = allowed_by_tag.get(element.tag, set())
        assert changed <= allowed, (element_id, element.tag, changed - allowed)


def test_manual_reference_and_repaired_file_are_idempotent():
    reference_tree = ET.parse(REFERENCE_FILE)
    reference_result = repair_tree_connections(reference_tree, REFERENCE_FILE)
    assert reference_result.updated_reference_count == 0
    assert reference_result.removed_reference_count == 0

    problem_tree = ET.parse(PROBLEM_FILE)
    repair_tree_connections(problem_tree, PROBLEM_FILE)
    second = repair_tree_connections(problem_tree, PROBLEM_FILE)
    assert second.aligned_device_count == 0
    assert second.adjusted_line_endpoint_count == 0
    assert second.added_reference_count == 0
    assert second.updated_reference_count == 0
    assert second.removed_reference_count == 0
    assert second.changed_element_count == 0


def test_basic_processor_checkbox_executes_conservative_alignment(tmp_path: Path):
    output_dir = tmp_path / "out"
    logs: list[str] = []
    result = process_basic(
        BasicSettings(
            source_path=PROBLEM_FILE,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=output_dir,
            repair_connection_points=True,
        ),
        logs.append,
    )
    assert result.success
    assert result.statistics["aligned_connection_device_count"] == 41
    assert result.statistics["adjusted_connection_line_count"] == 0
    assert result.statistics["updated_connection_reference_count"] == 0
    assert result.statistics["removed_connection_reference_count"] == 0
    assert any("半像素水平对齐设备 41 个" in line for line in logs)

    output_tree = ET.parse(output_dir / PROBLEM_FILE.name)
    output = _by_id(output_tree)
    reference = _by_id(ET.parse(REFERENCE_FILE))
    assert output["117000049"].get("x") == reference["117000049"].get("x")
    original = _by_id(ET.parse(PROBLEM_FILE))
    assert output["34000041"].get("d") == original["34000041"].get("d")


def test_ui_explains_conservative_alignment_but_keeps_checkbox_workflow():
    source = (ROOT / "g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")
    assert 'QCheckBox("修复连接点（补齐 node_area / link）")' in source
    assert "保守增量模式" in source
    assert "不修改任何连接线坐标" in source
    assert "原有连接不会被删除或改号" in source
    assert "不勾选时完全跳过" in source
