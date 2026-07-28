from pathlib import Path

from g_file_studio.models import (
    BasicSettings,
    FrameSettings,
    InputMode,
    MarginSettings,
    MergeSettings,
    PipelineSettings,
    TemplateMode,
)


def test_output_name_gets_sln_pic_g_suffix():
    settings = MergeSettings(input_dir=Path("a"), output_dir=Path("b"), output_name="merged")
    assert settings.output_name == "merged.sln.pic.g"


def test_output_name_replaces_plain_g_suffix():
    settings = MergeSettings(input_dir=Path("a"), output_dir=Path("b"), output_name="merged.g")
    assert settings.output_name == "merged.sln.pic.g"


def test_custom_template_does_not_edit_content():
    frame = FrameSettings(
        source_path=Path("in"),
        input_mode=InputMode.DIRECTORY,
        output_dir=Path("out"),
        template_file=Path("template.g"),
        template_mode=TemplateMode.CUSTOM,
    )
    assert frame.edit_builtin_content is False


def test_margin_defaults_are_500():
    margin = MarginSettings(source_path=Path("in"), output_dir=Path("out"))
    assert (margin.left_margin, margin.top_margin, margin.right_margin, margin.bottom_margin) == (
        500,
        500,
        500,
        500,
    )
    assert margin.preserve_existing_frame is True


def test_pipeline_uses_hidden_temp_work_dir():
    pipeline = PipelineSettings(
        source_path=Path("input/a.sln.pic.g"),
        input_mode=InputMode.SINGLE_FILE,
        temp_work_dir=Path("cache/session"),
        output_dir=Path("output"),
        basic=BasicSettings(source_path=Path("x"), input_mode=InputMode.DIRECTORY, output_dir=Path("y")),
        merge=MergeSettings(input_dir=Path("y"), output_dir=Path("z")),
        margin=MarginSettings(source_path=Path("z"), output_dir=Path("m")),
        frame=FrameSettings(
            source_path=Path("m"),
            input_mode=InputMode.DIRECTORY,
            output_dir=Path("output"),
            template_file=Path("template.g"),
        ),
    )
    assert pipeline.temp_work_dir == Path("cache/session")
