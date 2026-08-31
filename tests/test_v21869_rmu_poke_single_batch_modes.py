from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import (
    apply_smart_rmu_pokes,
    build_rmu_detail_filename,
    extract_batch_feeder,
    render_batch_rmu_rule,
    render_single_rmu_rule,
)


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


def test_single_rule_never_depends_on_source_filename():
    bad_source = Path('anything-at-all.g')
    assert render_single_rmu_rule(
        'JED-NTH-ABH-AH303-RMU.sln.pic.g', '22522'
    ) == 'JED-NTH-ABH-AH303-22522.sln.pic.g'
    assert build_rmu_detail_filename(
        bad_source, '22522', naming_mode='single',
        naming_rule='JED-NTH-ABH-AH303-RMU.sln.pic.g',
    ) == 'JED-NTH-ABH-AH303-22522.sln.pic.g'


def test_single_rule_accepts_prefix_placeholder_and_real_sample():
    assert render_single_rmu_rule('JED-NTH-ABH-AH303', '16781') == 'JED-NTH-ABH-AH303-16781.sln.pic.g'
    assert render_single_rmu_rule('JED-NTH-ABH-AH303-{RMU}.sln.pic.g', '16782') == 'JED-NTH-ABH-AH303-16782.sln.pic.g'
    assert render_single_rmu_rule('JED-NTH-ABH-AH303-34661.sln.pic.g', '22522') == 'JED-NTH-ABH-AH303-22522.sln.pic.g'


def test_batch_fixed_prefix_extracts_each_file_feeder_independently():
    assert extract_batch_feeder(Path('JED-NTH-ABH-03.sln.pic.g')) == '03'
    assert extract_batch_feeder(Path('JED-NTH-ABH-04.sln.pic.g')) == '04'
    assert render_batch_rmu_rule(
        Path('JED-NTH-ABH-03.sln.pic.g'), 'JED-NTH-ABH-AH3', '22522'
    ) == 'JED-NTH-ABH-AH303-22522.sln.pic.g'
    assert render_batch_rmu_rule(
        Path('JED-NTH-ABH-04.sln.pic.g'), 'JED-NTH-ABH-AH3', '22522'
    ) == 'JED-NTH-ABH-AH304-22522.sln.pic.g'


def test_batch_template_supports_feeder_and_rmu_tokens():
    rule = 'OTHER-SITE-X{FEEDER}-{RMU}.sln.pic.g'
    assert render_batch_rmu_rule(
        Path('OTHER-AREA-SITE-12.sln.pic.g'), rule, '30834'
    ) == 'OTHER-SITE-X12-30834.sln.pic.g'


def test_batch_bad_filename_skips_only_this_files_pokes():
    source = Path('JED-NTH-ABH-F03.sln.pic.g')
    tree = _tree()
    result = apply_smart_rmu_pokes(
        tree, source, _ident(source.name),
        naming_mode='batch', naming_rule='JED-NTH-ABH-AH3',
    )
    assert result.intelligent_rmu_count == 1
    assert result.skipped_count == 1
    assert result.added_count == 0
    assert any('FEEDER' in warning and '批处理' in warning for warning in result.warnings)
    assert not any(element.tag == 'poke' for element in tree.getroot().iter())


def test_single_bad_source_still_creates_poke_when_rule_is_valid():
    source = Path('NOT_A_STANDARD_MAIN_FILE.g')
    tree = _tree()
    result = apply_smart_rmu_pokes(
        tree, source, _ident(source.name),
        naming_mode='single', naming_rule='JED-NTH-ABH-AH303-RMU.sln.pic.g',
    )
    assert result.added_count == 1
    assert result.skipped_count == 0
    poke = next(element for element in tree.getroot().iter() if element.tag == 'poke')
    assert poke.get('ahref') == 'JED-NTH-ABH-AH303-22522.sln.pic.g'
