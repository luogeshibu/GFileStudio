from pathlib import Path

from g_file_studio.services.connection_environment_service import ConnectionEnvironmentService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_connection_environment_bootstraps_from_existing_shared_settings(tmp_path):
    settings = UserSettingsService(tmp_path / "settings.ini")
    settings.set_value("remote_g_source/host", "10.20.30.40")
    settings.set_value("remote_g_source/port", "2222")
    settings.set_value("remote_g_source/username", "reader")
    settings.set_value("remote_g_source/password", "pw")
    settings.set_value("remote_g_source/remote_directory", "/srv/g")
    settings.set_value("site_profile/remote_symbol_library_root", "/srv/element")
    settings.set_value("database/oracle_config_saved", "true")
    settings.set_value("database/oracle_username", "dbuser")
    settings.set_value("database/oracle_host", "10.20.30.41")
    settings.set_value("database/oracle_port", "1523")
    settings.set_value("database/oracle_service", "svc")

    service = ConnectionEnvironmentService(settings)
    profile = service.active()
    assert profile.ssh_host == "10.20.30.40"
    assert profile.ssh_port == 2222
    assert profile.business_g_directory == "/srv/g"
    assert profile.symbol_library_root == "/srv/element"
    assert profile.oracle_host == "10.20.30.41"
    assert profile.oracle_port == 1523
    assert profile.oracle_service == "svc"


def test_switching_environment_projects_into_legacy_shared_keys(tmp_path):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = ConnectionEnvironmentService(settings)
    settings.set_value("remote_g_source/host", "192.0.2.10")
    settings.set_value("remote_g_source/remote_directory", "/jeddah/sln")
    settings.set_value("site_profile/remote_symbol_library_root", "/jeddah/element")
    service.save_active_from_shared(name="Jeddah")
    copied = service.create_copy("Madinah")

    settings.set_value("remote_g_source/host", "192.0.2.20")
    settings.set_value("remote_g_source/remote_directory", "/madinah/sln")
    settings.set_value("site_profile/remote_symbol_library_root", "/madinah/element")
    service.save_active_from_shared(name="Madinah")

    jeddah = next(item for item in service.profiles() if item.name == "Jeddah")
    service.activate(jeddah.uid)
    assert settings.get_value("remote_g_source/host") == "192.0.2.10"
    assert settings.get_value("remote_g_source/remote_directory") == "/jeddah/sln"
    assert settings.get_value("site_profile/remote_symbol_library_root") == "/jeddah/element"
    assert copied.uid != jeddah.uid


def test_global_connection_ui_replaces_database_nav_and_business_credential_forms():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    db_page = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    remote_widget = Path("g_file_studio/ui/widgets/remote_g_source.py").read_text(encoding="utf-8")
    symbol_page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")

    assert 'self.connection_button = QPushButton("连接与环境")' in main
    assert '("数据库",' not in main
    assert '"连接与环境"' in db_page
    assert '"文件服务器（SSH/SFTP · 严格只读）"' in db_page
    assert '"Oracle 数据库连接"' in db_page
    assert 'self.connection_settings_button = QPushButton("连接设置")' in remote_widget
    assert 'editor.setVisible(False)' in remote_widget
    assert 'self.server_symbol_root.setReadOnly(True)' in symbol_page
    assert 'self.server_connection_button = QPushButton("连接设置")' in symbol_page


def test_server_write_surface_remains_forbidden():
    source = Path("g_file_studio/services/remote_g_source.py").read_text(encoding="utf-8")
    assert "self._sftp.get(" in source
    for forbidden in ("self._sftp.put(", "self._sftp.remove(", "self._sftp.rename(", "self._sftp.mkdir("):
        assert forbidden not in source
