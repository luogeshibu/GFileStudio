from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.rmu_group_engine import ungroup_rmu_tree

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"


def _layer(tree: ET.ElementTree) -> ET.Element:
    return next(child for child in tree.getroot() if local_name(child.tag) == "Layer")


def _prepend_rmu_merge(tree: ET.ElementTree) -> None:
    layer = _layer(tree)
    merge = ET.Element(
        "Merge",
        {
            "id": "20000004",
            "mergex": "735",
            "mergey": "397",
            "w": "215",
            "h": "164",
            "mergesize": "3",
        },
    )
    layer.insert(0, merge)


def _element_signature(tree: ET.ElementTree) -> list[tuple[str, str]]:
    return [
        (local_name(element.tag), (element.get("id") or "").strip())
        for element in _layer(tree)
    ]


def test_cancel_group_moves_rect_below_devices_using_user_reference_files():
    # rmu-frame-on-top.g 对应用户提供的 aaaaddd：rect 位于两个断路器之后，
    # 在编辑器中会遮盖设备；参考文件要求 rect 位于两个断路器之前。
    tree = ET.parse(DATA / "rmu-frame-on-top.g")
    expected = ET.parse(DATA / "rmu-devices-on-top.g")
    before_coordinates = {
        (local_name(element.tag), element.get("id")): (
            element.get("x"), element.get("y"), element.get("w"), element.get("h")
        )
        for element in _layer(tree)
    }
    _prepend_rmu_merge(tree)

    result = ungroup_rmu_tree(tree, Path("rmu-frame-on-top.g"))

    assert result.removed_rmu_merge_count == 1
    assert result.lowered_rect_count == 1
    assert result.lowered_rect_ids == ["2000003"]
    assert _element_signature(tree) == _element_signature(expected)

    after_coordinates = {
        (local_name(element.tag), element.get("id")): (
            element.get("x"), element.get("y"), element.get("w"), element.get("h")
        )
        for element in _layer(tree)
    }
    assert after_coordinates == before_coordinates


def test_cancel_group_keeps_rect_when_it_is_already_below_devices():
    tree = ET.parse(DATA / "rmu-devices-on-top.g")
    expected = _element_signature(tree)
    _prepend_rmu_merge(tree)

    result = ungroup_rmu_tree(tree, Path("rmu-devices-on-top.g"))

    assert result.removed_rmu_merge_count == 1
    assert result.lowered_rect_count == 0
    assert result.lowered_rect_ids == []
    assert _element_signature(tree) == expected
