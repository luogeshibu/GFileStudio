from __future__ import annotations

from pathlib import Path

from g_file_studio.services.classification_registry_service import (
    CLASSIFICATION_FILE_NAME,
    DEFAULT_CLASSIFICATION_PATH,
)


def test_v218168_server_file_name_is_explicit_and_unique() -> None:
    assert CLASSIFICATION_FILE_NAME == "symbol_classification.json"
    assert DEFAULT_CLASSIFICATION_PATH == (
        "/home/up8000/nari-international/gfilestudio/"
        "config/symbol_classification.json"
    )
    assert "admin.json" not in DEFAULT_CLASSIFICATION_PATH
    assert "v000" not in DEFAULT_CLASSIFICATION_PATH.lower()
    assert "history" not in DEFAULT_CLASSIFICATION_PATH.lower()


def test_v218168_ui_has_explicit_local_and_server_actions() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("保存到本地")' in source
    assert 'QPushButton("上传到服务器")' in source
    assert 'QPushButton("从服务器同步")' in source
    assert 'QPushButton("导出 JSON")' in source
    assert 'QPushButton("导入 JSON")' in source
    assert 'if not self._require_admin_mode("保存到本地")' not in source
    assert 'if not self._require_admin_mode("上传到服务器")' in source
    assert 'if not self._require_admin_mode("导入本地 JSON")' not in source


def test_v218168_upload_saves_local_first_and_sync_warns_about_overwrite() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    publish_start = source.index("def _publish_central_classification")
    publish_end = source.index("def _sync_central_classification", publish_start)
    publish_body = source[publish_start:publish_end]
    assert "_persist_visible_classification_markers()" in publish_body
    assert publish_body.index("_persist_visible_classification_markers()") < publish_body.index(
        "ClassificationRegistryService().publish"
    )
    sync_start = source.index("def _sync_central_classification")
    sync_end = source.index("def _on_central_publish_result", sync_start)
    sync_body = source[sync_start:sync_end]
    assert "用服务器分类覆盖本机分类标记" in sync_body
    assert "replace_classification_marker_payload" in sync_body


def test_v218168_version_metadata_stays_consistent() -> None:
    import re

    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert init_match and project_match
    assert init_match.group(1) == project_match.group(1)
