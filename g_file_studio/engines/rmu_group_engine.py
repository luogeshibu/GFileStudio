from __future__ import annotations

import copy
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.frame_engine import Box, format_number
from g_file_studio.engines.id_engine import (
    ElementIdPattern,
    collect_reference_tokens,
    generate_unique_id,
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
    lowered_rect_count: int = 0
    removed_merge_ids: list[str] = field(default_factory=list)
    lowered_rect_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _MergeBlock:
    index: int
    merge: ET.Element
    declared_size: int | None
    members: tuple[ET.Element, ...]
    rects: tuple[ET.Element, ...]
    size_convention: str

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
    """只有整个图元边界都位于外框内，才视为该外框的成员。"""
    return (
        inner.left >= outer.left - tolerance
        and inner.top >= outer.top - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def _merge_box(element: ET.Element) -> Box | None:
    try:
        left = float(element.get("mergex", ""))
        top = float(element.get("mergey", ""))
        width = float(element.get("w", ""))
        height = float(element.get("h", ""))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return Box(left, top, left + width, top + height)


def _read_positive_mergesize(element: ET.Element) -> int | None:
    raw = (element.get("mergesize") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _is_rmu_relation(rect_box: Box, merge_box: Box) -> bool:
    """判断一个 rect 是否属于该 Merge。

    实际项目文件中 ``mergesize`` 存在两种历史写法：
    1. 只记录成员数量；
    2. 记录 Merge 头 + 成员总数。

    因此不能仅依靠顺序计数识别环网柜，必须以编辑器保存的 Merge 几何范围为主。
    环网柜 Merge 通常只比 220×220 的 rect 外扩少量边距，故同时限制面积比例，
    避免把覆盖整张图的大型业务 Merge 误判成环网柜。
    """
    if not _fully_inside(rect_box, merge_box, tolerance=1.5):
        return False
    rect_area = _area(rect_box)
    merge_area = _area(merge_box)
    if rect_area <= 0 or merge_area <= 0:
        return False
    if merge_area > rect_area * 4.0:
        return False
    return (
        abs(rect_box.center_x - merge_box.center_x) <= max(40.0, rect_box.width * 0.35)
        and abs(rect_box.center_y - merge_box.center_y) <= max(50.0, rect_box.height * 0.40)
    )


def _next_merge_index(children: list[ET.Element], index: int) -> int:
    for cursor in range(index + 1, len(children)):
        if local_name(children[cursor].tag) == "Merge":
            return cursor
    return len(children)


def _resolve_merge_members(
    children: list[ET.Element],
    index: int,
    merge: ET.Element,
) -> tuple[tuple[ET.Element, ...], str, list[str]]:
    """用几何范围解析 Merge 成员，并兼容两种 mergesize 语义。

    用户提供的编辑器样本证明标准新组合使用 ``mergesize=成员数量``；部分历史
    G 文件却保存成 ``mergesize=成员数量+1``。这里不再用固定公式切片，优先取
    Merge 后、下一个 Merge 前、完整位于 Merge 几何范围内的连续成员。
    """
    warnings: list[str] = []
    declared_size = _read_positive_mergesize(merge)
    merge_id = (merge.get("id") or "").strip() or "<无ID>"
    next_index = _next_merge_index(children, index)
    following = [
        element
        for element in children[index + 1 : next_index]
        if local_name(element.tag) != "Merge"
    ]
    merge_box = _merge_box(merge)

    geometry_members: list[ET.Element] = []
    if merge_box is not None:
        for element in following:
            element_box = subtree_box(element)
            if element_box is not None and _fully_inside(element_box, merge_box, tolerance=1.5):
                geometry_members.append(element)

    if geometry_members:
        count = len(geometry_members)
        if declared_size == count:
            convention = "member_count"
        elif declared_size == count + 1:
            convention = "header_plus_members"
        else:
            convention = "geometry"
            if declared_size is not None:
                warnings.append(
                    f"Merge ID {merge_id} 的 mergesize={declared_size} 与几何成员数 {count} "
                    "不一致，已按 Merge 几何范围识别成员。"
                )
        return tuple(geometry_members), convention, warnings

    # 无有效几何时才使用顺序兼容兜底。优先采用编辑器新样本确认的“成员数量”。
    if declared_size is None:
        warnings.append(f"Merge ID {merge_id} 缺少有效 mergesize，无法解析成员。")
        return (), "unknown", warnings

    member_count = min(declared_size, len(following))
    members = following[:member_count]
    convention = "member_count_fallback"
    if not members and declared_size > 1:
        member_count = min(declared_size - 1, len(following))
        members = following[:member_count]
        convention = "header_plus_members_fallback"
    return tuple(members), convention, warnings


def _scan_merge_blocks(
    children: list[ET.Element],
    *,
    strict: bool,
) -> tuple[list[_MergeBlock], list[str]]:
    """扫描所有 Merge，不再因历史文件的区间重叠直接失败。"""
    blocks: list[_MergeBlock] = []
    warnings: list[str] = []
    all_rects = [element for element in children if local_name(element.tag) == "rect"]

    for index, element in enumerate(children):
        if local_name(element.tag) != "Merge":
            continue
        merge_id = (element.get("id") or "").strip() or "<无ID>"
        declared_size = _read_positive_mergesize(element)
        if declared_size is None:
            message = f"Merge ID {merge_id} 的 mergesize 不是正整数。"
            if strict and _merge_box(element) is None:
                raise RmuGroupingError(message)
            warnings.append(message + " 将优先按几何范围识别。")

        members, convention, member_warnings = _resolve_merge_members(children, index, element)
        warnings.extend(member_warnings)
        merge_box = _merge_box(element)
        rects: list[ET.Element] = []
        if merge_box is not None:
            for rect in all_rects:
                rect_box = subtree_box(rect)
                if rect_box is not None and _is_rmu_relation(rect_box, merge_box):
                    rects.append(rect)

        # 老文件的 Merge 几何偶尔缺失。为避免把后方无关 rect 误判为该组合，
        # 只有“第一个连续成员就是 rect”时才采用顺序兜底。
        if not rects and members and local_name(members[0].tag) == "rect":
            rects = [members[0]]

        blocks.append(
            _MergeBlock(
                index=index,
                merge=element,
                declared_size=declared_size,
                members=members,
                rects=tuple(rects),
                size_convention=convention,
            )
        )
    return blocks, warnings


def _infer_merge_pattern_and_seed(
    elements: list[ET.Element],
    existing_merges: list[ET.Element],
) -> tuple[ElementIdPattern | None, str]:
    """优先使用现有 Merge 规则；没有样本时从当前文件的 20 前缀对象推断。"""
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

    # 环网柜手工组合样本：选择框相对 rect 左、上各外扩 1，右、下与 rect 对齐。
    merge_left = rect_box.left - 1
    merge_top = rect_box.top - 1
    merge_width = rect_box.width + 1
    merge_height = rect_box.height + 1

    merge.set("id", merge_id)
    merge.set("mergex", format_number(merge_left))
    merge.set("mergey", format_number(merge_top))
    merge.set("w", format_number(merge_width))
    merge.set("h", format_number(merge_height))
    # 最新编辑器对照样本明确：mergesize 等于成员数量，不包含 Merge 头元素。
    merge.set("mergesize", str(member_count))
    merge.set(
        "tfr",
        f"rotate(0) scale({format_number(merge_width * 100)},{format_number(merge_height * 100)})",
    )
    return merge


def _validate_rebuilt_rmu_groups(layer: ET.Element) -> None:
    """验证本程序重建后的标准环网柜 Merge。"""
    children = list(layer)
    rect_membership: dict[int, str] = {}

    for index, merge in enumerate(children):
        if local_name(merge.tag) != "Merge":
            continue
        merge_box = _merge_box(merge)
        if merge_box is None:
            continue
        rects = []
        for rect in children:
            if local_name(rect.tag) != "rect":
                continue
            rect_box = subtree_box(rect)
            if rect_box is not None and _is_rmu_relation(rect_box, merge_box):
                rects.append(rect)
        if not rects:
            continue
        if len(rects) != 1:
            raise RmuGroupingError(
                f"Merge ID {merge.get('id', '') or '<无ID>'} 对应 {len(rects)} 个 <rect>，"
                "环网柜 Merge 必须且只能对应一个。"
            )

        size = _read_positive_mergesize(merge)
        if size is None:
            raise RmuGroupingError(
                f"Merge ID {merge.get('id', '') or '<无ID>'} 缺少有效 mergesize。"
            )
        end = index + 1 + size
        if end > len(children):
            raise RmuGroupingError(
                f"Merge ID {merge.get('id', '') or '<无ID>'} 的成员范围超出 Layer。"
            )
        members = children[index + 1 : end]
        if any(local_name(member.tag) == "Merge" for member in members):
            raise RmuGroupingError(
                f"Merge ID {merge.get('id', '') or '<无ID>'} 的成员区间包含另一个 Merge。"
            )

        rect = rects[0]
        if rect not in members:
            raise RmuGroupingError(
                f"Merge ID {merge.get('id', '') or '<无ID>'} 的连续成员中不包含对应 rect。"
            )
        rect_key = id(rect)
        if rect_key in rect_membership:
            raise RmuGroupingError("同一个 <rect> 被多个 Merge 重复组合。")
        rect_membership[rect_key] = (merge.get("id") or "").strip()

        rect_box = subtree_box(rect)
        assert rect_box is not None
        for member in members:
            member_box = subtree_box(member)
            if member_box is None:
                raise RmuGroupingError(
                    f"Merge ID {merge.get('id', '') or '<无ID>'} 中的 "
                    f"<{local_name(member.tag)}> 无有效边界。"
                )
            if not _fully_inside(member_box, rect_box):
                raise RmuGroupingError(
                    f"Merge ID {merge.get('id', '') or '<无ID>'} 包含 rect 框外图元 "
                    f"<{local_name(member.tag)}> ID {member.get('id', '') or '<无ID>'}。"
                )

    all_rects = [element for element in children if local_name(element.tag) == "rect"]
    if len(rect_membership) != len(all_rects):
        raise RmuGroupingError(
            f"环网柜组合验证失败：rect 共 {len(all_rects)} 个，已组合 {len(rect_membership)} 个。"
        )


def _best_existing_merge_for_rect(
    rect: ET.Element,
    candidate_blocks: list[_MergeBlock],
) -> ET.Element | None:
    rect_box = subtree_box(rect)
    if rect_box is None:
        return None
    matches: list[tuple[float, int, ET.Element]] = []
    for block in candidate_blocks:
        merge_box = _merge_box(block.merge)
        if merge_box is None or not _is_rmu_relation(rect_box, merge_box):
            continue
        matches.append((_area(merge_box), block.index, block.merge))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches[0][2]


def group_rmu_layer(layer: ET.Element, file_path: Path) -> RmuGroupingResult:
    """将每个直属 <rect> 框内的直属图元组合为一个标准 Merge。

    增强规则：
    - 不再把历史文件的 mergesize 当成唯一事实；
    - 通过 Merge 几何范围识别既有环网柜组合；
    - 兼容 ``成员数量`` 与 ``头+成员`` 两种历史写法；
    - 新写出的 Merge 统一使用编辑器样本确认的 ``成员数量`` 语义。
    """
    original_children = list(layer)
    blocks, warnings = _scan_merge_blocks(original_children, strict=False)
    rmu_blocks = [block for block in blocks if block.is_rmu]
    non_rmu_blocks = [block for block in blocks if not block.is_rmu]

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
    reused_merge_object_ids: set[int] = set()
    for rect in rects:
        rect_box = rect_boxes[id(rect)]
        members = members_by_rect[id(rect)]
        existing = _best_existing_merge_for_rect(rect, rmu_blocks)
        if existing is not None and id(existing) not in reused_merge_object_ids:
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
            reused_merge_object_ids.add(id(existing))
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
    _validate_rebuilt_rmu_groups(layer)
    return result



def _lower_released_rects_below_devices(
    children: list[ET.Element],
    rects: list[ET.Element],
) -> tuple[list[ET.Element], list[str]]:
    """把取消组合后的环网柜 ``rect`` 放到柜内设备的更低图层。

    图形编辑器按 Layer 直属元素的 XML 顺序绘制：越靠后的元素越靠上。
    因此要让外框位于断路器、文字、连接线等设备下方，只需要将 rect 移到
    所有完整位于该 rect 内部的直属图元之前，不改变任何坐标或业务属性。
    """
    working = list(children)
    lowered_ids: list[str] = []

    unique_rects: list[ET.Element] = []
    seen: set[int] = set()
    for rect in rects:
        if id(rect) in seen or rect not in working:
            continue
        seen.add(id(rect))
        unique_rects.append(rect)
    unique_rects.sort(key=lambda rect: working.index(rect))

    for rect in unique_rects:
        rect_box = subtree_box(rect)
        if rect_box is None:
            continue

        contained: list[ET.Element] = []
        for element in working:
            if element is rect or local_name(element.tag) == "Merge":
                continue
            element_box = subtree_box(element)
            if element_box is None:
                continue
            if _fully_inside(element_box, rect_box, tolerance=0.5):
                contained.append(element)

        if not contained:
            continue

        rect_index = working.index(rect)
        first_device_index = min(working.index(element) for element in contained)
        if rect_index <= first_device_index:
            continue

        working.pop(rect_index)
        first_device_index = min(working.index(element) for element in contained)
        working.insert(first_device_index, rect)
        lowered_ids.append((rect.get("id") or "").strip())

    return working, lowered_ids

def ungroup_rmu_layer(layer: ET.Element, file_path: Path) -> RmuUngroupingResult:
    """取消所有环网柜组合，并把环网柜外框放到柜内设备的下层。

    处理只改变 Layer 直属元素的顺序：
    - 删除几何范围对应 ``<rect>`` 的 Merge 头；
    - 将被释放的 rect 移到其框内设备之前，使外框在编辑器中位于设备下方；
    - 坐标、ID、引用、颜色和其他业务属性完全不变。
    """
    children = list(layer)
    blocks, warnings = _scan_merge_blocks(children, strict=False)
    rmu_blocks = [block for block in blocks if block.is_rmu]
    remove_ids = {id(block.merge) for block in rmu_blocks}
    released_member_ids = {id(member) for block in rmu_blocks for member in block.members}
    released_rects = [rect for block in rmu_blocks for rect in block.rects]

    result = RmuUngroupingResult(
        file_path=file_path,
        previous_merge_count=len([e for e in children if local_name(e.tag) == "Merge"]),
        removed_rmu_merge_count=len(rmu_blocks),
        preserved_non_rmu_merge_count=len([block for block in blocks if not block.is_rmu]),
        released_member_count=len(released_member_ids),
        removed_merge_ids=[(block.merge.get("id") or "").strip() for block in rmu_blocks],
        warnings=warnings,
    )

    if remove_ids:
        without_headers = [element for element in children if id(element) not in remove_ids]
        reordered, lowered_rect_ids = _lower_released_rects_below_devices(
            without_headers,
            released_rects,
        )
        result.lowered_rect_ids = lowered_rect_ids
        result.lowered_rect_count = len(lowered_rect_ids)

        for element in list(layer):
            layer.remove(element)
        for element in reordered:
            layer.append(element)

    remaining_merge_object_ids = {
        id(element)
        for element in list(layer)
        if local_name(element.tag) == "Merge"
    }
    if remove_ids & remaining_merge_object_ids:
        raise RmuGroupingError("取消环网柜组合后仍残留待删除的环网柜 Merge。")
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


@dataclass
class RmuEnhancementResult:
    file_path: Path
    smart_rmu_rect_count: int = 0
    smart_frame_color_changed: int = 0
    busdis_rect_count: int = 0
    busdis_column_count: int = 0
    busdis_target_spacing: float | None = None
    busdis_spacing_changed: int = 0
    busdis_moved_element_count: int = 0
    canvas_height_expanded_to: float | None = None
    bus_rect_count: int = 0
    bus_rect_removed: int = 0
    bus_title_moved: int = 0
    bus_merge_removed: int = 0
    warnings: list[str] = field(default_factory=list)


def _hex_to_color_values(color: str) -> tuple[str, str]:
    value = (color or '').strip().upper()
    if not re.fullmatch(r'#[0-9A-F]{6}', value):
        raise RmuGroupingError(f'颜色值 {color!r} 不是有效的 #RRGGBB。')
    rgb = tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    return ','.join(str(component) for component in rgb), value


def _set_static_line_color(element: ET.Element, color: str) -> bool:
    lc, lcc = _hex_to_color_values(color)
    changed = element.get('lc') != lc or (element.get('lcc') or '').upper() != lcc
    element.set('lc', lc)
    element.set('lcc', lcc)
    return changed


def _direct_rects(layer: ET.Element) -> list[ET.Element]:
    return [element for element in list(layer) if local_name(element.tag) == 'rect']


def _elements_inside_rect(layer: ET.Element, rect: ET.Element) -> list[ET.Element]:
    rect_box = subtree_box(rect)
    if rect_box is None:
        return []
    result: list[ET.Element] = []
    for element in list(layer):
        if element is rect or local_name(element.tag) == 'Merge':
            continue
        box = subtree_box(element)
        if box is not None and _fully_inside(box, rect_box, tolerance=0.5):
            result.append(element)
    return result


def _rect_contains_smart_text(layer: ET.Element, rect: ET.Element) -> bool:
    """仅当 rect 内存在可见内容等于 SMART 的直属 Text 时返回 True。"""
    for element in _elements_inside_rect(layer, rect):
        if local_name(element.tag) != 'Text':
            continue
        if (element.get('ts') or '').strip().upper() == 'SMART':
            return True
    return False


def _rmu_rects_by_bus_tag(layer: ET.Element, tag_name: str) -> list[tuple[ET.Element, ET.Element]]:
    matches: list[tuple[ET.Element, ET.Element]] = []
    for rect in _direct_rects(layer):
        candidates = [
            element for element in _elements_inside_rect(layer, rect)
            if local_name(element.tag) == tag_name
        ]
        if candidates:
            candidates.sort(key=lambda element: (
                _area(subtree_box(element)) if subtree_box(element) is not None else 0,
                (element.get('id') or ''),
            ))
            matches.append((rect, candidates[0]))
    return matches


_PATH_COORD_PATTERN = re.compile(r'(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)')
_LINE_LIKE_TAGS = {
    'ConnectLine', 'FeedLine', 'Line', 'FlowLine', 'Bus', 'BusDis',
    'Polyline', 'LWPolyline',
}
_Y_POSITION_ATTRS = ('y', 'y1', 'y2', 'cy', 'mergey')
_X_POSITION_ATTRS = ('x', 'x1', 'x2', 'cx', 'mergex')


@dataclass(frozen=True)
class _BusDisRmuMove:
    rect: ET.Element
    bus: ET.Element
    original_box: Box
    column_index: int
    order_index: int
    target_top: float
    delta_y: float
    upper_boundary: float
    lower_boundary: float


def _translate_number(value: str, delta: float) -> str:
    try:
        return format_number(float(value) + delta)
    except (TypeError, ValueError):
        return value


def _translate_path_y(value: str, delta: float) -> str:
    return _PATH_COORD_PATTERN.sub(
        lambda match: f'{match.group(1)},{_translate_number(match.group(2), delta)}',
        value,
    )


def _translate_element_y(element: ET.Element, delta: float) -> bool:
    """把一个图元作为刚体沿 Y 方向平移；尺寸和全部 X 坐标保持不变。"""
    if abs(delta) <= 1e-9:
        return False
    changed = False
    for node in element.iter():
        for attr in _Y_POSITION_ATTRS:
            if attr in node.attrib:
                old = node.get(attr, '')
                new = _translate_number(old, delta)
                if new != old:
                    node.set(attr, new)
                    changed = True
        if 'd' in node.attrib:
            old = node.get('d', '')
            new = _translate_path_y(old, delta)
            if new != old:
                node.set('d', new)
                changed = True
    return changed


def _horizontal_overlap(a: Box, b: Box) -> float:
    return max(0.0, min(a.right, b.right) - max(a.left, b.left))


def _group_busdis_columns(
    pairs: list[tuple[ET.Element, ET.Element]],
) -> list[list[tuple[ET.Element, ET.Element, Box]]]:
    """把环网柜按 X 方向分成竖直列，防止不同馈线列互相串行排列。"""
    items: list[tuple[ET.Element, ET.Element, Box]] = []
    for rect, bus in pairs:
        box = subtree_box(rect)
        if box is not None:
            items.append((rect, bus, box))
    items.sort(key=lambda item: (item[2].center_x, item[2].top, item[0].get('id') or ''))

    columns: list[list[tuple[ET.Element, ET.Element, Box]]] = []
    for item in items:
        box = item[2]
        best_index: int | None = None
        best_distance = math.inf
        for index, column in enumerate(columns):
            reference_boxes = [entry[2] for entry in column]
            center_x = sum(candidate.center_x for candidate in reference_boxes) / len(reference_boxes)
            typical_width = max(candidate.width for candidate in reference_boxes)
            overlap = max(_horizontal_overlap(box, candidate) for candidate in reference_boxes)
            distance = abs(box.center_x - center_x)
            same_column = overlap > 0 or distance <= max(box.width, typical_width) * 0.60
            if same_column and distance < best_distance:
                best_index = index
                best_distance = distance
        if best_index is None:
            columns.append([item])
        else:
            columns[best_index].append(item)

    for column in columns:
        column.sort(key=lambda item: (item[2].top, item[2].center_x, item[0].get('id') or ''))
    columns.sort(key=lambda column: min(item[2].center_x for item in column))
    return columns


def _build_busdis_moves(
    pairs: list[tuple[ET.Element, ET.Element]],
    spacing: float,
) -> list[_BusDisRmuMove]:
    columns = _group_busdis_columns(pairs)
    moves: list[_BusDisRmuMove] = []
    for column_index, column in enumerate(columns):
        if not column:
            continue
        maximum_height = max(item[2].height for item in column)
        if spacing + 1e-6 < maximum_height:
            raise RmuGroupingError(
                f'相邻环网柜柜顶 Y 间距 {format_number(spacing)} 小于本列最大柜高 '
                f'{format_number(maximum_height)}，会造成环网柜重叠。'
            )
        first_top = column[0][2].top
        centers = [item[2].center_y for item in column]
        for order_index, (rect, bus, box) in enumerate(column):
            target_top = first_top + order_index * spacing
            upper = -math.inf if order_index == 0 else (centers[order_index - 1] + centers[order_index]) / 2.0
            lower = math.inf if order_index == len(column) - 1 else (centers[order_index] + centers[order_index + 1]) / 2.0
            moves.append(
                _BusDisRmuMove(
                    rect=rect,
                    bus=bus,
                    original_box=box,
                    column_index=column_index,
                    order_index=order_index,
                    target_top=target_top,
                    delta_y=target_top - box.top,
                    upper_boundary=upper,
                    lower_boundary=lower,
                )
            )
    return moves


def _move_horizontal_margin(move: _BusDisRmuMove) -> float:
    # 柜外标题、状态图标、H.T/SMR 及短出线都属于柜体周边；扩展范围只用于判定归属。
    return max(450.0, move.original_box.width * 2.0)


def _owner_for_point(x: float, y: float, moves: list[_BusDisRmuMove]) -> _BusDisRmuMove | None:
    candidates: list[tuple[float, _BusDisRmuMove]] = []
    for move in moves:
        box = move.original_box
        margin = _move_horizontal_margin(move)
        if not (box.left - margin <= x <= box.right + margin):
            continue
        if not (move.upper_boundary <= y < move.lower_boundary):
            continue
        score = abs(y - box.center_y) + abs(x - box.center_x) * 0.20
        candidates.append((score, move))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].column_index, item[1].order_index))
    return candidates[0][1]


def _path_points(value: str) -> list[tuple[float, float]]:
    return [(float(match.group(1)), float(match.group(2))) for match in _PATH_COORD_PATTERN.finditer(value or '')]


def _move_line_by_owners(element: ET.Element, moves: list[_BusDisRmuMove]) -> bool:
    """逐点调整连线 Y 坐标，使相邻柜移动后，柜间线段自动伸缩或平移。"""
    path = element.get('d', '')
    old_points = _path_points(path)
    if not old_points:
        box = subtree_box(element)
        if box is None:
            return False
        owner = _owner_for_point(box.center_x, box.center_y, moves)
        return bool(owner and _translate_element_y(element, owner.delta_y))

    changed = False
    transformed: list[tuple[float, float]] = []
    for x, y in old_points:
        owner = _owner_for_point(x, y, moves)
        new_y = y + (owner.delta_y if owner is not None else 0.0)
        transformed.append((x, new_y))
        changed = changed or abs(new_y - y) > 1e-9
    if not changed:
        return False

    iterator = iter(transformed)
    element.set(
        'd',
        _PATH_COORD_PATTERN.sub(
            lambda _match: (
                lambda point: f'{format_number(point[0])},{format_number(point[1])}'
            )(next(iterator)),
            path,
        ),
    )

    old_min_y = min(y for _x, y in old_points)
    old_max_y = max(y for _x, y in old_points)
    new_min_y = min(y for _x, y in transformed)
    new_max_y = max(y for _x, y in transformed)

    # G 编辑器的线图元通常在真实路径外保留 3 像素包围盒；保留原有上下留白。
    try:
        old_y_attr = float(element.get('y', ''))
        old_h_attr = float(element.get('h', ''))
    except (TypeError, ValueError):
        old_y_attr = old_min_y
        old_h_attr = old_max_y - old_min_y
    top_padding = old_min_y - old_y_attr
    bottom_padding = old_y_attr + old_h_attr - old_max_y
    if 'y' in element.attrib:
        element.set('y', format_number(new_min_y - top_padding))
    if 'h' in element.attrib:
        element.set('h', format_number((new_max_y - new_min_y) + top_padding + bottom_padding))

    for y_attr, x_attr, point_index in (('y1', 'x1', 0), ('y2', 'x2', -1)):
        if y_attr not in element.attrib:
            continue
        try:
            x_value = float(element.get(x_attr, transformed[point_index][0]))
            y_value = float(element.get(y_attr, old_points[point_index][1]))
        except (TypeError, ValueError):
            continue
        owner = _owner_for_point(x_value, y_value, moves)
        if owner is not None:
            element.set(y_attr, format_number(y_value + owner.delta_y))
    return True


def _move_merge_for_rect(merge: ET.Element, move: _BusDisRmuMove) -> bool:
    merge_box = _merge_box(merge)
    if merge_box is None or not _is_rmu_relation(move.original_box, merge_box):
        return False
    return _translate_element_y(merge, move.delta_y)


def _normalize_busdis_rmu_spacing(
    layer: ET.Element,
    result: RmuEnhancementResult,
    target_spacing: float | None = None,
) -> None:
    """按柜顶 Y 坐标间距重新排列带 BusDis 的环网柜，不缩放任何柜体。"""
    pairs = _rmu_rects_by_bus_tag(layer, 'BusDis')
    result.busdis_rect_count = len(pairs)
    if target_spacing is None:
        target_spacing = 300.0
    if target_spacing <= 0:
        raise RmuGroupingError('带 BusDis 环网柜的相邻柜顶 Y 间距必须大于 0。')
    spacing = float(target_spacing)
    result.busdis_target_spacing = spacing
    if len(pairs) <= 1:
        result.busdis_column_count = len(pairs)
        return

    moves = _build_busdis_moves(pairs, spacing)
    result.busdis_column_count = len({move.column_index for move in moves})
    moving = [move for move in moves if abs(move.delta_y) > 1e-9]
    result.busdis_spacing_changed = len(moving)
    if not moving:
        return

    forced_owner: dict[int, _BusDisRmuMove] = {}
    for move in moves:
        forced_owner[id(move.rect)] = move
        for member in _elements_inside_rect(layer, move.rect):
            forced_owner[id(member)] = move

    moved_elements: set[int] = set()
    busdis_rect_ids = {id(move.rect) for move in moves}
    for element in list(layer):
        tag = local_name(element.tag)
        if tag == 'rect' and id(element) not in busdis_rect_ids:
            continue

        forced = forced_owner.get(id(element))
        if forced is not None:
            if _translate_element_y(element, forced.delta_y):
                moved_elements.add(id(element))
            continue

        if tag == 'Merge':
            for move in moves:
                if _move_merge_for_rect(element, move):
                    moved_elements.add(id(element))
                    break
            continue

        if tag in _LINE_LIKE_TAGS:
            if _move_line_by_owners(element, moves):
                moved_elements.add(id(element))
            continue

        box = subtree_box(element)
        if box is None:
            continue
        owner = _owner_for_point(box.center_x, box.center_y, moves)
        if owner is not None and _translate_element_y(element, owner.delta_y):
            moved_elements.add(id(element))

    result.busdis_moved_element_count = len(moved_elements)

    # 强制复核：最上方柜保持不动，后续柜顶 Y 坐标差必须等于用户给定值。
    for column in _group_busdis_columns(pairs):
        final_boxes = [subtree_box(rect) for rect, _bus, _old_box in column]
        if any(box is None for box in final_boxes):
            raise RmuGroupingError('BusDis 环网柜移动后无法重新计算外框范围。')
        resolved = [box for box in final_boxes if box is not None]
        resolved.sort(key=lambda box: box.top)
        for previous, current in zip(resolved, resolved[1:]):
            actual = current.top - previous.top
            if abs(actual - spacing) > 1e-6:
                raise RmuGroupingError(
                    f'BusDis 环网柜垂直间距验证失败：实际 {format_number(actual)}，'
                    f'目标 {format_number(spacing)}。'
                )

def _candidate_title_texts(layer: ET.Element, bus: ET.Element, rect: ET.Element) -> list[tuple[float, ET.Element]]:
    bus_box = subtree_box(bus)
    rect_box = subtree_box(rect)
    if bus_box is None or rect_box is None:
        return []
    candidates: list[tuple[float, ET.Element]] = []
    for element in list(layer):
        if local_name(element.tag) != 'Text':
            continue
        text = (element.get('ts') or '').strip()
        if not text or text.upper() in {'SMART', 'Y1', 'Y2', 'Y3', 'Q1', 'Q2'}:
            continue
        box = subtree_box(element)
        if box is None:
            continue
        dx = box.center_x - bus_box.center_x
        dy = box.center_y - bus_box.center_y
        distance = math.hypot(dx, dy)
        # 标题通常字号大、宽度较大，并位于母线上方。给这些条件更高优先级。
        font_size = 0.0
        try:
            font_size = float(element.get('fs', '0') or 0)
        except ValueError:
            pass
        penalty = 0.0
        if box.bottom > bus_box.top:
            penalty += 350.0
        if font_size < 28 and box.width < 60:
            penalty += 250.0
        if not (
            rect_box.left - rect_box.width * 1.5 <= box.center_x <= rect_box.right + rect_box.width * 1.5
            and rect_box.top - rect_box.height * 1.5 <= box.center_y <= rect_box.bottom + rect_box.height * 1.5
        ):
            penalty += 400.0
        candidates.append((distance + penalty, element))
    candidates.sort(key=lambda item: item[0])
    return candidates


def _move_text_above_bus(text: ET.Element, bus: ET.Element, gap: float = 18.0) -> bool:
    text_box = subtree_box(text)
    bus_box = subtree_box(bus)
    if text_box is None or bus_box is None:
        return False
    new_x = bus_box.center_x - text_box.width / 2.0
    new_y = bus_box.top - text_box.height - gap
    old_x = text.get('x')
    old_y = text.get('y')
    text.set('x', format_number(new_x))
    text.set('y', format_number(new_y))
    return text.get('x') != old_x or text.get('y') != old_y


def _remove_merges_for_rects(layer: ET.Element, rects: list[ET.Element]) -> int:
    children = list(layer)
    blocks, _warnings = _scan_merge_blocks(children, strict=False)
    rect_ids = {id(rect) for rect in rects}
    headers = {
        id(block.merge)
        for block in blocks
        if any(id(rect) in rect_ids for rect in block.rects)
    }
    if not headers:
        return 0
    for element in list(layer):
        if id(element) in headers:
            layer.remove(element)
    return len(headers)


def enhance_rmu_layer(
    layer: ET.Element,
    file_path: Path,
    *,
    change_smart_frame_color: bool = False,
    smart_frame_color: str = '#00A651',
    normalize_busdis_spacing: bool = False,
    busdis_vertical_spacing: float | None = None,
    # 兼容旧调用参数；语义已升级为“垂直间距”，不再缩放柜高。
    normalize_busdis_height: bool = False,
    busdis_target_height: float | None = None,
    remove_bus_frame_and_reposition_title: bool = False,
) -> RmuEnhancementResult:
    """执行环网柜视觉和布局增强。

    SMART 着色只修改“框内存在 SMART Text”的 rect 外框，绝不修改 SMART
    字体本身；BusDis 环网柜按用户给定的柜顶 Y 间距整体平移，柜体尺寸和
    所有 X 坐标保持不变；带 Bus 的环网柜删除外框并把最近的业务标题放到母线上方。
    """
    result = RmuEnhancementResult(file_path=file_path)
    rects = _direct_rects(layer)

    if change_smart_frame_color:
        for rect in rects:
            if not _rect_contains_smart_text(layer, rect):
                continue
            result.smart_rmu_rect_count += 1
            if _set_static_line_color(rect, smart_frame_color):
                result.smart_frame_color_changed += 1

    if normalize_busdis_spacing or normalize_busdis_height:
        spacing = (
            busdis_vertical_spacing
            if normalize_busdis_spacing
            else busdis_target_height
        )
        _normalize_busdis_rmu_spacing(layer, result, spacing)

    if remove_bus_frame_and_reposition_title:
        bus_pairs = _rmu_rects_by_bus_tag(layer, 'Bus')
        result.bus_rect_count = len(bus_pairs)
        bus_rects = [rect for rect, _bus in bus_pairs]
        result.bus_merge_removed = _remove_merges_for_rects(layer, bus_rects)
        for rect, bus in bus_pairs:
            candidates = _candidate_title_texts(layer, bus, rect)
            if candidates:
                if _move_text_above_bus(candidates[0][1], bus):
                    result.bus_title_moved += 1
            else:
                result.warnings.append(
                    f"带 Bus 的 rect ID {(rect.get('id') or '<无ID>')} 未找到合适的标题 Text。"
                )
            if rect in list(layer):
                layer.remove(rect)
                result.bus_rect_removed += 1

    return result


def _layer_content_bottom(layer: ET.Element) -> float:
    bottoms = [
        box.bottom
        for element in list(layer)
        if (box := subtree_box(element)) is not None
    ]
    return max(bottoms, default=0.0)


def _root_canvas_height(root: ET.Element) -> float:
    values: list[float] = []
    for attr in ('h', 'height'):
        try:
            values.append(float(root.get(attr, '')))
        except (TypeError, ValueError):
            pass
    return max(values, default=0.0)


def enhance_rmu_tree(
    tree: ET.ElementTree,
    file_path: Path,
    **kwargs,
) -> RmuEnhancementResult:
    root = tree.getroot()
    layer = _single_layer(tree, file_path)
    spacing_enabled = bool(
        kwargs.get('normalize_busdis_spacing') or kwargs.get('normalize_busdis_height')
    )
    original_content_bottom = _layer_content_bottom(layer)
    original_canvas_height = _root_canvas_height(root)
    original_bottom_margin = max(0.0, original_canvas_height - original_content_bottom)

    result = enhance_rmu_layer(layer, file_path, **kwargs)

    # 用户增大间距时，必要时只扩展画布高度，避免下方图元被裁剪；不主动缩小画布。
    if spacing_enabled and original_canvas_height > 0:
        new_content_bottom = _layer_content_bottom(layer)
        required_height = math.ceil(new_content_bottom + original_bottom_margin)
        if required_height > original_canvas_height + 1e-6:
            root.set('h', format_number(required_height))
            root.set('height', format_number(required_height))
            result.canvas_height_expanded_to = float(required_height)
    return result
