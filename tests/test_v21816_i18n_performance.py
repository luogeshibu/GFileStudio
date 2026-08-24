from pathlib import Path


def test_no_periodic_full_window_i18n_rescan():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert "_i18n_refresh_timer" not in main
    assert "setInterval(300)" not in main


def test_runtime_i18n_is_event_driven_for_tables_and_dialogs():
    i18n = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")
    assert "model.dataChanged.connect(translate_range)" in i18n
    assert "Never rescan a whole table from Paint" in i18n
    assert "watched.isWindow()" in i18n
