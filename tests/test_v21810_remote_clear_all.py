from pathlib import Path


def test_remote_source_removes_clear_current_results_button():
    text = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert 'QPushButton("取消当前结果")' not in text
    assert "unselect_visible" not in text


def test_clear_all_clears_search_and_all_checks():
    text = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert 'self.clear_selection = QPushButton("清空全部")' in text
    assert 'self.clear_selection.clicked.connect(self._clear_all)' in text
    assert 'def _clear_all(self)' in text
    assert 'self.search.clear()' in text
    assert 'self._clear_checks()' in text
