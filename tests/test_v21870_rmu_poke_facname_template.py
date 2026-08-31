from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes, render_facname_rmu_rule


def _tree(*, fac_name: str = 'AH303', name: str = '34661') -> ET.ElementTree:
    attrs = {'facName': fac_name} if fac_name else {}
    root = ET.Element('G', attrs)
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    ET.SubElement(layer, 'rect', {'id': '2001', 'x': '100', 'y': '200', 'w': '220', 'h': '220'})
    ET.SubElement(layer, 'Text', {'id': '8001', 'ts': name, 'x': '140', 'y': '150', 'w': '125', 'h': '50'})
    return ET.ElementTree(root)


def _ident(file_name: str, name: str = '34661') -> RmuIdentificationResult:
    return RmuIdentificationResult(
        file_path=Path(file_name),
        cabinet_count=1,
        items=[RmuIdentification(
            rect_id='2001', name=name, name_position='top', rmu_type='2L1T',
            l_count=2, t_count=1, smart_count=1, confidence='high',
            rect_x=100, rect_y=200, rect_w=220, rect_h=220,
        )],
    )


def test_facname_and_rmu_can_appear_anywhere_in_user_template():
    assert render_facname_rmu_rule(
        'JED-NTH-ABH-{FACNAME}-{RMU}-JED.sln.pic.g', 'AH303', '34661'
    ) == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'
    assert render_facname_rmu_rule(
        'DETAIL-{RMU}-SITE-{FACNAME}.sln.pic.g', 'AH303', '22522'
    ) == 'DETAIL-22522-SITE-AH303.sln.pic.g'
    assert render_facname_rmu_rule(
        'JED-NTH-ABH-FACNAME-RMU-JED.sln.pic.g', 'AH303', '34661'
    ) == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'


def test_single_file_can_hardcode_facname_and_only_mark_rmu_position():
    assert render_facname_rmu_rule(
        'JED-NTH-ABH-AH303-{RMU}-JED.sln.pic.g', '', '34661'
    ) == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'


def test_new_mode_never_reads_or_validates_source_filename():
    source = Path('THIS FILE NAME DOES NOT FOLLOW ANY SITE RULE.g')
    tree = _tree(fac_name='AH303')
    result = apply_smart_rmu_pokes(
        tree, source, _ident(source.name),
        naming_mode='facname_template',
        naming_rule='JED-NTH-ABH-{FACNAME}-{RMU}-JED.sln.pic.g',
    )
    assert result.added_count == 1
    assert result.skipped_count == 0
    poke = next(e for e in tree.getroot().iter() if e.tag == 'poke')
    assert poke.get('ahref') == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'


def test_batch_files_use_each_g_root_facname_not_filename_feeder():
    template = 'SITE-{FACNAME}-{RMU}-DETAIL.sln.pic.g'
    outputs = []
    for source_name, fac_name in [
        ('random-alpha.g', 'AH303'),
        ('another-random-name.g', 'AH304'),
        ('not-a-standard-filename.g', 'MD112'),
    ]:
        tree = _tree(fac_name=fac_name)
        result = apply_smart_rmu_pokes(
            tree, Path(source_name), _ident(source_name),
            naming_mode='facname_template', naming_rule=template,
        )
        assert result.added_count == 1
        assert result.skipped_count == 0
        outputs.append(next(e for e in tree.getroot().iter() if e.tag == 'poke').get('ahref'))
    assert outputs == [
        'SITE-AH303-34661-DETAIL.sln.pic.g',
        'SITE-AH304-34661-DETAIL.sln.pic.g',
        'SITE-MD112-34661-DETAIL.sln.pic.g',
    ]


def test_missing_facname_only_skips_poke_when_template_requests_facname():
    source = Path('anything.g')
    tree = _tree(fac_name='')
    result = apply_smart_rmu_pokes(
        tree, source, _ident(source.name),
        naming_mode='facname_template',
        naming_rule='SITE-{FACNAME}-{RMU}.sln.pic.g',
    )
    assert result.intelligent_rmu_count == 1
    assert result.skipped_count == 1
    assert result.added_count == 0
    assert any('facName' in warning for warning in result.warnings)


def test_rmu_placeholder_is_mandatory_and_unknown_fields_are_rejected():
    for rule in ('SITE-{FACNAME}.sln.pic.g', 'SITE-{FEEDER}-{RMU}.sln.pic.g'):
        try:
            render_facname_rmu_rule(rule, 'AH303', '34661')
        except ValueError:
            pass
        else:
            raise AssertionError(f'expected ValueError for {rule}')
