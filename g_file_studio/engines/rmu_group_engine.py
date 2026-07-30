from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from g_file_studio.engines.frame_engine import Box, format_number
from g_file_studio.engines.id_engine import (
    collect_reference_tokens,
    generate_unique_id,
    infer_element_id_patterns,
    local_name,
)
from g_file_studio.engines.margin_engine import subtree_box


class RmuGroupingError(RuntimeError):
    """环网柜图元组合错误。"""


@dataclass
class RmuGroupChange:
    rect_id: str
    merge_id: str
    member_count: int
    reused_existing_merge: bool
    rect_box: Box


@dataclass
class RmuGroupingResult:
    file_path: Path
    rect_count: int = 0
    previous_merge_count: int = 0
    removed_invalid_merge_count: int = 0
    rebuilt_group_count: int = 0
    reused_merge_count: int = 0
    created_merge_count: int = 0
    grouped_member_count: int = 0
    changes: list[RmuGroupChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# 当文件内完全没有可复用的 Merge 时使用。属性取自图形编辑器生成的标准 Merge，
# 几何、ID、mergesize 会在创建后重新设置。
_DEFAULT_MERGE_ATTRIBUTES = {
    "p_AssFlag": "128",
    "lw": "1",
    "p_DyColorFlag": "0",
    "ls": "1",
    "onMouseRightDoubleClickAction": "",
    "lc": "0,0,255",
    "ShadowType": "0",
    "onMouseLeftDoubleClickAciton": "",
    "trend_color": "0",
    "af4": "2147483647",
    "onMouseRightOneClickAction": "",
    "p_ShowModeMask": "3",
    "af2": "2147483647",
    "fc": "0,255,0",
    "onMouseHoverEnterAction": "",
    "aliasType": "",
    "LevelStart": "0",
    "af": "2147483647",
    "LevelEnd": "16",
    "p_SelfDefString": "",
    "rain_bow": "0",
    "eventRegister": "",
    "fm": "0",
    "switchapp": "1",
    "opacity": "1",
    "af3": "2147483647",
    "onMouseLeftOneClickAction": "",
    "domain": "",
    "switchappflag": "1",
    "p_EngcodeString": "",
    "onMouseHoverLeaveAction": "",
    "app": "",
    "devref": "",
    "clip": "false",
    "p_FatherObjId": "",
    "isDisplay": "1",
}


def _qualified_tag(reference: ET.Element, name: str) -> str:
    tag = reference.tag
    if isinstance(tag, str) and tag.startswith("{") and "}" in tag:
        namespace = tag.split("}", 1)[0] + "}"
        return namespace + name
    return name


def _area(box: Box) -> float:
    return max(0.0, box.width) * max(0.0, box.height)


def _fully_inside(inner: Box, outer: Box, tolerance: float = 0.5) -> bool:
    """只有整个图元边界都位于 rect 框内，才归入该环网柜。"""
    return (
        inner.left >= outer.left - tolerance
        and inner.top >= outer.top - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def _read_positive_mergesize(element: ET.Element) -> int | None:
    raw = (element.get("mergesize") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _existing_merge_by_rect(
    children: list[ET.Element],
) -> tuple[dict[int, ET.Element], list[ET.Element], list[str]]:
    """读取旧 Merge 与其后连续成员，仅用于复用对应环网柜的 Merge ID/样式。"""
    result: dict[int, ET.Element] = {}
    merges: list[ET.Element] = []
    warnings: list[str] = []

    for index, element in enumerate(children):
        if local_name(element.tag) != "Merge":
            continue
        merges.append(element)
        size = _read_positive_mergesize(element)
        if size is None:
            warnings.append(
                f"旧 Merge ID {element.get('id', '') or '<无ID>'} 的 mergesize 无效，已按新规则重建。"
            )
            continue
        members = children[index + 1 : index + 1 + size]
        if len(members) != size:
            warnings.append(
                f"旧 Merge ID {element.get('id', '') or '<无ID>'} 的成员数量越界，已按新规则重建。"
            )
            continue
        rects = [member for member in members if local_name(member.tag) == "rect"]
        if len(rects) != 1:
            warnings.append(
                f"旧 Merge ID {element.get('id', '') or '<无ID>'} 未唯一包含一个 <rect>，已按新规则重建。"
            )
            continue
        result[id(rects[0])] = element

    return result, merges, warnings


def _allocate_merge_id(
    seed_id: str,
    blocked_ids: set[str],
    merge_pattern,
) -> str:
    seed = seed_id.strip() or "20000000"
    candidate = generate_unique_id(seed, blocked_ids, merge_pattern)
    blocked_ids.add(candidate)
    return candidate


def _make_merge_element(
    rect: ET.Element,
    template: ET.Element | None,
    merge_id: str,
    rect_box: Box,
    member_count: int,
) -> ET.Element:
    if template is not None:
        merge = copy.deepcopy(template)
        # Merge 必须是叶节点；防止异常模板携带子节点。
        for child in list(merge):
            merge.remove(child)
    else:
        merge = ET.Element(
            _qualified_tag(rect, "Merge"),
            dict(_DEFAULT_MERGE_ATTRIBUTES),
        )

    merge.set("id", merge_id)
    merge.set("mergex", format_number(rect_box.left))
    merge.set("mergey", format_number(rect_box.top))
    merge.set("w", format_number(rect_box.width))
    merge.set("h", format_number(rect_box.height))
    merge.set("mergesize", str(member_count))
    merge.set(
        "tfr",
        f"rotate(0) scale({format_number(rect_box.width * 100)},{format_number(rect_box.height * 100)})",
    )
    return merge


def _validate_layer_groups(layer: ET.Element) -> None:
    children = list(layer)
    occupied: set[int] = set()
    rect_membership: dict[int, int] = {}

    for index, element in enumerate(children):
        if local_name(element.tag) != "Merge":
            continue
        size = _read_positive_mergesize(element)
        if size is None:
            raise RmuGroupingError(
                f"Merge ID {element.get('id', '') or '<无ID>'} 的 mergesize 不是正整数。"
            )
        end = index + 1 + size
        if end > len(children):
            raise RmuGroupingError(
                f"Merge ID {element.get('id', '') or '<无ID>'} 的成员范围超出 Layer。"
            )
        member_indexes = set(range(index + 1, end))
        overlap = occupied.intersection(member_indexes)
        if overlap:
            raise RmuGroupingError("不同 Merge 的连续成员区间发生重叠。")
        occupied.update(member_indexes)

        members = children[index + 1 : end]
        rects = [member for member in members if local_name(member.tag) == "rect"]
        if len(rects) != 1:
            raise RmuGroupingError(
                f"Merge ID {element.get('id', '') or '<无ID>'} 必须且只能包含一个 <rect>。"
            )
        rect = rects[0]
        if id(rect) in rect_membership:
            raise RmuGroupingError("同一个 <rect> 被多个 Merge 重复组合。")
        rect_membership[id(rect)] = index

        rect_box = subtree_box(rect)
        if rect_box is None:
            raise RmuGroupingError(
                f"rect ID {rect.get('id', '') or '<无ID>'} 无法读取有效矩形边界。"
            )
        for member in members:
            member_box = subtree_box(member)
            if member_box is None:
                raise RmuGroupingError(
                    f"Merge ID {element.get('id', '') or '<无ID>'} 中的 <{local_name(member.tag)}> 无有效边界。"
                )
            if not _fully_inside(member_box, rect_box):
                raise RmuGroupingError(
                    f"Merge ID {element.get('id', '') or '<无ID>'} 包含 rect 框外图元 "
                    f"<{local_name(member.tag)}> ID {member.get('id', '') or '<无ID>'}。"
                )

    all_rects = [element for element in children if local_name(element.tag) == "rect"]
    if len(rect_membership) != len(all_rects):
        raise RmuGroupingError(
            f"环网柜组合验证失败：rect 共 {len(all_rects)} 个，已组合 {len(rect_membership)} 个。"
        )


def group_rmu_layer(layer: ET.Element, file_path: Path) -> RmuGroupingResult:
    """将每个直属 <rect> 框内的直属图元组合为一个 Merge。

    规则是严格的“完整边界包含”：任何部分超出 rect 的图元都不进入组合。旧 Merge
    会被移除并按此规则重建，因此历史上误包含的框外连接线或状态图标也会被排除。
    """
    original_children = list(layer)
    existing_by_rect, old_merges, warnings = _existing_merge_by_rect(original_children)
    base_children = [
        element for element in original_children if local_name(element.tag) != "Merge"
    ]
    rects = [element for element in base_children if local_name(element.tag) == "rect"]

    result = RmuGroupingResult(
        file_path=file_path,
        rect_count=len(rects),
        previous_merge_count=len(old_merges),
        warnings=warnings,
    )
    if not rects:
        # 没有环网柜时仍清理异常孤立 Merge，避免保留无对应 rect 的组合。
        if old_merges:
            for element in list(layer):
                layer.remove(element)
            for element in base_children:
                layer.append(element)
            result.removed_invalid_merge_count = len(old_merges)
        return result

    original_index = {id(element): index for index, element in enumerate(base_children)}
    rect_boxes: dict[int, Box] = {}
    for rect in rects:
        rect_box = subtree_box(rect)
        if rect_box is None or rect_box.width <= 0 or rect_box.height <= 0:
            raise RmuGroupingError(
                f"文件 {file_path.name} 的 rect ID {rect.get('id', '') or '<无ID>'} "
                "没有有效的 x、y、w、h 边界。"
            )
        rect_boxes[id(rect)] = rect_box

    # 每个图元只允许归属一个 rect。重叠时选择面积最小的包含框；同面积重叠则拒绝猜测。
    owner_by_element: dict[int, ET.Element] = {}
    for element in base_children:
        element_box = subtree_box(element)
        if element_box is None:
            continue

        if local_name(element.tag) == "rect":
            owner_by_element[id(element)] = element
            continue

        candidates = [
            rect
            for rect in rects
            if _fully_inside(element_box, rect_boxes[id(rect)])
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda rect: (_area(rect_boxes[id(rect)]), original_index[id(rect)]))
        if len(candidates) > 1:
            first_area = _area(rect_boxes[id(candidates[0])])
            second_area = _area(rect_boxes[id(candidates[1])])
            if abs(first_area - second_area) <= 1e-6:
                raise RmuGroupingError(
                    f"文件 {file_path.name} 的图元 <{local_name(element.tag)}> "
                    f"ID {element.get('id', '') or '<无ID>'} 同时完整位于两个同尺寸 rect 内，"
                    "无法唯一确定组合归属。"
                )
        owner_by_element[id(element)] = candidates[0]

    members_by_rect: dict[int, list[ET.Element]] = {}
    for rect in rects:
        members = [
            element
            for element in base_children
            if owner_by_element.get(id(element)) is rect
        ]
        members.sort(key=lambda element: original_index[id(element)])
        if rect not in members:
            members.insert(0, rect)
        if not members:
            raise RmuGroupingError(
                f"rect ID {rect.get('id', '') or '<无ID>'} 没有可组合成员。"
            )
        members_by_rect[id(rect)] = members

    # 生成新 Merge ID。已有合法 Merge 对应 rect 时保留其 ID 和样式；新组优先复制旧 Merge 样式。
    all_direct = list(base_children) + list(old_merges)
    patterns = infer_element_id_patterns(all_direct)
    merge_pattern = patterns.get("Merge")
    template_merge = old_merges[0] if old_merges else None
    blocked_ids = {
        value
        for element in all_direct
        if (value := (element.get("id") or "").strip())
    }
    blocked_ids.update(collect_reference_tokens(layer))

    numeric_merge_ids = [
        (element.get("id") or "").strip()
        for element in old_merges
        if (element.get("id") or "").strip().isdigit()
    ]
    merge_seed = max(numeric_merge_ids, key=int) if numeric_merge_ids else ""

    merge_by_rect: dict[int, ET.Element] = {}
    for rect in rects:
        rect_box = rect_boxes[id(rect)]
        members = members_by_rect[id(rect)]
        existing = existing_by_rect.get(id(rect))
        if existing is not None:
            merge_id = (existing.get("id") or "").strip()
            if not merge_id:
                seed = merge_seed or (rect.get("id") or "20000000")
                merge_id = _allocate_merge_id(seed, blocked_ids, merge_pattern)
                merge_seed = merge_id
            merge = _make_merge_element(
                rect,
                existing,
                merge_id,
                rect_box,
                len(members),
            )
            reused = True
            result.reused_merge_count += 1
        else:
            seed = merge_seed or (rect.get("id") or "20000000")
            merge_id = _allocate_merge_id(seed, blocked_ids, merge_pattern)
            merge_seed = merge_id
            merge = _make_merge_element(
                rect,
                template_merge,
                merge_id,
                rect_box,
                len(members),
            )
            reused = False
            result.created_merge_count += 1

        merge_by_rect[id(rect)] = merge
        result.changes.append(
            RmuGroupChange(
                rect_id=(rect.get("id") or "").strip(),
                merge_id=merge_id,
                member_count=len(members),
                reused_existing_merge=reused,
                rect_box=rect_box,
            )
        )
        result.grouped_member_count += len(members)

    # 重建 Layer 顺序：每个 Merge 后只放其 rect 框内成员；框外图元保持原相对顺序。
    first_member_owner: dict[int, ET.Element] = {}
    group_member_ids: set[int] = set()
    for rect in rects:
        members = members_by_rect[id(rect)]
        first_member_owner[id(members[0])] = rect
        group_member_ids.update(id(member) for member in members)

    rebuilt: list[ET.Element] = []
    emitted_members: set[int] = set()
    for element in base_children:
        element_id = id(element)
        if element_id in emitted_members:
            continue
        rect = first_member_owner.get(element_id)
        if rect is not None:
            rebuilt.append(merge_by_rect[id(rect)])
            for member in members_by_rect[id(rect)]:
                rebuilt.append(member)
                emitted_members.add(id(member))
            continue
        if element_id in group_member_ids:
            # 该成员将在其组合第一个成员处统一输出。
            continue
        rebuilt.append(element)

    for element in list(layer):
        layer.remove(element)
    for element in rebuilt:
        layer.append(element)

    result.rebuilt_group_count = len(rects)
    result.removed_invalid_merge_count = max(0, len(old_merges) - result.reused_merge_count)
    _validate_layer_groups(layer)
    return result


def group_rmu_tree(tree: ET.ElementTree, file_path: Path) -> RmuGroupingResult:
    root = tree.getroot()
    layers = [child for child in list(root) if local_name(child.tag) == "Layer"]
    if not layers:
        raise RmuGroupingError(f"文件 {file_path.name} 的 G 根节点下没有直属 Layer。")
    if len(layers) > 1:
        raise RmuGroupingError(
            f"文件 {file_path.name} 包含 {len(layers)} 个直属 Layer；环网柜组合要求只有一个直属 Layer。"
        )
    return group_rmu_layer(layers[0], file_path)
