from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.engines.merge_engine import merge_aligned_top_buses, validate_final_layer


def test_removed_bus_required_targets_are_remapped_to_keeper() -> None:
    root = ET.fromstring(
        '''<G><Layer>
        <Bus id="30000001" keyid="K1" x="7" y="97" w="106" h="6" x1="10" y1="100" x2="110" y2="100" d="10,100 110,100" node_area="0,1,34000001" />
        <ConnectLine id="34000001" d="50,120 50,100" node_area="0,1,101000001;1,0,30000001" link="0,1,101000001;1,0,30000001" />
        <Bus id="30000002" keyid="K1" x="207" y="97" w="106" h="6" x1="210" y1="100" x2="310" y2="100" d="210,100 310,100" node_area="0,1,34000002" />
        <ConnectLine id="34000002" d="250,120 250,100" node_area="0,1,101000002;1,0,30000002" link="0,1,101000002;1,0,30000002" />
        </Layer></G>'''
    )
    layer = next(iter(root))
    required = {"30000001", "30000002"}

    result = merge_aligned_top_buses(layer, "sample.g")
    mapping = result["removed_id_map"]
    remapped_required = {mapping.get(item, item) for item in required}

    assert remapped_required == {"30000001"}
    validate_final_layer(layer, remapped_required)
