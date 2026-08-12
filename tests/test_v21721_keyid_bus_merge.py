from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines.merge_engine import (
    merge_aligned_top_buses,
    validate_main_bus_keyid_sequence,
)


def _write_g(path: Path, keyid: str, fac_id: str = "ST01") -> None:
    key_attr = f' keyid="{keyid}"' if keyid else ' keyid=""'
    path.write_text(
        f'''<G w="1000" h="800" facID="{fac_id}"><Layer>
        <Bus id="30000001"{key_attr} x="97" y="97" w="106" h="6" x1="100" y1="100" x2="200" y2="100" d="100,100 200,100"/>
        <Text id="8000001" x="120" y="200" w="30" h="20"/>
        </Layer></G>''',
        encoding="utf-8",
    )


def test_keyid_preflight_requires_every_file_to_be_associated(tmp_path: Path) -> None:
    a = tmp_path / "a.sln.pic.g"
    b = tmp_path / "b.sln.pic.g"
    _write_g(a, "BUS-A")
    _write_g(b, "")
    with pytest.raises(ValueError, match="keyid"):
        validate_main_bus_keyid_sequence([a, b])


def test_keyid_preflight_rejects_interrupted_same_keyid(tmp_path: Path) -> None:
    paths = []
    for name, keyid in [("a", "A"), ("b", "B"), ("c", "A")]:
        p = tmp_path / f"{name}.sln.pic.g"
        _write_g(p, keyid)
        paths.append(p)
    with pytest.raises(ValueError, match="被阻断"):
        validate_main_bus_keyid_sequence(paths)


def test_keyid_preflight_does_not_block_cross_station_facid(tmp_path: Path) -> None:
    a = tmp_path / "a.sln.pic.g"
    b = tmp_path / "b.sln.pic.g"
    _write_g(a, "A", "ST01")
    _write_g(b, "B", "ST02")
    assert len(validate_main_bus_keyid_sequence([a, b])) == 2


def test_group_merge_keeps_one_bus_per_contiguous_keyid_group() -> None:
    buses = []
    x = 10
    ids = 1
    for keyid in ["A", "A", "B", "B", "B", "B"]:
        buses.append(
            f'<Bus id="{30000000+ids}" keyid="{keyid}" x="{x-3}" y="97" w="106" h="6" '
            f'x1="{x}" y1="100" x2="{x+100}" y2="100" d="{x},100 {x+100},100"/>'
        )
        x += 200
        ids += 1
    root = ET.fromstring("<G><Layer>" + "".join(buses) + "</Layer></G>")
    layer = next(iter(root))
    result = merge_aligned_top_buses(layer, "sample.g")
    remaining = [e for e in layer if e.tag == "Bus"]
    assert result["changed"] is True
    assert result["removed"] == 4
    assert [e.get("keyid") for e in remaining] == ["A", "B"]
    assert len(result["groups"]) == 2
    assert result["groups"][0]["bus_count"] == 2
    assert result["groups"][1]["bus_count"] == 4
