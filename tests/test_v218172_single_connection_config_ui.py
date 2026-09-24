from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_connection_page_removes_multi_environment_profile_ui():
    text = (ROOT / "g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    for obsolete in ("当前环境", "新建 / 复制环境", "删除环境", "保存当前环境", "environment_selector", "environment_name"):
        assert obsolete not in text
    assert 'QGroupBox("中央配置")' in text
    assert 'QGroupBox("文件服务器（SSH/SFTP · 严格只读）")' in text
    assert 'QGroupBox("Oracle 数据库连接")' in text


def test_remote_source_uses_shared_connection_label():
    text = (ROOT / "g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    assert 'self.environment_label.setText("共享连接配置")' in text
    assert 'connection_environment/active_name' not in text


def test_release_version_metadata_is_consistent():
    import re

    init = (ROOT / "g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    project_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert init_match and project_match
    assert init_match.group(1) == project_match.group(1)

