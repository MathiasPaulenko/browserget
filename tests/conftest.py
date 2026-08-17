"""Shared test fixtures for browserget tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from browserget.models import InstalledArtifact, ResolvedVersion, SystemBrowser
from browserget.registry import Registry


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Return a temporary cache directory, auto-cleaned by pytest."""
    return tmp_path / "cache"


@pytest.fixture
def tmp_registry(tmp_cache_dir: Path) -> Registry:
    """Return a Registry instance backed by a temp cache directory."""
    return Registry(tmp_cache_dir)


@pytest.fixture
def sample_resolved_version() -> ResolvedVersion:
    """Return a sample ResolvedVersion for testing."""
    return ResolvedVersion(
        name="chrome",
        version="131.0.6778.87",
        url="https://example.com/chrome.zip",
        platform="win64",
        checksum="abc123",
        checksum_algorithm="sha256",
    )


@pytest.fixture
def sample_installed_artifact() -> InstalledArtifact:
    """Return a sample InstalledArtifact for testing."""
    return InstalledArtifact(
        name="chrome",
        version="131.0.6778.87",
        path=Path("/fake/chrome"),
        installed_at=datetime(2025, 1, 1, 12, 0, 0),
        checksum="abc123",
    )


@pytest.fixture
def sample_system_browser() -> SystemBrowser:
    """Return a sample SystemBrowser for testing."""
    return SystemBrowser(
        name="chrome",
        version="131.0.6778.87",
        path=Path("/usr/bin/chrome"),
    )
