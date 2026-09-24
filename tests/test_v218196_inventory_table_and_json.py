from __future__ import annotations

from pathlib import Path


def test_operator_inventory_keeps_table_but_removes_xml_element_tag_surface() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self._server_inventory_table_enabled = True" in source
    assert "self.standard_table.setVisible(True)" in source
    assert "self.standard_table_overview.setVisible(True)" in source
    assert "self.standard_table_search.setVisible(True)" in source
    assert "XML element type (column 2) is intentionally removed" in source
    assert 'self._hidden_standard_columns = {0, 1, 2, 4, 10, 11, 12, 13, 14, 15, 16, 17, 19}' in source
    assert 'display_path = relative_path or file_name' in source


def test_user_facing_classification_json_is_schema2_and_xml_free() -> None:
    remote = Path("g_file_studio/services/remote_symbol_library.py").read_text(encoding="utf-8")
    registry = Path("g_file_studio/services/classification_registry_service.py").read_text(encoding="utf-8")
    assert '"schema": 2' in remote
    validate_start = registry.index("def _validate_payload")
    validate_end = registry.index("def fetch", validate_start)
    validate = registry[validate_start:validate_end]
    assert '"schema": 2' in validate
    assert '"relative_path"' in validate
    assert '"file_name"' in validate
    assert '"devref"' in validate
    assert '"classification_marker"' in validate
    # The central normalized marker object must not propagate XML element-tag fields.
    cleaned_block = validate[validate.index("cleaned = {"):]
    assert 'element_tag' not in cleaned_block
    assert 'xml_tag' not in cleaned_block
    assert 'target_xml' not in cleaned_block


def test_normal_sync_uses_fast_fixed_width_inventory_rendering() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = source.index("def _apply_server_library_payload")
    end = source.index("def _create_next_version_from_server", start)
    method = source[start:end]
    assert "_apply_fast_inventory_column_widths()" in method
    assert "_fit_standard_table_columns()" not in method
