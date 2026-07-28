from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from g_file_studio.engines.frame_engine import (
    Box,
    FrameError,
    _shift_custom_template_components,
    boxes_intersect,
    element_box,
    identify_outer_frame_lines,
    parse_d_points,
    parse_number,
    read_canvas_size,
    require_single_direct_layer,
    set_line_geometry,
    shift_element,
)


class MarginAdjustmentError(RuntimeError):
    """图形边距调整错误。"""


@dataclass(frozen=True)
class ExistingFrame:
    outer_lines: dict[str, ET.Element]
    frame_box: Box
    components: tuple[ET.Element, ...]
    left_margin: float
    top_margin: float
    right_margin: float
    bottom_margin: float


@dataclass(frozen=True)
class MarginAdjustmentResult:
    output_path: Path
    had_existing_frame: bool
    old_canvas_width: int
    old_canvas_height: int
    new_canvas_width: int
    new_canvas_height: int
    body_left_margin: float
    body_top_margin: float
    body_right_margin: float
    body_bottom_margin: float
    frame_left_margin: float | None = None
    frame_top_margin: float | None = None
    frame_right_margin: float | None = None
    frame_bottom_margin: float | None = None


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _combine_boxes(boxes: Iterable[Box]) -> Box | None:
    values = list(boxes)
    if not values:
        return None
    return Box(
        min(box.left for box in values),
        min(box.top for box in values),
        max(box.right for box in values),
        max(box.bottom for box in values),
    )


def _node_box(node: ET.Element) -> Box | None:
    """计算单个 XML 节点的可见边界，兼顾尺寸和圆角半径。"""
    xs: list[float] = []
    ys: list[float] = []

    numeric: dict[str, float] = {}
    for name in (
        "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
        "mergex", "mergey", "w", "h", "width", "height", "rx", "ry",
    ):
        raw = node.get(name)
        if raw not in (None, ""):
            try:
                numeric[name] = parse_number(raw)
            except ValueError as exc:
                raise MarginAdjustmentError(
                    f"元素 <{_local_name(node.tag)}> 的 {name} 不是有效数字：{raw!r}"
                ) from exc

    for name in ("x", "x1", "x2", "cx", "mergex"):
        if name in numeric:
            xs.append(numeric[name])
    for name in ("y", "y1", "y2", "cy", "mergey"):
        if name in numeric:
            ys.append(numeric[name])

    width = numeric.get("w", numeric.get("width"))
    height = numeric.get("h", numeric.get("height"))
    if "x" in numeric and width is not None:
        xs.append(numeric["x"] + width)
    if "y" in numeric and height is not None:
        ys.append(numeric["y"] + height)
    if "mergex" in numeric and width is not None:
        xs.append(numeric["mergex"] + width)
    if "mergey" in numeric and height is not None:
        ys.append(numeric["mergey"] + height)
    if "cx" in numeric and "rx" in numeric:
        xs.extend((numeric["cx"] - numeric["rx"], numeric["cx"] + numeric["rx"]))
    if "cy" in numeric and "ry" in numeric:
        ys.extend((numeric["cy"] - numeric["ry"], numeric["cy"] + numeric["ry"]))

    for x, y in parse_d_points(node.get("d", "")):
        xs.append(x)
        ys.append(y)

    if not xs or not ys:
        return None
    return Box(min(xs), min(ys), max(xs), max(ys))


def subtree_box(element: ET.Element) -> Box | None:
    return _combine_boxes(
        box
        for node in element.iter()
        if (box := _node_box(node)) is not None
    )


def elements_box(elements: Iterable[ET.Element]) -> Box | None:
    return _combine_boxes(
        box
        for element in elements
        if (box := subtree_box(element)) is not None
    )


def _frame_is_canvas_outer(frame: Box, width: int, height: int) -> bool:
    """避免把普通设备矩形或表格误判为画布外框。"""
    if frame.width < width * 0.55 or frame.height < height * 0.55:
        return False
    tolerance_x = max(20.0, width * 0.03)
    tolerance_y = max(20.0, height * 0.03)
    margins = (
        frame.left,
        frame.top,
        width - frame.right,
        height - frame.bottom,
    )
    if any(value < -max(tolerance_x, tolerance_y) for value in margins):
        return False
    return (
        frame.left <= width * 0.25 + tolerance_x
        and width - frame.right <= width * 0.25 + tolerance_x
        and frame.top <= height * 0.25 + tolerance_y
        and height - frame.bottom <= height * 0.25 + tolerance_y
    )


def _connected_frame_components(
    elements: Sequence[ET.Element],
    outer_lines: dict[str, ET.Element],
    width: int,
    height: int,
) -> tuple[ET.Element, ...]:
    """从外框线出发，按几何邻接识别标题栏、签字栏等附属组件。"""
    boxes = {id(element): subtree_box(element) for element in elements}
    included = {id(element) for element in outer_lines.values()}
    tolerance = min(36.0, max(14.0, min(width, height) * 0.006))

    changed = True
    while changed:
        changed = False
        included_boxes = [boxes[item_id] for item_id in included if boxes.get(item_id) is not None]
        for element in elements:
            element_id = id(element)
            if element_id in included:
                continue
            box = boxes.get(element_id)
            if box is None:
                continue
            if any(boxes_intersect(box, existing, tolerance=tolerance) for existing in included_boxes):
                included.add(element_id)
                changed = True

    return tuple(element for element in elements if id(element) in included)


def detect_existing_frame(
    layer: ET.Element,
    canvas_width: int,
    canvas_height: int,
) -> ExistingFrame | None:
    elements = list(layer)
    try:
        outer_lines, frame_box = identify_outer_frame_lines(
            elements,
            canvas_width,
            canvas_height,
        )
    except (FrameError, ValueError):
        return None

    if not _frame_is_canvas_outer(frame_box, canvas_width, canvas_height):
        return None

    components = _connected_frame_components(
        elements,
        outer_lines,
        canvas_width,
        canvas_height,
    )
    return ExistingFrame(
        outer_lines=outer_lines,
        frame_box=frame_box,
        components=components,
        left_margin=frame_box.left,
        top_margin=frame_box.top,
        right_margin=canvas_width - frame_box.right,
        bottom_margin=canvas_height - frame_box.bottom,
    )


def _set_canvas_size(root: ET.Element, width: int, height: int) -> None:
    for name in ("w", "width"):
        root.set(name, str(int(width)))
    for name in ("h", "height"):
        root.set(name, str(int(height)))


def _output_name(input_name: str, suffix: str) -> str:
    if not suffix:
        return input_name
    compound = ".sln.pic.g"
    lower = input_name.lower()
    if lower.endswith(compound):
        return input_name[: -len(compound)] + suffix + compound
    if lower.endswith(".g"):
        return input_name[:-2] + suffix + ".g"
    return input_name + suffix


def adjust_one_file(
    input_path: Path,
    output_path: Path,
    *,
    left_margin: int = 500,
    top_margin: int = 500,
    right_margin: int = 500,
    bottom_margin: int = 500,
    preserve_existing_frame: bool = True,
) -> MarginAdjustmentResult:
    """调整主体图形到画布四边的距离，并同步适配已有外框。"""
    try:
        tree = ET.parse(input_path)
    except ET.ParseError as exc:
        raise MarginAdjustmentError(f"XML 解析失败：{input_path.name}：{exc}") from exc

    root = tree.getroot()
    if _local_name(root.tag) != "G":
        raise MarginAdjustmentError(f"{input_path.name} 的根节点不是 G。")

    layer = require_single_direct_layer(root, input_path.name)
    old_width, old_height = read_canvas_size(root, input_path.name)
    direct_elements = list(layer)
    existing_frame = (
        detect_existing_frame(layer, old_width, old_height)
        if preserve_existing_frame
        else None
    )
    frame_ids = {id(element) for element in existing_frame.components} if existing_frame else set()
    body_elements = [element for element in direct_elements if id(element) not in frame_ids]
    body_before = elements_box(body_elements)
    if body_before is None:
        raise MarginAdjustmentError(
            f"{input_path.name} 中没有找到可用于边距调整的主体图形。"
        )

    dx = float(left_margin) - body_before.left
    dy = float(top_margin) - body_before.top
    for element in body_elements:
        shift_element(element, dx, dy)

    body_after = elements_box(body_elements)
    if body_after is None:
        raise MarginAdjustmentError("主体图形平移后无法重新计算边界。")

    new_width = int(math.ceil(body_after.right + float(right_margin)))
    new_height = int(math.ceil(body_after.bottom + float(bottom_margin)))
    if new_width <= 0 or new_height <= 0:
        raise MarginAdjustmentError(f"计算得到的画布尺寸无效：{new_width} × {new_height}")

    frame_margins: tuple[float, float, float, float] | None = None
    if existing_frame is not None:
        new_frame = Box(
            left=existing_frame.left_margin,
            top=existing_frame.top_margin,
            right=new_width - existing_frame.right_margin,
            bottom=new_height - existing_frame.bottom_margin,
        )
        if new_frame.width <= 0 or new_frame.height <= 0:
            raise MarginAdjustmentError(
                "调整后的画布太小，无法保留原有图框四边距。"
            )

        outer = existing_frame.outer_lines
        set_line_geometry(outer["top"], new_frame.left, new_frame.top, new_frame.right, new_frame.top)
        set_line_geometry(outer["right"], new_frame.right, new_frame.top, new_frame.right, new_frame.bottom)
        set_line_geometry(outer["bottom"], new_frame.right, new_frame.bottom, new_frame.left, new_frame.bottom)
        set_line_geometry(outer["left"], new_frame.left, new_frame.bottom, new_frame.left, new_frame.top)
        _shift_custom_template_components(
            existing_frame.components,
            outer,
            existing_frame.frame_box,
            new_frame,
        )
        frame_margins = (
            new_frame.left,
            new_frame.top,
            new_width - new_frame.right,
            new_height - new_frame.bottom,
        )

    _set_canvas_size(root, new_width, new_height)

    # 写出前验证主体边距。右、下因画布尺寸取整，允许小于 1 像素的额外空白。
    final_body = elements_box(body_elements)
    if final_body is None:
        raise MarginAdjustmentError("无法验证最终主体图形边界。")
    actual_margins = (
        final_body.left,
        final_body.top,
        new_width - final_body.right,
        new_height - final_body.bottom,
    )
    requested = (left_margin, top_margin, right_margin, bottom_margin)
    for actual, expected, name in zip(actual_margins, requested, ("左", "上", "右", "下")):
        if actual + 1e-6 < expected or actual - expected >= 1.000001:
            raise MarginAdjustmentError(
                f"最终主体{name}边距验证失败：期望 {expected}，实际 {actual:.6f}。"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    try:
        if hasattr(ET, "indent"):
            ET.indent(tree, space="    ")
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
        ET.parse(tmp_path)
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return MarginAdjustmentResult(
        output_path=output_path,
        had_existing_frame=existing_frame is not None,
        old_canvas_width=old_width,
        old_canvas_height=old_height,
        new_canvas_width=new_width,
        new_canvas_height=new_height,
        body_left_margin=actual_margins[0],
        body_top_margin=actual_margins[1],
        body_right_margin=actual_margins[2],
        body_bottom_margin=actual_margins[3],
        frame_left_margin=frame_margins[0] if frame_margins else None,
        frame_top_margin=frame_margins[1] if frame_margins else None,
        frame_right_margin=frame_margins[2] if frame_margins else None,
        frame_bottom_margin=frame_margins[3] if frame_margins else None,
    )


def make_output_path(output_dir: Path, input_path: Path, suffix: str) -> Path:
    return output_dir / _output_name(input_path.name, suffix)
