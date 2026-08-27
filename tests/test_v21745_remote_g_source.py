from pathlib import Path

from g_file_studio.models import InputMode
from g_file_studio.services import remote_g_source


def test_remote_defaults_match_sec_server():
    assert remote_g_source.DEFAULT_SSH_HOST == "172.16.21.27"
    assert remote_g_source.DEFAULT_SSH_PORT == 22
    assert remote_g_source.DEFAULT_SSH_USERNAME == "up8000"
    assert remote_g_source.DEFAULT_SSH_PASSWORD == "up8000"
    assert remote_g_source.DEFAULT_SSH_REMOTE_DIRECTORY == "/home/up8000/data/graph/display/sln"


def test_ssh_client_is_read_only_surface():
    names = set(dir(remote_g_source.ReadOnlySshClient))
    for forbidden in ("put", "upload", "remove", "rename", "mkdir", "rmdir"):
        assert forbidden not in names
    for allowed in ("test_connection", "list_g_files", "stat_file", "download_file"):
        assert allowed in names


def test_remote_input_mode_and_shared_selector():
    assert InputMode.REMOTE_SSH.value == "remote_ssh"
    source = Path("g_file_studio/ui/widgets/input_source_selector.py").read_text(encoding="utf-8")
    assert 'SSH 远程 G 文件（只读）' in source
    assert 'RemoteGSourceWidget' in source
    assert 'prepare_for_processing' in source


def test_all_standard_g_input_pages_use_shared_selector():
    pages = [
        "basic_page.py",
        "id_page.py",
        "rmu_page.py",
        "small_element_page.py",
        "margin_page.py",
        "frame_page.py",
    ]
    for page in pages:
        text = Path("g_file_studio/ui/pages") / page
        assert "InputSourceSelector" in text.read_text(encoding="utf-8"), page


def test_merge_page_has_remote_source_and_readonly_workflow():
    text = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    assert 'SSH 远程 G 文件（只读）' in text
    assert 'RemoteGSourceWidget' in text
    assert '_prepare_remote_for_file_order' in text


def test_build_and_requirements_include_paramiko():
    assert 'paramiko' in Path('requirements.txt').read_text(encoding='utf-8').lower()
    build = Path('build_exe.ps1').read_text(encoding='utf-8')
    assert '--collect-all "paramiko"' in build
    assert '--collect-all "cryptography"' in build


def test_version_21745():
    assert '__version__ = "2.18.47"' in Path('g_file_studio/__init__.py').read_text(encoding='utf-8')
    assert 'version = "2.18.47"' in Path('pyproject.toml').read_text(encoding='utf-8')

def test_manual_download_does_not_clear_destination_and_settings_are_global():
    ui = Path('g_file_studio/ui/widgets/remote_g_source.py').read_text(encoding='utf-8')
    assert 'return f"remote_g_source/{suffix}"' in ui
    assert 'clear_target=False' in ui
    service = Path('g_file_studio/services/remote_g_source.py').read_text(encoding='utf-8')
    assert 'clear_target: bool = True' in service
