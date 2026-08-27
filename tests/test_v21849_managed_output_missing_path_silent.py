from pathlib import Path


def test_main_window_clears_managed_output_history_before_pages_are_built():
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    cleanup_pos = text.index("cleanup_expired_runs()")
    clear_pos = text.index("self._clear_legacy_managed_output_paths()")
    pages_pos = text.index("self.pages = [")
    assert cleanup_pos < clear_pos < pages_pos


def test_all_managed_output_setting_keys_are_cleared():
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    expected = [
        "small_elements/output_directory",
        "id_rules/output_directory",
        "site_profile/output_directory",
        "rmu/output_directory",
        "basic/output_directory",
        "merge/output_directory",
        "margin/output_directory",
        "frame/output_directory",
        "jeddah_batch/output_directory",
    ]
    for key in expected:
        assert f'"{key}"' in text
        assert f'"recent_paths/{key}"' in text
    assert "self.user_settings.clear(key)" in text


def test_release_version_is_v21849():
    assert '__version__ = "2.18.52"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.52"' in Path('pyproject.toml').read_text(encoding='utf-8')
