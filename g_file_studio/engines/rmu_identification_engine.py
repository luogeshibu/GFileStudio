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


def parse_intelligent_markers(raw: str) -> tuple[str, ...]:
    """Parse user-configured intelligent-RMU Text markers.

    Values are comma/semicolon/newline separated and matched as whole Text
    values, case-insensitively.  SMART/SMR remain the default for backward
    compatibility.  The same marker values are automatically excluded from RMU
    name candidates so a marker such as NEWSMART cannot become a cabinet name.
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
    return tuple(unique) if unique else ("SMART", "SMR")


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




_AUTO_NAME_POSITIONS = ("top", "right", "bottom", "left")


@dataclass(frozen=True)
class _AutoNameCandidate:
    rect_id: str
    text_key: str
    value: str
    position: str
    gap: float
    axis_offset: float
    pattern: str
    color: str
    green: bool

    @property
    def geometry_score(self) -> float:
        return self.gap + self.axis_offset * 0.08


def _auto_name_pattern(value: str) -> str:
    """Return a compact lexical style signature for cluster learning.

    Examples: ``29521 -> #``, ``AK-900841 -> AK-#``, ``K-00018 -> K-#``.
    The signature is deliberately learned from the current cluster instead of
    being hard-coded to a site/prefix.
    """
    compact = re.sub(r"\s+", "", (value or "").strip()).upper()
    return re.sub(r"\d+", "#", compact)


def _auto_color_key(text: ET.Element) -> str:
    lcc = (text.get("lcc") or "").strip().lower()
    if lcc:
        return lcc
    lc = re.sub(r"\s+", "", (text.get("lc") or "").strip())
    return lc.lower()


def _valid_auto_name_text(
    element: ET.Element,
    excluded_names: frozenset[str] = frozenset(),
) -> bool:
    """Stricter candidate filter used only by automatic RMU-name resolution.

    Direction/color are not hard requirements.  We only remove labels that are
    clearly internal/status annotations so a cluster can learn its own external
    name style (numeric, AK-*, etc.).
    """
    if not _valid_name_text(element, excluded_names):
        return False
    value = (element.get("ts") or "").strip()
    if re.fullmatch(r"\(\s*\d+\s*\)", value):
        return False
    compact = re.sub(r"\s+", "", value).upper()
    alnum = re.sub(r"[^A-Z0-9]+", "", compact)
    if alnum in {"NOP", "FC", "F", "SMART", "SMR", "BUS", "NORMAL", "EARTH"}:
        return False
    if re.fullmatch(r"[YQ]\d+D?", alnum):
        return False
    return True


def _candidate_for_auto_position(
    text: ET.Element,
    rect: _Box,
    position: str,
) -> tuple[float, float] | None:
    """All-direction RMU candidate geometry for auto-layout mode.

    Unlike the legacy selected-direction matcher, this does not encode a site
    direction.  The four sides are evaluated symmetrically, then a cabinet
    cluster chooses the best repeated layout.
    """
    box = _box(text)
    if box is None:
        return None

    base = max(rect.width, rect.height)
    max_distance = max(160.0, min(320.0, base * 1.10))
    projection_tolerance = max(60.0, min(140.0, base * 0.45))
    edge_tolerance = 45.0

    if position == "top":
        gap = rect.top - box.bottom
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_y < rect.top
            and rect.left - projection_tolerance <= box.center_x <= rect.right + projection_tolerance
        ):
            return max(0.0, gap), abs(box.center_x - rect.center_x)
    elif position == "bottom":
        gap = box.top - rect.bottom
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_y > rect.bottom
            and rect.left - projection_tolerance <= box.center_x <= rect.right + projection_tolerance
        ):
            return max(0.0, gap), abs(box.center_x - rect.center_x)
    elif position == "left":
        gap = rect.left - box.right
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_x < rect.left
            and rect.top - projection_tolerance <= box.center_y <= rect.bottom + projection_tolerance
        ):
            return max(0.0, gap), abs(box.center_y - rect.center_y)
    elif position == "right":
        gap = box.left - rect.right
        if (
            -edge_tolerance <= gap <= max_distance
            and box.center_x > rect.right
            and rect.top - projection_tolerance <= box.center_y <= rect.bottom + projection_tolerance
        ):
            return max(0.0, gap), abs(box.center_y - rect.center_y)
    return None


def _auto_candidates_for_rect(
    texts: list[ET.Element],
    rect_id: str,
    rect: _Box,
    excluded_names: frozenset[str],
) -> list[_AutoNameCandidate]:
    candidates: list[_AutoNameCandidate] = []
    for index, text in enumerate(texts):
        if not _valid_auto_name_text(text, excluded_names):
            continue
        value = (text.get("ts") or "").strip()
        text_id = (text.get("id") or "").strip()
        text_key = text_id or f"__auto_text_{index}"
        pattern = _auto_name_pattern(value)
        color = _auto_color_key(text)
        green = _is_green_name_text(text)
        for position in _AUTO_NAME_POSITIONS:
            metric = _candidate_for_auto_position(text, rect, position)
            if metric is None:
                continue
            candidates.append(_AutoNameCandidate(
                rect_id=rect_id,
                text_key=text_key,
                value=value,
                position=position,
                gap=metric[0],
                axis_offset=metric[1],
                pattern=pattern,
                color=color,
                green=green,
            ))
    return candidates


def _median(values: list[float], default: float) -> float:
    if not values:
        return default
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _axis_bands(
    cabinets: list[tuple[str, _Box]],
    axis: str,
) -> list[tuple[list[str], float]]:
    if not cabinets:
        return []
    if axis == "x":
        coords = [(rect.center_x, rect_id) for rect_id, rect in cabinets]
        size = _median([rect.width for _rect_id, rect in cabinets], 220.0)
    else:
        coords = [(rect.center_y, rect_id) for rect_id, rect in cabinets]
        size = _median([rect.height for _rect_id, rect in cabinets], 220.0)
    tolerance = max(35.0, min(110.0, size * 0.40))
    coords.sort()
    groups: list[list[tuple[float, str]]] = []
    for coord, rect_id in coords:
        if not groups:
            groups.append([(coord, rect_id)])
            continue
        current_mean = sum(value for value, _rid in groups[-1]) / len(groups[-1])
        if abs(coord - current_mean) <= tolerance:
            groups[-1].append((coord, rect_id))
        else:
            groups.append([(coord, rect_id)])
    result: list[tuple[list[str], float]] = []
    for group in groups:
        if len(group) < 2:
            continue
        vals = [value for value, _rid in group]
        spread = max(vals) - min(vals)
        result.append(([rid for _value, rid in group], spread))
    return result


def _auto_cluster_cabinets(cabinets: list[tuple[str, _Box]]) -> list[list[str]]:
    """Create non-overlapping repeated-layout RMU clusters.

    Long aligned columns beat shorter cross-rows (MAK sample); long aligned rows
    beat incidental short columns (ABHA-style rows).  Remaining cabinets become
    singletons and use the local all-direction fallback.
    """
    if len(cabinets) <= 1:
        return [[rect_id] for rect_id, _rect in cabinets]

    proposals: list[tuple[int, float, str, list[str]]] = []
    for axis in ("x", "y"):
        for ids, spread in _axis_bands(cabinets, axis):
            proposals.append((len(ids), spread, axis, ids))
    # Larger repeated patterns are stronger evidence; tighter alignment breaks ties.
    proposals.sort(key=lambda row: (-row[0], row[1], row[2], tuple(row[3])))

    assigned: set[str] = set()
    clusters: list[list[str]] = []
    for _size, _spread, _axis, ids in proposals:
        remaining = [rid for rid in ids if rid not in assigned]
        if len(remaining) < 2:
            continue
        clusters.append(remaining)
        assigned.update(remaining)
    for rect_id, _rect in cabinets:
        if rect_id not in assigned:
            clusters.append([rect_id])
            assigned.add(rect_id)
    return clusters


def _style_rank(
    style: tuple[str, str],
    candidates: list[_AutoNameCandidate],
    cluster_size: int,
) -> tuple[int, int, int, float, float, str, str]:
    pattern, color = style
    matched = [item for item in candidates if item.pattern == pattern and item.color == color]
    covered = {item.rect_id for item in matched}
    pattern_covered = {item.rect_id for item in candidates if item.pattern == pattern}
    green_bonus = 1 if any(item.green for item in matched) else 0
    avg_gap = sum(item.gap for item in matched) / max(1, len(matched))
    avg_axis = sum(item.axis_offset for item in matched) / max(1, len(matched))
    # Coverage is authoritative.  When two repeated styles cover the same RMUs,
    # green is a strong disambiguation signal (ABHA AK-* vs K-*/A-* labels), but
    # it never overrides a better-coverage non-green style.
    return (
        len(covered),
        green_bonus,
        len(pattern_covered),
        -avg_gap,
        -avg_axis,
        pattern,
        color,
    )


def _dominant_style_for_direction(
    candidates: list[_AutoNameCandidate],
    cluster_size: int,
) -> tuple[tuple[str, str] | None, tuple[int, int, int, float, float, str, str]]:
    styles = {(item.pattern, item.color) for item in candidates if item.pattern}
    if not styles:
        return None, (0, 0, 0, float("-inf"), float("-inf"), "", "")
    ranked = sorted(
        ((_style_rank(style, candidates, cluster_size), style) for style in styles),
        key=lambda row: row[0],
        reverse=True,
    )
    return ranked[0][1], ranked[0][0]


def _assign_cluster_direction(
    cluster_ids: list[str],
    all_candidates: dict[str, list[_AutoNameCandidate]],
) -> tuple[str | None, tuple[str, str] | None, dict[str, _AutoNameCandidate], dict[str, int]]:
    """Infer one repeated side/style and assign one Text to one RMU."""
    cluster_size = len(cluster_ids)
    direction_options: list[
        tuple[tuple[int, int, int, float, float, str, str], str, tuple[str, str] | None, list[_AutoNameCandidate]]
    ] = []
    for position in _AUTO_NAME_POSITIONS:
        directional = [
            item
            for rect_id in cluster_ids
            for item in all_candidates.get(rect_id, [])
            if item.position == position
        ]
        style, rank = _dominant_style_for_direction(directional, cluster_size)
        direction_options.append((rank, position, style, directional))

    direction_options.sort(key=lambda row: (row[0], row[1]), reverse=True)
    best_rank, position, dominant_style, directional = direction_options[0]
    min_support = max(2, (cluster_size + 1) // 2)
    if best_rank[0] < min_support:
        return None, None, {}, {}

    preferred_pattern = dominant_style[0] if dominant_style else ""
    edges: list[tuple[int, float, str, str, _AutoNameCandidate]] = []
    for item in directional:
        if dominant_style and (item.pattern, item.color) == dominant_style:
            fallback_level = 0
        elif preferred_pattern and item.pattern == preferred_pattern:
            fallback_level = 1
        else:
            fallback_level = 2
        edges.append((fallback_level, item.geometry_score, item.rect_id, item.text_key, item))
    edges.sort(key=lambda row: (row[0], row[1], row[2], row[3]))

    assigned_rects: set[str] = set()
    assigned_texts: set[str] = set()
    assigned: dict[str, _AutoNameCandidate] = {}
    fallback_levels: dict[str, int] = {}
    for fallback_level, _score, rect_id, text_key, item in edges:
        if rect_id in assigned_rects or text_key in assigned_texts:
            continue
        assigned_rects.add(rect_id)
        assigned_texts.add(text_key)
        assigned[rect_id] = item
        fallback_levels[rect_id] = fallback_level
    return position, dominant_style, assigned, fallback_levels


def _assign_singletons_auto(
    rect_ids: list[str],
    all_candidates: dict[str, list[_AutoNameCandidate]],
    used_texts: set[str],
) -> tuple[dict[str, _AutoNameCandidate], dict[str, str]]:
    assigned: dict[str, _AutoNameCandidate] = {}
    confidence: dict[str, str] = {}
    for rect_id in rect_ids:
        candidates = [item for item in all_candidates.get(rect_id, []) if item.text_key not in used_texts]
        if not candidates:
            continue
        # No cluster style is available.  Green remains a useful weak signal for
        # multi-line ABHA-style labels; otherwise pure geometry wins across all four sides.
        greens = [item for item in candidates if item.green]
        pool = greens if greens else candidates
        pool.sort(key=lambda item: (item.geometry_score, item.position, item.value, item.text_key))
        chosen = pool[0]
        assigned[rect_id] = chosen
        used_texts.add(chosen.text_key)
        confidence[rect_id] = "中" if len(candidates) > 1 else "高"
    return assigned, confidence


def _assign_names_auto_cluster(
    texts: list[ET.Element],
    cabinets: list[tuple[str, _Box]],
    excluded_names: frozenset[str] = frozenset(),
) -> dict[str, tuple[str, str, str, list[str]]]:
    """Automatic RMU name resolver used by G Graphic Content Analysis.

    It learns repeated layout per RMU cluster (TOP/RIGHT/BOTTOM/LEFT), then learns
    the dominant text style within that cluster and performs one-to-one matching.
    No site direction is required.  Single/irregular cabinets fall back to an
    all-direction local resolver.
    """
    all_candidates = {
        rect_id: _auto_candidates_for_rect(texts, rect_id, rect, excluded_names)
        for rect_id, rect in cabinets
    }
    result: dict[str, tuple[str, str, str, list[str]]] = {
        rect_id: ("", "", "未识别", []) for rect_id, _rect in cabinets
    }
    used_texts: set[str] = set()
    clusters = _auto_cluster_cabinets(cabinets)

    # Strong repeated-layout clusters first; singletons/irregular remnants later.
    for cluster_ids in [cluster for cluster in clusters if len(cluster) >= 2]:
        position, _style, assigned, fallback_levels = _assign_cluster_direction(cluster_ids, all_candidates)
        if position is None:
            continue
        for rect_id, item in assigned.items():
            if item.text_key in used_texts:
                continue
            used_texts.add(item.text_key)
            level = fallback_levels.get(rect_id, 2)
            confidence = "高" if level == 0 else "中"
            result[rect_id] = (item.value, position, confidence, [])

    unresolved = [
        rect_id
        for rect_id, _rect in cabinets
        if not result[rect_id][0]
    ]
    singleton_assigned, singleton_confidence = _assign_singletons_auto(unresolved, all_candidates, used_texts)
    for rect_id, item in singleton_assigned.items():
        result[rect_id] = (
            item.value,
            item.position,
            singleton_confidence.get(rect_id, "中"),
            [],
        )
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
    name_resolution_mode: str = "selected_direction",
    smart_in_type: bool = False,
    excluded_name_values: tuple[str, ...] = (),
    intelligent_marker_values: tuple[str, ...] = ("SMART", "SMR"),
) -> RmuIdentificationResult:
    """识别环网柜名称、L/T 柜型及 SMART 状态，不修改 XML。

    名称识别支持两种模式：
    - selected_direction（默认）：保持历史行为，只在用户指定方向内做一对一匹配；
    - auto_cluster：供 G 图形内容解析使用。按重复 RMU 排列自动分 Cluster，四方向对称评估，
      自动学习每个 Cluster 的名称方向与主导文字风格（颜色/文本模式仅作为组内证据），
      然后整组一对一分配；孤立/不规则 RMU 才退化到全方向局部最近候选。

    共同规则：
    1. 必须存在环网柜 rect，且框内同时具有 BusDis、CBreakerDis、ZhaiWaiJieDiDaoZha。
    2. BusDis.key_name 只作为保守回退，必须有附近完全同名 Text 确认，不接受纯 metadata 猜名。
    3. 柜型第一来源为框内 Y1/Y2/... 与 Q1/Q2/...：Y 数量=L，Q 数量=T，并检查序号连续性。
       第二来源仅按 CBreakerDis.devref 图元文件名：Load_Breaker*=L，Circuit_Breaker*=T。
       L/T 按类别分别交叉校验：已同时存在的类别计数不一致才 FAIL；某一类 Y/Q 完全缺失时
       使用 devref 对应类别回退并标记 WARN（证据不完整），不再因为完整字符串如 2L0T/2L1T 不同而误判 FAIL。
    4. 柜型始终只输出 nLmT；用户配置的智能标记 Text 在统计层统一归类为“智能环网柜”，不追加到柜型字符串。
       智能标记在全图有效 RMU 集合中做最近归属，每个标记只允许归属一个 RMU；标记无需完全落在柜框内。
       默认标记为 SMART / SMR，可扩展为 NEWSMART、SMART-SE 等任意完整 Text。

    smart_in_type 参数为了兼容现有设置保留；现在表示是否统计智能环网柜。
    """
    mode = (name_resolution_mode or "selected_direction").strip().lower()
    if mode not in {"selected_direction", "auto_cluster"}:
        raise ValueError(f"未知 RMU 柜名识别模式：{name_resolution_mode}")
    if mode == "selected_direction" and not name_positions:
        raise ValueError("环网柜名称位置至少选择一个方向。")

    intelligent_markers = tuple(
        value for value in intelligent_marker_values if _normalize_excluded_name(value)
    ) or ("SMART", "SMR")
    marker_key_to_source = {
        _normalize_excluded_name(value): re.sub(r"\s+", " ", value.strip()).upper()
        for value in intelligent_markers
        if _normalize_excluded_name(value)
    }
    excluded_names = frozenset(
        key
        for value in (*excluded_name_values, *intelligent_markers)
        if (key := _normalize_excluded_name(value))
    )

    elements = direct_layer_elements(tree.getroot())
    rects = [element for element in elements if local_name(element.tag) == "rect"]
    # Device/RMU names are static drawing labels.  DText is reserved for
    # dynamic measurements and must be handled only by a later association
    # stage, never as a name candidate.
    texts = [element for element in elements if local_name(element.tag) == "Text"]
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
    if mode == "auto_cluster":
        name_assignments = _assign_names_auto_cluster(texts, cabinet_boxes, excluded_names)
    else:
        name_assignments = _assign_names_globally(texts, cabinet_boxes, name_positions, excluded_names)

    # User-configured intelligent markers are global RMU markers. They are not
    # required to be fully inside a cabinet frame: a label may sit on / slightly
    # outside the frame. Each marker is assigned to exactly ONE nearest valid RMU.
    marker_sources_by_rect: dict[str, set[str]] = {}
    if smart_in_type and valid_cabinets:
        marker_texts = [
            item for item in tree.getroot().iter()
            if local_name(item.tag) == "Text"
            and _normalize_excluded_name(item.get("ts") or "") in marker_key_to_source
        ]
        for marker in marker_texts:
            marker_box = _box(marker)
            if marker_box is None:
                result.warnings.append(
                    f"智能标记 {(marker.get('ts') or '').strip().upper()} "
                    f"Text ID {(marker.get('id') or '<无ID>')} 缺少有效几何坐标，未参与 RMU 归属。"
                )
                continue
            candidates: list[tuple[float, float, str]] = []
            for cabinet_index, (rect, rect_box) in enumerate(valid_cabinets):
                key = rect.get("id") or f"__rect_{cabinet_index}"
                edge_distance = _point_to_box_distance(marker_box.center_x, marker_box.center_y, rect_box)
                center_distance = (
                    (marker_box.center_x - rect_box.center_x) ** 2
                    + (marker_box.center_y - rect_box.center_y) ** 2
                ) ** 0.5
                candidates.append((edge_distance, center_distance, key))
            if not candidates:
                continue
            # Distance to frame is authoritative. Center distance breaks ordinary
            # overlap/touch ties. If two RMUs remain geometrically identical after
            # both comparisons, the data is ambiguous: skip instead of guessing,
            # so one marker can never be attributed to two cabinets.
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            chosen_edge, chosen_center, chosen_key = candidates[0]
            if len(candidates) > 1:
                next_edge, next_center, next_key = candidates[1]
                if abs(chosen_edge - next_edge) <= 1e-6 and abs(chosen_center - next_center) <= 1e-6:
                    result.warnings.append(
                        f"智能标记 {(marker.get('ts') or '').strip().upper()} "
                        f"Text ID {(marker.get('id') or '<无ID>')} 与 RMU {chosen_key}/{next_key} "
                        f"几何距离完全相同，无法唯一归属；为避免一个标记属于两个 RMU，已跳过该标记。"
                    )
                    continue
            marker_key = _normalize_excluded_name(marker.get("ts") or "")
            source = marker_key_to_source.get(marker_key, (marker.get("ts") or "").strip().upper())
            marker_sources_by_rect.setdefault(chosen_key, set()).add(source)

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

        # v2.18.131: cross-check L/T per category instead of comparing the raw
        # full type string when one Y/Q category is completely absent.  A missing
        # category that is successfully filled from devref is incomplete evidence
        # (WARN), not a genuine conflict (FAIL).  A category that is present in
        # both sources but has different counts remains a hard FAIL.
        has_text_y = y_count > 0
        has_text_q = q_count > 0
        has_devref_l = devref_l > 0
        has_devref_t = devref_t > 0

        comparable_categories: list[str] = []
        mismatch_details: list[str] = []
        fallback_details: list[str] = []
        incomplete_details: list[str] = []

        if has_text_y and has_devref_l:
            comparable_categories.append("L")
            if y_count != devref_l:
                mismatch_details.append(f"Y={y_count}L 与 devref L={devref_l}L 不一致")
        elif has_text_y and not has_devref_l:
            incomplete_details.append(f"Y={y_count}L 缺少对应 devref L 证据")
        elif not has_text_y and has_devref_l:
            fallback_details.append(f"Y 缺失，L 使用 devref 回退 {devref_l}L")

        if has_text_q and has_devref_t:
            comparable_categories.append("T")
            if q_count != devref_t:
                mismatch_details.append(f"Q={q_count}T 与 devref T={devref_t}T 不一致")
        elif has_text_q and not has_devref_t:
            incomplete_details.append(f"Q={q_count}T 缺少对应 devref T 证据")
        elif not has_text_q and has_devref_t:
            fallback_details.append(f"Q 缺失，T 使用 devref 回退 {devref_t}T")

        if not y_sequence_ok:
            mismatch_details.append("Y 标签序号不连续")
        if not q_sequence_ok:
            mismatch_details.append("Q 标签序号不连续")

        if mismatch_details:
            type_cross_check = "NO"
            type_validation_status = "FAIL"
            type_cross_note = "；".join(mismatch_details)
            warnings.append(type_cross_note)
        elif has_text_y and has_text_q and has_devref_l and has_devref_t:
            # Both categories have complete two-source evidence and agree.
            type_cross_check = "YES"
            type_validation_status = "PASS"
            type_cross_note = f"Y/Q={text_yq_type}，devref={devref_type}，两种识别结果一致"
        elif text_yq_type and devref_type:
            # At least one Y/Q category is absent or one corresponding devref
            # category is missing.  Keep the resolved final type, but explicitly
            # report that only a partial cross-check was possible.
            type_cross_check = "PARTIAL" if comparable_categories else "N/A"
            type_validation_status = "WARN"
            details = []
            if comparable_categories:
                details.append("已交叉校验 " + "/".join(comparable_categories) + " 类计数一致")
            details.extend(fallback_details)
            details.extend(incomplete_details)
            type_cross_note = "；".join(details) or (
                f"Y/Q={text_yq_type}，devref={devref_type}，仅能进行部分双源交叉校验"
            )
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
            metadata_positions = _AUTO_NAME_POSITIONS if mode == "auto_cluster" else name_positions
            if bus_name and _metadata_name_confirmed_by_text(
                texts, rect_box, metadata_positions, bus_name, excluded_names
            ):
                name = bus_name
                position = "BusDis.key_name+Text"
                confidence = "高"

        smart_count = 0
        smart_source = ""
        if smart_in_type:
            marker_sources = marker_sources_by_rect.get(rect_key, set())
            smart_device = any(_is_smart_device(item) for item in inside_switches)
            source_order = [marker_key_to_source[_normalize_excluded_name(value)] for value in intelligent_markers]
            sources = [source for source in source_order if source in marker_sources]
            # Preserve the historical SMART-device fallback only when no configured
            # visible marker was assigned to this cabinet.
            if smart_device and not sources:
                sources.append("SMART_DEVICE")
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
            if mode == "auto_cluster":
                result.warnings.append(f"rect ID {item.rect_id or '<无ID>'} 自动布局未找到距离足够近的有效柜名。")
            else:
                result.warnings.append(f"rect ID {item.rect_id or '<无ID>'} 未找到指定方向且距离足够近的柜名。")
        for warning in item.warnings:
            result.warnings.append(f"rect ID {item.rect_id or '<无ID>'}：{warning}")
    return result
