from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from g_file_studio.engines.classified_device_poke_engine import (
    apply_classified_device_pokes,
    assign_device_names,
    find_classified_devices,
)
from g_file_studio.engines.rmu_identification_engine import (
    RmuIdentificationResult,
    identify_rmus,
    parse_intelligent_markers,
    parse_name_exclusions,
)
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes
from g_file_studio.engines.station_poke_engine import apply_station_pokes
from g_file_studio.models import InputMode, ProcessingResult
from g_file_studio.processors.common import (
    LogCallback,
    ProgressCallback,
    discover_g_inputs,
    enforce_confirmed_id_rules,
)
from g_file_studio.services.database_service import OracleDatabaseService
from g_file_studio.services.poke_report_service import write_poke_reports


@dataclass(frozen=True)
class PokeProcessingSettings:
    source_path: Path
    input_mode: InputMode
    output_dir: Path
    enable_rmu_poke: bool = True
    # AR/LBS/SEC is an independent equipment-Poke branch. It no longer follows
    # the RMU enable switch.
    enable_classified_device_poke: bool = True
    enable_station_poke: bool = True
    rmu_name_positions: tuple[str, ...] = ("top",)
    rmu_name_exclusions: str = ""
    rmu_intelligent_markers: str = "SMART, SMR"
    # (server file name, devref, local classification marker), loaded from the
    # server-symbol sync cache by the UI. Poke processing never queries SSH.
    classification_marker_entries: tuple[tuple[str, str, str], ...] = ()


def _write_tree_atomic(tree: ET.ElementTree, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="    ")
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    ET.parse(tmp_path)
    os.replace(tmp_path, output_path)


def _lookup_key(value: object) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def process_pokes(
    settings: PokeProcessingSettings,
    database_service: OracleDatabaseService,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """Standalone Poke processor without a facID precondition.

    Detail Poke has two independent equipment branches. RMU Poke consumes the
    shared ``identify_rmus()`` result. AR/LBS/SEC device Poke consumes only
    server-symbol classifications AR / LBS / SEC and assigns one nearby Text
    instance per device under its own hard name rules: red Text, above/right only,
    within 300 units. Both resolve EACH equipment instance independently by name:

        DMS_COMBINED_DEVICE.NAME -> FEEDER_ID -> DMS_FEEDER_DEVICE
        -> SUBSTATION -> SUBCONTROLAREA -> feeder full business name.

    This is required for station-level overview drawings that contain RMUs from
    many feeders.  Station-jump Poke is independent from facID as well and uses
    only the detected station key -> SUBSTATION -> SUBCONTROLAREA chain.
    """
    if not (
        settings.enable_rmu_poke
        or settings.enable_classified_device_poke
        or settings.enable_station_poke
    ):
        raise ValueError("请至少启用一种 Poke 跳转处理。")
    if settings.enable_rmu_poke and not settings.rmu_name_positions:
        raise ValueError("RMU 柜名位置至少需要一个方向；Poke 模块复用现有 RMU 识别设置。")

    files = discover_g_inputs(settings.source_path, settings.input_mode)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    warnings: list[str] = []
    file_summaries: list[dict[str, object]] = []
    report_rows: list[dict[str, object]] = []

    stats = {
        "input_count": len(files),
        "processed_count": 0,
        "facid_skipped_count": 0,  # retained for report/API compatibility; v2.18.96 no longer skips on facID
        "database_skipped_count": 0,
        "rmu_identified_total": 0,
        "smart_rmu_identified_total": 0,
        "rmu_database_resolved": 0,
        "rmu_database_unresolved": 0,
        "rmu_candidates": 0,
        "rmu_added": 0,
        "rmu_updated": 0,
        "rmu_unchanged": 0,
        "rmu_skipped": 0,
        "classified_device_total": 0,
        "classified_device_named": 0,
        "classified_device_database_resolved": 0,
        "classified_device_database_unresolved": 0,
        "classified_device_added": 0,
        "classified_device_updated": 0,
        "classified_device_unchanged": 0,
        "classified_device_skipped": 0,
        "station_candidates": 0,
        "station_resolved_count": 0,
        "station_added": 0,
        "station_updated": 0,
        "station_unchanged": 0,
        "station_duplicate_removed": 0,
        "station_skipped": 0,
        "station_classification_excluded": 0,
    }

    excluded = parse_name_exclusions(settings.rmu_name_exclusions)
    markers = parse_intelligent_markers(settings.rmu_intelligent_markers)
    if settings.enable_classified_device_poke:
        if settings.classification_marker_entries:
            log(
                f"[Poke/分类标记] 已读取本地服务器图元同步缓存中的 "
                f"{len(settings.classification_marker_entries)} 条分类标记；"
                "AR / LBS / SEC 独立设备 Poke 已启用，名称强制为红色且只认设备上方/右侧（≤300）；"
                "站点跳转不使用任何设备分类做排除。"
            )
        else:
            log(
                "[Poke/分类标记] AR/LBS/SEC 独立设备 Poke 已启用，但未找到本地图元分类标记；"
                "该分支不执行；RMU/站点跳转不受影响。"
            )
    else:
        log("[Poke/分类设备] AR/LBS/SEC 独立设备 Poke 未启用。")

    for index, input_path in enumerate(files, 1):
        if progress:
            progress(max(1, int((index - 1) / max(len(files), 1) * 90)))
        tree = ET.parse(input_path)
        root = tree.getroot()
        fac_id = (root.get("facID") or "").strip()  # report-only metadata; never a Poke prerequisite
        file_summary: dict[str, object] = {
            "File": input_path.name,
            "FacID": fac_id,
            "FeederBusinessName": "",
            "RMURecognized": 0,
            "SmartRMU": 0,
            "RMUAdded": 0,
            "RMUUpdated": 0,
            "RMUSkipped": 0,
            "DeviceRecognized": 0,
            "DeviceNamed": 0,
            "DeviceAdded": 0,
            "DeviceUpdated": 0,
            "DeviceSkipped": 0,
            "StationCandidates": 0,
            "StationResolved": 0,
            "StationAdded": 0,
            "StationUpdated": 0,
            "StationSkipped": 0,
            "StationClassificationExcluded": 0,
            "DuplicatesRemoved": 0,
            "Status": "OK",
            "Reason": "",
        }

        if progress:
            base = (index - 1) / max(len(files), 1) * 90
            progress(min(95, int(base + 12)))

        # RMU recognition is needed only by the RMU or station-jump branches.
        # A classified-device-only run is now genuinely independent and avoids
        # scanning RMU frames/names entirely.
        if settings.enable_rmu_poke or settings.enable_station_poke:
            identification = identify_rmus(
                tree,
                input_path,
                # Poke must use the same strict RMU resolver: only the Text above the
                # validated cabinet frame can be used as its name.
                name_positions=("top",),
                name_resolution_mode="selected_direction",
                smart_in_type=True,
                excluded_name_values=excluded,
                intelligent_marker_values=markers,
            )
            smart_items = [item for item in identification.items if bool(item.smart_count)]
            smart_count = len(smart_items)
            stats["rmu_identified_total"] += identification.cabinet_count
            stats["smart_rmu_identified_total"] += smart_count
            file_summary["RMURecognized"] = identification.cabinet_count
            file_summary["SmartRMU"] = smart_count
            log(
                f"[Poke/RMU识别] {input_path.name}：复用公共 identify_rmus()，"
                f"识别 RMU {identification.cabinet_count} 个，智能 RMU {smart_count} 个。"
            )
            for warning in identification.warnings:
                log(f"[Poke/RMU识别告警] {input_path.name}：{warning}")
        else:
            identification = RmuIdentificationResult(file_path=input_path)
            smart_items = []
            smart_count = 0
            log(f"[Poke/分类设备] {input_path.name}：仅执行 AR/LBS/SEC，跳过 RMU 识别。")

        if not fac_id:
            log(
                f"[Poke提示] {input_path.name}：facID 为空不影响 Poke 处理；"
                "设备 Poke 按设备名称逐个查库，站点跳转 Poke 本身不使用 facID。"
            )

        # Resolve intelligent RMUs in one bounded Oracle query.  Each RMU may map
        # to a different feeder, which is the key fix for station overview G files.
        rmu_contexts: dict[str, object] = {}
        rmu_db_issues: dict[str, str] = {}
        database_prefixes: dict[str, str] = {}
        if settings.enable_rmu_poke and smart_items:
            smart_names = [(item.name or "").strip() for item in smart_items if (item.name or "").strip()]
            try:
                rmu_contexts, rmu_db_issues = database_service.resolve_rmu_contexts(smart_names)
            except Exception as exc:
                # Database outage/query failure must not prevent station Poke logic
                # from running or prevent the G file/report from being written.
                message = f"RMU 名称批量查询失败：{exc}"
                for name in smart_names:
                    rmu_db_issues[_lookup_key(name)] = message
                stats["database_skipped_count"] += 1
                warnings.append(f"{input_path.name}: {message}")
                log(f"[RMU Poke数据库告警] {input_path.name}：{message}")

            database_prefixes = {
                key: str(getattr(context, "feeder_full_name", "") or "").strip()
                for key, context in rmu_contexts.items()
                if str(getattr(context, "feeder_full_name", "") or "").strip()
            }
            stats["rmu_database_resolved"] += len(rmu_contexts)
            stats["rmu_database_unresolved"] += len(rmu_db_issues)
            resolved_feeders = sorted(set(database_prefixes.values()))
            file_summary["FeederBusinessName"] = "; ".join(resolved_feeders)
            if resolved_feeders:
                log(
                    f"[RMU Poke数据库] {input_path.name}：按 RMU 名称解析到 "
                    f"{len(rmu_contexts)} 个环网柜、{len(resolved_feeders)} 条馈线。"
                )
                for key, context in rmu_contexts.items():
                    log(
                        f"  - RMU {getattr(context, 'rmu_name', key)} → FEEDER_ID={getattr(context, 'feeder_id', '')} "
                        f"→ {getattr(context, 'feeder_full_name', '')}"
                    )

        if settings.enable_rmu_poke:
            rmu_result = apply_smart_rmu_pokes(
                tree,
                input_path,
                identification,
                naming_mode="database_rmu_name",
                database_prefixes=database_prefixes,
                database_resolution_errors=rmu_db_issues,
            )
            stats["rmu_candidates"] += rmu_result.intelligent_rmu_count
            stats["rmu_added"] += rmu_result.added_count
            stats["rmu_updated"] += rmu_result.updated_count
            stats["rmu_unchanged"] += rmu_result.unchanged_count
            stats["rmu_skipped"] += rmu_result.skipped_count
            file_summary["RMUAdded"] = rmu_result.added_count
            file_summary["RMUUpdated"] = rmu_result.updated_count
            file_summary["RMUSkipped"] = rmu_result.skipped_count
            log(
                f"[RMU Poke] {input_path.name}：按 RMU 名称逐柜解析所属馈线；"
                f"新增 {rmu_result.added_count}，更新 {rmu_result.updated_count}，"
                f"已符合 {rmu_result.unchanged_count}，跳过 {rmu_result.skipped_count}。"
            )
            for change in rmu_result.changes:
                log(
                    f"  - RMU {change.rmu_name}：{change.action} Poke {change.poke_id} → {change.target_file}"
                )
            for record in rmu_result.records:
                key = _lookup_key(record.rmu_name)
                context = rmu_contexts.get(key)
                resolved_name = str(getattr(context, "feeder_full_name", "") or "").strip()
                report_rows.append({
                    "File": input_path.name,
                    "Type": "rmu",
                    "SourceName": record.rmu_name,
                    "NameElementID": record.name_text_id,
                    "FrameElementID": record.rect_id,
                    "StationKey": "",
                    "AdjacentRMU": "",
                    "LocateLabel": "",
                    "ResolvedBusinessName": resolved_name,
                    "Action": record.action,
                    "PokeID": record.poke_id,
                    "TargetAhref": record.target_file,
                    "Confidence": "HIGH" if record.action != "skipped" else "",
                    "RecognitionSource": "rmu_identification",
                    "Reason": record.reason,
                })
            for warning in rmu_result.warnings:
                warnings.append(f"{input_path.name}: {warning}")
                log(f"[RMU Poke告警] {input_path.name}：{warning}")

        # AR / LBS / SEC detail Poke is independent from the RMU Poke switch.
        # Classification markers identify only the target device symbols. Names
        # must be RED and geometrically ABOVE/RIGHT of the device, within 300 G
        # units. Equal rendered text remains independent when Text IDs differ.
        if settings.enable_classified_device_poke and settings.classification_marker_entries:
            classified_devices = find_classified_devices(root, settings.classification_marker_entries)
            device_assignments = assign_device_names(classified_devices)
            device_names = [assignment.name for assignment in device_assignments if assignment.name]
            device_contexts: dict[str, object] = {}
            device_db_issues: dict[str, str] = {}
            if device_names:
                try:
                    # These field devices use the same DMS_COMBINED_DEVICE.NAME ->
                    # FEEDER_ID business chain as the existing RMU detail jump.
                    device_contexts, device_db_issues = database_service.resolve_rmu_contexts(device_names)
                except Exception as exc:
                    message = f"AR/LBS/SEC 名称批量查询失败：{exc}"
                    for name in device_names:
                        device_db_issues[_lookup_key(name)] = message
                    warnings.append(f"{input_path.name}: {message}")
                    log(f"[设备 Poke数据库告警] {input_path.name}：{message}")

            device_prefixes = {
                key: str(getattr(context, "feeder_full_name", "") or "").strip()
                for key, context in device_contexts.items()
                if str(getattr(context, "feeder_full_name", "") or "").strip()
            }
            device_result = apply_classified_device_pokes(
                tree,
                input_path,
                classification_marker_entries=settings.classification_marker_entries,
                database_prefixes=device_prefixes,
                database_resolution_errors=device_db_issues,
            )
            stats["classified_device_total"] += device_result.device_count
            stats["classified_device_named"] += device_result.assigned_name_count
            stats["classified_device_database_resolved"] += len(device_contexts)
            stats["classified_device_database_unresolved"] += len(device_db_issues)
            stats["classified_device_added"] += device_result.added_count
            stats["classified_device_updated"] += device_result.updated_count
            stats["classified_device_unchanged"] += device_result.unchanged_count
            stats["classified_device_skipped"] += device_result.skipped_count
            file_summary["DeviceRecognized"] = device_result.device_count
            file_summary["DeviceNamed"] = device_result.assigned_name_count
            file_summary["DeviceAdded"] = device_result.added_count
            file_summary["DeviceUpdated"] = device_result.updated_count
            file_summary["DeviceSkipped"] = device_result.skipped_count
            log(
                f"[AR/LBS/SEC Poke] {input_path.name}：分类设备 {device_result.device_count}，"
                f"分配名称 {device_result.assigned_name_count}，新增 {device_result.added_count}，"
                f"更新 {device_result.updated_count}，跳过 {device_result.skipped_count}。"
            )
            for record in device_result.records:
                report_rows.append({
                    "File": input_path.name,
                    "Type": "classified_device",
                    "SourceName": record.name,
                    "NameElementID": record.text_id,
                    "FrameElementID": record.device_id,
                    "StationKey": record.marker,
                    "AdjacentRMU": "",
                    "LocateLabel": "",
                    "ResolvedBusinessName": device_prefixes.get(record.name.casefold(), ""),
                    "CurrentStation": "",
                    "Action": record.action,
                    "PokeID": record.poke_id,
                    "TargetAhref": record.target_file,
                    "Confidence": "HIGH" if record.action != "skipped" else "",
                    "RecognitionSource": "classification_device_name",
                    "Reason": record.reason,
                })
            for warning in device_result.warnings:
                warnings.append(f"{input_path.name}: {warning}")

        if progress:
            base = (index - 1) / max(len(files), 1) * 90
            progress(min(96, int(base + 40)))

        if settings.enable_station_poke:
            # facID is not needed.  If RMU database resolution happens to prove
            # one unique current station, use it only to suppress a self-jump;
            # otherwise station-jump recognition/query still proceeds normally.
            resolved_station_names = {
                str(getattr(context, "station_name", "") or "").strip()
                for context in rmu_contexts.values()
                if str(getattr(context, "station_name", "") or "").strip()
            }
            current_station_name = next(iter(resolved_station_names)) if len(resolved_station_names) == 1 else ""
            station_result = apply_station_pokes(
                tree,
                input_path,
                identification,
                current_station_name=current_station_name,
                station_resolver=database_service.resolve_station_context,
                # A same-station label is still allowed only when an existing
                # Poke has a unique adjacent RMU locate label.  This is a
                # graphic-constraint exception; it does not inspect line
                # geometry or connection references.
                allow_same_station_terminals=True,
                # Station-jump recognition is intentionally independent from
                # AR/LBS/SEC/FUSE/Transformer_OH classification markers.
            )
            stats["station_candidates"] += station_result.candidate_count
            stats["station_resolved_count"] += station_result.eligible_count
            stats["station_added"] += station_result.added_count
            stats["station_updated"] += station_result.updated_count
            stats["station_unchanged"] += station_result.unchanged_count
            stats["station_duplicate_removed"] += station_result.removed_duplicate_count
            stats["station_skipped"] += station_result.skipped_count
            stats["station_classification_excluded"] += station_result.classification_excluded_count
            file_summary["StationCandidates"] = station_result.candidate_count
            file_summary["StationResolved"] = station_result.eligible_count
            file_summary["StationAdded"] = station_result.added_count
            file_summary["StationUpdated"] = station_result.updated_count
            file_summary["StationSkipped"] = station_result.skipped_count
            file_summary["StationClassificationExcluded"] = station_result.classification_excluded_count
            file_summary["DuplicatesRemoved"] = station_result.removed_duplicate_count
            log(
                f"[站点跳转 Poke] {input_path.name}：不依赖 facID；候选 {station_result.candidate_count}，"
                f"新增 {station_result.added_count}，更新 {station_result.updated_count}，"
                f"已符合 {station_result.unchanged_count}，删除重复 {station_result.removed_duplicate_count}，"
                f"跳过 {station_result.skipped_count}（分类标记排除 {station_result.classification_excluded_count}）。"
            )
            for change in station_result.changes:
                log(
                    f"  - {change.label_text} → station={change.station_key} → "
                    f"{change.station_full_name}：{change.action} Poke {change.poke_id} → "
                    f"{change.target_file}（{change.confidence}）"
                )
            for record in station_result.records:
                report_rows.append({
                    "File": input_path.name,
                    "Type": "station",
                    "SourceName": record.label_text,
                    "NameElementID": record.text_id,
                    "FrameElementID": "",
                    "StationKey": record.station_key,
                    "AdjacentRMU": record.adjacent_rmu_names,
                    "LocateLabel": record.locate_label,
                    "ResolvedBusinessName": record.station_full_name,
                    "CurrentStation": "是（不添加）" if record.current_station else "",
                    "Action": record.action,
                    "PokeID": record.poke_id,
                    "TargetAhref": record.target_file,
                    "Confidence": record.confidence,
                    "RecognitionSource": record.recognition_source,
                    "Reason": record.reason,
                })
            for warning in station_result.warnings:
                warnings.append(f"{input_path.name}: {warning}")
                log(f"[站点跳转 Poke告警] {input_path.name}：{warning}")

        output_path = settings.output_dir / input_path.name
        _write_tree_atomic(tree, output_path)
        enforce_confirmed_id_rules(output_path, log)
        outputs.append(output_path)
        stats["processed_count"] += 1
        if (
            int(file_summary.get("RMUSkipped", 0) or 0)
            or int(file_summary.get("DeviceSkipped", 0) or 0)
            or int(file_summary.get("StationSkipped", 0) or 0)
        ):
            file_summary["Status"] = "WARNING"
            file_summary["Reason"] = "部分 Poke 未加跳转，详细原因见下方明细。"
        else:
            file_summary["Reason"] = "Poke 跳转处理完成。"
        file_summaries.append(file_summary)
        log(f"✓ {input_path.name}：Poke 跳转处理完成，输出 {output_path.name}")

        if progress:
            progress(min(98, int(index / max(len(files), 1) * 90 + 8)))

    if progress:
        progress(100)

    log(
        "[Poke跳转汇总] "
        f"处理 {stats['processed_count']}/{stats['input_count']} 个文件；"
        f"RMU数据库成功解析 {stats['rmu_database_resolved']}、未解析 {stats['rmu_database_unresolved']}；"
        f"RMU Poke 新增 {stats['rmu_added']}、更新 {stats['rmu_updated']}；"
        f"AR/LBS/SEC Poke 新增 {stats['classified_device_added']}、更新 {stats['classified_device_updated']}；"
        f"站点跳转 Poke 新增 {stats['station_added']}、更新 {stats['station_updated']}、"
        f"删除重复 {stats['station_duplicate_removed']}。"
    )
    csv_report, html_report = write_poke_reports(
        settings.output_dir,
        statistics=stats,
        file_summaries=file_summaries,
        detail_rows=report_rows,
    )
    outputs.extend([csv_report, html_report])
    stats["csv_report_path"] = str(csv_report)
    stats["html_report_path"] = str(html_report)
    log(f"[Poke处理报告] CSV：{csv_report}")
    log(f"[Poke处理报告] HTML：{html_report}")
    return ProcessingResult(
        success=True,
        output_files=outputs,
        warnings=warnings,
        statistics=stats,
    )
