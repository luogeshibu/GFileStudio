from pathlib import Path


def test_small_element_page_imports_validate_input_source():
    text = Path('g_file_studio/ui/pages/small_element_page.py').read_text(encoding='utf-8')
    assert 'from g_file_studio.ui.path_validation import validate_input_source' in text
    assert 'validate_input_source(' in text


def test_remote_client_exposes_no_server_write_operations():
    text = Path('g_file_studio/services/remote_g_source.py').read_text(encoding='utf-8')
    # The public wrapper intentionally exposes only read/list/download operations.
    forbidden_defs = ['def upload_file(', 'def put_file(', 'def remove_file(', 'def rename_file(', 'def mkdir(']
    for token in forbidden_defs:
        assert token not in text
    assert 'self._sftp.get(' in text


def test_processing_snapshot_is_forced_under_workspace():
    text = Path('g_file_studio/ui/widgets/remote_g_source.py').read_text(encoding='utf-8')
    assert 'workspace_root = default_workspace().resolve()' in text
    assert 'prepared.relative_to(workspace_root)' in text
    assert 'snapshot_dir = self._processing_snapshot_dir()' in text
    assert '后续扫描/处理仅使用 workspace 本地快照，不会修改服务器文件' in text
