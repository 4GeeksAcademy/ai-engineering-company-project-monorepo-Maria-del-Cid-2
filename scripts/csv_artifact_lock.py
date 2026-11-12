"""Cross-process locks for CSV artifacts on a shared Docker volume.

Lock files live in ``.locks`` next to the artifacts. POSIX uses ``flock``;
Windows uses a one-byte ``msvcrt`` lock. The OS releases either lock when its
owning process exits, so a container restart cannot leave a stale held lock.
Lock files themselves are deliberately never removed (avoiding inode races).
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import errno
from typing import IO, Iterator


class LockBusyError(BlockingIOError):
    """Raised when a non-blocking shared-volume lock is already held."""


def _try_lock(handle: IO[bytes], blocking: bool) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
            handle.flush()
            handle.seek(0)
        mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        try:
            msvcrt.locking(handle.fileno(), mode, 1)
        except OSError as exc:
            if not blocking and (
                getattr(exc, "winerror", None) in {32, 33}
                or exc.errno in {errno.EACCES, errno.EDEADLK}
            ):
                raise LockBusyError("shared-volume lock is already held") from exc
            raise
        return

    import fcntl

    flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    try:
        fcntl.flock(handle.fileno(), flags)
    except BlockingIOError as exc:
        raise LockBusyError("shared-volume lock is already held") from exc


def _unlock(handle: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def shared_file_lock(lock_path: Path, *, blocking: bool = True) -> Iterator[None]:
    """Hold an OS-managed lock at ``lock_path`` until the context exits."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        _try_lock(handle, blocking)
        try:
            yield
        finally:
            _unlock(handle)


def artifact_lock_path(artifact_path: Path) -> Path:
    """Return the stable shared lock-file path for one published artifact."""
    return artifact_path.parent / ".locks" / f"{artifact_path.name}.lock"


@contextmanager
def artifact_lock(artifact_path: Path, *, blocking: bool = True) -> Iterator[None]:
    """Coordinate a publisher and cleaner for the same artifact path."""
    with shared_file_lock(artifact_lock_path(artifact_path), blocking=blocking):
        yield
