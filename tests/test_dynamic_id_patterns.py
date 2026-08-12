import xml.etree.ElementTree as ET

from g_file_studio.engines.merge_engine import (
    generate_unique_id,
    infer_element_id_patterns,
    normalize_base_layer_duplicate_ids,
)


def test_infers_majority_prefix_and_fixed_total_length():
    layer = ET.fromstring(
        '<Layer>'
        '<ConnectLine id="34000070" />'
        '<ConnectLine id="34000071" />'
        '<ConnectLine id="34000125" />'
        '<ConnectLine id="130" />'
        '<Text id="8000070" />'
        '<Text id="8000085" />'
        '</Layer>'
    )

    patterns = infer_element_id_patterns(layer)

    connector = patterns["ConnectLine"]
    assert connector.prefix == "34"
    assert connector.total_length == 8
    assert connector.build(1) == "34000001"
    assert connector.build(68) == "34000068"
    assert connector.build(999) == "34000999"
    assert connector.build(1000) == "34001000"
    assert connector.build(10000) == "34010000"

    text = patterns["Text"]
    assert text.prefix == "8"
    assert text.total_length == 7


def test_duplicate_short_id_uses_same_type_majority_format():
    layer = ET.fromstring(
        '<Layer>'
        '<ConnectLine id="34000070" />'
        '<ConnectLine id="34000071" />'
        '<ConnectLine id="34000125" />'
        '<ConnectLine id="130" />'
        '<ConnectLine id="130" />'
        '</Layer>'
    )

    blocked = {element.get("id") for element in list(layer)}
    result = normalize_base_layer_duplicate_ids(layer, blocked)
    ids = [element.get("id") for element in list(layer)]

    assert result.source_internal_duplicates == 1
    assert ids[-2] == "130"  # v2.4.0 行为：第一次出现保持不变。
    assert ids[-1] == "34000126"
    assert len(ids[-1]) == 8
    assert ids[-1].startswith("34")


def test_normal_duplicate_increments_inside_fixed_pattern():
    layer = ET.fromstring(
        '<Layer>'
        '<ConnectLine id="34000038" />'
        '<ConnectLine id="34000038" />'
        '<ConnectLine id="34000039" />'
        '<ConnectLine id="34000040" />'
        '</Layer>'
    )
    patterns = infer_element_id_patterns(layer)
    pattern = patterns["ConnectLine"]

    assert generate_unique_id(
        "34000038",
        {"34000038", "34000039", "34000040"},
        pattern,
    ) == "34000041"
