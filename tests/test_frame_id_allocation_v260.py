import xml.etree.ElementTree as ET

from g_file_studio.engines.frame_engine import allocate_template_ids


def test_template_ids_follow_target_same_tag_format():
    target_layer = ET.fromstring(
        '<Layer><Text id="8000010"/><Text id="8000011"/><line id="34000010"/><line id="34000011"/></Layer>'
    )
    template = [
        ET.Element("Text", id="1"),
        ET.Element("Text", id="2"),
        ET.Element("line", id="3"),
        ET.Element("line", id="4"),
    ]
    used = {element.get("id") for element in list(target_layer)}
    mapping = allocate_template_ids(template, used, target_layer)

    assert mapping["1"].startswith("8") and len(mapping["1"]) == 7
    assert mapping["2"].startswith("8") and len(mapping["2"]) == 7
    assert mapping["3"].startswith("34") and len(mapping["3"]) == 8
    assert mapping["4"].startswith("34") and len(mapping["4"]) == 8
    assert len(set(mapping.values())) == 4
