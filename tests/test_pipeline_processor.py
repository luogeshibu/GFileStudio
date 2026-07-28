from pathlib import Path

from g_file_studio.models import (
    BasicSettings,
    FrameSettings,
    MergeSettings,
    InputMode,
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


def test_single_file_pipeline_skips_merge_and_outputs_directly(tmp_path: Path):
    source = tmp_path / "single.sln.pic.g"
    output = tmp_path / "output"
    work = tmp_path / "hidden-cache"
    _write_g(source)

    settings = PipelineSettings(
        source_path=source,
        input_mode=InputMode.SINGLE_FILE,
        temp_work_dir=work,
        output_dir=output,
        run_basic=False,
        run_merge=True,
        run_frame=False,
        basic=BasicSettings(source_path=work / "a", input_mode=InputMode.DIRECTORY, output_dir=work / "b"),
        merge=MergeSettings(input_dir=work / "b", output_dir=work / "c"),
        frame=FrameSettings(
            source_path=work / "c",
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
