from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.standard_connection_cleanup import (
    inspect_standard_device_connections,
    normalize_standard_device_connections,
)


def _tree(xml: str) -> ET.ElementTree:
    return ET.ElementTree(ET.fromstring(xml))


def _geometry(devref: str):
    return {
        devref: [
            {
                "rotation": 0,
                "width": 30,
                "height": 30,
                "anchor_offsets": [[6, 15], [24, 15]],
            }
        ]
    }


def test_authoritative_two_pin_geometry_removes_bypass_and_repairs_missing_topology():
    devref = "#CB.g:CB"
    tree = _tree(
        '''<G><Layer>
        <BusDis id="380000001" x="47" y="90" w="6" h="30" d="50,90 50,120" />
        <CBreakerDis id="117000001" x="100" y="90" w="30" h="30" rotate="0" devref="#CB.g:CB" />
        <ConnectLine id="340000001" x="47" y="102" w="126" h="6" d="50,105 170,105" node_area="0,0,380000001;1,0,340000004" link="0,0,380000001;1,0,340000004" />
        <ConnectLine id="340000002" x="47" y="102" w="62" h="6" d="50,105 106,105" node_area="0,0,380000001" link="0,0,380000001" />
        <ConnectLine id="340000003" x="121" y="102" w="52" h="6" d="124,105 170,105" node_area="1,0,340000004" link="1,0,340000004" />
        <ConnectLine id="340000004" x="167" y="102" w="20" h="6" d="170,105 181,105" node_area="0,0,340000003" link="0,0,340000003" />
        </Layer></G>'''
    )

    before = inspect_standard_device_connections(
        tree,
        eligible_devrefs={devref},
        geometry_templates=_geometry(devref),
    )
    assert any(issue.issue_type == "重复贯穿连接线" for issue in before.issues)

    result = normalize_standard_device_connections(
        tree,
        eligible_devrefs={devref},
        geometry_templates=_geometry(devref),
    )
    assert result.removed_redundant_lines == 1
    assert result.removed_line_ids == ["340000001"]
    assert result.repaired_topology_links >= 6

    rows = {el.get("id"): el for el in tree.getroot().iter() if el.get("id")}
    assert "340000001" not in rows
    assert rows["117000001"].get("node_area") == "0,1,340000002;1,0,340000003"
    assert "117000001" in (rows["340000002"].get("link") or "")
    assert "117000001" in (rows["340000003"].get("link") or "")


def test_two_pin_side_lines_can_snap_small_gap_to_authoritative_pins_before_bypass_removal():
    devref = "#CB.g:CB"
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="117000001" x="100" y="90" w="30" h="30" rotate="0" devref="#CB.g:CB" />
        <ConnectLine id="340000001" x="47" y="102" w="126" h="6" d="50,105 170,105" />
        <ConnectLine id="340000002" x="47" y="102" w="60" h="6" d="50,105 104,105" />
        <ConnectLine id="340000003" x="123" y="102" w="50" h="6" d="126,105 170,105" />
        </Layer></G>'''
    )
    result = normalize_standard_device_connections(
        tree,
        eligible_devrefs={devref},
        geometry_templates=_geometry(devref),
        max_snap_offset=8,
    )
    rows = {el.get("id"): el for el in tree.getroot().iter() if el.get("id")}
    assert result.removed_redundant_lines == 1
    assert result.connected_endpoints == 2
    assert rows["340000002"].get("d") == "50,105 106,105"
    assert rows["340000003"].get("d") == "124,105 170,105"


def test_jeddah_batch_passes_authoritative_geometry_into_shared_connection_normalizer():
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "connection_geometry_templates" in batch
    assert "geometry_templates=connection_geometry_templates" in batch


def test_two_pin_repair_can_use_feedline_endpoint_as_side_connection():
    devref = "#CB.g:CB"
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="117000001" x="100" y="90" w="30" h="30" rotate="0" devref="#CB.g:CB" />
        <ConnectLine id="340000001" x="47" y="102" w="126" h="6" d="50,105 170,105" />
        <FeedLine id="350000001" x="47" y="82" w="62" h="26" d="50,85 50,105 106,105" node_area="0,0,380000001" link="0,0,380000001" />
        <ConnectLine id="340000003" x="121" y="102" w="52" h="6" d="124,105 170,105" node_area="1,0,340000004" link="1,0,340000004" />
        <ConnectLine id="340000004" x="167" y="102" w="20" h="6" d="170,105 181,105" />
        </Layer></G>'''
    )
    result = normalize_standard_device_connections(
        tree,
        eligible_devrefs={devref},
        geometry_templates=_geometry(devref),
    )
    rows = {el.get("id"): el for el in tree.getroot().iter() if el.get("id")}
    assert result.removed_redundant_lines == 1
    assert "340000001" not in rows
    assert "117000001" in (rows["350000001"].get("link") or "")
    assert rows["117000001"].get("node_area") == "0,1,350000001;1,0,340000003"
