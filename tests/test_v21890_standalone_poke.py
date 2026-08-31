from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.engines.rmu_identification_engine import RmuIdentificationResult
from g_file_studio.engines.rmu_poke_engine import _ensure_jump_attributes, _Box
from g_file_studio.engines.station_poke_engine import apply_station_pokes, extract_station_key, _STATION_JUMP_POKE_REFERENCE_ATTRS
from g_file_studio.services.database_service import OracleDatabaseService


def _empty_identification(path: Path) -> RmuIdentificationResult:
    return RmuIdentificationResult(file_path=path)


def test_station_key_ignores_trailing_number_and_supports_space_format() -> None:
    assert extract_station_key('DHN-40') == 'DHN'
    assert extract_station_key('BWD2-49') == 'BWD2'
    assert extract_station_key('SALAB-12') == 'SALAB'
    assert extract_station_key('FEL 03') == 'FEL'
    assert extract_station_key('JM2-J2') == 'JM2'
    assert extract_station_key('5MR-23') == '5MR'
    assert extract_station_key('V2-W-J-H-0017') == ''
    assert extract_station_key('Y-1') == ''


def test_station_database_context_uses_name_and_subarea_only() -> None:
    service = object.__new__(OracleDatabaseService)
    captured = {}

    def fake_query(sql, params, **kwargs):
        captured['sql'] = sql
        captured['params'] = params
        return [], [(113, 'DHN', 200, 200, 'JED-CTL')]

    service.query = fake_query
    context = service.resolve_station_context('DHN')
    assert context.station_full_name == 'JED-CTL-DHN'
    assert context.station_name == 'DHN'
    assert context.subcontrolarea_name == 'JED-CTL'
    assert captured['params']['station_name'] == 'DHN'
    assert 'GRAPH_NAME' not in captured['sql'].upper()
    assert 'SUBSTATION' in captured['sql'].upper()
    assert 'SUBCONTROLAREA' in captured['sql'].upper()


def test_existing_station_poke_is_reused_deduplicated_and_copies_jm2_reference_properties(tmp_path: Path) -> None:
    file_path = tmp_path / 'sample.g'
    root = ET.Element('G')
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    ET.SubElement(layer, 'FeedLine', {'id': '35000001', 'd': '120,100 130,100', 'x': '120', 'y': '97', 'w': '16', 'h': '6'})
    ET.SubElement(layer, 'poke', {
        'id': '17000001', 'x': '130', 'y': '90', 'w': '100', 'h': '31',
        'lc': '173,173,173', 'lcc': '#adadad', 'fc': '163,163,163', 'fcc': '#a3a3a3',
        'RectStyle': '1', 'p_RectStyle': '1', 'fm': '1', 'ls': '1', 'ahref': 'OLD.sln.pic.g',
    })
    ET.SubElement(layer, 'poke', {
        'id': '17000002', 'x': '128', 'y': '88', 'w': '105', 'h': '35',
        'lc': '100,100,100', 'lcc': '#646464', 'fm': '1', 'ls': '1',
    })
    ET.SubElement(layer, 'Text', {'id': '80000001', 'x': '140', 'y': '95', 'w': '65', 'h': '21', 'ts': 'DHN-40'})
    tree = ET.ElementTree(root)

    result = apply_station_pokes(
        tree,
        file_path,
        _empty_identification(file_path),
        current_station_name='ABH',
        station_resolver=lambda key: SimpleNamespace(station_full_name='JED-CTL-DHN'),
    )
    assert result.eligible_count == 1
    assert result.removed_duplicate_count == 1
    pokes = [e for e in list(layer) if e.tag == 'poke']
    assert len(pokes) == 1
    poke = pokes[0]
    assert poke.get('ahref') == 'JED-CTL-DHN.sln.pic.g'
    for key, value in _STATION_JUMP_POKE_REFERENCE_ATTRS.items():
        assert poke.get(key) == value, key
    assert poke.get('gfs_station_name') == 'DHN'
    # Geometry remains tied to the selected label/Poke; business fields are dynamic.
    assert poke.get('id') == '17000001'
    assert poke.get('x') == '130'
    assert poke.get('y') == '90'
    assert poke.get('w') == '100'
    assert poke.get('h') == '31'


def test_no_existing_poke_can_be_created_from_line_endpoint_without_color_dependency(tmp_path: Path) -> None:
    file_path = tmp_path / 'sample.g'
    root = ET.Element('G')
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    ET.SubElement(layer, 'FeedLine', {'id': '35000001', 'd': '10,10 100,100', 'x': '10', 'y': '10', 'w': '90', 'h': '90'})
    ET.SubElement(layer, 'Text', {'id': '80000001', 'x': '105', 'y': '95', 'w': '90', 'h': '25', 'ts': 'FRSH-44'})
    tree = ET.ElementTree(root)

    result = apply_station_pokes(
        tree,
        file_path,
        _empty_identification(file_path),
        current_station_name='ABH',
        station_resolver=lambda key: SimpleNamespace(station_full_name='JED-NTH-FRSH'),
    )
    assert result.added_count == 1
    poke = next(e for e in list(layer) if e.tag == 'poke')
    assert poke.get('ahref') == 'JED-NTH-FRSH.sln.pic.g'
    for key, value in _STATION_JUMP_POKE_REFERENCE_ATTRS.items():
        assert poke.get(key) == value, key


def test_rmu_poke_line_color_is_always_blue() -> None:
    poke = ET.Element('poke', {'lc': '173,173,173', 'lcc': '#adadad'})
    changed = _ensure_jump_attributes(
        poke,
        target_file='JED-NTH-ABH-AH303-34661.sln.pic.g',
        rmu_name='34661',
        box=_Box(10, 20, 110, 50),
    )
    assert changed
    assert poke.get('lc') == '0,0,255'
    assert poke.get('lcc') == '#0000ff'
    assert poke.get('RectStyle') == '0'
    assert poke.get('p_RectStyle') == '0'


def test_rmu_page_no_longer_owns_poke_ui() -> None:
    rmu_source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    poke_source = Path('g_file_studio/ui/pages/poke_page.py').read_text(encoding='utf-8')
    assert '_build_rmu_poke_options' not in rmu_source
    assert 'add_smart_rmu_poke=False' in rmu_source
    assert 'class PokePage' in poke_source
    assert 'process_pokes' in poke_source
