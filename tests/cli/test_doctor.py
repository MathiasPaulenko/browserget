"""Tests for the `doctor` CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from browserget.cli import app


class TestDoctor:
    """Doctor command tests."""

    def test_doctor_clean_state(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """doctor (clean state) → all checks pass, exit 0."""
        from browserget import cli as cli_module

        tmp_path = MagicMock()
        tmp_path.exists = MagicMock(return_value=True)
        tmp_path.is_dir = MagicMock(return_value=True)
        monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))

        monkeypatch.setattr(cli_module, "get_cache_size", lambda: 1024 * 1024 * 50)
        monkeypatch.setattr(
            "browserget.cli.shutil.disk_usage",
            lambda p: MagicMock(free=1024 * 1024 * 5000),
        )

        mock_registry = MagicMock()
        mock_registry.load = MagicMock(return_value={"chrome": []})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        mock_detector = MagicMock()
        mock_detector.detect_all = MagicMock(
            return_value=[MagicMock(name="chrome", version="131.0")]
        )
        monkeypatch.setattr(cli_module, "SystemDetector", lambda: mock_detector)

        async def _fake_check(http: object) -> list[tuple[str, bool, str]]:
            return [
                ("CfT API", True, "reachable"),
                ("Firefox FTP", True, "reachable"),
                ("Edge API", True, "reachable"),
                ("EdgeDriver CDN", True, "reachable"),
                ("GitHub API", True, "reachable"),
            ]

        monkeypatch.setattr(cli_module, "_check_connectivity", _fake_check)

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "\u2713" in result.stdout

    def test_doctor_cache_dir_missing(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """doctor (cache dir missing) → ✗ for cache check, exit 0."""
        from browserget import cli as cli_module

        tmp_path = MagicMock()
        tmp_path.exists = MagicMock(return_value=False)
        monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))

        monkeypatch.setattr(cli_module, "get_cache_size", lambda: 0)
        monkeypatch.setattr(
            "browserget.cli.shutil.disk_usage",
            lambda p: MagicMock(free=1024 * 1024 * 5000),
        )

        mock_registry = MagicMock()
        mock_registry.load = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        mock_detector = MagicMock()
        mock_detector.detect_all = MagicMock(return_value=[])
        monkeypatch.setattr(cli_module, "SystemDetector", lambda: mock_detector)

        async def _fake_check(http: object) -> list[tuple[str, bool, str]]:
            return [
                ("CfT API", True, "reachable"),
                ("Firefox FTP", True, "reachable"),
                ("Edge API", True, "reachable"),
                ("EdgeDriver CDN", True, "reachable"),
                ("GitHub API", True, "reachable"),
            ]

        monkeypatch.setattr(cli_module, "_check_connectivity", _fake_check)

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "\u2717" in result.stdout
        assert "Cache directory" in result.stdout

    def test_doctor_no_system_browsers(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """doctor (no system browsers) → ✗ for browser checks, exit 0."""
        from browserget import cli as cli_module

        tmp_path = MagicMock()
        tmp_path.exists = MagicMock(return_value=True)
        tmp_path.is_dir = MagicMock(return_value=True)
        monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))

        monkeypatch.setattr(cli_module, "get_cache_size", lambda: 0)
        monkeypatch.setattr(
            "browserget.cli.shutil.disk_usage",
            lambda p: MagicMock(free=1024 * 1024 * 5000),
        )

        mock_registry = MagicMock()
        mock_registry.load = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        mock_detector = MagicMock()
        mock_detector.detect_all = MagicMock(return_value=[])
        monkeypatch.setattr(cli_module, "SystemDetector", lambda: mock_detector)

        async def _fake_check(http: object) -> list[tuple[str, bool, str]]:
            return [
                ("CfT API", True, "reachable"),
                ("Firefox FTP", True, "reachable"),
                ("Edge API", True, "reachable"),
                ("EdgeDriver CDN", True, "reachable"),
                ("GitHub API", True, "reachable"),
            ]

        monkeypatch.setattr(cli_module, "_check_connectivity", _fake_check)

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "\u2717" in result.stdout
        assert "System browsers" in result.stdout

    def test_doctor_network_down(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """doctor (network down) → ✗ for connectivity, exit 0."""
        from browserget import cli as cli_module

        tmp_path = MagicMock()
        tmp_path.exists = MagicMock(return_value=True)
        tmp_path.is_dir = MagicMock(return_value=True)
        monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))

        monkeypatch.setattr(cli_module, "get_cache_size", lambda: 0)
        monkeypatch.setattr(
            "browserget.cli.shutil.disk_usage",
            lambda p: MagicMock(free=1024 * 1024 * 5000),
        )

        mock_registry = MagicMock()
        mock_registry.load = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        mock_detector = MagicMock()
        mock_detector.detect_all = MagicMock(
            return_value=[MagicMock(name="chrome", version="131.0")]
        )
        monkeypatch.setattr(cli_module, "SystemDetector", lambda: mock_detector)

        async def _fake_check(http: object) -> list[tuple[str, bool, str]]:
            return [
                ("CfT API", False, "unreachable"),
                ("Firefox FTP", False, "unreachable"),
                ("Edge API", False, "unreachable"),
                ("EdgeDriver CDN", False, "unreachable"),
                ("GitHub API", False, "unreachable"),
            ]

        monkeypatch.setattr(cli_module, "_check_connectivity", _fake_check)

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "\u2717" in result.stdout

    def test_doctor_always_exit_0(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """doctor with partial failures → still exit 0."""
        from browserget import cli as cli_module

        tmp_path = MagicMock()
        tmp_path.exists = MagicMock(return_value=False)
        monkeypatch.setattr(cli_module, "load_config", lambda: MagicMock(cache_dir=tmp_path))

        monkeypatch.setattr(cli_module, "get_cache_size", lambda: 0)
        monkeypatch.setattr(
            "browserget.cli.shutil.disk_usage",
            lambda p: MagicMock(free=1024 * 1024 * 100),
        )

        mock_registry = MagicMock()
        mock_registry.load = MagicMock(return_value={})
        monkeypatch.setattr(cli_module, "Registry", lambda _: mock_registry)

        mock_detector = MagicMock()
        mock_detector.detect_all = MagicMock(return_value=[])
        monkeypatch.setattr(cli_module, "SystemDetector", lambda: mock_detector)

        async def _fake_check(http: object) -> list[tuple[str, bool, str]]:
            return [
                ("CfT API", False, "unreachable"),
                ("Firefox FTP", False, "unreachable"),
                ("Edge API", False, "unreachable"),
                ("EdgeDriver CDN", False, "unreachable"),
                ("GitHub API", False, "unreachable"),
            ]

        monkeypatch.setattr(cli_module, "_check_connectivity", _fake_check)

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
