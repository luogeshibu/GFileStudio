from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.margin_engine import subtree_box
from g_file_studio.engines.rmu_group_engine import group_rmu_tree
from g_file_studio.models import BasicSettings, InputMode
from g_file_studio.processors.basic_processor import process_basic


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "data" / "combine-test-20260730.sln.pic.g"


def _merge_members(layer: ET.Element):
    children = list(layer)
    result = []
    for index, element in enumerate(children):
        if local_name(element.tag) != "Merge":
            continue
        size = int(element.get("mergesize", "0"))
        result.append((element, children[index + 1 : index + 1 + size]))
    return result


def _inside(inner, outer, tolerance=0.5):
    return (
        inner.left >= outer.left - tolerance
        and inner.top >= outer.top - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def test_real_sample_rebuilds_two_rmu_groups_with_only_rect_contents():
    tree = ET.parse(SAMPLE)
    result = group_rmu_tree(tree, SAMPLE)

    assert result.rect_count == 2
    assert result.previous_merge_count == 1
    assert result.rebuilt_group_count == 2
    assert result.created_merge_count == 1
    assert result.reused_merge_count == 1
    assert [change.member_count for change in result.changes] == [23, 23]

    layer = next(child for child in tree.getroot() if local_name(child.tag) == "Layer")
    groups = _merge_members(layer)
    assert len(groups) == 2

    for merge, members in groups:
        rects = [member for member in members if local_name(member.tag) == "rect"]
        assert len(rects) == 1
        rect_box = subtree_box(rects[0])
        assert rect_box is not None
        assert int(merge.get("mergesize")) == len(members) == 23
        assert float(merge.get("mergex")) == rect_box.left
        assert float(merge.get("mergey")) == rect_box.top
        assert float(merge.get("w")) == rect_box.width
        assert float(merge.get("h")) == rect_box.height
        for member in members:
            member_box = subtree_box(member)
            assert member_box is not None
            assert _inside(member_box, rect_box)

    # 两侧伸出柜体的连接线、柜外状态图标和上方 35092 标题都必须留在 Merge 外。
    grouped_ids = {
        member.get("id")
        for _merge, members in groups
        for member in members
    }
    assert "34000048" not in grouped_ids
    assert "34000049" not in grouped_ids
    assert "34000024" not in grouped_ids
    assert "126000002" not in grouped_ids
    assert "126000033" not in grouped_ids
    assert "8000030" not in grouped_ids
    assert "8000061" not in grouped_ids


def test_basic_processor_groups_every_file_in_directory(tmp_path: Path):
    source_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    for name in ("a.sln.pic.g", "b.sln.pic.g"):
        (source_dir / name).write_bytes(SAMPLE.read_bytes())

    logs: list[str] = []
    result = process_basic(
        BasicSettings(
            source_path=source_dir,
            input_mode=InputMode.DIRECTORY,
            output_dir=output_dir,
            group_rmu_elements=True,
        ),
        log=logs.append,
    )

    assert result.success
    assert result.statistics["rmu_rect_count"] == 4
    assert result.statistics["rmu_group_count"] == 4
    assert len(result.output_files) == 2
    assert any("框外图元不组合" in line for line in logs)

    for output in result.output_files:
        layer = ET.parse(output).getroot().find("Layer")
        assert layer is not None
        groups = _merge_members(layer)
        assert len(groups) == 2
        assert [len(members) for _merge, members in groups] == [23, 23]


def test_grouping_uses_full_containment_not_center_point(tmp_path: Path):
    source = tmp_path / "strict.sln.pic.g"
    source.write_text(
        '<G><Layer>'
        '<rect id="2000001" x="100" y="100" w="200" h="200" />'
        '<Text id="8000001" x="120" y="120" w="20" h="20" />'
        '<ConnectLine id="3400001" x="50" y="150" w="100" h="6" />'
        '<Status id="1260001" x="310" y="150" w="20" h="20" />'
        '</Layer></G>',
        encoding="utf-8",
    )
    tree = ET.parse(source)
    result = group_rmu_tree(tree, source)
    assert result.rebuilt_group_count == 1

    layer = tree.getroot().find("Layer")
    assert layer is not None
    merge, members = _merge_members(layer)[0]
    assert int(merge.get("mergesize")) == 2
    assert [local_name(member.tag) for member in members] == ["rect", "Text"]
    assert layer.find("ConnectLine") is not None
    assert layer.find("Status") is not None
