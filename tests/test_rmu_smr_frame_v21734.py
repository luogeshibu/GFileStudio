from pathlib import Path

import pytest
import xml.etree.ElementTree as ET

from g_file_studio.engines.rmu_group_engine import enhance_rmu_tree


def test_smr_matches_nearest_valid_rmu_rect_on_real_file():
    path = Path('/mnt/data/JED-NTH-ABH.sln.pic(2).g')
    if not path.is_file():
        pytest.skip('external real-file fixture is not available in this environment')
    tree = ET.parse(path)
    result = enhance_rmu_tree(
        tree,
        path,
        change_smr_frame_color=True,
        smr_frame_color='#FF0000',
    )
    assert result.smr_text_count == 27
    assert len(result.smr_changes) == 27
    assert result.smr_matched_rect_count == 27
    assert all(change.new_color == '#FF0000' for change in result.smr_changes)
    assert all(change.rect_id for change in result.smr_changes)


def test_smr_feature_does_not_run_when_disabled_on_real_file():
    path = Path('/mnt/data/JED-NTH-ABH.sln.pic(2).g')
    if not path.is_file():
        pytest.skip('external real-file fixture is not available in this environment')
    tree = ET.parse(path)
    result = enhance_rmu_tree(tree, path)
    assert result.smr_text_count == 0
    assert result.smr_changes == []
