from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from g_file_studio.services.database_service import OracleConnectionConfig, OracleDatabaseService
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.pages.base_page import BasePage
from g_file_studio.ui.widgets import InfoBanner
from g_file_studio.workers import FunctionWorker


_DB_HELP = """
<h2>Oracle 数据库连接</h2>
<p>本页是 G File Studio 的公共数据库入口。后续需要数据库的业务模块应复用这里的配置和数据库服务，不再各自维护账号、地址或连接逻辑。</p>
<ul>
<li>使用 python-oracledb Thin 模式，不要求本机安装 Oracle Client。</li>
<li>“测试数据库连接”仅执行 SELECT 1 FROM DUAL 和环境信息查询，不修改任何业务表。</li>
<li>当前公共数据库 API 默认只允许 SELECT / WITH 查询；写数据库能力必须在具体业务模块中另行明确设计和授权。</li>
<li>首次运行使用项目预置的吉达 Oracle 默认连接参数；用户保存过配置后，后续启动始终优先加载用户配置。</li>
<li>用户修改后的密码在 Windows 下使用当前用户 DPAPI 加密保存，不以明文写入 user_settings.ini。</li>
</ul>
"""


class DatabasePage(BasePage):
    def __init__(self, user_settings: UserSettingsService, parent=None) -> None:
        self.user_settings = user_settings
        self.database_service = OracleDatabaseService(user_settings)
        self._pool = QThreadPool.globalInstance()
        self._worker: FunctionWorker | None = None
        super().__init__(
            "数据库",
            "Oracle 数据库作为独立公共模块；后续需要数据库的功能统一复用这里的连接配置。",
            "数据库连接说明",
            _DB_HELP,
            parent,
        )

        box = QGroupBox("Oracle 数据库连接")
        box_layout = QVBoxLayout(box)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Oracle 用户名")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("请输入数据库密码")
        self.host = QLineEdit()
        self.host.setPlaceholderText("服务器主机名或 IP")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.service_name = QLineEdit()
        self.service_name.setPlaceholderText("Oracle Service Name")

        form.addRow("用户名", self.username)
        password_row = QHBoxLayout()
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.addWidget(self.password, 1)
        self.show_password = QPushButton("显示密码")
        self.show_password.setCheckable(True)
        self.show_password.setMaximumWidth(96)
        self.show_password.toggled.connect(self._toggle_password)
        password_row.addWidget(self.show_password)
        form.addRow("密码", password_row)
        form.addRow("服务器地址", self.host)
        form.addRow("端口", self.port)
        form.addRow("Service Name", self.service_name)
        box_layout.addLayout(form)

        self.endpoint = QLabel()
        self.endpoint.setObjectName("mutedText")
        self.endpoint.setWordWrap(True)
        box_layout.addWidget(self.endpoint)

        box_layout.addWidget(
            InfoBanner(
                "数据库访问默认只读：本页连接测试只执行 SELECT 查询。后续模块如需数据库，统一复用本公共配置；"
                "除非具体功能明确设计并授权，否则不会执行 INSERT / UPDATE / DELETE。首次运行会自动带入吉达默认连接；"
                "用户保存过配置后始终优先加载用户配置，修改后的密码在 Windows 下使用当前用户 DPAPI 加密。"
            )
        )

        buttons = QHBoxLayout()
        self.test_button = QPushButton("测试数据库连接")
        self.save_button = QPushButton("保存数据库配置")
        self.test_button.clicked.connect(self._test_connection)
        self.save_button.clicked.connect(self._save_config)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch(1)
        box_layout.addLayout(buttons)

        self.status = QLabel("尚未验证")
        self.status.setObjectName("databaseStatus")
        self._set_status("尚未验证", "idle")
        box_layout.addWidget(self.status)
        self.layout.addWidget(box)

        log_box = QGroupBox("数据库运行日志")
        log_layout = QVBoxLayout(log_box)
        log_buttons = QHBoxLayout()
        self.copy_log_button = QPushButton("复制日志")
        self.clear_log_button = QPushButton("清空日志")
        self.copy_log_button.clicked.connect(self._copy_log)
        self.clear_log_button.clicked.connect(self._clear_log)
        log_buttons.addWidget(self.copy_log_button)
        log_buttons.addWidget(self.clear_log_button)
        log_buttons.addStretch(1)
        log_layout.addLayout(log_buttons)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(260)
        self.log.setPlaceholderText("数据库连接测试和后续公共数据库操作日志会显示在这里。")
        log_layout.addWidget(self.log, 1)
        self.layout.addWidget(log_box, 1)

        self._load_config()
        for field in (self.username, self.password, self.host, self.port, self.service_name):
            if hasattr(field, "textChanged"):
                field.textChanged.connect(self._update_endpoint)  # type: ignore[attr-defined]
            elif hasattr(field, "valueChanged"):
                field.valueChanged.connect(self._update_endpoint)  # type: ignore[attr-defined]

    def _load_config(self) -> None:
        config = self.database_service.load_config()
        self.username.setText(config.username)
        self.password.setText(config.password)
        self.host.setText(config.host)
        self.port.setValue(config.port)
        self.service_name.setText(config.service_name)
        self._update_endpoint()

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

    def _toggle_password(self, checked: bool) -> None:
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_password.setText("隐藏密码" if checked else "显示密码")

    def _set_status(self, text: str, state: str) -> None:
        self.status.setText(text)
        styles = {
            "idle": "background:#f6f8f7;border:1px solid #d2ddda;color:#687c82;",
            "testing": "background:#eef5f4;border:1px solid #b7cfcb;color:#46696d;",
            "ok": "background:#e3f5ed;border:1px solid #98d1bc;color:#087250;",
            "warning": "background:#fff7e7;border:1px solid #e6c675;color:#8a6200;",
            "error": "background:#fff0ee;border:1px solid #efb8af;color:#b2382b;",
        }
        self.status.setStyleSheet(
            "QLabel { border-radius:7px; padding:8px 12px; font-weight:700; "
            + styles.get(state, styles["idle"])
            + " }"
        )

    def _append_log(self, text: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.appendPlainText(f"[{stamp}] {text}")

    def _save_config(self) -> None:
        try:
            config = self._config_from_form()
            secure_password = self.database_service.save_config(config)
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        if secure_password:
            self._append_log("数据库配置已保存；密码已使用 Windows 当前用户 DPAPI 加密。")
            self._set_status("配置已保存 · 尚未验证", "idle")
        else:
            self._append_log("数据库配置已保存；当前系统不支持 Windows DPAPI，因此未持久化密码。")
            self._set_status("配置已保存 · 密码未持久化 · 尚未验证", "warning")

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
