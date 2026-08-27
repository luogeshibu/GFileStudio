from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_pairs, apply_icon_upgrade


def _write_icon(path: Path, w, h, ac, pins):
    pin_xml = "".join(f'<pin id="{pid}" cx="{x}" cy="{y}" />' for pid, x, y in pins)
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><G><Layer>'
        f'<CBreakerDis id="CB" w="{w}" h="{h}" AlignCenter="{ac[0]},{ac[1]}">{pin_xml}</CBreakerDis>'
        f'</Layer></G>',
        encoding="utf-8",
    )


def test_rotation_270_upgrade_keeps_existing_horizontal_wires_straight(tmp_path: Path):
    old = tmp_path / "old" / "LBS.zwk.icn.g"
    new = tmp_path / "new" / "LBS.zwk.icn.g"
    old.parent.mkdir(); new.parent.mkdir()

    # This mirrors the real Jeddah shape transition that exposed the issue:
    # 28x30 -> 40x40.  With a 270-degree instance, AlignCenter-based placement
    # alone puts both new pins one drawing unit above the old horizontal row.
    _write_icon(old, 28, 30, (14, 15), [("p1", 14, 5), ("p2", 14, 25)])
    _write_icon(new, 40, 40, (20, 20), [("p1", 20, 4), ("p2", 20, 36)])
    analysis = analyze_icon_pairs([old], [new])
    assert analysis.valid

    root = ET.fromstring('''<G><Layer>
      <CBreakerDis id="D1" x="1045" y="3328" w="28" h="30" rotate="270"
        devref="#LBS.zwk.icn.g:LBS" node_area="0,1,L0;1,0,L1" />
      <ConnectLine id="L0" d="1030,3343 1049,3343" x="1027" y="3340" w="25" h="6" />
      <ConnectLine id="L1" d="1069,3343 1103,3343" x="1066" y="3340" w="40" h="6" />
    </Layer></G>''')

    result = apply_icon_upgrade(ET.ElementTree(root), analysis.rules)
    device = root.find("./Layer/CBreakerDis")
    l0 = root.find("./Layer/ConnectLine[@id='L0']")
    l1 = root.find("./Layer/ConnectLine[@id='L1']")

    assert result.upgraded_instances == 1
    assert result.adjusted_lines == 2
    # zenon rotates the rectangular 28x30 symbol around the centre of its
    # original box. The centred transform preserves the old electrical centre
    # and keeps both upgraded endpoints exactly on the original horizontal row.
    assert (device.get("x"), device.get("y"), device.get("w"), device.get("h")) == ("1039", "3323", "40", "40")
    assert l0.get("d") == "1030,3343 1043,3343"
    assert l1.get("d") == "1075,3343 1103,3343"


def test_axis_preservation_does_not_change_normal_vertical_upgrade_behavior(tmp_path: Path):
    old = tmp_path / "old" / "CB.zwk.icn.g"
    new = tmp_path / "new" / "CB.zwk.icn.g"
    old.parent.mkdir(); new.parent.mkdir()
    _write_icon(old, 30, 30, (18, 16), [("p1", 18, 6), ("p2", 18, 26)])
    _write_icon(new, 34, 38, (17, 19), [("p1", 17, 4), ("p2", 17, 34)])
    analysis = analyze_icon_pairs([old], [new])

    root = ET.fromstring('''<G><Layer>
      <CBreakerDis id="D1" x="100" y="200" w="30" h="30" rotate="0" devref="#CB.zwk.icn.g:CB" node_area="0,0,L1;1,0,L2" />
      <ConnectLine id="L1" d="118,206 118,180" x="115" y="177" w="6" h="32" />
      <ConnectLine id="L2" d="118,226 118,250" x="115" y="223" w="6" h="30" />
    </Layer></G>''')
    apply_icon_upgrade(ET.ElementTree(root), analysis.rules)

    device = root.find("./Layer/CBreakerDis")
    assert (device.get("x"), device.get("y")) == ("101", "197")
    assert root.find("./Layer/ConnectLine[@id='L1']").get("d") == "118,201 118,180"
    assert root.find("./Layer/ConnectLine[@id='L2']").get("d") == "118,231 118,250"


def test_rotation_90_upgrade_keeps_existing_vertical_wire_straight(tmp_path: Path):
    old = tmp_path / "old" / "GROUND.zwjddz.icn.g"
    new = tmp_path / "new" / "GROUND.zwjddz.icn.g"
    old.parent.mkdir(); new.parent.mkdir()
    _write_icon(old, 30, 28, (15, 14), [("p1", 5, 14)])
    _write_icon(new, 36, 32, (18, 16), [("p1", 4, 16)])
    analysis = analyze_icon_pairs([old], [new])

    root = ET.fromstring('''<G><Layer>
      <CBreakerDis id="D1" x="100" y="200" w="30" h="28" rotate="90"
        devref="#GROUND.zwjddz.icn.g:GROUND" node_area="0,0,L1" />
      <ConnectLine id="L1" d="115,204 115,225" x="112" y="201" w="6" h="27" />
    </Layer></G>''')
    apply_icon_upgrade(ET.ElementTree(root), analysis.rules)

    device = root.find("./Layer/CBreakerDis")
    line = root.find("./Layer/ConnectLine[@id='L1']")
    # The centred 90-degree transform accounts for the rectangular w/h box;
    # the endpoint moves only along the existing vertical axis.
    assert (device.get("x"), device.get("y")) == ("97", "198")
    assert line.get("d") == "115,200 115,225"
