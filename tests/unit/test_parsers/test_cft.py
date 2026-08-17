"""Unit tests for the CfT (Chrome for Testing) parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from browserget.parsers.cft import (
    find_by_milestone,
    find_latest,
    find_version,
    parse_versions,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def cft_data() -> dict[str, object]:
    """Load the CfT fixture JSON."""
    with open(_FIXTURES_DIR / "cft_versions.json", encoding="utf-8") as f:
        return json.load(f)


class TestParseVersions:
    """Tests for parse_versions()."""

    def test_chrome_win64_correct_count(self, cft_data: dict[str, object]) -> None:
        """parse_versions for chrome/win64 should return all 5 versions."""
        results = parse_versions(cft_data, "chrome", "win64")
        assert len(results) == 5

    def test_chrome_sorted_descending(self, cft_data: dict[str, object]) -> None:
        """parse_versions should sort versions descending."""
        results = parse_versions(cft_data, "chrome", "win64")
        versions = [v.version for v in results]
        assert versions == [
            "131.0.6778.87",
            "131.0.6778.80",
            "130.0.6723.116",
            "130.0.6723.69",
            "129.0.6668.100",
        ]

    def test_chromedriver_win64_correct_count(self, cft_data: dict[str, object]) -> None:
        """parse_versions for chromedriver/win64 should return all 5 versions."""
        results = parse_versions(cft_data, "chromedriver", "win64")
        assert len(results) == 5

    def test_chromedriver_entries_have_correct_name(self, cft_data: dict[str, object]) -> None:
        """Each chromedriver entry should have name='chromedriver'."""
        results = parse_versions(cft_data, "chromedriver", "win64")
        for v in results:
            assert v.name == "chromedriver"

    def test_missing_checksum_returns_none(self, cft_data: dict[str, object]) -> None:
        """Version 130.0.6723.69 win64 has no checksums → checksum=None."""
        results = parse_versions(cft_data, "chrome", "win64")
        v130_69 = find_version(results, "130.0.6723.69")
        assert v130_69 is not None
        assert v130_69.checksum is None
        assert v130_69.checksum_algorithm is None

    def test_with_checksum_returns_value(self, cft_data: dict[str, object]) -> None:
        """Version 131.0.6778.87 win64 has checksum → not None."""
        results = parse_versions(cft_data, "chrome", "win64")
        v131 = find_version(results, "131.0.6778.87")
        assert v131 is not None
        assert v131.checksum is not None
        assert v131.checksum_algorithm == "sha256"

    def test_platform_not_in_downloads_skipped(self, cft_data: dict[str, object]) -> None:
        """Version 130.0.6723.69 has no mac-arm64 → skipped for that platform."""
        results = parse_versions(cft_data, "chrome", "mac-arm64")
        versions = [v.version for v in results]
        assert "130.0.6723.69" not in versions

    def test_empty_versions_returns_empty_list(self) -> None:
        """parse_versions with empty versions list should return []."""
        results = parse_versions({"versions": []}, "chrome", "win64")
        assert results == []

    def test_malformed_versions_key_returns_empty(self) -> None:
        """parse_versions with non-list versions should return []."""
        results = parse_versions({"versions": "not a list"}, "chrome", "win64")
        assert results == []


class TestFindLatest:
    """Tests for find_latest()."""

    def test_returns_highest_version(self, cft_data: dict[str, object]) -> None:
        """find_latest should return the highest version."""
        versions = parse_versions(cft_data, "chrome", "win64")
        latest = find_latest(versions)
        assert latest is not None
        assert latest.version == "131.0.6778.87"

    def test_empty_list_returns_none(self) -> None:
        """find_latest on empty list should return None."""
        assert find_latest([]) is None


class TestFindVersion:
    """Tests for find_version()."""

    def test_exact_match_found(self, cft_data: dict[str, object]) -> None:
        """find_version with exact match should return the version."""
        versions = parse_versions(cft_data, "chrome", "win64")
        result = find_version(versions, "130.0.6723.116")
        assert result is not None
        assert result.version == "130.0.6723.116"

    def test_nonexistent_returns_none(self, cft_data: dict[str, object]) -> None:
        """find_version with non-existent version should return None."""
        versions = parse_versions(cft_data, "chrome", "win64")
        assert find_version(versions, "999.0.0.0") is None


class TestFindByMilestone:
    """Tests for find_by_milestone()."""

    def test_milestone_131_returns_highest_131(self, cft_data: dict[str, object]) -> None:
        """find_by_milestone(131) should return highest 131.x.x.x."""
        versions = parse_versions(cft_data, "chrome", "win64")
        result = find_by_milestone(versions, 131)
        assert result is not None
        assert result.version == "131.0.6778.87"

    def test_milestone_130_returns_highest_130(self, cft_data: dict[str, object]) -> None:
        """find_by_milestone(130) should return highest 130.x.x.x."""
        versions = parse_versions(cft_data, "chrome", "win64")
        result = find_by_milestone(versions, 130)
        assert result is not None
        assert result.version == "130.0.6723.116"

    def test_nonexistent_milestone_returns_none(self, cft_data: dict[str, object]) -> None:
        """find_by_milestone with non-existent milestone should return None."""
        versions = parse_versions(cft_data, "chrome", "win64")
        assert find_by_milestone(versions, 999) is None
