from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.id_engine import inspect_tree_ids
from g_file_studio.engines.id_rule_engine import normalize_tree_ids_strict, scan_tree_against_rules
from g_file_studio.models import BasicOutputConflictAction, IdAction, IdSettings, ProcessingResult
from g_file_studio.processors.common import LogCallback, ProgressCallback, discover_g_inputs
from g_file_studio.services.id_rule_service import IdRuleService
from g_file_studio.services.output_naming import marked_output_name
from g_file_studio.services.user_settings_service import UserSettingsService


def process_ids(settings: IdSettings, log: LogCallback, progress: ProgressCallback) -> ProcessingResult:
    files = discover_g_inputs(settings.source_path, settings.input_mode)
    if not files:
        raise ValueError("没有找到可处理的 G 文件。")

    rules = IdRuleService().load_rules()
    strict_existing = UserSettingsService().get_bool("id_rules/global_strict", True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    warnings: list[str] = []
    duplicate_kinds = 0
    repaired_count = 0
    new_types: set[str] = set()
    changed_types: set[str] = set()

    for index, input_path in enumerate(files, 1):
        try:
            tree = ET.parse(input_path)
            report_lines = [f"ID 检查与修复报告", f"文件：{input_path}", ""]
            scan = scan_tree_against_rules(tree, input_path, rules)
            report_lines.append(f"匹配模板类型：{len(scan.matched_tags)}")
            if scan.new_rule_candidates or scan.unknown_uninferable:
                report_lines.append("发现未配置模板类型：" + ", ".join(sorted({x.tag for x in [*scan.new_rule_candidates, *scan.unknown_uninferable]})))
            if scan.changed_formats:
                report_lines.append("发现格式不符类型：" + ", ".join(sorted({x.tag for x in scan.changed_formats})))
            for item in scan.new_rule_candidates:
                new_types.add(item.tag)
                log(
                    f"[新 ID 类型] {input_path.name}：<{item.tag}> 尚未加入模板；"
                    f"候选前缀 {item.prefix}（需人工确认），样本：{', '.join(item.sample_ids)}"
                )
            for item in scan.unknown_uninferable:
                new_types.add(item.tag)
                log(
                    f"[新 ID 类型] {input_path.name}：<{item.tag}> 尚未加入模板，且样本不足以可靠推断格式；"
                    f"样本：{', '.join(item.sample_ids)}"
                )
            for item in scan.changed_formats:
                changed_types.add(item.tag)
                rule = rules.get(item.tag)
                log(
                    f"[ID 格式变化] {input_path.name}：<{item.tag}> 当前模板 "
                    f"要求前缀 {rule.prefix}、总位数 {rule.total_length}，但发现：{', '.join(item.sample_ids)}。"
                    + ("执行修复时将严格按当前模板强制更新这些 ID。" if strict_existing else "全局强制约束已关闭：这些已有格式不符 ID 将保留不变。")
                )

            inspection = inspect_tree_ids(tree, input_path)
            duplicate_kinds += len(inspection.duplicate_groups)
            report_lines.append(f"重复 ID 组：{len(inspection.duplicate_groups)}")
            if inspection.duplicate_groups:
                for group in inspection.duplicate_groups:
                    log(f"[重复 ID] {input_path.name}：{group.value} × {group.count}；类型：{', '.join(group.tags)}")
            else:
                log(f"[ID 检查] {input_path.name}：未发现重复 ID。")

            if settings.action == IdAction.CHECK:
                report_path = settings.output_dir / f"{input_path.stem}.id-report.txt"
                report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
                outputs.append(report_path)
                continue

            repair = normalize_tree_ids_strict(tree, input_path, rules, repair_invalid_formats=strict_existing)
            if repair.final_duplicate_count:
                raise ValueError("严格模板修复后仍存在重复 ID。")
            repaired_count += repair.changed_element_ids
            for tag, old_id, new_id, reason in repair.changes:
                log(f"[ID 强制修复] <{tag}> {old_id} → {new_id}（{reason}；严格按模板）")
            if repair.format_fixed_count:
                log(f"[ID 模板修复] {input_path.name}：强制修复格式不符 ID {repair.format_fixed_count} 个。")
            report_lines.append(f"修复 ID：{repair.changed_element_ids}")
            report_lines.append(f"其中格式修复：{repair.format_fixed_count}")
            report_lines.append(f"其中重复修复：{repair.duplicate_fixed_count}")
            for tag, old_id, new_id, reason in repair.changes:
                report_lines.append(f"<{tag}> {old_id} -> {new_id} ({reason})")

            output_name = input_path.name
            if settings.output_conflict_action == BasicOutputConflictAction.TIMESTAMP and settings.task_timestamp:
                output_name = marked_output_name(input_path.name, f"ID-{settings.task_timestamp}")
            output_path = settings.output_dir / output_name
            settings.output_dir.mkdir(parents=True, exist_ok=True)
            if hasattr(ET, "indent"):
                ET.indent(tree, space="    ")
            tmp = output_path.with_name(output_path.name + ".tmp")
            tree.write(tmp, encoding="utf-8", xml_declaration=True)
            ET.parse(tmp)
            os.replace(tmp, output_path)
            outputs.append(output_path)
            report_path = settings.output_dir / f"{input_path.stem}.id-report.txt"
            report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
            outputs.append(report_path)
        except Exception as exc:
            warnings.append(f"{input_path.name}: {exc}")
            log(f"[ID 处理失败] {input_path.name}：{exc}")
        if progress:
            progress(round(index * 100 / len(files)))

    return ProcessingResult(
        success=not warnings,
        output_files=outputs,
        warnings=warnings,
        statistics={
            "scanned_file_count": len(files),
            "duplicate_id_kind_count": duplicate_kinds,
            "repaired_id_count": repaired_count,
            "new_id_type_count": len(new_types),
            "changed_id_format_type_count": len(changed_types),
        },
    )
