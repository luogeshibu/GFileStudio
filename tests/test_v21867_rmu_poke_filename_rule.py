from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import (
    apply_smart_rmu_pokes,
    build_rmu_detail_filename,
    build_rmu_detail_prefix,
)


def test_auto_prefix_uses_filename_only_ah3_plus_feeder():
    assert build_rmu_detail_prefix(Path('JED-NTH-ABH-03.sln.pic.g')) == 'JED-NTH-ABH-AH303'
    assert build_rmu_detail_prefix(Path('JED-NTH-ABH-12.sln.pic(9).g')) == 'JED-NTH-ABH-AH312'
    # Legacy facName positional argument is deliberately ignored.
    assert build_rmu_detail_filename(
        Path('JED-NTH-ABH-03.sln.pic.g'), 'WRONG-FAC', '34661'
    ) == 'JED-NTH-ABH-AH303-34661.sln.pic.g'


def test_invalid_main_filename_fails_without_manual_override():
    with pytest.raises(ValueError, match='文件名.*不符合|不符合 Poke 自动命名要求'):
        build_rmu_detail_prefix(Path('JED-NTH-ABH.sln.pic.g'))
    with pytest.raises(ValueError, match='文件名.*不符合|不符合 Poke 自动命名要求'):
        build_rmu_detail_prefix(Path('JED-NTH-ABH-F03.sln.pic.g'))


def test_manual_override_accepts_prefix_or_sample_detail_filename():
    bad_source = Path('NOT-A-STANDARD-MAIN.g')
    assert build_rmu_detail_prefix(bad_source, 'JED-NTH-ABH-AH303') == 'JED-NTH-ABH-AH303'
    assert build_rmu_detail_prefix(
        bad_source, r'D:\examples\JED-NTH-ABH-AH303-22522.sln.pic.g'
    ) == 'JED-NTH-ABH-AH303'
    assert build_rmu_detail_filename(
        bad_source, '40597', target_override='JED-NTH-ABH-AH303-22522.sln.pic.g'
    ) == 'JED-NTH-ABH-AH303-40597.sln.pic.g'


def _multi_smart_tree():
    root = ET.Element('G', {'facName': 'SHOULD-NOT-BE-USED'})
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    for idx, (name, x) in enumerate((('22522', 100), ('34661', 500)), start=1):
        ET.SubElement(layer, 'rect', {'id': f'200{idx}', 'x': str(x), 'y': '200', 'w': '220', 'h': '220'})
        ET.SubElement(layer, 'Text', {'id': f'800{idx}', 'ts': name, 'x': str(x+40), 'y': '150', 'w': '125', 'h': '50'})
    return ET.ElementTree(root)


def test_one_sample_override_generates_distinct_targets_for_multiple_smart_rmus():
    tree = _multi_smart_tree()
    ident = RmuIdentificationResult(
        file_path=Path('odd-name.g'), cabinet_count=2,
        items=[
            RmuIdentification(rect_id='2001', name='22522', name_position='top', rmu_type='3L1T', l_count=3, t_count=1, smart_count=1, confidence='high', rect_x=100, rect_y=200, rect_w=220, rect_h=220),
            RmuIdentification(rect_id='2002', name='34661', name_position='top', rmu_type='2L1T', l_count=2, t_count=1, smart_count=1, confidence='high', rect_x=500, rect_y=200, rect_w=220, rect_h=220),
        ],
    )
    result = apply_smart_rmu_pokes(
        tree, Path('odd-name.g'), ident,
        target_override='JED-NTH-ABH-AH303-22522.sln.pic.g',
    )
    assert result.added_count == 2
    targets = sorted((e.get('ahref') or '') for e in tree.getroot().iter() if e.tag == 'poke')
    assert targets == [
        'JED-NTH-ABH-AH303-22522.sln.pic.g',
        'JED-NTH-ABH-AH303-34661.sln.pic.g',
    ]
