from pathlib import Path
import pytest

from g_file_studio.engines.merge_engine import validate_main_bus_keyid_sequence


def _write(path: Path, keyid: str, bus_id: str) -> None:
    path.write_text(
        f'<G><Layer><Bus id="{bus_id}" keyid="{keyid}" x="100" y="30" w="133" h="6" '
        f'x1="100" y1="30" x2="227" y2="30" d="100,30 227,30"/></Layer></G>',
        encoding='utf-8',
    )


def test_interrupted_keyid_error_identifies_files_and_bus_ids(tmp_path: Path) -> None:
    a = tmp_path / 'JED-NTH-ABN-01.sln.pic.g'
    b = tmp_path / 'JED-NTH-ABN-02.sln.pic.g'
    c = tmp_path / 'JED-NTH-ABN-03.sln.pic.g'
    _write(a, 'K-A', '30000001')
    _write(b, 'K-B', '30000002')
    _write(c, 'K-A', '30000003')

    with pytest.raises(ValueError) as exc_info:
        validate_main_bus_keyid_sequence([a, b, c], 'single')

    message = str(exc_info.value)
    assert 'keyid=K-A' in message
    assert 'JED-NTH-ABN-01.sln.pic.g' in message
    assert 'JED-NTH-ABN-02.sln.pic.g' in message
    assert 'JED-NTH-ABN-03.sln.pic.g' in message
    assert 'Bus XML ID=30000001' in message
    assert 'Bus XML ID=30000003' in message
    assert '中间阻断文件' in message
