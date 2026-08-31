from pathlib import Path

from g_file_studio.services.database_service import OracleConnectionConfig, OracleDatabaseService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_first_run_uses_factory_database_defaults(tmp_path):
    service = OracleDatabaseService(UserSettingsService(tmp_path / "settings.ini"))
    config = service.load_config()
    assert config.username == "d5000"
    assert config.password == "OracleDV1Dec.25"
    assert config.host == "172.16.21.45"
    assert config.port == 1521
    assert config.service_name == "jedup8000"
    assert config.dsn == "172.16.21.45:1521/jedup8000"


def test_saved_user_config_overrides_factory_defaults(tmp_path, monkeypatch):
    settings = UserSettingsService(tmp_path / "settings.ini")
    service = OracleDatabaseService(settings)

    # Simulate an existing user configuration without depending on Windows DPAPI.
    settings.set_value("database/oracle_config_saved", "true")
    settings.set_value("database/oracle_username", "custom_user")
    settings.set_value("database/oracle_host", "10.0.0.88")
    settings.set_value("database/oracle_port", 1522)
    settings.set_value("database/oracle_service", "customsvc")

    config = service.load_config()
    assert config.username == "custom_user"
    assert config.host == "10.0.0.88"
    assert config.port == 1522
    assert config.service_name == "customsvc"
    # A saved user profile never silently falls back to the factory password.
    assert config.password == ""


def test_legacy_saved_fields_are_treated_as_user_config(tmp_path):
    settings = UserSettingsService(tmp_path / "settings.ini")
    settings.set_value("database/oracle_host", "10.1.2.3")
    service = OracleDatabaseService(settings)
    config = service.load_config()
    assert config.host == "10.1.2.3"
    assert config.password == ""


def test_release_version_21888():
    assert '__version__ = "2.18.97"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.97"' in Path("pyproject.toml").read_text(encoding="utf-8")
