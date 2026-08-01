from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
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
