"""Platform detection and upstream API string mapping."""

from __future__ import annotations

import platform as _platform
import sys
from dataclasses import dataclass
from enum import StrEnum

from browserget.exceptions import UnsupportedPlatformError


class OS(StrEnum):
    """Operating system type."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class Arch(StrEnum):
    """CPU architecture type."""

    X64 = "x64"
    ARM64 = "arm64"
    X86 = "x86"


@dataclass(frozen=True, slots=True)
class Platform:
    """Detected platform combining OS and architecture.

    Attributes:
        os: The operating system.
        arch: The CPU architecture.
    """

    os: OS
    arch: Arch


def detect_os() -> OS:
    """Detect the operating system from ``sys.platform``.

    Returns:
        The detected ``OS`` member.

    Raises:
        UnsupportedPlatformError: If the OS is not Windows, macOS, or Linux.
    """
    if sys.platform == "win32":
        return OS.WINDOWS
    if sys.platform == "darwin":
        return OS.MACOS
    if sys.platform.startswith("linux"):
        return OS.LINUX
    raise UnsupportedPlatformError(platform=sys.platform, name="browserget")


def detect_arch() -> Arch:
    """Detect the CPU architecture from ``platform.machine()``.

    Normalizes ``arm64``, ``aarch64``, and ``ARM64`` to ``Arch.ARM64``,
    and 32-bit x86 variants (``i386``, ``i686``, ``x86``, ...) to
    ``Arch.X86``. All other values default to ``Arch.X64``.

    Returns:
        The detected ``Arch`` member.
    """
    machine = _platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return Arch.ARM64
    if machine in ("x86", "i386", "i486", "i586", "i686", "ia32", "x86_32"):
        return Arch.X86
    return Arch.X64


def detect_platform() -> Platform:
    """Detect the current platform (OS + architecture).

    Returns:
        A ``Platform`` instance combining the detected OS and architecture.
    """
    return Platform(os=detect_os(), arch=detect_arch())


def map_platform(platform: Platform, source: str) -> str:
    """Map a ``Platform`` to an upstream API platform string.

    Args:
        platform: The detected platform.
        source: The upstream API name (``"cft"``, ``"firefox"``, ``"edge"``,
            or ``"geckodriver"``).

    Returns:
        The platform string expected by the upstream API.

    Raises:
        UnsupportedPlatformError: If the platform/source combination is not
            supported (e.g. Linux ARM64).
    """
    mapping: dict[str, dict[tuple[OS, Arch], str]] = {
        "cft": {
            (OS.WINDOWS, Arch.X64): "win64",
            (OS.WINDOWS, Arch.X86): "win32",
            (OS.MACOS, Arch.ARM64): "mac-arm64",
            (OS.MACOS, Arch.X64): "mac-x64",
            (OS.LINUX, Arch.X64): "linux64",
        },
        "firefox": {
            (OS.WINDOWS, Arch.X64): "win64",
            (OS.WINDOWS, Arch.X86): "win32",
            (OS.MACOS, Arch.ARM64): "os",
            (OS.MACOS, Arch.X64): "os",
            (OS.LINUX, Arch.X64): "linux64",
            (OS.LINUX, Arch.X86): "linux-i686",
        },
        "edge": {
            (OS.WINDOWS, Arch.X64): "win64",
            (OS.WINDOWS, Arch.X86): "win32",
            (OS.MACOS, Arch.ARM64): "mac-arm64",
            (OS.MACOS, Arch.X64): "mac-x64",
            (OS.LINUX, Arch.X64): "linux64",
        },
        "edgedriver": {
            (OS.WINDOWS, Arch.X64): "win64",
            (OS.WINDOWS, Arch.X86): "win32",
            (OS.MACOS, Arch.ARM64): "mac-arm64",
            (OS.MACOS, Arch.X64): "mac-x64",
            (OS.LINUX, Arch.X64): "linux64",
        },
        "geckodriver": {
            (OS.WINDOWS, Arch.X64): "win64",
            (OS.WINDOWS, Arch.X86): "win32",
            (OS.MACOS, Arch.ARM64): "mac-arm64",
            (OS.MACOS, Arch.X64): "mac-x64",
            (OS.LINUX, Arch.X64): "linux64",
        },
    }

    source_map = mapping.get(source)
    if source_map is None:
        raise UnsupportedPlatformError(platform=source, name="browserget")

    key = (platform.os, platform.arch)
    result = source_map.get(key)
    if result is None:
        raise UnsupportedPlatformError(
            platform=f"{platform.os.value}-{platform.arch.value}",
            name=source,
        )
    return result
