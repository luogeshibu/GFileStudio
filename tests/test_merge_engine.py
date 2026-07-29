from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines import merge_engine


def _write_g(path: Path, body: str, width: int = 1000, height: int = 800) -> None:
    path.write_text(
        f'<G w="{width}" width="{width}" h="{height}" height="{height}"><Layer>{body}</Layer></G>',
        encoding="utf-8",
    )


def test_arbitrary_names_are_naturally_sorted_and_no_bus_uses_top_element(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    _write_g(
        input_dir / "diagram10.sln.pic.g",
        '<Bus id="10" x="50" y="100" x1="50" y1="100" x2="250" y2="100" d="50,100 250,100" />',
    )
    _write_g(
        input_dir / "diagram2.sln.pic.g",
        '<Text id="20" x="20" y="40" w="80" h="20" ts="No Bus" />',
    )

    infos = merge_engine.discover_files(input_dir)
    assert [info.path.name for info in infos] == [
        "diagram2.sln.pic.g",
        "diagram10.sln.pic.g",
    ]

    first = merge_engine.parse_g_file(infos[0])
    second = merge_engine.parse_g_file(infos[1])
    assert first.alignment_mode.startswith("最高图元")
    assert first.alignment_y == Decimal("40")
    assert second.alignment_mode == "顶部水平 <Bus>"

    output_path = output_dir / "MERGED.sln.pic.g"
    merge_engine.merge_g_files(
        infos,
        output_path,
        gap=Decimal("300"),
        left_margin=Decimal("300"),
        top_margin=Decimal("300"),
        right_margin=Decimal("300"),
        bottom_margin=Decimal("300"),
    )
    assert output_path.exists()
    ET.parse(output_path)


def test_invalid_g_suffix_is_rejected(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_g(input_dir / "wrong.g", '<Text id="1" x="10" y="10" w="10" h="10" />')
    with pytest.raises(ValueError, match=".sln.pic.g"):
        merge_engine.discover_files(input_dir)


def test_outer_frame_is_rejected(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    body = """
<line id="1" x1="50" y1="50" x2="950" y2="50" d="50,50 950,50" />
<line id="2" x1="950" y1="50" x2="950" y2="750" d="950,50 950,750" />
<line id="3" x1="950" y1="750" x2="50" y2="750" d="950,750 50,750" />
<line id="4" x1="50" y1="750" x2="50" y2="50" d="50,750 50,50" />
"""
    _write_g(input_dir / "framed.sln.pic.g", body)
    info = merge_engine.discover_files(input_dir)[0]
    with pytest.raises(ValueError, match="非 G File Studio 内置图框"):
        merge_engine.parse_g_file(info)


def test_later_file_without_bus_aligns_highest_element_to_base_bus(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    _write_g(
        input_dir / "a-base.sln.pic.g",
        '<Bus id="1" x="10" y="120" x1="10" y1="120" x2="210" y2="120" d="10,120 210,120" />',
    )
    _write_g(
        input_dir / "b-no-bus.sln.pic.g",
        '<Text id="2" x="30" y="45" w="50" h="20" ts="top" />',
    )

    infos = merge_engine.discover_files(input_dir)
    parsed = [merge_engine.parse_g_file(info) for info in infos]
    assert parsed[0].alignment_y == Decimal("120")
    assert parsed[1].alignment_y == Decimal("45")
    assert parsed[1].alignment_mode.startswith("最高图元")

    output_path = output_dir / "merged.sln.pic.g"
    merge_engine.merge_g_files(
        infos,
        output_path,
        gap=Decimal("100"),
        left_margin=Decimal("50"),
        top_margin=Decimal("50"),
        right_margin=Decimal("50"),
        bottom_margin=Decimal("50"),
    )
    root = ET.parse(output_path).getroot()
    layer = root.find("Layer")
    assert layer is not None
    bus = layer.find("Bus")
    text = layer.find("Text")
    assert bus is not None and text is not None
    assert Decimal(bus.get("y1")) == Decimal(text.get("y"))


def test_user_defined_order_overrides_natural_sort(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_g(
        input_dir / "diagram2.sln.pic.g",
        '<Text id="2" x="10" y="20" w="10" h="10" />',
    )
    _write_g(
        input_dir / "diagram10.sln.pic.g",
        '<Text id="10" x="10" y="30" w="10" h="10" />',
    )

    infos = merge_engine.discover_files(
        input_dir,
        ordered_file_names=[
            "diagram10.sln.pic.g",
            "diagram2.sln.pic.g",
        ],
    )
    assert [info.path.name for info in infos] == [
        "diagram10.sln.pic.g",
        "diagram2.sln.pic.g",
    ]
    assert [info.order for info in infos] == [1, 2]


def test_user_defined_order_must_include_each_file_once(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_g(input_dir / "a.sln.pic.g", '<Text id="1" x="1" y="1" />')
    _write_g(input_dir / "b.sln.pic.g", '<Text id="2" x="2" y="2" />')

    with pytest.raises(ValueError, match="遗漏"):
        merge_engine.discover_files(
            input_dir,
            ordered_file_names=["a.sln.pic.g"],
        )

    with pytest.raises(ValueError, match="重复"):
        merge_engine.discover_files(
            input_dir,
            ordered_file_names=["a.sln.pic.g", "a.sln.pic.g"],
        )


def test_merge_processor_accepts_log_callback_that_uses_print(tmp_path: Path):
    from g_file_studio.models import MergeSettings
    from g_file_studio.processors.merge_processor import merge_feeders

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    _write_g(input_dir / "a.sln.pic.g", '<Text id="1" x="10" y="20" w="10" h="10" />')
    _write_g(input_dir / "b.sln.pic.g", '<Text id="2" x="10" y="20" w="10" h="10" />')

    messages: list[str] = []

    def logger(line: str) -> None:
        print(line)
        messages.append(line)

    result = merge_feeders(
        MergeSettings(
            input_dir=input_dir,
            output_dir=output_dir,
            ordered_file_names=["b.sln.pic.g", "a.sln.pic.g"],
        ),
        log=logger,
    )

    assert result.success
    assert result.statistics["input_order"] == ["b.sln.pic.g", "a.sln.pic.g"]
    assert messages


def test_alignment_uses_topmost_valid_bus_and_ignores_busdis(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_g(
        input_dir / "bus-check.sln.pic.g",
        """
<BusDis id="1" x="10" y="10" x1="10" y1="10" x2="200" y2="10" d="10,10 200,10" />
<Bus id="2" x="10" y="150" x1="10" y1="150" x2="210" y2="150" d="10,150 210,150" />
<Bus id="3" x="10" y="80" x1="10" y1="80" x2="180" y2="80" d="10,80 180,80" />
<Bus id="4" x="10" y="40" x1="10" y1="40" x2="10" y2="40" d="10,40 10,40" />
""",
    )

    info = merge_engine.discover_files(input_dir)[0]
    parsed = merge_engine.parse_g_file(info)
    assert parsed.alignment_mode == "顶部水平 <Bus>"
    # BusDis 的 Y=10 不参与；零长度 Bus 的 Y=40 也不是有效水平母线。
    assert parsed.alignment_y == Decimal("80")


def test_user_defined_subset_is_allowed_when_enabled(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_g(input_dir / "a.sln.pic.g", '<Text id="1" x="1" y="1" />')
    _write_g(input_dir / "b.sln.pic.g", '<Text id="2" x="2" y="2" />')
    _write_g(input_dir / "c.sln.pic.g", '<Text id="3" x="3" y="3" />')

    infos = merge_engine.discover_files(
        input_dir,
        ordered_file_names=["c.sln.pic.g", "a.sln.pic.g"],
        allow_subset=True,
    )

    assert [info.path.name for info in infos] == [
        "c.sln.pic.g",
        "a.sln.pic.g",
    ]
    assert [info.order for info in infos] == [1, 2]


def test_merge_processor_merges_only_selected_subset(tmp_path: Path):
    from g_file_studio.models import MergeSettings
    from g_file_studio.processors.merge_processor import merge_feeders

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    _write_g(input_dir / "a.sln.pic.g", '<Text id="1" x="10" y="20" w="10" h="10" />')
    _write_g(input_dir / "b.sln.pic.g", '<Text id="2" x="20" y="20" w="10" h="10" />')
    _write_g(input_dir / "c.sln.pic.g", '<Text id="3" x="30" y="20" w="10" h="10" />')

    result = merge_feeders(
        MergeSettings(
            input_dir=input_dir,
            output_dir=output_dir,
            output_name="selected.sln.pic.g",
            ordered_file_names=["c.sln.pic.g", "a.sln.pic.g"],
        ),
        log=lambda _line: None,
    )

    assert result.success
    assert result.statistics["input_count"] == 2
    assert result.statistics["input_order"] == ["c.sln.pic.g", "a.sln.pic.g"]

    root = ET.parse(result.output_files[0]).getroot()
    layer = root.find("Layer")
    assert layer is not None
    source_ids = {element.get("id") for element in list(layer)}
    # b 文件未参与合并，因此不会出现其唯一 ID=2。
    assert "2" not in source_ids



def _builtin_frame_config() -> dict[str, object]:
    return {
        "default": {
            "title": "",
            "draw": {"name": "", "date": ""},
            "approve": {"name": "", "date": ""},
            "issue": {"name": "", "date": ""},
        },
        "files": {},
    }


def _add_builtin_frame(source: Path, output: Path) -> None:
    from g_file_studio.engines.frame_engine import process_one_file

    project_root = Path(__file__).resolve().parents[1]
    template_path = (
        project_root
        / "resources"
        / "templates"
        / "SLD-Drawing-Frame-Template.sln.pic.g"
    )
    process_one_file(
        source,
        output,
        ET.parse(template_path),
        _builtin_frame_config(),
        edit_content=True,
    )


def test_marked_builtin_frame_is_removed_before_merge(tmp_path: Path):
    plain = tmp_path / "plain.sln.pic.g"
    framed = tmp_path / "framed.sln.pic.g"
    _write_g(
        plain,
        '<Bus id="body-bus" x="100" y="200" x1="100" y1="200" '
        'x2="300" y2="200" d="100,200 300,200" />',
        width=1000,
        height=800,
    )
    _add_builtin_frame(plain, framed)

    info = merge_engine.parse_filename(framed)
    inspection = merge_engine.inspect_merge_candidate(info)
    assert inspection.eligible is True
    assert inspection.frame_kind == "builtin"
    assert "自动移除" in inspection.status

    parsed = merge_engine.parse_g_file(info)
    assert parsed.removed_builtin_frame_elements >= 25
    assert parsed.frame_kind == "builtin"
    assert parsed.layer.find("Bus") is not None
    # 合并内存副本中不再保留图框身份标记。
    assert parsed.root.get("gfs_frame_type") is None
    assert all(
        element.get("gfs_frame_type") != "builtin"
        for element in list(parsed.layer)
    )


def test_legacy_builtin_detection_ignores_all_text_content(tmp_path: Path):
    plain = tmp_path / "plain.sln.pic.g"
    framed = tmp_path / "legacy.sln.pic.g"
    _write_g(
        plain,
        '<Text id="body" x="200" y="200" w="100" h="50" ts="BODY" />',
        width=1000,
        height=800,
    )
    _add_builtin_frame(plain, framed)

    tree = ET.parse(framed)
    root = tree.getroot()
    root.attrib.pop("gfs_frame_type", None)
    root.attrib.pop("gfs_frame_template", None)
    layer = root.find("Layer")
    assert layer is not None
    for index, element in enumerate(list(layer)):
        element.attrib.pop("gfs_frame_type", None)
        element.attrib.pop("gfs_frame_component", None)
        if element.tag == "Text" and element.get("ts") != "BODY":
            element.set("ts", f"任意修改内容-{index}")
    tree.write(framed, encoding="utf-8", xml_declaration=True)

    info = merge_engine.parse_filename(framed)
    inspection = merge_engine.inspect_merge_candidate(info)
    assert inspection.eligible is True
    assert inspection.frame_kind == "builtin"
    assert inspection.frame_detection_mode == "legacy_builtin_geometry"

    parsed = merge_engine.parse_g_file(info)
    body = next(
        element
        for element in list(parsed.layer)
        if element.tag == "Text" and element.get("ts") == "BODY"
    )
    assert body.get("id") == "body"
    assert all(
        not (element.tag == "Text" and str(element.get("ts", "")).startswith("任意修改内容"))
        for element in list(parsed.layer)
    )


def test_non_builtin_frame_is_catalogued_as_ineligible(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    body = """
<line id="1" x1="50" y1="50" x2="950" y2="50" d="50,50 950,50" />
<line id="2" x1="950" y1="50" x2="950" y2="750" d="950,50 950,750" />
<line id="3" x1="950" y1="750" x2="50" y2="750" d="950,750 50,750" />
<line id="4" x1="50" y1="750" x2="50" y2="50" d="50,750 50,50" />
<Text id="5" x="200" y="200" w="100" h="50" ts="BODY" />
"""
    _write_g(input_dir / "customer.sln.pic.g", body)

    result = merge_engine.inspect_merge_candidates(input_dir)
    assert len(result) == 1
    assert result[0].eligible is False
    assert result[0].frame_kind == "unsupported"
    assert result[0].status == "非内置图框（禁止合并）"
