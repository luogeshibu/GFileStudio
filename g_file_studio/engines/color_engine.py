from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from g_file_studio.engines.id_engine import local_name

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ColorProcessingError(ValueError):
    """线路与母线颜色配置或处理错误。"""


@dataclass(frozen=True)
class ColorRule:
    element_tag: str
    display_name: str
    color: str


@dataclass
class ColorChangeResult:
    file_path: Path
    changed_by_tag: dict[str, int] = field(default_factory=dict)
    dynamic_color_by_tag: dict[str, int] = field(default_factory=dict)

    @property
    def total_changed(self) -> int:
        return sum(self.changed_by_tag.values())

    @property
    def total_dynamic_color(self) -> int:
        return sum(self.dynamic_color_by_tag.values())


def normalize_hex_color(value: str) -> str:
    color = value.strip()
    if not color.startswith("#") and len(color) == 6:
        color = "#" + color
    if not _COLOR_RE.fullmatch(color):
        raise ColorProcessingError(f"颜色必须是 #RRGGBB 格式：{value!r}")
    return color.upper()


def color_to_rgb_text(value: str) -> str:
    color = normalize_hex_color(value)
    return ",".join(str(int(color[index : index + 2], 16)) for index in (1, 3, 5))


def apply_line_colors(
    tree: ET.ElementTree,
    file_path: Path,
    rules: list[ColorRule],
) -> ColorChangeResult:
    """修改 G 根节点直属 Layer 的直属线路/母线图元静态线色。

    仅修改 `lc` 和 `lcc`。坐标、ID、引用、填充色和动态颜色开关均保持不变。
    """
    normalized_rules = {
        rule.element_tag: normalize_hex_color(rule.color)
        for rule in rules
    }
    result = ColorChangeResult(file_path=file_path)
    if not normalized_rules:
        return result

    root = tree.getroot()
    layers = [child for child in list(root) if local_name(child.tag) == "Layer"]
    if not layers:
        raise ColorProcessingError(f"文件 {file_path.name} 的 G 根节点下没有直属 Layer。")

    for layer in layers:
        for element in list(layer):
            tag = local_name(element.tag)
            color = normalized_rules.get(tag)
            if color is None:
                continue
            element.set("lcc", color)
            element.set("lc", color_to_rgb_text(color))
            result.changed_by_tag[tag] = result.changed_by_tag.get(tag, 0) + 1
            dy_flag = (element.get("p_DyColorFlag") or "0").strip()
            if dy_flag not in {"", "0"}:
                result.dynamic_color_by_tag[tag] = (
                    result.dynamic_color_by_tag.get(tag, 0) + 1
                )

    return result
