from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

from g_file_studio.engines.id_engine import direct_layers, local_name
from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import (
    _Box,
    _allocate_poke_id,
    _all_used_ids,
    _box,
    _move_poke_to_background,
    _new_poke,
    _number,
)


# Station-jump labels are intentionally kept stricter than ordinary drawing
# text.  A confirmed strip is normally a compact ``STATION-SUFFIX`` or
# ``STATION SUFFIX`` label.  The station token may start with a digit (5MR),
# and the drawing-side suffix may be alphanumeric (JM2-J2).  Requiring exactly
# one separator prevents long equipment/design labels such as V2-W-J-H-0017
# from becoming station-jump candidates merely because they end in digits.
_STATION_LABEL_RE = re.compile(
    r"^\s*(?P<station>[A-Za-z0-9][A-Za-z0-9_]*)\s*(?:[-–—]|\s)\s*(?P<suffix>[A-Za-z0-9][A-Za-z0-9_]*)\s*$"
)


# Canonical station-jump Poke properties copied from the user-provided
# JM2-J2 reference Poke (id=17001493) in JED-CTL-AJWD-15.sln.pic(2).g.
# Geometry (id/x/y/w/h), ahref and G File Studio metadata remain dynamic;
# every other Poke property below is normalized exactly to the reference.
_STATION_JUMP_POKE_REFERENCE_ATTRS: dict[str, str] = {
    'PlaneState19': '0',
    'PlaneState42': '0',
    'clip': 'false',
    'PlaneState7': '0',
    'af': '2147483647',
    'PlaneState8': '0',
    'PlaneState45': '0',
    'PlaneState40': '0',
    'fc': '100,100,100',
    'ShadowType': '0',
    'isDisplay': '1',
    'PlaneState9': '0',
    'PlaneState23': '0',
    'p_FatherObjId': '',
    'PlaneState30': '0',
    'PlaneState14': '0',
    'PlaneState48': '0',
    'lw': '1',
    'ls': '1',
    'PlaneState38': '0',
    'PlaneState36': '0',
    'PlaneState0': '1',
    'PlaneState37': '0',
    'p_EngcodeString': '',
    'lcc': '#000000',
    'PlaneState33': '0',
    'af4': '2147483647',
    'tfr': 'rotate(0) scale(1,1)',
    'p_RectStyle': '1',
    'onMouseLeftDoubleClickAciton': '',
    'PlaneState32': '0',
    'PlaneState6': '0',
    'PlaneState44': '0',
    'RectStyle': '1',
    'onMouseRightOneClickAction': '',
    'PlaneState49': '0',
    'PlaneState31': '0',
    'lc': '0,0,0',
    'switchapp': '1',
    'PlaneState25': '0',
    'PlaneState4': '0',
    'PlaneState17': '0',
    'fm': '1',
    'PlaneState12': '0',
    'aliasType': '',
    'onMouseHoverLeaveAction': '',
    'PlaneState47': '0',
    'PlaneState39': '0',
    'PlaneState46': '0',
    'LevelEnd': '16',
    'p_DyColorFlag': '0',
    'onMouseLeftOneClickAction': '',
    'PlaneState20': '0',
    'onMouseHoverEnterAction': '',
    'PlaneState27': '0',
    'p_ShowModeMask': '3',
    'rotate': '0',
    'PlaneState15': '0',
    'PlaneState21': '0',
    'PlaneState3': '0',
    'eventRegister': '',
    'PlaneState5': '0',
    'switchappflag': '1',
    'p_SelfDefString': '',
    'fcc': '#646464',
    'PlaneState29': '0',
    'af3': '2147483647',
    'trend_color': '0',
    'PlaneState10': '0',
    'PlaneState28': '0',
    'onMouseRightDoubleClickAction': '',
    'PlaneState41': '0',
    'PlaneState34': '0',
    'opacity': '1',
    'af2': '2147483647',
    'PlaneState1': '0',
    'PlaneState16': '0',
    'PlaneState18': '0',
    'PlaneState26': '0',
    'p_AssFlag': '128',
    'PlaneState24': '0',
    'rain_bow': '0',
    'PlaneState2': '0',
    'PlaneState11': '0',
    'PlaneState13': '0',
    'LevelStart': '0',
    'PlaneState35': '0',
    'PlaneState43': '0',
    'PlaneState22': '0',
    'devref': '',
}


@dataclass
class StationPokeChange:
    label_text: str
    station_key: str
    station_full_name: str
    text_id: str
    poke_id: str
    target_file: str
    action: str
    confidence: str
    recognition_source: str = ""
    removed_duplicates: int = 0


@dataclass
class StationPokeRecord:
    label_text: str
    station_key: str
    station_full_name: str = ""
    text_id: str = ""
    poke_id: str = ""
    target_file: str = ""
    action: str = "skipped"
    confidence: str = ""
    recognition_source: str = ""
    reason: str = ""


@dataclass
class StationPokeResult:
    file_path: Path
    scanned_text_count: int = 0
    candidate_count: int = 0
    eligible_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    removed_duplicate_count: int = 0
    skipped_count: int = 0
    changes: list[StationPokeChange] = field(default_factory=list)
    records: list[StationPokeRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_station_key(label: str) -> str:
    """Extract the station business key from a terminal label.

    Examples: DHN-40 -> DHN, BWD2-49 -> BWD2, FEL 03 -> FEL,
    JM2-J2 -> JM2, 5MR-23 -> 5MR.  The trailing drawing-side token is
    deliberately ignored by the database lookup and ahref generation.
    """
    value = re.sub(r"\s+", " ", str(label or "").strip())
    match = _STATION_LABEL_RE.fullmatch(value)
    if not match:
        return ""
    station = re.sub(r"\s+", " ", match.group("station").strip(" -–—"))
    # Avoid classifying device labels such as Y-1 / Q-1 as stations.
    letters = sum(ch.isalpha() for ch in station)
    if letters < 2:
        return ""
    return station


def _center(box: _Box) -> tuple[float, float]:
    return ((box.left + box.right) / 2.0, (box.top + box.bottom) / 2.0)


def _contains(outer: _Box, inner: _Box, tolerance: float = 3.0) -> bool:
    cx, cy = _center(inner)
    return (
        outer.left - tolerance <= cx <= outer.right + tolerance
        and outer.top - tolerance <= cy <= outer.bottom + tolerance
    )


def _intersection_area(a: _Box, b: _Box) -> float:
    width = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    height = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    return width * height


def _overlap_ratio_text(container: _Box, text: _Box) -> float:
    area = max(text.width * text.height, 1.0)
    return _intersection_area(container, text) / area


def _is_inside_rmu(text_box: _Box, identification: RmuIdentificationResult) -> bool:
    cx, cy = _center(text_box)
    for item in identification.items:
        left = item.rect_x
        top = item.rect_y
        right = left + item.rect_w
        bottom = top + item.rect_h
        if left <= cx <= right and top <= cy <= bottom:
            return True
    return False


def _parse_polyline_points(value: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for token in re.split(r"\s+", (value or "").strip()):
        if not token or "," not in token:
            continue
        x, y = token.split(",", 1)
        try:
            points.append((float(x), float(y)))
        except ValueError:
            continue
    return points


def _line_endpoints(layer: ET.Element) -> list[tuple[float, float]]:
    endpoints: list[tuple[float, float]] = []
    for element in list(layer):
        if local_name(element.tag) not in {"FeedLine", "ConnectLine"}:
            continue
        points = _parse_polyline_points(element.get("d") or "")
        if len(points) >= 2:
            endpoints.extend((points[0], points[-1]))
            continue
        box = _box(element)
        if box is not None:
            endpoints.extend(((box.left, box.top), (box.right, box.bottom)))
    return endpoints


def _nearest_endpoint_distance(text_box: _Box, endpoints: list[tuple[float, float]]) -> float:
    if not endpoints:
        return math.inf
    cx, cy = _center(text_box)
    return min(math.hypot(cx - x, cy - y) for x, y in endpoints)


def _compact_background_contains(layer: ET.Element, text_box: _Box) -> bool:
    """Fallback structural cue independent from fill color.

    Some drawings use a rect/rounded object behind the terminal label instead of
    a <poke>, and the fill color is not stable across projects.  A compact shape
    that geometrically contains the candidate text is therefore a supporting
    cue, but never sufficient by itself: the station name must also resolve
    uniquely in Oracle before any Poke is written.
    """
    for element in list(layer):
        if local_name(element.tag) not in {"rect", "roundrect", "ellipse"}:
            continue
        box = _box(element)
        if box is None or box.width <= 0 or box.height <= 0:
            continue
        if box.width > 500 or box.height > 160:
            continue
        if _contains(box, text_box, tolerance=6.0) or _overlap_ratio_text(box, text_box) >= 0.55:
            return True
    return False


def _related_station_pokes(layer: ET.Element, text_box: _Box, station_key: str, text_id: str) -> list[ET.Element]:
    candidates: list[ET.Element] = []
    for element in list(layer):
        if local_name(element.tag) != "poke":
            continue
        if (element.get("gfs_rmu_poke") or "") == "1":
            continue
        if text_id and (element.get("gfs_station_text_id") or "") == text_id:
            candidates.append(element)
            continue
        box = _box(element)
        if box is None:
            continue
        if _contains(box, text_box, tolerance=6.0) or _overlap_ratio_text(box, text_box) >= 0.35:
            candidates.append(element)
    # Keep identity uniqueness while preserving XML order.
    result: list[ET.Element] = []
    seen: set[int] = set()
    for item in candidates:
        marker = id(item)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def _choose_primary_poke(pokes: list[ET.Element], text_box: _Box, station_key: str, text_id: str) -> ET.Element:
    tcx, tcy = _center(text_box)

    def score(element: ET.Element) -> tuple[float, float, float, str]:
        metadata = 0.0
        if text_id and (element.get("gfs_station_text_id") or "") == text_id:
            metadata -= 3.0
        box = _box(element)
        if box is None:
            return (metadata + 20.0, 20.0, math.inf, element.get("id") or "")
        contains_penalty = 0.0 if _contains(box, text_box, tolerance=6.0) else 1.0
        overlap_penalty = 1.0 - min(1.0, _overlap_ratio_text(box, text_box))
        pcx, pcy = _center(box)
        distance = math.hypot(pcx - tcx, pcy - tcy)
        return (metadata + contains_penalty, overlap_penalty, distance, element.get("id") or "")

    return min(pokes, key=score)


def _ensure_station_attributes(
    poke: ET.Element,
    *,
    target_file: str,
    station_key: str,
    text_id: str,
    text_box: _Box,
    preserve_geometry: bool,
) -> bool:
    """Normalize one station-jump Poke to the JM2-J2 reference properties.

    The reference's non-geometric Poke attributes are copied exactly. The
    current object's id/geometry are preserved when reusing an existing Poke;
    a newly created Poke uses the detected station-label geometry. ahref and
    G File Studio metadata are dynamic by definition.
    """
    old = dict(poke.attrib)
    poke_id = (poke.get("id") or "").strip()
    if preserve_geometry:
        x = poke.get("x") or _number(text_box.left)
        y = poke.get("y") or _number(text_box.top)
        w = poke.get("w") or _number(text_box.width)
        h = poke.get("h") or _number(text_box.height)
    else:
        x = _number(text_box.left)
        y = _number(text_box.top)
        w = _number(text_box.width)
        h = _number(text_box.height)

    desired = dict(_STATION_JUMP_POKE_REFERENCE_ATTRS)
    desired.update({
        "id": poke_id,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "ahref": target_file,
        "gfs_station_poke": "1",
        "gfs_station_name": station_key,
        "gfs_station_text_id": text_id,
    })

    # Remove unrelated legacy attributes so a station-jump Poke has the same
    # complete property set as the JM2-J2 reference, plus dynamic fields.
    if old != desired:
        poke.attrib.clear()
        poke.attrib.update(desired)
        return True
    return False


def _logical_source_stem(file_path: Path) -> str:
    """Source filename used only as a self-jump safety check, never for naming."""
    name = file_path.name
    match = re.match(r"^(.*)\.sln\.pic(?:\(\d+\))?\.g$", name, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.match(r"^(.*?)(?:\(\d+\))?\.g$", name, flags=re.I)
    return (match.group(1) if match else file_path.stem).strip()


def apply_station_pokes(
    tree: ET.ElementTree,
    file_path: Path,
    identification: RmuIdentificationResult,
    *,
    current_station_name: str,
    station_resolver: Callable[[str], Any],
    endpoint_distance_limit: float = 320.0,
) -> StationPokeResult:
    """Create/update station-jump Pokes such as DHN-40 -> JED-CTL-DHN.

    Recognition intentionally does not depend on a particular background color.
    Priority is: an existing overlapping non-RMU Poke; otherwise a feeder/line
    endpoint near the label; otherwise a compact background shape.  Every visual
    candidate must still resolve uniquely through SUBSTATION.NAME -> SUBAREA_ID ->
    SUBCONTROLAREA.NAME before it is allowed to modify XML.
    """
    result = StationPokeResult(file_path=file_path)
    root = tree.getroot()
    used_ids = _all_used_ids(root)
    resolver_cache: dict[str, Any] = {}
    current_key = (current_station_name or "").strip().casefold()

    for layer in direct_layers(root):
        endpoints = _line_endpoints(layer)
        for text in list(layer):
            if local_name(text.tag) != "Text":
                continue
            result.scanned_text_count += 1
            label = (text.get("ts") or "").strip()
            station_key = extract_station_key(label)
            if not station_key:
                continue
            text_box = _box(text)
            if text_box is None:
                continue
            if _is_inside_rmu(text_box, identification):
                continue
            # Do not create a self-jump from the local feeder label back to the
            # current station.  Station-level Pokes represent remote terminals.
            if current_key and station_key.casefold() == current_key:
                continue

            result.candidate_count += 1
            text_id = (text.get("id") or "").strip()
            related = _related_station_pokes(layer, text_box, station_key, text_id)
            endpoint_distance = _nearest_endpoint_distance(text_box, endpoints)
            compact_background = _compact_background_contains(layer, text_box)

            if related:
                confidence = "HIGH"
                recognition_source = "existing_poke"
            elif endpoint_distance <= endpoint_distance_limit:
                confidence = "MEDIUM"
                recognition_source = "line_endpoint"
            elif compact_background:
                confidence = "MEDIUM"
                recognition_source = "compact_background"
            else:
                result.skipped_count += 1
                reason = f"站点跳转候选 {label!r} 缺少 Poke/线路末端/紧凑背景结构支撑，已跳过。"
                result.warnings.append(reason)
                result.records.append(StationPokeRecord(
                    label_text=label,
                    station_key=station_key,
                    text_id=text_id,
                    action="skipped",
                    recognition_source="none",
                    reason=reason,
                ))
                continue

            cache_key = station_key.casefold()
            try:
                context = resolver_cache.get(cache_key)
                if context is None:
                    context = station_resolver(station_key)
                    resolver_cache[cache_key] = context
            except Exception as exc:
                result.skipped_count += 1
                reason = f"站点跳转候选 {label!r} 提取变电站 {station_key!r} 后数据库校验失败：{exc}"
                result.warnings.append(reason)
                result.records.append(StationPokeRecord(
                    label_text=label,
                    station_key=station_key,
                    text_id=text_id,
                    action="skipped",
                    confidence=confidence,
                    recognition_source=recognition_source,
                    reason=reason,
                ))
                continue

            station_full_name = str(getattr(context, "station_full_name", "") or "").strip()
            if not station_full_name:
                result.skipped_count += 1
                reason = f"变电站 {station_key!r} 未解析到完整站名，已跳过。"
                result.warnings.append(reason)
                result.records.append(StationPokeRecord(
                    label_text=label,
                    station_key=station_key,
                    text_id=text_id,
                    action="skipped",
                    confidence=confidence,
                    recognition_source=recognition_source,
                    reason=reason,
                ))
                continue
            # facID is not required.  As a safety-only self-jump filter, compare
            # the DB-resolved station full name with the source filename stem.
            # This never constructs a target name from the filename; it only
            # prevents local feeder titles such as AJWD-16 inside
            # JED-CTL-AJWD-16.sln.pic.g from being mistaken for a remote station.
            source_stem = _logical_source_stem(file_path).casefold()
            station_full_key = station_full_name.casefold()
            if source_stem == station_full_key or source_stem.startswith(station_full_key + "-"):
                result.skipped_count += 1
                reason = (
                    f"站点跳转候选 {label!r} 数据库解析为本图当前变电站 {station_full_name!r}，"
                    "属于本地站/馈线标题，不创建对端变电站跳转。"
                )
                result.records.append(StationPokeRecord(
                    label_text=label,
                    station_key=station_key,
                    station_full_name=station_full_name,
                    text_id=text_id,
                    action="skipped",
                    confidence=confidence,
                    recognition_source=recognition_source,
                    reason=reason,
                ))
                continue

            target_file = f"{station_full_name}.sln.pic.g"
            result.eligible_count += 1

            if related:
                poke = _choose_primary_poke(related, text_box, station_key, text_id)
                removed = 0
                for extra in related:
                    if extra is poke:
                        continue
                    layer.remove(extra)
                    removed += 1
                result.removed_duplicate_count += removed
                changed = _ensure_station_attributes(
                    poke,
                    target_file=target_file,
                    station_key=station_key,
                    text_id=text_id,
                    text_box=text_box,
                    preserve_geometry=True,
                )
                moved = _move_poke_to_background(layer, poke)
                action = "updated" if (changed or moved or removed) else "unchanged"
                if action == "updated":
                    result.updated_count += 1
                else:
                    result.unchanged_count += 1
                if removed:
                    result.warnings.append(
                        f"站点跳转 {label!r} 发现 {removed + 1} 个相关 Poke，已删除多余 {removed} 个，仅保留 1 个。"
                    )
            else:
                poke_id = _allocate_poke_id(root, used_ids)
                poke = _new_poke(root, poke_id)
                _ensure_station_attributes(
                    poke,
                    target_file=target_file,
                    station_key=station_key,
                    text_id=text_id,
                    text_box=text_box,
                    preserve_geometry=False,
                )
                _move_poke_to_background(layer, poke)
                action = "added"
                result.added_count += 1

            result.changes.append(StationPokeChange(
                label_text=label,
                station_key=station_key,
                station_full_name=station_full_name,
                text_id=text_id,
                poke_id=(poke.get("id") or "").strip(),
                target_file=target_file,
                action=action,
                confidence=confidence,
                recognition_source=recognition_source,
                removed_duplicates=(removed if related else 0),
            ))
            if action == "added":
                reason = "未找到可复用的站点跳转 Poke，已根据结构识别结果新增并写入跳转。"
            elif action == "updated":
                reason = "已复用现有站点跳转 Poke，并更新目标/Line Color/元数据或清理重复 Poke。"
            else:
                reason = "现有站点跳转 Poke 已符合目标，无需修改。"
            if related and removed:
                reason += f" 同时删除重复 Poke {removed} 个。"
            result.records.append(StationPokeRecord(
                label_text=label,
                station_key=station_key,
                station_full_name=station_full_name,
                text_id=text_id,
                poke_id=(poke.get("id") or "").strip(),
                target_file=target_file,
                action=action,
                confidence=confidence,
                recognition_source=recognition_source,
                reason=reason,
            ))

    return result
