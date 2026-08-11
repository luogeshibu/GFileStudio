from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def test_top_only_metadata_fallback_does_not_search_other_text_directions():
    source = Path('/mnt/data/JED-NTH-ABH.sln.pic.g')
    if not source.exists():
        return
    result = identify_rmus(ET.parse(source), source, name_positions=('top',), smart_in_type=True)
    assert result.cabinet_count == 340
    assert result.named_count == 340
    by_id = {item.rect_id: item for item in result.items}
    assert by_id['2000333'].name == '30864'
    assert by_id['2000362'].name == '30833'
    assert by_id['2000429'].name == '30859'
    assert by_id['2000333'].name_position == 'top'
    assert any('BusDis.key_name' in warning for warning in by_id['2000333'].warnings)
