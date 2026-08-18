from pathlib import Path


def test_id_processor_never_timestamp_renames_g_output():
    source = Path("g_file_studio/processors/id_processor.py").read_text(encoding="utf-8")
    assert "output_path = settings.output_dir / input_path.name" in source
    assert 'marked_output_name(input_path.name, "ID"' not in source


def test_basic_processor_output_path_is_source_filename():
    source = Path("g_file_studio/processors/basic_processor.py").read_text(encoding="utf-8")
    block = source[source.index("def _output_path_for("):source.index("def _rmu_duplicate_names")]
    assert "return settings.output_dir / input_path.name" in block
    assert "_unique_timestamp_path" not in block


def test_connection_processor_output_path_is_source_filename():
    source = Path("g_file_studio/processors/connection_processor.py").read_text(encoding="utf-8")
    block = source[source.index("def _output_path_for"):source.index("def process_connection_points")]
    assert "return settings.output_dir / input_path.name" in block
    assert "timestamp" not in block.lower()


def test_margin_frame_and_small_element_keep_source_filename():
    margin = Path("g_file_studio/processors/margin_processor.py").read_text(encoding="utf-8")
    frame = Path("g_file_studio/processors/frame_processor.py").read_text(encoding="utf-8")
    small = Path("g_file_studio/engines/small_element_engine.py").read_text(encoding="utf-8")
    assert "settings.output_dir / input_path.name" in margin
    assert "settings.output_dir / input_path.name" in frame
    assert "output_dir / source.name" in small


def test_merge_is_documented_as_multi_source_exception():
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "多源 → 单一新 G" in changelog
