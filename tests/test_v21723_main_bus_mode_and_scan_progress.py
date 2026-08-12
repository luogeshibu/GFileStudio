from pathlib import Path

import pytest

from g_file_studio.engines.merge_engine import inspect_main_bus_metadata, validate_main_bus_keyid_sequence


def _write(path: Path, buses: list[dict[str, object]]) -> None:
    body = []
    for b in buses:
        key = "" if b.get("keyid") is None else f' keyid="{b["keyid"]}"'
        x1 = int(b.get("x1", 100))
        x2 = int(b.get("x2", 227))
        y = int(b["y"])
        w = int(b.get("w", abs(x2-x1)+6))
        body.append(
            f'<Bus id="{b["id"]}"{key} x="{x1}" y="{y}" w="{w}" h="6" '
            f'x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" d="{x1},{y} {x2},{y}"/>'
        )
    path.write_text('<G><Layer>' + ''.join(body) + '</Layer></G>', encoding='utf-8')


def test_single_bus_checks_only_highest_and_ignores_other_bus_without_keyid(tmp_path: Path) -> None:
    p = tmp_path / 'single.g'
    _write(p, [
        {"id": "30000001", "keyid": "TOP", "y": 30},
        {"id": "30000002", "keyid": None, "y": 100},
    ])
    item = inspect_main_bus_metadata(p, 'single')
    assert item['reason'] == ''
    assert item['keyids'] == ['TOP']


def test_bus_with_xml_w_less_than_10_is_not_filtered_by_main_bus_feature(tmp_path: Path) -> None:
    p = tmp_path / 'helper.g'
    _write(p, [
        {"id": "39999999", "keyid": None, "y": 10, "w": 6, "x1": 100, "x2": 106},
        {"id": "30000001", "keyid": "REAL", "y": 30, "w": 133},
    ])
    item = inspect_main_bus_metadata(p, 'single')
    assert 'keyid' in item['reason']


def test_double_bus_requires_two_parallel_similar_length_buses_and_both_keyids(tmp_path: Path) -> None:
    p = tmp_path / 'double.g'
    _write(p, [
        {"id": "30000001", "keyid": "A", "y": 30, "w": 133},
        {"id": "30000002", "keyid": None, "y": 51, "w": 133},
        {"id": "30000003", "keyid": "OTHER", "y": 90, "w": 40},
    ])
    item = inspect_main_bus_metadata(p, 'double')
    assert 'keyid' in item['reason']


def test_double_bus_keeps_two_keyids_independent(tmp_path: Path) -> None:
    p = tmp_path / 'double.g'
    _write(p, [
        {"id": "30000001", "keyid": "A", "y": 30, "w": 133},
        {"id": "30000002", "keyid": "B", "y": 51, "w": 133},
    ])
    item = inspect_main_bus_metadata(p, 'double')
    assert item['reason'] == ''
    assert item['keyids'] == ['A', 'B']


def test_interrupted_selected_keyid_still_blocks(tmp_path: Path) -> None:
    paths = []
    for i, key in enumerate(['A', 'B', 'A']):
        p = tmp_path / f'f{i}.g'
        _write(p, [{"id": f'3000000{i+1}', "keyid": key, "y": 30, "w": 133}])
        paths.append(p)
    with pytest.raises(ValueError, match='被阻断'):
        validate_main_bus_keyid_sequence(paths, 'single')


def test_real_uploaded_examples_match_expected_modes() -> None:
    root = Path('/mnt/data')
    abs_file = root / 'JED-NTH-ABS-01.sln.pic.g'
    bwd_file = root / 'JED-CTL-BWD-32.sln.pic(1).g'
    if abs_file.exists():
        item = inspect_main_bus_metadata(abs_file, 'double')
        assert item['reason'] == ''
        assert len(item['keyids']) == 2
    if bwd_file.exists():
        item = inspect_main_bus_metadata(bwd_file, 'single')
        assert 'keyid' in item['reason']


def test_id_scan_page_contains_visible_progress_dialog() -> None:
    source = (Path(__file__).parents[1] / 'g_file_studio' / 'ui' / 'pages' / 'id_page.py').read_text(encoding='utf-8')
    assert 'QProgressDialog' in source
    assert '正在扫描当前 G 文件并检查 ID 规则' in source
    assert 'progress_dialog.setValue(index)' in source
