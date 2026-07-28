from __future__ import annotations

import contextlib
import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines import frame_engine
from g_file_studio.models import FrameSettings, ProcessingResult
from g_file_studio.processors.common import (
    CallbackWriter,
    LogCallback,
    ProgressCallback,
    redirect_safe_callback,
)


def _output_name(input_name: str, suffix: str) -> str:
    if not suffix:
        return input_name
    compound = ".sln.pic.g"
    if input_name.lower().endswith(compound):
        return input_name[: -len(compound)] + suffix + compound
    if input_name.lower().endswith(".g"):
        return input_name[:-2] + suffix + ".g"
    return input_name + suffix


def add_drawing_frames(
    settings: FrameSettings,
    log: LogCallback = print,
    progress: ProgressCallback | None = None,
) -> ProcessingResult:
    if not settings.input_dir.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{settings.input_dir}")
    if not settings.template_file.is_file():
        raise FileNotFoundError(f"模板文件不存在：{settings.template_file}")
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in settings.input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".g")
    if not files:
        raise FileNotFoundError(f"输入目录中没有 .g 文件：{settings.input_dir}")

    template_tree = ET.parse(settings.template_file)
    if template_tree.getroot().tag != "G":
        raise ValueError("图框模板根节点必须是 G")

    # 模板识别函数使用这些模块级常量；运行前按 App 参数设置。
    frame_engine.FRAME_MARGIN_LEFT = settings.frame_left
    frame_engine.FRAME_MARGIN_TOP = settings.frame_top
    frame_engine.FRAME_MARGIN_RIGHT = settings.frame_right
    frame_engine.FRAME_MARGIN_BOTTOM = settings.frame_bottom
    frame_engine.OVERWRITE_OUTPUT = settings.overwrite
    frame_engine.OUTPUT_NAME_SUFFIX = settings.output_suffix

    all_config = settings.config_dict()
    outputs: list[Path] = []
    writer = CallbackWriter(redirect_safe_callback(log))

    for index, input_path in enumerate(files, 1):
        output_path = settings.output_dir / _output_name(input_path.name, settings.output_suffix)
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            frame_engine.process_one_file(
                input_path=input_path,
                output_path=output_path,
                template_tree=template_tree,
                all_config=all_config,
            )
        writer.flush()
        outputs.append(output_path)
        if progress:
            progress(round(index * 100 / len(files)))

    return ProcessingResult(
        success=True,
        output_files=outputs,
        statistics={"file_count": len(outputs), "template": str(settings.template_file)},
    )
