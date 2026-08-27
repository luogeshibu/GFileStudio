from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.icon_upgrade_engine import (
    analyze_icon_pairs,
    apply_icon_upgrade,
    rotated,
    suggest_icon_pairs,
)


def _write_icon(path: Path, *, tag: str, body_id: str, w: int, h: int, ac, pins):
    path.parent.mkdir(parents=True, exist_ok=True)
    pin_xml = "".join(
        f'<pin id="{pin_id}" cx="{x}" cy="{y}" />' for pin_id, x, y in pins
    )
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><G><Layer>'
        f'<{tag} id="{body_id}" w="{w}" h="{h}" AlignCenter="{ac[0]},{ac[1]}">'
        f'{pin_xml}</{tag}></Layer></G>',
        encoding="utf-8",
    )


def test_centered_rotation_matches_real_rectangular_symbol_coordinates():
    # Real legacy Jeddah LBS: 28x30, rotate=270. The pin is one unit left/down
    # from the naive top-left bounding-box rotation because zenon rotates around
    # the centre of the original rectangular box.
    assert rotated((14, 5), 28, 30, 270) == (4.0, 15.0)
    assert rotated((14, 25), 28, 30, 270) == (24.0, 15.0)

    # Real external ground disconnector: 30x28. Its opposite aspect ratio yields
    # the opposite one-unit centring offset.
    assert rotated((27, 14), 30, 28, 270) == (15.0, 2.0)
    assert rotated((27, 14), 30, 28, 90) == (15.0, 26.0)


def test_ground_disconnector_upgrade_preserves_existing_connection_exactly(tmp_path: Path):
    old = tmp_path / "old" / "External_grounddisconnector_new.zwjddz.icn.g"
    new = tmp_path / "new" / "External_grounddisconnector_new.zwjddz.icn.g"
    _write_icon(
        old,
        tag="ZhaiWaiJieDiDaoZha",
        body_id="External_grounddisconnector_new",
        w=30,
        h=28,
        ac=(27, 14),
        pins=[("18000003", 27, 14)],
    )
    _write_icon(
        new,
        tag="ZhaiWaiJieDiDaoZha",
        body_id="External_grounddisconnector_new",
        w=30,
        h=28,
        ac=(25, 14),
        pins=[("18000003", 25, 14)],
    )
    analysis = analyze_icon_pairs([old], [new])
    assert analysis.valid

    # Mirrors RMU 30907 from the user's real source G.
    root = ET.fromstring('''<G><Layer>
      <ZhaiWaiJieDiDaoZha id="188001300" x="1162" y="4495" w="30" h="28" rotate="270"
        devref="#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new"
        node_area="0,0,34001308" />
      <ConnectLine id="34001308" d="1177,4497 1177,4478" x="1174" y="4475" w="6" h="25" />
    </Layer></G>''')

    result = apply_icon_upgrade(ET.ElementTree(root), analysis.rules)
    device = root.find("./Layer/ZhaiWaiJieDiDaoZha")
    line = root.find("./Layer/ConnectLine")

    assert result.upgraded_instances == 1
    assert (device.get("x"), device.get("y")) == ("1162", "4493")
    # AC == pin for this symbol, so changing AC from x=27 to x=25 must move the
    # body around the electrical anchor, not move the electrical connection.
    assert line.get("d") == "1177,4497 1177,4478"

    # Re-running is idempotent even though old/new w/h are identical.
    second = apply_icon_upgrade(ET.ElementTree(root), analysis.rules)
    assert second.upgraded_instances == 0
    assert second.already_new_instances == 1
    assert line.get("d") == "1177,4497 1177,4478"


def test_batch_pairing_uses_exact_name_then_unique_body_identity(tmp_path: Path):
    old_a = tmp_path / "old" / "LBS_OLD.g"
    old_b = tmp_path / "old" / "CB.g"
    new_a = tmp_path / "new" / "LBS_RENAMED.g"
    new_b = tmp_path / "new" / "CB.g"

    _write_icon(old_a, tag="CBreakerDis", body_id="Load_Breaker_Switch_SMART", w=28, h=30, ac=(14, 15), pins=[("p1", 14, 5), ("p2", 14, 25)])
    _write_icon(new_a, tag="CBreakerDis", body_id="Load_Breaker_Switch_SMART", w=40, h=40, ac=(20, 20), pins=[("p1", 20, 4), ("p2", 20, 36)])
    _write_icon(old_b, tag="CBreakerDis", body_id="Circuit_Breaker_SMART", w=30, h=30, ac=(18, 16), pins=[("p1", 18, 6), ("p2", 18, 26)])
    _write_icon(new_b, tag="CBreakerDis", body_id="Circuit_Breaker_SMART", w=34, h=38, ac=(17, 19), pins=[("p1", 17, 4), ("p2", 17, 34)])

    suggestions = suggest_icon_pairs(
        {old_a.name: old_a, old_b.name: old_b},
        {new_a.name: new_a, new_b.name: new_b},
    )
    assert suggestions[old_b.name] == (new_b.name, "完全同名")
    assert suggestions[old_a.name] == (new_a.name, "图元类型 + 主体 ID")


def test_batch_pairing_never_guesses_ambiguous_body_identity(tmp_path: Path):
    old = tmp_path / "old" / "A.g"
    new1 = tmp_path / "new" / "B1.g"
    new2 = tmp_path / "new" / "B2.g"
    for path in (old, new1, new2):
        _write_icon(path, tag="CBreakerDis", body_id="SAME", w=30, h=30, ac=(15, 15), pins=[("p1", 15, 5), ("p2", 15, 25)])

    suggestions = suggest_icon_pairs(
        {old.name: old},
        {new1.name: new1, new2.name: new2},
    )
    assert old.name not in suggestions
