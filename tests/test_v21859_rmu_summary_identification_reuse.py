from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import g_file_studio.engines.rmu_group_engine as rmu_group_engine
from g_file_studio.engines.id_engine import local_name
from g_file_studio.models import BasicSettings, InputMode, RmuAction
from g_file_studio.processors.basic_processor import process_basic


def _direct_merges(path: Path) -> list[ET.Element]:
    tree = ET.parse(path)
    layer = next(child for child in tree.getroot() if local_name(child.tag) == "Layer")
    return [element for element in list(layer) if local_name(element.tag) == "Merge"]


def test_standalone_rmu_group_reuses_summary_identifier_for_cleanup_and_group(monkeypatch, tmp_path: Path):
    source = tmp_path / "rmu-with-decoy.g"
    source.write_text(
        '<G><Layer>'
        # Existing Merge forces the clean-rebuild pre-cleanup path.
        '<Merge id="2000999" mergex="99" mergey="99" w="222" h="222" mergesize="5" />'
        '<rect id="2000100" x="100" y="100" w="220" h="220" />'
        '<BusDis id="1200100" x="130" y="150" w="120" h="10" />'
        '<CBreakerDis id="1170100" x="180" y="190" w="30" h="30" devref="Circuit_Breaker_NO-SMART.g" />'
        '<ZhaiWaiJieDiDaoZha id="1140100" x="180" y="240" w="30" h="30" />'
        '<Text id="8000100" x="150" y="120" w="40" h="20" ts="RMU-100" />'
        # Decoy rect must never become a cabinet owner.
        '<rect id="2000200" x="500" y="500" w="350" h="120" gfs_frame_role="info_block" />'
        '<Text id="8000200" x="520" y="520" w="80" h="20" ts="INFO" />'
        '</Layer></G>',
        encoding="utf-8",
    )

    # v2.18.59 standalone flow must not use the group's private RMU-guess helper at all.
    def _legacy_guess_must_not_run(_layer):
        raise AssertionError("standalone RMU grouping must reuse identify_rmus(), not private rect guessing")

    monkeypatch.setattr(rmu_group_engine, "_valid_rmu_rects_for_smr", _legacy_guess_must_not_run)
    logs: list[str] = []
    result = process_basic(
        BasicSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=tmp_path / "out",
            rmu_action=RmuAction.GROUP,
            reset_existing_merges_before_rmu_group=True,
        ),
        log=logs.append,
    )

    assert result.success
    assert result.statistics["graphic_merge_removed_count"] == 1
    assert result.statistics["rmu_rect_count"] == 1
    assert result.statistics["rmu_group_count"] == 1
    assert any("直接复用 RMU 信息汇总识别器" in line and "确认 RMU 1 个" in line for line in logs)
    output = next(path for path in result.output_files if path.suffix == ".g")
    assert len(_direct_merges(output)) == 1


def test_rmu_page_explains_summary_identifier_is_single_source_of_truth():
    page = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    processor = Path("g_file_studio/processors/basic_processor.py").read_text(encoding="utf-8")

    assert "直接复用页面最前方“RMU 基础识别与汇总”的现有识别算法" in page
    assert "grouping_identification = identify_rmus(" in processor
    assert "validated_rmu_rect_ids=grouping_rmu_rect_ids" in processor
    assert "rmu_rect_ids=grouping_rmu_rect_ids" in processor
