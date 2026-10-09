"""Invocation-owned staging and Windows/NTFS no-replace publication.

POSIX is deliberately disabled pending native G1-P qualification. Existing
producers adopt this boundary in Phase 5; there is no legacy fallback here.
Atomic visibility is distinct from crash durability, which is not promised.
"""

from __future__ import annotations

import os
import shutil
import stat
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from operational_variance_toolkit.errors import (
    OutputExistsError,
    PublicationError,
    PublicationOwnershipError,
)
from operational_variance_toolkit.storage import _windows_publication as native


def _abs(path: str | Path) -> Path:
    # resolve() would conceal a redirected parent before the rejection checks.
    return Path(os.path.abspath(path))


def _absent(path: Path) -> None:
    if os.path.lexists(path):
        raise OutputExistsError(f"Output already exists: {path}")


class NewPublication:
    """One invocation's payload. Construct through publish_new, not directly."""

    def __init__(
        self, destination: Path, stage: Path, stage_handle: int, parent_identity: tuple[int, bytes]
    ) -> None:
        self.destination = destination
        self._stage = stage
        self._stage_identity = native.handle_identity(stage_handle)
        self._parent_identity = parent_identity
        self._closed = False
        self._committed = False

    @property
    def staged_path(self) -> Path:
        return self._stage / "artifact"

    @property
    def staged_sidecar(self) -> Path:
        return self._stage / "sidecar"

    def _owned(self) -> None:
        if self._closed:
            raise PublicationOwnershipError("Publication invocation is closed")
        try:
            native.reject_reparse(self._stage)
            with native.directory_handle(self._stage) as handle:
                identity = native.handle_identity(handle)
            with native.directory_handle(self.destination.parent) as handle:
                parent = native.handle_identity(handle)
            if identity != self._stage_identity or parent != self._parent_identity:
                raise PublicationOwnershipError("Publication staging ownership changed")
        except (OSError, PublicationError) as exc:
            raise PublicationOwnershipError(
                f"Cannot establish staging ownership; retained at {self._stage}: {exc}"
            ) from exc

    def _payload(self, path: Path) -> None:
        native.reject_reparse(path)
        if not (stat.S_ISREG(path.lstat().st_mode) or stat.S_ISDIR(path.lstat().st_mode)):
            raise PublicationError("Publication payload must be a regular file or directory")
        if path.stat().st_dev != self._stage.stat().st_dev:
            raise PublicationError("Cross-volume publication is unsupported")

    def commit(self, *, verify: Callable[[Path], None]) -> Path:
        """Verify and publish one completed file/directory without replacement."""
        self._prepare(verify)
        native.move_no_replace(self.staged_path, self.destination)
        self._committed = True
        return self.destination

    def _prepare(self, verify: Callable[[Path], None]) -> None:
        self._owned()
        if self._committed or not callable(verify):
            raise PublicationError("Publication requires one commit and a semantic verifier")
        native.qualify_destination(self.destination)
        _absent(self.destination)
        self._payload(self.staged_path)
        verify(self.staged_path)
        self._owned()
        self._payload(self.staged_path)

    def commit_pair(
        self, sidecar_destination: str | Path, *, verify: Callable[[Path], None]
    ) -> Path:
        """Sidecar first, database last. Retain any orphan public sidecar on failure.

        verify receives the private container containing artifact and sidecar.
        Future adopting readers must reject incomplete or mismatched pairs.
        """
        sidecar = _abs(sidecar_destination)
        if not callable(verify):
            raise PublicationError("Publication requires a semantic verifier")
        if sidecar.parent != self.destination.parent or sidecar == self.destination:
            raise PublicationError("A readiness pair requires distinct names in one parent")
        self._prepare(lambda _: verify(self._stage))
        native.qualify_destination(sidecar)
        _absent(sidecar)
        self._payload(self.staged_sidecar)
        if not self.staged_path.is_file() or not self.staged_sidecar.is_file():
            raise PublicationError("A readiness pair requires two regular files")
        native.move_no_replace(self.staged_sidecar, sidecar)
        try:
            native.move_no_replace(self.staged_path, self.destination)
        except (OSError, PublicationError, OutputExistsError) as exc:
            raise PublicationError(
                f"Readiness pair incomplete; sidecar retained at {sidecar}; "
                f"database was not published by this invocation: {exc}"
            ) from exc
        self._committed = True
        return self.destination


@contextmanager
def publish_new(destination: str | Path) -> Iterator[NewPublication]:
    """Fail closed before staging on unqualified configurations.

    The caller creates the complete artifact at staged_path, then commits with
    its semantic verifier. On failure only the proven invocation-owned private
    container is cleaned. Public names are never removed, even after a commit.
    """
    final = _abs(destination)
    native.qualify_destination(final)
    _absent(final)
    with native.directory_handle(final.parent, share_delete=False) as parent_handle:
        stage = final.parent / f".ovtk-stage-{uuid.uuid4().hex}"
        # CPython 3.14 Windows mode0700 grants only this user and administrators.
        stage.mkdir(mode=0o700)
        invocation = None
        try:
            with native.directory_handle(stage) as stage_handle:
                invocation = NewPublication(
                    final, stage, stage_handle, native.handle_identity(parent_handle)
                )
                try:
                    yield invocation
                finally:
                    invocation._owned()
                    try:
                        shutil.rmtree(stage)
                    except OSError as exc:
                        raise PublicationOwnershipError(
                            f"Owned staging cleanup failed; retained at {stage}: {exc}"
                        ) from exc
                    finally:
                        invocation._closed = True
        except BaseException:
            if invocation is None:
                raise PublicationOwnershipError(
                    f"Staging handle ownership unavailable; retained at {stage}"
                )
            raise
