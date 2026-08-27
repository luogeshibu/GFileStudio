from __future__ import annotations

import hashlib
import json
from pathlib import Path


def test_original_non_i18n_files_match_v21760_golden_baseline():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "config/golden_v21760_logic_sha256.json").read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in data["protected_files"].items():
        path = root / relative
        if not path.is_file():
            mismatches.append(f"missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            mismatches.append(relative)
    assert not mismatches, "Golden baseline logic changed: " + ", ".join(mismatches)


def test_approved_ui_exceptions_are_exactly_locked():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "config/golden_v21760_logic_sha256.json").read_text(encoding="utf-8"))
    exceptions = data.get("approved_ui_exceptions", {})
    assert set(exceptions) == {"g_file_studio/ui/widgets/remote_g_source.py"}
    for relative, meta in exceptions.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert actual == meta["release_sha256"], f"Approved UI exception changed unexpectedly: {relative}"


def test_user_approved_rmu_feature_exceptions_are_exactly_locked():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "config/golden_v21760_logic_sha256.json").read_text(encoding="utf-8"))
    exceptions = data.get("approved_feature_exceptions", {})
    expected = {
        "g_file_studio/engines/rmu_identification_engine.py",
        "g_file_studio/engines/icon_upgrade_engine.py",
        "g_file_studio/models.py",
        "g_file_studio/processors/basic_processor.py",
        "g_file_studio/ui/pages/basic_page.py",
        "g_file_studio/ui/pages/rmu_page.py",
        "g_file_studio/ui/widgets/icon_upgrade_editor.py",
    }
    assert set(exceptions) == expected
    for relative, meta in exceptions.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert actual == meta["release_sha256"], f"Approved RMU feature exception changed unexpectedly: {relative}"


def test_user_approved_report_i18n_exceptions_are_exactly_locked():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "config/golden_v21760_logic_sha256.json").read_text(encoding="utf-8"))
    exceptions = data.get("approved_report_exceptions", {})
    expected = {
        "g_file_studio/processors/id_processor.py",
        "g_file_studio/engines/small_element_engine.py",
        "g_file_studio/services/rmu_ledger_service.py",
        "g_file_studio/services/html_report_selection.py",
    }
    assert set(exceptions) == expected
    for relative, meta in exceptions.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert actual == meta["release_sha256"], f"Approved report i18n exception changed unexpectedly: {relative}"
