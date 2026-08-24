from pathlib import Path


def test_main_bus_dialog_uses_identity_safe_presentation_bridge_only():
    merge_source = Path("g_file_studio/ui/pages/merge_page.py").read_text(encoding="utf-8")
    i18n_source = Path("g_file_studio/i18n.py").read_text(encoding="utf-8")

    # Original v2.17.60 selection logic remains in the feature page.
    assert 'single_button = dialog.addButton("单母线", QMessageBox.ButtonRole.AcceptRole)' in merge_source
    assert 'double_button = dialog.addButton("双母线", QMessageBox.ButtonRole.AcceptRole)' in merge_source
    assert 'if clicked is double_button:' in merge_source
    assert 'elif clicked is single_button:' in merge_source

    # English captions are injected before QMessageBox creates the custom buttons,
    # so clickedButton() identity/roles are not touched after the modal dialog starts.
    assert "def _install_qmessagebox_button_i18n_bridge()" in i18n_source
    assert "QMessageBox.addButton = translated_add_button" in i18n_source
    assert "QMessageBox.clickedButton = exact_clicked_button" in i18n_source
    assert '_i18n_exact_clicked_button' in i18n_source
    assert '_i18n_exact_button_refs' in i18n_source
    assert '_i18n_custom_buttons_pretranslated' in i18n_source
    assert '"单母线": "Single Bus"' in i18n_source
    assert '"双母线": "Double Bus"' in i18n_source
    assert 'Single Bus: check only the highest valid horizontal <Bus>' in i18n_source
