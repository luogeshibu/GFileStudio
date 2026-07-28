from pathlib import Path

from g_file_studio.models import (
    BasicSettings,
    FrameSettings,
    MergeSettings,
    PipelineSettings,
)


def test_output_name_gets_sln_pic_g_suffix():
    settings = MergeSettings(input_dir=Path("a"), output_dir=Path("b"), output_name="merged")
    assert settings.output_name == "merged.sln.pic.g"


def test_output_name_replaces_plain_g_suffix():
    settings = MergeSettings(input_dir=Path("a"), output_dir=Path("b"), output_name="merged.g")
    assert settings.output_name == "merged.sln.pic.g"


def test_pipeline_cleans_work_directories_by_default():
    pipeline = PipelineSettings(
        source_dir=Path("input"),
        work_dir=Path("work"),
        output_dir=Path("output"),
        template_file=Path("template.g"),
        basic=BasicSettings(input_dir=Path("input"), output_dir=Path("processed")),
        merge=MergeSettings(input_dir=Path("processed"), output_dir=Path("merged")),
        frame=FrameSettings(
            input_dir=Path("merged"),
            output_dir=Path("output"),
            template_file=Path("template.g"),
        ),
    )
    assert pipeline.clear_work_dirs is True
