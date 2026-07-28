from pathlib import Path


def test_file_order_editor_has_remove_selected_subset_support():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "g_file_studio"
        / "ui"
        / "widgets"
        / "file_order_editor.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert 'QPushButton("删除所选")' in source
    assert "ExtendedSelection" in source
    assert "def remove_selected" in source
    assert "selectedRows" in source
    assert "_excluded_names" in source
    assert "allow_subset=True" in source
    assert "不会删除磁盘" in source


def test_merge_processor_enables_subset_when_order_is_supplied():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "g_file_studio"
        / "processors"
        / "merge_processor.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert "allow_subset=bool(settings.ordered_file_names)" in source
