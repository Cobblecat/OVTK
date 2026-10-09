"""Windows-only native operations for the qualified publish-new adapter."""

from __future__ import annotations

import ctypes
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
from functools import lru_cache
from pathlib import Path

from operational_variance_toolkit.errors import OutputExistsError, PublicationError


@lru_cache(maxsize=1)
def _kernel():
    if sys.platform != "win32":
        raise PublicationError("Publish-new is unqualified on this platform; G1-P is deferred")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumePathNameW.restype = wintypes.BOOL
    kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel.GetDriveTypeW.restype = wintypes.UINT
    kernel.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel.GetVolumeInformationW.restype = wintypes.BOOL
    kernel.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    kernel.MoveFileExW.restype = wintypes.BOOL
    return kernel


def _native(path: Path) -> str:
    return "\\\\?\\" + str(path)


def _failure(operation: str) -> PublicationError:
    return PublicationError(f"{operation} failed (Windows error {ctypes.get_last_error()})")


def reject_reparse(path: Path) -> None:
    metadata = path.lstat()
    if metadata.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise PublicationError(f"Publication path is redirected: {path}")


def qualify_destination(destination: Path) -> int:
    """Check OS and existing parent without creating any public/private paths."""
    if sys.platform != "win32":
        raise PublicationError("Publish-new is unqualified on this platform; G1-P is deferred")
    kernel = _kernel()
    import winreg

    if sys.version_info[:2] != (3, 14):
        raise PublicationError("Publish-new requires the qualified CPython 3.14 runtime")
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    ) as key:
        build = int(winreg.QueryValueEx(key, "CurrentBuild")[0])
        revision = int(winreg.QueryValueEx(key, "UBR")[0])
        edition = winreg.QueryValueEx(key, "EditionID")[0]
        display = winreg.QueryValueEx(key, "DisplayVersion")[0]
    if edition != "Core" or display != "25H2" or build != 26200 or revision < 9457:
        raise PublicationError("Publish-new is unqualified on this Windows configuration")
    if not destination.drive or len(destination.drive) != 2 or destination.drive[1] != ":":
        raise PublicationError("Publish-new requires a local fixed NTFS volume")
    if os.path.isreserved(destination):
        raise PublicationError(f"Reserved publication destination: {destination}")
    parent = destination.parent
    for component in (parent, *parent.parents):
        reject_reparse(component)
        if not component.is_dir():
            raise PublicationError(f"Publication parent is not a directory: {component}")
    volume = ctypes.create_unicode_buffer(32768)
    if not kernel.GetVolumePathNameW(_native(parent), volume, len(volume)):
        raise _failure("Volume lookup")
    if kernel.GetDriveTypeW(volume.value) != 3:  # DRIVE_FIXED
        raise PublicationError("Publish-new rejects network and non-fixed volumes")
    serial, maximum, flags = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    filesystem = ctypes.create_unicode_buffer(64)
    if not kernel.GetVolumeInformationW(
        volume.value,
        None,
        0,
        ctypes.byref(serial),
        ctypes.byref(maximum),
        ctypes.byref(flags),
        filesystem,
        len(filesystem),
    ):
        raise _failure("Filesystem lookup")
    if filesystem.value != "NTFS" or not flags.value & 8:  # FILE_PERSISTENT_ACLS
        raise PublicationError("Publish-new requires local NTFS with persistent ACLs")
    return serial.value


@contextmanager
def directory_handle(path: Path, *, share_delete: bool = True) -> Iterator[int]:
    """Keep an object identity alive, without claiming to pin its namespace.

    Attributes-only access does not establish a data/delete sharing conflict.
    The caller compares identities at its lifecycle boundaries; concurrent
    same-privilege namespace mutation is not a guarantee of this adapter.
    """
    kernel = _kernel()
    # FILE_READ_ATTRIBUTES, share read/write (+delete for invocation-owned stage),
    # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
    handle = kernel.CreateFileW(
        _native(path), 0x80, 3 | (4 if share_delete else 0), None, 3, 0x02000000 | 0x00200000, None
    )
    if handle == ctypes.c_void_p(-1).value:
        raise _failure("Open publication directory")
    try:
        yield handle
    finally:
        kernel.CloseHandle(handle)


def handle_identity(handle: int) -> tuple[int, bytes]:
    class FileIdInfo(ctypes.Structure):
        _fields_ = [("volume", ctypes.c_ulonglong), ("file_id", ctypes.c_ubyte * 16)]

    info = FileIdInfo()
    if not _kernel().GetFileInformationByHandleEx(
        handle, 18, ctypes.byref(info), ctypes.sizeof(info)
    ):
        raise _failure("Read publication handle identity")
    return info.volume, bytes(info.file_id)


def move_no_replace(source: Path, destination: Path) -> None:
    # No REPLACE_EXISTING, COPY_ALLOWED, deferred move, or durability flags.
    if not _kernel().MoveFileExW(_native(source), _native(destination), 0):
        error = ctypes.get_last_error()
        if error in {80, 183} or os.path.lexists(destination):
            raise OutputExistsError(f"Output already exists: {destination}")
        raise _failure("No-replace publication")
