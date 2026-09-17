from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.standard_connection_cleanup import _authoritative_pin_points


_LINE_TAGS = {"ConnectLine", "FeedLine", "BusDis", "Bus", "ACLine", "line"}
_POINT_RE = re.compile(
    r"(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*"
    r"(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
)
_NON_OBSTACLE_TAGS = _LINE_TAGS | {
    "Text", "DText", "Status", "poke", "rect", "ellipse", "image", "Layer",
    "Merge", "G", "Theme",
}


@dataclass(frozen=True)
class OrthogonalizationIssue:
    element_id: str
    element_type: str
    reason: str


@dataclass(frozen=True)
class _DeviceConnection:
    line: ET.Element
    endpoint: int
    pin: int | None
    point: tuple[float, float]


@dataclass
class OrthogonalizationResult:
    inspected_lines: int = 0
    changed_lines: int = 0
    changed_segments: int = 0
    aligned_devices: int = 0
    aligned_lines: int = 0
    connection_aligned_lines: int = 0
    rebuilt_lines: int = 0
    skipped_lines: int = 0
    changed_line_ids: list[str] = field(default_factory=list)
    aligned_device_ids: list[str] = field(default_factory=list)
    rebuilt_line_ids: list[str] = field(default_factory=list)
    issues: list[OrthogonalizationIssue] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.changed_lines
            or self.aligned_devices
            or self.aligned_lines
            or self.rebuilt_lines
        )


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format(value: float) -> str:
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _points(element: ET.Element) -> list[tuple[float, float]] | None:
    raw = element.get("d") or ""
    matches = list(_POINT_RE.finditer(raw))
    if re.search(r"[^\s;]", _POINT_RE.sub("", raw)):
        # Do not rewrite an unfamiliar path-command dialect by accident.
        return None
    points = [(float(match.group(1)), float(match.group(2))) for match in matches]
    if len(points) < 2:
        return None
    return points


def _referenced_ids(element: ET.Element) -> set[str]:
    result: set[str] = set()
    for key in ("link", "node_area"):
        for token in (element.get(key) or "").split(";"):
            parts = [part.strip() for part in token.split(",")]
            if len(parts) >= 3 and parts[2]:
                result.add(parts[2])
    return result


def _endpoint_references(element: ET.Element) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {0: set(), 1: set()}
    for key in ("link", "node_area"):
        for token in (element.get(key) or "").split(";"):
            parts = [part.strip() for part in token.split(",")]
            if len(parts) < 3 or not parts[2]:
                continue
            try:
                endpoint = int(parts[0])
            except ValueError:
                continue
            if endpoint in result:
                result[endpoint].add(parts[2])
    return result


def _point_to_box_distance(
    point: tuple[float, float],
    box: tuple[float, float, float, float],
) -> float:
    x, y = point
    left, top, right, bottom = box
    dx = max(left - x, 0.0, x - right)
    dy = max(top - y, 0.0, y - bottom)
    return math.hypot(dx, dy)


def _nearest_box_boundary(
    point: tuple[float, float],
    box: tuple[float, float, float, float],
) -> tuple[tuple[float, float], float]:
    x, y = point
    left, top, right, bottom = box
    candidates = [
        (max(left, min(right, x)), top),
        (max(left, min(right, x)), bottom),
        (left, max(top, min(bottom, y))),
        (right, max(top, min(bottom, y))),
    ]
    selected = min(candidates, key=lambda candidate: math.hypot(candidate[0] - x, candidate[1] - y))
    return selected, math.hypot(selected[0] - x, selected[1] - y)


def _device_elements(elements: list[ET.Element]) -> list[ET.Element]:
    return [
        element
        for element in elements
        if local_name(element.tag) not in _NON_OBSTACLE_TAGS
        and (element.get("devref") or "").strip()
        and _box(element) is not None
    ]


def _device_connections(
    elements: list[ET.Element],
    line_elements: list[ET.Element],
) -> dict[str, list[_DeviceConnection]]:
    """Resolve actual line endpoints attached to devices via node_area/link."""
    device_ids = {
        (element.get("id") or "").strip()
        for element in _device_elements(elements)
        if (element.get("id") or "").strip()
    }
    result: dict[str, list[_DeviceConnection]] = {}
    for line in line_elements:
        points = _points(line)
        if points is None:
            continue
        seen: set[tuple[str, int, int | None]] = set()
        # Older G files put the authoritative endpoint in link, newer files may
        # put it in node_area, and migrated files can contain both.  Merge both
        # attributes instead of treating them as alternatives.  The same token
        # in both attributes is deduplicated while different pins are retained.
        for key_name in ("link", "node_area"):
            for token in (line.get(key_name) or "").split(";"):
                parts = [part.strip() for part in token.split(",")]
                if len(parts) < 3 or parts[2] not in device_ids:
                    continue
                try:
                    endpoint = int(parts[0])
                except ValueError:
                    continue
                if endpoint not in (0, 1):
                    continue
                pin: int | None
                try:
                    pin = int(parts[1])
                except (ValueError, IndexError):
                    pin = None
                key = (parts[2], endpoint, pin)
                if key in seen:
                    continue
                seen.add(key)
                point = points[0] if endpoint == 0 else points[-1]
                result.setdefault(parts[2], []).append(
                    _DeviceConnection(line=line, endpoint=endpoint, pin=pin, point=point)
                )
    return result


def _standard_pin_for_connection(
    device: ET.Element,
    connection: _DeviceConnection,
    geometry_templates: dict[str, list[dict[str, object]]] | None,
) -> tuple[float, float] | None:
    """Return the ACTIVE/GLOBAL standard pin for a topology connection."""
    if not geometry_templates:
        return None
    if connection.pin is None:
        return None
    pin_points = _authoritative_pin_points(device, geometry_templates)
    for pin_index, point in pin_points:
        if pin_index == connection.pin:
            return point
    return None


def _connection_is_trusted(
    device: ET.Element,
    connection: _DeviceConnection,
    *,
    endpoint_tolerance: float,
    geometry_templates: dict[str, list[dict[str, object]]] | None,
) -> bool:
    """Require explicit standard-pin proximity when a standard is available."""
    if geometry_templates is None:
        return True
    expected = _standard_pin_for_connection(device, connection, geometry_templates)
    return expected is not None and math.hypot(
        connection.point[0] - expected[0], connection.point[1] - expected[1]
    ) <= endpoint_tolerance


def _shift_device_and_connections(
    device: ET.Element,
    delta: tuple[float, float],
    connections: list[_DeviceConnection],
) -> bool:
    """Move a device and every connected line endpoint by the same vector."""
    dx, dy = delta
    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return False
    x = _number(device.get("x"))
    y = _number(device.get("y"))
    if x is None or y is None:
        return False
    device.set("x", _format(x + dx))
    device.set("y", _format(y + dy))
    seen: set[tuple[int, int]] = set()
    changed = False
    for connection in connections:
        key = (id(connection.line), connection.endpoint)
        if key in seen:
            continue
        seen.add(key)
        changed = _move_line_endpoint(connection.line, connection.endpoint, delta) or changed
    return changed


def _local_similar_device_groups(
    devices: list[ET.Element],
    connections: dict[str, list[_DeviceConnection]],
    *,
    tolerance: float,
) -> list[list[ET.Element]]:
    """Split one standard class into nearby, unambiguous rows or columns."""
    anchors: dict[int, tuple[float, float]] = {}
    for device in devices:
        device_id = (device.get("id") or "").strip()
        points = [item.point for item in connections.get(device_id, [])]
        if not points:
            continue
        anchors[id(device)] = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
    if len(anchors) < 2:
        return []

    # A class can appear in many independent parts of a large drawing.  The
    # gap is derived from the symbol size, so nearby repeated bays form a
    # group while distant instances of the same standard do not get pulled
    # into one global row/column.
    dimensions = [
        max((_box(device)[2] - _box(device)[0]), (_box(device)[3] - _box(device)[1]))
        for device in devices
        if _box(device) is not None
    ]
    local_gap = max(tolerance * 10.0, (max(dimensions) if dimensions else tolerance) * 6.0)
    groups: list[list[ET.Element]] = []
    for axis in ("x", "y"):
        eligible = [device for device in devices if id(device) in anchors]
        adjacency: dict[int, set[int]] = {id(device): set() for device in eligible}
        for index, first in enumerate(eligible):
            first_anchor = anchors[id(first)]
            for second in eligible[index + 1:]:
                second_anchor = anchors[id(second)]
                aligned_delta = abs(first_anchor[0] - second_anchor[0]) if axis == "x" else abs(first_anchor[1] - second_anchor[1])
                along_delta = abs(first_anchor[1] - second_anchor[1]) if axis == "x" else abs(first_anchor[0] - second_anchor[0])
                if aligned_delta <= tolerance and tolerance < along_delta <= local_gap:
                    adjacency[id(first)].add(id(second))
                    adjacency[id(second)].add(id(first))

        by_id = {id(device): device for device in eligible}
        visited: set[int] = set()
        for device in eligible:
            device_key = id(device)
            if device_key in visited or not adjacency[device_key]:
                continue
            stack = [device_key]
            visited.add(device_key)
            component: list[ET.Element] = []
            while stack:
                current = stack.pop()
                component.append(by_id[current])
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            xs = [anchors[id(item)][0] for item in component]
            ys = [anchors[id(item)][1] for item in component]
            if (
                len(component) >= 2
                and ((axis == "x" and max(xs) - min(xs) <= tolerance)
                     or (axis == "y" and max(ys) - min(ys) <= tolerance))
            ):
                groups.append(component)
    return groups


def _device_shift_is_safe(
    device: ET.Element,
    delta: tuple[float, float],
    devices: list[ET.Element],
) -> bool:
    box = _box(device)
    if box is None:
        return False
    shifted = (box[0] + delta[0], box[1] + delta[1], box[2] + delta[0], box[3] + delta[1])
    for other in devices:
        if other is device:
            continue
        other_box = _box(other)
        if other_box is not None and _boxes_overlap(shifted, other_box):
            return False
    return True


def _build_obstacles(
    elements: list[ET.Element],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    return [
        ((element.get("id") or "").strip(), box)
        for element in elements
        if local_name(element.tag) not in _NON_OBSTACLE_TAGS
        and (box := _box(element)) is not None
    ]


def _line_hits_obstacles(
    points: list[tuple[float, float]],
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
    excluded_ids: set[str],
) -> bool:
    return any(
        _segment_hits_box(start, end, box)
        for start, end in zip(points, points[1:])
        for element_id, box in obstacles
        if element_id not in excluded_ids
    )


def _shifted_points(
    line: ET.Element,
    endpoint_index: int,
    delta: tuple[float, float],
) -> list[tuple[float, float]] | None:
    points = _points(line)
    if points is None:
        return None
    point_index = 0 if endpoint_index == 0 else len(points) - 1
    points[point_index] = (
        points[point_index][0] + delta[0],
        points[point_index][1] + delta[1],
    )
    return points


def _boxes_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    *,
    clearance: float = 0.5,
) -> bool:
    return (
        max(first[0], second[0]) < min(first[2], second[2]) - clearance
        and max(first[1], second[1]) < min(first[3], second[3]) - clearance
    )


def _move_line_endpoint(
    line: ET.Element,
    endpoint_index: int,
    delta: tuple[float, float],
) -> bool:
    points = _points(line)
    if points is None:
        return False
    point_index = 0 if endpoint_index == 0 else len(points) - 1
    old = points[point_index]
    moved = (old[0] + delta[0], old[1] + delta[1])
    if moved == old:
        return False
    points[point_index] = moved
    _rewrite_points(line, points)
    return True


def _align_similar_devices(
    elements: list[ET.Element],
    line_elements: list[ET.Element],
    result: OrthogonalizationResult,
    *,
    tolerance: float,
    connections: dict[str, list[_DeviceConnection]],
    endpoint_tolerance: float,
    geometry_templates: dict[str, list[dict[str, object]]] | None,
) -> None:
    """Snap repeated same-standard devices by their real connected pins."""
    devices = _device_elements(elements)
    by_key: dict[tuple[str, str, float, float, str], list[ET.Element]] = {}
    for device in devices:
        box = _box(device)
        if box is None:
            continue
        by_key.setdefault(
            (
                local_name(device.tag),
                (device.get("devref") or "").strip(),
                round(box[2] - box[0], 3),
                round(box[3] - box[1], 3),
                (device.get("rotate") or "").strip(),
            ),
            [],
        ).append(device)

    lines_by_device: dict[str, list[ET.Element]] = {}
    for line in line_elements:
        refs = _referenced_ids(line)
        for device_id in refs:
            lines_by_device.setdefault(device_id, []).append(line)

    local_groups: list[list[ET.Element]] = []
    for group in by_key.values():
        local_groups.extend(
            _local_similar_device_groups(group, connections, tolerance=tolerance)
        )

    # Resolve larger local arrays first.  A normal feeder bay is either a row
    # or a column; this ordering also makes the result deterministic if a
    # drawing contains an accidental crossing of two candidate groups.
    claimed_device_ids: set[str] = set()
    for group in sorted(local_groups, key=lambda items: (-len(items), (items[0].get("id") or ""))):
        group_ids = {
            (device.get("id") or "").strip()
            for device in group
            if (device.get("id") or "").strip()
        }
        # A drawing can contain a crossing row and column of the same symbol
        # class.  Do not move an instance twice using stale anchor coordinates;
        # the larger local array gets first claim and the other candidate is
        # left for the obstacle-aware line pass.
        if group_ids & claimed_device_ids:
            continue
        boxes = {id(device): _box(device) for device in group}
        anchors: dict[int, tuple[float, float]] = {}
        for device in group:
            device_id = (device.get("id") or "").strip()
            device_connections = connections.get(device_id, [])
            if any(
                not _connection_is_trusted(
                    device,
                    connection,
                    endpoint_tolerance=endpoint_tolerance,
                    geometry_templates=geometry_templates,
                )
                for connection in device_connections
            ):
                break
            points = [item.point for item in device_connections]
            if not points:
                break
            anchors[id(device)] = (
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            )
        if len(anchors) != len(group):
            continue
        x_values = [anchors[id(device)][0] for device in group]
        y_values = [anchors[id(device)][1] for device in group]
        x_spread = max(x_values) - min(x_values)
        y_spread = max(y_values) - min(y_values)
        if x_spread <= tolerance and y_spread > tolerance:
            axis = "x"
            target = sum(x_values) / len(x_values)
        elif y_spread <= tolerance and x_spread > tolerance:
            axis = "y"
            target = sum(y_values) / len(y_values)
        else:
            # Already coincident in both axes, or not a clear row/column.
            continue

        plans: list[tuple[ET.Element, float, float]] = []
        line_deltas: dict[int, list[tuple[ET.Element, int, tuple[float, float]]]] = {}
        safe = True
        for device in group:
            device_id = (device.get("id") or "").strip()
            if not device_id or not lines_by_device.get(device_id):
                safe = False
                break
            current_x, current_y = anchors[id(device)]
            delta = (target - current_x, 0.0) if axis == "x" else (0.0, target - current_y)
            if abs(delta[0]) <= 0.01 and abs(delta[1]) <= 0.01:
                continue
            for line in lines_by_device[device_id]:
                endpoint_refs = _endpoint_references(line)
                candidates = [
                    endpoint
                    for endpoint, refs in endpoint_refs.items()
                    if device_id in refs and len(refs) == 1
                ]
                if len(candidates) != 1:
                    safe = False
                    break
                line_deltas.setdefault(id(line), []).append((line, candidates[0], delta))
            if not safe:
                break
            plans.append((device, delta[0], delta[1]))
        if not safe or not plans:
            continue

        planned_boxes: dict[int, tuple[float, float, float, float]] = {}
        for device, dx, dy in plans:
            old_box = boxes[id(device)]
            if old_box is None:
                safe = False
                break
            planned_boxes[id(device)] = (
                old_box[0] + dx, old_box[1] + dy,
                old_box[2] + dx, old_box[3] + dy,
            )
        if not safe:
            continue
        planned_values = list(planned_boxes.values())
        if any(
            _boxes_overlap(first, second)
            for index, first in enumerate(planned_values)
            for second in planned_values[index + 1:]
        ):
            result.issues.append(OrthogonalizationIssue(
                element_id=", ".join((device.get("id") or "").strip() for device in group),
                element_type=local_name(group[0].tag),
                reason="同类设备对齐后会互相重叠，保守跳过该组。",
            ))
            continue
        for device in devices:
            if id(device) in planned_boxes:
                continue
            other_box = _box(device)
            if other_box is None:
                continue
            if any(_boxes_overlap(new_box, other_box) for new_box in planned_boxes.values()):
                safe = False
                break
        if not safe:
            result.issues.append(OrthogonalizationIssue(
                element_id=", ".join((device.get("id") or "").strip() for device in group),
                element_type=local_name(group[0].tag),
                reason="同类设备对齐后会与其他设备重叠，保守跳过该组。",
            ))
            continue

        for device, dx, dy in plans:
            device.set("x", _format((_number(device.get("x")) or 0.0) + dx))
            device.set("y", _format((_number(device.get("y")) or 0.0) + dy))
            device_id = (device.get("id") or "").strip()
            result.aligned_devices += 1
            if device_id:
                result.aligned_device_ids.append(device_id)
        for updates in line_deltas.values():
            changed_line = False
            for line, endpoint, delta in updates:
                changed_line = _move_line_endpoint(line, endpoint, delta) or changed_line
            if changed_line:
                result.aligned_lines += 1
        claimed_device_ids.update(group_ids)


def _align_mixed_device_connection_points(
    elements: list[ET.Element],
    line_elements: list[ET.Element],
    result: OrthogonalizationResult,
    *,
    endpoint_tolerance: float,
    axis_tolerance: float,
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
    geometry_templates: dict[str, list[dict[str, object]]] | None,
    max_device_shift: float = 160.0,
) -> None:
    """Align explicit endpoints for unlike devices without moving network hubs.

    A diagonal two-device connection is made straight by moving only a leaf
    device (degree one) along the minor axis.  Multi-connected devices are not
    moved by this fallback: their line is handled by the obstacle-aware elbow
    pass instead.  This keeps a common junction stable while still correcting
    the common end-device case shown in field drawings.
    """
    devices = {
        (element.get("id") or "").strip(): element
        for element in _device_elements(elements)
        if (element.get("id") or "").strip()
    }
    connections = _device_connections(elements, line_elements)
    degree = {device_id: len(items) for device_id, items in connections.items()}
    moved_devices: set[str] = set()

    for line in line_elements:
        points = _points(line)
        if points is None or len(points) != 2:
            continue
        endpoint_refs = _endpoint_references(line)
        if any(len(endpoint_refs[index]) != 1 for index in (0, 1)):
            continue
        device_ids = [next(iter(endpoint_refs[index])) for index in (0, 1)]
        if device_ids[0] == device_ids[1] or any(device_id not in devices for device_id in device_ids):
            continue
        if device_ids[0] in moved_devices or device_ids[1] in moved_devices:
            continue
        if abs(points[0][0] - points[1][0]) <= axis_tolerance or abs(points[0][1] - points[1][1]) <= axis_tolerance:
            continue

        endpoint_distances = []
        for index, device_id in enumerate(device_ids):
            box = _box(devices[device_id])
            if box is None:
                endpoint_distances.append(float("inf"))
            else:
                endpoint_distances.append(_point_to_box_distance(points[index], box))
        if any(distance > endpoint_tolerance for distance in endpoint_distances):
            continue

        if geometry_templates is not None:
            trusted = True
            for index, device_id in enumerate(device_ids):
                matching = [
                    connection
                    for connection in connections.get(device_id, [])
                    if connection.line is line and connection.endpoint == index
                ]
                device = devices[device_id]
                if len(matching) != 1 or not _connection_is_trusted(
                    device,
                    matching[0],
                    endpoint_tolerance=endpoint_tolerance,
                    geometry_templates=geometry_templates,
                ):
                    trusted = False
                    break
            if not trusted:
                continue

        # Prefer moving a true leaf.  If both are leaves, move the second
        # endpoint deterministically; if neither is a leaf, preserve the hubs.
        candidates = sorted(
            (0, 1),
            key=lambda index: (degree.get(device_ids[index], 99), index),
        )
        selected_index = candidates[0]
        other_index = 1 - selected_index
        if degree.get(device_ids[selected_index], 99) > 1:
            continue

        selected = points[selected_index]
        other = points[other_index]
        if abs(other[0] - selected[0]) >= abs(other[1] - selected[1]):
            delta = (0.0, other[1] - selected[1])
        else:
            delta = (other[0] - selected[0], 0.0)
        if max(abs(delta[0]), abs(delta[1])) <= axis_tolerance:
            continue
        if max(abs(delta[0]), abs(delta[1])) > max_device_shift:
            result.issues.append(OrthogonalizationIssue(
                element_id=(line.get("id") or "").strip(),
                element_type=local_name(line.tag),
                reason="不同类设备连接点偏差过大，未移动设备，保留线路正交化处理。",
            ))
            continue

        device_id = device_ids[selected_index]
        device = devices[device_id]
        if not _device_shift_is_safe(device, delta, list(devices.values())):
            result.issues.append(OrthogonalizationIssue(
                element_id=(line.get("id") or "").strip(),
                element_type=local_name(line.tag),
                reason="不同类设备按连接点对齐会与其他设备重叠，未移动设备。",
            ))
            continue
        for connection in connections.get(device_id, []):
            shifted = _shifted_points(connection.line, connection.endpoint, delta)
            if shifted is None:
                continue
            if _line_hits_obstacles(
                shifted,
                obstacles,
                _referenced_ids(connection.line),
            ):
                result.issues.append(OrthogonalizationIssue(
                    element_id=(line.get("id") or "").strip(),
                    element_type=local_name(line.tag),
                    reason="不同类设备按连接点对齐后线路会穿过其他设备，保守不移动。",
                ))
                break
        else:
            if not _shift_device_and_connections(device, delta, connections[device_id]):
                continue
            moved_devices.add(device_id)
            result.aligned_devices += 1
            result.aligned_device_ids.append(device_id)
            result.connection_aligned_lines += 1
            result.aligned_lines += 1
            continue


def _rebuild_confirmed_lines(
    elements: list[ET.Element],
    line_elements: list[ET.Element],
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
    result: OrthogonalizationResult,
    *,
    endpoint_tolerance: float,
    axis_tolerance: float,
    geometry_templates: dict[str, list[dict[str, object]]] | None,
) -> set[int]:
    """Re-route two-ended lines only when both endpoint device identities are explicit."""
    protected_lines: set[int] = set()
    devices = {
        (element.get("id") or "").strip(): element
        for element in _device_elements(elements)
        if (element.get("id") or "").strip()
    }
    for line in line_elements:
        original = _points(line)
        if original is None or len(original) != 2:
            continue
        endpoint_refs = _endpoint_references(line)
        if any(len(endpoint_refs[index]) != 1 for index in (0, 1)):
            continue
        device_ids = [next(iter(endpoint_refs[index])) for index in (0, 1)]
        if device_ids[0] == device_ids[1] or any(device_id not in devices for device_id in device_ids):
            continue
        targets: list[tuple[float, float]] = []
        safe = True
        for index, device_id in enumerate(device_ids):
            box = _box(devices[device_id])
            if box is None:
                safe = False
                break
            device = devices[device_id]
            endpoint_connection = [
                connection
                for connection in _device_connections(elements, [line]).get(device_id, [])
                if connection.endpoint == index
            ]
            target: tuple[float, float]
            if geometry_templates is not None:
                if len(endpoint_connection) != 1:
                    safe = False
                    break
                standard_pin = _standard_pin_for_connection(
                    device, endpoint_connection[0], geometry_templates
                )
                if standard_pin is None:
                    safe = False
                    break
                distance = math.hypot(
                    original[index][0] - standard_pin[0],
                    original[index][1] - standard_pin[1],
                )
                target = standard_pin
            else:
                target, distance = _nearest_box_boundary(original[index], box)
            if distance > endpoint_tolerance:
                safe = False
                break
            targets.append(target)
        if not safe:
            continue
        usable_obstacles = [item for item in obstacles if item[0] not in set(device_ids)]
        route = _orthogonal_route(
            targets[0], targets[1], usable_obstacles, axis_tolerance=axis_tolerance
        )
        if route is None:
            protected_lines.add(id(line))
            result.skipped_lines += 1
            result.issues.append(OrthogonalizationIssue(
                element_id=(line.get("id") or "").strip(),
                element_type=local_name(line.tag),
                reason="两端设备身份明确，但重画线路会穿过其他设备，保守保留原线路。",
            ))
            continue
        route_points, _added = route
        if route_points == original:
            continue
        _rewrite_points(line, route_points)
        result.rebuilt_lines += 1
        line_id = (line.get("id") or "").strip()
        if line_id:
            result.rebuilt_line_ids.append(line_id)
    return protected_lines


def _box(element: ET.Element) -> tuple[float, float, float, float] | None:
    x = _number(element.get("x"))
    y = _number(element.get("y"))
    width = _number(element.get("w"))
    height = _number(element.get("h"))
    if None in (x, y, width, height) or width <= 0 or height <= 0:
        return None
    assert x is not None and y is not None and width is not None and height is not None
    return x, y, x + width, y + height


def _segment_hits_box(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
    *,
    clearance: float = 0.5,
) -> bool:
    """Return whether a segment crosses the interior or clearance of a box."""
    x1, y1 = start
    x2, y2 = end
    left, top, right, bottom = box
    left -= clearance
    top -= clearance
    right += clearance
    bottom += clearance
    if abs(y1 - y2) <= 1e-9:
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
    if abs(x1 - x2) <= 1e-9:
        return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
    # Alignment can temporarily produce a diagonal segment on a multi-connected
    # device.  It still must be checked against obstacles; returning False here
    # would make the line-collision guard ineffective for exactly that case.
    dx = x2 - x1
    dy = y2 - y1
    t_min, t_max = 0.0, 1.0
    for coordinate, delta, lower, upper in (
        (x1, dx, left, right),
        (y1, dy, top, bottom),
    ):
        if abs(delta) <= 1e-12:
            if lower <= coordinate <= upper:
                continue
            return False
        entering = (lower - coordinate) / delta
        leaving = (upper - coordinate) / delta
        if entering > leaving:
            entering, leaving = leaving, entering
        t_min = max(t_min, entering)
        t_max = min(t_max, leaving)
        if t_min > t_max:
            return False
    return t_min < t_max and t_max >= 0.0 and t_min <= 1.0


def _route_hits_obstacle(
    start: tuple[float, float],
    elbow: tuple[float, float],
    end: tuple[float, float],
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
) -> bool:
    return any(
        _segment_hits_box(a, b, box)
        for a, b in ((start, elbow), (elbow, end))
        for _element_id, box in obstacles
    )


def _orthogonal_route(
    start: tuple[float, float],
    end: tuple[float, float],
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
    *,
    axis_tolerance: float,
) -> tuple[list[tuple[float, float]], int] | None:
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    if dy <= axis_tolerance or dx <= axis_tolerance:
        return [start, end], 0

    # Keep the dominant direction first.  The alternative is retained for cases
    # where the first elbow would cross a known device body.
    elbows = (
        [(end[0], start[1]), (start[0], end[1])]
        if dx >= dy
        else [(start[0], end[1]), (end[0], start[1])]
    )
    for elbow in elbows:
        if not _route_hits_obstacle(start, elbow, end, obstacles):
            return [start, elbow, end], 1
    return None


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if result and math.hypot(result[-1][0] - point[0], result[-1][1] - point[1]) <= 1e-9:
            continue
        result.append(point)
        while len(result) >= 3:
            a, b, c = result[-3:]
            if (abs(a[0] - b[0]) <= 1e-9 and abs(b[0] - c[0]) <= 1e-9) or (
                abs(a[1] - b[1]) <= 1e-9 and abs(b[1] - c[1]) <= 1e-9
            ):
                result.pop(-2)
            else:
                break
    return result


def _rewrite_points(element: ET.Element, points: list[tuple[float, float]]) -> None:
    element.set("d", " ".join(f"{_format(x)},{_format(y)}" for x, y in points))
    # Some Bus/BusDis writers also duplicate the endpoints in x1/y1/x2/y2.
    first_x, first_y = points[0]
    last_x, last_y = points[-1]
    for key, value in (
        ("x1", first_x), ("y1", first_y), ("x2", last_x), ("y2", last_y),
    ):
        if element.get(key) is not None:
            element.set(key, _format(value))


def _snapshot_geometry(
    elements: list[ET.Element],
    line_elements: list[ET.Element],
) -> dict[int, tuple[ET.Element, dict[str, str | None]]]:
    snapshot: dict[int, tuple[ET.Element, dict[str, str | None]]] = {}
    for element in _device_elements(elements):
        snapshot[id(element)] = (element, {key: element.get(key) for key in ("x", "y")})
    for line in line_elements:
        snapshot[id(line)] = (
            line,
            {key: line.get(key) for key in ("d", "x1", "y1", "x2", "y2")},
        )
    return snapshot


def _restore_geometry(
    snapshot: dict[int, tuple[ET.Element, dict[str, str | None]]],
) -> None:
    for element, attributes in snapshot.values():
        for key, value in attributes.items():
            if value is None:
                element.attrib.pop(key, None)
            else:
                element.set(key, value)


def _rollback_unsafe_alignment(
    line_elements: list[ET.Element],
    snapshot: dict[int, tuple[ET.Element, dict[str, str | None]]],
    result: OrthogonalizationResult,
    *,
    aligned_devices: int,
    aligned_lines: int,
    connection_aligned_lines: int,
    aligned_device_ids: int,
    obstacles: list[tuple[str, tuple[float, float, float, float]]],
) -> None:
    invalid_lines: list[ET.Element] = []
    for line in line_elements:
        before = snapshot.get(id(line))
        if before is None:
            continue
        old_attributes = before[1]
        if all(line.get(key) == value for key, value in old_attributes.items()):
            continue
        points = _points(line)
        if points is not None and _line_hits_obstacles(
            points,
            obstacles,
            _referenced_ids(line),
        ):
            invalid_lines.append(line)
    if not invalid_lines:
        return

    _restore_geometry(snapshot)
    result.aligned_devices = aligned_devices
    result.aligned_lines = aligned_lines
    result.connection_aligned_lines = connection_aligned_lines
    del result.aligned_device_ids[aligned_device_ids:]
    result.issues.extend(
        OrthogonalizationIssue(
            element_id=(line.get("id") or "").strip(),
            element_type=local_name(line.tag),
            reason="设备对齐后的线路会穿过其他设备，已回滚本次设备/线路对齐。",
        )
        for line in invalid_lines
    )


def orthogonalize_tree(
    tree: ET.ElementTree,
    *,
    axis_tolerance: float = 0.5,
    device_align_tolerance: float = 8.0,
    endpoint_tolerance: float = 18.0,
    geometry_templates: dict[str, list[dict[str, object]]] | None = None,
) -> OrthogonalizationResult:
    """Align repeated devices and safely normalize electrical line routes.

    Repeated same-standard devices are aligned only when they clearly form a
    row or column and every affected line endpoint identifies that device;
    the actual line endpoints are used as the alignment anchors.  A diagonal
    line between unlike devices may move only a small, unambiguous leaf device
    so its real connection point shares an axis with the other endpoint.
    Confirmed two-ended lines are then re-routed in place to the ACTIVE/GLOBAL
    standard Pin coordinates when available, preserving IDs and link/node_area.
    Without a standard geometry payload the legacy device-boundary fallback is
    retained.  Remaining diagonal segments become horizontal/vertical elbows.
    Any unsafe route is left unchanged.
    """
    root = tree.getroot()
    all_elements = list(root.iter())
    line_elements = [
        element for element in all_elements
        if local_name(element.tag) in _LINE_TAGS and _points(element) is not None
    ]
    result = OrthogonalizationResult(inspected_lines=len(line_elements))

    # Device alignment must happen before route generation so the line follows
    # the final device position.  The endpoint coordinates in d, together with
    # node_area/link endpoint references, are the authoritative topology
    # anchors.  Refresh the element list after every geometry pass because
    # endpoint geometry and obstacle boxes have changed in place.
    alignment_snapshot = _snapshot_geometry(all_elements, line_elements)
    alignment_checkpoint = (
        result.aligned_devices,
        result.aligned_lines,
        result.connection_aligned_lines,
        len(result.aligned_device_ids),
    )
    connections = _device_connections(all_elements, line_elements)
    _align_similar_devices(
        all_elements,
        line_elements,
        result,
        tolerance=device_align_tolerance,
        connections=connections,
        endpoint_tolerance=endpoint_tolerance,
        geometry_templates=geometry_templates,
    )
    all_elements = list(root.iter())
    line_elements = [
        element for element in all_elements
        if local_name(element.tag) in _LINE_TAGS and _points(element) is not None
    ]
    obstacles_before_mixed = _build_obstacles(all_elements)
    _align_mixed_device_connection_points(
        all_elements,
        line_elements,
        result,
        endpoint_tolerance=endpoint_tolerance,
        axis_tolerance=axis_tolerance,
        obstacles=obstacles_before_mixed,
        geometry_templates=geometry_templates,
    )
    all_elements = list(root.iter())
    line_elements = [
        element for element in all_elements
        if local_name(element.tag) in _LINE_TAGS and _points(element) is not None
    ]

    obstacles = _build_obstacles(all_elements)
    _rollback_unsafe_alignment(
        line_elements,
        alignment_snapshot,
        result,
        aligned_devices=alignment_checkpoint[0],
        aligned_lines=alignment_checkpoint[1],
        connection_aligned_lines=alignment_checkpoint[2],
        aligned_device_ids=alignment_checkpoint[3],
        obstacles=obstacles,
    )
    # A rollback restores device positions and line paths, so refresh both the
    # obstacle set and topology view before any confirmed route is regenerated.
    all_elements = list(root.iter())
    line_elements = [
        element for element in all_elements
        if local_name(element.tag) in _LINE_TAGS and _points(element) is not None
    ]
    obstacles = _build_obstacles(all_elements)

    protected_lines = _rebuild_confirmed_lines(
        all_elements,
        line_elements,
        obstacles,
        result,
        endpoint_tolerance=endpoint_tolerance,
        axis_tolerance=axis_tolerance,
        geometry_templates=geometry_templates,
    )
    # Rebuild may have changed a line's path.  The following pass handles any
    # remaining multi-segment or unconfirmed diagonal routes.
    for element in line_elements:
        if id(element) in protected_lines:
            continue
        original = _points(element)
        assert original is not None
        if all(
            abs(a[0] - b[0]) <= axis_tolerance or abs(a[1] - b[1]) <= axis_tolerance
            for a, b in zip(original, original[1:])
        ):
            continue

        referenced = _referenced_ids(element)
        usable_obstacles = [item for item in obstacles if item[0] not in referenced]
        transformed: list[tuple[float, float]] = [original[0]]
        added_segments = 0
        safe = True
        for start, end in zip(original, original[1:]):
            route = _orthogonal_route(
                start,
                end,
                usable_obstacles,
                axis_tolerance=axis_tolerance,
            )
            if route is None:
                safe = False
                break
            route_points, added = route
            transformed.extend(route_points[1:])
            added_segments += added
        if not safe:
            result.skipped_lines += 1
            result.issues.append(OrthogonalizationIssue(
                element_id=(element.get("id") or "").strip(),
                element_type=local_name(element.tag),
                reason="两个横平竖直走线方案都会穿过已识别设备图元，保守跳过。",
            ))
            continue

        transformed = _simplify(transformed)
        if transformed == original:
            continue
        _rewrite_points(element, transformed)
        result.changed_lines += 1
        result.changed_segments += added_segments
        element_id = (element.get("id") or "").strip()
        if element_id:
            result.changed_line_ids.append(element_id)

    return result
