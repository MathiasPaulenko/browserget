"""Tests for the `path` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.models import InstalledArtifact


class TestPath:
    """Path command tests."""

    def test_path_installed(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """path chrome (installed) → prints path, exit 0."""
        from browserget import cli as cli_module

        artifact = InstalledArtifact(
            name="chrome",
            version="131.0.6778.87",
            path=tmp_path / "chrome" / "chrome.exe",
            installed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            checksum="abc123",
        )
        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=artifact)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["path", "chrome"])
        assert result.exit_code == 0
        assert str(tmp_path / "chrome" / "chrome.exe") in result.stdout

    def test_path_with_version(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """path chrome --version 131.0.6778.87 → prints specific version path."""
        from browserget import cli as cli_module

        artifact = InstalledArtifact(
            name="chrome",
            version="131.0.6778.87",
            path=tmp_path / "chrome" / "131" / "chrome.exe",
            installed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            checksum="abc123",
        )
        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=artifact)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["path", "chrome", "--version", "131.0.6778.87"])
        assert result.exit_code == 0
        mock_registry.find.assert_called_once_with("chrome", "131.0.6778.87")

    def test_path_not_installed(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """path chrome (not installed) → exit 2."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["path", "chrome"])
        assert result.exit_code == 2

    def test_path_unknown_target(self, runner: CliRunner) -> None:
        """path unknown → exit 2."""
        result = runner.invoke(app, ["path", "unknown"])
        assert result.exit_code == 2
