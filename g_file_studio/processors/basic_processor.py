from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from g_file_studio.engines.color_engine import ColorRule, apply_line_colors
from g_file_studio.engines.id_engine import inspect_tree_ids, repair_tree_duplicate_ids
from g_file_studio.engines.rmu_group_engine import group_rmu_tree, ungroup_rmu_tree
from g_file_studio.models import (
    BasicIdAction,
    BasicOutputConflictAction,
    BasicSettings,
    ProcessingResult,
    RmuAction,
)
from g_file_studio.processors.common import LogCallback, ProgressCallback, discover_g_inputs
from g_file_studio.services.output_naming import (
    make_task_timestamp,
    marked_output_name,
    strip_g_suffix,
)

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
    """只处理 Layer 的直接子元素。"""
    replaced = 0
    removed_matching = 0
    removed_ids: set[str] = set()

    replace_tag = settings.replace_target_tag.strip()
    replace_attribute = settings.replace_target_attribute.strip()
    delete_tag = settings.delete_target_tag.strip()
    delete_attribute = settings.delete_target_attribute.strip()

    for element in list(layer):
        tag = _local_name(element.tag)

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


def _log_id_inspection(input_path: Path, tree: ET.ElementTree, log: LogCallback) -> tuple[int, int]:
    inspection = inspect_tree_ids(tree, input_path)
    duplicate_kinds = len(inspection.duplicate_groups)
    duplicate_elements = inspection.duplicate_element_count
    log(
        f"[ID检查] {input_path.name}：Layer 直属图元 {inspection.direct_element_count} 个，"
        f"带 ID 图元 {inspection.element_with_id_count} 个，重复 ID {duplicate_kinds} 种，"
        f"需重新分配 {duplicate_elements} 个图元。"
    )
    for group in inspection.duplicate_groups:
        tags = ", ".join(group.tags)
        log(f"  - ID {group.value} 出现 {group.count} 次；元素类型：{tags}")
    if not inspection.has_duplicates:
        log(f"[ID检查] {input_path.name}：未发现重复 ID。")
    return duplicate_kinds, duplicate_elements


def _effective_rmu_action(settings: BasicSettings) -> RmuAction:
    if settings.rmu_action != RmuAction.NONE:
        return settings.rmu_action
    if settings.group_rmu_elements:
        return RmuAction.GROUP
    return RmuAction.NONE


def _color_rules(settings: BasicSettings) -> list[ColorRule]:
    rules: list[ColorRule] = []
    if settings.change_feedline_color:
        rules.append(ColorRule("FeedLine", "馈线", settings.feedline_color))
    if settings.change_connectline_color:
        rules.append(ColorRule("ConnectLine", "连接线", settings.connectline_color))
    if settings.change_busdis_color:
        rules.append(ColorRule("BusDis", "配网母线", settings.busdis_color))
    if settings.change_bus_color:
        rules.append(ColorRule("Bus", "主网母线", settings.bus_color))
    return rules


def _unique_timestamp_path(output_dir: Path, input_name: str, timestamp: str) -> Path:
    name = marked_output_name(input_name, "", timestamp, append_timestamp=True)
    candidate = output_dir / name
    if not candidate.exists():
        return candidate
    stem, suffix = strip_g_suffix(candidate.name)
    counter = 2
    while True:
        alternative = candidate.with_name(f"{stem}-{counter}{suffix}")
        if not alternative.exists():
            return alternative
        counter += 1


def _output_path_for(
    input_path: Path,
    settings: BasicSettings,
    timestamp: str,
) -> Path:
    if settings.output_conflict_action == BasicOutputConflictAction.TIMESTAMP:
        return _unique_timestamp_path(settings.output_dir, input_path.name, timestamp)
    return settings.output_dir / input_path.name


def process_basic(
    settings: BasicSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """统一执行基础处理页面选择的全部操作。"""
    _validate_rules(settings)

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    files = discover_g_inputs(settings.source_path, settings.input_mode)
    timestamp = settings.task_timestamp.strip() or make_task_timestamp()
    rmu_action = _effective_rmu_action(settings)
    color_rules = _color_rules(settings)

    outputs: list[Path] = []
    failed: list[str] = []
    total_replaced = 0
    total_removed_matching = 0
    total_removed_reference_groups = 0
    total_cleared_single_references = 0
    total_duplicate_kinds = 0
    total_duplicate_elements = 0
    total_repaired_ids = 0
    total_rects = 0
    total_rmu_groups = 0
    total_rmu_members = 0
    total_rmu_ungrouped = 0
    total_rmu_released_members = 0
    total_rmu_lowered_rects = 0
    total_color_changed = 0
    total_dynamic_colors = 0

    if settings.output_conflict_action == BasicOutputConflictAction.TIMESTAMP:
        log(f"[输出策略] 检测到输出冲突，本批文件统一自动添加时间戳 {timestamp}。")
    else:
        log("[输出策略] 使用原文件名；如目标已存在，将通过临时文件验证后安全覆盖。")

    for index, input_path in enumerate(files, 1):
        try:
            output_path = _output_path_for(input_path, settings, timestamp)
            tree = ET.parse(input_path)
            root = tree.getroot()

            replaced = 0
            removed_matching = 0
            removed_reference_groups = 0
            cleared_single_references = 0

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

            if rmu_action == RmuAction.GROUP:
                grouping = group_rmu_tree(tree, input_path)
                total_rects += grouping.rect_count
                total_rmu_groups += grouping.rebuilt_group_count
                total_rmu_members += grouping.grouped_member_count
                log(
                    f"[环网柜组合] {input_path.name}：发现 <rect> {grouping.rect_count} 个，"
                    f"原环网柜 Merge {grouping.previous_rmu_merge_count} 个，保留其他业务 Merge "
                    f"{grouping.preserved_non_rmu_merge_count} 个，重建环网柜组合 "
                    f"{grouping.rebuilt_group_count} 个。"
                )
                for warning in grouping.warnings:
                    log(f"[环网柜组合告警] {warning}")
                for change in grouping.changes:
                    action_text = "复用原 Merge" if change.reused_existing_merge else "新建 Merge"
                    log(
                        f"  - rect ID {change.rect_id or '<无ID>'}：{action_text} "
                        f"ID {change.merge_id}，组合框内直属图元 {change.member_count} 个；"
                        "框外图元不组合。"
                    )
                if grouping.rect_count == 0:
                    log(f"[环网柜组合] {input_path.name}：未发现直属 <rect>，无需组合。")
            elif rmu_action == RmuAction.UNGROUP:
                ungrouping = ungroup_rmu_tree(tree, input_path)
                total_rmu_ungrouped += ungrouping.removed_rmu_merge_count
                total_rmu_released_members += ungrouping.released_member_count
                total_rmu_lowered_rects += ungrouping.lowered_rect_count
                log(
                    f"[取消环网柜组合] {input_path.name}：删除环网柜 Merge "
                    f"{ungrouping.removed_rmu_merge_count} 个，释放成员 "
                    f"{ungrouping.released_member_count} 个，将环网柜外框下移到设备下层 "
                    f"{ungrouping.lowered_rect_count} 个，保留其他业务 Merge "
                    f"{ungrouping.preserved_non_rmu_merge_count} 个。"
                )
                for merge_id in ungrouping.removed_merge_ids:
                    log(f"  - 已删除环网柜 Merge ID {merge_id or '<无ID>'}。")
                for rect_id in ungrouping.lowered_rect_ids:
                    log(
                        f"  - rect ID {rect_id or '<无ID>'} 已移动到柜内设备之前；"
                        "仅调整图层顺序，坐标和业务属性不变。"
                    )
                for warning in ungrouping.warnings:
                    log(f"[取消环网柜组合告警] {warning}")

            if color_rules:
                color_result = apply_line_colors(tree, input_path, color_rules)
                total_color_changed += color_result.total_changed
                total_dynamic_colors += color_result.total_dynamic_color
                labels = {rule.element_tag: rule.display_name for rule in color_rules}
                colors = {rule.element_tag: rule.color.upper() for rule in color_rules}
                log(f"[颜色处理] {input_path.name}：")
                for rule in color_rules:
                    count = color_result.changed_by_tag.get(rule.element_tag, 0)
                    dynamic = color_result.dynamic_color_by_tag.get(rule.element_tag, 0)
                    line = (
                        f"  - {labels[rule.element_tag]} <{rule.element_tag}>：修改 {count} 个，"
                        f"颜色 {colors[rule.element_tag]}"
                    )
                    if dynamic:
                        line += f"；其中 {dynamic} 个启用了动态颜色，运行时可能被动态规则覆盖"
                    log(line)
                log(f"[颜色处理] {input_path.name}：合计修改 {color_result.total_changed} 个图元。")

            if settings.id_action == BasicIdAction.CHECK:
                kinds, elements = _log_id_inspection(input_path, tree, log)
                total_duplicate_kinds += kinds
                total_duplicate_elements += elements
            elif settings.id_action == BasicIdAction.REPAIR:
                kinds, elements = _log_id_inspection(input_path, tree, log)
                total_duplicate_kinds += kinds
                total_duplicate_elements += elements
                repair = repair_tree_duplicate_ids(tree, input_path)
                total_repaired_ids += repair.changed_element_ids
                if repair.changed_element_ids:
                    log(
                        f"[ID修复] {input_path.name}：重新分配 {repair.changed_element_ids} 个重复图元 ID。"
                    )
                    for tag, old_id, new_id in repair.changes:
                        pattern = repair.pattern_sources.get(tag)
                        rule = (
                            f"参考同类 <{tag}>：前缀 {pattern.prefix}、固定总位数 {pattern.total_length}"
                            if pattern is not None
                            else "同类格式样本不足，使用原 ID 向上递增规则"
                        )
                        log(f"  - <{tag}> {old_id} → {new_id}；{rule}")
                else:
                    log(f"[ID修复] {input_path.name}：没有重复 ID，无需修改。")
                log(
                    f"[ID验证] {input_path.name}：修复后重复 ID {repair.final_duplicate_count} 种。"
                )
                if repair.final_duplicate_count:
                    raise ValueError("重复 ID 修复后仍存在冲突。")

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
                f"✓ {input_path.name}：属性替换 {replaced} 处，匹配元素删除 {removed_matching} 个，"
                f"清理引用分组 {removed_reference_groups} 个，清空父引用 "
                f"{cleared_single_references} 个；输出 {output_path.name}"
            )
        except Exception as exc:
            failed.append(f"{input_path.name}: {exc}")
            log(f"[基础处理失败] {input_path.name}：{exc}")

        if progress:
            progress(round(index * 100 / len(files)))

    log(
        f"[基础处理汇总] 输入 {len(files)} 个文件，成功 {len(outputs)} 个，失败 {len(failed)} 个；"
        f"重复 ID {total_duplicate_kinds} 种，需处理图元 {total_duplicate_elements} 个，"
        f"实际修复 {total_repaired_ids} 个；环网柜 rect {total_rects} 个，重建组合 "
        f"{total_rmu_groups} 个，取消组合 {total_rmu_ungrouped} 个，外框下移 "
        f"{total_rmu_lowered_rects} 个；颜色修改 {total_color_changed} 个图元。"
    )

    return ProcessingResult(
        success=not failed,
        output_files=outputs,
        warnings=failed,
        statistics={
            "input_mode": settings.input_mode.value,
            "source_path": str(settings.source_path),
            "file_count": len(outputs),
            "failed_file_count": len(failed),
            "replaced_attribute_count": total_replaced,
            "removed_matching_element_count": total_removed_matching,
            "removed_reference_group_count": total_removed_reference_groups,
            "cleared_single_reference_count": total_cleared_single_references,
            "duplicate_id_kind_count": total_duplicate_kinds,
            "duplicate_element_count": total_duplicate_elements,
            "repaired_id_count": total_repaired_ids,
            "rmu_rect_count": total_rects,
            "rmu_group_count": total_rmu_groups,
            "rmu_grouped_member_count": total_rmu_members,
            "rmu_ungrouped_count": total_rmu_ungrouped,
            "rmu_released_member_count": total_rmu_released_members,
            "rmu_lowered_rect_count": total_rmu_lowered_rects,
            "color_changed_count": total_color_changed,
            "dynamic_color_warning_count": total_dynamic_colors,
        },
    )
