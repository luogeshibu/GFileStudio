from __future__ import annotations

import shutil
from pathlib import Path

from g_file_studio.models import InputMode, PipelineSettings, ProcessingResult
from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.processors.common import LogCallback, ProgressCallback
from g_file_studio.processors.frame_processor import add_drawing_frames
from g_file_studio.processors.margin_processor import adjust_graph_margins
from g_file_studio.processors.merge_processor import merge_feeders


G_SUFFIX = ".sln.pic.g"


def _stage_progress(
    progress: ProgressCallback | None,
    stage_index: int,
    stage_count: int,
):
    if progress is None:
        return None

    start = round(stage_index * 100 / stage_count)
    end = round((stage_index + 1) * 100 / stage_count)

    def callback(value: int) -> None:
        bounded = max(0, min(100, value))
        progress(round(start + (end - start) * bounded / 100))

    return callback


def _clear_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def _is_sln_pic_g(path: Path) -> bool:
    return path.is_file() and path.name.lower().endswith(G_SUFFIX)


def _discover_stage_files(path: Path) -> list[Path]:
    return sorted(
        (item for item in path.iterdir() if _is_sln_pic_g(item)),
        key=lambda item: item.name.casefold(),
    )


def _prepare_source(
    settings: PipelineSettings,
    stage_source: Path,
    log: LogCallback,
) -> list[Path]:
    _clear_directory(stage_source)

    if settings.input_mode == InputMode.SINGLE_FILE:
        source = settings.source_path
        if not source.is_file():
            raise FileNotFoundError(f"原始输入文件不存在：{source}")
        if not source.name.lower().endswith(G_SUFFIX):
            raise ValueError(f"单个输入文件必须以 {G_SUFFIX} 结尾：{source.name}")
        target = stage_source / source.name
        shutil.copy2(source, target)
        log(f"已载入单个文件：{source}")
        return [target]

    source_dir = settings.source_path
    if not source_dir.is_dir():
        raise NotADirectoryError(f"原始输入目录不存在：{source_dir}")
    files = _discover_stage_files(source_dir)
    if not files:
        raise FileNotFoundError(f"目录中没有以 {G_SUFFIX} 结尾的文件：{source_dir}")

    outputs: list[Path] = []
    for source in files:
        target = stage_source / source.name
        shutil.copy2(source, target)
        outputs.append(target)
    log(f"已载入目录：{source_dir}，共 {len(outputs)} 个 G 文件。")
    return outputs


def _name_with_suffix(input_name: str, suffix: str) -> str:
    if not suffix:
        return input_name
    if input_name.lower().endswith(G_SUFFIX):
        return input_name[: -len(G_SUFFIX)] + suffix + G_SUFFIX
    if input_name.lower().endswith(".g"):
        return input_name[:-2] + suffix + ".g"
    return input_name + suffix


def _copy_final_files(
    source_dir: Path,
    output_dir: Path,
    log: LogCallback,
    *,
    suffix: str = "",
    selected_names: set[str] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = _discover_stage_files(source_dir)
    if selected_names is not None:
        files = [item for item in files if item.name in selected_names]
    if not files:
        return []

    outputs: list[Path] = []
    for source in files:
        target = output_dir / _name_with_suffix(source.name, suffix)
        shutil.copy2(source, target)
        outputs.append(target)
        log(f"最终输出：{target}")
    return outputs


def _copy_selected_to_stage(
    source_dir: Path,
    target_dir: Path,
    selected_names: set[str],
) -> list[Path]:
    _clear_directory(target_dir)
    outputs: list[Path] = []
    for source in _discover_stage_files(source_dir):
        if source.name not in selected_names:
            continue
        target = target_dir / source.name
        shutil.copy2(source, target)
        outputs.append(target)
    return outputs


def run_pipeline(
    settings: PipelineSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """执行一键流程，所有中间目录均位于 AppData 临时工作区。"""
    work = settings.temp_work_dir
    _clear_directory(work)
    stage_source = work / "00_source"
    stage_basic = work / "01_basic_processed"
    stage_merged = work / "02_merged"
    stage_adjusted = work / "03_adjusted"
    stage_frame_input = work / "04_frame_input"
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    source_files = _prepare_source(settings, stage_source, log)
    effective_merge = (
        settings.run_merge
        and settings.input_mode == InputMode.DIRECTORY
        and len(source_files) > 1
    )
    warnings: list[str] = []
    if settings.run_merge and not effective_merge:
        message = "单个文件或目录中只有一个文件，不执行 G 文件合并。"
        warnings.append(message)
        log(message)

    enabled_stages = [
        settings.run_basic,
        effective_merge,
        settings.run_margin,
        settings.run_frame,
    ]
    stage_count = max(1, sum(enabled_stages))
    stage_index = 0
    current_input = stage_source
    completed_names: list[str] = []
    outputs: list[Path] = []
    existing_frame_names: set[str] = set()

    if settings.run_basic:
        log("\n=== 阶段 1：基础处理 ===")
        basic = settings.basic.model_copy(
            update={
                "source_path": current_input,
                "input_mode": InputMode.DIRECTORY,
                "output_dir": stage_basic,
            }
        )
        result = process_basic(
            basic,
            log=log,
            progress=_stage_progress(progress, stage_index, stage_count),
        )
        stage_index += 1
        current_input = stage_basic
        outputs = result.output_files
        completed_names.append("基础处理")

    if effective_merge:
        log("\n=== 阶段 2：G 文件合并 ===")
        merge = settings.merge.model_copy(
            update={"input_dir": current_input, "output_dir": stage_merged}
        )
        result = merge_feeders(
            merge,
            log=log,
            progress=_stage_progress(progress, stage_index, stage_count),
        )
        stage_index += 1
        current_input = stage_merged
        outputs = result.output_files
        completed_names.append("G 文件合并")

    if settings.run_margin:
        log("\n=== 阶段 3：图形边距调整 ===")
        margin = settings.margin.model_copy(
            update={
                "source_path": current_input,
                "input_mode": InputMode.DIRECTORY,
                "output_dir": stage_adjusted,
                # 一键流程内部保持文件名，最终命名由添加图框或最终输出阶段决定。
                "output_suffix": "",
            }
        )
        result = adjust_graph_margins(
            margin,
            log=log,
            progress=_stage_progress(progress, stage_index, stage_count),
        )
        stage_index += 1
        current_input = stage_adjusted
        outputs = result.output_files
        existing_frame_names = set(
            result.statistics.get("files_with_existing_frame", [])
        )
        completed_names.append("图形边距调整")

    if settings.run_frame:
        log("\n=== 阶段 4：添加图框 ===")
        current_names = {item.name for item in _discover_stage_files(current_input)}
        skip_names = existing_frame_names & current_names
        frame_names = current_names - skip_names

        outputs = []
        if skip_names:
            log(
                f"检测到 {len(skip_names)} 个文件已包含完整图框；图形边距调整已保留并同步适配，"
                "为避免重复图框，本阶段将直接输出这些文件。"
            )
            outputs.extend(
                _copy_final_files(
                    current_input,
                    settings.output_dir,
                    log,
                    suffix=settings.frame.output_suffix,
                    selected_names=skip_names,
                )
            )

        if frame_names:
            _copy_selected_to_stage(current_input, stage_frame_input, frame_names)
            frame = settings.frame.model_copy(
                update={
                    "source_path": stage_frame_input,
                    "input_mode": InputMode.DIRECTORY,
                    "output_dir": settings.output_dir,
                }
            )
            result = add_drawing_frames(
                frame,
                log=log,
                progress=_stage_progress(progress, stage_index, stage_count),
            )
            outputs.extend(result.output_files)
        elif progress:
            stage_callback = _stage_progress(progress, stage_index, stage_count)
            if stage_callback:
                stage_callback(100)

        completed_names.append("添加图框/保留已有图框")
    else:
        outputs = _copy_final_files(current_input, settings.output_dir, log)
        if not completed_names:
            completed_names.append("原样输出")

    if progress:
        progress(100)
    return ProcessingResult(
        success=True,
        output_files=outputs,
        warnings=warnings,
        statistics={
            "input_mode": settings.input_mode.value,
            "input_count": len(source_files),
            "stages_completed": len(completed_names),
            "stage_names": " → ".join(completed_names),
            "output_count": len(outputs),
            "files_with_existing_frame": sorted(existing_frame_names),
            "temporary_workspace": str(work),
        },
    )
