from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus, parse_name_exclusions


def _base_cabinet(*, bus_key_name: str = "38995_BUS", extra_texts: str = "") -> ET.ElementTree:
    xml = f'''<G><Layer>
    <rect id="2001193" x="3752" y="2190" w="220" h="220" ls="2"/>
    <Text id="8001222" x="3789" y="2117" w="155" h="128" ts="38995&#10;" lc="255,255,255"/>
    <Text id="8001201" x="3780" y="2230" w="20" h="20" ts="Y1"/>
    <Text id="8001202" x="3780" y="2350" w="20" h="20" ts="Y2"/>
    <Text id="8001203" x="3890" y="2300" w="20" h="20" ts="Q1"/>
    {extra_texts}
    <BusDis id="3801193" x="3859" y="2230" w="6" h="140" key_name="{bus_key_name}"/>
    <ZhaiWaiJieDiDaoZha id="1881193" x="3770" y="2260" w="42" h="28"/>
    <CBreakerDis id="1171191" x="3780" y="2230" w="40" h="40" p_NameString="Y1" devref="#Load_Breaker_Switch.zwk.icn.g:Load_Breaker_Switch"/>
    <CBreakerDis id="1171192" x="3780" y="2350" w="40" h="40" p_NameString="Y2" devref="#Load_Breaker_Switch.zwk.icn.g:Load_Breaker_Switch"/>
    <CBreakerDis id="1171193" x="3890" y="2300" w="34" h="38" p_NameString="Q1" devref="#Circuit_Breaker.zwk.icn.g:Circuit_Breaker"/>
    </Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_tall_text_bbox_uses_unique_bus_key_name_fallback():
    item = identify_rmus(_base_cabinet(), Path("x.g"), name_positions=("top",)).items[0]
    assert item.name == "38995"
    assert item.name_position == "BusDis.key_name+Text"
    assert item.rmu_type == "2L1T"


def test_exact_user_exclusion_skips_bad_text_and_keeps_legitimate_name():
    extra = '''
    <Text id="8001301" x="3978" y="2260" w="70" h="25" ts="DAS/OK" lc="0,255,0" lcc="#00ff00"/>
    <Text id="8001302" x="3978" y="2320" w="75" h="25" ts="9009" lc="0,255,0" lcc="#00ff00"/>
    '''
    tree = _base_cabinet(bus_key_name="", extra_texts=extra)
    item = identify_rmus(
        tree,
        Path("x.g"),
        name_positions=("right",),
        excluded_name_values=parse_name_exclusions("NOP, DAS/OK, SFI"),
    ).items[0]
    assert item.name == "9009"
    assert item.name_position == "right"


def test_exclusion_is_exact_not_substring_and_applies_to_bus_fallback():
    assert parse_name_exclusions(" NOP, DAS/OK; SFI；nop ") == ("NOP", "DAS/OK", "SFI")

    # SFI is excluded, but SFI-1201 remains a valid exact candidate.
    extra = '<Text id="8001303" x="3978" y="2260" w="95" h="25" ts="SFI-1201"/>'
    item = identify_rmus(
        _base_cabinet(bus_key_name="SFI_BUS", extra_texts=extra),
        Path("x.g"),
        name_positions=("right",),
        excluded_name_values=("SFI",),
    ).items[0]
    assert item.name == "SFI-1201"
    assert item.name_position == "right"

    # If no text survives and metadata itself is excluded, do not resurrect it.
    item2 = identify_rmus(
        _base_cabinet(bus_key_name="SFI_BUS"),
        Path("x.g"),
        name_positions=("right",),
        excluded_name_values=("SFI",),
    ).items[0]
    assert item2.name == ""


def test_metadata_without_matching_text_is_not_used():
    tree = _base_cabinet(bus_key_name="WRONG_BUS")
    item = identify_rmus(tree, Path("x.g"), name_positions=("right",)).items[0]
    assert item.name == ""
    assert item.name_position == ""
