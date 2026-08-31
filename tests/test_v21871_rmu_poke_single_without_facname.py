from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_poke_engine import (
    apply_smart_rmu_pokes,
    render_facname_rmu_rule,
    template_uses_facname,
)
from g_file_studio.engines.rmu_identification_engine import (
    RmuIdentification,
    RmuIdentificationResult,
)


def test_template_uses_facname_detection():
    assert template_uses_facname('A-{FACNAME}-{RMU}.sln.pic.g') is True
    assert template_uses_facname('A-AH303-{RMU}.sln.pic.g') is False


def test_single_fixed_rule_without_facname_value_still_renders():
    assert (
        render_facname_rmu_rule(
            'JED-NTH-ABH-AH303-{RMU}-JED.sln.pic.g', '', '34661'
        )
        == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'
    )


def test_single_fixed_rule_with_facname_placeholder_and_empty_facname_fails():
    try:
        render_facname_rmu_rule(
            'JED-NTH-ABH-{FACNAME}-{RMU}-JED.sln.pic.g', '', '34661'
        )
    except ValueError as exc:
        assert 'facName 为空' in str(exc)
    else:
        raise AssertionError('expected ValueError')


def test_apply_smart_rmu_pokes_succeeds_without_facname_when_template_does_not_use_it():
    xml = (
        '<root><Layer id="L1">'
        '<rect id="2001" x="100" y="200" w="220" h="220"/>'
        '<Text id="3001" ts="34661" x="130" y="150" w="125" h="50"/>'
        '</Layer></root>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    ident = RmuIdentificationResult(
        file_path=Path('main.g'),
        cabinet_count=1,
        items=[
            RmuIdentification(
                rect_id='2001',
                name='34661',
                name_position='top',
                rmu_type='3L1T',
                l_count=2,
                t_count=1,
                smart_count=1,
                confidence='high',
                rect_x=100.0,
                rect_y=200.0,
                rect_w=220.0,
                rect_h=220.0,
            )
        ],
    )
    res = apply_smart_rmu_pokes(
        tree,
        Path('main.g'),
        ident,
        naming_mode='facname_template',
        naming_rule='JED-NTH-ABH-AH303-{RMU}-JED.sln.pic.g',
    )
    assert res.added_count == 1
    poke = [e for e in tree.getroot().iter() if e.tag == 'poke'][0]
    assert poke.get('ahref') == 'JED-NTH-ABH-AH303-34661-JED.sln.pic.g'
