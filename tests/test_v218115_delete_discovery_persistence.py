from pathlib import Path


def _page_source() -> str:
    return Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")


def test_deleted_discovery_row_is_persistently_ignored_in_profile():
    source = _page_source()
    delete_start = source.index("def _delete_selected_custom_standard")
    delete_end = source.index("def _add_unmapped_scanned_symbols", delete_start)
    delete_block = source[delete_start:delete_end]
    assert 'self._discovery_decisions[observed_devref] = "ignored"' in delete_block
    assert "self._graphic_discovery_catalog.pop(observed_devref, None)" in delete_block

    save_start = source.index("def _save_profile")
    save_end = source.index("def _delete_profile", save_start)
    save_block = source[save_start:save_end]
    assert "discovery_decisions=self._discovery_decisions" in save_block


def test_ignored_discovery_is_not_readded_when_profile_reload_applies_catalog():
    source = _page_source()
    apply_start = source.index("def _apply_discovery_to_rows")
    apply_end = source.index("def _apply_standard_table_filter", apply_start)
    apply_block = source[apply_start:apply_end]
    assert 'self._discovery_decisions.get(observed_devref, "")' in apply_block
    assert '== "ignored"' in apply_block

    select_start = source.index("def _profile_selection_changed")
    select_end = source.index("def _restore_selected_version", select_start)
    select_block = source[select_start:select_end]
    assert "self._discovery_decisions =" in select_block
    assert "profile.discovery_decisions.items()" in select_block


def test_profile_summary_distinguishes_effective_and_ignored_discovery_rows():
    source = _page_source()
    assert "有效图形G发现候选 {active_discovery_count} 种" in source
    assert 'ignored_text = f"，已忽略 {ignored_count} 种"' in source


def test_release_version_is_218115():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
