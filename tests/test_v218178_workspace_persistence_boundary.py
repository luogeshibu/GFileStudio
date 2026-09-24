from __future__ import annotations

import re
from pathlib import Path

from g_file_studio.services.paths import (
    app_cache_root,
    app_config_root,
    app_data_root,
    default_workspace,
    ensure_default_workspace,
)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def test_version_is_consistent_and_release_notes_are_consolidated() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    pyproject_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match and pyproject_match
    assert init_match.group(1) == pyproject_match.group(1)
    assert not list(Path(".").glob("UPDATE_NOTES_v*.md"))
    assert Path("CHANGELOG.md").is_file()
    assert Path("RELEASE_NOTES.md").is_file()


def test_persistent_roots_are_outside_workspace() -> None:
    workspace = default_workspace()
    for root in (app_config_root(), app_cache_root(), app_data_root()):
        assert not _is_within(root, workspace)
        assert root != workspace


def test_workspace_contains_only_disposable_business_runtime_directories() -> None:
    workspace = ensure_default_workspace()
    expected = {"input", "remote_input", "processed", "merged", "adjusted", "work", "output", "runs"}
    actual = {p.name for p in workspace.iterdir() if p.is_dir()}
    assert expected.issubset(actual)
    for forbidden in {"config", "cache", "standards", "symbolrepository", "classification", "logs"}:
        assert forbidden not in {name.casefold() for name in actual}


def test_persistent_services_do_not_import_default_workspace() -> None:
    persistent_modules = (
        "g_file_studio/services/user_settings_service.py",
        "g_file_studio/services/id_rule_service.py",
        "g_file_studio/services/remote_symbol_library.py",
        "g_file_studio/services/site_profile_service.py",
        "g_file_studio/services/symbol_standard_repository.py",
        "g_file_studio/services/admin_access_service.py",
        "g_file_studio/services/classification_registry_service.py",
    )
    for file_name in persistent_modules:
        text = Path(file_name).read_text(encoding="utf-8")
        assert "default_workspace" not in text, file_name
        assert 'project_root() / "workspace"' not in text, file_name
