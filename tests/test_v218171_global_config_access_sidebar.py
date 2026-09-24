from __future__ import annotations

import re
from pathlib import Path


def test_version_is_consistent() -> None:
    init_text = Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert match is not None
    version = re.escape(match.group(1))
    assert re.search(rf'^version\s*=\s*"{version}"$', pyproject, re.M)


def test_global_config_access_entry_is_in_persistent_sidebar() -> None:
    source = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    assert 'self.config_access_button = QPushButton("配置权限：普通客户端")' in source
    assert 'self.site_profile_page.adminAccessChanged.connect(self._update_global_admin_access)' in source
    assert 'self.config_access_button.clicked.connect(self._show_global_admin_access)' in source
    assert 'side_layout.addWidget(self.config_access_button)' in source
    assert source.index('side_layout.addWidget(self.config_access_button)') < source.index('side_layout.addWidget(self.nav, 1)')
    page = Path('g_file_studio/ui/pages/site_profile_page.py').read_text(encoding='utf-8')
    assert '配置权限：管理员模式' in page
    assert '配置权限：普通客户端' in page


def test_symbol_sync_page_no_longer_shows_admin_row() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'adminAccessChanged = Signal(object)' in source
    assert 'def admin_access_state(self)' in source
    assert 'standard_layout.addLayout(access_row)' not in source
    assert 'self._legacy_access_container.setVisible(False)' in source
    assert 'self.adminAccessChanged.emit(self.admin_access_state())' in source


def test_connection_page_points_admin_to_global_sidebar() -> None:
    source = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert '请通过左侧“配置权限”申请管理员权限。' in source
    assert '请先在“服务器图元同步管理”申请管理员权限。' not in source
