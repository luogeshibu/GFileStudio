from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import RmuIdentification, RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import apply_smart_rmu_pokes


def _build_tree() -> ET.ElementTree:
    xml = '''<root facName="AH303">
      <Layer id="L1">
        <poke id="17000050" x="10" y="10" w="80" h="30" ahref="OTHER_FILE.sln.pic.g" fm="1" ls="1"/>
        <rect id="2001" x="100" y="200" w="220" h="220"/>
        <Text id="3001" ts="34661" x="130" y="150" w="125" h="50"/>
        <poke id="17000051" x="129" y="149" w="126" h="51" ahref="JED-NTH-ABH-AH303-34661.sln.pic.g" fm="1" ls="1"/>
        <poke id="17000052" x="128" y="148" w="130" h="54" ahref="WRONG.sln.pic.g"/>
      </Layer>
    </root>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_rmu_poke_uses_name_box_and_deduplicates_related_pokes_only():
    tree = _build_tree()
    ident = RmuIdentificationResult(
        file_path=Path('JED-NTH-ABH-03.sln.pic.g'),
        cabinet_count=1,
        items=[
            RmuIdentification(
                rect_id='2001', name='34661', name_position='top', rmu_type='3L1T',
                l_count=2, t_count=1, smart_count=1, confidence='high',
                rect_x=100.0, rect_y=200.0, rect_w=220.0, rect_h=220.0,
            )
        ],
    )

    result = apply_smart_rmu_pokes(tree, Path('JED-NTH-ABH-03.sln.pic.g'), ident)
    assert result.intelligent_rmu_count == 1
    assert result.eligible_rmu_count == 1
    assert result.updated_count == 1
    assert result.added_count == 0
    assert result.skipped_count == 0

    root = tree.getroot()
    pokes = [e for e in root.iter() if e.tag == 'poke']
    # 1 unrelated + 1 retained related poke
    assert len(pokes) == 2

    related = [e for e in pokes if (e.get('gfs_rmu_name') or '') == '34661']
    assert len(related) == 1
    poke = related[0]
    assert poke.get('id') == '17000051'
    assert poke.get('ahref') == 'JED-NTH-ABH-AH303-34661.sln.pic.g'
    assert poke.get('x') == '130'
    assert poke.get('y') == '150'
    assert poke.get('w') == '125'
    assert poke.get('h') == '50'

    unrelated = [e for e in pokes if e.get('id') == '17000050']
    assert len(unrelated) == 1
