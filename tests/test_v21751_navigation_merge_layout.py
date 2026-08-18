from pathlib import Path


def test_history_page_removed_from_navigation():
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "HistoryPage" not in text
    assert '("操作历史"' not in text


def test_merge_local_and_remote_sources_do_not_use_stacked_widget():
    text = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert "QStackedWidget" not in text
    assert "self.local_input_page.setVisible(not remote)" in text
    assert "self.remote_source.setVisible(remote)" in text


def test_shared_input_selector_only_shows_active_source():
    text = Path("g_file_studio/ui/widgets/input_source_selector.py").read_text(encoding="utf-8")
    assert "QStackedWidget" not in text
    assert "self.file_row.setVisible(mode == InputMode.SINGLE_FILE)" in text
    assert "self.dir_row.setVisible(mode == InputMode.DIRECTORY)" in text
    assert "self.remote.setVisible(mode == InputMode.REMOTE_SSH)" in text


def test_merge_output_is_managed_workspace_read_only():
    text = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert 'configure_managed_output(self.output_path, "merge")' in text
    assert 'begin_managed_run(self.output_path, "merge", "merge")' in text
