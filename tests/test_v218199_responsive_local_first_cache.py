from __future__ import annotations

import json
from pathlib import Path

from g_file_studio.services.classification_registry_service import ClassificationRegistryService
from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


def test_remote_g_widget_is_local_first_and_server_io_is_off_gui_thread() -> None:
    source = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert "app_cache_root() / \"RemoteGSource\"" in source
    assert "FunctionWorker(task)" in source
    assert "QThreadPool.globalInstance()" in source
    assert "已覆盖本模块本地缓存" in source
    assert "resizeColumnsToContents" not in source
    # The synchronous API used by processing pages now waits through a Qt event
    # loop while the actual SFTP download runs in a worker, so the GUI still paints.
    assert "loop = QEventLoop(self)" in source
    assert "self._worker_pool.start(worker)" in source
    assert "_snapshot_matches_selection" in source


def test_classification_json_keeps_body_id_but_never_xml_tag(tmp_path: Path) -> None:
    service = RemoteSymbolLibraryService(cache_root=tmp_path)
    host = "172.16.21.27"
    root = "/home/up8000/data/graph/element"
    remote_path = root + "/breaker_dis/a.g"
    service._write_manifest(host, root, {
        remote_path: {
            "name": "a.g",
            "remote_path": remote_path,
            "standard_record": {
                "original_name": "a.g",
                "devref": "#a.g:BODY_1001",
                "element_id": "BODY_1001",
                "element_tag": "Breaker",
            },
            "classification_marker": "AR",
        }
    })
    service._write_marker_overrides(host, root, [{
        "relative_path": "breaker_dis/a.g",
        "file_name": "a.g",
        "devref": "#a.g:BODY_1001",
        # Simulate an existing schema-1 cache written before element_id was exported.
        "classification_marker": "AR",
    }])
    payload = service.build_classification_marker_payload(host=host, root=root)
    row = payload["markers"][0]
    assert payload["schema"] == 2
    assert row["element_id"] == "BODY_1001"
    assert "element_tag" not in row
    assert "xml_tag" not in row
    assert "target_xml" not in row

    cleaned = ClassificationRegistryService._validate_payload({
        "markers": [{
            **row,
            "element_tag": "Breaker",
            "xml_tag": "Breaker",
            "target_xml": "Breaker",
        }]
    })
    assert cleaned["markers"][0]["element_id"] == "BODY_1001"
    assert "element_tag" not in cleaned["markers"][0]
    assert "xml_tag" not in cleaned["markers"][0]
    assert "target_xml" not in cleaned["markers"][0]


def test_manual_json_import_replaces_local_marker_cache_instead_of_merging(tmp_path: Path) -> None:
    service = RemoteSymbolLibraryService(cache_root=tmp_path)
    host = "h"
    root = "/r"
    records = {
        "/r/a.g": {"name": "a.g", "remote_path": "/r/a.g", "standard_record": {"original_name": "a.g", "devref": "#a.g:A", "element_id": "A"}},
        "/r/b.g": {"name": "b.g", "remote_path": "/r/b.g", "standard_record": {"original_name": "b.g", "devref": "#b.g:B", "element_id": "B"}},
    }
    service._write_manifest(host, root, records)
    service._write_marker_overrides(host, root, [
        {"relative_path": "a.g", "file_name": "a.g", "devref": "#a.g:A", "element_id": "A", "classification_marker": "OLD_A"},
        {"relative_path": "b.g", "file_name": "b.g", "devref": "#b.g:B", "element_id": "B", "classification_marker": "OLD_B"},
    ])
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({"markers": [{
        "relative_path": "a.g", "file_name": "a.g", "devref": "#a.g:A", "element_id": "A", "classification_marker": "NEW_A"
    }]}), encoding="utf-8")
    service.import_classification_markers(host=host, root=root, source_path=incoming)
    rows = service.load_classification_marker_entries(host=host, root=root)
    assert len(rows) == 1
    assert rows[0]["classification_marker"] == "NEW_A"
    assert rows[0]["element_id"] == "A"


def test_short_central_operations_do_not_flash_progress_window() -> None:
    for name in ("database_page.py", "id_page.py", "site_profile_page.py"):
        source = Path("g_file_studio/ui/pages") / name
        text = source.read_text(encoding="utf-8")
        start = text.index("def _open_central_progress")
        end = text.index("def _close_central_progress", start)
        method = text[start:end]
        assert "setMinimumDuration(800)" in method
        assert "dialog.show()" not in method


def test_startup_allows_native_shell_to_paint_between_page_constructors() -> None:
    text = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "QTimer.singleShot(250, self._load_next_startup_page)" in text
    assert "QTimer.singleShot(120, self._load_next_startup_page)" in text


def test_version_218199() -> None:
    assert '__version__ = "2.18.199"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.199"' in Path("pyproject.toml").read_text(encoding="utf-8")
