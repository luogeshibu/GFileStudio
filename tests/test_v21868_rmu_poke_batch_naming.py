from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes, build_rmu_detail_filename


def _tree(name: str = '22522') -> ET.ElementTree:
    root = ET.Element('G')
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    ET.SubElement(layer, 'rect', {'id': '2001', 'x': '100', 'y': '200', 'w': '220', 'h': '220'})
    ET.SubElement(layer, 'Text', {'id': '8001', 'ts': name, 'x': '140', 'y': '150', 'w': '125', 'h': '50'})
    return ET.ElementTree(root)


def _ident(file_name: str, name: str = '22522') -> RmuIdentificationResult:
    return RmuIdentificationResult(
        file_path=Path(file_name),
        cabinet_count=1,
        items=[RmuIdentification(
            rect_id='2001', name=name, name_position='top', rmu_type='2L1T',
            l_count=2, t_count=1, smart_count=1, confidence='high',
            rect_x=100, rect_y=200, rect_w=220, rect_h=220,
        )],
    )


def test_batch_auto_naming_is_independent_per_source_file():
    cases = {
        'JED-NTH-ABH-03.sln.pic.g': 'JED-NTH-ABH-AH303-22522.sln.pic.g',
        'JED-NTH-ABH-07.sln.pic.g': 'JED-NTH-ABH-AH307-22522.sln.pic.g',
        'JED-NTH-ABH-12.sln.pic.g': 'JED-NTH-ABH-AH312-22522.sln.pic.g',
    }
    for source_name, expected in cases.items():
        tree = _tree()
        result = apply_smart_rmu_pokes(tree, Path(source_name), _ident(source_name))
        assert result.added_count == 1
        poke = next(e for e in tree.getroot().iter() if e.tag == 'poke')
        assert poke.get('ahref') == expected


def test_bad_filename_skips_only_poke_instead_of_raising_or_partially_editing():
    source = Path('JED-NTH-ABH-F03.sln.pic.g')
    tree = _tree()
    result = apply_smart_rmu_pokes(tree, source, _ident(source.name))
    assert result.intelligent_rmu_count == 1
    assert result.added_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 1
    assert any('命名预检查失败' in w and '文件名' in w for w in result.warnings)
    assert not any(e.tag == 'poke' for e in tree.getroot().iter())


def test_custom_template_is_batch_safe_and_requires_rmu_placeholder():
    template = '{region1}-{region2}-{station}-AH3{feeder}-{rmu}.sln.pic.g'
    assert build_rmu_detail_filename(
        Path('JED-NTH-ABH-03.sln.pic.g'), '22522', target_override=template
    ) == 'JED-NTH-ABH-AH303-22522.sln.pic.g'
    assert build_rmu_detail_filename(
        Path('JED-NTH-ABH-12.sln.pic.g'), '40597', target_override=template
    ) == 'JED-NTH-ABH-AH312-40597.sln.pic.g'

    tree = _tree()
    bad_template = 'JED-NTH-ABH-AH303.sln.pic.g'
    # Legacy fixed values remain API-compatible; the RMU page no longer exposes them as custom templates.
    # New custom-template mode itself is guarded in the UI to require {rmu}.
    result = apply_smart_rmu_pokes(tree, Path('JED-NTH-ABH-03.sln.pic.g'), _ident('JED-NTH-ABH-03.sln.pic.g'), target_override=bad_template)
    assert result.skipped_count == 1
    assert result.added_count == 0


def test_static_custom_template_can_support_nonstandard_main_name_when_only_rmu_is_dynamic():
    template = 'JED-NTH-ABH-AH399-{rmu}.sln.pic.g'
    assert build_rmu_detail_filename(
        Path('SPECIAL_MAIN_FILE.g'), '34661', target_override=template
    ) == 'JED-NTH-ABH-AH399-34661.sln.pic.g'
