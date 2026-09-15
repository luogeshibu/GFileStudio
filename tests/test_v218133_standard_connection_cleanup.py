from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.engines.standard_connection_cleanup import (
    inspect_standard_device_connections,
    normalize_standard_device_connections,
)


def _tree(xml: str) -> ET.ElementTree:
    return ET.ElementTree(ET.fromstring(xml))


def test_removes_only_proven_redundant_line_and_cleans_references():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="117000001" x="100" y="90" w="30" h="30" devref="#CB.g:CB" node_area="0,1,340000002;1,0,340000003" link="0,1,340000002;1,0,340000003" />
        <ConnectLine id="340000001" x="47" y="102" w="126" h="6" d="50,105 170,105" node_area="0,0,340000002;0,0,340000003" />
        <ConnectLine id="340000002" x="47" y="102" w="62" h="6" d="50,105 106,105" link="0,0,340000001;1,0,117000001" node_area="1,0,117000001" />
        <ConnectLine id="340000003" x="121" y="102" w="52" h="6" d="124,105 170,105" link="0,1,117000001;1,0,340000001" node_area="0,1,117000001" />
        </Layer></G>'''
    )
    before = inspect_standard_device_connections(tree, eligible_devrefs={"#CB.g:CB"})
    assert [issue.issue_type for issue in before.issues] == ["重复贯穿连接线"]

    result = normalize_standard_device_connections(tree, eligible_devrefs={"#CB.g:CB"})
    assert result.removed_redundant_lines == 1
    assert result.removed_line_ids == ["340000001"]
    remaining = {el.get("id"): el for el in tree.getroot().iter() if el.get("id")}
    assert "340000001" not in remaining
    assert remaining["340000002"].get("link") == "1,0,117000001"
    assert remaining["340000003"].get("link") == "0,1,117000001"


def test_preserves_intentional_carrier_line_when_device_has_no_reciprocal_topology():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="117000045" x="923" y="959" w="30" h="30" devref="#CB.g:CB" />
        <ConnectLine id="340000040" x="892" y="968" w="137" h="6" d="895,971 1026,971" node_area="0,0,38000064;1,1,340000046" />
        <ConnectLine id="340000044" x="892" y="968" w="40" h="6" d="895,971 929,971" node_area="0,0,38000064" />
        <ConnectLine id="340000043" x="946" y="968" w="25" h="6" d="949,971 968,971" />
        <ConnectLine id="340000046" x="965" y="968" w="64" h="6" d="968,971 1026,971" />
        </Layer></G>'''
    )
    before = inspect_standard_device_connections(tree, eligible_devrefs={"#CB.g:CB"})
    assert not [issue for issue in before.issues if issue.issue_type == "重复贯穿连接线"]
    result = normalize_standard_device_connections(tree, eligible_devrefs={"#CB.g:CB"})
    assert result.removed_redundant_lines == 0
    remaining = {el.get("id") for el in tree.getroot().iter() if el.get("id")}
    assert "340000040" in remaining


def test_single_pin_device_small_skew_snaps_orthogonal_and_moves_with_pin():
    tree = _tree(
        '''<G><Layer>
        <ZhaiWaiJieDiDaoZha id="188000001" x="100" y="100" w="30" h="28" devref="#GND.g:GND" />
        <ConnectLine id="340000010" x="97" y="97" w="59" h="10" d="100,100 153,104" />
        </Layer></G>'''
    )
    result = normalize_standard_device_connections(
        tree,
        eligible_devrefs={"#GND.g:GND"},
        single_pin_devrefs={"#GND.g:GND"},
        max_snap_offset=8,
    )
    assert result.straightened_lines == 1
    assert result.moved_devices == 1
    rows = {el.get("id"): el for el in tree.getroot().iter() if el.get("id")}
    # Far endpoint is fixed at y=104; near endpoint and device move down by 4.
    assert rows["340000010"].get("d") == "100,104 153,104"
    assert rows["188000001"].get("x") == "100"
    assert rows["188000001"].get("y") == "104"


def test_large_or_ambiguous_skew_is_not_guessed():
    tree = _tree(
        '''<G><Layer>
        <ZhaiWaiJieDiDaoZha id="188000001" x="100" y="100" w="30" h="28" devref="#GND.g:GND" />
        <ConnectLine id="340000010" x="97" y="97" w="59" h="26" d="100,100 153,120" />
        </Layer></G>'''
    )
    result = normalize_standard_device_connections(
        tree,
        eligible_devrefs={"#GND.g:GND"},
        single_pin_devrefs={"#GND.g:GND"},
        max_snap_offset=8,
    )
    assert not result.changed
