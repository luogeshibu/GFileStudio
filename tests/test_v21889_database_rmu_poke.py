from pathlib import Path

from g_file_studio.engines.rmu_poke_engine import build_rmu_detail_filename
from g_file_studio.services.database_service import GFileDatabaseContext, OracleDatabaseService


def test_database_context_uses_business_name_chain_not_graph_name(tmp_path):
    service = object.__new__(OracleDatabaseService)
    captured = {}

    def fake_query(sql, params, **kwargs):
        captured['sql'] = sql
        captured['params'] = params
        return [], [(3799912185593857723, 'AH303', 113997365567815681,
                     113997365567815681, 'ABH', 113715890591105026,
                     113715890591105026, 'JED-NTH')]

    service.query = fake_query
    context = service.resolve_g_file_context('3799912185593857723')
    assert context.station_full_name == 'JED-NTH-ABH'
    assert context.feeder_full_name == 'JED-NTH-ABH-AH303'
    assert context.feeder_name == 'AH303'
    assert context.station_name == 'ABH'
    assert context.subcontrolarea_name == 'JED-NTH'
    assert 'GRAPH_NAME' not in captured['sql'].upper()
    assert 'DMS_FEEDER_DEVICE' in captured['sql'].upper()
    assert 'SUBSTATION' in captured['sql'].upper()
    assert 'SUBCONTROLAREA' in captured['sql'].upper()
    assert captured['params']['fac_id'] == 3799912185593857723


def test_database_context_rejects_blank_facid():
    service = object.__new__(OracleDatabaseService)
    try:
        service.resolve_g_file_context('')
    except ValueError as exc:
        assert 'facID' in str(exc)
        assert '先关联馈线' in str(exc)
    else:
        raise AssertionError('blank facID must be rejected')


def test_database_prefix_builds_expected_rmu_target():
    target = build_rmu_detail_filename(
        Path('JED-NTH-ABH-03.sln.pic.g'),
        'JED-NTH-ABH-AH303',
        '34661',
        naming_mode='database_prefix',
        naming_rule='JED-NTH-ABH-AH303',
    )
    assert target == 'JED-NTH-ABH-AH303-34661.sln.pic.g'


def test_rmu_page_no_longer_requires_manual_poke_template():
    source = Path('g_file_studio/ui/pages/rmu_page.py').read_text(encoding='utf-8')
    poke_source = Path('g_file_studio/ui/pages/poke_page.py').read_text(encoding='utf-8')
    assert 'ahref 文件名模板' not in source
    assert 'OracleDatabaseService(self.user_settings)' not in source
    assert '_build_rmu_poke_options' not in source
    assert 'Poke 跳转处理' in source
    assert 'OracleDatabaseService(user_settings)' in poke_source
    assert 'facID 不再作为执行前提' in poke_source


def test_process_blank_facid_skips_poke_without_calling_database(tmp_path):
    import xml.etree.ElementTree as ET
    from g_file_studio.models import BasicSettings, InputMode
    from g_file_studio.processors.basic_processor import process_basic

    source = tmp_path / 'blank-facid.g'
    root = ET.Element('G', {'facID': ''})
    layer = ET.SubElement(root, 'Layer', {'name': '0'})
    ET.SubElement(layer, 'rect', {'id': '2001', 'x': '100', 'y': '100', 'w': '220', 'h': '220'})
    ET.SubElement(layer, 'BusDis', {'id': '3801', 'x': '140', 'y': '170', 'w': '140', 'h': '8'})
    ET.SubElement(layer, 'CBreakerDis', {'id': '1171', 'x': '175', 'y': '190', 'w': '28', 'h': '28', 'p_NameString': 'Y1'})
    ET.SubElement(layer, 'ZhaiWaiJieDiDaoZha', {'id': '1881', 'x': '180', 'y': '250', 'w': '30', 'h': '28'})
    ET.SubElement(layer, 'Text', {'id': '8001', 'x': '130', 'y': '110', 'w': '60', 'h': '20', 'ts': 'SMART'})
    ET.SubElement(layer, 'Text', {'id': '8002', 'x': '145', 'y': '40', 'w': '125', 'h': '50', 'ts': '34661'})
    ET.ElementTree(root).write(source, encoding='utf-8', xml_declaration=True)

    class MustNotCallDb:
        def resolve_g_file_context(self, fac_id):
            raise AssertionError('database must not be queried when facID is blank')

    logs = []
    settings = BasicSettings(
        source_path=source,
        input_mode=InputMode.SINGLE_FILE,
        output_dir=tmp_path / 'out',
        add_smart_rmu_poke=True,
        identify_rmu_name_and_type=True,
        rmu_smart_in_type=True,
        rmu_name_top=True,
        export_rmu_identification_csv=False,
    )
    result = process_basic(settings, logs.append, database_service=MustNotCallDb())
    assert result.success
    assert any('facID 为空' in line and '先关联馈线' in line for line in logs)
    output = tmp_path / 'out' / source.name
    assert output.is_file()
    assert not any(e.tag == 'poke' and e.get('gfs_rmu_poke') == '1' for e in ET.parse(output).getroot().iter())
