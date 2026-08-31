from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.id_engine import local_name
from g_file_studio.models import BasicSettings, InputMode, RmuAction
from g_file_studio.processors.basic_processor import process_basic


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "data" / "combine-test-20260730.sln.pic.g"


def _direct_merges(path: Path) -> list[ET.Element]:
    tree = ET.parse(path)
    layer = next(child for child in tree.getroot() if local_name(child.tag) == "Layer")
    return [element for element in list(layer) if local_name(element.tag) == "Merge"]


def test_rmu_page_group_enables_clean_rebuild_only_for_standalone_rmu_page():
    rmu_page = Path("g_file_studio/ui/pages/rmu_page.py").read_text(encoding="utf-8")
    basic_page = Path("g_file_studio/ui/pages/basic_page.py").read_text(encoding="utf-8")

    assert "reset_existing_merges_before_rmu_group=(self._selected_rmu_action() == RmuAction.GROUP)" in rmu_page
    assert "如果当前文件已存在任何 <Merge>" in rmu_page
    assert "reset_existing_merges_before_rmu_group" not in basic_page


def test_rmu_clean_rebuild_removes_existing_merge_before_grouping(tmp_path: Path):
    source = tmp_path / "input.sln.pic.g"
    source.write_bytes(SAMPLE.read_bytes())
    assert len(_direct_merges(source)) == 1

    output_dir = tmp_path / "out"
    logs: list[str] = []
    result = process_basic(
        BasicSettings(
            source_path=source,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=output_dir,
            rmu_action=RmuAction.GROUP,
            reset_existing_merges_before_rmu_group=True,
        ),
        log=logs.append,
    )

    assert result.success
    assert result.statistics["graphic_merge_removed_count"] == 1
    assert result.statistics["rmu_group_count"] == 2
    assert any("[环网柜组合预清理]" in line and "检测到旧 Merge 1 个" in line for line in logs)

    output = next(path for path in result.output_files if path.suffix == ".g")
    # 旧 Merge 已被删除，随后完全按当前几何重建两个 RMU Merge。
    assert len(_direct_merges(output)) == 2


def test_clean_rebuild_does_not_run_cleanup_when_file_has_no_merge(tmp_path: Path):
    source = tmp_path / "plain.sln.pic.g"
    source.write_text(
        '<G><Layer>'
        '<rect id="2000001" x="100" y="100" w="200" h="200" />'
        '<BusDis id="1200001" x="130" y="150" w="80" h="10" />'
        '<CBreakerDis id="1170001" x="160" y="180" w="20" h="20" />'
        '<ZhaiWaiJieDiDaoZha id="1140001" x="170" y="220" w="20" h="20" />'
        '<Text id="8000001" x="120" y="120" w="20" h="20" />'
        '</Layer></G>',
        encoding="utf-8",
    )
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
    assert result.statistics["graphic_merge_removed_count"] == 0
    assert not any("[环网柜组合预清理]" in line for line in logs)
    output = next(path for path in result.output_files if path.suffix == ".g")
    assert len(_direct_merges(output)) == 1
