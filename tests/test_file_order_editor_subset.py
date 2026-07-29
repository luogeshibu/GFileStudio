from pathlib import Path


def test_file_order_editor_supports_fuzzy_import_and_subset_ordering():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "g_file_studio"
        / "ui"
        / "widgets"
        / "file_order_editor.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert 'QPushButton("加载 / 检查")' in source
    assert 'QPushButton("查询并导入")' in source
    assert 'QPushButton("全选当前结果")' in source
    assert 'QPushButton("确认导入")' in source
    assert "CandidateImportDialog" in source
    assert "def _matches" in source
    assert "text.split()" in source
    assert "inspect_merge_candidates" in source
    assert "QProgressDialog" in source
    assert 'setWindowTitle("加载中")' in source

    assert 'QPushButton("删除所选")' in source
    assert "ExtendedSelection" in source
    assert "def remove_selected" in source
    assert "selectedRows" in source
    assert "_excluded_names" in source
    assert "ordered_file_names" in source
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
    assert "正在加载并检查已导入的 G 文件" in source
