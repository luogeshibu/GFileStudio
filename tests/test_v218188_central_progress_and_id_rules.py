from __future__ import annotations

from pathlib import Path

from g_file_studio.services.classification_registry_service import (
    ClassificationRegistryService,
    DEFAULT_ID_RULES_PATH,
)
from g_file_studio.services.id_rule_service import IdRuleService


def test_central_files_map_includes_id_rules() -> None:
    files = ClassificationRegistryService._files_map()
    assert files["id_rules"] == "id_rules.json"
    assert DEFAULT_ID_RULES_PATH.endswith("/gfilestudio/config/id_rules.json")


def test_id_rule_service_can_roundtrip_central_payload(tmp_path: Path) -> None:
    local = IdRuleService(tmp_path / "Config" / "id_rules.json")
    payload = local.export_payload()
    assert payload["rules"]

    replacement = IdRuleService(tmp_path / "Other" / "id_rules.json")
    result = replacement.replace_from_payload(payload)
    assert result["rules"] == len(payload["rules"])
    assert replacement.json_path.is_file()


def test_database_central_sync_has_progress_dialog() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert "QProgressDialog" in source
    assert "def _open_central_progress" in source
    assert "worker.signals.progress.connect(progress_dialog.setValue)" in source
    assert "正在覆盖本机连接配置缓存" in source


def test_classification_central_sync_has_progress_dialog_and_background_worker() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert "QProgressDialog" in source
    assert "worker.signals.progress.connect(progress_dialog.setValue)" in source
    assert "QTimer.singleShot(0, lambda w=worker: self._scan_pool.start(w))" in source
    assert "正在更新本地图元分类缓存" in source


def test_id_page_has_manual_central_sync_and_publish_controls() -> None:
    source = Path("g_file_studio/ui/pages/id_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("从中央同步规则")' in source
    assert 'QPushButton("发布规则到中央")' in source
    assert "ClassificationRegistryService().fetch_id_rules" in source
    assert "publish_id_rules(" in source
    assert "QProgressDialog" in source


def test_startup_still_never_reads_central_id_rules() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "fetch_id_rules(" not in source
    assert "publish_id_rules(" not in source


def test_application_version_is_consistent() -> None:
    import re
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert init_match is not None and project_match is not None
    assert init_match.group(1) == project_match.group(1)
