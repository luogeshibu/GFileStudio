from pathlib import Path


def test_global_content_analysis_module_is_removed_from_the_ui():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert not Path("g_file_studio/ui/pages/symbol_inventory_page.py").exists()
    assert "SymbolInventoryPage" not in main
    assert '"G 图形内容解析"' not in main


def test_locked_active_standard_hides_graphic_discovery_input_panel():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self.discovery_input_panel = QWidget()' in source
    assert 'def _set_discovery_input_visible(self, visible: bool)' in source
    assert 'self.discovery_input_panel.setVisible(visible)' in source
    assert 'self.discovery_locked_note.setVisible(not visible)' in source
    assert 'allow_discovery = (not name) or bool(active and profile is not None and not locked)' in source
    assert 'self._set_discovery_input_visible(not bool(active and profile.locked))' in source
    assert 'self._set_discovery_input_visible(True)' in source
