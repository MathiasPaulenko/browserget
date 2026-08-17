"""Tests for the `remove` CLI command."""

from __future__ import annotations

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
        checksum=None,
    )


class TestRemove:
    """Remove command tests."""

    def test_remove_single(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """remove chrome → removes from registry + cache, exit 0."""
        from browserget import cli as cli_module

        artifact = _make_artifact("chrome", "131.0.6778.87", tmp_path)
        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=artifact)
        mock_registry.remove = MagicMock()
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)
        monkeypatch.setattr(cli_module, "get_artifact_dir", lambda n, v: tmp_path / n / v)

        result = runner.invoke(app, ["remove", "chrome"])
        assert result.exit_code == 0
        assert "Removed" in result.stdout
        mock_registry.remove.assert_called_once_with("chrome", "131.0.6778.87")

    def test_remove_with_version(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """remove chrome --version 131.0.6778.87 → removes specific version."""
        from browserget import cli as cli_module

        artifact = _make_artifact("chrome", "131.0.6778.87", tmp_path)
        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=artifact)
        mock_registry.remove = MagicMock()
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)
        monkeypatch.setattr(cli_module, "get_artifact_dir", lambda n, v: tmp_path / n / v)

        result = runner.invoke(app, ["remove", "chrome", "--version", "131.0.6778.87"])
        assert result.exit_code == 0
        mock_registry.remove.assert_called_once_with("chrome", "131.0.6778.87")

    def test_remove_all(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """remove chrome --all → removes all versions."""
        from browserget import cli as cli_module

        artifacts = [
            _make_artifact("chrome", "131.0.6778.87", tmp_path),
            _make_artifact("chrome", "130.0.6723.116", tmp_path),
        ]
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=artifacts)
        mock_registry.remove = MagicMock()
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)
        monkeypatch.setattr(cli_module, "get_artifact_dir", lambda n, v: tmp_path / n / v)

        result = runner.invoke(app, ["remove", "chrome", "--all"])
        assert result.exit_code == 0
        assert "Removed all" in result.stdout
        assert mock_registry.remove.call_count == 2

    def test_remove_not_installed(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """remove chrome (not installed) → exit 2."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["remove", "chrome"])
        assert result.exit_code == 2

    def test_remove_all_not_installed(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """remove chrome --all (no installations) → exit 2."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=[])
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["remove", "chrome", "--all"])
        assert result.exit_code == 2

    def test_remove_unknown_target(self, runner: CliRunner) -> None:
        """remove unknown → exit 2."""
        result = runner.invoke(app, ["remove", "unknown"])
        assert result.exit_code == 2
