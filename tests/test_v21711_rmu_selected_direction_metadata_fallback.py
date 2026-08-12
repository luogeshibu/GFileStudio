from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def test_top_only_never_uses_metadata_or_other_direction_as_fallback():
    source = Path('/mnt/data/JED-NTH-ABH.sln.pic.g')
    if not source.exists():
        return
    result = identify_rmus(ET.parse(source), source, name_positions=('top',), smart_in_type=True)
    assert result.cabinet_count == 340
    assert result.named_count == 337
    by_id = {item.rect_id: item for item in result.items}
    for rect_id in ('2000333', '2000362', '2000429'):
        assert by_id[rect_id].name == ''
        assert by_id[rect_id].name_position == ''
        assert not any('BusDis.key_name' in warning for warning in by_id[rect_id].warnings)
