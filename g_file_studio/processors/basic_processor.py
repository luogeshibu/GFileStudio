from __future__ import annotations

import csv
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from g_file_studio.engines.color_engine import ColorRule, apply_line_colors
from g_file_studio.engines.connection_engine import repair_tree_connections
from g_file_studio.engines.feeder_title_engine import move_feeder_titles_above_buses
from g_file_studio.engines.icon_upgrade_engine import analyze_icon_pairs, apply_icon_upgrade
from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree, group_rmu_tree, ungroup_rmu_tree
from g_file_studio.engines.rmu_identification_engine import identify_rmus
from g_file_studio.models import (
    BasicOutputConflictAction,
    BasicSettings,
    ProcessingResult,
    RmuAction,
    RmuLedgerInputMode,
)
from g_file_studio.processors.common import LogCallback, ProgressCallback, discover_g_inputs, enforce_confirmed_id_rules
from g_file_studio.services.output_naming import (
    make_task_timestamp,
    strip_g_suffix,
)
from g_file_studio.services.html_report_selection import selection_bar, selection_cell, selection_header, selection_script, selection_style
from g_file_studio.services.rmu_ledger_service import (
    GraphicRmuRow,
    compare_ledger,
    load_ledger_file,
    parse_name_list,
    parse_pasted_table,
    write_comparison_reports,
)

REFERENCE_LIST_ATTRIBUTES = ("link", "node_area")
REFERENCE_SINGLE_ATTRIBUTES = ("p_FatherObjId",)


def _write_rmu_processing_report(output_dir: Path, rows: list[dict[str, object]]) -> tuple[Path, Path]:
    """Write one fixed RMU graphic-processing report for the latest run."""
    from html import escape

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rmu-graphic-processing-report.csv"
    html_path = output_dir / "rmu-graphic-processing-report.html"
    headers = [
        "File", "Action", "RMURectCount", "GroupedCount", "UngroupedCount",
        "SmartMatched", "SmartChanged", "SmrTextCount", "SmrMatched", "SmrChanged",
        "ChannelStatusFound", "ChannelStatusMoved", "BusFrameRemoved", "TitleMoved", "Warnings",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])

    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row.get(h, '')))}</td>" for h in headers)
        body.append("<tr>" + selection_cell() + cells + "</tr>")
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>环网柜图元处理报告</title>"
        "<style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;margin:24px;color:#1f2937}"
        "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left}"
        "th{background:#e8f3ef;position:sticky;top:0}" + selection_style() + "</style></head><body>"
        "<h2>环网柜图元处理报告</h2><p>本报告记录本次启用的环网柜图元操作；再次执行会覆盖上一份同类报告。</p>"
        + selection_bar() + "<table><thead><tr>" + selection_header()
        + "".join(f"<th>{escape(h)}</th>" for h in headers)
        + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
        + selection_script() + "</body></html>",
        encoding="utf-8",
    )
    return csv_path, html_path


def _write_rmu_summary_reports(
    output_dir: Path, rows: list[GraphicRmuRow], *, intelligent_classification_enabled: bool = True
) -> tuple[Path, Path]:
    """Write one aggregate fixed RMU information summary report for the latest run."""
    from html import escape

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rmu-summary-report.csv"
    html_path = output_dir / "rmu-summary-report.html"
    headers = [
        "File", "RMUName", "RMUType", "IntelligentRMU", "IntelligentSource",
        "Confidence", "Duplicate", "RectID", "RectX", "RectY", "RectW", "RectH", "Warnings",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([
                row.file_name, row.name, row.rmu_type, row.intelligent, row.intelligent_source,
                row.confidence, row.duplicate, row.rect_id, row.rect_x, row.rect_y, row.rect_w, row.rect_h, row.warnings,
            ])

    def row_class(row: GraphicRmuRow) -> str:
        if row.duplicate == "YES" or not row.name or not row.rmu_type:
            return "bad"
        if row.confidence not in {"高", "HIGH", "High"}:
            return "warn"
        return "good"

    body = []
    for row in rows:
        vals = [
            row.file_name, row.name, row.rmu_type, row.intelligent, row.intelligent_source,
            row.confidence, row.duplicate, row.rect_id, row.rect_x, row.rect_y, row.rect_w, row.rect_h, row.warnings,
        ]
        body.append(
            f"<tr class='{row_class(row)}'>" + selection_cell()
            + "".join(f"<td>{escape(str(v))}</td>" for v in vals) + "</tr>"
        )
    total = len(rows)
    duplicates = sum(1 for row in rows if row.duplicate == "YES")
    intelligent = sum(1 for row in rows if row.intelligent == "YES")
    ordinary = sum(1 for row in rows if row.intelligent == "NO") if intelligent_classification_enabled else 0
    unnamed = sum(1 for row in rows if not row.name)
    untyped = sum(1 for row in rows if not row.rmu_type or row.rmu_type == "0L0T")
    warning_rows = sum(1 for row in rows if row.confidence not in {"高", "HIGH", "High"} and row.name and row.rmu_type and row.duplicate != "YES")
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>RMU 信息汇总报告</title>"
        "<style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;margin:24px;color:#1f2937}"
        ".summary{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.badge{padding:7px 10px;border:1px solid #cbd5e1;border-radius:6px}"
        "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left}"
        "th{background:#e8f3ef;position:sticky;top:0}tr.good td{background:#dcfce7}tr.warn td{background:#fef9c3}tr.bad td{background:#fee2e2}"
        + selection_style() + "</style></head><body><h2>RMU 信息汇总报告</h2>"
        f"<div class='summary'><div class='badge'>RMU 总数：<b>{total}</b></div>"
        + (f"<div class='badge'>智能环网柜：<b>{intelligent}</b></div><div class='badge'>普通环网柜：<b>{ordinary}</b></div>" if intelligent_classification_enabled else "<div class='badge'>智能分类：<b>未启用</b></div>")
        + f"<div class='badge'>重复名称/ID 行：<b>{duplicates}</b></div>"
        + f"<div class='badge'>名称未识别：<b>{unnamed}</b></div>"
        + f"<div class='badge'>柜型未识别：<b>{untyped}</b></div>"
        + f"<div class='badge'>中/低置信度待确认：<b>{warning_rows}</b></div></div>"
        "<p>绿色=高置信度且完整；黄色=需要确认；红色=重复、名称/柜型未识别。</p>"
        + selection_bar() + "<table><thead><tr>" + selection_header()
        + "".join(f"<th>{escape(h)}</th>" for h in headers)
        + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
        + selection_script() + "</body></html>",
        encoding="utf-8",
    )
    return csv_path, html_path



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

    if settings.delete_attribute:
        if not settings.delete_attribute_target_tag.strip():
            raise ValueError("启用‘删除元素属性’后，元素标签不能为空。")
        if not settings.delete_attribute_name.strip():
            raise ValueError("启用‘删除元素属性’后，要删除的属性名不能为空。")

    if settings.delete_matching_element:
        if not settings.delete_target_tag.strip():
            raise ValueError("启用‘删除匹配元素’后，元素标签不能为空。")
        if not settings.delete_target_attribute.strip():
            raise ValueError("启用‘删除匹配元素’后，属性名不能为空。")

    if settings.identify_rmu_name_and_type and not any((
        settings.rmu_name_top, settings.rmu_name_bottom, settings.rmu_name_left, settings.rmu_name_right
    )):
        raise ValueError("启用环网柜名称与柜型识别后，柜名位置至少选择一个方向。")

    if settings.compare_rmu_ledger and not settings.identify_rmu_name_and_type:
        raise ValueError("启用 RMU 台账对比前，必须先启用 RMU 信息汇总。")
    if settings.compare_rmu_ledger:
        if settings.rmu_ledger_input_mode == RmuLedgerInputMode.FILE:
            if settings.rmu_ledger_file is None:
                raise ValueError("请选择 RMU 台账 Excel/CSV 文件。")
        elif not settings.rmu_ledger_text.strip():
            raise ValueError("RMU 台账输入内容不能为空。")

    if settings.upgrade_icon_geometry:
        analysis = analyze_icon_pairs(settings.old_icon_files, settings.new_icon_files)
        problems: list[str] = []
        if analysis.missing_old:
            problems.append("缺少旧图元：" + ", ".join(analysis.missing_old))
        if analysis.missing_new:
            problems.append("缺少新图元：" + ", ".join(analysis.missing_new))
        if analysis.incompatible:
            problems.append("不兼容图元：" + " | ".join(analysis.incompatible))
        if not analysis.rules:
            problems.append("没有可用的旧/新图元配对。")
        if problems:
            raise ValueError("图元版本升级适配检查未通过：" + "；".join(problems))


def _write_smr_frame_reports(output_dir: Path, rows: list[dict[str, object]]) -> tuple[Path, Path]:
    from html import escape
    csv_path = output_dir / "rmu-smr-frame-report.csv"
    html_path = output_dir / "rmu-smr-frame-report.html"
    headers = ["File","SMRTextID","SMRX","SMRY","RectID","RectX","RectY","RectW","RectH","Distance","OldColor","NewColor","Result"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers); writer.writeheader(); writer.writerows(rows)
    trs=[]
    for row in rows:
        cells="".join("<td>%s</td>" % escape(str(row.get(h,""))) for h in headers)
        trs.append("<tr>%s%s</tr>" % (selection_cell(), cells))
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>RMU SMR 外框处理报告</title><style>" + selection_style() + "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left}</style></head><body><h2>RMU SMR 外框处理报告</h2><p>本报告每次执行覆盖上一份同类报告。</p>" + selection_bar() + "<table><thead><tr>" + selection_header() + "".join("<th>%s</th>" % escape(h) for h in headers) + "</tr></thead><tbody>" + "".join(trs) + "</tbody></table>" + selection_script() + "</body></html>")
    html_path.write_text(html, encoding="utf-8")
    return csv_path, html_path


def _process_layer(
    layer: ET.Element,
    settings: BasicSettings,
) -> tuple[int, int, int, set[str]]:
    """只处理 Layer 的直接子元素。"""
    replaced = 0
    deleted_attributes = 0
    removed_matching = 0
    removed_ids: set[str] = set()

    replace_tag = settings.replace_target_tag.strip()
    replace_attribute = settings.replace_target_attribute.strip()
    delete_attr_tag = settings.delete_attribute_target_tag.strip()
    delete_attr_name = settings.delete_attribute_name.strip()
    delete_tag = settings.delete_target_tag.strip()
    delete_attribute = settings.delete_target_attribute.strip()

    for element in list(layer):
        tag = _local_name(element.tag)

        if (
            settings.delete_attribute
            and tag == delete_attr_tag
            and delete_attr_name in element.attrib
        ):
            del element.attrib[delete_attr_name]
            deleted_attributes += 1

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

    return replaced, deleted_attributes, removed_matching, removed_ids


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


def _output_path_for(
    input_path: Path,
    settings: BasicSettings,
    timestamp: str,
) -> Path:
    # 一对一处理统一保留源 G 文件名。每次运行使用独立 workspace 目录，
    # 因此不再通过时间戳修改 G 文件名。
    return settings.output_dir / input_path.name


def _rmu_duplicate_names(identification) -> tuple[dict[str, int], set[str]]:
    counts: dict[str, int] = {}
    for item in identification.items:
        name = (item.name or "").strip()
        if not name:
            continue
        key = name.casefold()
        counts[key] = counts.get(key, 0) + 1
    duplicates = {key for key, count in counts.items() if count > 1}
    return counts, duplicates


def _write_rmu_csv(output_path: Path, identification) -> Path:
    stem, _suffix = strip_g_suffix(output_path.name)
    csv_path = output_path.with_name(f"{stem}.rmu.csv")
    _counts, duplicates = _rmu_duplicate_names(identification)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "CabinetName", "CabinetType", "TypeSource", "TextYQType", "DevrefType",
            "TypeCrossCheck", "TypeValidationStatus", "TypeCrossNote",
            "LCount", "TCount", "IntelligentRMU", "IntelligentSource",
            "NamePosition", "Confidence", "Duplicate", "RectID",
            "RectX", "RectY", "RectW", "RectH", "Warnings",
        ])
        for item in identification.items:
            name_key = (item.name or "").strip().casefold()
            duplicate = "YES" if name_key and name_key in duplicates else "NO"
            writer.writerow([
                item.name, item.rmu_type, getattr(item, "type_source", ""), getattr(item, "text_yq_type", ""),
                getattr(item, "devref_type", ""), getattr(item, "type_cross_check", "N/A"),
                getattr(item, "type_validation_status", "WARN"), getattr(item, "type_cross_note", ""),
                item.l_count, item.t_count, item.smart_count, getattr(item, "smart_source", ""),
                item.name_position, item.confidence, duplicate, item.rect_id,
                f"{item.rect_x:g}", f"{item.rect_y:g}", f"{item.rect_w:g}", f"{item.rect_h:g}",
                " | ".join(item.warnings),
            ])
    return csv_path


def _write_rmu_html(output_path: Path, identification) -> Path:
    from html import escape

    stem, _suffix = strip_g_suffix(output_path.name)
    html_path = output_path.with_name(f"{stem}.rmu.html")
    counts, duplicates = _rmu_duplicate_names(identification)

    high_count = sum(
        1 for item in identification.items
        if item.confidence == "高" and (item.name or "").strip().casefold() not in duplicates
    )
    medium_count = sum(
        1 for item in identification.items
        if item.confidence in {"中", "待确认"} and (item.name or "").strip().casefold() not in duplicates
    )
    unidentified_count = sum(
        1 for item in identification.items if not item.name or item.confidence == "未识别"
    )
    duplicate_row_count = sum(
        1 for item in identification.items
        if (item.name or "").strip() and (item.name or "").strip().casefold() in duplicates
    )
    type_pass_count = sum(1 for item in identification.items if getattr(item, "type_validation_status", "") == "PASS")
    type_warn_count = sum(1 for item in identification.items if getattr(item, "type_validation_status", "") == "WARN")
    type_fail_count = sum(1 for item in identification.items if getattr(item, "type_validation_status", "") == "FAIL")

    def row_class(item) -> str:
        key = (item.name or "").strip().casefold()
        type_status = getattr(item, "type_validation_status", "WARN")
        if (key and key in duplicates) or not item.name or item.confidence == "未识别" or type_status == "FAIL":
            return "bad"
        if type_status == "WARN" or item.confidence in {"中", "待确认"}:
            return "medium"
        if item.confidence == "高":
            return "high"
        return "medium"

    headers = [
        "环网柜名称", "环网柜类型", "类型识别来源", "柜内Y/Q文字类型", "devref类型",
        "类型交叉校验", "柜型校验状态", "柜型交叉校验说明",
        "L数量", "T数量", "智能环网柜", "智能标识来源",
        "柜名位置", "识别置信度", "是否重复", "RectID",
        "RectX", "RectY", "RectW", "RectH", "Warnings",
    ]
    rows: list[str] = []
    for item in identification.items:
        key = (item.name or "").strip().casefold()
        duplicate = "YES" if key and key in duplicates else "NO"
        values = [
            item.name, item.rmu_type, getattr(item, "type_source", ""), getattr(item, "text_yq_type", ""),
            getattr(item, "devref_type", ""), getattr(item, "type_cross_check", "N/A"),
            getattr(item, "type_validation_status", "WARN"), getattr(item, "type_cross_note", ""),
            str(item.l_count), str(item.t_count), str(item.smart_count), getattr(item, "smart_source", ""),
            item.name_position, item.confidence, duplicate, item.rect_id,
            f"{item.rect_x:g}", f"{item.rect_y:g}", f"{item.rect_w:g}", f"{item.rect_h:g}",
            " | ".join(item.warnings),
        ]
        cells = "".join(f"<td>{escape(value)}</td>" for value in values)
        rows.append(f'<tr class="{row_class(item)}">{selection_cell()}{cells}</tr>')

    duplicate_list: list[str] = []
    for key in sorted(duplicates):
        display_name = next(
            (item.name for item in identification.items if (item.name or "").strip().casefold() == key),
            key,
        )
        duplicate_list.append(f"{escape(display_name)} × {counts[key]}")
    duplicate_text = "、".join(duplicate_list) if duplicate_list else "无"

    header_cells = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = "".join(rows)
    html = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\">
<title>{escape(stem)} RMU 信息汇总报告</title>
<style>
body {{ font-family: \"Microsoft YaHei\", Arial, sans-serif; margin: 24px; color: #1f2937; }}
h1 {{ margin: 0 0 16px; font-size: 24px; }}
.summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
.badge {{ border: 1px solid #d1d5db; border-radius: 6px; padding: 7px 10px; background: #f8fafc; }}
.note {{ margin: 10px 0 18px; color: #475569; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #e2e8f0; position: sticky; top: 0; }}
tr.high td {{ background: #dcfce7; }}
tr.medium td {{ background: #fef9c3; }}
tr.bad td {{ background: #fee2e2; }}
{selection_style()}
</style>
</head>
<body>
<h1>RMU 信息汇总报告</h1>
<div class=\"summary\">
  <div class=\"badge\">总环网柜：<b>{len(identification.items)}</b></div>
  <div class=\"badge\">柜名成功：<b>{identification.named_count}</b></div>
  <div class=\"badge\">柜型成功：<b>{identification.typed_count}</b></div>
  <div class=\"badge\">高置信度：<b>{high_count}</b></div>
  <div class=\"badge\">中/待确认：<b>{medium_count}</b></div>
  <div class=\"badge\">未识别：<b>{unidentified_count}</b></div>
  <div class=\"badge\">重复柜名/ID：<b>{len(duplicates)}</b> 个（涉及 {duplicate_row_count} 行）</div>
</div>
<div class=\"note\">颜色：绿色=高置信度；黄色=中等/待确认；红色=未识别或柜名/环网柜 ID 重复。重复项：{duplicate_text}</div>
{selection_bar()}
<table>
<thead><tr>{selection_header()}{header_cells}</tr></thead>
<tbody>{body_rows}</tbody>
</table>
{selection_script()}
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return html_path

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
    icon_analysis = (
        analyze_icon_pairs(settings.old_icon_files, settings.new_icon_files)
        if settings.upgrade_icon_geometry
        else None
    )
    icon_rules = icon_analysis.rules if icon_analysis is not None else {}
    if settings.upgrade_icon_geometry:
        log(f"[图元版本升级] 已加载并验证 {len(icon_rules)} 种旧/新图元配对。")
        for name, rule in sorted(icon_rules.items()):
            log(
                f"  - {name}：{rule.old.width:g}×{rule.old.height:g} → "
                f"{rule.new.width:g}×{rule.new.height:g}；AlignCenter "
                f"{rule.old.align_center} → {rule.new.align_center}；Pins "
                f"{len(rule.old.pins)} → {len(rule.new.pins)}。"
            )

    outputs: list[Path] = []
    failed: list[str] = []
    total_replaced = 0
    total_deleted_attributes = 0
    total_removed_matching = 0
    total_removed_reference_groups = 0
    total_cleared_single_references = 0
    total_rects = 0
    total_rmu_groups = 0
    total_rmu_members = 0
    total_rmu_ungrouped = 0
    total_rmu_released_members = 0
    total_rmu_lowered_rects = 0
    total_color_changed = 0
    total_dynamic_colors = 0
    total_smart_rmu_rects = 0
    total_smart_rmu_frames_changed = 0
    total_smr_texts = 0
    total_smr_matched_rects = 0
    total_smr_frames_changed = 0
    smr_report_rows: list[dict[str, object]] = []
    total_channel_status_rects = 0
    total_channel_status_found = 0
    total_channel_status_moved = 0
    total_channel_status_missing = 0
    total_bus_rect_removed = 0
    total_bus_title_moved = 0
    total_connection_aligned_devices = 0
    total_connection_adjusted_lines = 0
    total_connection_relations = 0
    total_connection_added = 0
    total_connection_updated = 0
    total_connection_removed = 0
    total_connection_changed_elements = 0
    total_connection_changed_attributes = 0
    total_feeder_title_bus_segments = 0
    total_feeder_title_bus_groups = 0
    total_feeder_title_candidates = 0
    total_feeder_title_moved = 0
    total_feeder_title_unchanged = 0
    total_feeder_title_skipped = 0
    total_icon_upgraded_instances = 0
    total_icon_adjusted_lines = 0
    total_icon_already_new = 0
    total_icon_skipped_unknown_size = 0
    total_rmu_identified = 0
    total_rmu_named = 0
    total_rmu_typed = 0
    total_rmu_ambiguous = 0
    total_rmu_csv = 0
    rmu_graphic_rows: list[GraphicRmuRow] = []
    rmu_processing_rows: list[dict[str, object]] = []
    ledger_rows = []
    if settings.compare_rmu_ledger:
        if settings.rmu_ledger_input_mode == RmuLedgerInputMode.FILE:
            ledger_rows = load_ledger_file(settings.rmu_ledger_file)
        elif settings.rmu_ledger_input_mode == RmuLedgerInputMode.PASTE_TABLE:
            ledger_rows = parse_pasted_table(settings.rmu_ledger_text)
        else:
            ledger_rows = parse_name_list(settings.rmu_ledger_text)
        if not ledger_rows:
            raise ValueError("RMU 台账没有解析到任何有效名称。")
        log(f"[RMU台账] 已读取 {len(ledger_rows)} 条台账记录，输入方式：{settings.rmu_ledger_input_mode.value}。")

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
            deleted_attributes = 0
            removed_matching = 0
            removed_reference_groups = 0
            cleared_single_references = 0

            layers = [child for child in list(root) if _local_name(child.tag) == "Layer"]
            if not layers:
                raise ValueError(f"文件 {input_path.name} 的 G 根节点下没有直属 Layer。")

            rmu_identification = None
            if settings.identify_rmu_name_and_type:
                positions = tuple(
                    key for key, enabled in (
                        ("top", settings.rmu_name_top),
                        ("bottom", settings.rmu_name_bottom),
                        ("left", settings.rmu_name_left),
                        ("right", settings.rmu_name_right),
                    ) if enabled
                )
                rmu_identification = identify_rmus(
                    tree, input_path, name_positions=positions, smart_in_type=settings.rmu_smart_in_type
                )
                total_rmu_identified += rmu_identification.cabinet_count
                total_rmu_named += rmu_identification.named_count
                total_rmu_typed += rmu_identification.typed_count
                total_rmu_ambiguous += rmu_identification.ambiguous_name_count
                log(
                    f"[环网柜识别] {input_path.name}：识别环网柜 {rmu_identification.cabinet_count} 个，"
                    f"柜名 {rmu_identification.named_count} 个，柜型 {rmu_identification.typed_count} 个，"
                    f"待确认柜名 {rmu_identification.ambiguous_name_count} 个。"
                )
                for item in rmu_identification.items:
                    name = item.name or "<未识别>"
                    position_label = {"top": "上方", "bottom": "下方", "left": "左侧", "right": "右侧"}.get(item.name_position, item.name_position or "-")
                    log(
                        f"  - rect {item.rect_id or '<无ID>'}：柜名 {name}（{position_label}），"
                        f"类型 {item.rmu_type}，L={item.l_count}，T={item.t_count}，智能={item.smart_count}（{item.smart_source or "-"}），"
                        f"置信度 {item.confidence}。"
                    )
                if settings.identify_rmu_name_and_type:
                    _, duplicate_names = _rmu_duplicate_names(rmu_identification)
                    for item in rmu_identification.items:
                        name_key = (item.name or "").strip().casefold()
                        rmu_graphic_rows.append(GraphicRmuRow(
                            file_name=input_path.name,
                            name=(item.name or "").strip(),
                            rmu_type=(item.rmu_type or "").strip(),
                            intelligent=("YES" if bool(item.smart_count) else "NO") if settings.rmu_smart_in_type else "",
                            intelligent_source=(getattr(item, "smart_source", "") or "") if settings.rmu_smart_in_type else "",
                            confidence=item.confidence or "",
                            duplicate="YES" if name_key and name_key in duplicate_names else "NO",
                            rect_id=item.rect_id or "",
                            rect_x=f"{item.rect_x:g}", rect_y=f"{item.rect_y:g}",
                            rect_w=f"{item.rect_w:g}", rect_h=f"{item.rect_h:g}",
                            warnings=" | ".join(item.warnings),
                        ))
                for warning in rmu_identification.warnings:
                    log(f"[环网柜识别告警] {input_path.name}：{warning}")

            for layer in layers:
                one_replaced, one_deleted_attributes, one_removed, one_removed_ids = _process_layer(layer, settings)
                replaced += one_replaced
                deleted_attributes += one_deleted_attributes
                removed_matching += one_removed

                groups, singles = _clean_removed_references(layer, one_removed_ids)
                removed_reference_groups += groups
                cleared_single_references += singles

            if settings.upgrade_icon_geometry:
                icon_result = apply_icon_upgrade(tree, icon_rules)
                total_icon_upgraded_instances += icon_result.upgraded_instances
                total_icon_adjusted_lines += icon_result.adjusted_lines
                total_icon_already_new += icon_result.already_new_instances
                total_icon_skipped_unknown_size += icon_result.skipped_unknown_size
                log(
                    f"[图元版本升级] {input_path.name}：升级实例 "
                    f"{icon_result.upgraded_instances} 个，调整连接线 "
                    f"{icon_result.adjusted_lines} 条；已是新尺寸 "
                    f"{icon_result.already_new_instances} 个，未知尺寸跳过 "
                    f"{icon_result.skipped_unknown_size} 个。"
                )
                if icon_result.changed_instance_ids:
                    log("  - 升级图元 ID：" + ", ".join(icon_result.changed_instance_ids))
                for warning in icon_result.warnings:
                    log(f"[图元版本升级告警] {input_path.name}：{warning}")

            rmu_processing_row = {
                "File": input_path.name,
                "Action": rmu_action.value,
                "RMURectCount": 0,
                "GroupedCount": 0,
                "UngroupedCount": 0,
                "SmartMatched": 0,
                "SmartChanged": 0,
                "SmrTextCount": 0,
                "SmrMatched": 0,
                "SmrChanged": 0,
                "ChannelStatusFound": 0,
                "ChannelStatusMoved": 0,
                "BusFrameRemoved": 0,
                "TitleMoved": 0,
                "Warnings": "",
            }
            rmu_processing_warnings: list[str] = []

            if rmu_action == RmuAction.GROUP:
                grouping = group_rmu_tree(tree, input_path)
                total_rects += grouping.rect_count
                total_rmu_groups += grouping.rebuilt_group_count
                total_rmu_members += grouping.grouped_member_count
                rmu_processing_row["RMURectCount"] = grouping.rect_count
                rmu_processing_row["GroupedCount"] = grouping.rebuilt_group_count
                rmu_processing_warnings.extend(grouping.warnings)
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
                rmu_processing_row["UngroupedCount"] = ungrouping.removed_rmu_merge_count
                rmu_processing_warnings.extend(ungrouping.warnings)
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

            if (
                settings.change_smart_rmu_frame_color
                or settings.change_smr_rmu_frame_color
                or settings.reposition_channel_status
                or settings.remove_bus_rmu_frame_and_reposition_title
            ):
                enhancement = enhance_rmu_tree(
                    tree,
                    input_path,
                    change_smart_frame_color=settings.change_smart_rmu_frame_color,
                    smart_frame_color=settings.smart_rmu_frame_color,
                    change_smr_frame_color=settings.change_smr_rmu_frame_color,
                    smr_frame_color=settings.smr_rmu_frame_color,
                    reposition_channel_status=settings.reposition_channel_status,
                    channel_status_position=settings.channel_status_position.value,
                    channel_status_inner_margin=settings.channel_status_inner_margin,
                    remove_bus_frame_and_reposition_title=(
                        settings.remove_bus_rmu_frame_and_reposition_title
                    ),
                )
                total_smart_rmu_rects += enhancement.smart_rmu_rect_count
                total_smart_rmu_frames_changed += enhancement.smart_frame_color_changed
                total_smr_texts += enhancement.smr_text_count
                total_smr_matched_rects += enhancement.smr_matched_rect_count
                total_smr_frames_changed += enhancement.smr_frame_color_changed
                for change in enhancement.smr_changes:
                    smr_report_rows.append({"File": input_path.name, "SMRTextID": change.text_id, "SMRX": f"{change.text_x:g}", "SMRY": f"{change.text_y:g}", "RectID": change.rect_id, "RectX": f"{change.rect_x:g}", "RectY": f"{change.rect_y:g}", "RectW": f"{change.rect_w:g}", "RectH": f"{change.rect_h:g}", "Distance": f"{change.distance:.2f}", "OldColor": change.old_color, "NewColor": change.new_color, "Result": "已修改" if change.changed else "已是目标颜色"})
                total_channel_status_rects += enhancement.channel_status_rect_count
                total_channel_status_found += enhancement.channel_status_found_count
                total_channel_status_moved += enhancement.channel_status_moved_count
                total_channel_status_missing += enhancement.channel_status_missing_count
                total_bus_rect_removed += enhancement.bus_rect_removed
                total_bus_title_moved += enhancement.bus_title_moved
                rmu_processing_row["SmartMatched"] = enhancement.smart_rmu_rect_count
                rmu_processing_row["SmartChanged"] = enhancement.smart_frame_color_changed
                rmu_processing_row["SmrTextCount"] = enhancement.smr_text_count
                rmu_processing_row["SmrMatched"] = enhancement.smr_matched_rect_count
                rmu_processing_row["SmrChanged"] = enhancement.smr_frame_color_changed
                rmu_processing_row["ChannelStatusFound"] = enhancement.channel_status_found_count
                rmu_processing_row["ChannelStatusMoved"] = enhancement.channel_status_moved_count
                rmu_processing_row["BusFrameRemoved"] = enhancement.bus_rect_removed
                rmu_processing_row["TitleMoved"] = enhancement.bus_title_moved
                rmu_processing_warnings.extend(enhancement.warnings)
                if settings.change_smart_rmu_frame_color:
                    log(
                        f"[SMART环网柜外框颜色] {input_path.name}：识别框内含 SMART 的环网柜 "
                        f"{enhancement.smart_rmu_rect_count} 个，仅修改外框 "
                        f"{enhancement.smart_frame_color_changed} 个，颜色 "
                        f"{settings.smart_rmu_frame_color.upper()}；SMART 字体未修改。"
                    )
                if settings.change_smr_rmu_frame_color:
                    log(f"[SMR环网柜外框颜色] {input_path.name}：SMR Text {enhancement.smr_text_count} 个，匹配外框 {enhancement.smr_matched_rect_count} 个，改色 {enhancement.smr_frame_color_changed} 个；SMR Text 未修改。")
                if settings.reposition_channel_status:
                    log(
                        f"[环网柜红色状态点] {input_path.name}：识别带 BusDis 的环网柜 "
                        f"{enhancement.channel_status_rect_count} 个，找到 channel_status 状态点 "
                        f"{enhancement.channel_status_found_count} 个，移动 "
                        f"{enhancement.channel_status_moved_count} 个到框内“"
                        f"{settings.channel_status_position.label}”，距边 "
                        f"{settings.channel_status_inner_margin} 像素；环网柜、母线、设备和连接线位置未修改。"
                    )
                if settings.remove_bus_rmu_frame_and_reposition_title:
                    log(
                        f"[Bus环网柜处理] {input_path.name}：识别带 Bus 的环网柜 "
                        f"{enhancement.bus_rect_count} 个，删除外框 {enhancement.bus_rect_removed} 个，"
                        f"删除对应 Merge {enhancement.bus_merge_removed} 个，"
                        f"将最近标题移到母线上方并居中 {enhancement.bus_title_moved} 个。"
                    )
                for warning in enhancement.warnings:
                    log(f"[环网柜增强告警] {warning}")

            if (
                rmu_action != RmuAction.NONE
                or settings.change_smart_rmu_frame_color
                or settings.change_smr_rmu_frame_color
                or settings.reposition_channel_status
                or settings.remove_bus_rmu_frame_and_reposition_title
            ):
                rmu_processing_row["Warnings"] = " | ".join(rmu_processing_warnings)
                rmu_processing_rows.append(rmu_processing_row)

            if settings.move_feeder_titles_above_bus:
                feeder_titles = move_feeder_titles_above_buses(tree, input_path)
                total_feeder_title_bus_segments += feeder_titles.bus_segment_count
                total_feeder_title_bus_groups += feeder_titles.bus_group_count
                total_feeder_title_candidates += feeder_titles.candidate_count
                total_feeder_title_moved += feeder_titles.moved_count
                total_feeder_title_unchanged += feeder_titles.unchanged_count
                total_feeder_title_skipped += (
                    feeder_titles.skipped_no_candidate_count
                    + feeder_titles.skipped_ambiguous_count
                    + feeder_titles.skipped_collision_count
                )
                log(
                    f"[馈线名称定位] {input_path.name}：有效水平 Bus "
                    f"{feeder_titles.bus_segment_count} 条、母线组 {feeder_titles.bus_group_count} 组、"
                    f"候选 Text {feeder_titles.candidate_count} 个；移动 "
                    f"{feeder_titles.moved_count} 个、已在目标位置 "
                    f"{feeder_titles.unchanged_count} 个、跳过 "
                    f"{feeder_titles.skipped_no_candidate_count + feeder_titles.skipped_ambiguous_count + feeder_titles.skipped_collision_count} 组。"
                )
                for move in feeder_titles.moves:
                    log(
                        f"  - Text {move.text_id} [{move.text}]：Bus "
                        f"{','.join(move.bus_ids)}；({move.old_x}, {move.old_y}) → "
                        f"({move.new_x}, {move.new_y})。"
                    )
                for warning in feeder_titles.warnings:
                    log(f"[馈线名称定位告警] {input_path.name}：{warning}")

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

            if settings.repair_connection_points:
                connection = repair_tree_connections(tree, input_path)
                total_connection_aligned_devices += connection.aligned_device_count
                total_connection_adjusted_lines += connection.adjusted_line_endpoint_count
                total_connection_relations += connection.inferred_relation_count
                total_connection_added += connection.added_reference_count
                total_connection_updated += connection.updated_reference_count
                total_connection_removed += connection.removed_reference_count
                total_connection_changed_elements += connection.changed_element_count
                total_connection_changed_attributes += connection.changed_attribute_count
                log(
                    f"[连接点修复] {input_path.name}：连接线 {connection.line_count} 个、"
                    f"母线 {connection.conductor_count} 个、可连接设备 {connection.device_count} 个；"
                    f"半像素水平对齐设备 {connection.aligned_device_count} 个、连接线坐标修改 "
                    f"{connection.adjusted_line_endpoint_count} 个；保守识别连接关系 "
                    f"{connection.inferred_relation_count} 条，新增引用 "
                    f"{connection.added_reference_count} 处；原引用改号 "
                    f"{connection.updated_reference_count} 处、原引用删除 "
                    f"{connection.removed_reference_count} 处，实际变更图元 "
                    f"{connection.changed_element_count} 个、属性 "
                    f"{connection.changed_attribute_count} 个。"
                )
                if connection.changed_element_ids:
                    log("  - 变更图元 ID：" + ", ".join(connection.changed_element_ids))
                else:
                    log("  - 当前文件连接关系完整，无需修改。")
                for warning in connection.warnings:
                    log(f"[连接点修复告警] {input_path.name}：{warning}")

            if hasattr(ET, "indent"):
                ET.indent(tree, space="    ")

            tmp_path = output_path.with_name(output_path.name + ".tmp")
            tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
            ET.parse(tmp_path)
            os.replace(tmp_path, output_path)

            enforce_confirmed_id_rules(output_path, log)
            outputs.append(output_path)
            if rmu_identification is not None and settings.export_rmu_identification_csv:
                rmu_csv = _write_rmu_csv(output_path, rmu_identification)
                rmu_html = _write_rmu_html(output_path, rmu_identification)
                total_rmu_csv += 1
                log(f"[环网柜识别] 已导出：{rmu_csv.name}；HTML：{rmu_html.name}")
            total_replaced += replaced
            total_deleted_attributes += deleted_attributes
            total_removed_matching += removed_matching
            total_removed_reference_groups += removed_reference_groups
            total_cleared_single_references += cleared_single_references

            log(
                f"✓ {input_path.name}：属性替换 {replaced} 处，删除元素属性 {deleted_attributes} 处，"
                f"匹配元素删除 {removed_matching} 个，"
                f"清理引用分组 {removed_reference_groups} 个，清空父引用 "
                f"{cleared_single_references} 个；输出 {output_path.name}"
            )
        except Exception as exc:
            failed.append(f"{input_path.name}: {exc}")
            log(f"[基础处理失败] {input_path.name}：{exc}")

        if progress:
            progress(round(index * 100 / len(files)))

    rmu_graphic_report_csv = None
    rmu_graphic_report_html = None
    if rmu_processing_rows:
        rmu_graphic_report_csv, rmu_graphic_report_html = _write_rmu_processing_report(settings.output_dir, rmu_processing_rows)
        log(f"[环网柜图元处理报告] CSV：{rmu_graphic_report_csv}；HTML：{rmu_graphic_report_html}（覆盖上一份同类报告）。")

    rmu_summary_report_csv = None
    rmu_summary_report_html = None
    if settings.identify_rmu_name_and_type:
        rmu_summary_report_csv, rmu_summary_report_html = _write_rmu_summary_reports(
            settings.output_dir, rmu_graphic_rows,
            intelligent_classification_enabled=settings.rmu_smart_in_type,
        )
        log(f"[RMU信息汇总报告] CSV：{rmu_summary_report_csv}；HTML：{rmu_summary_report_html}（覆盖上一份同类报告）。")

    if settings.change_smr_rmu_frame_color:
        csv_report, html_report = _write_smr_frame_reports(settings.output_dir, smr_report_rows)
        outputs.extend([csv_report, html_report])
        log(f"[SMR环网柜报告] CSV：{csv_report}；HTML：{html_report}（覆盖上一份同类报告）。")

    ledger_stats = {}
    ledger_csv = None
    ledger_html = None
    if settings.compare_rmu_ledger:
        comparison_rows, ledger_stats = compare_ledger(ledger_rows, rmu_graphic_rows)
        ledger_csv, ledger_html = write_comparison_reports(settings.output_dir, comparison_rows, ledger_stats)
        outputs.extend([ledger_csv, ledger_html])
        log(
            f"[RMU台账对比] 台账 {ledger_stats['ledger_count']} 条，图形 {ledger_stats['graphic_count']} 个；"
            f"完全一致 {ledger_stats['matched_count']}，柜型不一致 {ledger_stats['type_mismatch_count']}，"
            f"智能属性不一致 {ledger_stats['intelligent_mismatch_count']}，图形缺失 {ledger_stats['graphic_missing_count']}，"
            f"台账缺失 {ledger_stats['ledger_missing_count']}。"
        )
        log(f"[RMU台账对比] 报告：{ledger_csv.name}；{ledger_html.name}（覆盖上一份同类报告）。")

    summary = (
        f"[基础处理汇总] 输入 {len(files)} 个文件，成功 {len(outputs)} 个，失败 {len(failed)} 个；"
        f"环网柜 rect {total_rects} 个，重建组合 "
        f"{total_rmu_groups} 个，取消组合 {total_rmu_ungrouped} 个，外框下移 "
        f"{total_rmu_lowered_rects} 个；识别含 SMART 环网柜 {total_smart_rmu_rects} 个，"
        f"SMART 环网柜外框改色 {total_smart_rmu_frames_changed} 个；SMR Text {total_smr_texts} 个，匹配环网柜 {total_smr_matched_rects} 个，SMR 外框改色 {total_smr_frames_changed} 个；channel_status 状态点"
        f"找到 {total_channel_status_found} 个、移动 {total_channel_status_moved} 个、"
        f"未找到 {total_channel_status_missing} 个，带 Bus 外框删除 "
        f"{total_bus_rect_removed} 个，标题上移 {total_bus_title_moved} 个；"
        f"线路/母线颜色修改 {total_color_changed} 个图元"
    )
    if settings.identify_rmu_name_and_type:
        summary += (
            f"；环网柜识别 {total_rmu_identified} 个、柜名成功 {total_rmu_named} 个、"
            f"柜型成功 {total_rmu_typed} 个、待确认 {total_rmu_ambiguous} 个、导出 CSV/HTML 报告 {total_rmu_csv} 份"
        )
    if settings.compare_rmu_ledger and ledger_stats:
        summary += (
            f"；RMU台账 {ledger_stats['ledger_count']} 条，对比完全一致 {ledger_stats['matched_count']} 条，"
            f"柜型不一致 {ledger_stats['type_mismatch_count']} 条，智能属性不一致 {ledger_stats['intelligent_mismatch_count']} 条，"
            f"图形缺失 {ledger_stats['graphic_missing_count']} 条，台账缺失 {ledger_stats['ledger_missing_count']} 条"
        )
    if settings.upgrade_icon_geometry:
        summary += (
            f"；图元版本升级实例 {total_icon_upgraded_instances} 个、连接线端点适配 "
            f"{total_icon_adjusted_lines} 条、已是新尺寸 {total_icon_already_new} 个、"
            f"未知尺寸跳过 {total_icon_skipped_unknown_size} 个"
        )
    if settings.move_feeder_titles_above_bus:
        summary += (
            f"；馈线名称定位识别有效 Bus {total_feeder_title_bus_segments} 条、母线组 "
            f"{total_feeder_title_bus_groups} 组，移动 Text {total_feeder_title_moved} 个、"
            f"已在目标位置 {total_feeder_title_unchanged} 个、跳过 {total_feeder_title_skipped} 组"
        )
    if settings.repair_connection_points:
        summary += (
            f"；连接点半像素水平对齐设备 {total_connection_aligned_devices} 个、连接线坐标修改 "
            f"{total_connection_adjusted_lines} 个，保守识别关系 {total_connection_relations} 条，新增引用 "
            f"{total_connection_added} 处、原引用改号 {total_connection_updated} 处、"
            f"原引用删除 {total_connection_removed} 处，"
            f"变更图元 {total_connection_changed_elements} 个、属性 "
            f"{total_connection_changed_attributes} 个"
        )
    log(summary + "。")

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
            "deleted_attribute_count": total_deleted_attributes,
            "removed_matching_element_count": total_removed_matching,
            "removed_reference_group_count": total_removed_reference_groups,
            "cleared_single_reference_count": total_cleared_single_references,
            "rmu_rect_count": total_rects,
            "rmu_group_count": total_rmu_groups,
            "rmu_grouped_member_count": total_rmu_members,
            "rmu_ungrouped_count": total_rmu_ungrouped,
            "rmu_released_member_count": total_rmu_released_members,
            "rmu_lowered_rect_count": total_rmu_lowered_rects,
            "color_changed_count": total_color_changed,
            "dynamic_color_warning_count": total_dynamic_colors,
            "smart_rmu_rect_count": total_smart_rmu_rects,
            "smart_rmu_frame_color_changed_count": total_smart_rmu_frames_changed,
            "smr_text_count": total_smr_texts,
            "smr_matched_rmu_rect_count": total_smr_matched_rects,
            "smr_rmu_frame_color_changed_count": total_smr_frames_changed,
            "channel_status_rmu_rect_count": total_channel_status_rects,
            "channel_status_found_count": total_channel_status_found,
            "channel_status_moved_count": total_channel_status_moved,
            "channel_status_missing_count": total_channel_status_missing,
            "bus_rmu_frame_removed_count": total_bus_rect_removed,
            "bus_rmu_title_moved_count": total_bus_title_moved,
            "move_feeder_titles_above_bus_enabled": settings.move_feeder_titles_above_bus,
            "feeder_title_bus_segment_count": total_feeder_title_bus_segments,
            "feeder_title_bus_group_count": total_feeder_title_bus_groups,
            "feeder_title_candidate_count": total_feeder_title_candidates,
            "feeder_title_moved_count": total_feeder_title_moved,
            "feeder_title_unchanged_count": total_feeder_title_unchanged,
            "feeder_title_skipped_count": total_feeder_title_skipped,
            "rmu_identification_enabled": settings.identify_rmu_name_and_type,
            "rmu_identified_count": total_rmu_identified,
            "rmu_named_count": total_rmu_named,
            "rmu_typed_count": total_rmu_typed,
            "rmu_ambiguous_name_count": total_rmu_ambiguous,
            "rmu_csv_count": total_rmu_csv,
            "rmu_ledger_compare_enabled": settings.compare_rmu_ledger,
            "rmu_ledger_count": ledger_stats.get("ledger_count", 0),
            "rmu_ledger_matched_count": ledger_stats.get("matched_count", 0),
            "rmu_ledger_type_mismatch_count": ledger_stats.get("type_mismatch_count", 0),
            "rmu_ledger_intelligent_mismatch_count": ledger_stats.get("intelligent_mismatch_count", 0),
            "rmu_ledger_graphic_missing_count": ledger_stats.get("graphic_missing_count", 0),
            "rmu_ledger_missing_count": ledger_stats.get("ledger_missing_count", 0),
            "rmu_graphic_processing_report_html": str(rmu_graphic_report_html or ""),
            "rmu_summary_report_html": str(rmu_summary_report_html or ""),
            "rmu_ledger_report_html": str(ledger_html or ""),
            "icon_upgrade_enabled": settings.upgrade_icon_geometry,
            "icon_upgrade_rule_count": len(icon_rules),
            "icon_upgraded_instance_count": total_icon_upgraded_instances,
            "icon_adjusted_line_count": total_icon_adjusted_lines,
            "icon_already_new_count": total_icon_already_new,
            "icon_unknown_size_skipped_count": total_icon_skipped_unknown_size,
            "connection_repair_enabled": settings.repair_connection_points,
            "aligned_connection_device_count": total_connection_aligned_devices,
            "adjusted_connection_line_count": total_connection_adjusted_lines,
            "inferred_connection_count": total_connection_relations,
            "added_connection_reference_count": total_connection_added,
            "updated_connection_reference_count": total_connection_updated,
            "removed_connection_reference_count": total_connection_removed,
            "changed_connection_element_count": total_connection_changed_elements,
            "changed_connection_attribute_count": total_connection_changed_attributes,
        },
    )
