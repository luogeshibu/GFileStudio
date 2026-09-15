from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_identification_engine import identify_rmus


def _tree(*, y_labels=("Y1", "Y2", "Y3"), q_labels=("Q1",), l_devrefs=3, t_devrefs=1):
    text_parts = []
    for index, label in enumerate(y_labels):
        text_parts.append(
            f'<Text id="81000{index}" x="130" y="{150 + index * 40}" w="20" h="20" ts="{label}"/>'
        )
    for index, label in enumerate(q_labels):
        text_parts.append(
            f'<Text id="82000{index}" x="235" y="{190 + index * 40}" w="20" h="20" ts="{label}"/>'
        )

    switch_parts = []
    for index in range(l_devrefs):
        switch_parts.append(
            f'<CBreakerDis id="11710{index}" x="130" y="{145 + index * 40}" w="40" h="40" '
            'devref="#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"/>'
        )
    for index in range(t_devrefs):
        switch_parts.append(
            f'<CBreakerDis id="11810{index}" x="230" y="{185 + index * 40}" w="34" h="38" '
            'devref="#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART"/>'
        )

    xml = f'''<G><Layer>
    <rect id="2000001" x="100" y="100" w="220" h="220" ls="2"/>
    <Text id="8000002" x="155" y="60" w="90" h="30" ts="33404" lc="0,255,0" lcc="#00ff00"/>
    {''.join(text_parts)}
    <BusDis id="3800004" x="205" y="140" w="6" h="140"/>
    <ZhaiWaiJieDiDaoZha id="188000009" x="120" y="260" w="42" h="28"/>
    {''.join(switch_parts)}
    </Layer></G>'''
    return ET.ElementTree(ET.fromstring(xml))


def test_missing_q_text_uses_devref_t_as_warn_not_fail():
    item = identify_rmus(_tree(q_labels=()), Path("x.g"), name_positions=("top",)).items[0]
    assert item.rmu_type == "3L1T"
    assert item.text_yq_type == "3L0T"
    assert item.devref_type == "3L1T"
    assert item.type_source == "TEXT_YQ+DEVREF_FALLBACK"
    assert item.type_cross_check == "PARTIAL"
    assert item.type_validation_status == "WARN"
    assert "Q 缺失" in item.type_cross_note
    assert "L 类计数一致" in item.type_cross_note


def test_missing_y_text_uses_devref_l_as_warn_not_fail():
    item = identify_rmus(_tree(y_labels=()), Path("x.g"), name_positions=("top",)).items[0]
    assert item.rmu_type == "3L1T"
    assert item.text_yq_type == "0L1T"
    assert item.devref_type == "3L1T"
    assert item.type_source == "TEXT_YQ+DEVREF_FALLBACK"
    assert item.type_cross_check == "PARTIAL"
    assert item.type_validation_status == "WARN"
    assert "Y 缺失" in item.type_cross_note
    assert "T 类计数一致" in item.type_cross_note


def test_present_y_category_still_fails_when_devref_l_disagrees_during_q_fallback():
    item = identify_rmus(
        _tree(y_labels=("Y1", "Y2"), q_labels=(), l_devrefs=3, t_devrefs=1),
        Path("x.g"),
        name_positions=("top",),
    ).items[0]
    assert item.rmu_type == "2L1T"  # Y remains authoritative; only T is filled from devref.
    assert item.text_yq_type == "2L0T"
    assert item.devref_type == "3L1T"
    assert item.type_cross_check == "NO"
    assert item.type_validation_status == "FAIL"
    assert "Y=2L" in item.type_cross_note
    assert "devref L=3L" in item.type_cross_note
