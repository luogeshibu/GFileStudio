from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.frame_engine import Box
from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.margin_engine import subtree_box
from g_file_studio.engines.rmu_group_engine import group_rmu_tree, ungroup_rmu_tree

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"


def _layer(tree: ET.ElementTree) -> ET.Element:
    return next(child for child in tree.getroot() if local_name(child.tag) == "Layer")


def test_editor_generic_merge_sample_uses_member_count_and_union_geometry():
    tree = ET.parse(DATA / "generic-combine-test.sln.pic.g")
    children = list(_layer(tree))
    assert [local_name(element.tag) for element in children] == ["Merge", "CBreaker", "CBreaker"]
    merge = children[0]
    assert merge.get("mergesize") == "2"

    member_boxes = [subtree_box(element) for element in children[1:]]
    assert all(box is not None for box in member_boxes)
    left = min(box.left for box in member_boxes if box is not None)
    top = min(box.top for box in member_boxes if box is not None)
    right = max(box.right for box in member_boxes if box is not None)
    bottom = max(box.bottom for box in member_boxes if box is not None)
    assert (float(merge.get("mergex")), float(merge.get("mergey"))) == (left, top)
    assert (float(merge.get("w")), float(merge.get("h"))) == (right - left, bottom - top)


def test_large_real_file_with_mixed_mergesize_conventions_can_ungroup_and_regroup():
    source = DATA / "JED-CTL-AJWD-22.sln.pic.g"
    tree = ET.parse(source)
    original_layer = _layer(tree)
    original_rects = [element for element in original_layer if local_name(element.tag) == "rect"]
    original_merges = [element for element in original_layer if local_name(element.tag) == "Merge"]
    assert len(original_rects) == 15
    assert len(original_merges) == 14

    ungrouped = ungroup_rmu_tree(tree, source)
    assert ungrouped.removed_rmu_merge_count == 14
    assert all(local_name(element.tag) != "Merge" for element in _layer(tree))

    grouped = group_rmu_tree(tree, source)
    assert grouped.rect_count == 15
    assert grouped.rebuilt_group_count == 15
    layer = _layer(tree)
    merges = [element for element in layer if local_name(element.tag) == "Merge"]
    assert len(merges) == 15

    children = list(layer)
    for index, merge in enumerate(children):
        if local_name(merge.tag) != "Merge":
            continue
        count = int(merge.get("mergesize", "0"))
        members = children[index + 1 : index + 1 + count]
        assert len(members) == count
        rects = [member for member in members if local_name(member.tag) == "rect"]
        assert len(rects) == 1
        rect_box = subtree_box(rects[0])
        assert rect_box is not None
        for member in members:
            member_box = subtree_box(member)
            assert member_box is not None
            assert member_box.left >= rect_box.left - 0.5
            assert member_box.top >= rect_box.top - 0.5
            assert member_box.right <= rect_box.right + 0.5
            assert member_box.bottom <= rect_box.bottom + 0.5


def test_mergesize_mismatch_does_not_cause_overlap_failure_when_geometry_is_valid():
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer>'
        '<Merge id="20000001" mergesize="99" mergex="0" mergey="0" w="101" h="101"/>'
        '<rect id="20000002" x="1" y="1" w="100" h="100"/>'
        '<Text id="8000001" x="10" y="10" w="10" h="10"/>'
        '<Merge id="20000003" mergesize="1" mergex="200" mergey="0" w="101" h="101"/>'
        '<rect id="20000004" x="201" y="1" w="100" h="100"/>'
        '<Text id="8000002" x="210" y="10" w="10" h="10"/>'
        '</Layer></G>'
    ))
    result = ungroup_rmu_tree(tree, Path("mixed-size.g"))
    assert result.removed_rmu_merge_count == 2
    assert all(local_name(element.tag) != "Merge" for element in _layer(tree))
