"""Safe archive extraction utilities with path-traversal protection.

All extraction functions validate that every entry in the archive resolves
to a path inside the destination directory, preventing Zip Slip and similar
path-traversal attacks.
"""

from __future__ import annotations

import os
import stat
import sys
import tarfile
import zipfile
from pathlib import Path


def _safe_extract_path(dest: Path, member_name: str) -> Path:
    """Resolve *member_name* relative to *dest* and verify it stays inside.

    Args:
        dest: The destination directory.
        member_name: The archive member's relative path.

    Returns:
        The resolved, validated path.

    Raises:
        ValueError: If the resolved path escapes *dest*.
    """
    dest_resolved = dest.resolve()
    target = (dest / member_name).resolve()
    try:
        target.relative_to(dest_resolved)
    except ValueError as exc:
        raise ValueError(f"Archive entry '{member_name}' escapes destination directory") from exc
    return target


def extract_zip(archive_path: Path, dest: Path) -> None:
    """Extract a zip archive safely, preventing path traversal.

    Validates both member paths and symlink targets to prevent
    path-traversal attacks via malicious symlinks.

    Args:
        archive_path: Path to the zip file.
        dest: Destination directory (must exist).

    Raises:
        ValueError: If any entry escapes the destination directory.
        zipfile.BadZipFile: If the archive is corrupt or not a zip file.
    """
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.infolist():
            _safe_extract_path(dest, member.filename)
            unix_mode = member.external_attr >> 16
            if stat.S_ISLNK(unix_mode):
                link_target = zf.read(member).decode("utf-8", errors="replace")
                _safe_extract_path(dest, link_target)
        zf.extractall(dest)


def extract_tar(archive_path: Path, dest: Path) -> None:
    """Extract a tar archive safely, preventing path traversal.

    Automatically detects compression (gzip, bzip2, xz, or uncompressed).
    Validates both member paths and symlink/hardlink targets to prevent
    path-traversal attacks via malicious symlinks.

    Args:
        archive_path: Path to the tar file.
        dest: Destination directory (must exist).

    Raises:
        ValueError: If any entry escapes the destination directory.
        tarfile.TarError: If the archive is corrupt.
    """
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive_path), "r:*") as tf:
        for member in tf.getmembers():
            _safe_extract_path(dest, member.name)
            if member.issym() or member.islnk():
                _safe_extract_path(dest, member.linkname)
        if sys.version_info >= (3, 12):
            tf.extractall(dest, filter="data")
        else:
            for member in tf.getmembers():
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise ValueError(f"Refusing to extract special file: {member.name!r}")
            tf.extractall(dest)


def find_file_by_name(root: Path, filename: str) -> Path | None:
    """Find a file by name in a directory tree without following symlinks.

    Uses ``os.walk(followlinks=False)`` to avoid infinite recursion from
    circular symlinks that may exist in extracted archives.

    Args:
        root: The root directory to search.
        filename: The filename to match (basename only).

    Returns:
        The first matching file path, or ``None`` if not found.
    """
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for fname in filenames:
            if fname == filename:
                candidate = Path(dirpath) / fname
                if not candidate.is_symlink() and candidate.is_file():
                    return candidate
    return None
