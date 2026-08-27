from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.batch_processor import _FileSummary, _remove_all_graphic_merges_first


def _signature(element: ET.Element):
    return element.tag, tuple(sorted(element.attrib.items())), element.text


def test_jeddah_runs_existing_graphic_merge_cleanup_as_first_stage(tmp_path: Path):
    source = tmp_path / "input.g"
    source.write_text(
        '''<G><Layer>
        <Merge id="20000001" mergex="100" mergey="100" w="220" h="220" mergesize="4" />
        <rect id="2000001" x="100" y="100" w="220" h="220" keyid="KEEP_RECT" />
        <BusDis id="38000001" x="205" y="145" w="8" h="130" key_name="6703_BUS" keyid="KEEP_BUS" />
        <CBreakerDis id="117000001" x="155" y="180" w="28" h="30" p_NameString="Y1" devref="KEEP_DEVREF" keyid="KEEP_CB" />
        <Text id="8000001" ts="6703" x="150" y="45" w="120" h="50" keyid="KEEP_TEXT" />
        </Layer></G>''',
        encoding="utf-8",
    )
    before_tree = ET.parse(source)
    before_layer = before_tree.getroot().find("Layer")
    before = {
        e.get("id"): _signature(e)
        for e in list(before_layer)
        if e.tag != "Merge"
    }

    out_dir = tmp_path / "out"
    summaries = {source.name: _FileSummary(source.name)}
    removed, lowered = _remove_all_graphic_merges_first(
        [source], out_dir, summaries=summaries, log=lambda _msg: None, progress=None
    )

    after_tree = ET.parse(out_dir / source.name)
    after_layer = after_tree.getroot().find("Layer")
    after = {
        e.get("id"): _signature(e)
        for e in list(after_layer)
        if e.tag != "Merge"
    }

    assert removed == 1
    assert not [e for e in list(after_layer) if e.tag == "Merge"]
    assert before == after
    assert summaries[source.name].graphic_merges_removed == 1
    assert summaries[source.name].rmu_rects_lowered == lowered


def test_jeddah_pipeline_calls_merge_cleanup_before_small_element_scan():
    source = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    cleanup_call = source.index("_remove_all_graphic_merges_first(", source.index("def process_jeddah_batch"))
    small_call = source.index("_copy_or_delete_small_elements(", source.index("def process_jeddah_batch"))
    assert cleanup_call < small_call

    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    assert '"✓ 1. 彻底取消图形组合（删除全部 <Merge>，并将 RMU 外框置底）"' in page
    assert '"✓ 2. 删除异常小尺寸元素"' in page
