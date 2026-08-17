"""Unit tests for the Firefox FTP parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from browserget.parsers.firefox import (
    build_checksum_url,
    build_download_url,
    find_latest,
    parse_releases,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def firefox_html() -> str:
    """Load the Firefox FTP fixture HTML."""
    return (_FIXTURES_DIR / "firefox_releases.html").read_text(encoding="utf-8")


class TestParseReleases:
    """Tests for parse_releases()."""

    def test_extracts_version_directories(self, firefox_html: str) -> None:
        """parse_releases should extract version-like directory names."""
        versions = parse_releases(firefox_html)
        assert "131.0" in versions
        assert "130.0.1" in versions
        assert "130.0" in versions
        assert "129.0" in versions
        assert "128.0" in versions

    def test_filters_non_version_entries(self, firefox_html: str) -> None:
        """parse_releases should filter out non-version entries."""
        versions = parse_releases(firefox_html)
        assert "latest" not in versions
        assert "releases" not in versions
        assert "contrib" not in versions
        assert "partner-repacks" not in versions
        assert ".." not in versions

    def test_includes_esr_suffix(self, firefox_html: str) -> None:
        """parse_releases should include esr versions."""
        versions = parse_releases(firefox_html)
        assert "115.0esr" in versions

    def test_empty_html_returns_empty(self) -> None:
        """parse_releases with no version dirs should return []."""
        assert parse_releases("<html><body>No links</body></html>") == []

    def test_html_with_only_non_version_entries(self) -> None:
        """parse_releases should return [] when only non-version entries exist."""
        html = '<a href="latest/">latest/</a><a href="releases/">releases/</a>'
        assert parse_releases(html) == []


class TestFindLatest:
    """Tests for find_latest()."""

    def test_returns_highest_version(self, firefox_html: str) -> None:
        """find_latest should return 131.0."""
        versions = parse_releases(firefox_html)
        assert find_latest(versions) == "131.0"

    def test_empty_list_returns_none(self) -> None:
        """find_latest on empty list should return None."""
        assert find_latest([]) is None

    def test_esr_lower_than_normal(self) -> None:
        """find_latest should rank 115.0esr below 131.0."""
        versions = ["115.0esr", "131.0", "130.0"]
        assert find_latest(versions) == "131.0"


class TestBuildDownloadUrl:
    """Tests for build_download_url()."""

    def test_win64_url(self) -> None:
        """build_download_url for win64 should produce .exe URL."""
        url = build_download_url("131.0", "win64")
        assert "131.0" in url
        assert "win64" in url
        assert url.endswith("Firefox Setup 131.0.exe")

    def test_mac_url(self) -> None:
        """build_download_url for mac should produce .dmg URL."""
        url = build_download_url("131.0", "mac")
        assert "131.0" in url
        assert "mac" in url
        assert url.endswith("Firefox 131.0.dmg")

    def test_linux_x86_64_url(self) -> None:
        """build_download_url for linux-x86_64 should produce .tar.bz2 URL."""
        url = build_download_url("131.0", "linux-x86_64")
        assert "131.0" in url
        assert "linux-x86_64" in url
        assert url.endswith("firefox-131.0.tar.bz2")

    def test_mac_arm64_maps_to_mac(self) -> None:
        """build_download_url for mac-arm64 should map to mac path."""
        url = build_download_url("131.0", "mac-arm64")
        assert "/mac/" in url
        assert url.endswith("Firefox 131.0.dmg")

    def test_linux64_maps_to_linux_x86_64(self) -> None:
        """build_download_url for linux64 should map to linux-x86_64 path."""
        url = build_download_url("131.0", "linux64")
        assert "/linux-x86_64/" in url
        assert url.endswith("firefox-131.0.tar.bz2")

    def test_os_maps_to_mac(self) -> None:
        """build_download_url for 'os' (map_platform macOS output) should produce .dmg URL."""
        url = build_download_url("131.0", "os")
        assert "/mac/" in url
        assert url.endswith("Firefox 131.0.dmg")


class TestBuildChecksumUrl:
    """Tests for build_checksum_url()."""

    def test_win64_checksum_url(self) -> None:
        """build_checksum_url for win64 should produce SHA512SUMS URL at release root."""
        url = build_checksum_url("131.0", "win64")
        assert url is not None
        assert "131.0" in url
        assert url.endswith("SHA512SUMS")

    def test_linux64_checksum_url(self) -> None:
        """build_checksum_url for linux64 should produce SHA512SUMS URL at release root."""
        url = build_checksum_url("131.0", "linux64")
        assert url is not None
        assert "131.0" in url
        assert url.endswith("SHA512SUMS")

    def test_unknown_platform_returns_url(self) -> None:
        """build_checksum_url returns SHA512SUMS URL regardless of platform (platform is unused)."""
        url = build_checksum_url("131.0", "solaris")
        assert url is not None
        assert url.endswith("SHA512SUMS")

    def test_os_checksum_url(self) -> None:
        """build_checksum_url for 'os' (map_platform macOS output) should produce SHA512SUMS URL."""
        url = build_checksum_url("131.0", "os")
        assert url is not None
        assert "131.0" in url
        assert url.endswith("SHA512SUMS")

    def test_empty_version_returns_none(self) -> None:
        """build_checksum_url for empty version should return None."""
        assert build_checksum_url("", "linux64") is None
