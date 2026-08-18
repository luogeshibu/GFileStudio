from decimal import Decimal
import xml.etree.ElementTree as ET

from g_file_studio.engines.merge_engine import merge_explicit_bus_elements
from g_file_studio.models import MergeSettings


def _bus(i, x1, x2, y, keyid):
    return ET.Element("Bus", {
        "id": str(i), "keyid": keyid,
        "x1": str(x1), "y1": str(y), "x2": str(x2), "y2": str(y),
        "d": f"{x1},{y} {x2},{y}", "x": str(x1-3), "y": str(y-3),
        "w": str(x2-x1+6), "h": "6",
    })


def test_manual_bus_merge_ignores_different_keyids():
    layer = ET.Element("Layer")
    a = _bus(30000001, 0, 100, 200, "AAA")
    b = _bus(30000002, 200, 300, 200, "BBB")
    layer.extend([a, b])
    result = merge_explicit_bus_elements(layer, [a, b], "out.g", "组1", "上母线")
    assert result["removed"] == 1
    buses = list(layer)
    assert len(buses) == 1
    assert buses[0].get("id") == "30000001"
    assert buses[0].get("keyid") == "AAA"  # keeper keeps its original attributes
    assert buses[0].get("x1") == "0"
    assert buses[0].get("x2") == "300"


def test_merge_settings_accepts_manual_groups():
    settings = MergeSettings(
        input_dir=".", output_dir=".", ordered_file_names=["08.sln.pic.g", "09.sln.pic.g", "10.sln.pic.g"],
        merge_main_bus=True, main_bus_mode="single",
        main_bus_groups=[["08.sln.pic.g", "09.sln.pic.g"]],
    )
    assert settings.main_bus_groups == [["08.sln.pic.g", "09.sln.pic.g"]]
