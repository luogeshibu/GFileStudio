from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.engines.id_engine import local_name
from g_file_studio.engines.rmu_group_engine import group_rmu_tree
from g_file_studio.models import BasicSettings, InputMode, RmuAction
from g_file_studio.processors.basic_processor import process_basic


def _layer(tree: ET.ElementTree) -> ET.Element:
    return next(child for child in tree.getroot() if local_name(child.tag) == "Layer")


def _fixture_xml() -> str:
    # Four overlapping builtin info-block rects reproduce the real failure around Text 8001589.
    # Only rect 2000100 is an actual RMU because it contains BusDis + CBreakerDis + ground switch.
    return (
        '<G><Layer>'
        '<rect id="2000100" x="100" y="100" w="220" h="220" />'
        '<BusDis id="1200100" x="130" y="150" w="120" h="10" />'
        '<CBreakerDis id="1170100" x="180" y="190" w="30" h="30" />'
        '<ZhaiWaiJieDiDaoZha id="1140100" x="180" y="240" w="30" h="30" />'
        '<Text id="8000100" x="150" y="120" w="40" h="20" ts="RMU" />'
        '<rect id="2001480" x="500" y="500" w="350" h="97" gfs_frame_type="builtin" gfs_frame_role="info_block" />'
        '<rect id="2001482" x="500" y="500" w="350" h="97" gfs_frame_type="builtin" gfs_frame_role="info_block" />'
        '<rect id="2001484" x="500" y="500" w="350" h="97" gfs_frame_type="builtin" gfs_frame_role="info_block" />'
        '<rect id="2001486" x="500" y="500" w="350" h="97" gfs_frame_type="builtin" gfs_frame_role="info_block" />'
        '<Text id="8001589" x="522" y="504" w="39" h="22" gfs_frame_type="builtin" gfs_frame_role="info_block" />'
        '</Layer></G>'
    )


def test_strict_rmu_grouping_ignores_overlapping_builtin_frame_rects():
    tree = ET.ElementTree(ET.fromstring(_fixture_xml()))
    result = group_rmu_tree(tree, Path("frame-and-rmu.g"), validated_rmu_only=True)

    assert result.rect_count == 1
    assert result.rebuilt_group_count == 1
    layer = _layer(tree)
    merges = [element for element in layer if local_name(element.tag) == "Merge"]
    assert len(merges) == 1
    assert len([element for element in layer if local_name(element.tag) == "rect"]) == 5
    # The frame info text remains outside the RMU Merge and no ambiguity is raised.
    assert any((element.get("id") or "") == "8001589" for element in layer)


def test_standalone_rmu_process_writes_g_when_frame_rects_overlap(tmp_path: Path):
    source = tmp_path / "JED-NTH-ABH-12.sln.pic.g"
    source.write_text(_fixture_xml(), encoding="utf-8")
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
    assert result.statistics["failed_file_count"] == 0
    assert result.statistics["rmu_rect_count"] == 1
    assert result.statistics["rmu_group_count"] == 1
    output = next(path for path in result.output_files if path.suffix == ".g")
    assert output.exists()
    assert any("输出" in line and output.name in line for line in logs)


def test_default_grouping_api_keeps_legacy_all_rect_behavior():
    tree = ET.ElementTree(ET.fromstring(
        '<G><Layer><rect id="2000001" x="0" y="0" w="100" h="100" />'
        '<Text id="8000001" x="10" y="10" w="10" h="10" /></Layer></G>'
    ))
    result = group_rmu_tree(tree, Path("legacy.g"))
    assert result.rect_count == 1
    assert result.rebuilt_group_count == 1
