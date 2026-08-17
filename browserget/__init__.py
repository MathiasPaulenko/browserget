"""browserget — Standalone CLI to install browsers and drivers without any framework."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from browserget.config import Config, load_config
from browserget.exceptions import (
    AlreadyInstalledError,
    BrowsergetError,
    ChecksumMismatchError,
    DriverMatchError,
    InsufficientDiskSpaceError,
    NetworkError,
    UnknownTargetError,
    UnsupportedPlatformError,
    VersionNotFoundError,
)
from browserget.models import InstalledArtifact, ResolvedVersion, SystemBrowser
from browserget.platform import OS, Arch, Platform, detect_platform

try:
    __version__ = _pkg_version("browserget")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "AlreadyInstalledError",
    "Arch",
    "BrowsergetError",
    "ChecksumMismatchError",
    "Config",
    "DriverMatchError",
    "InsufficientDiskSpaceError",
    "InstalledArtifact",
    "NetworkError",
    "OS",
    "Platform",
    "ResolvedVersion",
    "SystemBrowser",
    "UnknownTargetError",
    "UnsupportedPlatformError",
    "VersionNotFoundError",
    "__version__",
    "detect_platform",
    "load_config",
]
