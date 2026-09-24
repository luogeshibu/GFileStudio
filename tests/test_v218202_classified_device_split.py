from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from g_file_studio.models import InputMode
from g_file_studio.processors import poke_processor
from g_file_studio.processors.poke_processor import PokeProcessingSettings, process_pokes


ENTRIES = (
    ("RMU_LBS_S.zwk.icn.g", "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S", "LBS"),
)


def _write_device_file(path: Path) -> None:
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer", {"name": "0"})
    ET.SubElement(layer, "CBreakerDis", {
        "id": "117000292", "x": "1358", "y": "3046", "w": "40", "h": "40",
        "devref": "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S",
    })
    # White numeric text reproduces the false candidate that must now be ignored.
    ET.SubElement(layer, "Text", {
        "id": "8000229", "x": "1226", "y": "2992", "w": "125", "h": "50",
        "ts": "96566", "lc": "255,255,255", "lcc": "#ffffff",
    })
    ET.SubElement(layer, "Text", {
        "id": "8000295", "x": "1404", "y": "3049", "w": "182", "h": "50",
        "ts": "LBS1197", "lc": "255,0,0", "lcc": "#ff0000",
    })
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_classified_only_run_is_independent_from_rmu_recognition(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "overview.g"
    _write_device_file(source)

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("RMU recognition must not run in classified-device-only mode")

    monkeypatch.setattr(poke_processor, "identify_rmus", should_not_run)

    class FakeDb:
        def resolve_rmu_contexts(self, names):
            assert list(names) == ["LBS1197"]
            return {
                "lbs1197": SimpleNamespace(
                    rmu_name="LBS1197",
                    feeder_full_name="JED-STH-ADEL-AH306",
                )
            }, {}

    out = tmp_path / "out"
    result = process_pokes(
        PokeProcessingSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=out,
            enable_rmu_poke=False,
            enable_classified_device_poke=True,
            enable_station_poke=False,
            classification_marker_entries=ENTRIES,
        ),
        FakeDb(),
        log=lambda _msg: None,
    )

    assert result.success
    assert result.statistics["rmu_identified_total"] == 0
    assert result.statistics["classified_device_total"] == 1
    assert result.statistics["classified_device_named"] == 1
    assert result.statistics["classified_device_added"] == 1

    output = ET.parse(out / source.name).getroot()
    pokes = [e for e in output.iter() if e.tag == "poke" and e.get("gfs_device_poke") == "1"]
    assert len(pokes) == 1
    assert pokes[0].get("gfs_device_name") == "LBS1197"
    assert pokes[0].get("gfs_device_text_id") == "8000295"
    assert pokes[0].get("ahref") == "JED-STH-ADEL-AH306-LBS1197.com.pic.g"
