from __future__ import annotations

from pathlib import Path
import hashlib

from g_file_studio.engines.icon_upgrade_engine import analyze_icon_mappings, parse_icon_definition


def _write(path: Path, *, body_id: str, w: int, h: int, align: tuple[int, int], pins: list[tuple[str, str, int, int]]) -> None:
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


def test_real_normal_cb_28x28_to_34x38_maps_top_to_top_bottom_to_bottom(tmp_path: Path) -> None:
    old = tmp_path / "Circuit_Breaker_NON-SMART.zwk.icn.g"
    new = tmp_path / "Circuit_Breaker_NO-SMART.zwk.icn.g"
    _write(
        old,
        body_id="Circuit_Breaker_NON-SMART",
        w=28,
        h=28,
        align=(12, 14),
        pins=[("18000002", "2", 12, 4), ("18000003", "3", 12, 24)],
    )
    _write(
        new,
        body_id="Circuit_Breaker_NO-SMART",
        w=34,
        h=38,
        align=(17, 19),
        pins=[("18000003", "6", 17, 4), ("18000004", "7", 17, 34)],
    )

    old_def = parse_icon_definition(old)
    new_def = parse_icon_definition(new)
    assert old_def.pin_indices == ("2", "3")
    assert new_def.pin_indices == ("6", "7")
    assert set(old_def.pin_ids) != set(new_def.pin_ids)

    analysis = analyze_icon_mappings([(old, new)])
    assert analysis.valid, analysis.incompatible
    rule = analysis.rules[old.name]
    assert rule.new.pins == ((17.0, 4.0), (17.0, 34.0))
    # The normalized target preserves OLD port order for node_area's 0/1 references.
    assert rule.new.pin_indices == old_def.pin_indices
    assert rule.new.pin_ids == old_def.pin_ids


def test_jeddah_pipeline_sources_are_not_changed_by_v21855() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "g_file_studio/jeddah/batch_processor.py": "969d32c050391356784806c3c41745e23f63f8c84eeae4ba92b9a95739c748f7",
        "g_file_studio/ui/pages/jeddah_batch_page.py": "b93c270bb2f8f9644472ed36524b7113fd177d2ed61305e49ae6218090716480",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
