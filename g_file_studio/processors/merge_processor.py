from __future__ import annotations

import contextlib
from decimal import Decimal

from g_file_studio.engines import merge_engine
from g_file_studio.models import MergeSettings, ProcessingResult
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

    if progress:
        progress(10)
    writer = CallbackWriter(redirect_safe_callback(log))
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        merge_engine.merge_g_files(
            infos=infos,
            output_path=output_path,
            gap=Decimal(settings.feeder_gap),
            feeder_min_width=Decimal(settings.feeder_min_width),
            merge_main_bus=bool(settings.merge_main_bus),
            main_bus_mode=settings.main_bus_mode,
            left_margin=Decimal(settings.left_margin),
            top_margin=Decimal(settings.top_margin),
            right_margin=Decimal(settings.right_margin),
            bottom_margin=Decimal(settings.bottom_margin),
        )
    writer.flush()
    enforce_confirmed_id_rules(output_path, log)
    if progress:
        progress(100)

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
            "output_file": str(output_path),
        },
    )
