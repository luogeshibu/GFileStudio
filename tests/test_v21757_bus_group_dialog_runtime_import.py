from pathlib import Path


def test_merge_page_imports_qheaderview_for_manual_group_dialog():
    text = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert "QHeaderView" in text.split("from g_file_studio.models", 1)[0]
    assert "header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)" in text
