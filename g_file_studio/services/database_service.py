from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable

from g_file_studio.services.user_settings_service import UserSettingsService


_DEFAULT_USERNAME = "d5000"
_DEFAULT_PASSWORD = "OracleDV1Dec.25"
_DEFAULT_HOST = "172.16.21.45"
_DEFAULT_PORT = 1521
_DEFAULT_SERVICE = "jedup8000"


@dataclass(frozen=True)
class OracleConnectionConfig:
    """Central Oracle connection configuration used by future business modules."""

    username: str = _DEFAULT_USERNAME
    password: str = _DEFAULT_PASSWORD
    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    service_name: str = _DEFAULT_SERVICE

    @property
    def dsn(self) -> str:
        return f"{self.host}:{self.port}/{self.service_name}"

    def validate(self) -> None:
        if not self.username.strip():
            raise ValueError("数据库用户名不能为空。")
        if not self.password:
            raise ValueError("数据库密码不能为空。")
        if not self.host.strip():
            raise ValueError("数据库服务器地址不能为空。")
        if not (1 <= int(self.port) <= 65535):
            raise ValueError("数据库端口必须在 1~65535 之间。")
        if not self.service_name.strip():
            raise ValueError("Oracle Service Name 不能为空。")




@dataclass(frozen=True)
class GFileDatabaseContext:
    """Resolved business identity for one feeder G file."""

    fac_id: str
    feeder_id: str
    feeder_name: str
    station_id: str
    station_name: str
    subarea_id: str
    subcontrolarea_name: str
    station_full_name: str
    feeder_full_name: str


@dataclass(frozen=True)
class RmuDatabaseContext:
    """Resolved feeder/station business identity from one RMU cabinet name.

    Authoritative relation:
    DMS_COMBINED_DEVICE.NAME -> DMS_COMBINED_DEVICE.FEEDER_ID
    -> DMS_FEEDER_DEVICE.ID/NAME/ST_ID -> SUBSTATION -> SUBCONTROLAREA.
    GRAPH_NAME is intentionally absent.
    """

    rmu_name: str
    combined_device_id: str
    feeder_id: str
    feeder_name: str
    station_id: str
    station_name: str
    subarea_id: str
    subcontrolarea_name: str
    station_full_name: str
    feeder_full_name: str


@dataclass(frozen=True)
class StationDatabaseContext:
    """Resolved canonical station identity from SUBSTATION.NAME.

    GRAPH_NAME is intentionally absent: station Poke naming is based only on
    SUBSTATION.NAME and its SUBAREA_ID -> SUBCONTROLAREA.NAME relation.
    """

    station_id: str
    station_name: str
    subarea_id: str
    subcontrolarea_name: str
    station_full_name: str

class _WindowsDpapiSecretStore:
    """Protect the database password with Windows DPAPI for the current user.

    The encrypted blob may safely live in the ordinary user_settings.ini.  It can be
    decrypted only by the same Windows user profile.  On non-Windows systems the
    password is deliberately not persisted.
    """

    @staticmethod
    def available() -> bool:
        return os.name == "nt"

    @staticmethod
    def protect(text: str) -> str:
        if not text or not _WindowsDpapiSecretStore.available():
            return ""
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        raw = text.encode("utf-8")
        buffer = ctypes.create_string_buffer(raw)
        in_blob = DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        description = "G File Studio Oracle Password"
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            description,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise OSError("Windows DPAPI 无法加密数据库密码。")
        try:
            protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return base64.b64encode(protected).decode("ascii")
        finally:
            kernel32.LocalFree(out_blob.pbData)

    @staticmethod
    def unprotect(encoded: str) -> str:
        if not encoded or not _WindowsDpapiSecretStore.available():
            return ""
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        protected = base64.b64decode(encoded.encode("ascii"), validate=True)
        buffer = ctypes.create_string_buffer(protected)
        in_blob = DATA_BLOB(len(protected), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise OSError("Windows DPAPI 无法解密数据库密码。")
        try:
            raw = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return raw.decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)


class OracleDatabaseService:
    """Shared Oracle access service.

    Current G File Studio policy is intentionally conservative: the public query API
    is read-only and accepts SELECT / WITH statements only.  Future modules should
    consume this service rather than create private connection settings or embed
    credentials independently.
    """

    _WRITE_SQL = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COMMIT|ROLLBACK|CALL|BEGIN|DECLARE|EXEC(?:UTE)?)\b",
        re.IGNORECASE,
    )

    def __init__(self, settings: UserSettingsService) -> None:
        self.settings = settings

    def _has_saved_user_config(self) -> bool:
        """Return True once the user has persisted any Oracle connection setting.

        v2.18.86/v2.18.87 did not write an explicit marker, so the field existence
        check also preserves settings saved by those versions during upgrade.
        """
        if self.settings.get_bool("database/oracle_config_saved", False):
            return True
        sentinel = "__GFS_DATABASE_SETTING_MISSING__"
        keys = (
            "database/oracle_username",
            "database/oracle_password_dpapi",
            "database/oracle_host",
            "database/oracle_port",
            "database/oracle_service",
        )
        return any(self.settings.get_value(key, sentinel) != sentinel for key in keys)

    def load_config(self) -> OracleConnectionConfig:
        # Factory values are used only when the user has never saved a database
        # configuration. Once a user configuration exists, it is authoritative.
        if not self._has_saved_user_config():
            return OracleConnectionConfig()

        password = ""
        protected = self.settings.get_value("database/oracle_password_dpapi").strip()
        if protected and _WindowsDpapiSecretStore.available():
            try:
                password = _WindowsDpapiSecretStore.unprotect(protected)
            except Exception:
                # A copied profile or changed Windows user cannot decrypt the blob.
                # Never fall back to the factory password after a user configuration
                # has been saved, because that could silently use the wrong account.
                password = ""
        return OracleConnectionConfig(
            username=self.settings.get_value("database/oracle_username", _DEFAULT_USERNAME).strip() or _DEFAULT_USERNAME,
            password=password,
            host=self.settings.get_value("database/oracle_host", _DEFAULT_HOST).strip() or _DEFAULT_HOST,
            port=self.settings.get_int("database/oracle_port", _DEFAULT_PORT),
            service_name=self.settings.get_value("database/oracle_service", _DEFAULT_SERVICE).strip() or _DEFAULT_SERVICE,
        )

    def save_config(self, config: OracleConnectionConfig) -> bool:
        """Persist public fields and, on Windows, protect the password with DPAPI.

        Returns True when the password was persisted securely.  On non-Windows
        systems only non-secret fields are saved and the caller should inform the
        user that the password will need to be re-entered.
        """
        config.validate()
        self.settings.set_value("database/oracle_username", config.username.strip())
        self.settings.set_value("database/oracle_host", config.host.strip())
        self.settings.set_value("database/oracle_port", int(config.port))
        self.settings.set_value("database/oracle_service", config.service_name.strip())
        self.settings.set_value("database/oracle_config_saved", "true")
        if _WindowsDpapiSecretStore.available():
            protected = _WindowsDpapiSecretStore.protect(config.password)
            self.settings.set_value("database/oracle_password_dpapi", protected)
            return True
        self.settings.clear("database/oracle_password_dpapi")
        return False

    @staticmethod
    def _import_driver():
        try:
            import oracledb  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on runtime packaging
            raise RuntimeError(
                "未安装 Oracle 驱动 python-oracledb。请重新运行 setup_env.ps1 或安装 requirements.txt。"
            ) from exc
        return oracledb

    @staticmethod
    def _connect(config: OracleConnectionConfig):
        config.validate()
        oracledb = OracleDatabaseService._import_driver()
        params = oracledb.ConnectParams(
            host=config.host.strip(),
            port=int(config.port),
            service_name=config.service_name.strip(),
            tcp_connect_timeout=8.0,
        )
        return oracledb.connect(
            user=config.username.strip(),
            password=config.password,
            params=params,
        )

    def test_connection(self, config: OracleConnectionConfig) -> dict[str, Any]:
        """Open a short-lived connection and execute read-only health queries."""
        connection = self._connect(config)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchone()
                cursor.execute(
                    "SELECT USER, SYS_CONTEXT('USERENV','DB_NAME'), "
                    "SYS_CONTEXT('USERENV','SERVICE_NAME') FROM DUAL"
                )
                row = cursor.fetchone() or (config.username, "", config.service_name)
            return {
                "username": str(row[0] or config.username),
                "database": str(row[1] or ""),
                "service": str(row[2] or config.service_name),
                "dsn": config.dsn,
            }
        finally:
            connection.close()


    def resolve_g_file_context(
        self,
        fac_id: str | int,
        *,
        config: OracleConnectionConfig | None = None,
    ) -> GFileDatabaseContext:
        """Resolve station/feeder business names from a G root ``facID``.

        Authoritative relation:
        G.facID -> DMS_FEEDER_DEVICE.ID -> (NAME, ST_ID)
        -> SUBSTATION.ID -> (NAME, SUBAREA_ID)
        -> SUBCONTROLAREA.ID -> NAME.

        GRAPH_NAME is deliberately not used to construct business names.
        """
        raw_fac_id = str(fac_id or "").strip()
        if not raw_fac_id:
            raise ValueError(
                "当前 G 文件 facID 为空。请先关联馈线，再执行智能环网柜 Poke 跳转。"
            )
        if not raw_fac_id.isdigit():
            raise ValueError(f"当前 G 文件 facID 不是有效数字：{raw_fac_id!r}")

        sql = """
            SELECT
                f.ID,
                f.NAME,
                f.ST_ID,
                s.ID,
                s.NAME,
                s.SUBAREA_ID,
                a.ID,
                a.NAME
            FROM DMS_FEEDER_DEVICE f
            LEFT JOIN SUBSTATION s
                   ON s.ID = f.ST_ID
            LEFT JOIN SUBCONTROLAREA a
                   ON a.ID = s.SUBAREA_ID
            WHERE f.ID = :fac_id
        """
        _columns, rows = self.query(sql, {"fac_id": int(raw_fac_id)}, max_rows=2, config=config)
        if not rows:
            raise LookupError(
                f"数据库未找到 facID={raw_fac_id} 对应的 DMS_FEEDER_DEVICE 记录。"
            )
        if len(rows) > 1:
            raise LookupError(
                f"数据库中 facID={raw_fac_id} 返回多条馈线记录，无法唯一确定。"
            )

        row = rows[0]
        feeder_id = str(row[0] or "").strip()
        feeder_name = str(row[1] or "").strip()
        station_id = str(row[3] or row[2] or "").strip()
        station_name = str(row[4] or "").strip()
        subarea_id = str(row[5] or "").strip()
        subcontrolarea_name = str(row[7] or "").strip()

        missing = [
            label for label, value in (
                ("DMS_FEEDER_DEVICE.NAME", feeder_name),
                ("SUBSTATION.NAME", station_name),
                ("SUBSTATION.SUBAREA_ID", subarea_id),
                ("SUBCONTROLAREA.NAME", subcontrolarea_name),
            ) if not value
        ]
        if missing:
            raise LookupError(
                f"facID={raw_fac_id} 的数据库关联信息不完整：" + ", ".join(missing)
            )

        station_full_name = f"{subcontrolarea_name}-{station_name}"
        feeder_full_name = f"{station_full_name}-{feeder_name}"
        return GFileDatabaseContext(
            fac_id=raw_fac_id,
            feeder_id=feeder_id or raw_fac_id,
            feeder_name=feeder_name,
            station_id=station_id,
            station_name=station_name,
            subarea_id=subarea_id,
            subcontrolarea_name=subcontrolarea_name,
            station_full_name=station_full_name,
            feeder_full_name=feeder_full_name,
        )

    @staticmethod
    def _rmu_lookup_key(value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    def resolve_rmu_contexts(
        self,
        rmu_names: Iterable[str],
        *,
        config: OracleConnectionConfig | None = None,
    ) -> tuple[dict[str, RmuDatabaseContext], dict[str, str]]:
        """Resolve many RMU names to their feeder/station context in one DB round trip.

        This is the authoritative Poke path for RMU detail jumps.  ``facID`` is
        deliberately not involved because a station overview drawing may contain
        RMUs from many feeders.  Each cabinet resolves independently through
        DMS_COMBINED_DEVICE.NAME -> FEEDER_ID.

        The returned dictionaries are keyed by normalized/case-folded RMU name.
        Missing, duplicated, or incomplete database rows are returned in
        ``issues`` instead of aborting the whole G file.
        """
        requested: list[str] = []
        seen: set[str] = set()
        for raw in rmu_names:
            name = re.sub(r"\s+", " ", str(raw or "").strip())
            key = self._rmu_lookup_key(name)
            if name and key not in seen:
                seen.add(key)
                requested.append(name)
        if not requested:
            return {}, {}

        # A single station overview can contain hundreds of cabinets.  Keep the
        # query below Oracle's 1000-expression IN limit while avoiding one TCP/DB
        # connection per RMU.
        rows_by_key: dict[str, list[tuple[Any, ...]]] = {self._rmu_lookup_key(n): [] for n in requested}
        chunk_size = 500
        for start in range(0, len(requested), chunk_size):
            chunk = requested[start:start + chunk_size]
            params = {f"rmu_{i}": name for i, name in enumerate(chunk)}
            bind_list = ", ".join(f":rmu_{i}" for i in range(len(chunk)))
            sql = f"""
                SELECT
                    c.ID,
                    c.NAME,
                    c.FEEDER_ID,
                    f.ID,
                    f.NAME,
                    f.ST_ID,
                    s.ID,
                    s.NAME,
                    s.SUBAREA_ID,
                    a.ID,
                    a.NAME
                FROM DMS_COMBINED_DEVICE c
                LEFT JOIN DMS_FEEDER_DEVICE f
                       ON f.ID = c.FEEDER_ID
                LEFT JOIN SUBSTATION s
                       ON s.ID = f.ST_ID
                LEFT JOIN SUBCONTROLAREA a
                       ON a.ID = s.SUBAREA_ID
                WHERE UPPER(TRIM(CAST(c.NAME AS VARCHAR2(128)))) IN (
                    {bind_list}
                )
            """
            upper_params = {key: str(value).upper() for key, value in params.items()}
            _columns, rows = self.query(sql, upper_params, max_rows=max(len(chunk) * 4, 100), config=config)
            for row in rows:
                row_key = self._rmu_lookup_key(row[1] if len(row) > 1 else "")
                if row_key in rows_by_key:
                    rows_by_key[row_key].append(row)

        contexts: dict[str, RmuDatabaseContext] = {}
        issues: dict[str, str] = {}
        for requested_name in requested:
            key = self._rmu_lookup_key(requested_name)
            rows = rows_by_key.get(key, [])
            if not rows:
                issues[key] = (
                    f"数据库未找到 DMS_COMBINED_DEVICE.NAME={requested_name!r} 的环网柜记录。"
                )
                continue
            if len(rows) > 1:
                issues[key] = (
                    f"数据库中 DMS_COMBINED_DEVICE.NAME={requested_name!r} 返回 {len(rows)} 条记录，"
                    "无法唯一确定所属馈线。"
                )
                continue

            row = rows[0]
            combined_device_id = str(row[0] or "").strip()
            resolved_rmu_name = str(row[1] or requested_name).strip()
            feeder_id = str(row[3] or row[2] or "").strip()
            feeder_name = str(row[4] or "").strip()
            station_id = str(row[6] or row[5] or "").strip()
            station_name = str(row[7] or "").strip()
            subarea_id = str(row[8] or "").strip()
            subcontrolarea_name = str(row[10] or "").strip()
            missing = [
                label for label, value in (
                    ("DMS_COMBINED_DEVICE.ID", combined_device_id),
                    ("DMS_COMBINED_DEVICE.FEEDER_ID", feeder_id),
                    ("DMS_FEEDER_DEVICE.NAME", feeder_name),
                    ("SUBSTATION.NAME", station_name),
                    ("SUBSTATION.SUBAREA_ID", subarea_id),
                    ("SUBCONTROLAREA.NAME", subcontrolarea_name),
                ) if not value
            ]
            if missing:
                issues[key] = (
                    f"RMU {requested_name!r} 的数据库关联信息不完整：" + ", ".join(missing)
                )
                continue

            station_full_name = f"{subcontrolarea_name}-{station_name}"
            feeder_full_name = f"{station_full_name}-{feeder_name}"
            contexts[key] = RmuDatabaseContext(
                rmu_name=resolved_rmu_name,
                combined_device_id=combined_device_id,
                feeder_id=feeder_id,
                feeder_name=feeder_name,
                station_id=station_id,
                station_name=station_name,
                subarea_id=subarea_id,
                subcontrolarea_name=subcontrolarea_name,
                station_full_name=station_full_name,
                feeder_full_name=feeder_full_name,
            )

        return contexts, issues

    def resolve_rmu_context(
        self,
        rmu_name: str,
        *,
        config: OracleConnectionConfig | None = None,
    ) -> RmuDatabaseContext:
        """Resolve one RMU name; convenience wrapper over the batch resolver."""
        name = re.sub(r"\s+", " ", str(rmu_name or "").strip())
        if not name:
            raise ValueError("RMU 名称不能为空。")
        contexts, issues = self.resolve_rmu_contexts([name], config=config)
        key = self._rmu_lookup_key(name)
        if key in issues:
            raise LookupError(issues[key])
        context = contexts.get(key)
        if context is None:
            raise LookupError(f"RMU {name!r} 未解析到所属馈线。")
        return context

    def resolve_station_context(
        self,
        station_name: str,
        *,
        config: OracleConnectionConfig | None = None,
    ) -> StationDatabaseContext:
        """Resolve a station's canonical name using business fields only.

        Authoritative relation:
        SUBSTATION.NAME -> SUBSTATION.SUBAREA_ID -> SUBCONTROLAREA.ID/NAME.
        GRAPH_NAME is deliberately not read or used.  Exact case-insensitive
        NAME matching is required; zero or multiple rows are considered unsafe.
        """
        name = re.sub(r"\s+", " ", str(station_name or "").strip())
        if not name:
            raise ValueError("变电站关键字不能为空。")

        sql = """
            SELECT
                s.ID,
                s.NAME,
                s.SUBAREA_ID,
                a.ID,
                a.NAME
            FROM SUBSTATION s
            LEFT JOIN SUBCONTROLAREA a
                   ON a.ID = s.SUBAREA_ID
            WHERE UPPER(TRIM(s.NAME)) = UPPER(TRIM(:station_name))
        """
        _columns, rows = self.query(sql, {"station_name": name}, max_rows=3, config=config)
        if not rows:
            raise LookupError(f"数据库未找到 SUBSTATION.NAME={name!r} 的变电站记录。")
        if len(rows) > 1:
            raise LookupError(
                f"数据库中 SUBSTATION.NAME={name!r} 返回多条记录，无法唯一确定完整变电站名称。"
            )

        row = rows[0]
        station_id = str(row[0] or "").strip()
        resolved_name = str(row[1] or "").strip()
        subarea_id = str(row[2] or "").strip()
        subcontrolarea_name = str(row[4] or "").strip()
        missing = [
            label for label, value in (
                ("SUBSTATION.ID", station_id),
                ("SUBSTATION.NAME", resolved_name),
                ("SUBSTATION.SUBAREA_ID", subarea_id),
                ("SUBCONTROLAREA.NAME", subcontrolarea_name),
            ) if not value
        ]
        if missing:
            raise LookupError(
                f"SUBSTATION.NAME={name!r} 的数据库关联信息不完整：" + ", ".join(missing)
            )

        station_full_name = f"{subcontrolarea_name}-{resolved_name}"
        return StationDatabaseContext(
            station_id=station_id,
            station_name=resolved_name,
            subarea_id=subarea_id,
            subcontrolarea_name=subcontrolarea_name,
            station_full_name=station_full_name,
        )


    @classmethod
    def validate_read_only_sql(cls, sql: str) -> str:
        statement = str(sql).strip().rstrip(";").strip()
        if not statement:
            raise ValueError("SQL 不能为空。")
        # Ignore leading SQL comments when deciding the first statement keyword.
        normalized = re.sub(r"^\s*(?:(?:--[^\n]*\n)|(?:/\*.*?\*/\s*))*", "", statement, flags=re.DOTALL)
        first = normalized.split(None, 1)[0].upper() if normalized else ""
        if first not in {"SELECT", "WITH"} or cls._WRITE_SQL.search(normalized):
            raise PermissionError("公共数据库服务当前只允许 SELECT / WITH 只读查询。")
        return statement

    def query(
        self,
        sql: str,
        params: dict[str, Any] | Iterable[Any] | None = None,
        *,
        max_rows: int = 10000,
        config: OracleConnectionConfig | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute a bounded read-only query for future modules."""
        statement = self.validate_read_only_sql(sql)
        cfg = config or self.load_config()
        connection = self._connect(cfg)
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, params or {})
                columns = [str(item[0]) for item in (cursor.description or [])]
                rows = cursor.fetchmany(max(1, min(int(max_rows), 100000)))
                return columns, list(rows)
        finally:
            connection.close()
