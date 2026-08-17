"""Configuration loading from environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _default_cache_dir() -> Path:
    """Return the platform-appropriate default cache directory.

    Returns:
        ``%LOCALAPPDATA%\\browserget`` on Windows, ``~/.browserget`` elsewhere.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "browserget"
        return Path.home() / "AppData" / "Local" / "browserget"
    return Path.home() / ".browserget"


def _parse_int(value: str, default: int) -> int:
    """Parse an integer from a string, falling back to ``default`` on failure.

    Args:
        value: The string to parse.
        default: The fallback value if parsing fails.

    Returns:
        The parsed integer or the default.
    """
    try:
        return int(value)
    except ValueError:
        return default


def _parse_bool(value: str) -> bool:
    """Parse a boolean from a string.

    ``"1"``, ``"true"``, ``"yes"`` (case-insensitive) → ``True``.
    All other values → ``False``.

    Args:
        value: The string to parse.

    Returns:
        The parsed boolean.
    """
    return value.lower() in ("1", "true", "yes")


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for browserget.

    Attributes:
        cache_dir: Directory for downloaded browser/driver artifacts.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of HTTP retry attempts.
        verbose: Whether to enable verbose logging output.
    """

    cache_dir: Path
    timeout: int = 30
    max_retries: int = 3
    verbose: bool = False


def load_config() -> Config:
    """Load configuration from environment variables with defaults.

    Reads ``BROWSERGET_CACHE_DIR``, ``BROWSERGET_TIMEOUT``,
    ``BROWSERGET_MAX_RETRIES``, and ``BROWSERGET_VERBOSE``.

    Returns:
        A ``Config`` instance populated from env vars or defaults.
    """
    cache_dir_str = os.environ.get("BROWSERGET_CACHE_DIR")
    cache_dir = Path(cache_dir_str) if cache_dir_str else _default_cache_dir()

    timeout = _parse_int(os.environ.get("BROWSERGET_TIMEOUT", ""), 30)
    max_retries = _parse_int(os.environ.get("BROWSERGET_MAX_RETRIES", ""), 3)

    if timeout < 1:
        timeout = 30
    if max_retries < 0:
        max_retries = 3

    verbose_str = os.environ.get("BROWSERGET_VERBOSE", "")
    verbose = _parse_bool(verbose_str) if verbose_str else False

    return Config(
        cache_dir=cache_dir,
        timeout=timeout,
        max_retries=max_retries,
        verbose=verbose,
    )
