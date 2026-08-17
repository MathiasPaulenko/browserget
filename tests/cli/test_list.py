"""Tests for the `list` CLI command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.models import InstalledArtifact


def _make_artifact(name: str, version: str, tmp_path: Path) -> InstalledArtifact:
    """Create a test artifact."""
    return InstalledArtifact(
        name=name,
        version=version,
        path=tmp_path / name / version / "binary",
        installed_at=datetime.now(UTC),
        checksum="abc123",
    )


class TestList:
    """List command tests."""

    def test_list_empty(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """list with empty registry → 'No artifacts installed', exit 0."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.list_all = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No artifacts installed" in result.stdout

    def test_list_with_artifacts(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """list with artifacts → table with Name, Version, Path, Installed At."""
        from browserget import cli as cli_module

        artifacts = [
            _make_artifact("chrome", "131.0.6778.87", tmp_path),
            _make_artifact("chromedriver", "131.0.6778.87", tmp_path),
        ]
        mock_registry = MagicMock()
        mock_registry.list_all = MagicMock(
            return_value={
                "chrome": [artifacts[0]],
                "chromedriver": [artifacts[1]],
            }
        )
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "chrome" in result.stdout
        assert "131.0.6778.87" in result.stdout
        assert "chromedriver" in result.stdout
        assert "Name" in result.stdout

    def test_list_json_empty(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """list --json with empty registry → valid empty JSON array."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.list_all = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_json_with_artifacts(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """list --json with artifacts → valid JSON array."""
        from browserget import cli as cli_module

        artifact = _make_artifact("chrome", "131.0.6778.87", tmp_path)
        mock_registry = MagicMock()
        mock_registry.list_all = MagicMock(return_value={"chrome": [artifact]})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "chrome"
        assert data[0]["version"] == "131.0.6778.87"
