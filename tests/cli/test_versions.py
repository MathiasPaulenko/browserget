"""Tests for the `versions` CLI command."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.exceptions import NetworkError


class TestVersions:
    """Versions command tests."""

    def test_versions_chrome(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """versions chrome → table of available versions, exit 0."""
        from browserget import cli as cli_module

        async def _fake_fetch(target: str, http: object) -> list[str]:
            return ["131.0.6778.87", "131.0.6778.80", "130.0.6723.116"]

        monkeypatch.setattr(cli_module, "_fetch_available_versions", _fake_fetch)

        result = runner.invoke(app, ["versions", "chrome"])
        assert result.exit_code == 0
        assert "131.0.6778.87" in result.stdout
        assert "Available versions" in result.stdout

    def test_versions_json(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """versions chrome --json → JSON array."""
        from browserget import cli as cli_module

        async def _fake_fetch(target: str, http: object) -> list[str]:
            return ["131.0.6778.87", "130.0.6723.116"]

        monkeypatch.setattr(cli_module, "_fetch_available_versions", _fake_fetch)

        result = runner.invoke(app, ["versions", "chrome", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0] == "131.0.6778.87"

    def test_versions_unknown_target(self, runner: CliRunner) -> None:
        """versions unknown → exit 2."""
        result = runner.invoke(app, ["versions", "unknown"])
        assert result.exit_code == 2

    def test_versions_network_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """versions chrome (network error) → exit 3."""
        from browserget import cli as cli_module

        async def _fake_fetch(target: str, http: object) -> list[str]:
            raise NetworkError("https://example.com", "timeout")

        monkeypatch.setattr(cli_module, "_fetch_available_versions", _fake_fetch)

        result = runner.invoke(app, ["versions", "chrome"])
        assert result.exit_code == 3

    def test_versions_more_than_20(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """versions with >20 results → table shows 20, JSON shows all."""
        from browserget import cli as cli_module

        all_versions = [f"130.0.{i}.0" for i in range(25)]

        async def _fake_fetch(target: str, http: object) -> list[str]:
            return all_versions

        monkeypatch.setattr(cli_module, "_fetch_available_versions", _fake_fetch)

        result = runner.invoke(app, ["versions", "chrome"])
        assert result.exit_code == 0
        assert "and 5 more" in result.stdout

        result_json = runner.invoke(app, ["versions", "chrome", "--json"])
        assert result_json.exit_code == 0
        data = json.loads(result_json.stdout)
        assert len(data) == 25
