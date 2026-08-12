from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.merge_engine import (
    get_bus_line,
    local_name,
    merge_aligned_top_buses,
)
from g_file_studio.models import MergeSettings


def test_merge_settings_single_bus_default_off(tmp_path: Path) -> None:
    settings = MergeSettings(input_dir=tmp_path, output_dir=tmp_path)
    assert settings.merge_main_bus is False


def test_merge_aligned_top_buses_keeps_one_and_rewrites_references() -> None:
    root = ET.fromstring(
        '''<G><Layer>
        <Bus id="30000001" keyid="K1" x="7" y="97" w="106" h="6" x1="10" y1="100" x2="110" y2="100" d="10,100 110,100" node_area="0,1,34000001" />
        <ConnectLine id="34000001" d="50,120 50,100" node_area="0,1,101000001;1,0,30000001" link="0,1,101000001;1,0,30000001" />
        <Bus id="30000002" keyid="K1" x="207" y="97" w="106" h="6" x1="210" y1="100" x2="310" y2="100" d="210,100 310,100" node_area="0,1,34000002" />
        <ConnectLine id="34000002" d="250,120 250,100" node_area="0,1,101000002;1,0,30000002" link="0,1,101000002;1,0,30000002" />
        <BusDis id="38000003" x="20" y="200" w="100" h="6" d="20,203 120,203" />
        </Layer></G>'''
    )
    layer = next(iter(root))
    result = merge_aligned_top_buses(layer, "sample.g")
    assert result["changed"] is True
    assert result["removed"] == 1
    assert result["removed_id_map"] == {"30000002": "30000001"}

    buses = [e for e in layer.iter() if local_name(e.tag) == "Bus"]
    assert len(buses) == 1
    bus = buses[0]
    assert bus.get("id") == "30000001"
    assert get_bus_line(bus) == (10, 100, 310, 100)
    assert bus.get("node_area") == "0,1,34000001;0,1,34000002"

    line2 = next(e for e in layer.iter() if e.get("id") == "34000002")
    assert "30000002" not in (line2.get("node_area") or "")
    assert "30000001" in (line2.get("node_area") or "")
    assert "30000001" in (line2.get("link") or "")

    # BusDis is not a main Bus and must not be touched.
    assert any(local_name(e.tag) == "BusDis" and e.get("id") == "38000003" for e in layer.iter())
