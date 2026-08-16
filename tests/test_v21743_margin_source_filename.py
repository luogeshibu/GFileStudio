from pathlib import Path

from g_file_studio.models import InputMode, MarginSettings
from g_file_studio.processors.margin_processor import adjust_graph_margins


def test_margin_page_has_no_output_suffix_field():
    source = Path("g_file_studio/ui/pages/margin_page.py").read_text(encoding="utf-8")
    assert 'HelpLabel("输出标记"' not in source
    assert 'output_suffix=""' in source
    assert 'append_timestamp=False' in source


def test_margin_processor_uses_source_filename(tmp_path: Path, monkeypatch):
    src_dir = tmp_path / "src"
    out_dir = tmp_path / "out"
    src_dir.mkdir(); out_dir.mkdir()
    src = src_dir / "A.sln.pic.g"
    src.write_text('<G w="10" h="10"><Layer/></G>', encoding="utf-8")

    class Result:
        had_existing_frame=False
        old_canvas_width=10; old_canvas_height=10
        new_canvas_width=20; new_canvas_height=20
        body_left_margin=1; body_top_margin=1; body_right_margin=1; body_bottom_margin=1
        frame_detection_mode=""
        frame_left_margin=0; frame_top_margin=0; frame_right_margin=0; frame_bottom_margin=0

    def fake_adjust(input_path, output_path, **kwargs):
        output_path.write_text(input_path.read_text(encoding="utf-8"), encoding="utf-8")
        return Result()
    monkeypatch.setattr("g_file_studio.processors.margin_processor.adjust_one_file", fake_adjust)
    monkeypatch.setattr("g_file_studio.processors.margin_processor.enforce_confirmed_id_rules", lambda *a, **k: None)

    settings = MarginSettings(source_path=src, input_mode=InputMode.SINGLE_FILE, output_dir=out_dir)
    result = adjust_graph_margins(settings)
    assert result.output_files == [out_dir / src.name]
    assert result.statistics["output_naming"] == "source_filename"


def test_margin_processor_rejects_same_source_target(tmp_path: Path):
    src = tmp_path / "A.sln.pic.g"
    src.write_text('<G w="10" h="10"><Layer/></G>', encoding="utf-8")
    settings = MarginSettings(source_path=src, input_mode=InputMode.SINGLE_FILE, output_dir=tmp_path)
    try:
        adjust_graph_margins(settings)
    except ValueError as exc:
        assert "禁止覆盖原始 G 文件" in str(exc)
    else:
        raise AssertionError("expected ValueError")
