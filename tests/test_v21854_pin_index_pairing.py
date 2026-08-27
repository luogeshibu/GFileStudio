from __future__ import annotations

from pathlib import Path

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_mappings, parse_icon_definition


def _write_icon(path: Path, *, body_id: str, w: int, h: int, align: tuple[int, int], pins: list[tuple[str, str, int, int]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pin_xml = "".join(
        f'<pin id="{pin_id}" index="{pin_index}" cx="{x}" cy="{y}"/>'
        for pin_id, pin_index, x, y in pins
    )
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<G><CBreakerDis id="{body_id}" w="{w}" h="{h}" AlignCenter="{align[0]},{align[1]}">'
        f'<Layer>{pin_xml}</Layer></CBreakerDis></G>',
        encoding="utf-8",
    )


def test_realistic_normal_cb_revision_pairs_by_pin_index_when_xml_ids_shift(tmp_path: Path):
    old = tmp_path / "old" / "Circuit_Breaker_NON-SMART.zwk.icn.g"
    new = tmp_path / "new" / "Circuit_Breaker_NO-SMART.zwk.icn.g"
    _write_icon(
        old,
        body_id="Circuit_Breaker_NON-SMART",
        w=28,
        h=28,
        align=(12, 14),
        pins=[("18000002", "2", 12, 4), ("18000003", "3", 12, 24)],
    )
    _write_icon(
        new,
        body_id="Circuit_Breaker_NO-SMART",
        w=30,
        h=30,
        align=(18, 16),
        pins=[("18000003", "2", 18, 6), ("18000004", "3", 18, 26)],
    )

    old_def = parse_icon_definition(old)
    new_def = parse_icon_definition(new)
    assert old_def.pin_ids != new_def.pin_ids
    assert old_def.pin_indices == new_def.pin_indices == ("2", "3")

    analysis = analyze_icon_mappings([(old, new)])
    assert analysis.valid, analysis.incompatible
    rule = analysis.rules[old.name]
    assert rule.new.pins == ((18.0, 6.0), (18.0, 26.0))
    assert rule.new.pin_indices == ("2", "3")


def test_pin_index_mapping_reorders_new_xml_pin_order(tmp_path: Path):
    old = tmp_path / "old.g"
    new = tmp_path / "new.g"
    _write_icon(
        old,
        body_id="OLD",
        w=28,
        h=28,
        align=(12, 14),
        pins=[("A", "2", 12, 4), ("B", "3", 12, 24)],
    )
    # New XML order is reversed and ids are both different. Stable index must win.
    _write_icon(
        new,
        body_id="NEW",
        w=30,
        h=30,
        align=(18, 16),
        pins=[("X", "3", 18, 26), ("Y", "2", 18, 6)],
    )
    analysis = analyze_icon_mappings([(old, new)])
    assert analysis.valid, analysis.incompatible
    assert analysis.rules[old.name].new.pins == ((18.0, 6.0), (18.0, 26.0))


def test_geometry_direction_fallback_allows_renumbered_two_pin_revision(tmp_path: Path):
    old = tmp_path / "old.g"
    new = tmp_path / "new.g"
    _write_icon(
        old,
        body_id="OLD",
        w=28,
        h=28,
        align=(12, 14),
        pins=[("18000002", "2", 12, 4), ("18000003", "3", 12, 24)],
    )
    _write_icon(
        new,
        body_id="NEW",
        w=34,
        h=38,
        align=(17, 19),
        pins=[("18000003", "6", 17, 4), ("18000004", "7", 17, 34)],
    )
    analysis = analyze_icon_mappings([(old, new)])
    assert analysis.valid, analysis.incompatible
    rule = analysis.rules[old.name]
    assert rule.new.pins == ((17.0, 4.0), (17.0, 34.0))


def test_geometry_direction_fallback_rejects_ambiguous_multi_pin_same_side(tmp_path: Path):
    old = tmp_path / "old.g"
    new = tmp_path / "new.g"
    _write_icon(
        old,
        body_id="OLD",
        w=30,
        h=30,
        align=(15, 15),
        pins=[("A", "2", 10, 0), ("B", "3", 20, 0)],
    )
    _write_icon(
        new,
        body_id="NEW",
        w=40,
        h=40,
        align=(20, 20),
        pins=[("X", "6", 12, 0), ("Y", "7", 28, 0)],
    )
    analysis = analyze_icon_mappings([(old, new)])
    assert not analysis.valid
    assert any("几何方向仍有歧义" in issue for issue in analysis.incompatible)
