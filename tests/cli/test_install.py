"""Tests for the `install` CLI command."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.exceptions import (
    AlreadyInstalledError,
    ChecksumMismatchError,
    NetworkError,
)
from browserget.models import InstalledArtifact


class TestInstallBasic:
    """Basic install command tests."""

    def test_install_chrome_success(
        self, runner: CliRunner, patched_installers: dict[str, MagicMock]
    ) -> None:
        """install chrome → calls installer, exit 0."""
        result = runner.invoke(app, ["install", "chrome"])
        assert result.exit_code == 0
        assert "Installed" in result.stdout
        patched_installers["chrome"].install.assert_called_once()

    def test_install_multiple_targets(
        self, runner: CliRunner, patched_installers: dict[str, MagicMock]
    ) -> None:
        """install chrome chromedriver → both called, exit 0."""
        result = runner.invoke(app, ["install", "chrome", "chromedriver"])
        assert result.exit_code == 0
        patched_installers["chrome"].install.assert_called_once()
        patched_installers["chromedriver"].install.assert_called_once()

    def test_install_with_version(
        self, runner: CliRunner, patched_installers: dict[str, MagicMock]
    ) -> None:
        """install chrome --version 131.0.6778.87 → passes version to resolver."""
        result = runner.invoke(app, ["install", "chrome", "--version", "131.0.6778.87"])
        assert result.exit_code == 0
        patched_installers["chrome"].resolve.assert_called_once_with("131.0.6778.87")

    def test_install_force(
        self, runner: CliRunner, patched_installers: dict[str, MagicMock]
    ) -> None:
        """install chrome --force → force=True passed to install."""
        result = runner.invoke(app, ["install", "chrome", "--force"])
        assert result.exit_code == 0
        call_args = patched_installers["chrome"].install.call_args
        assert call_args.args[1] is True

    def test_install_no_force_default(
        self, runner: CliRunner, patched_installers: dict[str, MagicMock]
    ) -> None:
        """install chrome (no --force) → force=False passed to install."""
        result = runner.invoke(app, ["install", "chrome"])
        assert result.exit_code == 0
        call_args = patched_installers["chrome"].install.call_args
        assert call_args.args[1] is False

    def test_no_targets_shows_help(self, runner: CliRunner) -> None:
        """install with no targets → shows usage, exit 1."""
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Usage" in result.stdout or "Supported" in result.stdout


class TestInstallErrors:
    """Install error handling tests."""

    def test_unknown_target_exit_2(self, runner: CliRunner) -> None:
        """install unknown → UnknownTargetError, exit 2."""
        result = runner.invoke(app, ["install", "unknown"])
        assert result.exit_code == 2

    def test_already_installed_exit_5(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
    ) -> None:
        """install chrome (already installed, no force) → exit 5."""
        patched_installers["chrome"].install = AsyncMock(
            side_effect=AlreadyInstalledError("chrome", "131.0.6778.87")
        )
        result = runner.invoke(app, ["install", "chrome"])
        assert result.exit_code == 5

    def test_network_error_exit_3(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
    ) -> None:
        """install chrome (network error) → exit 3."""
        patched_installers["chrome"].install = AsyncMock(
            side_effect=NetworkError("https://example.com", "timeout")
        )
        result = runner.invoke(app, ["install", "chrome"])
        assert result.exit_code == 3

    def test_checksum_error_exit_4(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
    ) -> None:
        """install chrome (checksum error) → exit 4."""
        patched_installers["chrome"].install = AsyncMock(
            side_effect=ChecksumMismatchError("file.zip", "expected", "actual")
        )
        result = runner.invoke(app, ["install", "chrome"])
        assert result.exit_code == 4


class TestInstallForBrowser:
    """Tests for --for browser matching."""

    def test_install_chromedriver_for_chrome(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """install chromedriver --for chrome → resolves from registry."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=mock_installed)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["install", "chromedriver", "--for", "chrome"])
        assert result.exit_code == 0
        patched_installers["chromedriver"].match_browser.assert_called_once_with(
            mock_installed.version
        )

    def test_install_for_chrome_not_in_registry(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """install chromedriver --for chrome (chrome not installed) → exit 2."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["install", "chromedriver", "--for", "chrome"])
        assert result.exit_code == 2


class TestInstallJson:
    """Tests for --json output."""

    def test_install_json_success(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
    ) -> None:
        """install chrome --json → valid JSON output."""
        result = runner.invoke(app, ["install", "chrome", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "chrome"

    def test_install_json_error(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
    ) -> None:
        """install chrome --json (already installed) → JSON error object."""
        patched_installers["chrome"].install = AsyncMock(
            side_effect=AlreadyInstalledError("chrome", "131.0.6778.87")
        )
        result = runner.invoke(app, ["install", "chrome", "--json"])
        assert result.exit_code == 5
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert any(entry.get("status") == "error" for entry in data)


class TestInstallPartialFailure:
    """Tests for concurrent install with partial failure."""

    def test_chrome_succeeds_chromedriver_fails(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
    ) -> None:
        """install chrome chromedriver where chromedriver fails → exit with error code."""
        patched_installers["chromedriver"].install = AsyncMock(
            side_effect=NetworkError("https://example.com", "timeout")
        )
        result = runner.invoke(app, ["install", "chrome", "chromedriver"])
        assert result.exit_code == 3
