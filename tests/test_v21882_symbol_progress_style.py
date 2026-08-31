from pathlib import Path


def test_symbol_standard_page_keeps_determinate_percentage_progress():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self.task.set_live_progress_enabled(False)" in source
    assert "始终以 0~100% 百分比样式显示" in source
    block = source[source.index("self.task = TaskPanel()") : source.index("self.task.set_result_dialogs_enabled(False)")]
    assert "set_live_progress_enabled(True)" not in block


def test_release_version_is_21882():
    assert '__version__ = "2.18.97"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.97"' in Path("pyproject.toml").read_text(encoding="utf-8")
