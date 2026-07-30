from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.frame_engine import Box, format_number
from g_file_studio.engines.id_engine import (
    collect_reference_tokens,
    generate_unique_id,
    ElementIdPattern,
    infer_element_id_patterns,
    local_name,
)
from g_file_studio.engines.margin_engine import subtree_box


class RmuGroupingError(RuntimeError):
    """环网柜组合或取消组合错误。"""


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
    previous_rmu_merge_count: int = 0
    preserved_non_rmu_merge_count: int = 0
    removed_invalid_merge_count: int = 0
    rebuilt_group_count: int = 0
    reused_merge_count: int = 0
    created_merge_count: int = 0
    grouped_member_count: int = 0
    changes: list[RmuGroupChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RmuUngroupingResult:
    file_path: Path
    previous_merge_count: int = 0
    removed_rmu_merge_count: int = 0
    preserved_non_rmu_merge_count: int = 0
    released_member_count: int = 0
    removed_merge_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _MergeBlock:
    index: int
    merge: ET.Element
    size: int
    members: tuple[ET.Element, ...]

    @property
    def rects(self) -> tuple[ET.Element, ...]:
        return tuple(member for member in self.members if local_name(member.tag) == "rect")

    @property
    def is_rmu(self) -> bool:
        return bool(self.rects)


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


def _scan_merge_blocks(
    children: list[ET.Element],
    *,
    strict: bool,
) -> tuple[list[_MergeBlock], list[str]]:
    blocks: list[_MergeBlock] = []
    warnings: list[str] = []
    occupied_members: set[int] = set()

    for index, element in enumerate(children):
        if local_name(element.tag) != "Merge":
            continue
        merge_id = element.get("id", "") or "<无ID>"
        size = _read_positive_mergesize(element)
        if size is None:
            message = f"Merge ID {merge_id} 的 mergesize 不是正整数。"
            if strict:
                raise RmuGroupingError(message)
            warnings.append(message + " 已保留不变。")
            continue
        end = index + 1 + size
        if end > len(children):
            message = f"Merge ID {merge_id} 的成员范围超出 Layer。"
            if strict:
                raise RmuGroupingError(message)
            warnings.append(message + " 已保留不变。")
            continue
        member_indexes = set(range(index + 1, end))
        if occupied_members.intersection(member_indexes) or index in occupied_members:
            message = f"Merge ID {merge_id} 与其他 Merge 的连续成员区间重叠。"
            if strict:
                raise RmuGroupingError(message)
            warnings.append(message + " 已保留不变。")
            continue
        occupied_members.update(member_indexes)
        blocks.append(
            _MergeBlock(
                index=index,
                merge=element,
                size=size,
                members=tuple(children[index + 1 : end]),
            )
        )
    return blocks, warnings


def _infer_merge_pattern_and_seed(
    elements: list[ET.Element],
    existing_merges: list[ET.Element],
) -> tuple[ElementIdPattern | None, str]:
    """优先使用现有 Merge 规则；没有样本时从当前文件的 20 前缀对象推断。

    图形编辑器新建 Merge 时通常使用 Rectangle/Merge 的 20 前缀，并沿用当前
    文件图元顺序号。例如样本文件最后一个序号为 27，新 Merge 为 20000028。
    """
    patterns = infer_element_id_patterns(elements + existing_merges)
    merge_pattern = patterns.get("Merge")
    merge_ids = [
        (element.get("id") or "").strip()
        for element in existing_merges
        if (element.get("id") or "").strip().isdigit()
    ]
    if merge_pattern is not None and merge_ids:
        matching = [value for value in merge_ids if merge_pattern.matches(value)]
        return merge_pattern, max(matching or merge_ids, key=int)

    numeric_ids = [
        (element.get("id") or "").strip()
        for element in elements
        if (element.get("id") or "").strip().isdigit()
    ]
    twenty_ids = [value for value in numeric_ids if value.startswith("20")]
    if twenty_ids:
        total_length = max(8, max(len(value) for value in twenty_ids))
        merge_pattern = ElementIdPattern("Merge", "20", total_length)
        matching = [value for value in twenty_ids if merge_pattern.matches(value)]
        if matching:
            return merge_pattern, max(matching, key=int)

        # 当前文件可能还没有标准 20 前缀对象。此时从各元素自身主流规则中
        # 提取已使用的最大顺序号，使新 Merge 与图形编辑器的创建顺序一致。
        element_patterns = infer_element_id_patterns(elements)
        sequences: list[int] = []
        for element in elements:
            value = (element.get("id") or "").strip()
            pattern = element_patterns.get(local_name(element.tag))
            if pattern is not None and pattern.matches(value):
                sequences.append(int(value[len(pattern.prefix) :]))
        if sequences:
            sequence = min(max(sequences), merge_pattern.max_sequence)
            return merge_pattern, merge_pattern.build(sequence)
        return merge_pattern, merge_pattern.build(0)

    return None, "20000000"


def _allocate_merge_id(seed_id: str, blocked_ids: set[str], merge_pattern) -> str:
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
        for child in list(merge):
            merge.remove(child)
    else:
        merge = ET.Element(_qualified_tag(rect, "Merge"), dict(_DEFAULT_MERGE_ATTRIBUTES))

    # 图形编辑器手工组合时，Merge 选择框相对 rect 左、上各外扩 1，
    # 右、下边界与 rect 保持一致。严格复现该几何格式。
    merge_left = rect_box.left - 1
    merge_top = rect_box.top - 1
    merge_width = rect_box.width + 1
    merge_height = rect_box.height + 1

    merge.set("id", merge_id)
    merge.set("mergex", format_number(merge_left))
    merge.set("mergey", format_number(merge_top))
    merge.set("w", format_number(merge_width))
    merge.set("h", format_number(merge_height))
    merge.set("mergesize", str(member_count))
    merge.set(
        "tfr",
        f"rotate(0) scale({format_number(merge_width * 100)},{format_number(merge_height * 100)})",
    )
    return merge


def _validate_layer_groups(layer: ET.Element) -> None:
    children = list(layer)
    blocks, _ = _scan_merge_blocks(children, strict=True)
    rect_membership: dict[int, int] = {}

    for block in blocks:
        rects = block.rects
        if not rects:
            # 其他业务 Merge 不属于环网柜，本功能不修改也不验证其几何。
            continue
        if len(rects) != 1:
            raise RmuGroupingError(
                f"Merge ID {block.merge.get('id', '') or '<无ID>'} 包含 {len(rects)} 个 <rect>，"
                "环网柜 Merge 必须且只能包含一个。"
            )
        rect = rects[0]
        if id(rect) in rect_membership:
            raise RmuGroupingError("同一个 <rect> 被多个 Merge 重复组合。")
        rect_membership[id(rect)] = block.index

        rect_box = subtree_box(rect)
        if rect_box is None:
            raise RmuGroupingError(
                f"rect ID {rect.get('id', '') or '<无ID>'} 无法读取有效矩形边界。"
            )
        for member in block.members:
            member_box = subtree_box(member)
            if member_box is None:
                raise RmuGroupingError(
                    f"Merge ID {block.merge.get('id', '') or '<无ID>'} 中的 "
                    f"<{local_name(member.tag)}> 无有效边界。"
                )
            if not _fully_inside(member_box, rect_box):
                raise RmuGroupingError(
                    f"Merge ID {block.merge.get('id', '') or '<无ID>'} 包含 rect 框外图元 "
                    f"<{local_name(member.tag)}> ID {member.get('id', '') or '<无ID>'}。"
                )

    all_rects = [element for element in children if local_name(element.tag) == "rect"]
    if len(rect_membership) != len(all_rects):
        raise RmuGroupingError(
            f"环网柜组合验证失败：rect 共 {len(all_rects)} 个，已组合 {len(rect_membership)} 个。"
        )


def group_rmu_layer(layer: ET.Element, file_path: Path) -> RmuGroupingResult:
    """将每个直属 <rect> 框内的直属图元组合为一个 Merge。

    只重建成员中含 <rect> 的环网柜 Merge；不含 <rect> 的其他业务 Merge 及其成员保持不变。
    """
    original_children = list(layer)
    blocks, warnings = _scan_merge_blocks(original_children, strict=True)
    rmu_blocks = [block for block in blocks if block.is_rmu]
    non_rmu_blocks = [block for block in blocks if not block.is_rmu]

    existing_by_rect: dict[int, ET.Element] = {}
    for block in rmu_blocks:
        if len(block.rects) == 1:
            existing_by_rect[id(block.rects[0])] = block.merge
        else:
            warnings.append(
                f"旧 Merge ID {block.merge.get('id', '') or '<无ID>'} 包含多个 <rect>，"
                "已拆开并按每个 rect 重新组合。"
            )

    removed_rmu_headers = {id(block.merge) for block in rmu_blocks}
    protected_member_ids = {
        id(member)
        for block in non_rmu_blocks
        for member in block.members
    }
    base_children = [
        element for element in original_children if id(element) not in removed_rmu_headers
    ]
    rects = [element for element in base_children if local_name(element.tag) == "rect"]

    result = RmuGroupingResult(
        file_path=file_path,
        rect_count=len(rects),
        previous_merge_count=len(blocks),
        previous_rmu_merge_count=len(rmu_blocks),
        preserved_non_rmu_merge_count=len(non_rmu_blocks),
        warnings=warnings,
    )
    if not rects:
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

    owner_by_element: dict[int, ET.Element] = {}
    for element in base_children:
        element_id = id(element)
        tag = local_name(element.tag)
        if tag == "Merge" or element_id in protected_member_ids:
            continue
        element_box = subtree_box(element)
        if element_box is None:
            continue
        if tag == "rect":
            owner_by_element[element_id] = element
            continue

        candidates = [
            rect for rect in rects if _fully_inside(element_box, rect_boxes[id(rect)])
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda rect: (_area(rect_boxes[id(rect)]), original_index[id(rect)]))
        if len(candidates) > 1:
            first_area = _area(rect_boxes[id(candidates[0])])
            second_area = _area(rect_boxes[id(candidates[1])])
            if abs(first_area - second_area) <= 1e-6:
                raise RmuGroupingError(
                    f"文件 {file_path.name} 的图元 <{tag}> "
                    f"ID {element.get('id', '') or '<无ID>'} 同时完整位于两个同尺寸 rect 内，"
                    "无法唯一确定组合归属。"
                )
        owner_by_element[element_id] = candidates[0]

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
        members_by_rect[id(rect)] = members

    all_direct = list(base_children) + [block.merge for block in rmu_blocks]
    template_merge = rmu_blocks[0].merge if rmu_blocks else None
    merge_pattern, merge_seed = _infer_merge_pattern_and_seed(
        list(base_children),
        [block.merge for block in rmu_blocks],
    )
    blocked_ids = {
        value
        for element in all_direct
        if (value := (element.get("id") or "").strip())
    }
    blocked_ids.update(collect_reference_tokens(layer))
    merge_by_rect: dict[int, ET.Element] = {}
    for rect in rects:
        rect_box = rect_boxes[id(rect)]
        members = members_by_rect[id(rect)]
        existing = existing_by_rect.get(id(rect))
        if existing is not None:
            merge_id = (existing.get("id") or "").strip()
            if not merge_id:
                merge_id = _allocate_merge_id(
                    merge_seed or (rect.get("id") or "20000000"),
                    blocked_ids,
                    merge_pattern,
                )
                merge_seed = merge_id
            merge = _make_merge_element(rect, existing, merge_id, rect_box, len(members))
            reused = True
            result.reused_merge_count += 1
        else:
            merge_id = _allocate_merge_id(
                merge_seed or (rect.get("id") or "20000000"),
                blocked_ids,
                merge_pattern,
            )
            merge_seed = merge_id
            merge = _make_merge_element(rect, template_merge, merge_id, rect_box, len(members))
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
            continue
        rebuilt.append(element)

    for element in list(layer):
        layer.remove(element)
    for element in rebuilt:
        layer.append(element)

    result.rebuilt_group_count = len(rects)
    result.removed_invalid_merge_count = max(0, len(rmu_blocks) - result.reused_merge_count)
    _validate_layer_groups(layer)
    return result


def ungroup_rmu_layer(layer: ET.Element, file_path: Path) -> RmuUngroupingResult:
    """取消所有环网柜组合，只删除成员中含 <rect> 的 Merge 头元素。"""
    children = list(layer)
    blocks, warnings = _scan_merge_blocks(children, strict=False)
    rmu_blocks = [block for block in blocks if block.is_rmu]
    remove_ids = {id(block.merge) for block in rmu_blocks}

    result = RmuUngroupingResult(
        file_path=file_path,
        previous_merge_count=len([e for e in children if local_name(e.tag) == "Merge"]),
        removed_rmu_merge_count=len(rmu_blocks),
        preserved_non_rmu_merge_count=len([block for block in blocks if not block.is_rmu]),
        released_member_count=sum(block.size for block in rmu_blocks),
        removed_merge_ids=[(block.merge.get("id") or "").strip() for block in rmu_blocks],
        warnings=warnings,
    )

    if remove_ids:
        for element in list(layer):
            layer.remove(element)
        for element in children:
            if id(element) not in remove_ids:
                layer.append(element)

    # 取消后，不应再存在结构有效且成员含 rect 的 Merge。
    remaining, _ = _scan_merge_blocks(list(layer), strict=False)
    if any(block.is_rmu for block in remaining):
        raise RmuGroupingError("取消环网柜组合后仍存在包含 <rect> 的 Merge。")
    return result


def _single_layer(tree: ET.ElementTree, file_path: Path) -> ET.Element:
    root = tree.getroot()
    layers = [child for child in list(root) if local_name(child.tag) == "Layer"]
    if not layers:
        raise RmuGroupingError(f"文件 {file_path.name} 的 G 根节点下没有直属 Layer。")
    if len(layers) > 1:
        raise RmuGroupingError(
            f"文件 {file_path.name} 包含 {len(layers)} 个直属 Layer；"
            "环网柜组合处理要求只有一个直属 Layer。"
        )
    return layers[0]


def group_rmu_tree(tree: ET.ElementTree, file_path: Path) -> RmuGroupingResult:
    return group_rmu_layer(_single_layer(tree, file_path), file_path)


def ungroup_rmu_tree(tree: ET.ElementTree, file_path: Path) -> RmuUngroupingResult:
    return ungroup_rmu_layer(_single_layer(tree, file_path), file_path)
