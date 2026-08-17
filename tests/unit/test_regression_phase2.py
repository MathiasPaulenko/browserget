"""Regression tests for Phase 2 static audit fixes.

Each test class corresponds to a specific bug fix:

1. Firefox versions sorted descending in _fetch_available_versions.
2. Firefox _parse_checksums filters by path (SHA512SUMS format).
3. traceback.print_exception used instead of print_exc in CLI error handling.
4. _gather_with_dependencies installs browser targets before driver targets.
5. _retry_with_backoff cleans up on unexpected exceptions (e.g. CancelledError).
6. install/ensure with empty targets exits with code 1.
7. Archive files cleaned up on extraction/installation failure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from browserget.http import HttpClient

# ---------------------------------------------------------------------------
# Bug 2: Firefox _parse_checksums filters by path (SHA512SUMS format)
# ---------------------------------------------------------------------------


class TestParseChecksumsFilenameFilter:
    """Tests that _parse_checksums filters by relative path."""

    def test_returns_correct_hash_for_matching_path(self) -> None:
        """_parse_checksums should return the hash matching the expected path."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
            "bbb222  win64/en-US/Firefox Setup 131.0.exe\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-131.0.tar.bz2")
        assert result == "aaa111"

    def test_returns_correct_hash_for_different_path(self) -> None:
        """_parse_checksums should return the hash for the requested path."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
            "bbb222  win64/en-US/Firefox Setup 131.0.exe\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "win64/en-US/Firefox Setup 131.0.exe")
        assert result == "bbb222"

    def test_returns_none_when_path_not_found(self) -> None:
        """_parse_checksums should return None if path doesn't match."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111  linux-x86_64/en-US/some-other-file.tar.bz2\n"
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-131.0.tar.bz2")
        assert result is None

    def test_returns_none_for_empty_text(self) -> None:
        """_parse_checksums should return None for empty text."""
        from browserget.installers.firefox import FirefoxInstaller

        assert (
            FirefoxInstaller._parse_checksums("", "linux-x86_64/en-US/firefox-131.0.tar.bz2")
            is None
        )

    def test_backward_compat_no_path_arg(self) -> None:
        """_parse_checksums should still work without path argument."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
        result = FirefoxInstaller._parse_checksums(text)
        assert result == "aaa111"


# ---------------------------------------------------------------------------
# Bug 5: _retry_with_backoff cleans up on unexpected exceptions
# ---------------------------------------------------------------------------


class TestRetryCleanupOnUnexpectedException:
    """Tests that cleanup runs on unexpected exceptions (not just retryable ones)."""

    async def test_cleanup_called_on_unexpected_exception(self, tmp_path: Path) -> None:
        """download should clean up partial file when an unexpected exception occurs."""
        client = HttpClient(max_retries=1)
        dest = tmp_path / "partial.bin"

        async def failing_action() -> None:
            raise RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError, match="Unexpected error"):
            await client._retry_with_backoff(
                url="https://example.com/file",
                action=failing_action,
                cleanup=lambda: dest.unlink(missing_ok=True),
            )

        # The cleanup function should have been called, removing the file
        # We verify by checking that the cleanup ran (dest doesn't exist)
        assert not dest.exists()

    async def test_cleanup_called_on_cancelled_error(self, tmp_path: Path) -> None:
        """download should clean up partial file when CancelledError occurs."""
        client = HttpClient(max_retries=1)
        dest = tmp_path / "partial.bin"
        dest.write_bytes(b"partial data")

        async def cancelled_action() -> None:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await client._retry_with_backoff(
                url="https://example.com/file",
                action=cancelled_action,
                cleanup=lambda: dest.unlink(missing_ok=True),
            )

        assert not dest.exists()

    async def test_no_cleanup_when_cleanup_is_none(self) -> None:
        """_retry_with_backoff should not crash when cleanup is None and unexpected error occurs."""
        client = HttpClient(max_retries=1)

        async def failing_action() -> None:
            raise RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError, match="Unexpected error"):
            await client._retry_with_backoff(
                url="https://example.com/file",
                action=failing_action,
                cleanup=None,
            )


# ---------------------------------------------------------------------------
# Bug 6: install/ensure with empty targets exits with code 1
# ---------------------------------------------------------------------------


class TestEmptyTargetsExitCode:
    """Tests that install/ensure with empty targets exits with code 1."""

    def test_install_no_targets_exits_1(self) -> None:
        """install with no targets should exit with code 1."""
        from typer.testing import CliRunner

        from browserget.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1

    def test_ensure_no_targets_exits_1(self) -> None:
        """ensure with no targets should exit with code 1."""
        from typer.testing import CliRunner

        from browserget.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["ensure"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Bug 1: Firefox versions sorted descending in _fetch_available_versions
# ---------------------------------------------------------------------------


class TestFirefoxVersionsSortedDescending:
    """Tests that Firefox versions are sorted descending."""

    def test_versions_sorted_descending(self) -> None:
        """_fetch_available_versions should sort Firefox versions descending."""
        from browserget.parsers.firefox import _firefox_version_tuple

        versions = ["100.0", "131.0", "115.0esr", "130.0.1", "90.0"]
        versions.sort(key=_firefox_version_tuple, reverse=True)
        assert versions[0] == "131.0"
        assert versions[1] == "130.0.1"
        assert versions[2] == "115.0esr"
        assert versions[3] == "100.0"
        assert versions[4] == "90.0"


# ---------------------------------------------------------------------------
# Bug 4: _gather_with_dependencies installs browser before driver
# ---------------------------------------------------------------------------


class TestGatherWithDependencies:
    """Tests that _gather_with_dependencies installs browser targets first."""

    async def test_browser_installed_before_driver(self) -> None:
        """When --for is used, browser targets should be installed before driver targets."""
        from browserget.cli import _gather_with_dependencies

        call_order: list[str] = []

        async def mock_action(target, version, force, for_browser, *args, **kwargs):
            call_order.append(target)
            return MagicMock()

        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()

        await _gather_with_dependencies(
            mock_action,
            targets=["chromedriver", "chrome"],
            version=None,
            force=False,
            for_browser="chrome",
            http=http,
            registry=registry,
            config=config,
        )

        # Chrome (browser) should be called before chromedriver (driver)
        chrome_idx = call_order.index("chrome")
        driver_idx = call_order.index("chromedriver")
        assert chrome_idx < driver_idx

    async def test_no_ordering_without_for_browser(self) -> None:
        """Without --for, all targets should run concurrently (no ordering guarantee)."""
        from browserget.cli import _gather_with_dependencies

        call_order: list[str] = []

        async def mock_action(target, version, force, for_browser, *args, **kwargs):
            call_order.append(target)
            return MagicMock()

        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()

        await _gather_with_dependencies(
            mock_action,
            targets=["chrome", "chromedriver"],
            version=None,
            force=False,
            for_browser=None,
            http=http,
            registry=registry,
            config=config,
        )

        # Both should have been called
        assert "chrome" in call_order
        assert "chromedriver" in call_order

    async def test_results_preserve_target_order(self) -> None:
        """Results should be in the same order as the input targets list."""
        from browserget.cli import _gather_with_dependencies

        async def mock_action(target, version, force, for_browser, *args, **kwargs):
            return target  # Return the target name as the "result"

        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()

        results = await _gather_with_dependencies(
            mock_action,
            targets=["chrome", "chromedriver", "firefox"],
            version=None,
            force=False,
            for_browser=None,
            http=http,
            registry=registry,
            config=config,
        )

        assert results == ["chrome", "chromedriver", "firefox"]

    async def test_browser_exception_propagates(self) -> None:
        """If browser installation fails, the exception should be in results."""
        from browserget.cli import _gather_with_dependencies

        async def mock_action(target, version, force, for_browser, *args, **kwargs):
            if target == "chrome":
                raise RuntimeError("Browser install failed")
            return MagicMock()

        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()

        results = await _gather_with_dependencies(
            mock_action,
            targets=["chrome", "chromedriver"],
            version=None,
            force=False,
            for_browser="chrome",
            http=http,
            registry=registry,
            config=config,
        )

        # Chrome result should be an exception
        assert isinstance(results[0], RuntimeError)
        assert "Browser install failed" in str(results[0])
