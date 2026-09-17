from __future__ import annotations

import hashlib
import json
import re
import stat as stat_module
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

from platformdirs import user_cache_dir

from g_file_studio.services.remote_g_source import ReadOnlySshClient, RemoteGFile
from g_file_studio.services.site_profile_service import SiteProfileService


DEFAULT_REMOTE_SYMBOL_ROOT = "/home/up8000/data/graph/element"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_component(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return text or "default"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _list_g_files_recursive(client: ReadOnlySshClient, root: str, *, max_files: int = 20000) -> list[RemoteGFile]:
    """Recursively enumerate remote ``*.g`` files without changing the server.

    ``remote_g_source.py`` is part of the protected v2.17.60 business baseline, so
    the symbol-library feature deliberately keeps recursive traversal here instead
    of extending that protected service. Existing/fake clients that expose their
    own recursive helper are supported; otherwise the already-connected SFTP
    channel is used only for ``listdir_attr`` metadata reads. Symlinks are never
    followed.
    """
    recursive = getattr(client, "list_g_files_recursive", None)
    if callable(recursive):
        return list(recursive(root, max_files=max_files))

    client.connect()
    sftp = getattr(client, "_sftp", None)
    if sftp is None:
        raise RuntimeError("SSH/SFTP 连接未建立，无法读取服务器图元库。")
    root_text = str(root).strip()
    if not root_text:
        raise ValueError("服务器图元库根目录不能为空。")
    rows: list[RemoteGFile] = []
    pending = [str(PurePosixPath(root_text))]
    while pending:
        current = pending.pop()
        for attr in sftp.listdir_attr(current):
            name = str(attr.filename)
            remote_path = str(PurePosixPath(current) / name)
            mode = int(getattr(attr, "st_mode", 0) or 0)
            if stat_module.S_ISLNK(mode):
                continue
            if stat_module.S_ISDIR(mode):
                pending.append(remote_path)
                continue
            if not name.lower().endswith(".g"):
                continue
            rows.append(RemoteGFile(
                name=name,
                remote_path=remote_path,
                size=int(attr.st_size),
                mtime_epoch=int(attr.st_mtime),
            ))
            if len(rows) > int(max_files):
                raise ValueError(f"服务器图元库中的 .g 文件超过安全上限 {max_files}，请缩小根目录。")
    rows.sort(key=lambda item: (item.name.casefold(), item.remote_path.casefold()))
    return rows


@dataclass
class RemoteSymbolLibrarySyncResult:
    host: str
    root: str
    scanned_remote_files: int = 0
    requested_names: list[str] = field(default_factory=list)
    matched_records: dict[str, dict[str, object]] = field(default_factory=dict)
    unmatched_names: list[str] = field(default_factory=list)
    conflicts: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    errors: dict[str, list[str]] = field(default_factory=dict)
    downloaded: int = 0
    reused: int = 0
    changed_names: list[str] = field(default_factory=list)
    checked_at: str = ""
    cache_root: str = ""

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


class RemoteSymbolLibraryService:
    """Read-only remote symbol-library index + incremental local cache.

    The remote server is never modified. The service recursively lists ``*.g``
    metadata, downloads either requested definitions or the complete catalog,
    parses them locally, and remembers size/mtime/hash metadata in an atomic
    manifest. Duplicate basenames are accepted only when their downloaded content
    hashes are identical.
    """

    def __init__(self, cache_root: str | Path | None = None) -> None:
        base = Path(cache_root) if cache_root is not None else Path(user_cache_dir("GFileStudio", "NARI")) / "SymbolLibrary"
        self.cache_root = base
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.standard_service = SiteProfileService()

    @staticmethod
    def _root_token(host: str, root: str) -> str:
        digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
        return f"{_safe_component(host)}_{digest}"

    def _library_dir(self, host: str, root: str) -> Path:
        target = self.cache_root / self._root_token(host, root)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def library_dir(self, host: str, root: str = DEFAULT_REMOTE_SYMBOL_ROOT) -> Path:
        """Return/create the persistent local cache directory for one server root."""
        return self._library_dir(host, root)

    def _manifest_path(self, host: str, root: str) -> Path:
        return self._library_dir(host, root) / "manifest.json"

    def _load_manifest(self, host: str, root: str) -> dict[str, dict[str, object]]:
        path = self._manifest_path(host, root)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        return {str(key): dict(value) for key, value in records.items() if isinstance(value, dict)} if isinstance(records, dict) else {}

    def _write_manifest(self, host: str, root: str, records: dict[str, dict[str, object]]) -> None:
        path = self._manifest_path(host, root)
        payload = {
            "version": 1,
            "host": str(host),
            "root": str(root),
            "updated_at": _utc_now(),
            "records": records,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _record_unchanged(cached: dict[str, object], remote: RemoteGFile) -> bool:
        local = Path(str(cached.get("cache_path", "")))
        return (
            local.is_file()
            and int(cached.get("size", -1) or -1) == int(remote.size)
            and int(cached.get("mtime_epoch", -1) or -1) == int(remote.mtime_epoch)
            and bool(str(cached.get("sha256", "")).strip())
        )

    @staticmethod
    def _relative_parent(root: str, remote_path: str) -> Path:
        try:
            rel = PurePosixPath(remote_path).relative_to(PurePosixPath(root))
            parts = [part for part in rel.parent.parts if part not in {"", ".", ".."}]
            return Path(*[_safe_component(part) for part in parts]) if parts else Path()
        except Exception:
            return Path("external")

    def _download_and_parse(
        self,
        *,
        client: ReadOnlySshClient,
        remote: RemoteGFile,
        host: str,
        root: str,
        library_dir: Path,
        log: Callable[[str], None],
    ) -> dict[str, object]:
        relative_parent = self._relative_parent(root, remote.remote_path)
        target_dir = library_dir / "files" / relative_parent
        target_dir.mkdir(parents=True, exist_ok=True)
        # Preserve the authoritative basename exactly: parse_icon_definition() uses
        # Path.name to construct the devref file component. Relative directories
        # already keep duplicate basenames isolated.
        target = target_dir / remote.name
        temp = target.with_name(target.name + ".downloading")
        temp.unlink(missing_ok=True)

        before = client.stat_file(remote.remote_path)
        log(f"[服务器图元库] 下载 {before.remote_path} -> {target}")
        client.download_file(before.remote_path, str(temp))
        after = client.stat_file(remote.remote_path)
        if before.size != after.size or before.mtime_epoch != after.mtime_epoch:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"服务器图元下载期间发生变化：{remote.remote_path}，请重试。")
        if not temp.is_file() or temp.stat().st_size != after.size:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"服务器图元下载不完整：{remote.remote_path}")
        temp.replace(target)

        standard = dict(self.standard_service.prepare_standard_file_records([target])[0])
        digest = _sha256(target)
        standard.update({
            "sha256": digest,
            "standard_source": "server",
            "remote_host": str(host),
            "remote_root": str(root),
            "remote_path": str(after.remote_path),
            "remote_size": int(after.size),
            "remote_mtime": int(after.mtime_epoch),
            "cache_path": str(target.resolve(strict=False)),
            "original_name": str(after.name),
            "original_source": str(target.resolve(strict=False)),
            "synced_at": _utc_now(),
        })
        return {
            "name": str(after.name),
            "remote_path": str(after.remote_path),
            "size": int(after.size),
            "mtime_epoch": int(after.mtime_epoch),
            "sha256": digest,
            "cache_path": str(target.resolve(strict=False)),
            "standard_record": standard,
            "synced_at": _utc_now(),
        }

    def sync_expected(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        root: str = DEFAULT_REMOTE_SYMBOL_ROOT,
        expected_names: Iterable[str] | None,
        log: Callable[[str], None] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> RemoteSymbolLibrarySyncResult:
        log = log or (lambda _msg: None)
        # ``None`` means the complete server catalog.  An explicit empty iterable
        # retains the historical no-op behavior used by callers that only want to
        # resolve a known set of filenames.
        sync_all = expected_names is None
        expected = (
            []
            if sync_all
            else sorted(
                {Path(str(name).strip()).name for name in expected_names if Path(str(name).strip()).name},
                key=str.casefold,
            )
        )
        root = str(root or DEFAULT_REMOTE_SYMBOL_ROOT).strip() or DEFAULT_REMOTE_SYMBOL_ROOT
        result = RemoteSymbolLibrarySyncResult(
            host=str(host).strip(),
            root=root,
            requested_names=expected,
            checked_at=_utc_now(),
            cache_root=str(self._library_dir(host, root)),
        )
        if progress:
            progress(0)
        if not expected and not sync_all:
            if progress:
                progress(100)
            return result

        library_dir = self._library_dir(host, root)
        manifest = self._load_manifest(host, root)
        with ReadOnlySshClient(host, int(port), username, password) as client:
            remote_files = _list_g_files_recursive(client, root)
            result.scanned_remote_files = len(remote_files)
            if sync_all:
                # Keep one logical work item per basename while the manifest still
                # retains every relative remote path.  Duplicate basenames are
                # resolved below and are reported as conflicts when their bytes
                # differ, so no path is silently discarded.
                expected = sorted({item.name for item in remote_files}, key=str.casefold)
                result.requested_names = list(expected)
            if progress:
                progress(15)
            by_name: dict[str, list[RemoteGFile]] = {}
            remote_paths = {item.remote_path for item in remote_files}
            for item in remote_files:
                by_name.setdefault(item.name.casefold(), []).append(item)

            # Prune records that disappeared from the configured root.
            manifest = {path: row for path, row in manifest.items() if path in remote_paths}
            total = max(1, len(expected))
            for index, expected_name in enumerate(expected, 1):
                matches = sorted(by_name.get(expected_name.casefold(), []), key=lambda item: item.remote_path.casefold())
                if not matches:
                    result.unmatched_names.append(expected_name)
                    if progress:
                        progress(15 + round(index * 80 / total))
                    continue

                candidate_records: list[dict[str, object]] = []
                candidate_errors: list[str] = []
                for remote in matches:
                    cached = manifest.get(remote.remote_path, {})
                    try:
                        if self._record_unchanged(cached, remote):
                            record = dict(cached)
                            result.reused += 1
                            standard = dict(record.get("standard_record", {})) if isinstance(record.get("standard_record"), dict) else {}
                            # Old manifests without parsed metadata are refreshed once.
                            if not standard:
                                record = self._download_and_parse(
                                    client=client, remote=remote, host=host, root=root, library_dir=library_dir, log=log
                                )
                                result.downloaded += 1
                            else:
                                # Refresh volatile provenance fields while preserving parsed geometry.
                                standard.update({
                                    "standard_source": "server",
                                    "remote_host": str(host),
                                    "remote_root": root,
                                    "remote_path": remote.remote_path,
                                    "remote_size": int(remote.size),
                                    "remote_mtime": int(remote.mtime_epoch),
                                    "cache_path": str(record.get("cache_path", "")),
                                    "original_name": remote.name,
                                    "original_source": str(record.get("cache_path", "")),
                                    "synced_at": str(record.get("synced_at", "")) or _utc_now(),
                                })
                                record["standard_record"] = standard
                        else:
                            old_hash = str(cached.get("sha256", "")).strip().lower()
                            record = self._download_and_parse(
                                client=client, remote=remote, host=host, root=root, library_dir=library_dir, log=log
                            )
                            result.downloaded += 1
                            new_hash = str(record.get("sha256", "")).strip().lower()
                            # mtime/size is only a cache invalidation hint. A standard is
                            # considered changed only when its content hash changed.
                            if old_hash and new_hash and old_hash != new_hash:
                                result.changed_names.append(expected_name)
                        manifest[remote.remote_path] = record
                        candidate_records.append(record)
                    except Exception as exc:
                        message = f"{remote.remote_path}: {exc}"
                        candidate_errors.append(message)
                        log(f"[服务器图元库] 解析失败：{message}")

                if candidate_errors:
                    # Do not guess when one of several same-name definitions could
                    # not be verified. The operator can inspect/fallback manually.
                    result.errors[expected_name] = candidate_errors
                else:
                    hashes = {str(item.get("sha256", "")).strip().lower() for item in candidate_records if str(item.get("sha256", "")).strip()}
                    if len(hashes) > 1:
                        result.conflicts[expected_name] = [
                            {
                                "remote_path": str(item.get("remote_path", "")),
                                "sha256": str(item.get("sha256", "")),
                                "size": int(item.get("size", 0) or 0),
                                "mtime_epoch": int(item.get("mtime_epoch", 0) or 0),
                            }
                            for item in candidate_records
                        ]
                    elif candidate_records:
                        chosen = candidate_records[0]
                        standard_record = dict(chosen.get("standard_record", {}))
                        if standard_record:
                            result.matched_records[expected_name] = standard_record

                if progress:
                    progress(15 + round(index * 80 / total))

        # Standard version changes are content-based. size/mtime only decide whether
        # a cached file must be re-fetched; touching a file without changing bytes
        # must not manufacture a new locked Profile version.
        result.changed_names = sorted({name for name in result.changed_names if name}, key=str.casefold)
        self._write_manifest(host, root, manifest)
        if progress:
            progress(100)
        return result

    def sync_all(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        root: str = DEFAULT_REMOTE_SYMBOL_ROOT,
        log: Callable[[str], None] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> RemoteSymbolLibrarySyncResult:
        """Read and incrementally cache every icon-definition G below ``root``.

        The server remains strictly read-only.  PNG previews and non-G files are
        ignored by the recursive indexer; every parseable ``.g`` is downloaded on
        first use and reused thereafter until its remote size/mtime changes.
        """
        return self.sync_expected(
            host=host,
            port=port,
            username=username,
            password=password,
            root=root,
            expected_names=None,
            log=log,
            progress=progress,
        )
