from pathlib import Path

from g_file_studio.services.g_schema_service import scan_direct_layer_schema


def test_scan_only_direct_children_of_direct_layer(tmp_path: Path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "sample.sln.pic.g").write_text(
        """
<G>
  <Theme>
    <IgnoredTheme themeAttr="1" />
  </Theme>
  <Layer>
    <Bus id="1" x="10" y="20" />
    <ConnectLine id="2" w="137" custom="A" />
    <Group id="3">
      <NestedDevice nestedAttr="1" />
    </Group>
  </Layer>
  <IgnoredOutside outsideAttr="1" />
</G>
""".strip(),
        encoding="utf-8",
    )

    result = scan_direct_layer_schema(source)

    assert result.file_count == 1
    assert result.layer_count == 1
    assert result.direct_element_count == 3
    assert result.tags == ("Bus", "ConnectLine", "Group")
    assert result.tag_attributes["Bus"] == ("id", "x", "y")
    assert result.tag_attributes["ConnectLine"] == ("custom", "id", "w")
    assert "IgnoredTheme" not in result.tag_attributes
    assert "NestedDevice" not in result.tag_attributes
    assert "IgnoredOutside" not in result.tag_attributes


def test_scan_combines_attributes_for_same_tag(tmp_path: Path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "a.g").write_text(
        '<G><Layer><Device id="1" p_NameString="A" /></Layer></G>',
        encoding="utf-8",
    )
    (source / "b.g").write_text(
        '<G><Layer><Device id="2" key_name="B" /></Layer></G>',
        encoding="utf-8",
    )

    result = scan_direct_layer_schema(source)

    assert result.file_count == 2
    assert result.tag_attributes["Device"] == ("id", "key_name", "p_NameString")
