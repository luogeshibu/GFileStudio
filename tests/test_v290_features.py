from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.color_engine import ColorRule, apply_line_colors
from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.rmu_group_engine import group_rmu_tree, ungroup_rmu_tree
from g_file_studio.models import (
    BasicOutputConflictAction,
    BasicSettings,
    InputMode,
    RmuAction,
)
from g_file_studio.processors.basic_processor import process_basic

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"


def _layer(tree: ET.ElementTree) -> ET.Element:
    return next(child for child in tree.getroot() if local_name(child.tag) == "Layer")


def test_group_and_ungroup_real_rmu_file_are_reversible_in_structure():
    source = DATA / "no-combine.sln.pic.g"
    tree = ET.parse(source)
    grouped = group_rmu_tree(tree, source)
    assert grouped.rebuilt_group_count == 1
    layer = _layer(tree)
    merge = next(element for element in layer if local_name(element.tag) == "Merge")
    assert merge.get("id") == "20000028"
    assert merge.get("mergesize") == "23"

    ungrouped = ungroup_rmu_tree(tree, source)
    assert ungrouped.removed_rmu_merge_count == 1
    assert ungrouped.released_member_count == 23
    assert all(local_name(element.tag) != "Merge" for element in _layer(tree))


def test_ungrouped_real_sample_matches_user_cancel_file():
    source = DATA / "combine.sln.pic.g"
    expected = DATA / "cancel-combine.sln.pic.g"
    tree = ET.parse(source)
    ungroup_rmu_tree(tree, source)
    actual_layer = _layer(tree)
    expected_layer = _layer(ET.parse(expected))
    actual = [(local_name(e.tag), dict(e.attrib)) for e in actual_layer]
    target = [(local_name(e.tag), dict(e.attrib)) for e in expected_layer]
    assert actual == target


def test_ungroup_removes_only_merge_containing_rect():
    source = Path("mixed.g")
    tree = ET.ElementTree(
        ET.fromstring(
            '<G><Layer>'
            '<Merge id="900" mergesize="1"/><Text id="1" x="0" y="0" w="1" h="1"/>'
            '<Merge id="901" mergesize="2"/><rect id="2" x="0" y="0" w="20" h="20"/>'
            '<Text id="3" x="1" y="1" w="2" h="2"/>'
            '</Layer></G>'
        )
    )
    result = ungroup_rmu_tree(tree, source)
    assert result.removed_rmu_merge_count == 1
    assert result.preserved_non_rmu_merge_count == 1
    merges = [e for e in _layer(tree) if local_name(e.tag) == "Merge"]
    assert [e.get("id") for e in merges] == ["900"]


def test_group_preserves_non_rmu_merge():
    source = Path("mixed.g")
    tree = ET.ElementTree(
        ET.fromstring(
            '<G><Layer>'
            '<Merge id="900" mergesize="1"/><Text id="1" x="500" y="500" w="2" h="2"/>'
            '<rect id="2000000" x="0" y="0" w="100" h="100"/>'
            '<Text id="8000001" x="10" y="10" w="10" h="10"/>'
            '</Layer></G>'
        )
    )
    result = group_rmu_tree(tree, source)
    assert result.preserved_non_rmu_merge_count == 1
    merges = [e for e in _layer(tree) if local_name(e.tag) == "Merge"]
    assert len(merges) == 2
    assert any(e.get("id") == "900" for e in merges)


def test_color_engine_changes_only_lc_and_lcc():
    tree = ET.ElementTree(
        ET.fromstring(
            '<G><Layer>'
            '<FeedLine id="1" lc="0,0,255" lcc="#0000ff" fc="0,255,0" lw="3"/>'
            '<ConnectLine id="2" lc="0,0,255" fc="1,2,3" p_DyColorFlag="1"/>'
            '<BusDis id="3" lc="0,0,255"/>'
            '<Bus id="4" lc="0,0,255"/>'
            '<Text id="5" lc="0,0,255"/>'
            '</Layer></G>'
        )
    )
    result = apply_line_colors(
        tree,
        Path("colors.g"),
        [
            ColorRule("FeedLine", "馈线", "#FF0000"),
            ColorRule("ConnectLine", "连接线", "00FF00"),
            ColorRule("BusDis", "配网母线", "#112233"),
            ColorRule("Bus", "主网母线", "#FFFFFF"),
        ],
    )
    assert result.total_changed == 4
    assert result.total_dynamic_color == 1
    elements = {local_name(e.tag): e for e in _layer(tree)}
    assert elements["FeedLine"].get("lc") == "255,0,0"
    assert elements["FeedLine"].get("lcc") == "#FF0000"
    assert elements["FeedLine"].get("fc") == "0,255,0"
    assert elements["FeedLine"].get("lw") == "3"
    assert elements["ConnectLine"].get("lc") == "0,255,0"
    assert elements["Text"].get("lc") == "0,0,255"


def test_basic_processor_timestamp_policy_does_not_overwrite_source(tmp_path: Path):
    source = tmp_path / "same.sln.pic.g"
    original = '<G><Layer><Text id="1" p_NameString="OLD"/></Layer></G>'
    source.write_text(original, encoding="utf-8")
    result = process_basic(
        BasicSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=tmp_path,
            replace_attribute=True,
            replace_target_tag="Text",
            replace_target_attribute="p_NameString",
            replace_old_value="OLD",
            replace_new_value="NEW",
            output_conflict_action=BasicOutputConflictAction.TIMESTAMP,
            task_timestamp="20260730_145300",
        )
    )
    assert result.success
    assert source.read_text(encoding="utf-8") == original
    output = tmp_path / "same-20260730_145300.sln.pic.g"
    assert output in result.output_files
    assert ET.parse(output).getroot().find("Layer/Text").get("p_NameString") == "NEW"


def test_basic_processor_ungroup_and_color_log(tmp_path: Path):
    source = DATA / "combine.sln.pic.g"
    output = tmp_path / "out"
    logs: list[str] = []
    result = process_basic(
        BasicSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=output,
            rmu_action=RmuAction.UNGROUP,
            change_connectline_color=True,
            connectline_color="#FF00FF",
        ),
        log=logs.append,
    )
    assert result.success
    tree = ET.parse(output / source.name)
    assert all(local_name(e.tag) != "Merge" for e in _layer(tree))
    connectors = [e for e in _layer(tree) if local_name(e.tag) == "ConnectLine"]
    assert connectors and all(e.get("lcc") == "#FF00FF" for e in connectors)
    assert any("取消环网柜组合" in line for line in logs)
    assert any("颜色处理" in line for line in logs)
