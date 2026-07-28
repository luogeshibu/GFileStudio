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
)


def merge_feeders(
    settings: MergeSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    if not settings.input_dir.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{settings.input_dir}")
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    if progress:
        progress(5)
    infos = merge_engine.discover_files(
        settings.input_dir,
        ordered_file_names=settings.ordered_file_names or None,
        allow_subset=bool(settings.ordered_file_names),
    )
    output_path = (
        settings.output_dir / settings.output_name
        if settings.output_name
        else merge_engine.build_default_output_path(settings.output_dir, infos)
    )

    writer = CallbackWriter(redirect_safe_callback(log))
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        merge_engine.merge_g_files(
            infos=infos,
            output_path=output_path,
            gap=Decimal(settings.feeder_gap),
            left_margin=Decimal(settings.left_margin),
            top_margin=Decimal(settings.top_margin),
            right_margin=Decimal(settings.right_margin),
            bottom_margin=Decimal(settings.bottom_margin),
        )
    writer.flush()
    if progress:
        progress(100)

    return ProcessingResult(
        success=True,
        output_files=[output_path],
        statistics={
            "input_count": len(infos),
            "input_order": [info.path.name for info in infos],
            "feeder_gap": settings.feeder_gap,
            "output_file": str(output_path),
        },
    )
