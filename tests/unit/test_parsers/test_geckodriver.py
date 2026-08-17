"""Unit tests for the GeckoDriver GitHub releases parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from browserget.parsers.geckodriver import (
    find_latest,
    find_version,
    parse_releases,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def geckodriver_data() -> list[dict[str, object]]:
    """Load the GeckoDriver fixture JSON."""
    with open(_FIXTURES_DIR / "geckodriver_releases.json", encoding="utf-8") as f:
        return json.load(f)


class TestParseReleases:
    """Tests for parse_releases()."""

    def test_win64_correct_count(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases for win64 should return all 3 releases."""
        results = parse_releases(geckodriver_data, "win64")
        assert len(results) == 3

    def test_macos_arm64_correct_count(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases for mac-arm64 should return 3 releases."""
        results = parse_releases(geckodriver_data, "mac-arm64")
        assert len(results) == 3

    def test_macos_x64_correct_count(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases for mac-x64 should return 3 releases."""
        results = parse_releases(geckodriver_data, "mac-x64")
        assert len(results) == 3

    def test_linux64_correct_count(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases for linux64 should return 3 releases."""
        results = parse_releases(geckodriver_data, "linux64")
        assert len(results) == 3

    def test_sorted_descending(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases should sort versions descending."""
        results = parse_releases(geckodriver_data, "win64")
        versions = [v.version for v in results]
        assert versions == ["0.35.0", "0.34.0", "0.33.0"]

    def test_tag_name_strips_v_prefix(self, geckodriver_data: list[dict[str, object]]) -> None:
        """tag_name 'v0.35.0' should produce version '0.35.0'."""
        results = parse_releases(geckodriver_data, "win64")
        assert results[0].version == "0.35.0"
        assert not results[0].version.startswith("v")

    def test_checksum_none_for_all(self, geckodriver_data: list[dict[str, object]]) -> None:
        """All geckodriver entries should have checksum=None (GitHub has no checksums)."""
        results = parse_releases(geckodriver_data, "win64")
        for v in results:
            assert v.checksum is None
            assert v.checksum_algorithm is None

    def test_name_is_geckodriver(self, geckodriver_data: list[dict[str, object]]) -> None:
        """All entries should have name='geckodriver'."""
        results = parse_releases(geckodriver_data, "win64")
        for v in results:
            assert v.name == "geckodriver"

    def test_url_correct_for_win64(self, geckodriver_data: list[dict[str, object]]) -> None:
        """win64 URL should point to the win64.zip asset."""
        results = parse_releases(geckodriver_data, "win64")
        assert "win64.zip" in results[0].url

    def test_url_correct_for_macos_arm64(self, geckodriver_data: list[dict[str, object]]) -> None:
        """mac-arm64 URL should point to the macos-aarch64.tar.gz asset."""
        results = parse_releases(geckodriver_data, "mac-arm64")
        assert "macos-aarch64.tar.gz" in results[0].url

    def test_url_correct_for_macos_x64(self, geckodriver_data: list[dict[str, object]]) -> None:
        """mac-x64 URL should point to the macos.tar.gz asset."""
        results = parse_releases(geckodriver_data, "mac-x64")
        assert "macos.tar.gz" in results[0].url
        assert "aarch64" not in results[0].url

    def test_macos_platform_string(self, geckodriver_data: list[dict[str, object]]) -> None:
        """parse_releases with 'macos' (map_platform output) should return results."""
        results = parse_releases(geckodriver_data, "macos")
        assert len(results) == 3
        assert "macos.tar.gz" in results[0].url

    def test_url_correct_for_linux64(self, geckodriver_data: list[dict[str, object]]) -> None:
        """linux64 URL should point to the linux64.tar.gz asset."""
        results = parse_releases(geckodriver_data, "linux64")
        assert "linux64.tar.gz" in results[0].url

    def test_unsupported_platform_returns_empty(
        self, geckodriver_data: list[dict[str, object]]
    ) -> None:
        """parse_releases for unsupported platform should return []."""
        assert parse_releases(geckodriver_data, "solaris") == []

    def test_release_with_no_matching_asset_skipped(self) -> None:
        """Release with assets but none matching the platform should be skipped."""
        data: list[dict[str, object]] = [
            {
                "tag_name": "v0.36.0",
                "assets": [
                    {
                        "name": "geckodriver-v0.36.0-win64.zip",
                        "browser_download_url": "https://example.com/win64.zip",
                    }
                ],
            }
        ]
        results = parse_releases(data, "linux64")
        assert results == []

    def test_empty_releases_returns_empty(self) -> None:
        """parse_releases with empty list should return []."""
        assert parse_releases([], "win64") == []

    def test_release_without_tag_name_skipped(self) -> None:
        """Release without tag_name should be skipped."""
        data: list[dict[str, object]] = [
            {"assets": [{"name": "x.zip", "browser_download_url": "http://x"}]}
        ]
        assert parse_releases(data, "win64") == []


class TestFindLatest:
    """Tests for find_latest()."""

    def test_returns_highest_version(self, geckodriver_data: list[dict[str, object]]) -> None:
        """find_latest should return 0.35.0."""
        versions = parse_releases(geckodriver_data, "win64")
        latest = find_latest(versions)
        assert latest is not None
        assert latest.version == "0.35.0"

    def test_empty_list_returns_none(self) -> None:
        """find_latest on empty list should return None."""
        assert find_latest([]) is None


class TestFindVersion:
    """Tests for find_version()."""

    def test_exact_match_without_v_prefix(self, geckodriver_data: list[dict[str, object]]) -> None:
        """find_version with '0.34.0' (no v prefix) should find it."""
        versions = parse_releases(geckodriver_data, "win64")
        result = find_version(versions, "0.34.0")
        assert result is not None
        assert result.version == "0.34.0"

    def test_exact_match_with_v_prefix(self, geckodriver_data: list[dict[str, object]]) -> None:
        """find_version with 'v0.34.0' (v prefix) should also find it."""
        versions = parse_releases(geckodriver_data, "win64")
        result = find_version(versions, "v0.34.0")
        assert result is not None
        assert result.version == "0.34.0"

    def test_nonexistent_returns_none(self, geckodriver_data: list[dict[str, object]]) -> None:
        """find_version with non-existent version should return None."""
        versions = parse_releases(geckodriver_data, "win64")
        assert find_version(versions, "9.99.0") is None

    def test_double_v_prefix_not_stripped(self, geckodriver_data: list[dict[str, object]]) -> None:
        """find_version with 'vv0.34.0' should NOT match '0.34.0' (only one v stripped)."""
        versions = parse_releases(geckodriver_data, "win64")
        assert find_version(versions, "vv0.34.0") is None
