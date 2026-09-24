from __future__ import annotations

from pathlib import Path


def _slice(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def test_startup_profile_selection_does_not_clear_restored_server_inventory() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    method = _slice(source, "def _profile_selection_changed", "def _restore_selected_version")
    else_anchor = "if load_catalog:"
    assert else_anchor in method
    # The independent server AppData cache/table must survive the deferred
    # load_catalog=False startup profile selection.
    tail = method[method.index(else_anchor):]
    assert "self._server_file_inventory.clear()" not in tail
    assert "self._server_catalog_records.clear()" not in tail
    assert "self.standard_table.setRowCount(0)" not in tail
    assert "Keep the cached server catalog/table exactly as restored" in tail


def test_version_is_v218197() -> None:
    assert '__version__ = "2.18.198"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.198"' in Path("pyproject.toml").read_text(encoding="utf-8")
