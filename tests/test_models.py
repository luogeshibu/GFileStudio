from pathlib import Path

from g_file_studio.models import (
    BasicSettings,
    FrameSettings,
    InputMode,
    MarginSettings,
    MergeSettings,
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

