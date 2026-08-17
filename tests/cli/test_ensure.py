"""Tests for the `ensure` CLI command."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.exceptions import NetworkError
from browserget.models import InstalledArtifact


class TestEnsure:
    """Ensure command tests."""

    def test_ensure_not_installed_installs(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chrome (not installed) → installs, exit 0."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chrome"])
        assert result.exit_code == 0
        assert "Installed" in result.stdout
        patched_installers["chrome"].install.assert_called_once()

    def test_ensure_already_installed_noop(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chrome (already installed) → no-op, exit 0."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=mock_installed)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chrome"])
        assert result.exit_code == 0
        assert "Already installed" in result.stdout
        patched_installers["chrome"].install.assert_not_called()

    def test_ensure_chromedriver_for_chrome(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chromedriver --for chrome (chrome installed, driver not) → installs."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()

        def _find(name: str, version: str | None = None) -> InstalledArtifact | None:
            if name == "chrome":
                return mock_installed
            return None

        mock_registry.find = _find
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chromedriver", "--for", "chrome"])
        assert result.exit_code == 0
        patched_installers["chromedriver"].install.assert_called_once()

    def test_ensure_both_installed_noop(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chromedriver --for chrome (both installed) → no-op."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=mock_installed)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chromedriver", "--for", "chrome"])
        assert result.exit_code == 0
        patched_installers["chromedriver"].install.assert_not_called()

    def test_ensure_json_output(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chrome --json → JSON with status."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chrome", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["status"] == "installed"

    def test_ensure_json_already_installed(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        mock_installed: InstalledArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chrome --json (already installed) → status=already_installed."""
        from browserget import cli as cli_module

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=mock_installed)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chrome", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["status"] == "already_installed"

    def test_ensure_json_error_no_double_output(
        self,
        runner: CliRunner,
        patched_installers: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure chrome --json (install fails) → single JSON array, not double output."""
        from browserget import cli as cli_module

        patched_installers["chrome"].install = AsyncMock(
            side_effect=NetworkError("https://example.com", "timeout")
        )

        mock_registry = MagicMock()
        mock_registry.find = MagicMock(return_value=None)
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        result = runner.invoke(app, ["ensure", "chrome", "--json"])
        assert result.exit_code == 3
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert any(entry.get("status") == "error" for entry in data)
