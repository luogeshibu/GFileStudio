from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines.merge_engine import (
    inspect_main_bus_metadata,
    merge_aligned_top_buses,
    validate_main_bus_keyid_sequence,
)


def _write(path: Path, buses: list[tuple[str, str, int]], fac_id: str = "") -> None:
    attrs = f' facID="{fac_id}"' if fac_id else ""
    body = []
    for i, (bus_id, keyid, y) in enumerate(buses):
        key_attr = f' keyid="{keyid}"' if keyid != "__MISSING__" else ""
        body.append(
            f'<Bus id="{bus_id}"{key_attr} x="97" y="{y-3}" w="106" h="6" '
            f'x1="100" y1="{y}" x2="200" y2="{y}" d="100,{y} 200,{y}"/>'
        )
    # vertical/degenerate Bus helper without keyid must not count as a bus bar
    body.append('<Bus id="39999999" x="200" y="50" w="6" h="6" x1="203" y1="50" x2="203" y2="50" d="203,50 203,50"/>')
    path.write_text(f'<G w="1000" h="800"{attrs}><Layer>{"".join(body)}</Layer></G>', encoding='utf-8')


def test_cross_station_facid_is_not_a_hard_block_anymore(tmp_path: Path) -> None:
    a = tmp_path / "A-01.sln.pic.g"
    b = tmp_path / "B-01.sln.pic.g"
    _write(a, [("30000001", "K1", 100)], "ST01")
    _write(b, [("30000002", "K1", 100)], "ST02")
    result = validate_main_bus_keyid_sequence([a, b])
    assert len(result) == 2


def test_double_bus_file_is_allowed_and_exposes_two_keyids(tmp_path: Path) -> None:
    p = tmp_path / "double.sln.pic.g"
    _write(p, [("30000001", "BB1", 100), ("30000002", "BB2", 121)])
    item = inspect_main_bus_metadata(p, "double")
    assert item["reason"] == ""
    assert item["keyids"] == ["BB1", "BB2"]


def test_real_horizontal_bus_without_keyid_blocks_feature(tmp_path: Path) -> None:
    p = tmp_path / "missing.sln.pic.g"
    _write(p, [("30000001", "__MISSING__", 100)])
    with pytest.raises(ValueError, match="keyid"):
        validate_main_bus_keyid_sequence([p])


def test_same_keyid_must_be_contiguous_even_with_double_bus_files(tmp_path: Path) -> None:
    paths = []
    specs = [
        [("30000001", "A", 100), ("30000002", "X", 121)],
        [("30000003", "B", 100), ("30000004", "X", 121)],
        [("30000005", "A", 100), ("30000006", "X", 121)],
    ]
    for i, buses in enumerate(specs):
        p = tmp_path / f"f{i}.sln.pic.g"
        _write(p, buses)
        paths.append(p)
    with pytest.raises(ValueError, match="被阻断"):
        validate_main_bus_keyid_sequence(paths, "double")


def test_different_keyids_never_collapse_even_if_same_y() -> None:
    root = ET.fromstring(
        '<G><Layer>'
        '<Bus id="30000001" keyid="A" x="7" y="97" w="106" h="6" x1="10" y1="100" x2="110" y2="100" d="10,100 110,100"/>'
        '<Bus id="30000002" keyid="B" x="207" y="97" w="106" h="6" x1="210" y1="100" x2="310" y2="100" d="210,100 310,100"/>'
        '</Layer></G>'
    )
    layer = next(iter(root))
    result = merge_aligned_top_buses(layer, "sample.g")
    assert result["removed"] == 0
    assert len([e for e in layer if e.tag == "Bus"]) == 2


def test_same_keyid_on_different_horizontal_levels_is_forbidden() -> None:
    root = ET.fromstring(
        '<G><Layer>'
        '<Bus id="30000001" keyid="A" x="7" y="97" w="106" h="6" x1="10" y1="100" x2="110" y2="100" d="10,100 110,100"/>'
        '<Bus id="30000002" keyid="A" x="207" y="118" w="106" h="6" x1="210" y1="121" x2="310" y2="121" d="210,121 310,121"/>'
        '</Layer></G>'
    )
    layer = next(iter(root))
    with pytest.raises(ValueError, match="同一水平线"):
        merge_aligned_top_buses(layer, "sample.g")


def test_double_bus_groups_merge_independently() -> None:
    root = ET.fromstring(
        '<G><Layer>'
        '<Bus id="30000001" keyid="A" x="7" y="97" w="106" h="6" x1="10" y1="100" x2="110" y2="100" d="10,100 110,100"/>'
        '<Bus id="30000002" keyid="B" x="7" y="118" w="106" h="6" x1="10" y1="121" x2="110" y2="121" d="10,121 110,121"/>'
        '<Bus id="30000003" keyid="A" x="207" y="97" w="106" h="6" x1="210" y1="100" x2="310" y2="100" d="210,100 310,100"/>'
        '<Bus id="30000004" keyid="B" x="207" y="118" w="106" h="6" x1="210" y1="121" x2="310" y2="121" d="210,121 310,121"/>'
        '</Layer></G>'
    )
    layer = next(iter(root))
    result = merge_aligned_top_buses(layer, "sample.g")
    remaining = [e for e in layer if e.tag == "Bus"]
    assert result["removed"] == 2
    assert len(remaining) == 2
    assert {e.get("keyid") for e in remaining} == {"A", "B"}
    ys = {e.get("keyid"): e.get("y1") for e in remaining}
    assert ys == {"A": "100", "B": "121"}
