from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(smr=False, smart=False):
    root = ET.Element("Root")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="20000001", x="100", y="100", w="220", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="150", y="150", w="20", h="20")
    ET.SubElement(layer, "CBreakerDis", id="117000001", x="190", y="170", w="20", h="20", p_NameString="Y1")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="230", y="190", w="20", h="20")
    ET.SubElement(layer, "Text", id="8000001", x="160", y="60", w="80", h="20", ts="RMU-01", lc="0,255,0")
    ET.SubElement(layer, "Text", id="8000002", x="180", y="130", w="30", h="15", ts="Y1")
    if smart:
        ET.SubElement(layer, "Text", id="8000003", x="210", y="140", w="40", h="15", ts="SMART")
    if smr:
        ET.SubElement(layer, "Text", id="8000004", x="40", y="180", w="40", h="15", ts="SMR")
    return ET.ElementTree(root)


def test_smr_is_counted_as_intelligent_rmu():
    result = identify_rmus(_tree(smr=True), Path("x.g"), name_positions=("top",), smart_in_type=True)
    assert len(result.items) == 1
    assert result.items[0].smart_count == 1
    assert result.items[0].smart_source == "SMR"


def test_smart_and_smr_count_once_and_keep_sources():
    result = identify_rmus(_tree(smr=True, smart=True), Path("x.g"), name_positions=("top",), smart_in_type=True)
    item = result.items[0]
    assert item.smart_count == 1
    assert item.smart_source == "SMART + SMR"
