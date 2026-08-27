from __future__ import annotations

from pathlib import Path


def test_jeddah_batch_reuses_existing_margin_and_frame_processors():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "adjust_graph_margins" in source
    assert "add_drawing_frames" in source
    assert "MarginSettings" in source
    assert "FrameSettings" in source
    assert 'margin_left: int = 500' in source
    assert 'margin_top: int = 500' in source
    assert 'margin_right: int = 500' in source
    assert 'margin_bottom: int = 500' in source
    assert 'source_path=stage_id' in source
    assert 'output_dir=stage_margin' in source
    assert 'source_path=stage_margin' in source
    assert 'output_dir=final_dir' in source


def test_existing_margin_and_frame_processors_are_not_modified_by_jeddah_feature():
    # The Jeddah feature must orchestrate the already-existing processors rather than
    # copying their algorithms into the site-specific workflow.
    margin = Path("g_file_studio/processors/margin_processor.py").read_text(encoding="utf-8")
    frame = Path("g_file_studio/processors/frame_processor.py").read_text(encoding="utf-8")
    assert "def adjust_graph_margins(" in margin
    assert "def add_drawing_frames(" in frame
    jeddah = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    assert "adjust_one_file(" not in jeddah
    assert "frame_engine.process_one_file(" not in jeddah


def test_jeddah_page_exposes_margin_500_and_existing_frame_template_selector():
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert 'get_int("jeddah_batch/margin_left", 500)' in page
    assert 'get_int("jeddah_batch/margin_top", 500)' in page
    assert 'get_int("jeddah_batch/margin_right", 500)' in page
    assert 'get_int("jeddah_batch/margin_bottom", 500)' in page
    assert 'TemplateSelector(' in page
    assert 'settings_prefix="jeddah_batch/frame"' in page
