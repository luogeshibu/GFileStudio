from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


ENCODING_RE = re.compile(br"<\?xml[^>]*encoding=[\"']([^\"']+)[\"']", re.I)
DEVREF_RE = re.compile(r"#([^:]+):")
POINT_RE = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class IconDefinition:
    path: Path
    file_name: str
    element_tag: str
    element_id: str
    width: float
    height: float
    align_center: tuple[float, float]
    pins: tuple[tuple[float, float], ...]
    pin_ids: tuple[str, ...]


@dataclass(frozen=True)
class IconUpgradeRule:
    file_name: str
    old: IconDefinition
    new: IconDefinition


@dataclass
class IconPairAnalysis:
    rules: dict[str, IconUpgradeRule] = field(default_factory=dict)
    missing_old: list[str] = field(default_factory=list)
    missing_new: list[str] = field(default_factory=list)
    incompatible: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.missing_old and not self.missing_new and not self.incompatible and bool(self.rules)


@dataclass
class IconUpgradeResult:
    upgraded_instances: int = 0
    adjusted_lines: int = 0
    already_new_instances: int = 0
    skipped_unknown_size: int = 0
    changed_instance_ids: list[str] = field(default_factory=list)
    changed_line_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return float(default)


def _number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return str(int(rounded))
    return ("%.6f" % value).rstrip("0").rstrip(".")


def _decode_xml(raw: bytes) -> str:
    match = ENCODING_RE.search(raw[:512])
    declared = match.group(1).decode("ascii", "ignore") if match else "utf-8"
    candidates = [declared]
    if declared.lower().replace("-", "") in {"gbk", "gb2312"}:
        candidates.append("gb18030")
    candidates.extend(["utf-8", "gb18030", "gbk"])
    tried: set[str] = set()
    for encoding in candidates:
        key = encoding.lower()
        if key in tried:
            continue
        tried.add(key)
        try:
            text = raw.decode(encoding)
            return re.sub(
                r"(<\?xml\b[^>]*\bencoding=)[\"'][^\"']+[\"']",
                r'\1"utf-8"',
                text,
                count=1,
                flags=re.I,
            )
        except (LookupError, UnicodeDecodeError):
            continue
    raise ValueError("无法识别图元 G 文件编码。")


def _parse_icon_root(path: Path) -> ET.Element:
    raw = path.read_bytes()
    text = _decode_xml(raw)
    try:
        return ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"{path.name} XML 解析失败：{exc}") from exc


def parse_icon_definition(path: Path) -> IconDefinition:
    path = Path(path)
    root = _parse_icon_root(path)
    candidates: list[tuple[int, ET.Element, list[ET.Element]]] = []
    for element in root.iter():
        if "AlignCenter" not in element.attrib or "w" not in element.attrib or "h" not in element.attrib:
            continue
        pins = [child for child in element.iter() if _local_name(child.tag).lower() == "pin"]
        candidates.append((len(pins), element, pins))
    if not candidates:
        raise ValueError(f"{path.name} 未找到包含 w/h/AlignCenter 的图元主体。")

    # 优先选择含端口最多的主体；无端口图元则选择第一个有效主体。
    candidates.sort(key=lambda item: item[0], reverse=True)
    _pin_count, body, pin_elements = candidates[0]
    align_text = (body.get("AlignCenter") or "").strip()
    match = POINT_RE.fullmatch(align_text)
    if not match:
        raise ValueError(f"{path.name} 的 AlignCenter 无法解析：{align_text!r}")
    align = (float(match.group(1)), float(match.group(2)))
    pins = tuple((_float(pin.get("cx")), _float(pin.get("cy"))) for pin in pin_elements)
    pin_ids = tuple((pin.get("id") or "").strip() for pin in pin_elements)
    return IconDefinition(
        path=path,
        file_name=path.name,
        element_tag=_local_name(body.tag),
        element_id=(body.get("id") or "").strip(),
        width=_float(body.get("w")),
        height=_float(body.get("h")),
        align_center=align,
        pins=pins,
        pin_ids=pin_ids,
    )


def _index_unique(paths: list[Path], side: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    duplicates: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        key = path.name
        if key in result and result[key].resolve(strict=False) != path.resolve(strict=False):
            duplicates.append(key)
        result[key] = path
    if duplicates:
        names = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"{side}图元中存在重复文件名：{names}。请每种图元只保留一份。")
    return result


def analyze_icon_pairs(old_paths: list[Path], new_paths: list[Path]) -> IconPairAnalysis:
    old_map = _index_unique(old_paths, "旧")
    new_map = _index_unique(new_paths, "新")
    analysis = IconPairAnalysis(
        missing_old=sorted(set(new_map) - set(old_map)),
        missing_new=sorted(set(old_map) - set(new_map)),
    )
    for name in sorted(set(old_map) & set(new_map)):
        try:
            old = parse_icon_definition(old_map[name])
            new = parse_icon_definition(new_map[name])
            reasons: list[str] = []
            if old.element_tag != new.element_tag:
                reasons.append(f"标签 {old.element_tag} → {new.element_tag}")
            if old.element_id and new.element_id and old.element_id != new.element_id:
                reasons.append(f"主体 ID {old.element_id} → {new.element_id}")
            if len(old.pins) != len(new.pins):
                reasons.append(f"端口数 {len(old.pins)} → {len(new.pins)}")
            if old.width <= 0 or old.height <= 0 or new.width <= 0 or new.height <= 0:
                reasons.append("宽高必须大于 0")
            normalized_new = new
            if len(old.pins) == 1 and len(new.pins) == 1:
                normalized_new = IconDefinition(
                    path=new.path, file_name=new.file_name, element_tag=new.element_tag,
                    element_id=new.element_id, width=new.width, height=new.height,
                    align_center=new.align_center, pins=new.pins, pin_ids=old.pin_ids,
                )
            elif old.pins:
                if not all(old.pin_ids) or not all(new.pin_ids):
                    reasons.append("存在缺少 id 的 pin，无法可靠建立新旧端口对应")
                elif len(set(old.pin_ids)) != len(old.pin_ids) or len(set(new.pin_ids)) != len(new.pin_ids):
                    reasons.append("pin id 存在重复，无法可靠建立端口对应")
                elif set(old.pin_ids) != set(new.pin_ids):
                    reasons.append("新旧 pin id 集合不同，无法确认端口对应")
                else:
                    new_by_id = {pin_id: pin for pin_id, pin in zip(new.pin_ids, new.pins)}
                    normalized_new = IconDefinition(
                        path=new.path,
                        file_name=new.file_name,
                        element_tag=new.element_tag,
                        element_id=new.element_id,
                        width=new.width,
                        height=new.height,
                        align_center=new.align_center,
                        pins=tuple(new_by_id[pin_id] for pin_id in old.pin_ids),
                        pin_ids=old.pin_ids,
                    )
            if reasons:
                analysis.incompatible.append(f"{name}：" + "；".join(reasons))
                continue
            analysis.rules[name] = IconUpgradeRule(name, old, normalized_new)
        except Exception as exc:
            analysis.incompatible.append(f"{name}：{exc}")
    return analysis


def rotated(point: tuple[float, float], width: float, height: float, degrees: int) -> tuple[float, float]:
    x, y = point
    rotation = degrees % 360
    if rotation == 0:
        return x, y
    if rotation == 90:
        return height - y, x
    if rotation == 180:
        return width - x, height - y
    if rotation == 270:
        return y, width - x
    raise ValueError(f"不支持的旋转角度：{degrees}")


def _points_from_d(value: str) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in POINT_RE.findall(value or "")]


def _element_by_id(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for element in root.iter():
        object_id = (element.get("id") or "").strip()
        if object_id:
            result[object_id] = element
    return result


def apply_icon_upgrade(tree: ET.ElementTree, rules: dict[str, IconUpgradeRule]) -> IconUpgradeResult:
    root = tree.getroot()
    elements = list(root.iter())
    by_id = _element_by_id(root)
    reverse_links: dict[str, list[tuple[str, str, str]]] = {}

    for candidate in elements:
        line_id = (candidate.get("id") or "").strip()
        points = _points_from_d(candidate.get("d") or "")
        if not line_id or len(points) != 2:
            continue
        for link in (candidate.get("node_area") or "").split(";"):
            fields = link.split(",")
            if len(fields) != 3:
                continue
            endpoint_index, pin_index, object_id = fields
            reverse_links.setdefault(object_id, []).append((pin_index, endpoint_index, line_id))

    result = IconUpgradeResult()
    line_points: dict[str, dict[int, tuple[float, float]]] = {}

    for element in elements:
        devref = element.get("devref") or ""
        match = DEVREF_RE.search(devref)
        if not match:
            continue
        file_name = match.group(1)
        rule = rules.get(file_name)
        if rule is None:
            continue
        current_w = _float(element.get("w"))
        current_h = _float(element.get("h"))
        if abs(current_w - rule.new.width) < 1e-6 and abs(current_h - rule.new.height) < 1e-6:
            result.already_new_instances += 1
            continue
        if abs(current_w - rule.old.width) >= 1e-6 or abs(current_h - rule.old.height) >= 1e-6:
            result.skipped_unknown_size += 1
            result.warnings.append(
                f"图元 ID {element.get('id') or '<无ID>'} 引用 {file_name}，当前尺寸 "
                f"{_number(current_w)}×{_number(current_h)} 既不是旧尺寸 "
                f"{_number(rule.old.width)}×{_number(rule.old.height)}，也不是新尺寸，已跳过。"
            )
            continue

        rotation = int(round(_float(element.get("rotate"), 0.0)))
        old_align = rotated(rule.old.align_center, rule.old.width, rule.old.height, rotation)
        new_align = rotated(rule.new.align_center, rule.new.width, rule.new.height, rotation)
        new_x = _float(element.get("x")) + old_align[0] - new_align[0]
        new_y = _float(element.get("y")) + old_align[1] - new_align[1]
        element.set("x", _number(new_x))
        element.set("y", _number(new_y))
        element.set("w", _number(rule.new.width))
        element.set("h", _number(rule.new.height))
        result.upgraded_instances += 1
        object_id = (element.get("id") or "").strip()
        if object_id:
            result.changed_instance_ids.append(object_id)

        links: list[tuple[str, str, str]] = []
        for link in (element.get("node_area") or "").split(";"):
            fields = link.split(",")
            if len(fields) == 3:
                links.append((fields[0], fields[1], fields[2]))
        if object_id:
            links.extend(reverse_links.get(object_id, []))

        for pin_index, endpoint_index, line_id in set(links):
            try:
                pin_number = int(pin_index)
                endpoint_number = int(endpoint_index)
            except ValueError:
                result.warnings.append(f"图元 ID {object_id} 的连接引用无法解析：{pin_index},{endpoint_index},{line_id}")
                continue
            if pin_number < 0 or pin_number >= len(rule.new.pins):
                result.warnings.append(
                    f"图元 ID {object_id} 的端口索引 {pin_number} 超出 {file_name} 新图元端口范围，已跳过该连接。"
                )
                continue
            if endpoint_number not in (0, 1):
                result.warnings.append(f"连接线 {line_id} 的端点索引 {endpoint_number} 不是 0/1，已跳过。")
                continue
            pin = rotated(rule.new.pins[pin_number], rule.new.width, rule.new.height, rotation)
            line_points.setdefault(line_id, {})[endpoint_number] = (new_x + pin[0], new_y + pin[1])

    for line_id, endpoints in line_points.items():
        line = by_id.get(line_id)
        if line is None:
            raise ValueError(f"图元升级需要修改连接线 {line_id}，但当前 G 文件中找不到该 ID。")
        points = _points_from_d(line.get("d") or "")
        if len(points) != 2:
            raise ValueError(f"连接线 {line_id} 不是两点线段，无法按已验证算法安全适配。")
        for endpoint_index, point in endpoints.items():
            points[endpoint_index] = point
        (x1, y1), (x2, y2) = points
        line.set("d", f"{_number(x1)},{_number(y1)} {_number(x2)},{_number(y2)}")
        line.set("x", _number(min(x1, x2) - 3))
        line.set("y", _number(min(y1, y2) - 3))
        line.set("w", _number(abs(x1 - x2) + 6))
        line.set("h", _number(abs(y1 - y2) + 6))
        for name, value in (("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)):
            if name in line.attrib:
                line.set(name, _number(value))
        result.adjusted_lines += 1
        result.changed_line_ids.append(line_id)

    return result
