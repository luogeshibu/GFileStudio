from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from g_file_studio.jeddah.style_engine import apply_jeddah_busdis_blue
from g_file_studio.models import MergeSettings, TemplateMode
from g_file_studio.processors.merge_processor import merge_feeders
from g_file_studio.services.template_service import get_builtin_template


def _write_g(path: Path, body: str, width: int = 1600, height: int = 1200) -> None:
    path.write_text(
        f'<G w="{width}" width="{width}" h="{height}" height="{height}"><Layer>{body}</Layer></G>',
        encoding="utf-8",
    )


def test_jeddah_busdis_blue_uses_relation_then_keyid_fallback():
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    linked = ET.SubElement(layer, "BusDis", id="38000001", link="1,0,1", lc="255,0,0", lcc="#FF0000")
    fallback = ET.SubElement(layer, "BusDis", id="38000002", keyid="K-1", lc="0,255,0", lcc="#00FF00")
    skipped = ET.SubElement(layer, "BusDis", id="38000003", lc="128,128,128", lcc="#808080")

    result = apply_jeddah_busdis_blue(ET.ElementTree(root), Path("fixture.g"))

    assert result.scanned_count == 3
    assert result.eligible_count == 2
    assert result.linked_count == 1
    assert result.keyid_fallback_count == 1
    assert result.changed_count == 2
    assert result.skipped_count == 1
    assert linked.get("lc") == "0,0,255" and linked.get("lcc") == "#0000FF"
    assert fallback.get("lc") == "0,0,255" and fallback.get("lcc") == "#0000FF"
    assert skipped.get("lc") == "128,128,128" and skipped.get("lcc") == "#808080"


def test_merge_can_optionally_add_builtin_frame_after_merge(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    _write_g(
        input_dir / "a.sln.pic.g",
        '<Bus id="41000001" x="100" y="200" x1="100" y1="200" x2="600" y2="200" d="100,200 600,200" />',
    )

    template = get_builtin_template()
    result = merge_feeders(
        MergeSettings(
            input_dir=input_dir,
            output_dir=output_dir,
            ordered_file_names=["a.sln.pic.g"],
            output_name="merged.sln.pic.g",
            add_frame_after_merge=True,
            frame_template_file=template.path,
            frame_template_mode=TemplateMode.BUILTIN,
            frame_builtin_template_id=template.template_id,
        ),
        log=lambda _line: None,
    )

    assert result.success
    assert result.statistics["frame_added"] == 1
    assert len(result.output_files) == 1
    output = Path(result.output_files[0])
    assert output.exists()
    root = ET.parse(output).getroot()
    assert root.get("gfs_frame_type") == "builtin"
    assert not any(p.name.startswith(".merge-frame-stage-") for p in output_dir.iterdir())


def test_merge_page_exposes_optional_frame_ui_and_jeddah_page_mentions_busdis_blue():
    merge_page = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    jeddah_page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")

    assert "合并完成后自动添加图框" in merge_page
    assert 'settings_prefix="merge/frame"' in merge_page
    assert "add_frame_after_merge=self.add_frame_after_merge.isChecked()" in merge_page
    assert "BusDis 母线统一刷为蓝色" in jeddah_page
    assert "apply_jeddah_busdis_blue(tree, source)" in batch
    assert '"busdis_blue_changed_count"' in batch


def test_release_version_is_v218135():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
