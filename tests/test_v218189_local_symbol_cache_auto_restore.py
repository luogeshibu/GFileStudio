from __future__ import annotations

from pathlib import Path

from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


def test_local_snapshot_payload_roundtrip_without_network(tmp_path: Path) -> None:
    service = RemoteSymbolLibraryService(cache_root=tmp_path / "SymbolLibrary")
    payload = {
        "server_file_records": [
            {
                "name": "Circuit_Breaker_SMART.zwk.icn.g",
                "remote_path": "/home/up8000/data/graph/element/breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                "relative_path": "breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                "sync_status": "READY",
            }
        ],
        "matched_records": {},
        "inventory_complete": True,
    }
    path = service.save_cached_sync_snapshot_payload(
        host="172.16.21.27",
        root="/home/up8000/data/graph/element",
        payload=payload,
    )
    assert path.is_file()

    restored = service.load_cached_sync_snapshot(
        host="172.16.21.27",
        root="/home/up8000/data/graph/element",
    )
    assert len(restored["server_file_records"]) == 1
    assert restored["server_file_records"][0]["name"] == "Circuit_Breaker_SMART.zwk.icn.g"


def test_site_page_restore_is_not_gated_by_profile_selection() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = source.index("def _restore_catalog_after_activation")
    end = source.index("def _finish_initial_load", start)
    method = source[start:end]
    assert "restored = self._restore_cached_server_sync()" in method
    assert "if not restored:" in method
    assert "self._profile_selection_changed(load_catalog=True)" in method


def test_normal_page_startup_directly_restores_local_cache() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "if not self._defer_catalog_restore:" in source
    assert "self._restore_cached_server_sync()" in source


def test_save_to_local_persists_current_catalog_snapshot() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "save_cached_sync_snapshot_payload(" in source
    assert '"server_file_records"' in source
    assert "当前图元目录快照保存到本机缓存" in source


def test_startup_still_does_not_read_central_or_ssh() -> None:
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "fetch_classification(" not in main
    assert "fetch_connection_configs(" not in main
    assert "fetch_id_rules(" not in main
    assert "ReadOnlySshClient(" not in main


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
