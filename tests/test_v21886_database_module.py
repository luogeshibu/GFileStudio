from pathlib import Path

import pytest

from g_file_studio.services.database_service import OracleConnectionConfig, OracleDatabaseService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_database_defaults_and_dsn(tmp_path):
    service = OracleDatabaseService(UserSettingsService(tmp_path / "settings.ini"))
    config = service.load_config()
    assert config.username == "d5000"
    assert config.host == "172.16.21.45"
    assert config.port == 1521
    assert config.service_name == "jedup8000"
    assert config.password == "OracleDV1Dec.25"
    assert config.dsn == "172.16.21.45:1521/jedup8000"


def test_factory_password_is_prefilled_and_user_password_is_dpapi_persisted():
    text = Path("g_file_studio/services/database_service.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert '_DEFAULT_PASSWORD = "OracleDV1Dec.25"' in text
    assert 'password=self.password.text()' in page
    assert 'oracle_password_dpapi' in text
    assert 'oracle_config_saved' in text

def test_public_database_api_is_read_only():
    assert OracleDatabaseService.validate_read_only_sql("select 1 from dual") == "select 1 from dual"
    assert OracleDatabaseService.validate_read_only_sql("WITH x AS (SELECT 1 a FROM dual) SELECT * FROM x")
    for sql in (
        "insert into t values (1)",
        "update t set a=1",
        "delete from t",
        "merge into t using x on (1=1) when matched then update set a=1",
        "begin null; end;",
    ):
        with pytest.raises(PermissionError):
            OracleDatabaseService.validate_read_only_sql(sql)


def test_database_page_is_public_module_and_oracle_dependency_is_packaged():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "DatabasePage(self.user_settings)" in main
    assert '("数据库",' in main
    assert "测试数据库连接" in page
    assert "保存数据库配置" in page
    assert "oracledb" in req


def test_symbol_standard_scope_remains_isolated():
    main = Path("g_file_studio/ui/main_window.py").read_text(encoding="utf-8")
    db_service = Path("g_file_studio/services/database_service.py").read_text(encoding="utf-8")
    db_page = Path("g_file_studio/ui/pages/database_page.py").read_text(encoding="utf-8")
    assert "smart_profile_engine" not in db_service
    assert "smart_profile_engine" not in db_page
    assert "site_profile_page.activeProfileChanged.connect(self.jeddah_batch_page.refresh_profiles)" in main


def test_release_version_21888():
    assert '__version__ = "2.18.97"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.97"' in Path("pyproject.toml").read_text(encoding="utf-8")
