from __future__ import annotations

import shutil
from pathlib import Path

from g_file_studio.models import PipelineSettings, ProcessingResult
from g_file_studio.processors.basic_processor import process_basic
from g_file_studio.processors.common import LogCallback, ProgressCallback
from g_file_studio.processors.frame_processor import add_drawing_frames
from g_file_studio.processors.merge_processor import merge_feeders


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


def _clear_directory(path: Path, log: LogCallback) -> None:
    if path.exists():
        shutil.rmtree(path)
        log(f"已清理中间目录：{path}")
    path.mkdir(parents=True, exist_ok=True)


def _copy_g_files(source_dir: Path, output_dir: Path, log: LogCallback) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for source in sorted(source_dir.glob("*.g")):
        if not source.is_file():
            continue
        target = output_dir / source.name
        shutil.copy2(source, target)
        outputs.append(target)
        log(f"复制：{source.name} → {target}")
    if not outputs:
        raise FileNotFoundError(f"目录中没有可复制的 .g 文件：{source_dir}")
    return outputs


def run_pipeline(
    settings: PipelineSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    enabled_stages = [settings.run_basic, settings.run_merge, settings.run_frame]
    stage_count = sum(enabled_stages)
    if stage_count == 0:
        raise ValueError("至少需要启用一个处理阶段。")
    if not settings.source_dir.is_dir():
        raise NotADirectoryError(f"原始输入目录不存在：{settings.source_dir}")

    work = settings.work_dir
    stage_basic = work / "01_basic_processed"
    stage_merged = work / "02_merged"
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    if settings.clear_work_dirs:
        if settings.run_basic:
            _clear_directory(stage_basic, log)
        if settings.run_merge:
            _clear_directory(stage_merged, log)

    current_input = settings.source_dir
    outputs: list[Path] = []
    stage_index = 0
    completed_names: list[str] = []

    if settings.run_basic:
        log("\n=== 阶段 1：基础处理 ===")
        basic = settings.basic.model_copy(
            update={"input_dir": current_input, "output_dir": stage_basic}
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

    if settings.run_merge:
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

    if settings.run_frame:
        log("\n=== 阶段 3：添加图框 ===")
        frame = settings.frame.model_copy(
            update={"input_dir": current_input, "output_dir": settings.output_dir}
        )
        result = add_drawing_frames(
            frame,
            log=log,
            progress=_stage_progress(progress, stage_index, stage_count),
        )
        outputs = result.output_files
        completed_names.append("添加图框")
    else:
        # 最后一个启用阶段的结果仍需要进入最终输出目录。
        outputs = _copy_g_files(current_input, settings.output_dir, log)

    if progress:
        progress(100)
    return ProcessingResult(
        success=True,
        output_files=outputs,
        statistics={
            "stages_completed": len(completed_names),
            "stage_names": " → ".join(completed_names),
            "output_count": len(outputs),
        },
    )
