from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.models import FrameSettings, InputMode, TemplateMode
from g_file_studio.processors.frame_processor import add_drawing_frames


def _template() -> Path:
    return Path(__file__).parents[1] / "resources" / "templates" / "SLD-Drawing-Frame-Template.sln.pic.g"


def _write_g(path: Path) -> None:
    path.write_text('<G w="1200" width="1200" h="900" height="900"><Layer><Text id="8000001" x="300" y="300" w="50" h="20" ts="A" /></Layer></G>', encoding="utf-8")


def test_frame_output_keeps_source_filename(tmp_path: Path):
    source = tmp_path / "JED-NTH-ABH-03.sln.pic.g"
    out = tmp_path / "out"
    _write_g(source)
    result = add_drawing_frames(FrameSettings(source_path=source, input_mode=InputMode.SINGLE_FILE, output_dir=out, template_file=_template(), template_mode=TemplateMode.BUILTIN), log=lambda _line: None)
    target = out / source.name
    assert target in result.output_files
    assert target.is_file()
    ET.parse(target)


def test_frame_skip_existing_same_name(tmp_path: Path):
    source = tmp_path / "same.sln.pic.g"
    out = tmp_path / "out"
    out.mkdir()
    _write_g(source)
    target = out / source.name
    target.write_text("KEEP", encoding="utf-8")
    result = add_drawing_frames(FrameSettings(source_path=source, input_mode=InputMode.SINGLE_FILE, output_dir=out, template_file=_template(), template_mode=TemplateMode.BUILTIN, overwrite=False), log=lambda _line: None)
    assert result.output_files == []
    assert target.read_text(encoding="utf-8") == "KEEP"


def test_frame_rejects_same_source_and_output_location(tmp_path: Path):
    source = tmp_path / "same.sln.pic.g"
    _write_g(source)
    try:
        add_drawing_frames(FrameSettings(source_path=source, input_mode=InputMode.SINGLE_FILE, output_dir=tmp_path, template_file=_template(), template_mode=TemplateMode.BUILTIN), log=lambda _line: None)
    except ValueError as exc:
        assert "禁止覆盖原始 G 文件" in str(exc)
    else:
        raise AssertionError("expected ValueError")
