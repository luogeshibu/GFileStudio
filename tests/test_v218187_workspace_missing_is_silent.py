from __future__ import annotations

from pathlib import Path


def test_missing_workspace_paths_are_silent_in_pathrow() -> None:
    source = Path("g_file_studio/ui/widgets/path_row.py").read_text(encoding="utf-8")
    assert "def _is_disposable_workspace_path" in source
    assert "default_workspace()" in source
    assert "if missing is not None and self._is_disposable_workspace_path(missing):" in source
    assert "and not self._is_disposable_workspace_path(resolved.missing_saved_directory)" in source


def test_managed_output_runs_recreate_workspace_instead_of_validating_old_path() -> None:
    pages = {
        "frame_page.py": "begin_managed_run(self.output_path, \"frame\"",
        "margin_page.py": "begin_managed_run(self.output_path, \"margin\"",
        "orthogonalize_page.py": "begin_managed_run(self.output_path, \"orthogonalize\"",
        "merge_page.py": "begin_managed_run(self.output_path, \"merge\"",
        "poke_page.py": "begin_managed_run(self.output_path, \"poke\"",
        "basic_page.py": "begin_managed_run(self.output_path, \"basic\"",
        "id_page.py": "begin_managed_run(self.output_path, \"id\"",
    }
    root = Path("g_file_studio/ui/pages")
    for filename, run_token in pages.items():
        text = (root / filename).read_text(encoding="utf-8")
        assert run_token in text
        # Old managed-output existence validation must not gate runtime recreation.
        assert "validate_existing_directory(self, self.output_path.path()" not in text


def test_run_history_creates_workspace_on_demand() -> None:
    source = Path("g_file_studio/services/run_history.py").read_text(encoding="utf-8")
    assert 'root = default_workspace() / "runs"' in source
    assert "root.mkdir(parents=True, exist_ok=True)" in source
    assert "candidate.mkdir(parents=True, exist_ok=False)" in source


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
