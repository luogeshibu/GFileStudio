from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_pairs, apply_icon_upgrade


def _write_icon(path: Path, w, h, ac, pins):
    pin_xml = "".join(
        f'<pin id="{pid}" cx="{x}" cy="{y}" />' for pid, x, y in pins
    )
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><G><Layer><CBreakerDis id="CB" w="{w}" h="{h}" AlignCenter="{ac[0]},{ac[1]}">{pin_xml}</CBreakerDis></Layer></G>',
        encoding="utf-8",
    )


def test_requires_complete_old_new_pairs(tmp_path: Path):
    old = tmp_path / "old" / "CB.zwk.icn.g"
    old.parent.mkdir()
    _write_icon(old, 30, 30, (18, 16), [("p1", 18, 6), ("p2", 18, 26)])
    analysis = analyze_icon_pairs([old], [])
    assert not analysis.valid
    assert analysis.missing_new == ["CB.zwk.icn.g"]


def test_pin_order_is_mapped_by_stable_pin_id(tmp_path: Path):
    old = tmp_path / "old" / "CB.zwk.icn.g"
    new = tmp_path / "new" / "CB.zwk.icn.g"
    old.parent.mkdir(); new.parent.mkdir()
    _write_icon(old, 30, 30, (18, 16), [("p1", 18, 6), ("p2", 18, 26)])
    # 新图元 XML 顺序故意反过来；逻辑端口仍应按 pin id 对齐。
    _write_icon(new, 34, 38, (17, 19), [("p2", 17, 34), ("p1", 17, 4)])
    analysis = analyze_icon_pairs([old], [new])
    assert analysis.valid
    rule = analysis.rules["CB.zwk.icn.g"]
    assert rule.new.pins == ((17.0, 4.0), (17.0, 34.0))


def test_upgrade_keeps_align_center_and_moves_line_endpoints_to_new_pins(tmp_path: Path):
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
    tree = ET.ElementTree(root)
    result = apply_icon_upgrade(tree, analysis.rules)
    device = root.find("./Layer/CBreakerDis")
    lines = {line.get("id"): line for line in root.findall("./Layer/ConnectLine")}

    assert result.upgraded_instances == 1
    assert result.adjusted_lines == 2
    # 旧绝对 AlignCenter=(118,216)，新相对 AC=(17,19)，故新 x/y=(101,197)。
    assert device.get("x") == "101"
    assert device.get("y") == "197"
    assert device.get("w") == "34"
    assert device.get("h") == "38"
    assert lines["L1"].get("d") == "118,201 118,180"
    assert lines["L2"].get("d") == "118,231 118,250"
