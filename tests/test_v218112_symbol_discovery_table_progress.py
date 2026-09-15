from pathlib import Path


def test_symbol_standard_table_has_serial_gutter_and_live_summary():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "vertical_header.setVisible(True)" in source
    assert "self.standard_table_overview = QLabel" in source
    assert "图元标准表（左侧为序号）：共 {total} 项图元" in source
    assert "扫描实例 {instances} 个" in source
    assert "table.setVerticalHeaderLabels(labels)" in source


def test_graphic_discovery_progress_is_next_to_scan_and_immediate():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    progress_pos = source.index("self.scan_progress = QProgressBar()")
    table_pos = source.index("self.standard_table = QTableWidget")
    assert progress_pos < table_pos
    scan_start = source.index("def _scan_graphic_symbol_candidates")
    scan_end = source.index("def _on_graphic_discovery_result", scan_start)
    scan = source[scan_start:scan_end]
    assert "self.scan_progress.setVisible(True)" in scan
    assert "QTimer.singleShot(0" in scan
    assert "self._scan_pool.start" in scan


def test_remote_discovery_download_is_not_prepared_on_ui_thread():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    scan_start = source.index("def _scan_graphic_symbol_candidates")
    scan_end = source.index("def _on_graphic_discovery_result", scan_start)
    scan = source[scan_start:scan_end]
    assert "if input_mode == InputMode.REMOTE_SSH" in scan
    assert "download_stable_files(" in scan
    assert "prepare_for_processing(" not in scan
    assert "validate_input_source(self, self.discovery_source" in scan  # local path validation remains
    assert "self.scan_progress.setRange(0, 0)" in scan


def test_release_version_is_218112():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
