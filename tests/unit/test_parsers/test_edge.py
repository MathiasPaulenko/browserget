"""Unit tests for the Edge API parser and EdgeDriver URL builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from browserget.exceptions import UnsupportedPlatformError
from browserget.parsers.edge import (
    EDGEDRIVER_CDN_URL,
    build_edgedriver_url,
    find_by_milestone,
    find_latest,
    find_version,
    parse_versions,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def edge_data() -> list[dict[str, object]]:
    """Load the Edge API fixture JSON."""
    with open(_FIXTURES_DIR / "edge_api.json", encoding="utf-8") as f:
        return json.load(f)


class TestParseVersions:
    """Tests for parse_versions()."""

    def test_edge_win64_correct_count(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions for edge/win64 should return all 3 versions."""
        results = parse_versions(edge_data, "edge", "win64")
        assert len(results) == 3

    def test_edge_sorted_descending(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions should sort versions descending."""
        results = parse_versions(edge_data, "edge", "win64")
        versions = [v.version for v in results]
        assert versions == ["131.0.2903.86", "130.0.2849.68", "129.0.2792.89"]

    def test_edge_entries_have_correct_name(self, edge_data: list[dict[str, object]]) -> None:
        """Each edge entry should have name='edge'."""
        results = parse_versions(edge_data, "edge", "win64")
        for v in results:
            assert v.name == "edge"

    def test_missing_checksum_returns_none(self, edge_data: list[dict[str, object]]) -> None:
        """Version 130.0.2849.68 win64 has null Hash → checksum=None."""
        results = parse_versions(edge_data, "edge", "win64")
        v130 = find_version(results, "130.0.2849.68")
        assert v130 is not None
        assert v130.checksum is None

    def test_with_checksum_returns_value(self, edge_data: list[dict[str, object]]) -> None:
        """Version 131.0.2903.86 win64 has checksum → not None."""
        results = parse_versions(edge_data, "edge", "win64")
        v131 = find_version(results, "131.0.2903.86")
        assert v131 is not None
        assert v131.checksum is not None
        assert v131.checksum_algorithm == "sha256"

    def test_mac_arm64_correct_count(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions for edge/mac-arm64 should return 3 versions (universal)."""
        results = parse_versions(edge_data, "edge", "mac-arm64")
        assert len(results) == 3

    def test_mac_x64_correct_count(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions for edge/mac-x64 should also return 3 versions (universal)."""
        results = parse_versions(edge_data, "edge", "mac-x64")
        assert len(results) == 3

    def test_linux64_correct_count(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions for edge/linux64 should return 3 versions."""
        results = parse_versions(edge_data, "edge", "linux64")
        assert len(results) == 3

    def test_unsupported_platform_raises(self, edge_data: list[dict[str, object]]) -> None:
        """parse_versions with unsupported platform should raise."""
        with pytest.raises(UnsupportedPlatformError):
            parse_versions(edge_data, "edge", "solaris")

    def test_empty_list_returns_empty(self) -> None:
        """parse_versions with empty list should return []."""
        assert parse_versions([], "edge", "win64") == []

    def test_non_list_input_returns_empty(self) -> None:
        """parse_versions with non-list input should return []."""
        assert parse_versions({"versions": []}, "edge", "win64") == []

    def test_beta_product_ignored(self, edge_data: list[dict[str, object]]) -> None:
        """Only the Stable product should be parsed, not Beta."""
        results = parse_versions(edge_data, "edge", "win64")
        versions = [v.version for v in results]
        # Beta has 131.0.2903.86 but it should not duplicate
        assert versions.count("131.0.2903.86") == 1


class TestFindLatest:
    """Tests for find_latest()."""

    def test_returns_highest_version(self, edge_data: list[dict[str, object]]) -> None:
        """find_latest should return the highest version."""
        versions = parse_versions(edge_data, "edge", "win64")
        latest = find_latest(versions)
        assert latest is not None
        assert latest.version == "131.0.2903.86"

    def test_empty_list_returns_none(self) -> None:
        """find_latest on empty list should return None."""
        assert find_latest([]) is None


class TestFindVersion:
    """Tests for find_version()."""

    def test_exact_match_found(self, edge_data: list[dict[str, object]]) -> None:
        """find_version with exact match should return the version."""
        versions = parse_versions(edge_data, "edge", "win64")
        result = find_version(versions, "130.0.2849.68")
        assert result is not None
        assert result.version == "130.0.2849.68"

    def test_nonexistent_returns_none(self, edge_data: list[dict[str, object]]) -> None:
        """find_version with non-existent version should return None."""
        versions = parse_versions(edge_data, "edge", "win64")
        assert find_version(versions, "999.0.0.0") is None


class TestFindByMilestone:
    """Tests for find_by_milestone()."""

    def test_milestone_131(self, edge_data: list[dict[str, object]]) -> None:
        """find_by_milestone(131) should return highest 131.x.x.x."""
        versions = parse_versions(edge_data, "edge", "win64")
        result = find_by_milestone(versions, 131)
        assert result is not None
        assert result.version == "131.0.2903.86"

    def test_nonexistent_milestone(self, edge_data: list[dict[str, object]]) -> None:
        """find_by_milestone with non-existent milestone should return None."""
        versions = parse_versions(edge_data, "edge", "win64")
        assert find_by_milestone(versions, 999) is None


class TestBuildEdgeDriverUrl:
    """Tests for build_edgedriver_url()."""

    @pytest.mark.parametrize(
        ("platform", "expected_suffix"),
        [
            ("win64", "edgedriver_win64.zip"),
            ("win32", "edgedriver_win32.zip"),
            ("mac-arm64", "edgedriver_mac64.zip"),
            ("mac-x64", "edgedriver_mac64.zip"),
            ("linux64", "edgedriver_linux64.zip"),
        ],
    )
    def test_url_construction(self, platform: str, expected_suffix: str) -> None:
        """build_edgedriver_url should produce correct CDN URLs."""
        url = build_edgedriver_url("131.0.2903.86", platform)
        assert url == f"{EDGEDRIVER_CDN_URL}/131.0.2903.86/{expected_suffix}"

    def test_unsupported_platform_raises(self) -> None:
        """build_edgedriver_url with unsupported platform should raise."""
        with pytest.raises(UnsupportedPlatformError):
            build_edgedriver_url("131.0.2903.86", "solaris")

    def test_mac_arm64_and_x64_same_url(self) -> None:
        """macOS ARM64 and x64 should produce the same URL (universal binary)."""
        url_arm64 = build_edgedriver_url("131.0.2903.86", "mac-arm64")
        url_x64 = build_edgedriver_url("131.0.2903.86", "mac-x64")
        assert url_arm64 == url_x64
