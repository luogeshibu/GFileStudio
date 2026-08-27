from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.id_engine import direct_layer_elements, local_name
from g_file_studio.engines.icon_upgrade_engine import parse_icon_definition, rotated
from g_file_studio.engines.rmu_identification_engine import identify_rmus
from g_file_studio.engines.smart_icon_geometry import (
    apply_devref_preserving_anchors,
    build_geometry_templates,
    deserialize_geometry_templates,
    merge_geometry_templates,
    serialize_geometry_templates,
)


@dataclass(frozen=True)
class SmartProfileCandidate:
    devref: str
    count: int
    confidence: float


@dataclass
class SmartProfileScanResult:
    files: list[Path] = field(default_factory=list)
    parsed_file_count: int = 0
    smart_rmu_count: int = 0
    normal_rmu_count: int = 0
    ignored_rmu_count: int = 0
    lbs_counts: dict[str, int] = field(default_factory=dict)
    breaker_counts: dict[str, int] = field(default_factory=dict)
    normal_lbs_counts: dict[str, int] = field(default_factory=dict)
    normal_breaker_counts: dict[str, int] = field(default_factory=dict)
    ground_counts: dict[str, int] = field(default_factory=dict)
    normal_ground_counts: dict[str, int] = field(default_factory=dict)
    geometry_templates: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    symbol_catalog: dict[str, dict[str, object]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def lbs_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.lbs_counts)

    @property
    def breaker_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.breaker_counts)

    @property
    def normal_lbs_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.normal_lbs_counts)

    @property
    def normal_breaker_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.normal_breaker_counts)

    @property
    def ground_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.ground_counts)

    @property
    def normal_ground_candidates(self) -> list[SmartProfileCandidate]:
        return _candidate_rows(self.normal_ground_counts)

    @property
    def suggested_lbs_devref(self) -> str:
        rows = self.lbs_candidates
        return rows[0].devref if rows else ""

    @property
    def suggested_breaker_devref(self) -> str:
        rows = self.breaker_candidates
        return rows[0].devref if rows else ""

    @property
    def suggested_normal_lbs_devref(self) -> str:
        rows = self.normal_lbs_candidates
        return rows[0].devref if rows else ""

    @property
    def suggested_normal_breaker_devref(self) -> str:
        rows = self.normal_breaker_candidates
        return rows[0].devref if rows else ""

    @property
    def suggested_ground_devref(self) -> str:
        rows = self.ground_candidates
        return rows[0].devref if rows else ""

    @property
    def suggested_normal_ground_devref(self) -> str:
        rows = self.normal_ground_candidates
        return rows[0].devref if rows else ""


@dataclass
class SmartProfileApplyResult:
    file_path: Path
    scanned_rmu_count: int = 0
    smart_rmu_count: int = 0
    normal_rmu_count: int = 0
    ignored_rmu_count: int = 0
    lbs_checked_count: int = 0
    breaker_checked_count: int = 0
    normal_lbs_checked_count: int = 0
    normal_breaker_checked_count: int = 0
    ground_checked_count: int = 0
    normal_ground_checked_count: int = 0
    lbs_changed_count: int = 0
    breaker_changed_count: int = 0
    normal_lbs_changed_count: int = 0
    normal_breaker_changed_count: int = 0
    ground_changed_count: int = 0
    normal_ground_changed_count: int = 0
    custom_checked_count: int = 0
    custom_changed_count: int = 0
    geometry_adjusted_count: int = 0
    mismatch_counts: dict[str, int] = field(default_factory=dict)
    mismatch_details: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed_count(self) -> int:
        return (
            self.lbs_changed_count
            + self.breaker_changed_count
            + self.normal_lbs_changed_count
            + self.normal_breaker_changed_count
            + self.ground_changed_count
            + self.normal_ground_changed_count
            + self.custom_changed_count
        )


def _candidate_rows(counts: dict[str, int]) -> list[SmartProfileCandidate]:
    total = sum(max(0, int(value)) for value in counts.values())
    rows = [
        SmartProfileCandidate(devref=devref, count=int(count), confidence=(count / total if total else 0.0))
        for devref, count in counts.items()
        if devref and count > 0
    ]
    rows.sort(key=lambda row: (-row.count, row.devref.casefold()))
    return rows


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _box(element: ET.Element) -> tuple[float, float, float, float] | None:
    width = _number(element.get("w"))
    height = _number(element.get("h"))
    if width <= 0 or height <= 0:
        return None
    x = _number(element.get("x"))
    y = _number(element.get("y"))
    return x, y, x + width, y + height


def _center_inside(element: ET.Element, rect: ET.Element, tolerance: float = 0.5) -> bool:
    inner = _box(element)
    outer = _box(rect)
    if inner is None or outer is None:
        return False
    cx = (inner[0] + inner[2]) / 2.0
    cy = (inner[1] + inner[3]) / 2.0
    return (
        outer[0] - tolerance <= cx <= outer[2] + tolerance
        and outer[1] - tolerance <= cy <= outer[3] + tolerance
    )


def _near_rect(element: ET.Element, rect: ET.Element, margin: float = 140.0) -> bool:
    """Conservative marker association for SMR labels that are often outside the frame."""
    inner = _box(element)
    outer = _box(rect)
    if inner is None or outer is None:
        return False
    cx = (inner[0] + inner[2]) / 2.0
    cy = (inner[1] + inner[3]) / 2.0
    return (
        outer[0] - margin <= cx <= outer[2] + margin
        and outer[1] - margin <= cy <= outer[3] + margin
    )


def _find_rect(rects: list[ET.Element], item) -> ET.Element | None:
    rect_id = (item.rect_id or "").strip()
    by_id = [rect for rect in rects if (rect.get("id") or "").strip() == rect_id]
    candidates = by_id or rects
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda rect: (
            abs(_number(rect.get("x")) - item.rect_x)
            + abs(_number(rect.get("y")) - item.rect_y)
            + abs(_number(rect.get("w")) - item.rect_w)
            + abs(_number(rect.get("h")) - item.rect_h),
            (rect.get("id") or ""),
        ),
    )


def _device_role(element: ET.Element) -> str | None:
    if local_name(element.tag) != "CBreakerDis":
        return None
    devref = (element.get("devref") or "").upper()
    normalized = "_".join(part for part in "".join(ch if ch.isalnum() else " " for ch in devref).split())
    name = (element.get("p_NameString") or "").strip().upper()
    key_name = (element.get("key_name") or "").strip().upper()

    if any(token in normalized for token in ("LOAD_BREAKER", "LOADBREAKERSWITCH", "RMU_LBS")):
        return "LBS"
    if any(token in normalized for token in ("CIRCUIT_BREAKER", "CIRCUITBREAKER", "RMU_BRK")):
        return "BREAKER"
    if name.startswith("Y") or key_name.startswith("Y"):
        return "LBS"
    if name.startswith("Q") or key_name.startswith("Q"):
        return "BREAKER"
    return None


def _marker_texts(elements: list[ET.Element], marker: str) -> list[ET.Element]:
    marker = marker.strip().upper()
    return [
        element
        for element in elements
        if local_name(element.tag) in {"Text", "DText"}
        and (element.get("ts") or "").strip().upper() == marker
    ]


def _rmu_class(rect: ET.Element, smart_texts: list[ET.Element], smr_texts: list[ET.Element]) -> str:
    # Explicit text is the business label.  Do not classify from current devref,
    # otherwise a wrong SMART icon inside a NORMAL cabinet becomes self-confirming.
    if any(_center_inside(text, rect) for text in smart_texts):
        return "SMART"
    if any(_near_rect(text, rect) for text in smr_texts):
        return "SMR"
    return "NORMAL"


def _append_geometry_payload(
    destination: dict[str, list[dict[str, object]]],
    source: dict[str, list[dict[str, object]]],
) -> None:
    seen: dict[str, set[str]] = {}
    import json

    for devref, rows in destination.items():
        seen[devref] = {json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows}
    for devref, rows in source.items():
        bucket = destination.setdefault(devref, [])
        signatures = seen.setdefault(devref, set())
        for row in rows:
            signature = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if signature in signatures:
                continue
            signatures.add(signature)
            bucket.append(row)



def _element_rotation(element: ET.Element) -> int:
    raw = (element.get("rotate") or "").strip()
    if raw:
        try:
            return int(round(float(raw))) % 360
        except ValueError:
            pass
    import re
    match = re.search(r"rotate\(\s*([-+]?\d+(?:\.\d+)?)", element.get("tfr") or "")
    if match:
        try:
            return int(round(float(match.group(1)))) % 360
        except ValueError:
            pass
    return 0


def _merge_symbol_catalog_row(
    catalog: dict[str, dict[str, object]],
    devref: str,
    *,
    element_tag: str = "",
    element_id: str = "",
    source_file: str = "",
    width: float = 0.0,
    height: float = 0.0,
    align_center: list[float] | tuple[float, float] | None = None,
    pins: list[list[float]] | tuple[tuple[float, float], ...] | None = None,
    pin_ids: list[str] | tuple[str, ...] | None = None,
    rotation: int | None = None,
    p_name: str = "",
    key_name: str = "",
    increment: int = 1,
) -> None:
    devref = str(devref).strip()
    if not devref:
        return
    row = catalog.setdefault(devref, {
        "devref": devref,
        "element_tag": "",
        "element_id": "",
        "source_file": "",
        "width": 0.0,
        "height": 0.0,
        "align_center": [],
        "pins": [],
        "pin_ids": [],
        "rotations": [],
        "p_NameString": "",
        "key_name": "",
        "count": 0,
    })
    row["count"] = int(row.get("count", 0) or 0) + max(0, int(increment))
    for key, value in (
        ("element_tag", element_tag),
        ("element_id", element_id),
        ("source_file", source_file),
        ("p_NameString", p_name),
        ("key_name", key_name),
    ):
        if value and not str(row.get(key, "")).strip():
            row[key] = str(value)
    if width > 0 and float(row.get("width", 0.0) or 0.0) <= 0:
        row["width"] = float(width)
    if height > 0 and float(row.get("height", 0.0) or 0.0) <= 0:
        row["height"] = float(height)
    if align_center and len(align_center) >= 2:
        row["align_center"] = [float(align_center[0]), float(align_center[1])]
    if pins:
        row["pins"] = [[float(pair[0]), float(pair[1])] for pair in pins]
    if pin_ids:
        row["pin_ids"] = [str(item) for item in pin_ids]
    if rotation is not None:
        rotations = {int(item) % 360 for item in row.get("rotations", [])}
        rotations.add(int(rotation) % 360)
        row["rotations"] = sorted(rotations)


def _collect_main_g_symbol_catalog(
    catalog: dict[str, dict[str, object]],
    elements: list[ET.Element],
    file_path: Path,
) -> None:
    for element in elements:
        devref = (element.get("devref") or "").strip()
        if not devref:
            continue
        body_id = devref.split(":", 1)[1].strip() if ":" in devref else ""
        _merge_symbol_catalog_row(
            catalog,
            devref,
            element_tag=local_name(element.tag),
            element_id=body_id,
            source_file=file_path.name,
            width=_number(element.get("w")),
            height=_number(element.get("h")),
            rotation=_element_rotation(element),
            p_name=(element.get("p_NameString") or "").strip(),
            key_name=(element.get("key_name") or "").strip(),
        )


def collect_symbol_catalog_from_tree(tree: ET.ElementTree, file_path: Path) -> dict[str, dict[str, object]]:
    """Collect user-visible GIcon/devref candidates from one main G tree.

    This is used by the read-only standard checker to discover symbols that are not
    yet covered by the selected standard.  Discovery is informational only and does
    not make the business G file a standard sample.
    """
    catalog: dict[str, dict[str, object]] = {}
    elements = direct_layer_elements(tree.getroot())
    visible_candidates = [
        element for element in elements
        if (element.get("devref") or "").strip()
        and (element.get("composeType") or "").strip() == "GIcon"
    ]
    _collect_main_g_symbol_catalog(catalog, visible_candidates, Path(file_path))
    return catalog


def _collect_icon_definition_catalog(
    catalog: dict[str, dict[str, object]],
    file_path: Path,
) -> bool:
    """Read raw symbol-definition G attributes when the selected file is an icon G."""
    try:
        definition = parse_icon_definition(file_path)
    except Exception:
        return False
    devref = f"#{definition.file_name}:{definition.element_id}"
    _merge_symbol_catalog_row(
        catalog,
        devref,
        element_tag=definition.element_tag,
        element_id=definition.element_id,
        source_file=definition.file_name,
        width=definition.width,
        height=definition.height,
        align_center=definition.align_center,
        pins=definition.pins,
        pin_ids=definition.pin_ids,
        increment=0,
    )
    return True


def _collect_icon_definition_geometry(
    destination: dict[str, list[dict[str, object]]],
    file_path: Path,
) -> bool:
    """Build reusable rotation-specific geometry directly from a symbol-definition G."""
    try:
        definition = parse_icon_definition(file_path)
    except Exception:
        return False
    devref = f"#{definition.file_name}:{definition.element_id}"
    rows = destination.setdefault(devref, [])
    import json
    signatures = {json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows}
    for rotation in (0, 90, 180, 270):
        offsets = [
            list(rotated(pin, definition.width, definition.height, rotation))
            for pin in definition.pins
        ]
        if not offsets:
            continue
        row = {
            "rotation": rotation,
            "width": float(definition.width),
            "height": float(definition.height),
            "anchor_offsets": offsets,
        }
        signature = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if signature not in signatures:
            signatures.add(signature)
            rows.append(row)
    return True


def _custom_rule_matches(element: ET.Element, rule: dict[str, object], cabinet_class: str | None) -> bool:
    if not bool(rule.get("enabled", True)):
        return False
    scope = str(rule.get("scope", "ANY")).strip().upper() or "ANY"
    if scope in {"SMART", "NORMAL"} and cabinet_class != scope:
        return False
    element_tag = str(rule.get("element_tag", "")).strip()
    if element_tag and local_name(element.tag) != element_tag:
        return False
    match_attr = str(rule.get("match_attr", "devref")).strip() or "devref"
    match_value = str(rule.get("match_value", "")).strip()
    target = str(rule.get("standard_devref", "")).strip()
    if match_attr == "XML元素":
        return bool(element_tag)
    if match_attr == "devref":
        current = (element.get("devref") or "").strip()
        if not match_value:
            return bool(element_tag)
        # Include the standard devref itself so a second pass still validates geometry.
        return current in {match_value, target}
    if match_attr in {"p_NameString", "key_name"}:
        current = (element.get(match_attr) or "").strip()
        return bool(match_value) and current.casefold() == match_value.casefold()
    return False


def scan_smart_profile_samples(files: list[Path], progress=None) -> SmartProfileScanResult:
    """Learn SMART and NORMAL RMU device profiles from user-designated standard G files.

    Classification deliberately uses explicit RMU labels rather than the current
    device devref: SMART text inside the frame -> SMART; nearby SMR -> ignored/special;
    otherwise -> NORMAL.  This prevents a wrong icon from teaching itself as the
    cabinet type.  Both devref families and their geometry/port templates are learned.
    """

    result = SmartProfileScanResult(files=[Path(path) for path in files])
    smart_lbs = Counter()
    smart_breaker = Counter()
    normal_lbs = Counter()
    normal_breaker = Counter()
    smart_ground = Counter()
    normal_ground = Counter()

    total_files = max(1, len(result.files))
    if progress:
        progress(0)

    for file_index, file_path in enumerate(result.files, 1):
        def emit_phase(fraction: float) -> None:
            if progress:
                value = round((((file_index - 1) + max(0.0, min(1.0, fraction))) / total_files) * 100)
                progress(max(0, min(100, value)))

        emit_phase(0.03)
        icon_loaded = _collect_icon_definition_catalog(result.symbol_catalog, file_path)
        if icon_loaded:
            _collect_icon_definition_geometry(result.geometry_templates, file_path)
        try:
            tree = ET.parse(file_path)
        except Exception as exc:
            # Raw icon G files commonly declare GBK/GB18030, which Python's
            # ElementTree/expat cannot always parse directly. parse_icon_definition()
            # already decoded those safely above, so an icon definition still counts
            # as a successfully scanned standard sample.
            if icon_loaded:
                result.parsed_file_count += 1
                emit_phase(1.0)
                continue
            result.warnings.append(f"{file_path.name}: XML 解析失败：{exc}")
            continue
        result.parsed_file_count += 1
        emit_phase(0.20)
        elements = direct_layer_elements(tree.getroot())
        _collect_main_g_symbol_catalog(result.symbol_catalog, elements, file_path)
        rects = [element for element in elements if local_name(element.tag) == "rect"]
        smart_texts = _marker_texts(elements, "SMART")
        smr_texts = _marker_texts(elements, "SMR")

        # Learn geometry for every device devref found in the designated standard
        # sample; the saved profile later keeps the selected four devrefs.
        all_devrefs = {
            (element.get("devref") or "").strip()
            for element in elements
            if (element.get("devref") or "").strip()
            and _number(element.get("w")) > 0
            and _number(element.get("h")) > 0
        }
        _append_geometry_payload(
            result.geometry_templates,
            serialize_geometry_templates(build_geometry_templates(elements, all_devrefs)),
        )
        emit_phase(0.45)

        identification = identify_rmus(
            tree,
            file_path,
            name_positions=("top", "bottom", "left", "right"),
            smart_in_type=True,
        )
        emit_phase(0.65)
        for item in identification.items:
            rect = _find_rect(rects, item)
            if rect is None:
                continue
            cabinet_class = _rmu_class(rect, smart_texts, smr_texts)
            if cabinet_class == "SMART":
                result.smart_rmu_count += 1
            elif cabinet_class == "NORMAL":
                result.normal_rmu_count += 1
            else:
                result.ignored_rmu_count += 1
                continue

            for element in elements:
                tag = local_name(element.tag)
                if tag not in {"CBreakerDis", "ZhaiWaiJieDiDaoZha"} or not _center_inside(element, rect):
                    continue
                devref = (element.get("devref") or "").strip()
                if not devref:
                    continue
                if tag == "ZhaiWaiJieDiDaoZha":
                    if cabinet_class == "SMART":
                        smart_ground[devref] += 1
                    elif cabinet_class == "NORMAL":
                        normal_ground[devref] += 1
                    continue
                role = _device_role(element)
                if cabinet_class == "SMART" and role == "LBS":
                    smart_lbs[devref] += 1
                elif cabinet_class == "SMART" and role == "BREAKER":
                    smart_breaker[devref] += 1
                elif cabinet_class == "NORMAL" and role == "LBS":
                    normal_lbs[devref] += 1
                elif cabinet_class == "NORMAL" and role == "BREAKER":
                    normal_breaker[devref] += 1
        emit_phase(1.0)

    result.lbs_counts = dict(smart_lbs)
    result.breaker_counts = dict(smart_breaker)
    result.normal_lbs_counts = dict(normal_lbs)
    result.normal_breaker_counts = dict(normal_breaker)
    result.ground_counts = dict(smart_ground)
    result.normal_ground_counts = dict(normal_ground)
    if result.smart_rmu_count == 0:
        result.warnings.append("扫描样本中没有找到可确认的 SMART 环网柜。")
    if result.normal_rmu_count == 0:
        result.warnings.append("扫描样本中没有找到可确认的普通环网柜。")
    if not result.lbs_counts:
        result.warnings.append("没有从 SMART 环网柜中学习到 LBS CBreakerDis devref。")
    if not result.breaker_counts:
        result.warnings.append("没有从 SMART 环网柜中学习到 Circuit Breaker CBreakerDis devref。")
    if not result.normal_lbs_counts:
        result.warnings.append("没有从普通环网柜中学习到 LBS CBreakerDis devref。")
    if not result.normal_breaker_counts:
        result.warnings.append("没有从普通环网柜中学习到 Circuit Breaker CBreakerDis devref。")
    if not result.ground_counts:
        result.warnings.append("没有从 SMART 环网柜中学习到 ZhaiWaiJieDiDaoZha 接地刀闸 devref。")
    if not result.normal_ground_counts:
        result.warnings.append("没有从普通环网柜中学习到 ZhaiWaiJieDiDaoZha 接地刀闸 devref。")
    if progress:
        progress(100)
    return result


def _record_mismatch(counter: Counter, cabinet_class: str, role: str, old_devref: str) -> None:
    if old_devref:
        counter[f"{cabinet_class}:{role}:{old_devref}"] += 1


def _variant_kind(devref: str) -> str:
    """Return SMART/NORMAL when the devref makes the variant explicit."""
    value = (devref or "").upper().replace(" ", "_")
    if any(token in value for token in ("NON-SMART", "NON_SMART", "NO-SMART", "NO_SMART")):
        return "NORMAL"
    if "SMART" in value:
        return "SMART"
    return ""


def _element_snapshot(element: ET.Element) -> dict[str, object]:
    return {
        "devref": (element.get("devref") or "").strip(),
        "x": (element.get("x") or "").strip(),
        "y": (element.get("y") or "").strip(),
        "w": (element.get("w") or "").strip(),
        "h": (element.get("h") or "").strip(),
        "rotation": _element_rotation(element),
    }


def _connected_line_ids_for_report(element: ET.Element) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for item in (element.get("node_area") or "").split(";"):
        parts = [part.strip() for part in item.split(",")]
        if len(parts) < 3:
            continue
        value = parts[2]
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return ", ".join(values)


def _mismatch_detail(
    *,
    file_path: Path,
    element: ET.Element,
    scope: str,
    role: str,
    target: str,
    before: dict[str, object],
    applied,
    rmu_name: str = "",
    rmu_rect_id: str = "",
) -> dict[str, object] | None:
    devref_changed = str(before.get("devref", "")) != target
    geometry_changed = bool(applied.geometry_changed)
    if not devref_changed and not geometry_changed:
        return None

    after = _element_snapshot(element)
    issue_types: list[str] = []
    reasons: list[str] = []
    current_devref = str(before.get("devref", ""))
    current_variant = _variant_kind(current_devref)
    target_variant = _variant_kind(target)

    if devref_changed:
        if scope in {"SMART", "NORMAL"} and current_variant and target_variant and current_variant != target_variant:
            issue_types.append("SMART/NORMAL 图元变体错误")
            reasons.append(
                f"当前 RMU 为 {scope}，但设备使用了 {current_variant} 图元；"
                f"当前 devref={current_devref or '<空>'}，标准要求={target}。"
            )
        else:
            issue_types.append("标准图元引用不一致")
            reasons.append(
                f"当前 devref={current_devref or '<空>'}，与 ACTIVE 标准要求的 devref={target} 不一致。"
            )

    if geometry_changed:
        size_before = f"{before.get('w') or '?'}×{before.get('h') or '?'}"
        size_after = f"{after.get('w') or '?'}×{after.get('h') or '?'}"
        pos_before = f"({before.get('x') or '?'}, {before.get('y') or '?'})"
        pos_after = f"({after.get('x') or '?'}, {after.get('y') or '?'})"
        changed_bits: list[str] = []
        if (before.get("w"), before.get("h")) != (after.get("w"), after.get("h")):
            changed_bits.append(f"尺寸当前 {size_before}，标准 {size_after}")
        if (before.get("x"), before.get("y")) != (after.get("x"), after.get("y")):
            changed_bits.append(f"为保持电气锚点不动，图元位置应由 {pos_before} 调整为 {pos_after}")
        if not changed_bits:
            changed_bits.append("图元连接锚点/几何模板与 ACTIVE 标准不一致")
        issue_types.append("图元几何不符合标准")
        reasons.append("；".join(changed_bits) + f"；旋转={before.get('rotation', 0)}°。")

    return {
        "File": file_path.name,
        "RMU": rmu_name or "-",
        "RMURectID": rmu_rect_id or "-",
        "Scope": scope or "ANY",
        "Role": role or local_name(element.tag) or "CUSTOM",
        "ElementTag": local_name(element.tag),
        "ElementID": (element.get("id") or "").strip() or "-",
        "DeviceName": (element.get("p_NameString") or "").strip() or "-",
        "KeyName": (element.get("key_name") or "").strip() or "-",
        "Rotation": before.get("rotation", 0),
        "IssueType": " + ".join(issue_types),
        "Reason": " ".join(reasons),
        "CurrentDevref": current_devref or "<空>",
        "StandardDevref": target,
        "CurrentSize": f"{before.get('w') or '?'}×{before.get('h') or '?'}",
        "StandardSize": f"{after.get('w') or '?'}×{after.get('h') or '?'}",
        "CurrentPosition": f"({before.get('x') or '?'}, {before.get('y') or '?'})",
        "ExpectedPosition": f"({after.get('x') or '?'}, {after.get('y') or '?'})",
        "ConnectedLines": _connected_line_ids_for_report(element) or "-",
        "_AppliedDevrefChanged": bool(applied.devref_changed),
        "_AppliedGeometryChanged": bool(applied.geometry_changed),
    }


def apply_smart_profile_to_tree(
    tree: ET.ElementTree,
    file_path: Path,
    *,
    smart_lbs_devref: str,
    smart_breaker_devref: str,
    normal_lbs_devref: str = "",
    normal_breaker_devref: str = "",
    smart_ground_devref: str = "",
    normal_ground_devref: str = "",
    profile_geometry_templates: dict[str, list[dict[str, object]]] | None = None,
    custom_symbols: list[dict[str, object]] | None = None,
    require_template_for_connected_devref_change: bool = False,
) -> SmartProfileApplyResult:
    """Normalize SMART and, when configured, NORMAL RMU device symbols.

    SMART/NORMAL classification is based on explicit cabinet labels, not current
    devrefs.  SMR cabinets are skipped because their conversion is a site-specific
    business rule (for example Jeddah batch processing).  Replacements reuse geometry
    learned from both the current G file and the profile's standard sample files so
    electrical ConnectLine anchor coordinates remain fixed.
    """

    file_path = Path(file_path)
    if not smart_lbs_devref.strip():
        raise ValueError("SMART LBS devref 不能为空。")
    if not smart_breaker_devref.strip():
        raise ValueError("SMART Circuit Breaker devref 不能为空。")

    result = SmartProfileApplyResult(file_path=file_path)
    elements = direct_layer_elements(tree.getroot())
    rects = [element for element in elements if local_name(element.tag) == "rect"]
    smart_texts = _marker_texts(elements, "SMART")
    smr_texts = _marker_texts(elements, "SMR")

    targets = {smart_lbs_devref, smart_breaker_devref}
    if normal_lbs_devref.strip():
        targets.add(normal_lbs_devref.strip())
    if normal_breaker_devref.strip():
        targets.add(normal_breaker_devref.strip())
    if smart_ground_devref.strip():
        targets.add(smart_ground_devref.strip())
    if normal_ground_devref.strip():
        targets.add(normal_ground_devref.strip())
    for rule in custom_symbols or []:
        if bool(rule.get("enabled", True)):
            target = str(rule.get("standard_devref", "")).strip()
            if target:
                targets.add(target)
    file_geometry_templates = build_geometry_templates(elements, targets)
    profile_templates = deserialize_geometry_templates(profile_geometry_templates or {})
    # A saved Site Profile is the confirmed standard.  Prefer its geometry for each
    # devref/rotation and only fall back to same-file geometry when that rotation was
    # not learned.  This is critical when a vendor keeps the same devref name but
    # changes icon width/height or electrical anchor offsets in a new Profile version.
    geometry_templates = {}
    for key in set(file_geometry_templates) | set(profile_templates):
        geometry_templates[key] = list(profile_templates.get(key) or file_geometry_templates.get(key) or [])

    mismatch_counter: Counter = Counter()
    identification = identify_rmus(
        tree,
        file_path,
        name_positions=("top", "bottom", "left", "right"),
        smart_in_type=True,
    )
    result.scanned_rmu_count = len(identification.items)
    element_scope: dict[int, str] = {}
    element_rmu_name: dict[int, str] = {}
    element_rmu_rect_id: dict[int, str] = {}
    fixed_processed: set[int] = set()
    for item in identification.items:
        rect = _find_rect(rects, item)
        if rect is None:
            result.warnings.append(
                f"{file_path.name}: RMU rect {item.rect_id or '<无ID>'} 未定位，跳过图元一致性检查。"
            )
            continue
        cabinet_class = _rmu_class(rect, smart_texts, smr_texts)
        if cabinet_class == "SMR":
            result.ignored_rmu_count += 1
            continue
        if cabinet_class == "SMART":
            result.smart_rmu_count += 1
        else:
            result.normal_rmu_count += 1

        for scoped_element in elements:
            if _center_inside(scoped_element, rect):
                element_scope[id(scoped_element)] = cabinet_class
                element_rmu_name[id(scoped_element)] = item.name or ""
                element_rmu_rect_id[id(scoped_element)] = item.rect_id or ""

        for element in elements:
            tag = local_name(element.tag)
            if tag not in {"CBreakerDis", "ZhaiWaiJieDiDaoZha"} or not _center_inside(element, rect):
                continue
            old_devref = (element.get("devref") or "").strip()
            if tag == "ZhaiWaiJieDiDaoZha":
                role = "GROUND"
                if cabinet_class == "SMART":
                    result.ground_checked_count += 1
                    target = smart_ground_devref.strip()
                else:
                    result.normal_ground_checked_count += 1
                    target = normal_ground_devref.strip()
                # Historical profiles did not learn grounding-switch symbols.
                if not target:
                    continue
            else:
                role = _device_role(element)
                if role not in {"LBS", "BREAKER"}:
                    continue
                if cabinet_class == "SMART":
                    if role == "LBS":
                        result.lbs_checked_count += 1
                        target = smart_lbs_devref
                    else:
                        result.breaker_checked_count += 1
                        target = smart_breaker_devref
                else:
                    if role == "LBS":
                        result.normal_lbs_checked_count += 1
                        target = normal_lbs_devref.strip()
                    else:
                        result.normal_breaker_checked_count += 1
                        target = normal_breaker_devref.strip()
                    if not target:
                        continue

            fixed_processed.add(id(element))
            before = _element_snapshot(element)
            if old_devref != target:
                _record_mismatch(mismatch_counter, cabinet_class, role, old_devref)
            applied = apply_devref_preserving_anchors(
                element,
                target,
                elements=elements,
                templates=geometry_templates,
                require_template_for_connected_devref_change=require_template_for_connected_devref_change,
            )
            if old_devref != target and require_template_for_connected_devref_change and not applied.devref_changed:
                result.warnings.append(
                    f"{file_path.name}: 元素 {element.get('id') or '<无ID>'} 连接到电气线路，但当前 ACTIVE 标准没有可安全拟合的目标 pin/几何模板；为避免图元错位，devref 与位置均保持不变。"
                )
            detail = _mismatch_detail(
                file_path=file_path,
                element=element,
                scope=cabinet_class,
                role=role,
                target=target,
                before=before,
                applied=applied,
                rmu_name=item.name or "",
                rmu_rect_id=item.rect_id or "",
            )
            if detail is not None:
                result.mismatch_details.append(detail)
            if applied.geometry_changed:
                result.geometry_adjusted_count += 1
            if not applied.devref_changed:
                continue
            if role == "GROUND":
                if cabinet_class == "SMART":
                    result.ground_changed_count += 1
                else:
                    result.normal_ground_changed_count += 1
            elif cabinet_class == "SMART" and role == "LBS":
                result.lbs_changed_count += 1
            elif cabinet_class == "SMART":
                result.breaker_changed_count += 1
            elif role == "LBS":
                result.normal_lbs_changed_count += 1
            else:
                result.normal_breaker_changed_count += 1

    # User-defined standards are evaluated after the protected built-in RMU rules.
    # A custom rule can target any XML element type, optionally limited to SMART or
    # NORMAL RMUs. Built-in elements already handled above are never double-mutated.
    enabled_custom = [
        dict(rule) for rule in (custom_symbols or [])
        if isinstance(rule, dict)
        and bool(rule.get("enabled", True))
        and str(rule.get("standard_devref", "")).strip()
    ]
    for element in elements:
        if id(element) in fixed_processed:
            continue
        matches = [
            rule for rule in enabled_custom
            if _custom_rule_matches(element, rule, element_scope.get(id(element)))
        ]
        if not matches:
            continue
        if len(matches) > 1:
            roles = ", ".join(str(rule.get("role", "自定义")) for rule in matches)
            result.warnings.append(
                f"{file_path.name}: 元素 {element.get('id') or '<无ID>'} 同时匹配多个自定义图元标准（{roles}），为避免误改已跳过。"
            )
            continue
        rule = matches[0]
        target = str(rule.get("standard_devref", "")).strip()
        role = str(rule.get("role", "")).strip() or local_name(element.tag) or "CUSTOM"
        old_devref = (element.get("devref") or "").strip()
        before = _element_snapshot(element)
        result.custom_checked_count += 1
        if old_devref != target:
            _record_mismatch(mismatch_counter, "CUSTOM", role, old_devref)
        applied = apply_devref_preserving_anchors(
            element,
            target,
            elements=elements,
            templates=geometry_templates,
            require_template_for_connected_devref_change=require_template_for_connected_devref_change,
        )
        if old_devref != target and require_template_for_connected_devref_change and not applied.devref_changed:
            result.warnings.append(
                f"{file_path.name}: 自定义元素 {element.get('id') or '<无ID>'} 连接到电气线路，但当前 ACTIVE 标准没有可安全拟合的目标 pin/几何模板；为避免图元错位，devref 与位置均保持不变。"
            )
        detail = _mismatch_detail(
            file_path=file_path,
            element=element,
            scope=element_scope.get(id(element), "CUSTOM"),
            role=role,
            target=target,
            before=before,
            applied=applied,
            rmu_name=element_rmu_name.get(id(element), ""),
            rmu_rect_id=element_rmu_rect_id.get(id(element), ""),
        )
        if detail is not None:
            result.mismatch_details.append(detail)
        if applied.geometry_changed:
            result.geometry_adjusted_count += 1
        if applied.devref_changed:
            result.custom_changed_count += 1

    result.mismatch_counts = dict(mismatch_counter)
    return result


def apply_smart_profile_to_file(
    source_path: Path,
    output_path: Path,
    *,
    smart_lbs_devref: str,
    smart_breaker_devref: str,
    normal_lbs_devref: str = "",
    normal_breaker_devref: str = "",
    smart_ground_devref: str = "",
    normal_ground_devref: str = "",
    profile_geometry_templates: dict[str, list[dict[str, object]]] | None = None,
    custom_symbols: list[dict[str, object]] | None = None,
    require_template_for_connected_devref_change: bool = False,
) -> SmartProfileApplyResult:
    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(source_path)
    result = apply_smart_profile_to_tree(
        tree,
        source_path,
        smart_lbs_devref=smart_lbs_devref,
        smart_breaker_devref=smart_breaker_devref,
        normal_lbs_devref=normal_lbs_devref,
        normal_breaker_devref=normal_breaker_devref,
        smart_ground_devref=smart_ground_devref,
        normal_ground_devref=normal_ground_devref,
        profile_geometry_templates=profile_geometry_templates,
        custom_symbols=custom_symbols,
        require_template_for_connected_devref_change=require_template_for_connected_devref_change,
    )
    if result.changed_count or result.geometry_adjusted_count:
        if hasattr(ET, "indent"):
            ET.indent(tree, space="    ")
        tmp = output_path.with_name(output_path.name + ".tmp")
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        ET.parse(tmp)
        os.replace(tmp, output_path)
    else:
        shutil.copy2(source_path, output_path)
    return result
