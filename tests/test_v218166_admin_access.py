from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from g_file_studio.services.admin_access_service import AdminAccessService
from g_file_studio.services.user_settings_service import UserSettingsService


def test_first_deployment_has_no_admin_and_plaintext_is_never_persisted(tmp_path: Path) -> None:
    settings_path = tmp_path / "user_settings.ini"
    service = AdminAccessService(UserSettingsService(settings_path))

    assert service.is_initialized() is False
    with pytest.raises(ValueError):
        service.set_password("123")

    password = "admin-166"
    service.set_password(password)
    assert service.is_initialized() is True
    assert service.verify_password(password) is True
    assert service.verify_password("wrong-password") is False
    assert password not in settings_path.read_text(encoding="utf-8")

    # A new process/service instance must be able to verify the saved hash.
    restored = AdminAccessService(UserSettingsService(settings_path))
    assert restored.is_initialized() is True
    assert restored.verify_password(password) is True


def test_corrupt_admin_verifier_is_treated_as_uninitialized(tmp_path: Path) -> None:
    settings = UserSettingsService(tmp_path / "broken.ini")
    settings.set_value("access_control/admin_password_salt", "not-hex")
    settings.set_value("access_control/admin_password_hash", "also-not-hex")
    settings.set_value("access_control/admin_password_iterations", 310000)
    service = AdminAccessService(settings)
    assert service.is_initialized() is False
    assert service.verify_password("anything") is False


def test_access_mode_source_keeps_admin_for_central_publish_only() -> None:
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'self._is_admin_mode = False' in source
    assert 'self.access_mode_button.setText("抢占 Admin 权限")' in source
    assert 'self.access_mode_button.setText("释放管理员权限")' in source
    # Ordinary workstations may maintain their own local classification copy.
    assert 'if not self._require_admin_mode("保存到本地")' not in source
    assert 'if not self._require_admin_mode("导入本地 JSON")' not in source
    assert 'item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)' in source
    # Only central publication requires Admin.
    assert 'if not self._require_admin_mode("上传到服务器")' in source


def test_release_version_is_consistent() -> None:
    package_version = (
        Path("g_file_studio/__init__.py")
        .read_text(encoding="utf-8")
        .split('"', 2)[1]
    )
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert package_version.count(".") == 2
    assert pyproject["project"]["version"] == package_version
