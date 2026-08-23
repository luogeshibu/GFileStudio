from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g_file_studio.services.paths import default_workspace
from g_file_studio.services.remote_g_source import (
    DEFAULT_SSH_HOST,
    DEFAULT_SSH_PASSWORD,
    DEFAULT_SSH_PORT,
    DEFAULT_SSH_REMOTE_DIRECTORY,
    DEFAULT_SSH_USERNAME,
    ReadOnlySshClient,
    RemoteGFile,
    download_stable_files,
    human_size,
)
from g_file_studio.services.user_settings_service import UserSettingsService
from g_file_studio.ui.widgets.help_widgets import set_secondary


class RemoteGSourceWidget(QWidget):
    """统一 SSH/SFTP 只读 G 文件源。可多选并下载本地副本。"""

    selectionChanged = Signal()
    prepared = Signal(str)

    def __init__(
        self,
        *,
        settings_prefix: str,
        settings_service: UserSettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_prefix = settings_prefix
        self.settings_service = settings_service or UserSettingsService()
        self._files: list[RemoteGFile] = []
        self._prepared_dir = default_workspace() / "remote_input" / settings_prefix

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        form = QFormLayout()
        self.host = QLineEdit(self._saved("host", DEFAULT_SSH_HOST))
        self.port = QLineEdit(self._saved("port", str(DEFAULT_SSH_PORT)))
        self.username = QLineEdit(self._saved("username", DEFAULT_SSH_USERNAME))
        self.password = QLineEdit(self._saved("password", DEFAULT_SSH_PASSWORD))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.remote_dir = QLineEdit(self._saved("remote_directory", DEFAULT_SSH_REMOTE_DIRECTORY))
        form.addRow("IP / 主机", self.host)
        form.addRow("端口", self.port)
        form.addRow("用户名", self.username)
        form.addRow("密码", self.password)
        form.addRow("远程目录", self.remote_dir)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.test_button = QPushButton("测试 SSH 连接")
        self.refresh_button = QPushButton("刷新 G 文件列表")
        self.save_button = QPushButton("保存 SSH 设置")
        self.download_button = QPushButton("下载所选到本地…")
        set_secondary(self.test_button)
        set_secondary(self.refresh_button)
        set_secondary(self.save_button)
        set_secondary(self.download_button)
        actions.addWidget(self.test_button)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.download_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.status = QLabel("尚未测试 SSH/SFTP 连接。")
        self.status.setWordWrap(True)
        self.status.setObjectName("mutedText")
        root.addWidget(self.status)

        notice = QLabel(
            "SSH 服务器严格只读：仅列目录、读取文件属性和下载 G 文件；"
            "G File Studio 不提供上传、覆盖、重命名、删除或修改服务器文件的接口。"
        )
        notice.setWordWrap(True)
        notice.setObjectName("infoBanner")
        root.addWidget(notice)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("搜索 G 文件"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("例如：ABH-06、JED-NTH、B412")
        search_row.addWidget(self.search, 1)
        self.count_label = QLabel("尚未加载远程文件")
        search_row.addWidget(self.count_label)
        root.addLayout(search_row)

        select_row = QHBoxLayout()
        self.select_visible = QPushButton("全选当前结果")
        self.unselect_visible = QPushButton("取消当前结果")
        self.clear_selection = QPushButton("清空全部选择")
        for btn in (self.select_visible, self.unselect_visible, self.clear_selection):
            set_secondary(btn)
            select_row.addWidget(btn)
        select_row.addStretch(1)
        root.addLayout(select_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "文件名", "大小", "服务器修改时间"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(230)
        root.addWidget(self.table)

        self.test_button.clicked.connect(self.test_connection)
        self.save_button.clicked.connect(self.save_settings)
        self.refresh_button.clicked.connect(self.refresh_files)
        self.download_button.clicked.connect(self.download_selected_to_local)
        self.search.textChanged.connect(self._apply_filter)
        self.select_visible.clicked.connect(lambda: self._set_visible_checked(True))
        self.unselect_visible.clicked.connect(lambda: self._set_visible_checked(False))
        self.clear_selection.clicked.connect(self._clear_checks)
        self.table.itemChanged.connect(self._item_changed)

        # SSH 连接参数是全局共享设置：任一模块修改后，其他使用 SSH 文件源的
        # 模块在再次显示时都会读取同一组最后输入值。字段结束编辑时自动保存，
        # 同时保留显式“保存 SSH 设置”按钮，避免必须先测试连接才会记住输入。
        for editor in (self.host, self.port, self.username, self.password, self.remote_dir):
            editor.editingFinished.connect(self._persist_silently)

    def _key(self, suffix: str) -> str:
        return f"remote_g_source/{suffix}"

    def _saved(self, suffix: str, default: str) -> str:
        return str(self.settings_service.get_value(self._key(suffix), default))

    def persist(self) -> None:
        self.settings_service.set_value(self._key("host"), self.host.text().strip())
        self.settings_service.set_value(self._key("port"), self.port.text().strip())
        self.settings_service.set_value(self._key("username"), self.username.text().strip())
        self.settings_service.set_value(self._key("password"), self.password.text())
        self.settings_service.set_value(self._key("remote_directory"), self.remote_dir.text().strip())

    def _persist_silently(self) -> None:
        """保存最后一次 SSH 输入，不弹窗、不发起网络连接。"""
        self.persist()

    def save_settings(self) -> None:
        """显式保存 SSH/SFTP 参数；只写本机用户配置，不访问服务器。"""
        try:
            # 先校验端口格式，避免把明显无效的连接参数保存成当前配置。
            self.config()
            self.persist()
            self.status.setText("SSH 设置已保存；所有使用 SSH 文件源的模块将复用这组最后输入。")
        except Exception as exc:
            QMessageBox.warning(self, "保存 SSH 设置失败", str(exc))

    def _restore_shared_settings(self) -> None:
        """从全局 SSH 设置恢复字段，供模块切换后同步其他页面的最新输入。"""
        values = (
            (self.host, self._saved("host", DEFAULT_SSH_HOST)),
            (self.port, self._saved("port", str(DEFAULT_SSH_PORT))),
            (self.username, self._saved("username", DEFAULT_SSH_USERNAME)),
            (self.password, self._saved("password", DEFAULT_SSH_PASSWORD)),
            (self.remote_dir, self._saved("remote_directory", DEFAULT_SSH_REMOTE_DIRECTORY)),
        )
        for editor, value in values:
            if not editor.hasFocus() and editor.text() != value:
                editor.setText(value)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API naming
        # MainWindow 会预先创建各页面，因此切换到另一个模块时重新读取共享 SSH
        # 配置，确保所有模块看到的是用户最近一次保存/结束编辑后的参数。
        self._restore_shared_settings()
        super().showEvent(event)

    def config(self) -> dict[str, object]:
        try:
            port = int(self.port.text().strip())
        except ValueError as exc:
            raise ValueError("SSH 端口必须是整数。") from exc
        return {
            "host": self.host.text().strip(),
            "port": port,
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "remote_directory": self.remote_dir.text().strip(),
        }

    def _client(self) -> ReadOnlySshClient:
        cfg = self.config()
        return ReadOnlySshClient(cfg["host"], cfg["port"], cfg["username"], cfg["password"])

    def test_connection(self) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.persist()
            with self._client() as client:
                client.test_connection()
            cfg = self.config()
            self.status.setText(
                f"SSH/SFTP 连接正常：{cfg['host']}:{cfg['port']}；远程文件源为只读。"
            )
            return True
        except Exception as exc:
            self.status.setText(f"SSH/SFTP 连接失败：{exc}")
            QMessageBox.warning(self, "SSH 连接失败", str(exc))
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def refresh_files(self) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.persist()
            cfg = self.config()
            with self._client() as client:
                files = client.list_g_files(str(cfg["remote_directory"]))
            self._files = files
            self._rebuild_table()
            self.status.setText(
                f"SSH/SFTP 连接正常；远程文件源只读。已加载 {len(files)} 个 .g 文件。"
            )
            return True
        except Exception as exc:
            self.status.setText(f"读取远程 G 文件列表失败：{exc}")
            QMessageBox.warning(self, "远程文件列表加载失败", str(exc))
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def _rebuild_table(self) -> None:
        checked = {item.remote_path for item in self.selected_files()}
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._files))
        for row, info in enumerate(self._files):
            select_item = QTableWidgetItem("")
            select_item.setFlags(select_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            select_item.setCheckState(Qt.CheckState.Checked if info.remote_path in checked else Qt.CheckState.Unchecked)
            select_item.setData(Qt.ItemDataRole.UserRole, info.remote_path)
            self.table.setItem(row, 0, select_item)
            self.table.setItem(row, 1, QTableWidgetItem(info.name))
            self.table.setItem(row, 2, QTableWidgetItem(human_size(info.size)))
            self.table.setItem(row, 3, QTableWidgetItem(info.mtime_text))
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self.search.text().strip().casefold()
        visible = 0
        selected = 0
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 1).text().casefold()
            show = not keyword or keyword in name
            self.table.setRowHidden(row, not show)
            if show:
                visible += 1
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                selected += 1
        self.count_label.setText(f"总数 {len(self._files)} | 当前显示 {visible} | 已选择 {selected}")

    def _set_visible_checked(self, checked: bool) -> None:
        self.table.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(state)
        self.table.blockSignals(False)
        self._apply_filter()
        self.selectionChanged.emit()

    def _clear_checks(self) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._apply_filter()
        self.selectionChanged.emit()

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._apply_filter()
            self.selectionChanged.emit()

    def selected_files(self) -> list[RemoteGFile]:
        by_path = {item.remote_path: item for item in self._files}
        selected: list[RemoteGFile] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                remote_path = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if remote_path in by_path:
                    selected.append(by_path[remote_path])
        return selected

    def cache_dir(self) -> Path:
        return self._prepared_dir

    def _processing_snapshot_dir(self) -> Path:
        """Return the local workspace directory used for automatic SSH processing snapshots.

        Automatic processing must never point at the remote server path.  Every selected
        server G file is first downloaded through SFTP GET into workspace/remote_input/<module>.
        All business engines then receive only these local Path objects.
        """
        workspace_root = default_workspace().resolve()
        prepared = self._prepared_dir.resolve()
        try:
            prepared.relative_to(workspace_root)
        except ValueError as exc:
            raise RuntimeError(
                f"SSH 处理快照目录必须位于本地 workspace 中：{prepared}"
            ) from exc
        return prepared

    def prepare_selected(self, *, log=None) -> Path:
        selected = self.selected_files()
        if not selected:
            raise ValueError("请先在 SSH G 文件列表中选择一个或多个文件。")
        self.persist()
        cfg = self.config()
        snapshot_dir = self._processing_snapshot_dir()
        if log is not None:
            log(
                f"[SSH只读] 将 {len(selected)} 个服务器 G 文件下载为本地处理快照：{snapshot_dir}"
            )
            log("[SSH只读] 后续扫描/处理仅使用 workspace 本地快照，不会修改服务器文件。")
        download_stable_files(
            host=str(cfg["host"]),
            port=int(cfg["port"]),
            username=str(cfg["username"]),
            password=str(cfg["password"]),
            selected_files=selected,
            target_dir=snapshot_dir,
            log=log,
        )
        self.prepared.emit(str(snapshot_dir))
        return snapshot_dir

    def download_selected_to_local(self) -> None:
        selected = self.selected_files()
        if not selected:
            QMessageBox.information(self, "请选择文件", "请先选择一个或多个要下载到本地的 G 文件。")
            return
        destination = QFileDialog.getExistingDirectory(self, "选择本地下载目录", str(default_workspace()))
        if not destination:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.persist()
            cfg = self.config()
            outputs = download_stable_files(
                host=str(cfg["host"]),
                port=int(cfg["port"]),
                username=str(cfg["username"]),
                password=str(cfg["password"]),
                selected_files=selected,
                target_dir=Path(destination),
                clear_target=False,
            )
            QMessageBox.information(
                self,
                "下载完成",
                f"已下载 {len(outputs)} 个 G 文件到：\n{destination}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "下载失败", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
