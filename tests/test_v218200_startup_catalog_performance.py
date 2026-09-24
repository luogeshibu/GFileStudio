from __future__ import annotations

import json
from pathlib import Path

from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


def test_main_window_true_lazy_startup_and_chinese_skips_full_tree_translation() -> None:
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "self._startup_page_order = [self._startup_target_page]" in text
    assert "QTimer.singleShot(150, self._load_next_startup_page)" in text
    assert "if self.language_manager.is_english:" in text
    assert "self.language_manager.translate_widget_tree(page)" in text


def test_catalog_public_action_state_never_loads_legacy_profile_repository() -> None:
    text = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "if not self._legacy_profile_state_loaded:" in text
    assert "self._refresh_catalog_action_state()" in text
    start = text.index("def _refresh_catalog_action_state")
    end = text.index("def _update_action_state", start)
    method = text[start:end]
    assert "load_profiles(" not in method
    assert "get_profile_version(" not in method
    assert "get_global_profile_selection(" not in method


def test_catalog_table_restore_is_visible_columns_only_batched_and_header_only_fit() -> None:
    text = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "self._inventory_render_batch_size = 100" in text
    assert "def _populate_server_inventory_row_fast" in text
    start = text.index("def _apply_fast_inventory_column_widths")
    end = text.index("def _restore_cached_inventory_table_fast", start)
    method = text[start:end]
    assert "resizeColumnsToContents" not in method
    assert "metrics.horizontalAdvance(title)" in method
    assert "visible = (3, 5, 6, 7, 8, 9, 18)" in method


def test_classification_edit_no_longer_rewrites_json_on_gui_callback() -> None:
    text = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = text.index("def _classification_marker_changed")
    end = text.index("@staticmethod\n    def _format_dimension", start)
    method = text[start:end]
    assert "update_classification_marker(" not in method
    assert "_pending_classification_marker_updates" in method
    assert "FunctionWorker(persist_local_markers)" in method
    assert "update_classification_markers_batch" in method


def test_batch_marker_persistence_updates_all_local_layers_once(tmp_path: Path) -> None:
    service = RemoteSymbolLibraryService(cache_root=tmp_path)
    host = "h"
    root = "/element"
    rows = []
    matched = {}
    records = {}
    for name, body in (("a.g", "A1"), ("b.g", "B2")):
        remote = f"{root}/{name}"
        standard = {
            "original_name": name,
            "devref": f"#{name}:{body}",
            "element_id": body,
            "remote_path": remote,
        }
        records[remote] = {
            "name": name,
            "remote_path": remote,
            "standard_record": dict(standard),
        }
        rows.append({
            "name": name,
            "remote_path": remote,
            "relative_path": name,
            "standard_record": dict(standard),
            "sync_status": "READY",
        })
        matched[name] = dict(standard)
    service._write_manifest(host, root, records)
    service.save_cached_sync_snapshot_payload(
        host=host,
        root=root,
        payload={"server_file_records": rows, "matched_records": matched},
    )

    saved = service.update_classification_markers_batch(
        host=host,
        root=root,
        updates={f"{root}/a.g": "AR", f"{root}/b.g": "FUSE"},
    )
    assert saved == 2
    entries = service.load_classification_marker_entries(host=host, root=root)
    by_name = {row["file_name"]: row for row in entries}
    assert by_name["a.g"]["classification_marker"] == "AR"
    assert by_name["a.g"]["element_id"] == "A1"
    assert by_name["b.g"]["classification_marker"] == "FUSE"
    assert by_name["b.g"]["element_id"] == "B2"

    snapshot_path = service._sync_snapshot_path(host, root, existing=True)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_markers = {
        row["name"]: row.get("classification_marker", "")
        for row in payload["server_file_records"]
    }
    assert snapshot_markers == {"a.g": "AR", "b.g": "FUSE"}


def test_version_218200() -> None:
    assert '__version__ = "2.18.201"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.201"' in Path("pyproject.toml").read_text(encoding="utf-8")
