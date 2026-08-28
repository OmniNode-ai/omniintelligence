# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Durable, deterministic artifacts for code-projection application.

The store deliberately separates writing immutable inputs from advancing the
current-source pointer.  A caller stages the raw source and canonical batch,
applies the batch to its authoritative backends, and only then calls
``mark_applied``.  A failed backend application therefore cannot make an
unapplied projection appear current.
"""

from __future__ import annotations

import errno
import fcntl
import os
import re
import stat
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    decode_json_no_duplicates,
    normalize_relative_path,
    normalize_repository_id,
    normalize_tenant_id,
    sha256_hex,
)
from omniintelligence.code_projection.codec import (
    parse_code_projection_batch,
    plan_code_projection_replay,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection.models import ModelCodeProjectionBatch

_STATE_FORMAT_VERSION = "2.0.0"
_SOURCE_ID_PATTERN = re.compile(r"^csrc_v2_[0-9a-f]{64}$")
_BATCH_ID_PATTERN = re.compile(r"^cbatch_v2_[0-9a-f]{64}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_REF_PREFIX = "artifact://sha256/"
_STATE_KEYS = frozenset(
    {
        "batch_content_hash_sha256",
        "batch_id",
        "format_version",
        "operation",
        "raw_content_hash_sha256",
        "relative_path",
        "repository_id",
        "source_id",
        "tenant_id",
    }
)


class CodeProjectionArtifactIntegrityError(ValueError):
    """Raised when durable artifact or state bytes fail closed validation."""


@dataclass(frozen=True, slots=True)
class StagedCodeProjection:
    """Immutable receipt for content-addressed artifacts awaiting application."""

    source_id: str
    batch_id: str
    raw_content_hash_sha256: str
    batch_content_hash_sha256: str
    raw_artifact_path: Path
    batch_artifact_path: Path


@dataclass(frozen=True, slots=True)
class StagedContentArtifact:
    """One immutable content-addressed blob resolvable by its artifact URI."""

    content_hash_sha256: str
    artifact_path: Path


@dataclass(frozen=True, slots=True)
class CurrentCodeProjection:
    """Validated current-source state and the canonical batch it addresses."""

    batch: ModelCodeProjectionBatch
    raw_artifact_path: Path
    batch_artifact_path: Path
    state_path: Path
    batch_content_hash_sha256: str


@dataclass(frozen=True, slots=True)
class _CurrentState:
    source_id: str
    tenant_id: str
    repository_id: str
    relative_path: str
    batch_id: str
    operation: str
    raw_content_hash_sha256: str
    batch_content_hash_sha256: str

    def to_wire(self) -> dict[str, str]:
        return {
            "batch_content_hash_sha256": self.batch_content_hash_sha256,
            "batch_id": self.batch_id,
            "format_version": _STATE_FORMAT_VERSION,
            "operation": self.operation,
            "raw_content_hash_sha256": self.raw_content_hash_sha256,
            "relative_path": self.relative_path,
            "repository_id": self.repository_id,
            "source_id": self.source_id,
            "tenant_id": self.tenant_id,
        }


def _integrity_error(message: str) -> CodeProjectionArtifactIntegrityError:
    return CodeProjectionArtifactIntegrityError(message)


def _read_regular_file(path: Path, *, description: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise _integrity_error(f"unable to read {description}: {path.name}") from exc

    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise _integrity_error(f"{description} is not a regular file: {path.name}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _integrity_error(
            f"unable to synchronize artifact directory: {path.name}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise _integrity_error(f"artifact path is not a directory: {path.name}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_real_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        raise
    if stat.S_ISLNK(metadata.st_mode):
        raise _integrity_error(
            f"artifact directory path contains a symbolic link: {path.name}"
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise _integrity_error(f"artifact path is not a directory: {path.name}")


def _directory_chain(path: Path) -> tuple[Path, ...]:
    if not path.is_absolute():  # pragma: no cover - store paths are anchored at init
        raise ValueError("artifact directory path must be absolute")
    anchor = Path(path.anchor)
    current = anchor
    directories = [anchor]
    for component in path.parts[1:]:
        current /= component
        directories.append(current)
    return tuple(directories)


def _validate_directory_chain(path: Path) -> None:
    for directory in _directory_chain(path):
        _require_real_directory(directory)


def _ensure_directory_chain(path: Path) -> None:
    directories = _directory_chain(path)
    _require_real_directory(directories[0])
    for directory in directories[1:]:
        try:
            _require_real_directory(directory)
        except FileNotFoundError:
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                _require_real_directory(directory)
            else:
                # Persist both the directory inode and the parent entry that
                # makes it reachable before creating anything below it.
                _sync_directory(directory)
                _sync_directory(directory.parent)


def _write_temp(path: Path, payload: bytes) -> Path:
    _validate_directory_chain(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".staging-", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _write_immutable(path: Path, payload: bytes, *, description: str) -> None:
    _validate_directory_chain(path.parent)
    if path.exists() or path.is_symlink():
        existing = _read_regular_file(path, description=description)
        if existing != payload:
            raise _integrity_error(
                f"existing content-addressed {description} is corrupt: {path.name}"
            )
        # The caller may be recovering after a crash between linking the
        # immutable object and syncing its containing directory.
        _sync_directory(path.parent)
        return

    temporary_path = _write_temp(path, payload)
    try:
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            existing = _read_regular_file(path, description=description)
            if existing != payload:
                raise _integrity_error(
                    f"concurrent content-addressed {description} is corrupt: "
                    f"{path.name}"
                )
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                existing = _read_regular_file(path, description=description)
                if existing != payload:
                    raise _integrity_error(
                        f"concurrent content-addressed {description} is corrupt: "
                        f"{path.name}"
                    )
            else:
                raise
        _sync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_replace(path: Path, payload: bytes) -> None:
    temporary_path = _write_temp(path, payload)
    try:
        temporary_path.replace(path)
        _sync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _require_wire_string(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise _integrity_error(f"current state {key} must be a string")
    return value


def _parse_current_state(payload: bytes) -> _CurrentState:
    try:
        decoded = decode_json_no_duplicates(payload)
    except ValueError as exc:
        raise _integrity_error("current state is not valid unambiguous JSON") from exc
    if not isinstance(decoded, dict):
        raise _integrity_error("current state must be a JSON object")
    if set(decoded) != _STATE_KEYS:
        raise _integrity_error("current state has missing or unsupported fields")
    if payload != canonical_json_bytes(decoded) + b"\n":
        raise _integrity_error("current state is not exact canonical bytes")

    format_version = _require_wire_string(decoded, "format_version")
    if format_version != _STATE_FORMAT_VERSION:
        raise _integrity_error("current state format_version is unsupported")

    source_id = _require_wire_string(decoded, "source_id")
    tenant_id = _require_wire_string(decoded, "tenant_id")
    batch_id = _require_wire_string(decoded, "batch_id")
    raw_digest = _require_wire_string(decoded, "raw_content_hash_sha256")
    batch_digest = _require_wire_string(decoded, "batch_content_hash_sha256")
    repository_id = _require_wire_string(decoded, "repository_id")
    relative_path = _require_wire_string(decoded, "relative_path")
    operation = _require_wire_string(decoded, "operation")

    if _SOURCE_ID_PATTERN.fullmatch(source_id) is None:
        raise _integrity_error("current state source_id is invalid")
    try:
        normalize_tenant_id(tenant_id)
    except ValueError as exc:
        raise _integrity_error("current state tenant_id is invalid") from exc
    if _BATCH_ID_PATTERN.fullmatch(batch_id) is None:
        raise _integrity_error("current state batch_id is invalid")
    if _SHA256_PATTERN.fullmatch(raw_digest) is None:
        raise _integrity_error("current state raw content digest is invalid")
    if _SHA256_PATTERN.fullmatch(batch_digest) is None:
        raise _integrity_error("current state batch content digest is invalid")
    if repository_id != normalize_repository_id(repository_id):
        raise _integrity_error("current state repository_id is not canonical")
    if relative_path != normalize_relative_path(relative_path):
        raise _integrity_error("current state relative_path is not canonical")
    if operation not in {"snapshot", "tombstone"}:
        raise _integrity_error("current state operation is invalid")

    return _CurrentState(
        source_id=source_id,
        tenant_id=tenant_id,
        repository_id=repository_id,
        relative_path=relative_path,
        batch_id=batch_id,
        operation=operation,
        raw_content_hash_sha256=raw_digest,
        batch_content_hash_sha256=batch_digest,
    )


#: Request-scoped memo for `load_current`, keyed by store root then source id.
#:
#: A ContextVar rather than an instance attribute so the scope follows the
#: asyncio task or thread that opened it. The store is shared and long-lived;
#: concurrent requests must not see each other's memo, and PR 3 of OMN-16764
#: resolves candidates concurrently within one request.
_CURRENT_MEMO: ContextVar[dict[Path, dict[str, CurrentCodeProjection | None]] | None]
_CURRENT_MEMO = ContextVar("code_projection_current_memo", default=None)


class CodeProjectionArtifactStore:
    """Filesystem store with immutable objects and explicit current promotion."""

    def __init__(self, root: str | Path) -> None:
        # ``abspath`` anchors a relative operator path without resolving it
        # through a symlink.  Resolving here would silently turn a symlinked
        # store root into trusted storage at the link target.
        self._root = Path(os.path.abspath(Path(root)))
        _ensure_directory_chain(self._root)
        self._source_lock_guard = threading.Lock()
        self._source_thread_locks: dict[str, threading.Lock] = {}
        self._source_lock_owners: dict[str, int] = {}

    @property
    def root(self) -> Path:
        """Return the explicit store root without environment-derived defaults."""

        return self._root

    def _raw_path(self, digest: str) -> Path:
        return self._root / "objects" / "raw" / "sha256" / digest[:2] / digest

    def _batch_path(self, digest: str) -> Path:
        return (
            self._root
            / "objects"
            / "batches"
            / "sha256"
            / digest[:2]
            / f"{digest}.json"
        )

    def _state_path(self, source_id: str) -> Path:
        return self._root / "current" / "by-source" / f"{source_id}.json"

    def _lock_path(self, source_id: str) -> Path:
        return self._root / "locks" / "by-source" / f"{source_id}.lock"

    def _require_store_path(self, path: Path) -> None:
        try:
            path.relative_to(self._root)
        except ValueError as exc:  # pragma: no cover - all paths are internal
            raise _integrity_error("artifact path escapes the store root") from exc
        _validate_directory_chain(path.parent)

    def _ensure_store_path(self, path: Path) -> None:
        try:
            path.relative_to(self._root)
        except ValueError as exc:  # pragma: no cover - all paths are internal
            raise _integrity_error("artifact path escapes the store root") from exc
        _ensure_directory_chain(path.parent)

    def _read_store_file(self, path: Path, *, description: str) -> bytes:
        self._require_store_path(path)
        return _read_regular_file(path, description=description)

    def _caller_holds_source_lock(self, source_id: str) -> bool:
        caller = threading.get_ident()
        with self._source_lock_guard:
            return self._source_lock_owners.get(source_id) == caller

    @contextmanager
    def source_lock(self, source_id: str) -> Iterator[None]:
        """Serialize one source's read/build/apply/promote operator workflow."""

        if _SOURCE_ID_PATTERN.fullmatch(source_id) is None:
            raise ValueError("source_id must be a canonical code source ID")
        caller = threading.get_ident()
        with self._source_lock_guard:
            if self._source_lock_owners.get(source_id) == caller:
                raise RuntimeError("code projection source locks are not reentrant")
            thread_lock = self._source_thread_locks.setdefault(
                source_id,
                threading.Lock(),
            )

        # ``flock`` is the interprocess boundary.  This in-process lock also
        # gives separate threads deterministic blocking semantics instead of
        # relying on platform-specific flock behavior within one process.
        thread_lock.acquire()

        lock_path = self._lock_path(source_id)
        descriptor: int | None = None
        try:
            self._ensure_store_path(lock_path)
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(lock_path, flags, 0o600)
            except OSError as exc:
                raise _integrity_error("unable to open source lock") from exc
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise _integrity_error("source lock is not a regular file")
            os.fsync(descriptor)
            _sync_directory(lock_path.parent)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with self._source_lock_guard:
                if source_id in self._source_lock_owners:  # pragma: no cover
                    raise RuntimeError("source lock ownership is inconsistent")
                self._source_lock_owners[source_id] = caller
            try:
                yield
            finally:
                with self._source_lock_guard:
                    owner = self._source_lock_owners.pop(source_id, None)
                    if owner != caller:  # pragma: no cover - invariant guard
                        raise RuntimeError("source lock ownership was lost")
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            thread_lock.release()

    def stage_content_artifact(self, payload: bytes) -> StagedContentArtifact:
        """Persist and return a blob addressed by ``artifact://sha256/<digest>``."""

        digest = sha256_hex(payload)
        artifact_path = self._raw_path(digest)
        self._ensure_store_path(artifact_path)
        _write_immutable(
            artifact_path,
            payload,
            description="content artifact",
        )
        return StagedContentArtifact(
            content_hash_sha256=digest,
            artifact_path=artifact_path,
        )

    def read_content_artifact(self, digest: str) -> bytes:
        """Resolve and integrity-check one content-addressed artifact digest."""

        if _SHA256_PATTERN.fullmatch(digest) is None:
            raise ValueError("content artifact digest must be a canonical SHA-256")
        try:
            payload = self._read_store_file(
                self._raw_path(digest),
                description="content artifact",
            )
        except FileNotFoundError as exc:
            raise _integrity_error("content artifact is missing") from exc
        if sha256_hex(payload) != digest:
            raise _integrity_error("content artifact digest does not match")
        return payload

    def stage(
        self,
        *,
        raw_source: bytes,
        batch: ModelCodeProjectionBatch,
    ) -> StagedCodeProjection:
        """Atomically persist immutable inputs without advancing current state."""

        canonical_batch = serialize_code_projection_batch(batch)
        validated_batch = parse_code_projection_batch(canonical_batch)
        raw_digest = sha256_hex(raw_source)
        if raw_digest != validated_batch.source.raw_content_hash_sha256:
            raise ValueError("raw source digest does not match batch source")
        if len(raw_source) != validated_batch.source.byte_count:
            raise ValueError("raw source byte count does not match batch source")

        batch_digest = sha256_hex(canonical_batch)
        raw_artifact = self.stage_content_artifact(raw_source)
        raw_path = raw_artifact.artifact_path
        batch_path = self._batch_path(batch_digest)
        self._ensure_store_path(batch_path)
        _write_immutable(batch_path, canonical_batch, description="batch artifact")
        return StagedCodeProjection(
            source_id=validated_batch.source.source_id,
            batch_id=validated_batch.batch_id,
            raw_content_hash_sha256=raw_digest,
            batch_content_hash_sha256=batch_digest,
            raw_artifact_path=raw_path,
            batch_artifact_path=batch_path,
        )

    def _load_staged(self, staged: StagedCodeProjection) -> CurrentCodeProjection:
        if _SOURCE_ID_PATTERN.fullmatch(staged.source_id) is None:
            raise _integrity_error("staged source_id is invalid")
        if _BATCH_ID_PATTERN.fullmatch(staged.batch_id) is None:
            raise _integrity_error("staged batch_id is invalid")
        for digest, name in (
            (staged.raw_content_hash_sha256, "raw content"),
            (staged.batch_content_hash_sha256, "batch content"),
        ):
            if _SHA256_PATTERN.fullmatch(digest) is None:
                raise _integrity_error(f"staged {name} digest is invalid")

        expected_raw_path = self._raw_path(staged.raw_content_hash_sha256)
        expected_batch_path = self._batch_path(staged.batch_content_hash_sha256)
        if staged.raw_artifact_path != expected_raw_path:
            raise _integrity_error("staged raw artifact path does not match its digest")
        if staged.batch_artifact_path != expected_batch_path:
            raise _integrity_error(
                "staged batch artifact path does not match its digest"
            )

        batch_bytes = self._read_store_file(
            expected_batch_path, description="batch artifact"
        )
        if sha256_hex(batch_bytes) != staged.batch_content_hash_sha256:
            raise _integrity_error("staged batch artifact digest does not match")
        try:
            batch = parse_code_projection_batch(batch_bytes)
        except ValueError as exc:
            raise _integrity_error("staged batch artifact is not canonical") from exc
        if batch.source.source_id != staged.source_id:
            raise _integrity_error("staged source_id does not match batch")
        if batch.batch_id != staged.batch_id:
            raise _integrity_error("staged batch_id does not match batch")
        if batch.source.raw_content_hash_sha256 != staged.raw_content_hash_sha256:
            raise _integrity_error("staged raw digest does not match batch")

        raw_bytes = self._read_store_file(
            expected_raw_path,
            description="raw artifact",
        )
        if sha256_hex(raw_bytes) != staged.raw_content_hash_sha256:
            raise _integrity_error("staged raw artifact digest does not match")
        if len(raw_bytes) != batch.source.byte_count:
            raise _integrity_error("staged raw artifact byte count does not match")
        self._validate_contracted_artifacts(batch, raw_source=raw_bytes)
        return CurrentCodeProjection(
            batch=batch,
            raw_artifact_path=expected_raw_path,
            batch_artifact_path=expected_batch_path,
            state_path=self._state_path(staged.source_id),
            batch_content_hash_sha256=staged.batch_content_hash_sha256,
        )

    def mark_applied(self, staged: StagedCodeProjection) -> CurrentCodeProjection:
        """Advance current state after the caller has successfully applied a batch."""

        if not self._caller_holds_source_lock(staged.source_id):
            raise RuntimeError(
                "mark_applied requires the matching source_lock to be held"
            )

        incoming = self._load_staged(staged)
        # Drop any memo entry first: this is the write path, and a cached
        # projection would make the replay decision against stale truth. The
        # public method is used deliberately -- it is the seam callers and
        # tests patch to observe promotion.
        self._invalidate_current(staged.source_id)
        current = self.load_current(staged.source_id)
        if current is not None:
            replay = plan_code_projection_replay(
                incoming.batch,
                current.batch.manifest,
            )
            if replay.decision == "noop":
                return current
            if replay.decision in {"stale", "conflict"}:
                raise ValueError(
                    f"cannot mark {replay.decision} code projection as applied"
                )

        state = _CurrentState(
            source_id=incoming.batch.source.source_id,
            tenant_id=incoming.batch.source.tenant_id,
            repository_id=incoming.batch.source.repository_id,
            relative_path=incoming.batch.source.relative_path,
            batch_id=incoming.batch.batch_id,
            operation=incoming.batch.operation,
            raw_content_hash_sha256=incoming.batch.source.raw_content_hash_sha256,
            batch_content_hash_sha256=incoming.batch_content_hash_sha256,
        )
        self._ensure_store_path(incoming.state_path)
        _atomic_replace(
            incoming.state_path, canonical_json_bytes(state.to_wire()) + b"\n"
        )
        # Invalidate again so an enclosing read scope cannot serve the
        # pre-promotion projection either here or after this returns.
        self._invalidate_current(staged.source_id)
        promoted = self.load_current(staged.source_id)
        if (
            promoted is None
        ):  # pragma: no cover - atomic replace either succeeds or raises
            raise _integrity_error("current state disappeared after atomic promotion")
        return promoted

    @contextmanager
    def memoized_current(self) -> Iterator[None]:
        """Memoize `load_current` for the duration of a read-only scope.

        Serving one context pack calls `load_current` once per candidate plus
        once per source inside search's current-generation check, and each call
        re-reads and re-verifies every semantic document in the whole batch.
        Candidates sharing a source therefore pay the full cost repeatedly.

        Deliberately opt-in. `mark_applied` reads current state immediately
        after replacing it, so an always-on cache would hand the write path its
        own stale value. Callers that mutate state must not wrap themselves in
        this scope, and `mark_applied` bypasses and invalidates the memo even if
        they do.

        Nesting reuses the active memo rather than resetting it.
        """

        if _CURRENT_MEMO.get() is not None:
            yield
            return
        token = _CURRENT_MEMO.set({})
        try:
            yield
        finally:
            _CURRENT_MEMO.reset(token)

    def _memo(self) -> dict[str, CurrentCodeProjection | None] | None:
        """Return this store's memo for the active scope, or None outside one."""

        memos = _CURRENT_MEMO.get()
        if memos is None:
            return None
        return memos.setdefault(self._root, {})

    def _invalidate_current(self, source_id: str) -> None:
        """Drop any memoized projection for ``source_id`` in the active scope."""

        memo = self._memo()
        if memo is not None:
            memo.pop(source_id, None)

    def load_current(self, source_id: str) -> CurrentCodeProjection | None:
        """Load and fully validate current state for one stable source ID.

        Inside `memoized_current()` the result is served from the scope's memo
        on repeat calls; outside one, every call does the full read-and-verify.
        """

        if _SOURCE_ID_PATTERN.fullmatch(source_id) is None:
            raise ValueError("source_id must be a canonical code source ID")

        memo = self._memo()
        if memo is not None and source_id in memo:
            return memo[source_id]

        current = self._load_current_uncached(source_id)
        if memo is not None:
            memo[source_id] = current
        return current

    def _load_current_uncached(self, source_id: str) -> CurrentCodeProjection | None:
        """Read and fully validate current state, never consulting the memo."""

        state_path = self._state_path(source_id)
        try:
            state_bytes = self._read_store_file(
                state_path,
                description="current state",
            )
        except FileNotFoundError:
            return None
        state = _parse_current_state(state_bytes)
        if state.source_id != source_id:
            raise _integrity_error(
                "current state source_id does not match its filename"
            )

        batch_path = self._batch_path(state.batch_content_hash_sha256)
        try:
            batch_bytes = self._read_store_file(
                batch_path,
                description="batch artifact",
            )
        except FileNotFoundError as exc:
            raise _integrity_error("current batch artifact is missing") from exc
        if sha256_hex(batch_bytes) != state.batch_content_hash_sha256:
            raise _integrity_error("current batch artifact digest does not match state")
        try:
            batch = parse_code_projection_batch(batch_bytes)
        except ValueError as exc:
            raise _integrity_error("current batch artifact is not canonical") from exc

        expected_state = _CurrentState(
            source_id=batch.source.source_id,
            tenant_id=batch.source.tenant_id,
            repository_id=batch.source.repository_id,
            relative_path=batch.source.relative_path,
            batch_id=batch.batch_id,
            operation=batch.operation,
            raw_content_hash_sha256=batch.source.raw_content_hash_sha256,
            batch_content_hash_sha256=state.batch_content_hash_sha256,
        )
        if state != expected_state:
            raise _integrity_error("current state does not exactly describe its batch")

        raw_path = self._raw_path(state.raw_content_hash_sha256)
        try:
            raw_bytes = self._read_store_file(
                raw_path,
                description="raw artifact",
            )
        except FileNotFoundError as exc:
            raise _integrity_error("current raw artifact is missing") from exc
        if sha256_hex(raw_bytes) != state.raw_content_hash_sha256:
            raise _integrity_error("current raw artifact digest does not match state")
        if len(raw_bytes) != batch.source.byte_count:
            raise _integrity_error(
                "current raw artifact byte count does not match batch"
            )
        self._validate_contracted_artifacts(batch, raw_source=raw_bytes)

        return CurrentCodeProjection(
            batch=batch,
            raw_artifact_path=raw_path,
            batch_artifact_path=batch_path,
            state_path=state_path,
            batch_content_hash_sha256=state.batch_content_hash_sha256,
        )

    def load_current_batch(self, source_id: str) -> ModelCodeProjectionBatch | None:
        """Load the canonical current batch for ``source_id``, if one exists."""

        current = self.load_current(source_id)
        return current.batch if current is not None else None

    def find_current(
        self,
        *,
        tenant_id: str,
        repository_id: str,
        relative_path: str,
    ) -> CurrentCodeProjection | None:
        """Find current state by canonical logical repository and relative path."""

        canonical_tenant_id = normalize_tenant_id(tenant_id)
        canonical_repository_id = normalize_repository_id(repository_id)
        canonical_relative_path = normalize_relative_path(relative_path)
        state_root = self._root / "current" / "by-source"
        try:
            _validate_directory_chain(state_root)
        except FileNotFoundError:
            return None

        for state_path in sorted(state_root.iterdir(), key=lambda path: path.name):
            if not state_path.name.endswith(".json"):
                continue
            source_id = state_path.name.removesuffix(".json")
            if _SOURCE_ID_PATTERN.fullmatch(source_id) is None:
                continue
            current = self.load_current(source_id)
            if current is None:  # pragma: no cover - concurrent unlink only
                continue
            source = current.batch.source
            if (
                source.tenant_id == canonical_tenant_id
                and source.repository_id == canonical_repository_id
                and source.relative_path == canonical_relative_path
            ):
                return current
        return None

    def find_current_batch(
        self,
        *,
        tenant_id: str,
        repository_id: str,
        relative_path: str,
    ) -> ModelCodeProjectionBatch | None:
        """Find the canonical current batch by logical source identity."""

        current = self.find_current(
            tenant_id=tenant_id,
            repository_id=repository_id,
            relative_path=relative_path,
        )
        return current.batch if current is not None else None

    def _resolve_artifact_ref(self, artifact_ref: str, *, description: str) -> bytes:
        digest = artifact_ref.removeprefix(_ARTIFACT_REF_PREFIX)
        if (
            not artifact_ref.startswith(_ARTIFACT_REF_PREFIX)
            or _SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise _integrity_error(f"{description} artifact reference is invalid")
        try:
            return self.read_content_artifact(digest)
        except CodeProjectionArtifactIntegrityError as exc:
            raise _integrity_error(
                f"{description} artifact reference does not resolve exactly"
            ) from exc

    def _validate_contracted_artifacts(
        self,
        batch: ModelCodeProjectionBatch,
        *,
        raw_source: bytes,
    ) -> None:
        source_bytes = self._resolve_artifact_ref(
            batch.source.artifact_ref,
            description="source raw",
        )
        if source_bytes != raw_source:
            raise _integrity_error(
                "source raw artifact reference does not match staged bytes"
            )

        transform_manifest = self._resolve_artifact_ref(
            batch.provenance.transform_manifest_ref,
            description="provenance transform manifest",
        )
        if (
            sha256_hex(transform_manifest)
            != batch.provenance.transform_manifest_hash_sha256
        ):
            raise _integrity_error(
                "provenance transform manifest digest does not match contract"
            )

        for document in batch.semantic_documents:
            content = self._resolve_artifact_ref(
                document.content_ref,
                description=f"semantic document {document.document_id}",
            )
            if sha256_hex(content) != document.sanitized_content_hash_sha256:
                raise _integrity_error(
                    "semantic document digest does not match contract"
                )
            if len(content) != document.byte_count:
                raise _integrity_error(
                    "semantic document byte count does not match contract"
                )

        for edge in batch.edges:
            for evidence_ref in edge.evidence_refs:
                self._resolve_artifact_ref(
                    evidence_ref,
                    description=f"edge {edge.edge_id} evidence",
                )


__all__ = [
    "CodeProjectionArtifactIntegrityError",
    "CodeProjectionArtifactStore",
    "CurrentCodeProjection",
    "StagedContentArtifact",
    "StagedCodeProjection",
]
