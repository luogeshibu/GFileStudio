from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.id_engine import direct_layers, local_name
from g_file_studio.engines.rmu_identification_engine import _valid_auto_name_text
from g_file_studio.engines.rmu_poke_engine import (
    _Box,
    _CANONICAL_POKE_ATTRS,
    _allocate_poke_id,
    _all_used_ids,
    _box,
    _move_poke_to_background,
    _number,
    build_rmu_detail_filename,
)

DEVICE_NAME_MAX_DISTANCE = 300.0
# AR/LBS/SEC device names are a separate recognition contract from RMU names.
# The customer drawing convention is strict: the name Text itself is RED and
# is placed either ABOVE or to the RIGHT of the classified device.
DEVICE_NAME_ALLOWED_DIRECTIONS = frozenset({"top", "right"})
DEVICE_NAME_EDGE_TOLERANCE = 20.0
TARGET_MARKERS = frozenset({"AR", "LBS", "SEC"})


@dataclass(frozen=True)
class ClassifiedDevice:
    marker: str
    element: ET.Element
    element_id: str
    box: _Box
    layer: ET.Element


@dataclass(frozen=True)
class DeviceNameAssignment:
    marker: str
    device_id: str
    text_id: str
    name: str
    distance: float
    direction: str
    device: ET.Element
    text: ET.Element
    layer: ET.Element


@dataclass
class ClassifiedDevicePokeRecord:
    marker: str
    device_id: str
    name: str = ""
    text_id: str = ""
    distance: float = 0.0
    poke_id: str = ""
    target_file: str = ""
    action: str = "skipped"
    reason: str = ""


@dataclass
class ClassifiedDevicePokeResult:
    file_path: Path
    device_count: int = 0
    assigned_name_count: int = 0
    eligible_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    records: list[ClassifiedDevicePokeRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _marker_key(value: object) -> str:
    return re.sub(r"[\s\-]+", "_", str(value or "").strip()).upper()


def _devref_keys(value: object) -> tuple[str, str, str]:
    raw = str(value or "").strip().lstrip("#")
    if not raw:
        return "", "", ""
    file_part, separator, element_part = raw.partition(":")
    file_key = Path(file_part.replace("\\", "/")).name.casefold()
    element_key = element_part.strip().casefold() if separator else ""
    return file_key, element_key, raw.casefold()


def _entry_values(entry: object) -> tuple[str, str, str]:
    if isinstance(entry, dict):
        return (
            str(entry.get("file_name", entry.get("name", "")) or ""),
            str(entry.get("devref", "") or ""),
            str(entry.get("classification_marker", entry.get("category_marker", "")) or ""),
        )
    if isinstance(entry, (tuple, list)) and len(entry) >= 3:
        return str(entry[0] or ""), str(entry[1] or ""), str(entry[2] or "")
    return "", "", ""


def find_classified_devices(
    root: ET.Element,
    classification_marker_entries: tuple[object, ...] | list[object],
) -> list[ClassifiedDevice]:
    marker_by_file: dict[str, str] = {}
    marker_by_devref: dict[str, str] = {}
    for entry in classification_marker_entries or ():
        file_name, devref, marker = _entry_values(entry)
        normalized = _marker_key(marker)
        if normalized not in TARGET_MARKERS:
            continue
        file_key, element_key, full_key = _devref_keys(devref)
        explicit_file = Path(file_name.replace("\\", "/")).name.casefold()
        if explicit_file:
            marker_by_file[explicit_file] = normalized
        if file_key:
            marker_by_file[file_key] = normalized
        if element_key:
            marker_by_devref[element_key] = normalized
        if full_key:
            marker_by_devref[full_key] = normalized

    result: list[ClassifiedDevice] = []
    for layer in direct_layers(root):
        for element in list(layer):
            if local_name(element.tag).casefold() in {"text", "dtext", "poke"}:
                continue
            file_key, element_key, full_key = _devref_keys(element.get("devref") or "")
            marker = (
                marker_by_devref.get(full_key)
                or marker_by_devref.get(element_key)
                or marker_by_file.get(file_key)
            )
            if marker not in TARGET_MARKERS:
                continue
            box = _box(element)
            if box is None:
                continue
            result.append(ClassifiedDevice(
                marker=marker,
                element=element,
                element_id=(element.get("id") or "").strip(),
                box=box,
                layer=layer,
            ))
    return result


def _text_to_device_distance(text_box: _Box, device_box: _Box) -> float:
    cx = text_box.center_x
    cy = text_box.center_y
    dx = max(device_box.left - cx, 0.0, cx - device_box.right)
    dy = max(device_box.top - cy, 0.0, cy - device_box.bottom)
    return math.hypot(dx, dy)


def _is_red_device_name_text(text: ET.Element) -> bool:
    """Hard color rule for AR/LBS/SEC names.

    In G files the visible text line/font color is represented by ``lc`` and
    ``lcc``.  ``fc`` is intentionally ignored because many valid red names keep
    a green fill/background value.
    """
    lcc = (text.get("lcc") or "").strip().lower()
    lc = re.sub(r"\s+", "", (text.get("lc") or "").strip()).lower()
    return lcc in {"#ff0000", "#f00"} or lc == "255,0,0"


def _device_name_direction(text_box: _Box, device_box: _Box) -> str:
    """Return ``top``/``right`` when Text is in the allowed device-name band.

    The projection tolerance prevents a remote diagonal red label from winning
    merely because it is within the 300-unit radius.  A small edge tolerance is
    retained for legacy drawings where text and device boxes touch/overlap by a
    few units.
    """
    base = max(device_box.width, device_box.height, 1.0)
    projection_tolerance = max(60.0, min(140.0, base * 1.5))
    edge = DEVICE_NAME_EDGE_TOLERANCE

    top_gap = device_box.top - text_box.bottom
    if (
        -edge <= top_gap <= DEVICE_NAME_MAX_DISTANCE
        and text_box.center_y <= device_box.top + edge
        and device_box.left - projection_tolerance <= text_box.center_x <= device_box.right + projection_tolerance
    ):
        return "top"

    right_gap = text_box.left - device_box.right
    if (
        -edge <= right_gap <= DEVICE_NAME_MAX_DISTANCE
        and text_box.center_x >= device_box.right - edge
        and device_box.top - projection_tolerance <= text_box.center_y <= device_box.bottom + projection_tolerance
    ):
        return "right"

    return ""


def assign_device_names(devices: list[ClassifiedDevice]) -> list[DeviceNameAssignment]:
    """Assign at most one Text instance to each device, globally one-to-one.

    Text ownership uses XML text-id when available, otherwise object identity.
    Therefore two distinct Text elements may carry the same rendered ``ts`` value
    and still be assigned independently, exactly as long as they have different
    Text IDs/instances.
    """
    candidates: list[tuple[float, str, str, str, int, ClassifiedDevice, ET.Element]] = []
    for device_index, device in enumerate(devices):
        for text in list(device.layer):
            if local_name(text.tag) != "Text" or not _valid_auto_name_text(text):
                continue
            text_box = _box(text)
            if text_box is None:
                continue
            # AR/LBS/SEC name recognition intentionally does NOT reuse the RMU
            # name-style heuristic.  The operator-defined contract is: red Text,
            # above/right only, within 300, globally one-to-one.
            if not _is_red_device_name_text(text):
                continue
            direction = _device_name_direction(text_box, device.box)
            if direction not in DEVICE_NAME_ALLOWED_DIRECTIONS:
                continue
            distance = _text_to_device_distance(text_box, device.box)
            if distance > DEVICE_NAME_MAX_DISTANCE:
                continue
            candidates.append((
                distance,
                direction,
                device.marker,
                device.element_id or f"__device_{device_index}",
                device_index,
                device,
                text,
            ))

    direction_rank = {"top": 0, "right": 1}
    candidates.sort(
        key=lambda row: (
            row[0], direction_rank.get(row[1], 9), row[2], row[3],
            (row[6].get("id") or ""), id(row[6]),
        )
    )
    used_devices: set[int] = set()
    used_text_keys: set[str] = set()
    assignments: list[DeviceNameAssignment] = []
    for distance, direction, _marker, _device_key, device_index, device, text in candidates:
        text_id = (text.get("id") or "").strip()
        text_key = text_id or f"__text_object_{id(text)}"
        if device_index in used_devices or text_key in used_text_keys:
            continue
        name = (text.get("ts") or "").strip()
        if not name:
            continue
        used_devices.add(device_index)
        used_text_keys.add(text_key)
        assignments.append(DeviceNameAssignment(
            marker=device.marker,
            device_id=device.element_id,
            text_id=text_id,
            name=name,
            distance=distance,
            direction=direction,
            device=device.element,
            text=text,
            layer=device.layer,
        ))
    return assignments


def _related_pokes(assignment: DeviceNameAssignment) -> list[ET.Element]:
    name_box = _box(assignment.text)
    if name_box is None:
        return []
    result: list[ET.Element] = []
    for element in list(assignment.layer):
        if local_name(element.tag) != "poke":
            continue
        # Never take ownership of Pokes created by another processing branch.
        # Geometry may overlap in dense drawings, but RMU/station/device Pokes are
        # independent objects and must not convert one another.
        if (element.get("gfs_rmu_poke") or "") == "1" or (element.get("gfs_station_poke") or "") == "1":
            continue
        if assignment.text_id and (element.get("gfs_device_text_id") or "") == assignment.text_id:
            result.append(element)
            continue
        if assignment.device_id and (element.get("gfs_device_element_id") or "") == assignment.device_id:
            result.append(element)
            continue
        box = _box(element)
        if box is None:
            continue
        if not (box.right < name_box.left or box.left > name_box.right or box.bottom < name_box.top or box.top > name_box.bottom):
            result.append(element)
    # identity de-dup, XML order preserved
    seen: set[int] = set()
    unique: list[ET.Element] = []
    for item in result:
        if id(item) not in seen:
            seen.add(id(item))
            unique.append(item)
    return unique


def _ensure_device_poke(
    poke: ET.Element,
    *,
    assignment: DeviceNameAssignment,
    target_file: str,
    box: _Box,
) -> bool:
    old = dict(poke.attrib)
    poke_id = (poke.get("id") or "").strip()
    desired = dict(_CANONICAL_POKE_ATTRS)
    desired.update({
        "id": poke_id,
        "ahref": target_file,
        "x": _number(box.left),
        "y": _number(box.top),
        "w": _number(box.width),
        "h": _number(box.height),
        "gfs_device_poke": "1",
        "gfs_device_marker": assignment.marker,
        "gfs_device_name": assignment.name,
        "gfs_device_text_id": assignment.text_id,
        "gfs_device_element_id": assignment.device_id,
    })
    if old == desired:
        return False
    poke.attrib.clear()
    poke.attrib.update(desired)
    return True


def apply_classified_device_pokes(
    tree: ET.ElementTree,
    file_path: Path,
    *,
    classification_marker_entries: tuple[object, ...] | list[object],
    database_prefixes: dict[str, str] | None = None,
    database_resolution_errors: dict[str, str] | None = None,
) -> ClassifiedDevicePokeResult:
    result = ClassifiedDevicePokeResult(file_path=file_path)
    root = tree.getroot()
    devices = find_classified_devices(root, classification_marker_entries)
    result.device_count = len(devices)
    if not devices:
        return result

    assignments = assign_device_names(devices)
    result.assigned_name_count = len(assignments)
    assigned_device_objects = {id(item.device) for item in assignments}
    for device in devices:
        if id(device.element) not in assigned_device_objects:
            result.skipped_count += 1
            reason = (
                f"{device.marker} 设备 {device.element_id or '<无ID>'} 在 300 范围内未找到/未分配到"
                "符合规则的名称 Text（必须红色，且位于设备上方或右侧）。"
            )
            result.records.append(ClassifiedDevicePokeRecord(
                marker=device.marker, device_id=device.element_id, action="skipped", reason=reason
            ))

    prefixes = {str(k).strip().casefold(): str(v).strip() for k, v in (database_prefixes or {}).items()}
    errors = {str(k).strip().casefold(): str(v).strip() for k, v in (database_resolution_errors or {}).items()}
    used_ids = _all_used_ids(root)

    for assignment in assignments:
        name_box = _box(assignment.text)
        if name_box is None:
            result.skipped_count += 1
            continue
        key = assignment.name.casefold()
        if key in errors:
            result.skipped_count += 1
            reason = f"{assignment.marker} {assignment.name!r}：{errors[key]}"
            result.records.append(ClassifiedDevicePokeRecord(
                marker=assignment.marker, device_id=assignment.device_id,
                name=assignment.name, text_id=assignment.text_id, distance=assignment.distance,
                action="skipped", reason=reason,
            ))
            continue
        prefix = prefixes.get(key, "")
        if not prefix:
            result.skipped_count += 1
            reason = f"数据库未根据设备名称 {assignment.name!r} 解析到所属馈线完整业务名。"
            result.records.append(ClassifiedDevicePokeRecord(
                marker=assignment.marker, device_id=assignment.device_id,
                name=assignment.name, text_id=assignment.text_id, distance=assignment.distance,
                action="skipped", reason=reason,
            ))
            continue
        try:
            target_file = build_rmu_detail_filename(
                file_path, prefix, assignment.name,
                naming_mode="database_prefix", naming_rule=prefix,
            )
        except ValueError as exc:
            result.skipped_count += 1
            result.records.append(ClassifiedDevicePokeRecord(
                marker=assignment.marker, device_id=assignment.device_id,
                name=assignment.name, text_id=assignment.text_id, distance=assignment.distance,
                action="skipped", reason=str(exc),
            ))
            continue

        related = _related_pokes(assignment)
        if related:
            poke = related[0]
            removed = 0
            for extra in related[1:]:
                assignment.layer.remove(extra)
                removed += 1
            changed = _ensure_device_poke(poke, assignment=assignment, target_file=target_file, box=name_box)
            moved = _move_poke_to_background(assignment.layer, poke)
            action = "updated" if changed or moved or removed else "unchanged"
            if action == "updated":
                result.updated_count += 1
            else:
                result.unchanged_count += 1
        else:
            poke_id = _allocate_poke_id(root, used_ids)
            poke = ET.Element("poke", dict(_CANONICAL_POKE_ATTRS))
            poke.set("id", poke_id)
            _ensure_device_poke(poke, assignment=assignment, target_file=target_file, box=name_box)
            _move_poke_to_background(assignment.layer, poke)
            action = "added"
            result.added_count += 1

        result.eligible_count += 1
        result.records.append(ClassifiedDevicePokeRecord(
            marker=assignment.marker,
            device_id=assignment.device_id,
            name=assignment.name,
            text_id=assignment.text_id,
            distance=assignment.distance,
            poke_id=(poke.get("id") or "").strip(),
            target_file=target_file,
            action=action,
            reason=(
                f"{assignment.marker} 图元按名称 Text ID={assignment.text_id or '<无ID>'} 分配；"
                f"名称为红色且位于设备{('上方' if assignment.direction == 'top' else '右侧')}，"
                f"距离 {assignment.distance:.1f}（≤300）；后续数据库与目标文件逻辑沿用原设备明细规则。"
            ),
        ))
    return result
