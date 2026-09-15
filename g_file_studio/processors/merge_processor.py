from __future__ import annotations

import contextlib
import shutil
from decimal import Decimal
from pathlib import Path

from g_file_studio.engines import merge_engine
from g_file_studio.models import FrameSettings, InputMode, MergeSettings, PersonSettings, ProcessingResult
from g_file_studio.processors.frame_processor import add_drawing_frames
from g_file_studio.processors.common import (
    CallbackWriter,
    LogCallback,
    ProgressCallback,
    redirect_safe_callback,
    enforce_confirmed_id_rules,
)
from g_file_studio.services.output_naming import (
    default_merge_output_path,
    make_task_timestamp,
)


def merge_feeders(
    settings: MergeSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    if not settings.input_dir.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{settings.input_dir}")
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    log("正在加载并检查已导入的 G 文件……")
    if progress:
        progress(5)
    infos = merge_engine.discover_files(
        settings.input_dir,
        ordered_file_names=settings.ordered_file_names or None,
        allow_subset=bool(settings.ordered_file_names),
    )
    task_timestamp = make_task_timestamp()
    output_path = (
        settings.output_dir / settings.output_name
        if settings.output_name
        else default_merge_output_path(settings.output_dir, task_timestamp)
    )
    if settings.output_name:
        log(f"使用用户指定输出文件名：{output_path.name}")
    else:
        log(f"未填写输出文件名，自动生成：{output_path.name}")

    frame_stage_dir: Path | None = None
    merge_output_path = output_path
    if settings.add_frame_after_merge:
        if settings.frame_template_file is None or not Path(settings.frame_template_file).is_file():
            raise FileNotFoundError(f"馈线合并图框模板不存在：{settings.frame_template_file}")
        frame_stage_dir = settings.output_dir / f".merge-frame-stage-{task_timestamp}"
        frame_stage_dir.mkdir(parents=True, exist_ok=True)
        merge_output_path = frame_stage_dir / output_path.name
        log("已启用“合并完成后自动添加图框”；先生成无图框中间文件，再复用图框添加模块生成最终文件。")

    if progress:
        progress(10)
    writer = CallbackWriter(redirect_safe_callback(log))
    try:
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            merge_engine.merge_g_files(
                infos=infos,
                output_path=merge_output_path,
                gap=Decimal(settings.feeder_gap),
                feeder_min_width=Decimal(settings.feeder_min_width),
                merge_main_bus=bool(settings.merge_main_bus),
                main_bus_mode=settings.main_bus_mode,
                main_bus_groups=settings.main_bus_groups,
                left_margin=Decimal(settings.left_margin),
                top_margin=Decimal(settings.top_margin),
                right_margin=Decimal(settings.right_margin),
                bottom_margin=Decimal(settings.bottom_margin),
            )
        writer.flush()
        enforce_confirmed_id_rules(merge_output_path, log)

        frame_added = 0
        if settings.add_frame_after_merge:
            if progress:
                progress(85)
            frame_settings = FrameSettings(
                source_path=merge_output_path,
                input_mode=InputMode.SINGLE_FILE,
                output_dir=settings.output_dir,
                template_file=Path(settings.frame_template_file),
                template_mode=settings.frame_template_mode,
                builtin_template_id=settings.frame_builtin_template_id,
                title="",
                draw=PersonSettings(),
                approve=PersonSettings(),
                issue=PersonSettings(),
                frame_left=settings.frame_left,
                frame_top=settings.frame_top,
                frame_right=settings.frame_right,
                frame_bottom=settings.frame_bottom,
                output_suffix="",
                append_timestamp=False,
                task_timestamp=task_timestamp,
                overwrite=True,
            )
            frame_result = add_drawing_frames(
                frame_settings,
                log=log,
                progress=(
                    (lambda value: progress(85 + round(max(0, min(100, int(value))) * 15 / 100)))
                    if progress
                    else None
                ),
            )
            if not frame_result.output_files:
                raise RuntimeError("馈线合并完成，但自动图框添加没有生成最终 G 文件。")
            output_path = Path(frame_result.output_files[0])
            frame_added = 1
            log(f"[馈线图合并/自动图框] 已添加图框：{output_path.name}")
        elif progress:
            progress(100)
    finally:
        writer.flush()
        if frame_stage_dir is not None and frame_stage_dir.exists():
            shutil.rmtree(frame_stage_dir, ignore_errors=True)

    return ProcessingResult(
        success=True,
        output_files=[output_path],
        statistics={
            "input_count": len(infos),
            "input_order": [info.path.name for info in infos],
            "feeder_gap": settings.feeder_gap,
            "feeder_min_width": settings.feeder_min_width,
            "merge_main_bus": settings.merge_main_bus,
            "main_bus_mode": settings.main_bus_mode,
            "main_bus_groups": settings.main_bus_groups,
            "frame_added": frame_added,
            "frame_template": str(settings.frame_template_file or ""),
            "output_file": str(output_path),
        },
    )
