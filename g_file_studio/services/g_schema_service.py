from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LayerSchemaScanResult:
    """输入目录中直属 Layer 图元的标签和属性扫描结果。"""

    file_count: int = 0
    layer_count: int = 0
    direct_element_count: int = 0
    tag_attributes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def tags(self) -> tuple[str, ...]:
        return tuple(self.tag_attributes)


def local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def scan_direct_layer_schema(input_dir: Path) -> LayerSchemaScanResult:
    """扫描目录下 G 文件中直属 Layer 的直接子元素。

    该函数只读取以下范围：

        G 根节点 -> 直属 Layer -> 直接子元素

    Theme、Layer 外内容以及图元内部嵌套子元素都不会参与标签和属性选项统计。
    """
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        return LayerSchemaScanResult(warnings=(f"输入目录不存在：{input_dir}",))

    files = sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".g"
        ),
        key=lambda path: path.name.casefold(),
    )

    tag_attributes: dict[str, set[str]] = {}
    warnings: list[str] = []
    layer_count = 0
    direct_element_count = 0
    valid_file_count = 0

    for path in files:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            warnings.append(f"{path.name} 读取失败：{exc}")
            continue

        layers = [child for child in list(root) if local_name(child.tag) == "Layer"]
        if not layers:
            warnings.append(f"{path.name} 没有直属 Layer")
            continue

        valid_file_count += 1
        layer_count += len(layers)
        for layer in layers:
            for element in list(layer):
                tag = local_name(element.tag)
                if not tag:
                    continue
                direct_element_count += 1
                tag_attributes.setdefault(tag, set()).update(element.attrib)

    normalized = {
        tag: tuple(sorted(attributes, key=str.casefold))
        for tag, attributes in sorted(tag_attributes.items(), key=lambda item: item[0].casefold())
    }
    return LayerSchemaScanResult(
        file_count=valid_file_count,
        layer_count=layer_count,
        direct_element_count=direct_element_count,
        tag_attributes=normalized,
        warnings=tuple(warnings),
    )
