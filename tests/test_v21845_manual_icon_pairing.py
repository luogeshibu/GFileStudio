from __future__ import annotations

from pathlib import Path

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_mappings


def _write_icon(path: Path, *, tag: str, body_id: str, w: int = 30, h: int = 30):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><G><Layer>'
        f'<{tag} id="{body_id}" w="{w}" h="{h}" AlignCenter="15,15">'
        f'<pin id="p1" cx="15" cy="5"/><pin id="p2" cx="15" cy="25"/>'
        f'</{tag}></Layer></G>',
        encoding="utf-8",
    )


def test_explicit_mapping_allows_different_filename_and_body_id(tmp_path: Path):
    old = tmp_path / "old" / "Circuit_Breaker_NON-SMART.zwk.icn.g"
    new = tmp_path / "new" / "Circuit_Breaker_NO-SMART.zwk.icn.g"
    _write_icon(old, tag="CBreakerDis", body_id="Legacy_CB_NON_SMART")
    _write_icon(new, tag="CBreakerDis", body_id="Circuit_Breaker_NO-SMART", w=34, h=38)

    analysis = analyze_icon_mappings([(old, new)])
    assert analysis.valid, analysis.incompatible
    rule = analysis.rules[old.name]
    assert rule.old.file_name != rule.new.file_name
    assert rule.old.element_id != rule.new.element_id
    assert rule.new_reference_name == "Circuit_Breaker_NO-SMART"


def test_explicit_mapping_still_rejects_incompatible_xml_type(tmp_path: Path):
    old = tmp_path / "old" / "OLD.g"
    new = tmp_path / "new" / "NEW.g"
    _write_icon(old, tag="CBreakerDis", body_id="OLD")
    _write_icon(new, tag="ZhaiWaiJieDiDaoZha", body_id="NEW")

    analysis = analyze_icon_mappings([(old, new)])
    assert not analysis.valid
    assert any("标签" in issue for issue in analysis.incompatible)


def test_manual_pair_dialog_is_present_in_editor_source():
    source = Path("g_file_studio/ui/widgets/icon_upgrade_editor.py").read_text(encoding="utf-8")
    assert 'QPushButton("手动配对…")' in source
    assert 'setWindowTitle("手动 OLD → NEW 图元配对")' in source
    assert 'form.addRow("旧图元 OLD", old_combo)' in source
    assert 'form.addRow("新图元 NEW", new_combo)' in source
    assert "self._all_new" in source
    assert "手动配对优先级最高" in source
