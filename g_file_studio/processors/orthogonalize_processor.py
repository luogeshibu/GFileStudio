from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.orthogonalize_engine import orthogonalize_tree
from g_file_studio.models import InputMode, OrthogonalizeSettings, ProcessingResult
from g_file_studio.processors.common import LogCallback, ProgressCallback, discover_g_inputs
from g_file_studio.services.site_profile_service import SiteProfileService


def _global_geometry_templates() -> dict[str, list[dict[str, object]]] | None:
    """Load the user-confirmed GLOBAL symbol Pin geometry for this run."""
    try:
        profile = SiteProfileService().get_global_profile(auto_initialize=False)
    except Exception:
        # A malformed or unavailable profile must not prevent safe legacy
        # orthogonalization of the input G files.
        return None
    if profile is None or not profile.geometry_templates:
        return None
    return profile.geometry_templates


def orthogonalize_g_files(
    source_path: Path,
    input_mode: InputMode,
    output_dir: Path,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """Create orthogonalized copies of one G file or a first-level G directory."""
    files = discover_g_inputs(source_path, input_mode)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    failed: list[str] = []
    total_inspected = 0
    total_changed = 0
    total_segments = 0
    total_aligned_devices = 0
    total_aligned_lines = 0
    total_connection_aligned_lines = 0
    total_rebuilt_lines = 0
    total_skipped = 0
    geometry_templates = _global_geometry_templates()
    if geometry_templates:
        log(f"[标准几何] 已加载 GLOBAL 标准 Pin：{len(geometry_templates)} 类图元。")
    else:
        log("[标准几何] 未找到可用 GLOBAL Pin，线路终点保留保守外框兼容策略。")

    for index, input_path in enumerate(files, start=1):
        output_path = output_dir / input_path.name
        try:
            if output_path.resolve() == input_path.resolve():
                raise ValueError("正交化输出目录不能与源文件位置相同，避免覆盖原始 G 文件。")
            tree = ET.parse(input_path)
            result = orthogonalize_tree(tree, geometry_templates=geometry_templates)
            total_inspected += result.inspected_lines
            total_changed += result.changed_lines
            total_segments += result.changed_segments
            total_aligned_devices += result.aligned_devices
            total_aligned_lines += result.aligned_lines
            total_connection_aligned_lines += result.connection_aligned_lines
            total_rebuilt_lines += result.rebuilt_lines
            total_skipped += result.skipped_lines
            if result.changed:
                if hasattr(ET, "indent"):
                    ET.indent(tree, space="    ")
                temp_path = output_path.with_name(output_path.name + ".tmp")
                tree.write(temp_path, encoding="utf-8", xml_declaration=True)
                ET.parse(temp_path)
                os.replace(temp_path, output_path)
            else:
                shutil.copy2(input_path, output_path)
            outputs.append(output_path)
            log(
                f"[OK] {input_path.name}：检查线路 {result.inspected_lines} 条，"
                f"正交化 {result.changed_lines} 条、增加直角段 {result.changed_segments} 个，"
                    f"同类设备对齐 {result.aligned_devices} 个、跟随修正线路 {result.aligned_lines} 条，"
                    f"其中连接点对齐 {result.connection_aligned_lines} 条，"
                    f"确认重画线路 {result.rebuilt_lines} 条，"
                f"保守跳过 {result.skipped_lines} 条；输出 {output_path.name}。"
            )
            for issue in result.issues[:20]:
                log(
                    f"  - 跳过 <{issue.element_type}> id={issue.element_id or '(空)'}："
                    f"{issue.reason}"
                )
            if len(result.issues) > 20:
                log(f"  - 其余 {len(result.issues) - 20} 条跳过原因省略。")
        except Exception as exc:
            failed.append(f"{input_path.name}: {exc}")
            log(f"[ERROR] {input_path.name}：{exc}")
        if progress:
            progress(round(index * 100 / len(files)))

    log(
        f"[线路正交化汇总] 输入 {len(files)} 个，成功 {len(outputs)} 个，失败 {len(failed)} 个；"
        f"检查线路 {total_inspected} 条，正交化 {total_changed} 条，"
        f"增加直角段 {total_segments} 个，同类设备对齐 {total_aligned_devices} 个，"
        f"跟随修正线路 {total_aligned_lines} 条，确认重画线路 {total_rebuilt_lines} 条，"
        f"其中连接点对齐 {total_connection_aligned_lines} 条，"
        f"保守跳过 {total_skipped} 条。"
    )
    return ProcessingResult(
        success=not failed,
        output_files=outputs,
        warnings=failed,
        statistics={
            "input_mode": input_mode.value,
            "source_path": str(source_path),
            "file_count": len(outputs),
            "failed_file_count": len(failed),
            "inspected_line_count": total_inspected,
            "orthogonalized_line_count": total_changed,
            "added_right_angle_segment_count": total_segments,
            "aligned_device_count": total_aligned_devices,
            "aligned_line_count": total_aligned_lines,
            "connection_aligned_line_count": total_connection_aligned_lines,
            "rebuilt_line_count": total_rebuilt_lines,
            "skipped_line_count": total_skipped,
            "global_standard_geometry_class_count": len(geometry_templates or {}),
            "output_naming": "source_filename",
        },
    )


def process_orthogonalize(
    settings: OrthogonalizeSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """Run the standalone线路正交化 module from its typed settings object."""
    return orthogonalize_g_files(
        settings.source_path,
        settings.input_mode,
        settings.output_dir,
        log,
        progress,
    )
