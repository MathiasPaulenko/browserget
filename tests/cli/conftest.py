"""Shared fixtures for CLI tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from browserget.models import InstalledArtifact, ResolvedVersion


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def mock_resolved() -> ResolvedVersion:
    """A resolved version for testing."""
    return ResolvedVersion(
        name="chrome",
        version="131.0.6778.87",
        url="https://example.com/chrome-win64.zip",
        platform="win64",
        checksum="abc123",
        checksum_algorithm="sha256",
    )


@pytest.fixture
def mock_installed(tmp_path: Path) -> InstalledArtifact:
    """An installed artifact for testing."""
    return InstalledArtifact(
        name="chrome",
        version="131.0.6778.87",
        path=tmp_path / "chrome" / "131.0.6778.87" / "chrome.exe",
        installed_at=datetime.now(UTC),
        checksum="abc123",
    )


@pytest.fixture
def mock_installed_artifact_dict(mock_installed: InstalledArtifact) -> str:
    """JSON string of an installed artifact (for registry file setup)."""
    return json.dumps({"chrome": [mock_installed.to_dict()]})


@pytest.fixture
def patched_installers(
    monkeypatch: pytest.MonkeyPatch,
    mock_resolved: ResolvedVersion,
    mock_installed: InstalledArtifact,
    tmp_path: Path,
) -> dict[str, MagicMock]:
    """Patch all installer classes and config to avoid real I/O.

    Returns a dict of mock installer classes keyed by target name.
    Each mock's ``install`` is an AsyncMock returning ``mock_installed``.
    """
    from browserget import cli as cli_module

    mock_instances: dict[str, MagicMock] = {}

    target_names = [
        "chrome",
        "chromedriver",
        "firefox",
        "geckodriver",
        "edge",
        "edgedriver",
    ]

    for target in target_names:
        mock_inst = MagicMock()
        mock_inst.name = target
        mock_inst.resolve = AsyncMock(return_value=mock_resolved)
        mock_inst.match_browser = AsyncMock(return_value=mock_resolved)
        mock_inst.install = AsyncMock(return_value=mock_installed)
        mock_inst.get_installed = AsyncMock(return_value=[])
        mock_instances[target] = mock_inst

    def _fake_create_installer(
        target: str,
        http: object,
        registry: object,
        config: object,
    ) -> object:
        return mock_instances.get(target, MagicMock())

    monkeypatch.setattr(cli_module, "_create_installer", _fake_create_installer)
    monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))
    monkeypatch.setattr(
        cli_module,
        "Registry",
        lambda _: MagicMock(
            find=MagicMock(return_value=None),
            get=MagicMock(return_value=[]),
            list_all=MagicMock(return_value={}),
            add=MagicMock(),
            remove=MagicMock(),
            load=MagicMock(return_value={}),
        ),
    )

    return mock_instances
