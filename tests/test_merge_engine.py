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
    with pytest.raises(ValueError, match="外框架图"):
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
