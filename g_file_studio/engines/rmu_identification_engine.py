from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.id_engine import direct_layer_elements, local_name


@dataclass(frozen=True)
class _Box:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class RmuIdentification:
    rect_id: str
    name: str
    name_position: str
    rmu_type: str
    l_count: int
    t_count: int
    smart_count: int
    confidence: str
    rect_x: float
    rect_y: float
    rect_w: float
    rect_h: float
    smart_source: str = ""
    type_source: str = ""
    text_yq_type: str = ""
    devref_type: str = ""
    type_cross_check: str = "N/A"
    type_validation_status: str = "WARN"
    type_cross_note: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class RmuIdentificationResult:
    file_path: Path
    cabinet_count: int = 0
    named_count: int = 0
    typed_count: int = 0
    ambiguous_name_count: int = 0
    items: list[RmuIdentification] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_Y_LABEL_RE = re.compile(r"^Y\s*(\d+)$", re.I)
_Q_LABEL_RE = re.compile(r"^Q\s*(\d+)$", re.I)


def _float(element: ET.Element, name: str, default: float = 0.0) -> float:
    try:
        return float(element.get(name, default))
    except (TypeError, ValueError):
        return default


def _box(element: ET.Element) -> _Box | None:
    width = _float(element, "w")
    height = _float(element, "h")
    if width <= 0 or height <= 0:
        return None
    left = _float(element, "x")
    top = _float(element, "y")
    return _Box(left, top, left + width, top + height)


def _point_to_box_distance(x: float, y: float, box: _Box) -> float:
    dx = max(box.left - x, 0.0, x - box.right)
    dy = max(box.top - y, 0.0, y - box.bottom)
    return (dx * dx + dy * dy) ** 0.5


def _center_inside(element: ET.Element, outer: _Box, tolerance: float = 0.5) -> bool:
    box = _box(element)
    if box is None:
        return False
    return (
        outer.left - tolerance <= box.center_x <= outer.right + tolerance
        and outer.top - tolerance <= box.center_y <= outer.bottom + tolerance
    )


def _classify_switch_by_devref(element: ET.Element) -> str | None:
    """仅按图元文件名/devref 识别 L/T，用于与柜内 Y/Q 文字交叉校验。"""
    if local_name(element.tag) != "CBreakerDis":
        return None
    devref = re.sub(r"[^A-Z0-9]+", "_", (element.get("devref") or "").upper())
    if any(token in devref for token in ("LOAD_BREAKER", "LOADBREAKERSWITCH", "RMU_LBS")):
        return "L"
    if any(token in devref for token in ("CIRCUIT_BREAKER", "CIRCUITBREAKER", "RMU_BRK")):
        return "T"
    return None


def _classify_switch(element: ET.Element) -> str | None:
    """兼容旧调用：devref 优先；仅在 devref 无法判断时用 Y/Q 名称回退。"""
    kind = _classify_switch_by_devref(element)
    if kind is not None:
        return kind
    name = (element.get("p_NameString") or "").strip().upper()
    if re.fullmatch(r"Y\d+", name):
        return "L"
    if re.fullmatch(r"Q\d+", name):
        return "T"
    return None


def _is_smart_device(element: ET.Element) -> bool:
    devref = (element.get("devref") or "").upper()
    if "NON-SMART" in devref or "NO-SMART" in devref:
        return False
    return "SMART" in devref or "RMU_LBS_S" in devref or "RMU_BRK_S" in devref


def _is_green_name_text(element: ET.Element) -> bool:
    """判断 Text 是否为绿色。绿色仅用于多候选柜名消歧，不再作为硬条件。"""
    lcc = (element.get("lcc") or "").strip().lower()
    lc = re.sub(r"\s+", "", (element.get("lc") or "").strip())
    return lcc == "#00ff00" or lc == "0,255,0"


def _normalize_excluded_name(value: str) -> str:
    """Normalize one user-specified RMU-name exclusion for exact matching."""
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def parse_name_exclusions(raw: str) -> tuple[str, ...]:
    """Parse comma/semicolon/newline separated exact RMU-name exclusions.

    Matching is whole-string, case-insensitive, and ignores surrounding/repeated
    whitespace.  It deliberately does NOT use substring matching, so excluding
    ``SFI`` will not exclude a legitimate name such as ``SFI-1201``.
    """
    values = re.split(r"[,;，；\n\r]+", raw or "")
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", value.strip())
        key = _normalize_excluded_name(cleaned)
        if cleaned and key and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return tuple(unique)


def _valid_name_text(element: ET.Element, excluded_names: frozenset[str] = frozenset()) -> bool:
    """柜名候选的基础过滤。

    名称颜色不是硬条件。这里仅排除明确属于柜内设备/状态的短标签，
    其余数字、字母数字、带连字符的名称均允许参与距离匹配。
    用户配置的排除项只做完整字符串匹配，不做包含/模糊匹配。
    """
    value = (element.get("ts") or "").strip()
    if not value or not any(ch.isalnum() for ch in value):
        return False
    if _normalize_excluded_name(value) in excluded_names:
        return False
    compact = re.sub(r"\s+", "", value).upper()
    if _Y_LABEL_RE.fullmatch(compact) or _Q_LABEL_RE.fullmatch(compact):
        return False
    if compact in {"SMART", "SMR", "G", "I"}:
        return False
    return True


def _candidate_for_position(text: ET.Element, rect: _Box, position: str) -> tuple[float, float] | None:
    """Return (edge gap, perpendicular-axis offset) for one selected direction.

    The direction is a hard user constraint.  This deliberately mirrors the
    proven DMM RMU label geometry: 120 G-units maximum edge distance and 20
    G-units projection tolerance.  A Text may overlap the frame edge by up to
    20 units, but its center must still be on the requested side.
    """
    box = _box(text)
    if box is None:
        return None

    max_distance = 120.0
    edge_tolerance = 20.0

    if position == "top":
        gap = rect.top - box.bottom
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_y < rect.top
            and rect.left - edge_tolerance <= box.center_x <= rect.right + edge_tolerance
        ):
            return max(0.0, gap), abs(box.center_x - rect.center_x)
    elif position == "bottom":
        gap = box.top - rect.bottom
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_y > rect.bottom
            and rect.left - edge_tolerance <= box.center_x <= rect.right + edge_tolerance
        ):
            return max(0.0, gap), abs(box.center_x - rect.center_x)
    elif position == "left":
        gap = rect.left - box.right
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_x < rect.left
            and rect.top - edge_tolerance <= box.center_y <= rect.bottom + edge_tolerance
        ):
            return max(0.0, gap), abs(box.center_y - rect.center_y)
    elif position == "right":
        gap = box.left - rect.right
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_x > rect.right
            and rect.top - edge_tolerance <= box.center_y <= rect.bottom + edge_tolerance
        ):
            return max(0.0, gap), abs(box.center_y - rect.center_y)
    return None


def _candidate_score(
    item: tuple[float, float, str, str, str, bool],
    positions: tuple[str, ...],
) -> float:
    gap, axis_offset, position, _value, _text_id, _green = item
    # DMM-style geometry: edge distance dominates; axis offset only nudges the
    # choice.  Direction order is only a deterministic exact-tie breaker.
    return gap + axis_offset * 0.08 + positions.index(position) * 0.0001


def _all_candidates_for_rect(
    texts: list[ET.Element],
    rect: _Box,
    positions: tuple[str, ...],
    excluded_names: frozenset[str] = frozenset(),
) -> list[tuple[float, float, str, str, str, bool]]:
    """Collect candidates only from explicitly selected directions.

    The same Text can geometrically touch two selected directions near a corner;
    keep only its best direction for this cabinet so it still counts as ONE
    candidate name.
    """
    best_by_text: dict[str, tuple[float, float, str, str, str, bool]] = {}
    for index, text in enumerate(texts):
        if not _valid_name_text(text, excluded_names):
            continue
        value = (text.get("ts") or "").strip()
        text_id = (text.get("id") or "").strip()
        text_key = text_id or f"__text_{index}"
        green = _is_green_name_text(text)
        for position in positions:
            metric = _candidate_for_position(text, rect, position)
            if metric is None:
                continue
            item = (metric[0], metric[1], position, value, text_key, green)
            current = best_by_text.get(text_key)
            if current is None or _candidate_score(item, positions) < _candidate_score(current, positions):
                best_by_text[text_key] = item
    return list(best_by_text.values())


def _name_candidates_for_rect(
    texts: list[ET.Element],
    rect: _Box,
    positions: tuple[str, ...],
    excluded_names: frozenset[str] = frozenset(),
) -> list[tuple[float, float, str, str, str, bool]]:
    """Compatibility helper: candidates from selected directions only."""
    return _all_candidates_for_rect(texts, rect, positions, excluded_names)


def _assign_names_globally(
    texts: list[ET.Element],
    cabinets: list[tuple[str, _Box]],
    positions: tuple[str, ...],
    excluded_names: frozenset[str] = frozenset(),
) -> dict[str, tuple[str, str, str, list[str]]]:
    """Assign RMU names with strict direction and one-owner rules.

    This follows the reference Distribution Model Manager behaviour supplied by
    the user:
      1. inspect ONLY user-selected directions;
      2. one Text belongs to the nearest eligible RMU cabinet for that direction;
      3. if an RMU owns exactly one candidate, use it regardless of color;
      4. if it owns multiple candidates, choose the nearest GREEN candidate when
         any green candidate exists; otherwise choose the nearest candidate.
    No unselected direction and no metadata fallback participates.
    """
    rect_map = dict(cabinets)
    per_rect_raw: dict[str, list[tuple[float, float, str, str, str, bool]]] = {
        rect_id: _all_candidates_for_rect(texts, rect, positions, excluded_names)
        for rect_id, rect in cabinets
    }

    # Resolve one owner for every Text.  A candidate label cannot be reused by a
    # neighbouring cabinet.  Ownership is purely geometric; color never changes
    # ownership and is used only after ownership when an RMU has multiple names.
    owners: dict[str, tuple[str, float, tuple[float, float, str, str, str, bool]]] = {}
    for rect_id, items in per_rect_raw.items():
        for item in items:
            text_key = item[4]
            score = _candidate_score(item, positions)
            current = owners.get(text_key)
            if current is None or (score, rect_id) < (current[1], current[0]):
                owners[text_key] = (rect_id, score, item)

    owned_by_rect: dict[str, list[tuple[float, float, str, str, str, bool]]] = {
        rect_id: [] for rect_id, _rect in cabinets
    }
    for rect_id, _score, item in owners.values():
        owned_by_rect.setdefault(rect_id, []).append(item)

    result: dict[str, tuple[str, str, str, list[str]]] = {}
    for rect_id, _rect in cabinets:
        candidates = owned_by_rect.get(rect_id, [])
        candidates.sort(key=lambda item: (_candidate_score(item, positions), item[3], item[4]))
        if not candidates:
            result[rect_id] = ("", "", "未识别", [])
            continue

        warnings: list[str] = []
        if len(candidates) == 1:
            chosen = candidates[0]
            confidence = "高"
        else:
            greens = [item for item in candidates if item[5]]
            if greens:
                chosen = min(greens, key=lambda item: (_candidate_score(item, positions), item[3], item[4]))
                warnings.append("指定方向内存在多个柜名候选，按绿色优先选择")
            else:
                chosen = candidates[0]
                warnings.append("指定方向内存在多个柜名候选且无绿色名称，按最近位置选择")
            confidence = "中"

        _gap, _axis_offset, position, value, _text_key, _green = chosen
        result[rect_id] = (value, position, confidence, warnings)

    return result


def _find_name(
    texts: list[ET.Element],
    rect: _Box,
    positions: tuple[str, ...],
    excluded_names: frozenset[str] = frozenset(),
) -> tuple[str, str, str, list[str]]:
    """Compatibility wrapper used by focused unit tests/single-cabinet callers."""
    matches = _assign_names_globally(texts, [("__single__", rect)], positions, excluded_names)
    return matches["__single__"]


def _bus_key_name_candidate(inside_buses: list[ET.Element], excluded_names: frozenset[str] = frozenset()) -> str:
    """Extract an RMU cabinet name encoded by BusDis.key_name, e.g. 30864_BUS.

    This is a metadata fallback only.  It does not inspect any unselected text
    direction, so the user's direction restriction remains a hard constraint for
    geometric Text matching.
    """
    candidates: list[str] = []
    for bus in inside_buses:
        key_name = (bus.get("key_name") or "").strip()
        if not key_name:
            continue
        match = re.fullmatch(r"(.+?)_BUS", key_name, re.I)
        if not match:
            continue
        value = match.group(1).strip()
        if value and value.upper() != "BUS" and _normalize_excluded_name(value) not in excluded_names:
            candidates.append(value)
    unique = []
    seen = set()
    for value in candidates:
        key = value.upper()
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique[0] if len(unique) == 1 else ""


def _metadata_name_confirmed_by_text(
    texts: list[ET.Element],
    rect: _Box,
    positions: tuple[str, ...],
    candidate: str,
    excluded_names: frozenset[str] = frozenset(),
) -> bool:
    """Confirm a BusDis.key_name fallback using nearby Text with the exact same value.

    This is intentionally more tolerant than normal name geometry only because
    the metadata value already supplies an exact candidate.  It handles tall
    Text bounding boxes such as ``38995`` whose box overlaps the RMU frame by
    more than the normal 20-unit tolerance, while still respecting the user's
    selected directions and refusing metadata-only guesses.
    """
    key = _normalize_excluded_name(candidate)
    if not key or key in excluded_names:
        return False

    max_distance = 160.0
    edge_tolerance = 80.0
    for text in texts:
        value = (text.get("ts") or "").strip()
        if _normalize_excluded_name(value) != key:
            continue
        box = _box(text)
        if box is None:
            continue
        for position in positions:
            if position == "top":
                gap = rect.top - box.bottom
                if (-edge_tolerance <= gap <= max_distance and box.center_y < rect.top
                        and rect.left - edge_tolerance <= box.center_x <= rect.right + edge_tolerance):
                    return True
            elif position == "bottom":
                gap = box.top - rect.bottom
                if (-edge_tolerance <= gap <= max_distance and box.center_y > rect.bottom
                        and rect.left - edge_tolerance <= box.center_x <= rect.right + edge_tolerance):
                    return True
            elif position == "left":
                gap = rect.left - box.right
                if (-edge_tolerance <= gap <= max_distance and box.center_x < rect.left
                        and rect.top - edge_tolerance <= box.center_y <= rect.bottom + edge_tolerance):
                    return True
            elif position == "right":
                gap = box.left - rect.right
                if (-edge_tolerance <= gap <= max_distance and box.center_x > rect.right
                        and rect.top - edge_tolerance <= box.center_y <= rect.bottom + edge_tolerance):
                    return True
    return False


def _label_counts(inside_texts: list[ET.Element]) -> tuple[int, int, set[str], set[str]]:
    y_labels: set[str] = set()
    q_labels: set[str] = set()
    for item in inside_texts:
        value = (item.get("ts") or "").strip().upper().replace(" ", "")
        if _Y_LABEL_RE.fullmatch(value):
            y_labels.add(value)
        elif _Q_LABEL_RE.fullmatch(value):
            q_labels.add(value)
    return len(y_labels), len(q_labels), y_labels, q_labels


def _label_sequence_ok(labels: set[str], prefix: str) -> bool:
    if not labels:
        return True
    numbers = sorted(int(re.sub(r"\D", "", label)) for label in labels)
    return numbers == list(range(1, len(numbers) + 1))


def _type_string(l_count: int, t_count: int) -> str:
    return f"{l_count}L{t_count}T" if (l_count or t_count) else ""


def identify_rmus(
    tree: ET.ElementTree,
    file_path: Path,
    *,
    name_positions: tuple[str, ...] = ("top",),
    smart_in_type: bool = False,
    excluded_name_values: tuple[str, ...] = (),
) -> RmuIdentificationResult:
    """识别环网柜名称、L/T 柜型及 SMART 状态，不修改 XML。

    v2.17.11 规则：
    1. 必须存在环网柜 rect，且框内同时具有 BusDis、CBreakerDis、ZhaiWaiJieDiDaoZha。
    2. 柜名只在用户指定方向寻找并做全局一对一匹配；单候选直接使用，多候选时绿色优先。
       指定方向的常规几何匹配失败时，仅当柜内 BusDis.key_name 唯一候选与所选方向附近同名 Text 完全一致时回退；不跨方向猜名。
    3. 柜型第一来源为框内 Y1/Y2/... 与 Q1/Q2/...：Y 数量=L，Q 数量=T，并检查序号连续性。
       第二来源仅按 CBreakerDis.devref 图元文件名：Load_Breaker*=L，Circuit_Breaker*=T。
       两种来源同时存在时强制交叉校验；某一类 Y/Q 完全缺失时才用 devref 对应类别回退。
    4. 柜型始终只输出 nLmT；SMART 与 SMR 在统计层统一归类为“智能环网柜”，不追加到柜型字符串。

    smart_in_type 参数为了兼容现有设置保留；现在表示是否统计智能环网柜（SMART / SMR）。
    """
    if not name_positions:
        raise ValueError("环网柜名称位置至少选择一个方向。")

    excluded_names = frozenset(
        key for value in excluded_name_values
        if (key := _normalize_excluded_name(value))
    )

    elements = direct_layer_elements(tree.getroot())
    rects = [element for element in elements if local_name(element.tag) == "rect"]
    texts = [element for element in elements if local_name(element.tag) in {"Text", "DText"}]
    switches = [element for element in elements if local_name(element.tag) == "CBreakerDis"]
    buses = [element for element in elements if local_name(element.tag) == "BusDis"]
    grounds = [element for element in elements if local_name(element.tag) == "ZhaiWaiJieDiDaoZha"]

    result = RmuIdentificationResult(file_path=file_path)

    # First determine the complete cabinet set.  Name assignment is deliberately
    # done globally afterwards so adjacent cabinets cannot reuse/steal the same
    # Text.  Only user-selected directions are ever considered.
    valid_cabinets: list[tuple[ET.Element, _Box]] = []
    for rect in rects:
        rect_box = _box(rect)
        if rect_box is None or rect_box.width < 100 or rect_box.height < 100:
            continue
        inside_switches = [item for item in switches if _center_inside(item, rect_box)]
        inside_bus = [item for item in buses if _center_inside(item, rect_box)]
        inside_ground = [item for item in grounds if _center_inside(item, rect_box)]
        if not inside_bus or not inside_switches or not inside_ground:
            continue
        valid_cabinets.append((rect, rect_box))

    cabinet_boxes = [((rect.get("id") or f"__rect_{index}"), rect_box)
                     for index, (rect, rect_box) in enumerate(valid_cabinets)]
    name_assignments = _assign_names_globally(texts, cabinet_boxes, name_positions, excluded_names)

    # SMR is also an intelligent RMU marker. It is usually outside the cabinet frame,
    # so map each direct Text[ts=SMR] to the nearest valid RMU rect. This is read-only
    # identification and does not change the existing SMART/grouping algorithms.
    smr_rect_keys: set[str] = set()
    if smart_in_type and valid_cabinets:
        smr_texts = [
            item for item in elements
            if local_name(item.tag) == "Text" and (item.get("ts") or "").strip().upper() == "SMR"
        ]
        for text in smr_texts:
            text_box = _box(text)
            if text_box is None:
                continue
            candidates: list[tuple[float, str]] = []
            for cabinet_index, (rect, rect_box) in enumerate(valid_cabinets):
                key = rect.get("id") or f"__rect_{cabinet_index}"
                candidates.append((_point_to_box_distance(text_box.center_x, text_box.center_y, rect_box), key))
            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1]))
                smr_rect_keys.add(candidates[0][1])

    for index, (rect, rect_box) in enumerate(valid_cabinets):
        rect_key = rect.get("id") or f"__rect_{index}"
        inside_switches = [item for item in switches if _center_inside(item, rect_box)]
        inside_buses = [item for item in buses if _center_inside(item, rect_box)]
        inside_texts = [item for item in texts if _center_inside(item, rect_box)]
        y_count, q_count, y_labels, q_labels = _label_counts(inside_texts)
        devref_l = sum(1 for item in inside_switches if _classify_switch_by_devref(item) == "L")
        devref_t = sum(1 for item in inside_switches if _classify_switch_by_devref(item) == "T")

        warnings: list[str] = []
        y_sequence_ok = _label_sequence_ok(y_labels, "Y")
        q_sequence_ok = _label_sequence_ok(q_labels, "Q")
        if not y_sequence_ok:
            warnings.append("柜内 Y 标签不是从 Y1 开始连续递增")
        if not q_sequence_ok:
            warnings.append("柜内 Q 标签不是从 Q1 开始连续递增")

        text_yq_type = _type_string(y_count, q_count)
        devref_type = _type_string(devref_l, devref_t)

        # 最终柜型仍以 Y/Q 文字为主；某一类文字完全缺失时，才使用 devref 对应类别补齐。
        l_count = y_count if y_count > 0 else devref_l
        t_count = q_count if q_count > 0 else devref_t
        if y_count == 0 and devref_l:
            warnings.append(f"未识别到 Y 名称，L 使用 devref 图元文件名回退计数 {devref_l}")
        if q_count == 0 and devref_t:
            warnings.append(f"未识别到 Q 名称，T 使用 devref 图元文件名回退计数 {devref_t}")

        if y_count and q_count:
            type_source = "TEXT_YQ"
        elif (y_count or q_count) and (devref_l or devref_t):
            type_source = "TEXT_YQ+DEVREF_FALLBACK"
        elif devref_l or devref_t:
            type_source = "DEVREF"
        else:
            type_source = "UNKNOWN"

        if text_yq_type and devref_type:
            if text_yq_type == devref_type and y_sequence_ok and q_sequence_ok:
                type_cross_check = "YES"
                type_validation_status = "PASS"
                type_cross_note = f"Y/Q={text_yq_type}，devref={devref_type}，两种识别结果一致"
            else:
                type_cross_check = "NO"
                type_validation_status = "FAIL"
                details: list[str] = []
                if text_yq_type != devref_type:
                    details.append(f"Y/Q={text_yq_type} 与 devref={devref_type} 不一致")
                if not y_sequence_ok:
                    details.append("Y 标签序号不连续")
                if not q_sequence_ok:
                    details.append("Q 标签序号不连续")
                type_cross_note = "；".join(details) or "柜型交叉校验失败"
                warnings.append(type_cross_note)
        elif text_yq_type:
            type_cross_check = "N/A"
            type_validation_status = "WARN"
            type_cross_note = f"仅识别到 Y/Q 文字类型 {text_yq_type}，devref 信息不足，无法双源交叉校验"
            warnings.append(type_cross_note)
        elif devref_type:
            type_cross_check = "N/A"
            type_validation_status = "WARN"
            type_cross_note = f"仅识别到 devref 类型 {devref_type}，Y/Q 文字不足，使用 devref 回退"
            warnings.append(type_cross_note)
        else:
            type_cross_check = "NO"
            type_validation_status = "FAIL"
            type_cross_note = "Y/Q 文字和 devref 均无法识别柜型"
            warnings.append(type_cross_note)

        name, position, confidence, name_warnings = name_assignments.get(
            rect_key, ("", "", "未识别", [])
        )
        warnings.extend(name_warnings)
        # Conservative metadata fallback: only when the existing direction-based
        # Text algorithm found no usable name.  A unique BusDis.key_name such as
        # 38995_BUS may then supply 38995.  This does not broaden direction geometry
        # and does not alter cabinet/type detection.
        if not name:
            bus_name = _bus_key_name_candidate(inside_buses, excluded_names)
            if bus_name and _metadata_name_confirmed_by_text(
                texts, rect_box, name_positions, bus_name, excluded_names
            ):
                name = bus_name
                position = "BusDis.key_name+Text"
                confidence = "高"

        smart_count = 0
        smart_source = ""
        if smart_in_type:
            smart_text = any((item.get("ts") or "").strip().upper() == "SMART" for item in inside_texts)
            smart_device = any(_is_smart_device(item) for item in inside_switches)
            smr_text = rect_key in smr_rect_keys
            sources: list[str] = []
            if smart_text or smart_device:
                sources.append("SMART")
            if smr_text:
                sources.append("SMR")
            smart_source = " + ".join(sources)
            smart_count = 1 if sources else 0

        rmu_type = _type_string(l_count, t_count)
        if warnings and confidence == "高":
            confidence = "中"

        result.items.append(RmuIdentification(
            rect_id=(rect.get("id") or "").strip(),
            name=name,
            name_position=position,
            rmu_type=rmu_type,
            l_count=l_count,
            t_count=t_count,
            smart_count=smart_count,
            smart_source=smart_source,
            type_source=type_source,
            text_yq_type=text_yq_type,
            devref_type=devref_type,
            type_cross_check=type_cross_check,
            type_validation_status=type_validation_status,
            type_cross_note=type_cross_note,
            confidence=confidence,
            rect_x=rect_box.left,
            rect_y=rect_box.top,
            rect_w=rect_box.width,
            rect_h=rect_box.height,
            warnings=warnings,
        ))

    result.cabinet_count = len(result.items)
    result.named_count = sum(1 for item in result.items if item.name)
    result.typed_count = sum(1 for item in result.items if item.l_count or item.t_count)
    result.ambiguous_name_count = sum(1 for item in result.items if item.confidence == "待确认")
    for item in result.items:
        if not item.name:
            result.warnings.append(f"rect ID {item.rect_id or '<无ID>'} 未找到指定方向且距离足够近的柜名。")
        for warning in item.warnings:
            result.warnings.append(f"rect ID {item.rect_id or '<无ID>'}：{warning}")
    return result
