from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.services.connection_environment_service import ConnectionEnvironmentService
from g_file_studio.services.database_service import OracleConnectionConfig, OracleDatabaseService
from g_file_studio.services.remote_g_source import ReadOnlySshClient
from g_file_studio.services.remote_symbol_library import DEFAULT_REMOTE_SYMBOL_ROOT
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import InfoBanner, WheelSafeComboBox
from g_file_studio.ui.widgets.integer_input import IntegerInput
from g_file_studio.ui.widgets.wheel_safe_line_edit import WheelSafeLineEdit
from g_file_studio.workers import FunctionWorker


_ENV_HELP = """
<h2>连接与环境</h2>
<p>本页集中管理 G File Studio 的公共文件服务器、资源目录和 Oracle 数据库连接。业务页面只选择要处理的数据，不再各自保存账号和连接参数。</p>
<ul>
<li>一个“环境”可表示 Jeddah、Madinah、Makkah、Abha 等现场；切换环境会同步切换公共 SSH、业务 G 根目录、标准图元库目录和 Oracle 连接。</li>
<li>SSH/SFTP 永远严格只读：只允许列目录、读取属性/内容和下载本地副本；程序没有上传、覆盖、删除、重命名、移动、建目录或修改权限的服务器写接口。</li>
<li>Oracle 公共 API 默认只允许 SELECT / WITH 只读查询。</li>
<li>Windows 下 Oracle 密码使用当前用户 DPAPI 加密；SSH 配置保持与历史版本兼容并继续存储在当前用户配置中。</li>
</ul>
"""


class DatabasePage(BasePage):
    """Central connection/environment page.

    Class name is retained for compatibility with older imports and stable page
    indexes.  The visible module now owns both shared SSH/SFTP and Oracle settings.
    """

    environmentChanged = Signal(str)

    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.database_service = OracleDatabaseService(user_settings)
        self.environment_service = ConnectionEnvironmentService(user_settings)
        self._pool = QThreadPool.globalInstance()
        self._worker: FunctionWorker | None = None
        self._ssh_worker: FunctionWorker | None = None
        self._loading_environment = False
        super().__init__(
            "连接与环境",
            "统一管理当前现场的只读文件服务器、业务 G/标准图元目录和 Oracle 数据库；所有业务模块复用这里的全局配置。",
            "连接与环境说明",
            _ENV_HELP,
            parent,
        )

        self.layout.addWidget(
            InfoBanner(
                "这是全局公共配置。切换环境后，异常检测、ID 检查、图元标准检查、图形处理和现场批处理都会复用同一套连接。"
                "服务器访问是硬性只读原则：只允许列目录、读取文件属性/内容和下载到本地；禁止上传、覆盖、删除、重命名、移动、创建文件/目录、chmod/chown 或任何服务器状态修改。"
            )
        )

        env_box = QGroupBox("当前环境")
        env_layout = QVBoxLayout(env_box)
        env_layout.setSpacing(10)
        env_row = QHBoxLayout()
        env_row.addWidget(QLabel("环境"))
        self.environment_selector = WheelSafeComboBox()
        self.environment_selector.setMinimumContentsLength(32)
        env_row.addWidget(self.environment_selector, 1)
        self.environment_name = WheelSafeLineEdit()
        self.environment_name.setPlaceholderText("例如：Jeddah Site / Production")
        self.environment_name.setMinimumHeight(38)
        self.environment_name.setStyleSheet("font-size: 14px;")
        env_row.addWidget(self.environment_name, 1)
        self.new_environment_button = QPushButton("新建 / 复制环境")
        self.delete_environment_button = QPushButton("删除环境")
        self.save_environment_button = QPushButton("保存当前环境")
        env_row.addWidget(self.new_environment_button)
        env_row.addWidget(self.delete_environment_button)
        env_row.addWidget(self.save_environment_button)
        env_layout.addLayout(env_row)
        self.environment_summary = QLabel()
        self.environment_summary.setObjectName("mutedText")
        self.environment_summary.setWordWrap(True)
        env_layout.addWidget(self.environment_summary)
        self.layout.addWidget(env_box)

        ssh_box = QGroupBox("文件服务器（SSH/SFTP · 严格只读）")
        ssh_box.setObjectName("globalSshConnectionBox")
        ssh_layout = QVBoxLayout(ssh_box)
        ssh_layout.setSpacing(14)
        ssh_form = QFormLayout()
        ssh_form.setHorizontalSpacing(24)
        ssh_form.setVerticalSpacing(13)
        ssh_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.ssh_host = WheelSafeLineEdit()
        self.ssh_port = IntegerInput(value=22, minimum=1, maximum=65535)
        self.ssh_username = WheelSafeLineEdit()
        self.ssh_password = WheelSafeLineEdit()
        self.ssh_password.setEchoMode(WheelSafeLineEdit.EchoMode.Password)
        self.business_g_directory = WheelSafeLineEdit()
        self.symbol_library_root = WheelSafeLineEdit()
        self.symbol_library_root.setPlaceholderText(DEFAULT_REMOTE_SYMBOL_ROOT)
        for field in (
            self.ssh_host,
            self.ssh_port,
            self.ssh_username,
            self.ssh_password,
            self.business_g_directory,
            self.symbol_library_root,
        ):
            field.setMinimumHeight(38)
            field.setStyleSheet("font-size: 14px;")

        ssh_form.addRow(self._field_label("IP / 主机"), self.ssh_host)
        ssh_form.addRow(self._field_label("端口"), self.ssh_port)
        ssh_form.addRow(self._field_label("用户名"), self.ssh_username)
        ssh_password_widget = QWidget()
        ssh_password_row = QHBoxLayout(ssh_password_widget)
        ssh_password_row.setContentsMargins(0, 0, 0, 0)
        ssh_password_row.setSpacing(10)
        ssh_password_row.addWidget(self.ssh_password, 1)
        self.show_ssh_password = QPushButton("显示密码")
        self.show_ssh_password.setCheckable(True)
        self.show_ssh_password.setMinimumHeight(38)
        self.show_ssh_password.toggled.connect(self._toggle_ssh_password)
        ssh_password_row.addWidget(self.show_ssh_password)
        ssh_form.addRow(self._field_label("密码"), ssh_password_widget)
        ssh_form.addRow(self._field_label("业务 G 根目录"), self.business_g_directory)
        ssh_form.addRow(self._field_label("标准图元库"), self.symbol_library_root)
        ssh_layout.addLayout(ssh_form)

        ssh_layout.addWidget(
            InfoBanner(
                "服务器严格只读：仅允许测试连接、列目录、读取文件属性/内容和 SFTP GET 下载。"
                "所有扫描、缓存、解析、纠正、替换、报告和批处理输出都只发生在本地 workspace。"
            )
        )
        ssh_actions = QHBoxLayout()
        self.test_ssh_button = QPushButton("测试 SSH 连接")
        self.save_ssh_button = QPushButton("保存文件服务器配置")
        ssh_actions.addWidget(self.test_ssh_button)
        ssh_actions.addWidget(self.save_ssh_button)
        ssh_actions.addStretch(1)
        ssh_layout.addLayout(ssh_actions)
        self.ssh_status = QLabel("尚未验证")
        self._set_inline_status(self.ssh_status, "尚未验证", "idle")
        ssh_layout.addWidget(self.ssh_status)
        self.layout.addWidget(ssh_box)

        db_box = QGroupBox("Oracle 数据库连接")
        db_box.setObjectName("databaseConnectionBox")
        db_box.setStyleSheet("QGroupBox#databaseConnectionBox { font-size: 14px; }")
        db_layout = QVBoxLayout(db_box)
        db_layout.setSpacing(14)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(13)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        # 数据库连接属于关键配置：所有可编辑字段显式使用防滚轮控件。
        self.username = WheelSafeLineEdit()
        self.username.setPlaceholderText("Oracle 用户名")
        self.password = WheelSafeLineEdit()
        self.password.setEchoMode(WheelSafeLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("请输入数据库密码")
        self.host = WheelSafeLineEdit()
        self.host.setPlaceholderText("服务器主机名或 IP")
        self.port = IntegerInput(value=1521, minimum=1, maximum=65535)
        self.service_name = WheelSafeLineEdit()
        self.service_name.setPlaceholderText("Oracle Service Name")
        for field in (self.username, self.password, self.host, self.port, self.service_name):
            field.setProperty("databaseField", True)
            field.setMinimumHeight(38)
            field.setStyleSheet("font-size: 14px;")

        form.addRow(self._field_label("用户名"), self.username)
        password_widget = QWidget()
        password_row = QHBoxLayout(password_widget)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(10)
        password_row.addWidget(self.password, 1)
        self.show_password = QPushButton("显示密码")
        self.show_password.setCheckable(True)
        self.show_password.setMinimumHeight(38)
        self.show_password.toggled.connect(self._toggle_password)
        password_row.addWidget(self.show_password)
        form.addRow(self._field_label("密码"), password_widget)
        form.addRow(self._field_label("服务器地址"), self.host)
        form.addRow(self._field_label("端口"), self.port)
        form.addRow(self._field_label("Service Name"), self.service_name)
        db_layout.addLayout(form)

        self.endpoint = QLabel()
        self.endpoint.setObjectName("mutedText")
        self.endpoint.setWordWrap(True)
        db_layout.addWidget(self.endpoint)
        db_layout.addWidget(
            InfoBanner(
                "数据库访问默认只读：连接测试只执行 SELECT 查询；后续业务模块统一复用本公共配置。"
                "除非未来具体功能由用户明确设计并授权，否则公共数据库 API 不执行 INSERT / UPDATE / DELETE。"
            )
        )
        db_actions = QHBoxLayout()
        self.test_button = QPushButton("测试数据库连接")
        self.save_button = QPushButton("保存数据库配置")
        db_actions.addWidget(self.test_button)
        db_actions.addWidget(self.save_button)
        db_actions.addStretch(1)
        db_layout.addLayout(db_actions)
        self.status = QLabel("尚未验证")
        self.status.setObjectName("databaseStatus")
        self._set_status("尚未验证", "idle")
        db_layout.addWidget(self.status)
        self.layout.addWidget(db_box)

        log_box = QGroupBox("连接运行日志")
        log_layout = QVBoxLayout(log_box)
        log_buttons = QHBoxLayout()
        self.copy_log_button = QPushButton("复制日志")
        self.clear_log_button = QPushButton("清空日志")
        log_buttons.addWidget(self.copy_log_button)
        log_buttons.addWidget(self.clear_log_button)
        log_buttons.addStretch(1)
        log_layout.addLayout(log_buttons)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        self.log.setPlaceholderText("文件服务器和数据库连接测试日志会显示在这里。")
        log_layout.addWidget(self.log, 1)
        self.layout.addWidget(log_box, 1)

        self.environment_selector.currentIndexChanged.connect(self._environment_selected)
        self.new_environment_button.clicked.connect(self._create_environment)
        self.delete_environment_button.clicked.connect(self._delete_environment)
        self.save_environment_button.clicked.connect(lambda: self._save_environment(show_message=True))
        self.test_ssh_button.clicked.connect(self._test_ssh_connection)
        self.save_ssh_button.clicked.connect(self._save_file_server_config)
        self.test_button.clicked.connect(self._test_connection)
        self.save_button.clicked.connect(self._save_database_config)
        self.copy_log_button.clicked.connect(self._copy_log)
        self.clear_log_button.clicked.connect(self._clear_log)
        for field in (self.username, self.password, self.host, self.port, self.service_name):
            if hasattr(field, "textChanged"):
                field.textChanged.connect(self._update_endpoint)  # type: ignore[attr-defined]
            elif hasattr(field, "valueChanged"):
                field.valueChanged.connect(self._update_endpoint)  # type: ignore[attr-defined]

        self._reload_environment_selector()
        self._load_active_environment()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("databaseFieldLabel")
        label.setMinimumWidth(112)
        label.setStyleSheet("color:#28474e; font-size:14px; font-weight:650; padding-right:6px;")
        return label

    def _reload_environment_selector(self) -> None:
        active_uid = self.environment_service.active_uid()
        self.environment_selector.blockSignals(True)
        self.environment_selector.clear()
        target = 0
        for index, profile in enumerate(self.environment_service.profiles()):
            self.environment_selector.addItem(profile.name, profile.uid)
            if profile.uid == active_uid:
                target = index
        self.environment_selector.setCurrentIndex(target)
        self.environment_selector.blockSignals(False)

    def _load_active_environment(self) -> None:
        self._loading_environment = True
        profile = self.environment_service.active()
        self.environment_name.setText(profile.name)
        self.ssh_host.setText(profile.ssh_host)
        self.ssh_port.setValue(profile.ssh_port)
        self.ssh_username.setText(profile.ssh_username)
        self.ssh_password.setText(profile.ssh_password)
        self.business_g_directory.setText(profile.business_g_directory)
        self.symbol_library_root.setText(profile.symbol_library_root)
        db = self.database_service.load_config()
        self.username.setText(db.username)
        self.password.setText(db.password)
        self.host.setText(db.host)
        self.port.setValue(db.port)
        self.service_name.setText(db.service_name)
        self._update_endpoint()
        self._update_environment_summary()
        self._loading_environment = False

    def _environment_selected(self, _index: int) -> None:
        if self._loading_environment:
            return
        uid = str(self.environment_selector.currentData() or "")
        if not uid:
            return
        try:
            profile = self.environment_service.activate(uid)
        except Exception as exc:
            QMessageBox.warning(self, "切换环境失败", str(exc))
            return
        self._load_active_environment()
        self._append_log(f"已切换连接环境：{profile.name}")
        self.environmentChanged.emit(profile.uid)

    def _create_environment(self) -> None:
        suggested = f"{self.environment_name.text().strip() or 'Site'} Copy"
        name, ok = QInputDialog.getText(self, "新建 / 复制环境", "新环境名称", text=suggested)
        if not ok or not name.strip():
            return
        self._save_environment(show_message=False)
        profile = self.environment_service.create_copy(name.strip())
        self._reload_environment_selector()
        self._load_active_environment()
        self._append_log(f"已从当前配置创建环境：{profile.name}")
        self.environmentChanged.emit(profile.uid)

    def _delete_environment(self) -> None:
        active = self.environment_service.active()
        reply = QMessageBox.question(self, "删除环境", f"确定删除连接环境“{active.name}”吗？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            profile = self.environment_service.delete(active.uid)
        except Exception as exc:
            QMessageBox.warning(self, "无法删除环境", str(exc))
            return
        self._reload_environment_selector()
        self._load_active_environment()
        self._append_log(f"已删除环境并切换到：{profile.name}")
        self.environmentChanged.emit(profile.uid)

    def _persist_ssh_shared(self) -> None:
        host = self.ssh_host.text().strip()
        username = self.ssh_username.text().strip()
        business_dir = self.business_g_directory.text().strip()
        symbol_root = self.symbol_library_root.text().strip() or DEFAULT_REMOTE_SYMBOL_ROOT
        if not host:
            raise ValueError("SSH IP/主机不能为空。")
        if not username:
            raise ValueError("SSH 用户名不能为空。")
        if not business_dir:
            raise ValueError("业务 G 根目录不能为空。")
        self.user_settings.set_value("remote_g_source/host", host)
        self.user_settings.set_value("remote_g_source/port", self.ssh_port.value())
        self.user_settings.set_value("remote_g_source/username", username)
        self.user_settings.set_value("remote_g_source/password", self.ssh_password.text())
        self.user_settings.set_value("remote_g_source/remote_directory", business_dir)
        self.user_settings.set_value("site_profile/remote_symbol_library_root", symbol_root)

    def _save_file_server_config(self) -> None:
        try:
            self._persist_ssh_shared()
            profile = self.environment_service.save_active_from_shared(name=self.environment_name.text().strip())
        except Exception as exc:
            QMessageBox.warning(self, "保存文件服务器配置失败", str(exc))
            return
        self._reload_environment_selector()
        self._update_environment_summary()
        self._set_inline_status(self.ssh_status, "配置已保存 · 尚未验证", "idle")
        self._append_log(f"文件服务器配置已保存到环境：{profile.name}")
        self.environmentChanged.emit(profile.uid)

    def _save_environment(self, *, show_message: bool) -> None:
        try:
            self._persist_ssh_shared()
            # Save Oracle only when a password is currently available. This keeps
            # the existing DPAPI policy; on non-Windows the service never persists it.
            config = self._config_from_form()
            config.validate()
            self.database_service.save_config(config)
            profile = self.environment_service.save_active_from_shared(name=self.environment_name.text().strip())
        except Exception as exc:
            if show_message:
                QMessageBox.warning(self, "保存环境失败", str(exc))
            return
        self._reload_environment_selector()
        self._update_environment_summary()
        self._append_log(f"连接环境已保存：{profile.name}")
        self.environmentChanged.emit(profile.uid)
        if show_message:
            self._set_inline_status(self.ssh_status, "配置已保存 · 尚未验证", "idle")
            self._set_status("配置已保存 · 尚未验证", "idle")

    def _update_environment_summary(self) -> None:
        name = self.environment_name.text().strip() or "-"
        self.environment_summary.setText(
            f"{name}  ·  SSH {self.ssh_host.text().strip() or '-'}:{self.ssh_port.value()}  ·  "
            f"Business G {self.business_g_directory.text().strip() or '-'}  ·  "
            f"Symbol Library {self.symbol_library_root.text().strip() or '-'}  ·  "
            f"Oracle {self.host.text().strip() or '-'}:{self.port.value()}/{self.service_name.text().strip() or '-'}"
        )

    def _toggle_ssh_password(self, checked: bool) -> None:
        self.ssh_password.setEchoMode(WheelSafeLineEdit.EchoMode.Normal if checked else WheelSafeLineEdit.EchoMode.Password)
        self.show_ssh_password.setText("隐藏密码" if checked else "显示密码")

    def _test_ssh_connection(self) -> None:
        if self._ssh_worker is not None:
            return
        try:
            self._persist_ssh_shared()
            host = self.ssh_host.text().strip()
            port = self.ssh_port.value()
            username = self.ssh_username.text().strip()
            password = self.ssh_password.text()
        except Exception as exc:
            QMessageBox.warning(self, "文件服务器配置不完整", str(exc))
            return
        self.test_ssh_button.setEnabled(False)
        self._set_inline_status(self.ssh_status, "正在连接…", "testing")
        self._append_log(f"开始测试只读 SSH/SFTP：{username}@{host}:{port}")

        def task(*, log, progress):
            del log
            progress(20)
            with ReadOnlySshClient(host, port, username, password) as client:
                client.test_connection()
            progress(100)
            return True

        worker = FunctionWorker(task)
        self._ssh_worker = worker
        worker.signals.result.connect(lambda _result: self._ssh_ok())
        worker.signals.error.connect(self._ssh_error)
        worker.signals.finished.connect(self._ssh_finished)
        self._pool.start(worker)

    def _ssh_ok(self) -> None:
        self._set_inline_status(self.ssh_status, "连接成功 · 服务器只读", "ok")
        self._append_log("SSH/SFTP 连接成功；只读策略保持有效。")

    def _ssh_error(self, details: str) -> None:
        message = str(details).split("\n\n---TRACEBACK---", 1)[0].strip()
        self._set_inline_status(self.ssh_status, f"连接失败 · {message}", "error")
        self._append_log(f"SSH/SFTP 连接失败：{message}")

    def _ssh_finished(self) -> None:
        self._ssh_worker = None
        self.test_ssh_button.setEnabled(True)

    def _config_from_form(self) -> OracleConnectionConfig:
        return OracleConnectionConfig(
            username=self.username.text().strip(),
            password=self.password.text(),
            host=self.host.text().strip(),
            port=self.port.value(),
            service_name=self.service_name.text().strip(),
        )

    def _update_endpoint(self, *_args) -> None:
        config = self._config_from_form()
        self.endpoint.setText(f"当前连接：{config.username or '-'} @ {config.host or '-'}:{config.port}/{config.service_name or '-'}")
        if not self._loading_environment:
            self._update_environment_summary()

    def _toggle_password(self, checked: bool) -> None:
        self.password.setEchoMode(WheelSafeLineEdit.EchoMode.Normal if checked else WheelSafeLineEdit.EchoMode.Password)
        self.show_password.setText("隐藏密码" if checked else "显示密码")

    @staticmethod
    def _status_style(state: str) -> str:
        styles = {
            "idle": "background:#f6f8f7;border:1px solid #d2ddda;color:#687c82;",
            "testing": "background:#eef5f4;border:1px solid #b7cfcb;color:#46696d;",
            "ok": "background:#e3f5ed;border:1px solid #98d1bc;color:#087250;",
            "warning": "background:#fff7e7;border:1px solid #e6c675;color:#8a6200;",
            "error": "background:#fff0ee;border:1px solid #efb8af;color:#b2382b;",
        }
        return "QLabel { border-radius:7px; padding:8px 12px; font-weight:700; " + styles.get(state, styles["idle"]) + " }"

    def _set_inline_status(self, label: QLabel, text: str, state: str) -> None:
        label.setText(text)
        label.setStyleSheet(self._status_style(state))

    def _set_status(self, text: str, state: str) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(self._status_style(state))

    def _append_log(self, text: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.appendPlainText(f"[{stamp}] {text}")

    def _save_database_config(self) -> None:
        try:
            config = self._config_from_form()
            secure_password = self.database_service.save_config(config)
            self._persist_ssh_shared()
            profile = self.environment_service.save_active_from_shared(name=self.environment_name.text().strip())
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._reload_environment_selector()
        self._update_environment_summary()
        if secure_password:
            self._append_log("数据库配置已保存；密码已使用 Windows 当前用户 DPAPI 加密。")
            self._set_status("配置已保存 · 尚未验证", "idle")
        else:
            self._append_log("数据库配置已保存；当前系统不支持 Windows DPAPI，因此未持久化密码。")
            self._set_status("配置已保存 · 密码未持久化 · 尚未验证", "warning")
        self.environmentChanged.emit(profile.uid)

    # Backward-compatible method name used by older tests/callers.
    def _save_config(self) -> None:
        self._save_database_config()

    def _test_connection(self) -> None:
        if self._worker is not None:
            return
        try:
            config = self._config_from_form()
            config.validate()
        except Exception as exc:
            QMessageBox.warning(self, "数据库配置不完整", str(exc))
            return
        self.test_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self._set_status("正在连接…", "testing")
        self._append_log(f"开始测试 Oracle 连接：{config.username} @ {config.dsn}")

        def task(*, log, progress):
            del log
            progress(20)
            result = self.database_service.test_connection(config)
            progress(100)
            return result

        worker = FunctionWorker(task)
        self._worker = worker
        worker.signals.result.connect(self._connection_ok)
        worker.signals.error.connect(self._connection_error)
        worker.signals.finished.connect(self._connection_finished)
        self._pool.start(worker)

    def _connection_ok(self, result: object) -> None:
        info = result if isinstance(result, dict) else {}
        database = str(info.get("database", "") or "-")
        service = str(info.get("service", "") or self.service_name.text().strip())
        username = str(info.get("username", "") or self.username.text().strip())
        self._set_status(f"连接成功 · {username} · {database} · {service}", "ok")
        self._append_log(f"连接成功：USER={username}, DB={database}, SERVICE={service}")

    def _connection_error(self, details: str) -> None:
        message = str(details).split("\n\n---TRACEBACK---", 1)[0].strip()
        self._set_status(f"连接失败 · {message}", "error")
        self._append_log(f"连接失败：{message}")

    def _connection_finished(self) -> None:
        self._worker = None
        self.test_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def _copy_log(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.log.toPlainText())

    def _clear_log(self) -> None:
        self.log.clear()

    def on_page_activated(self) -> None:
        # Other modules use the same shared keys. Re-read the active profile whenever
        # this page becomes visible so the summary never displays stale values.
        self._reload_environment_selector()
        self._load_active_environment()
