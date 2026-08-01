from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.rmu_group_engine import group_rmu_tree, ungroup_rmu_tree


def _layer(tree: ET.ElementTree) -> ET.Element:
    return next(child for child in tree.getroot() if local_name(child.tag) == "Layer")


def test_legacy_header_plus_members_mergesize_is_accepted_by_geometry():
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer>'
        '<Merge id="20000001" mergesize="3" mergex="0" mergey="0" w="100" h="100"/>'
        '<rect id="20000002" x="0" y="0" w="100" h="100"/>'
        '<Text id="8000001" x="10" y="10" w="10" h="10"/>'
        '<Merge id="20000003" mergesize="3" mergex="200" mergey="0" w="100" h="100"/>'
        '<rect id="20000004" x="200" y="0" w="100" h="100"/>'
        '<Text id="8000002" x="210" y="10" w="10" h="10"/>'
        '</Layer></G>'
    ))
    result = ungroup_rmu_tree(tree, Path("adjacent.g"))
    assert result.removed_rmu_merge_count == 2
    assert result.released_member_count == 4
    assert all(local_name(e.tag) != "Merge" for e in _layer(tree))


def test_group_writes_mergesize_as_member_count():
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer>'
        '<rect id="20000002" x="0" y="0" w="100" h="100"/>'
        '<Text id="8000001" x="10" y="10" w="10" h="10"/>'
        '</Layer></G>'
    ))
    result = group_rmu_tree(tree, Path("group.g"))
    assert result.rebuilt_group_count == 1
    merge = next(e for e in _layer(tree) if local_name(e.tag) == "Merge")
    assert merge.get("mergesize") == "2"
