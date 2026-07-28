from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from g_file_studio.models import BasicSettings, ProcessingResult
from g_file_studio.processors.common import LogCallback, ProgressCallback

REFERENCE_LIST_ATTRIBUTES = ("link", "node_area")
REFERENCE_SINGLE_ATTRIBUTES = ("p_FatherObjId",)


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _iter_graph_elements(root: ET.Element) -> Iterable[ET.Element]:
    for element in root.iter():
        if element is not root:
            yield element


def _collect_subtree_ids(element: ET.Element) -> set[str]:
    result: set[str] = set()
    for current in element.iter():
        value = (current.get("id") or "").strip()
        if value:
            result.add(value)
    return result


def _remove_reference_groups(value: str, removed_ids: set[str]) -> tuple[str, int]:
    """清理 link/node_area 中第三段 ID 指向已删除图元的分组。"""
    if not value or not removed_ids:
        return value, 0

    kept: list[str] = []
    removed_count = 0
    for group in value.split(";"):
        parts = group.split(",", 2)
        if len(parts) >= 3 and parts[2].strip() in removed_ids:
            removed_count += 1
            continue
        kept.append(group)
    return ";".join(kept), removed_count


def _clean_removed_references(layer: ET.Element, removed_ids: set[str]) -> tuple[int, int]:
    """删除图元后，仅在当前 Layer 范围内清理仍保留图元中的真实引用。"""
    if not removed_ids:
        return 0, 0

    remaining_ids = {
        value
        for element in layer.iter()
        if (value := (element.get("id") or "").strip())
    }
    truly_removed_ids = removed_ids - remaining_ids
    if not truly_removed_ids:
        return 0, 0

    removed_groups = 0
    cleared_single = 0
    for element in _iter_graph_elements(layer):
        for attribute in REFERENCE_LIST_ATTRIBUTES:
            value = element.get(attribute)
            if value is None:
                continue
            new_value, count = _remove_reference_groups(value, truly_removed_ids)
            if count:
                element.set(attribute, new_value)
                removed_groups += count

        for attribute in REFERENCE_SINGLE_ATTRIBUTES:
            value = (element.get(attribute) or "").strip()
            if value and value in truly_removed_ids:
                element.set(attribute, "")
                cleared_single += 1

    return removed_groups, cleared_single


def _validate_rules(settings: BasicSettings) -> None:
    if settings.replace_attribute:
        if not settings.replace_target_tag.strip():
            raise ValueError("启用‘替换元素属性值’后，元素标签不能为空。")
        if not settings.replace_target_attribute.strip():
            raise ValueError("启用‘替换元素属性值’后，属性名不能为空。")

    if settings.delete_matching_element:
        if not settings.delete_target_tag.strip():
            raise ValueError("启用‘删除匹配元素’后，元素标签不能为空。")
        if not settings.delete_target_attribute.strip():
            raise ValueError("启用‘删除匹配元素’后，属性名不能为空。")


def _process_layer(
    layer: ET.Element,
    settings: BasicSettings,
) -> tuple[int, int, set[str]]:
    """只处理 Layer 的直接子元素。

    删除和属性替换都不会递归进入图元子树，也不会触碰 G、Theme、Layer
    本身或 Layer 之外的其他 XML 内容。删除完成后，仅在当前 Layer 范围内
    清理指向已删除真实图元的引用。
    """
    replaced = 0
    removed_matching = 0
    removed_ids: set[str] = set()

    replace_tag = settings.replace_target_tag.strip()
    replace_attribute = settings.replace_target_attribute.strip()
    delete_tag = settings.delete_target_tag.strip()
    delete_attribute = settings.delete_target_attribute.strip()

    # 用户规则明确限定为 Layer 直属子元素，因此这里不递归。
    for element in list(layer):
        tag = _local_name(element.tag)

        # 删除规则优先：标签、属性名、属性值全部精确匹配时，
        # 删除整个直属图元及其子树。
        if (
            settings.delete_matching_element
            and tag == delete_tag
            and element.get(delete_attribute) == settings.delete_target_value
        ):
            removed_ids.update(_collect_subtree_ids(element))
            layer.remove(element)
            removed_matching += 1
            continue

        if (
            settings.replace_attribute
            and tag == replace_tag
            and element.get(replace_attribute) == settings.replace_old_value
        ):
            element.set(replace_attribute, settings.replace_new_value)
            replaced += 1

    return replaced, removed_matching, removed_ids


def process_basic(
    settings: BasicSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    _validate_rules(settings)

    if not settings.input_dir.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{settings.input_dir}")
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        (
            path
            for path in settings.input_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".g"
        ),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        raise FileNotFoundError(f"输入目录中没有 .g 文件：{settings.input_dir}")

    outputs: list[Path] = []
    total_replaced = 0
    total_removed_matching = 0
    total_removed_reference_groups = 0
    total_cleared_single_references = 0

    for index, input_path in enumerate(files, 1):
        output_path = settings.output_dir / input_path.name
        tree = ET.parse(input_path)
        root = tree.getroot()

        replaced = 0
        removed_matching = 0
        removed_reference_groups = 0
        cleared_single_references = 0

        # 只处理 G 根节点的直属 Layer；Theme 或其他位置即使出现同名元素也不处理。
        layers = [child for child in list(root) if _local_name(child.tag) == "Layer"]
        if not layers:
            raise ValueError(f"文件 {input_path.name} 的 G 根节点下没有直属 Layer。")

        for layer in layers:
            one_replaced, one_removed, one_removed_ids = _process_layer(layer, settings)
            replaced += one_replaced
            removed_matching += one_removed

            groups, singles = _clean_removed_references(layer, one_removed_ids)
            removed_reference_groups += groups
            cleared_single_references += singles

        if hasattr(ET, "indent"):
            ET.indent(tree, space="    ")

        tmp_path = output_path.with_name(output_path.name + ".tmp")
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
        ET.parse(tmp_path)
        os.replace(tmp_path, output_path)

        outputs.append(output_path)
        total_replaced += replaced
        total_removed_matching += removed_matching
        total_removed_reference_groups += removed_reference_groups
        total_cleared_single_references += cleared_single_references

        log(
            f"✓ {input_path.name}：属性替换 {replaced} 处，"
            f"匹配元素删除 {removed_matching} 个，"
            f"清理引用分组 {removed_reference_groups} 个，"
            f"清空父引用 {cleared_single_references} 个"
        )
        if progress:
            progress(round(index * 100 / len(files)))

    return ProcessingResult(
        success=True,
        output_files=outputs,
        statistics={
            "file_count": len(outputs),
            "replaced_attribute_count": total_replaced,
            "removed_matching_element_count": total_removed_matching,
            "removed_reference_group_count": total_removed_reference_groups,
            "cleared_single_reference_count": total_cleared_single_references,
        },
    )
