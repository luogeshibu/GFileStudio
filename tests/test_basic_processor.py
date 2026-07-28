import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.models import BasicSettings
from g_file_studio.processors.basic_processor import process_basic


def test_replace_attribute_and_generic_delete(tmp_path: Path):
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    (source / "a.g").write_text(
        '<G><Layer><ConnectLine id="10" w="137"/>'
        '<ZhaiWaiJieDiDaoZha p_NameString="YcccD"/></Layer></G>',
        encoding="utf-8",
    )

    settings = BasicSettings(
        input_dir=source,
        output_dir=output,
        replace_attribute=True,
        replace_target_tag="ZhaiWaiJieDiDaoZha",
        replace_target_attribute="p_NameString",
        replace_old_value="YcccD",
        replace_new_value="Q1D",
        delete_matching_element=True,
        delete_target_tag="ConnectLine",
        delete_target_attribute="w",
        delete_target_value="137",
    )
    result = process_basic(settings)
    assert result.success
    assert result.statistics["replaced_attribute_count"] == 1
    assert result.statistics["removed_matching_element_count"] == 1

    root = ET.parse(output / "a.g").getroot()
    layer = root.find("Layer")
    assert layer is not None
    assert layer.find("ConnectLine") is None
    assert layer.find("ZhaiWaiJieDiDaoZha").get("p_NameString") == "Q1D"


def test_delete_matching_element_and_clean_references(tmp_path: Path):
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    (source / "a.g").write_text(
        """
<G>
  <Layer>
    <Disconnector id="100" p_NameString="D1001" />
    <Text id="200" link="0,0,100;0,0,999" node_area="0,0,100" p_FatherObjId="100" />
  </Layer>
</G>
""".strip(),
        encoding="utf-8",
    )
    settings = BasicSettings(
        input_dir=source,
        output_dir=output,
        replace_attribute=False,
        delete_matching_element=True,
        delete_target_tag="Disconnector",
        delete_target_attribute="p_NameString",
        delete_target_value="D1001",
    )
    result = process_basic(settings)
    assert result.statistics["removed_matching_element_count"] == 1

    root = ET.parse(output / "a.g").getroot()
    layer = root.find("Layer")
    assert layer is not None
    assert layer.find("Disconnector") is None
    text = layer.find("Text")
    assert text is not None
    assert text.get("link") == "0,0,999"
    assert text.get("node_area") == ""
    assert text.get("p_FatherObjId") == ""


def test_basic_rules_only_touch_direct_children_of_direct_layer(tmp_path: Path):
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    (source / "scope.g").write_text(
        """
<G p_NameString="YcccD">
  <Theme>
    <ZhaiWaiJieDiDaoZha p_NameString="YcccD" />
    <Disconnector p_NameString="D1001" />
  </Theme>
  <Layer>
    <ZhaiWaiJieDiDaoZha id="2" p_NameString="YcccD" />
    <Disconnector id="3" p_NameString="D1001" />
    <Group id="4">
      <ZhaiWaiJieDiDaoZha id="6" p_NameString="YcccD" />
      <Disconnector id="7" p_NameString="D1001" />
    </Group>
  </Layer>
</G>
""".strip(),
        encoding="utf-8",
    )
    settings = BasicSettings(
        input_dir=source,
        output_dir=output,
        replace_attribute=True,
        replace_target_tag="ZhaiWaiJieDiDaoZha",
        replace_target_attribute="p_NameString",
        replace_old_value="YcccD",
        replace_new_value="Q1D",
        delete_matching_element=True,
        delete_target_tag="Disconnector",
        delete_target_attribute="p_NameString",
        delete_target_value="D1001",
    )
    process_basic(settings)

    root = ET.parse(output / "scope.g").getroot()
    assert root.get("p_NameString") == "YcccD"

    theme = root.find("Theme")
    assert theme is not None
    assert theme.find("ZhaiWaiJieDiDaoZha").get("p_NameString") == "YcccD"
    assert theme.find("Disconnector") is not None

    layer = root.find("Layer")
    assert layer is not None
    assert layer.find("ZhaiWaiJieDiDaoZha").get("p_NameString") == "Q1D"
    assert layer.find("Disconnector") is None

    group = layer.find("Group")
    assert group is not None
    assert group.find("ZhaiWaiJieDiDaoZha").get("p_NameString") == "YcccD"
    assert group.find("Disconnector") is not None


def test_rule_validation_requires_tag_and_attribute(tmp_path: Path):
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    (source / "a.g").write_text("<G><Layer /></G>", encoding="utf-8")

    settings = BasicSettings(
        input_dir=source,
        output_dir=output,
        replace_attribute=True,
        replace_target_tag="",
        replace_target_attribute="p_NameString",
    )

    try:
        process_basic(settings)
    except ValueError as error:
        assert "元素标签不能为空" in str(error)
    else:
        raise AssertionError("空元素标签应当触发校验错误")


def test_replace_rule_is_disabled_by_default(tmp_path: Path):
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    (source / "a.g").write_text(
        '<G><Layer><Device p_NameString="OLD" /></Layer></G>',
        encoding="utf-8",
    )

    settings = BasicSettings(
        input_dir=source,
        output_dir=output,
        replace_target_tag="Device",
        replace_target_attribute="p_NameString",
        replace_old_value="OLD",
        replace_new_value="NEW",
    )
    result = process_basic(settings)
    assert result.statistics["replaced_attribute_count"] == 0
    device = ET.parse(output / "a.g").getroot().find("Layer/Device")
    assert device is not None
    assert device.get("p_NameString") == "OLD"
