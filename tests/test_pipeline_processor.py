from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from g_file_studio.engines.frame_engine import process_one_file
from g_file_studio.engines.margin_engine import UnsupportedExistingFrameError
from g_file_studio.models import (
    BasicSettings,
    FrameSettings,
    InputMode,
    MarginSettings,
    MergeSettings,
    PipelineSettings,
)
from g_file_studio.processors.pipeline_processor import run_pipeline
from g_file_studio.services.temp_workspace_service import TempWorkspaceService


def _write_g(path: Path) -> None:
    path.write_text(
        '<G w="1000" width="1000" h="800" height="800"><Layer>'
        '<Text id="1" x="10" y="20" w="20" h="10" ts="A" />'
        '</Layer></G>',
        encoding="utf-8",
    )


def _builtin_config() -> dict[str, object]:
    return {
        "default": {
            "title": "",
            "draw": {"name": "", "date": ""},
            "approve": {"name": "", "date": ""},
            "issue": {"name": "", "date": ""},
        },
        "files": {},
    }


def _add_builtin_frame(source: Path, output: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    template_path = project_root / "resources" / "templates" / "SLD-Drawing-Frame-Template.sln.pic.g"
    process_one_file(
        source,
        output,
        ET.parse(template_path),
        _builtin_config(),
        edit_content=True,
    )


def _pipeline_settings(source: Path, output: Path, work: Path, template_file: Path) -> PipelineSettings:
    return PipelineSettings(
        source_path=source,
        input_mode=InputMode.SINGLE_FILE,
        temp_work_dir=work,
        output_dir=output,
        run_basic=False,
        run_merge=False,
        run_margin=True,
        run_frame=True,
        basic=BasicSettings(source_path=work / "a", output_dir=work / "b"),
        merge=MergeSettings(input_dir=work / "b", output_dir=work / "c"),
        margin=MarginSettings(
            source_path=work / "c",
            output_dir=work / "d",
            output_suffix="",
        ),
        frame=FrameSettings(
            source_path=work / "d",
            output_dir=output,
            template_file=template_file,
            output_suffix="-FINAL",
        ),
    )


def test_single_file_pipeline_skips_merge_and_outputs_directly(tmp_path: Path):
    source = tmp_path / "single.sln.pic.g"
    output = tmp_path / "output"
    output.mkdir()
    work = tmp_path / "hidden-cache"
    _write_g(source)

    settings = PipelineSettings(
        source_path=source,
        input_mode=InputMode.SINGLE_FILE,
        temp_work_dir=work,
        output_dir=output,
        run_basic=False,
        run_merge=True,
        run_margin=False,
        run_frame=False,
        basic=BasicSettings(source_path=work / "a", input_mode=InputMode.DIRECTORY, output_dir=work / "b"),
        merge=MergeSettings(input_dir=work / "b", output_dir=work / "c"),
        margin=MarginSettings(source_path=work / "c", output_dir=work / "d"),
        frame=FrameSettings(
            source_path=work / "d",
            input_mode=InputMode.DIRECTORY,
            output_dir=output,
            template_file=tmp_path / "unused.g",
        ),
    )
    result = run_pipeline(settings, log=lambda _line: None)
    assert result.success
    assert (output / source.name).is_file()
    assert result.warnings
    assert result.statistics["input_mode"] == "single_file"


def test_temp_workspace_is_cleaned_on_startup_and_close(tmp_path: Path):
    service = TempWorkspaceService()
    service.cache_root = tmp_path / "Cache"
    stale = service.cache_root / "old" / "file.tmp"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    service.startup_cleanup()
    assert not stale.exists()
    task = service.reset_task_workspace()
    (task / "middle.g").write_text("x", encoding="utf-8")
    service.cleanup()
    assert not task.exists()


def test_pipeline_preserves_marked_builtin_frame_and_skips_duplicate_frame(tmp_path: Path):
    plain = tmp_path / "plain.sln.pic.g"
    source = tmp_path / "framed.sln.pic.g"
    _write_g(plain)
    _add_builtin_frame(plain, source)

    output = tmp_path / "output"
    output.mkdir()
    work = tmp_path / "cache"
    settings = _pipeline_settings(source, output, work, tmp_path / "not-needed.g")

    result = run_pipeline(settings, log=lambda _line: None)
    targets = list(output.glob("framed-FINAL-*.sln.pic.g"))
    assert len(targets) == 1
    target = targets[0]
    assert target.is_file()
    root = ET.parse(target).getroot()
    layer = next(child for child in root if child.tag == "Layer")
    assert len(layer.findall("line")) == 9
    assert result.statistics["files_with_existing_frame"] == ["framed.sln.pic.g"]


def test_pipeline_rejects_unknown_existing_frame(tmp_path: Path):
    source = tmp_path / "custom-frame.sln.pic.g"
    source.write_text(
        '<G w="1000" width="1000" h="800" height="800"><Layer>'
        '<line id="10" x="50" y="50" w="906" h="6" x1="50" y1="50" x2="950" y2="50" d="50,50 950,50" />'
        '<line id="11" x="950" y="50" w="6" h="706" x1="950" y1="50" x2="950" y2="750" d="950,50 950,750" />'
        '<line id="12" x="50" y="750" w="906" h="6" x1="950" y1="750" x2="50" y2="750" d="950,750 50,750" />'
        '<line id="13" x="50" y="50" w="6" h="706" x1="50" y1="750" x2="50" y2="50" d="50,750 50,50" />'
        '<Text id="1" x="200" y="200" w="100" h="50" ts="BODY" />'
        '</Layer></G>',
        encoding="utf-8",
    )
    output = tmp_path / "output"
    output.mkdir()
    settings = _pipeline_settings(source, output, tmp_path / "cache", tmp_path / "not-needed.g")

    with pytest.raises(UnsupportedExistingFrameError):
        run_pipeline(settings, log=lambda _line: None)
