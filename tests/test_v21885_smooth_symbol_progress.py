from pathlib import Path


def test_symbol_standard_page_uses_smooth_determinate_progress_only():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self.task.set_live_progress_enabled(False)" in source
    assert "self.task.set_smooth_progress_enabled(True)" in source
    assert "0~100% 百分比样式显示，并平滑递增" in source


def test_task_panel_smoothing_is_target_driven_and_monotonic():
    source = Path("g_file_studio/ui/widgets/task_panel.py").read_text(encoding="utf-8")
    assert "self._smooth_progress_timer.setInterval(30)" in source
    assert "value = max(int(self._last_progress_value), value)" in source
    assert "self._smooth_progress_target = max(int(self._smooth_progress_target), value)" in source
    assert "self.progress.setValue(current)" in source
    # Raw worker callbacks must not repaint the progress bar when smoothing is enabled.
    block = source[source.index("def _on_worker_progress") : source.index("def log_view_clear")]
    assert "if self._smooth_progress_enabled:" in block
    assert "self.progress.setValue(value)" in block  # only the explicit non-smooth branch


def test_release_version_is_21885():
    assert '__version__ = "2.18.97"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.97"' in Path("pyproject.toml").read_text(encoding="utf-8")
