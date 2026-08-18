from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import g_file_studio.services.run_history as rh


def test_run_directory_and_status(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(rh, "default_workspace", lambda: tmp_path / "workspace")
    run_dir = rh.create_run_directory("merge", "merge")
    assert run_dir.is_dir()
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert meta["module_key"] == "merge"
    assert meta["status"] == "RUNNING"
    rh.update_run_status(run_dir, "SUCCESS")
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert meta["status"] == "SUCCESS"
    assert meta["finished_at"]


def test_cleanup_removes_only_older_than_30_days(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(rh, "default_workspace", lambda: tmp_path / "workspace")
    old_dir = rh.module_runs_root("id") / "old"
    new_dir = rh.module_runs_root("id") / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_ts = (datetime.now() - timedelta(days=31)).timestamp()
    os.utime(old_dir, (old_ts, old_ts))
    removed = rh.cleanup_expired_runs(30)
    assert removed == 1
    assert not old_dir.exists()
    assert new_dir.exists()
