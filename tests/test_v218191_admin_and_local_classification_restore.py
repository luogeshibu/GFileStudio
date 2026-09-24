from __future__ import annotations

import json
from pathlib import Path

from g_file_studio.services.remote_symbol_library import RemoteSymbolLibraryService


def test_admin_lease_config_method_exists_and_is_local_only() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = source.index("def _admin_lease_config")
    end = source.index("def _toggle_admin_mode", start)
    method = source[start:end]
    assert "self.discovery_source.remote.config()" in method
    assert "ClassificationRegistryService" not in method
    assert "fetch_admin_lease(" not in method
    assert "instance.json" in method  # docstring explicitly says it is NOT read


def test_classification_marker_loader_uses_override_file_even_if_manifest_marker_missing(tmp_path: Path) -> None:
    cache_root = tmp_path / "SymbolLibrary"
    service = RemoteSymbolLibraryService(cache_root=cache_root)
    host = "172.16.21.27"
    root = "/home/up8000/data/graph/element"
    remote_path = root + "/breaker_dis/Circuit_Breaker_SMART.zwk.icn.g"

    # Build a minimal catalog manifest with no classification marker.
    service._write_manifest(
        host,
        root,
        {
            remote_path: {
                "name": "Circuit_Breaker_SMART.zwk.icn.g",
                "remote_path": remote_path,
                "relative_path": "breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                "standard_record": {
                    "original_name": "Circuit_Breaker_SMART.zwk.icn.g",
                    "remote_path": remote_path,
                    "devref": "#Circuit_Breaker_SMART.zwk.icn.g:CBreakerDis",
                },
            }
        },
    )

    # Authoritative local classification layer contains the marker.
    marker_path = service._marker_overrides_path(host, root)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "markers": [
                    {
                        "relative_path": "breaker_dis/Circuit_Breaker_SMART.zwk.icn.g",
                        "file_name": "Circuit_Breaker_SMART.zwk.icn.g",
                        "devref": "#Circuit_Breaker_SMART.zwk.icn.g:CBreakerDis",
                        "classification_marker": "CIRCUIT_BREAKER_SMART",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markers = service.load_classification_markers(host=host, root=root)
    assert markers[remote_path] == "CIRCUIT_BREAKER_SMART"


def test_snapshot_restore_receives_classification_before_table_rebuild() -> None:
    service = Path("g_file_studio/services/remote_symbol_library.py").read_text(encoding="utf-8")
    load_start = service.index("def load_cached_sync_snapshot")
    load_end = service.index("def _", load_start + 10)
    loader = service[load_start:load_end]
    assert "overrides = self._load_marker_overrides(host, root)" in loader
    assert "self._apply_marker_override(" in loader

    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    start = page.index("def _restore_cached_server_sync")
    end = page.index("def _persist_server_library_settings", start)
    method = page[start:end]
    assert "self._apply_server_library_payload(" in method
    assert "self._refresh_local_classification_markers()" not in method
    assert "分类标记" in method


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
