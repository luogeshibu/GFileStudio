from pathlib import Path


def test_history_page_removed_in_v21751():
    assert not Path('g_file_studio/ui/pages/history_page.py').exists()
