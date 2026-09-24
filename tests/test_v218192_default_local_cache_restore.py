from __future__ import annotations

import json
from pathlib import Path

from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


def test_mainwindow_site_page_uses_immediate_local_restore() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    factory_start = source.index("def _create_page")
    factory_end = source.index("def _ensure_page", factory_start)
    factory = source[factory_start:factory_end]
    assert "SiteProfilePage(self.user_settings, defer_catalog_restore=False)" in factory

    finish_start = source.index("def _finish_startup_page_loading")
    finish_end = source.index("def _clear_legacy_managed_output_paths", finish_start)
    finish = source[finish_start:finish_end]
    assert "on_page_activated" not in finish
    assert "restore_local_catalog" not in finish


def test_site_page_constructor_immediately_restores_existing_local_cache() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    constructor_start = source.index("def __init__")
    constructor_end = source.index("def on_page_activated", constructor_start)
    constructor = source[constructor_start:constructor_end]
    assert "if not self._defer_catalog_restore:" in constructor
    assert "restored = self._restore_cached_server_sync()" in constructor
    assert "正在自动打开本地图元缓存" in constructor
    assert "不会自动访问服务器" in constructor


def test_legacy_cache_directory_is_found_by_host_and_root_metadata(tmp_path: Path) -> None:
    cache_root = tmp_path / "SymbolLibrary"
    legacy = cache_root / "legacy_folder_name"
    legacy.mkdir(parents=True)
    snapshot = legacy / "sync_snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema": 1,
                "host": "172.16.21.27",
                "root": "/home/up8000/data/graph/element",
                "server_file_records": [
                    {
                        "name": "Circuit_Breaker_SMART.zwk.icn.g",
                        "remote_path": "/home/up8000/data/graph/element/breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                        "relative_path": "breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                    }
                ],
                "matched_records": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = RemoteSymbolLibraryService(cache_root=cache_root)
    resolved = service._existing_library_dir(
        "172.16.21.27",
        "/home/up8000/data/graph/element",
    )
    assert resolved == legacy

    restored = service.load_cached_sync_snapshot(
        host="172.16.21.27",
        root="/home/up8000/data/graph/element",
    )
    assert len(restored["server_file_records"]) == 1


def test_local_cache_discovery_never_creates_cache_directories(tmp_path: Path) -> None:
    cache_root = tmp_path / "SymbolLibrary"
    service = RemoteSymbolLibraryService(cache_root=cache_root)
    resolved = service._existing_library_dir(
        "172.16.21.27",
        "/home/up8000/data/graph/element",
    )
    assert not cache_root.exists()
    assert not resolved.exists()


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
