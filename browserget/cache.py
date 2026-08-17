"""Cache directory management for browserget."""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from browserget.config import load_config


def get_cache_dir() -> Path:
    """Return the cache directory, creating it if it does not exist.

    Returns:
        The path to the cache directory.

    Raises:
        OSError: If the directory cannot be created (e.g. read-only filesystem).
    """
    cache_dir = load_config().cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _validate_path_component(component: str) -> str:
    """Validate that a string is safe to use as a single path component.

    Rejects empty strings, strings containing path separators (``/`` or ``\\``),
    and the ``..`` traversal sequence.  This prevents path-traversal attacks
    when version strings or names from upstream APIs are used to construct
    filesystem paths.

    Args:
        component: The string to validate.

    Returns:
        The validated string.

    Raises:
        ValueError: If the component contains path separators or ``..``.
    """
    if not component or component == ".." or component == ".":
        raise ValueError(f"Unsafe path component: {component!r}")
    if "\x00" in component:
        raise ValueError(f"Path component contains null byte: {component!r}")
    if "/" in component or "\\" in component:
        raise ValueError(f"Path component contains separator: {component!r}")
    # Reject any component that resolves to a parent path
    if Path(component).parts != (component,):
        raise ValueError(f"Path component is not a single segment: {component!r}")
    return component


def get_artifact_dir(name: str, version: str) -> Path:
    """Return the directory path for a specific artifact version.

    Args:
        name: Artifact name (e.g. "chrome", "chromedriver").
        version: Artifact version string.

    Returns:
        The path ``{cache_dir}/{name}/{version}/``.

    Raises:
        ValueError: If *name* or *version* contains path separators or
            traversal sequences (``..``).
    """
    _validate_path_component(name)
    _validate_path_component(version)
    return get_cache_dir() / name / version


def get_download_dir() -> Path:
    """Return the temporary download directory inside the cache.

    Returns:
        The path ``{cache_dir}/downloads/``.
    """
    return get_cache_dir() / "downloads"


def safe_download_path(download_dir: Path, filename: str) -> Path:
    """Construct a safe download path, rejecting path traversal in *filename*.

    Args:
        download_dir: The base download directory.
        filename: The filename to append (typically extracted from a URL).

    Returns:
        The resolved path inside *download_dir*.

    Raises:
        ValueError: If *filename* contains path separators or ``..``
            sequences that would escape *download_dir*.
    """
    _validate_path_component(filename)
    return download_dir / filename


def cleanup_downloads() -> None:
    """Delete all contents of the download directory.

    Individual deletion errors are suppressed so that one locked file
    does not prevent cleanup of the remaining items.
    """
    download_dir = get_download_dir()
    if download_dir.is_symlink():
        download_dir.unlink()
        return
    if not download_dir.exists():
        return
    for item in download_dir.iterdir():
        try:
            if item.is_symlink():
                item.unlink()
            elif item.is_dir():
                safe_rmtree(item)
            else:
                item.unlink()
        except OSError:
            pass


def safe_rmtree(path: Path) -> None:
    """Remove a directory tree, handling symlinks safely.

    If *path* is a symlink, the symlink itself is unlinked rather than
    recursing into its target. This prevents accidental deletion of
    files outside the cache when ``path`` points elsewhere via a symlink.

    Args:
        path: Directory path to remove.
    """
    if path.is_symlink():
        path.unlink()
        return
    shutil.rmtree(path)


def check_disk_space(required_mb: int) -> bool:
    """Check if there is enough disk space for an installation.

    Args:
        required_mb: Required space in megabytes.

    Returns:
        True if available space is sufficient, False otherwise.
    """
    cache_dir = get_cache_dir()
    check_dir = cache_dir if cache_dir.exists() else Path.home()
    usage = shutil.disk_usage(check_dir)
    return usage.free >= required_mb * 1024 * 1024


def get_available_disk_mb() -> int:
    """Return available disk space in megabytes.

    Returns:
        Available space in MB at the cache directory location.
    """
    cache_dir = get_cache_dir()
    check_dir = cache_dir if cache_dir.exists() else Path.home()
    usage = shutil.disk_usage(check_dir)
    return usage.free // (1024 * 1024)


def get_cache_size() -> int:
    """Return the total size of the cache directory in bytes.

    Returns:
        Total bytes in the cache directory (recursive), or 0 if the
        directory does not exist.
    """
    cache_dir = load_config().cache_dir
    if not cache_dir.exists():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(cache_dir, followlinks=False):
        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.is_symlink():
                continue
            with contextlib.suppress(OSError):
                total += filepath.stat().st_size
    return total
