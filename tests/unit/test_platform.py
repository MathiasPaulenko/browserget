"""Unit tests for platform detection and mapping."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from browserget.exceptions import UnsupportedPlatformError
from browserget.platform import (
    OS,
    Arch,
    Platform,
    detect_arch,
    detect_os,
    detect_platform,
    map_platform,
)


class TestDetectOS:
    """Tests for detect_os()."""

    def test_returns_valid_os_enum(self) -> None:
        """detect_os should return a valid OS enum member."""
        result = detect_os()
        assert result in (OS.WINDOWS, OS.MACOS, OS.LINUX)


class TestDetectArch:
    """Tests for detect_arch()."""

    def test_returns_valid_arch_enum(self) -> None:
        """detect_arch should return a valid Arch enum member."""
        result = detect_arch()
        assert result in (Arch.X64, Arch.ARM64)


class TestDetectPlatform:
    """Tests for detect_platform()."""

    def test_returns_platform_with_os_and_arch(self) -> None:
        """detect_platform should return a Platform with both os and arch."""
        p = detect_platform()
        assert isinstance(p, Platform)
        assert isinstance(p.os, OS)
        assert isinstance(p.arch, Arch)

    def test_platform_is_frozen(self) -> None:
        """Platform should be frozen."""
        p = detect_platform()
        with pytest.raises(FrozenInstanceError):
            p.os = OS.LINUX


class TestMapPlatform:
    """Tests for map_platform()."""

    @pytest.mark.parametrize("source", ["cft", "firefox", "edge", "edgedriver", "geckodriver"])
    def test_map_platform_returns_string_for_current_platform(self, source: str) -> None:
        """map_platform should return a non-empty string for each source on current platform."""
        p = detect_platform()
        result = map_platform(p, source)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_map_platform_cft_macos_arm64(self) -> None:
        """map_platform for macOS ARM64 with cft source should return mac-arm64."""
        p = Platform(os=OS.MACOS, arch=Arch.ARM64)
        assert map_platform(p, "cft") == "mac-arm64"

    def test_map_platform_firefox_macos_arm64(self) -> None:
        """map_platform for macOS ARM64 with firefox source should return 'os'."""
        p = Platform(os=OS.MACOS, arch=Arch.ARM64)
        assert map_platform(p, "firefox") == "os"

    def test_map_platform_linux_arm64_raises(self) -> None:
        """map_platform for Linux ARM64 should raise UnsupportedPlatformError."""
        p = Platform(os=OS.LINUX, arch=Arch.ARM64)
        with pytest.raises(UnsupportedPlatformError):
            map_platform(p, "cft")

    def test_map_platform_linux_arm64_all_sources(self) -> None:
        """map_platform for Linux ARM64 should raise for all sources."""
        p = Platform(os=OS.LINUX, arch=Arch.ARM64)
        for source in ("cft", "firefox", "edge", "edgedriver", "geckodriver"):
            with pytest.raises(UnsupportedPlatformError):
                map_platform(p, source)

    def test_map_platform_invalid_source_raises(self) -> None:
        """map_platform with invalid source should raise UnsupportedPlatformError."""
        p = detect_platform()
        with pytest.raises(UnsupportedPlatformError):
            map_platform(p, "invalid_source")

    def test_map_platform_cft_windows_x64(self) -> None:
        """map_platform for Windows X64 with cft should return win64."""
        p = Platform(os=OS.WINDOWS, arch=Arch.X64)
        assert map_platform(p, "cft") == "win64"

    def test_map_platform_edge_windows_x64(self) -> None:
        """map_platform for Windows X64 with edge should return win64."""
        p = Platform(os=OS.WINDOWS, arch=Arch.X64)
        assert map_platform(p, "edge") == "win64"

    def test_map_platform_geckodriver_macos_x64(self) -> None:
        """map_platform for macOS X64 with geckodriver should return mac-x64."""
        p = Platform(os=OS.MACOS, arch=Arch.X64)
        assert map_platform(p, "geckodriver") == "mac-x64"

    def test_map_platform_geckodriver_macos_arm64(self) -> None:
        """map_platform for macOS ARM64 with geckodriver should return mac-arm64."""
        p = Platform(os=OS.MACOS, arch=Arch.ARM64)
        assert map_platform(p, "geckodriver") == "mac-arm64"

    def test_map_platform_edgedriver_windows_x64(self) -> None:
        """map_platform for Windows X64 with edgedriver should return win64."""
        p = Platform(os=OS.WINDOWS, arch=Arch.X64)
        assert map_platform(p, "edgedriver") == "win64"

    def test_map_platform_edgedriver_macos_arm64(self) -> None:
        """map_platform for macOS ARM64 with edgedriver should return mac-arm64."""
        p = Platform(os=OS.MACOS, arch=Arch.ARM64)
        assert map_platform(p, "edgedriver") == "mac-arm64"

    def test_map_platform_edgedriver_linux_x64(self) -> None:
        """map_platform for Linux X64 with edgedriver should return linux64."""
        p = Platform(os=OS.LINUX, arch=Arch.X64)
        assert map_platform(p, "edgedriver") == "linux64"
