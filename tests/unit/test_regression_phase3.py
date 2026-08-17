"""Regression tests for Phase 3 bug fixes.

Covers:
- Bug 8: extract_tar symlink/hardlink path traversal protection
- Bug 9: Edge _install_macos/_install_linux archive cleanup on failure
- Bug 10: CLI commands handle non-BrowsergetError exceptions gracefully
- Bug 11: cleanup_downloads stops on first OSError
- Bug 12: remove command stops on shutil.rmtree failure, leaves registry dirty
- Bug 13: doctor connectivity check doesn't catch all Exception types
- Bug 14: _exit_with_error uses exact type matching, fails for subclasses
"""

from __future__ import annotations

import io
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

from browserget.archive import extract_tar
from browserget.config import Config
from browserget.models import InstalledArtifact

# ---------------------------------------------------------------------------
# Bug 8: extract_tar symlink/hardlink path traversal protection
# ---------------------------------------------------------------------------


class TestTarSymlinkPathTraversal:
    """Tests that extract_tar rejects symlinks pointing outside dest."""

    def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        """A tar with a symlink pointing outside dest is rejected."""
        archive = tmp_path / "evil_symlink.tar.gz"

        with tarfile.open(archive, "w:gz") as tf:
            link_info = tarfile.TarInfo(name="link.txt")
            link_info.type = tarfile.SYMTYPE
            link_info.linkname = "../../etc/passwd"
            tf.addfile(link_info)

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_tar(archive, dest)

    def test_hardlink_escape_blocked(self, tmp_path: Path) -> None:
        """A tar with a hardlink pointing outside dest is rejected."""
        archive = tmp_path / "evil_hardlink.tar.gz"

        with tarfile.open(archive, "w:gz") as tf:
            link_info = tarfile.TarInfo(name="link.txt")
            link_info.type = tarfile.LNKTYPE
            link_info.linkname = "../../etc/passwd"
            tf.addfile(link_info)

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_tar(archive, dest)

    def test_safe_symlink_inside_dest_allowed(self, tmp_path: Path) -> None:
        """A symlink pointing inside dest is allowed."""
        archive = tmp_path / "safe_symlink.tar.gz"
        data = b"target content"

        with tarfile.open(archive, "w:gz") as tf:
            # Add a real file
            info = tarfile.TarInfo(name="target.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

            # Add a symlink pointing to target.txt (inside dest)
            link_info = tarfile.TarInfo(name="link.txt")
            link_info.type = tarfile.SYMTYPE
            link_info.linkname = "target.txt"
            tf.addfile(link_info)

        dest = tmp_path / "dest"
        extract_tar(archive, dest)

        assert (dest / "target.txt").read_bytes() == data


# ---------------------------------------------------------------------------
# Bug 9: Edge _install_macos/_install_linux archive cleanup on failure
# ---------------------------------------------------------------------------


class TestEdgeArchiveCleanup:
    """Tests that Edge installer cleans up archive on failure."""

    def test_install_macos_cleans_up_on_checksum_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_install_macos should delete archive when checksum verification fails."""
        from browserget.installers.edge import EdgeInstaller
        from browserget.models import ResolvedVersion

        # Create a fake archive file
        download_dir = tmp_path / "downloads"
        download_dir.mkdir(parents=True)
        archive_path = download_dir / "edge.pkg"
        archive_path.write_bytes(b"fake archive")

        # Mock everything
        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()
        config.cache_dir = tmp_path

        installer = EdgeInstaller(http, registry, config)

        # Mock detect_edge to return None (force download path)
        monkeypatch.setattr(
            "browserget.installers.edge.SystemDetector.detect_edge",
            lambda self: None,
        )
        # Mock disk space check
        monkeypatch.setattr("browserget.installers.edge.check_disk_space", lambda mb: True)

        # Mock download to not overwrite our file
        async def fake_download(url: str, dest: Path) -> None:
            pass

        http.download = fake_download

        # Mock get_download_dir to return our dir
        monkeypatch.setattr("browserget.installers.edge.get_download_dir", lambda: download_dir)

        resolved = ResolvedVersion(
            name="edge",
            version="127.0.2651.74",
            url="https://example.com/edge.pkg",
            platform="macos",
            checksum="wronghash",
            checksum_algorithm="sha256",
        )

        # Checksum verification should fail and raise
        from browserget.exceptions import ChecksumMismatchError

        with pytest.raises(ChecksumMismatchError):
            import asyncio

            asyncio.run(installer._install_macos(resolved, force=True))

        # Archive should be cleaned up
        assert not archive_path.exists()

    def test_install_linux_cleans_up_on_checksum_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_install_linux should delete archive when checksum verification fails."""
        from browserget.installers.edge import EdgeInstaller
        from browserget.models import ResolvedVersion

        # Create a fake archive file
        download_dir = tmp_path / "downloads"
        download_dir.mkdir(parents=True)
        archive_path = download_dir / "edge.deb"
        archive_path.write_bytes(b"fake archive")

        # Mock everything
        http = MagicMock()
        registry = MagicMock()
        config = MagicMock()
        config.cache_dir = tmp_path

        installer = EdgeInstaller(http, registry, config)

        # Mock detect_edge to return None (force download path)
        monkeypatch.setattr(
            "browserget.installers.edge.SystemDetector.detect_edge",
            lambda self: None,
        )
        # Mock disk space check
        monkeypatch.setattr("browserget.installers.edge.check_disk_space", lambda mb: True)

        # Mock download
        async def fake_download(url: str, dest: Path) -> None:
            pass

        http.download = fake_download

        # Mock get_download_dir to return our dir
        monkeypatch.setattr("browserget.installers.edge.get_download_dir", lambda: download_dir)

        resolved = ResolvedVersion(
            name="edge",
            version="127.0.2651.74",
            url="https://example.com/edge.deb",
            platform="linux64",
            checksum="wronghash",
            checksum_algorithm="sha256",
        )

        from browserget.exceptions import ChecksumMismatchError

        with pytest.raises(ChecksumMismatchError):
            import asyncio

            asyncio.run(installer._install_linux(resolved, force=True))

        # Archive should be cleaned up
        assert not archive_path.exists()


# ---------------------------------------------------------------------------
# Bug 10: CLI commands handle non-BrowsergetError exceptions
# ---------------------------------------------------------------------------


class TestCliNonBrowsergetErrorHandling:
    """Tests that CLI commands handle non-BrowsergetError exceptions gracefully."""

    def test_versions_command_handles_runtime_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """versions command should handle RuntimeError without crashing."""
        from browserget.cli import versions

        # Mock _run_async to raise RuntimeError before any coroutine is created
        def fake_run_async(coro_factory):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("browserget.cli._run_async", fake_run_async)
        monkeypatch.setattr("browserget.cli.load_config", lambda: MagicMock(cache_dir=tmp_path))
        monkeypatch.setattr("browserget.cli.setup_logging", lambda **kw: None)
        # Mock _fetch_available_versions to avoid creating a real coroutine
        monkeypatch.setattr("browserget.cli._fetch_available_versions", MagicMock(return_value=[]))

        import typer

        with pytest.raises(typer.Exit) as exc_info:
            versions("chrome", json_output=False)

        # Should exit with code 1 (default for unknown exceptions)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Bug 11: cleanup_downloads stops on first OSError
# ---------------------------------------------------------------------------


class TestCleanupDownloadsResilience:
    """Tests that cleanup_downloads continues past individual failures."""

    def test_cleanup_continues_past_failed_item(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """cleanup_downloads should not stop when one item fails to delete."""
        from browserget.cache import cleanup_downloads

        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        monkeypatch.setattr("browserget.cache.get_download_dir", lambda: download_dir)

        good_file = download_dir / "good.txt"
        good_file.write_text("delete me")
        bad_file = download_dir / "bad.txt"
        bad_file.write_text("locked")

        # Make bad_file.unlink raise OSError, but good_file should still be deleted
        original_unlink = Path.unlink

        def selective_unlink(self: Path, *args: object, **kwargs: object) -> None:
            if self == bad_file:
                raise OSError("Permission denied")
            original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "unlink", selective_unlink)

        cleanup_downloads()

        assert not good_file.exists()


# ---------------------------------------------------------------------------
# Bug 12: remove command stops on shutil.rmtree failure, leaves registry dirty
# ---------------------------------------------------------------------------


class TestRemoveCommandResilience:
    """Tests that the remove command handles directory deletion failures gracefully."""

    def test_remove_all_continues_past_failed_rmtree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """remove --all should continue removing registry entries even if rmtree fails."""
        from browserget.cli import remove
        from browserget.registry import Registry

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        registry = Registry(cache_dir)

        # Add two artifacts to the registry
        for ver in ("1.0", "2.0"):
            artifact_dir = cache_dir / "chrome" / ver
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "chrome").write_text("fake")
            registry.add(
                InstalledArtifact(
                    name="chrome",
                    version=ver,
                    path=artifact_dir / "chrome",
                    installed_at=datetime.now(UTC),
                    checksum=None,
                )
            )

        monkeypatch.setattr("browserget.cli.load_config", lambda: Config(cache_dir=cache_dir))
        monkeypatch.setattr("browserget.cli.get_artifact_dir", lambda n, v: cache_dir / n / v)

        # Make rmtree fail for the first artifact directory
        original_rmtree = shutil.rmtree

        def selective_rmtree(path: Path, *args: object, **kwargs: object) -> None:
            if "1.0" in str(path):
                raise OSError("Permission denied")
            original_rmtree(path, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr("browserget.cli.shutil.rmtree", selective_rmtree)

        remove("chrome", all_versions=True)

        # Both registry entries should be removed even though 1.0's dir failed
        data = registry.load()
        assert "chrome" not in data
        # 2.0's directory should be deleted
        assert not (cache_dir / "chrome" / "2.0").exists()

    def test_remove_single_cleans_registry_on_rmtree_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """remove should still clean up the registry entry if directory deletion fails."""
        from browserget.cli import remove
        from browserget.registry import Registry

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        registry = Registry(cache_dir)

        artifact_dir = cache_dir / "chrome" / "1.0"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "chrome").write_text("fake")
        registry.add(
            InstalledArtifact(
                name="chrome",
                version="1.0",
                path=artifact_dir / "chrome",
                installed_at=datetime.now(UTC),
                checksum=None,
            )
        )

        monkeypatch.setattr("browserget.cli.load_config", lambda: Config(cache_dir=cache_dir))
        monkeypatch.setattr("browserget.cli.get_artifact_dir", lambda n, v: cache_dir / n / v)

        def _fail_rmtree(*a: object, **kw: object) -> None:
            raise OSError("Permission denied")

        monkeypatch.setattr("browserget.cli.shutil.rmtree", _fail_rmtree)

        remove("chrome", version="1.0")

        # Registry entry should be removed even though directory deletion failed
        data = registry.load()
        assert "chrome" not in data


# ---------------------------------------------------------------------------
# Bug 13: doctor command connectivity check doesn't catch all Exception types
# ---------------------------------------------------------------------------


class TestDoctorConnectivityExceptionHandling:
    """Tests that the doctor command handles unexpected exceptions in connectivity check."""

    def test_doctor_handles_type_error_from_run_async(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """doctor should not crash if _run_async raises an unexpected exception type."""
        from browserget.cli import doctor

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        monkeypatch.setattr("browserget.cli.load_config", lambda: Config(cache_dir=cache_dir))
        monkeypatch.setattr("browserget.cli.get_cache_size", lambda: 0)

        # Make _run_async raise TypeError (not OSError, BrowsergetError, or RuntimeError)
        def _fail_run_async(_coro: object) -> object:
            raise TypeError("Unexpected event loop error")

        monkeypatch.setattr("browserget.cli._run_async", _fail_run_async)

        # Should not raise — should report all APIs as unreachable
        doctor()


# ---------------------------------------------------------------------------
# Bug 14: _exit_with_error uses exact type matching, fails for subclasses
# ---------------------------------------------------------------------------


class TestExitCodeSubclassHandling:
    """Tests that _exit_with_error returns correct exit codes for subclassed exceptions."""

    def test_subclassed_exception_gets_parent_exit_code(self) -> None:
        """A subclass of NetworkError should get NetworkError's exit code, not 1."""
        from browserget.cli import _exit_with_error
        from browserget.exceptions import NetworkError

        class CustomNetworkError(NetworkError):
            pass

        exc = CustomNetworkError(url="http://example.com", reason="test")
        try:
            _exit_with_error(exc, json_output=False, debug=False)
        except typer.Exit as e:
            assert e.exit_code == 3
        else:
            pytest.fail("Expected typer.Exit to be raised")

    def test_subclassed_version_not_found_gets_correct_code(self) -> None:
        """A subclass of VersionNotFoundError should get its exit code, not 1."""
        from browserget.cli import _exit_with_error
        from browserget.exceptions import VersionNotFoundError

        class CustomVersionError(VersionNotFoundError):
            pass

        exc = CustomVersionError(version="1.0", name="chrome", top_3_versions="1.0, 2.0")
        try:
            _exit_with_error(exc, json_output=False, debug=False)
        except typer.Exit as e:
            assert e.exit_code == 2
        else:
            pytest.fail("Expected typer.Exit to be raised")


# ---------------------------------------------------------------------------
# Bug 15: _fetch_text_sync doesn't wrap UnicodeDecodeError in NetworkError
# ---------------------------------------------------------------------------


class TestFetchTextEncodingError:
    """Tests that _fetch_text_sync wraps UnicodeDecodeError in NetworkError."""

    def test_non_utf8_response_raises_network_error(self) -> None:
        """A response with invalid UTF-8 should raise NetworkError, not UnicodeDecodeError."""
        from unittest.mock import patch

        from browserget.exceptions import NetworkError
        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=1)

        # Create a response-like context manager that returns non-UTF-8 bytes
        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                pass

            def read(self) -> bytes:
                # Invalid UTF-8 byte sequence
                return b"\xff\xfe\x00invalid"

        with (
            patch("urllib.request.urlopen", return_value=FakeResponse()),
            pytest.raises(NetworkError, match="not valid UTF-8"),
        ):
            client._fetch_text_sync("http://example.com/test")


# ---------------------------------------------------------------------------
# Bug 16: install/ensure commands use type() for exit code lookup, fails for subclasses
# ---------------------------------------------------------------------------


class TestInstallEnsureExitCodeSubclassHandling:
    """Tests that _get_exit_code handles subclassed exceptions correctly."""

    def test_get_exit_code_subclassed_network_error(self) -> None:
        """A subclass of NetworkError should get NetworkError's exit code."""
        from browserget.cli import _get_exit_code
        from browserget.exceptions import NetworkError

        class CustomNetworkError(NetworkError):
            pass

        exc = CustomNetworkError(url="http://example.com", reason="test")
        assert _get_exit_code(exc) == 3

    def test_get_exit_code_subclassed_version_not_found(self) -> None:
        """A subclass of VersionNotFoundError should get its exit code."""
        from browserget.cli import _get_exit_code
        from browserget.exceptions import VersionNotFoundError

        class CustomVersionError(VersionNotFoundError):
            pass

        exc = CustomVersionError(version="1.0", name="chrome", top_3_versions="1.0, 2.0")
        assert _get_exit_code(exc) == 2

    def test_get_exit_code_unmapped_exception_returns_1(self) -> None:
        """An unmapped exception type should return exit code 1."""
        from browserget.cli import _get_exit_code

        exc = RuntimeError("something went wrong")
        assert _get_exit_code(exc) == 1


# ---------------------------------------------------------------------------
# Bug 17: _retry_with_backoff makes zero attempts when max_retries=0
# ---------------------------------------------------------------------------


class TestMaxRetriesZeroAttempts:
    """Tests that HttpClient still tries at least once when max_retries=0."""

    def test_max_retries_zero_still_attempts_once(self) -> None:
        """With max_retries=0, the client should still make one request attempt."""
        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=0)

        call_count = 0

        async def mock_action() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        import asyncio

        result = asyncio.new_event_loop().run_until_complete(
            client._retry_with_backoff("http://example.com", mock_action)
        )
        assert result == "success"
        assert call_count == 1

    def test_max_retries_zero_raises_on_failure(self) -> None:
        """With max_retries=0, a network error should still raise NetworkError after one attempt."""
        import asyncio

        from browserget.exceptions import NetworkError
        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=0)

        call_count = 0

        async def mock_action() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("connection refused")

        with pytest.raises(NetworkError, match="connection refused"):
            asyncio.new_event_loop().run_until_complete(
                client._retry_with_backoff("http://example.com", mock_action)
            )
        assert call_count == 1


# ---------------------------------------------------------------------------
# Bug 18: config.py doesn't validate negative timeout/max_retries
# ---------------------------------------------------------------------------


class TestBug18NegativeConfigValues:
    """Regression tests for Bug 18: negative timeout/max_retries from env vars.

    Setting BROWSERGET_TIMEOUT=-1 causes urllib.request.urlopen to raise
    a raw ValueError from socket.settimeout(), which propagates unhandled
    instead of being wrapped in NetworkError.  Similarly, negative
    max_retries is semantically nonsensical.
    """

    def test_negative_timeout_falls_back_to_default(self) -> None:
        """BROWSERGET_TIMEOUT=-1 should fall back to the default of 30."""
        import os

        from browserget.config import load_config

        old = os.environ.get("BROWSERGET_TIMEOUT")
        try:
            os.environ["BROWSERGET_TIMEOUT"] = "-1"
            config = load_config()
            assert config.timeout == 30
        finally:
            if old is None:
                os.environ.pop("BROWSERGET_TIMEOUT", None)
            else:
                os.environ["BROWSERGET_TIMEOUT"] = old

    def test_zero_timeout_falls_back_to_default(self) -> None:
        """BROWSERGET_TIMEOUT=0 (non-blocking) should fall back to default."""
        import os

        from browserget.config import load_config

        old = os.environ.get("BROWSERGET_TIMEOUT")
        try:
            os.environ["BROWSERGET_TIMEOUT"] = "0"
            config = load_config()
            assert config.timeout == 30
        finally:
            if old is None:
                os.environ.pop("BROWSERGET_TIMEOUT", None)
            else:
                os.environ["BROWSERGET_TIMEOUT"] = old

    def test_negative_max_retries_falls_back_to_default(self) -> None:
        """BROWSERGET_MAX_RETRIES=-1 should fall back to the default of 3."""
        import os

        from browserget.config import load_config

        old = os.environ.get("BROWSERGET_MAX_RETRIES")
        try:
            os.environ["BROWSERGET_MAX_RETRIES"] = "-1"
            config = load_config()
            assert config.max_retries == 3
        finally:
            if old is None:
                os.environ.pop("BROWSERGET_MAX_RETRIES", None)
            else:
                os.environ["BROWSERGET_MAX_RETRIES"] = old

    def test_zero_max_retries_is_allowed(self) -> None:
        """BROWSERGET_MAX_RETRIES=0 is valid (means no retries, 1 attempt)."""
        import os

        from browserget.config import load_config

        old = os.environ.get("BROWSERGET_MAX_RETRIES")
        try:
            os.environ["BROWSERGET_MAX_RETRIES"] = "0"
            config = load_config()
            assert config.max_retries == 0
        finally:
            if old is None:
                os.environ.pop("BROWSERGET_MAX_RETRIES", None)
            else:
                os.environ["BROWSERGET_MAX_RETRIES"] = old


# ---------------------------------------------------------------------------
# Bug 19: _parse_version_output returns wrong part for Chromium-style output
# ---------------------------------------------------------------------------


class TestBug19VersionParser:
    """Regression tests for Bug 19.

    _parse_version_output iterated in reverse and returned the last token
    containing any digit.  For Chromium output like "Chromium 131.0.6778.87,
    built on Linux, running on Ubuntu 22.04" it would return "22.04" instead
    of "131.0.6778.87".
    """

    def test_chromium_with_extra_info(self) -> None:
        """Chromium output with build info should extract the version, not '22.04'."""
        from browserget.system import SystemDetector

        output = "Chromium 131.0.6778.87, built on Linux, running on Ubuntu 22.04"
        result = SystemDetector._parse_version_output(output)
        assert result == "131.0.6778.87"

    def test_chrome_with_64bit_suffix(self) -> None:
        """Chrome output with '(64-bit)' should extract the version, not '(64-bit)'."""
        from browserget.system import SystemDetector

        output = "Google Chrome 131.0.6778.87 (64-bit)"
        result = SystemDetector._parse_version_output(output)
        assert result == "131.0.6778.87"

    def test_standard_chrome_output(self) -> None:
        """Standard Chrome output should still parse correctly."""
        from browserget.system import SystemDetector

        result = SystemDetector._parse_version_output("Google Chrome 131.0.6778.87")
        assert result == "131.0.6778.87"

    def test_standard_firefox_output(self) -> None:
        """Standard Firefox output should still parse correctly."""
        from browserget.system import SystemDetector

        result = SystemDetector._parse_version_output("Mozilla Firefox 129.0")
        assert result == "129.0"

    def test_standard_edge_output(self) -> None:
        """Standard Edge output should still parse correctly."""
        from browserget.system import SystemDetector

        result = SystemDetector._parse_version_output("Microsoft Edge 127.0.2651.74")
        assert result == "127.0.2651.74"

    def test_empty_output(self) -> None:
        """Empty output should return None."""
        from browserget.system import SystemDetector

        assert SystemDetector._parse_version_output("") is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only output should return None."""
        from browserget.system import SystemDetector

        assert SystemDetector._parse_version_output("   ") is None

    def test_no_digits(self) -> None:
        """Output with no digits should return None."""
        from browserget.system import SystemDetector

        assert SystemDetector._parse_version_output("Mozilla Firefox") is None


# ---------------------------------------------------------------------------
# Bug 20: _parse_checksums fallback returns wrong file's hash
# ---------------------------------------------------------------------------


class TestBug20ChecksumsFallback:
    """Regression tests for Bug 20.

    _parse_checksums returned a fallback SHA-512 hash from a different file
    when expected_path didn't match.  This caused checksum verification
    to use the wrong hash (e.g., hash for .tar.bz2 when downloading .exe),
    leading to a guaranteed ChecksumMismatchError.
    """

    def test_exact_path_match(self) -> None:
        """Should return the hash for the exact matching path."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  win64/en-US/Firefox Setup 131.0.exe\n"
            "bbb222  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "win64/en-US/Firefox Setup 131.0.exe")
        assert result == "aaa111"

    def test_no_match_returns_none(self) -> None:
        """Should return None when expected_path doesn't match any entry."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  win64/en-US/Firefox Setup 131.0.exe\n"
            "bbb222  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "nonexistent/path/file.zip")
        assert result is None

    def test_no_expected_path_returns_first(self) -> None:
        """Without expected_path, should return the first entry."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  win64/en-US/Firefox Setup 131.0.exe\n"
            "bbb222  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
        )
        result = FirefoxInstaller._parse_checksums(text)
        assert result == "aaa111"

    def test_empty_text(self) -> None:
        """Empty checksums text should return None."""
        from browserget.installers.firefox import FirefoxInstaller

        assert FirefoxInstaller._parse_checksums("", "win64/en-US/file.exe") is None

    def test_single_field_lines_ignored(self) -> None:
        """Lines with only one field (no path) should be ignored."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111\nbbb222  win64/en-US/Firefox Setup 131.0.exe\n"
        result = FirefoxInstaller._parse_checksums(text, "win64/en-US/Firefox Setup 131.0.exe")
        assert result == "bbb222"

    def test_path_with_spaces_handled_correctly(self) -> None:
        """Paths with spaces (e.g. 'Firefox Setup') should be handled correctly."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111  win64/en-US/Firefox Setup 131.0.exe\n"
        result = FirefoxInstaller._parse_checksums(text, "win64/en-US/Firefox Setup 131.0.exe")
        assert result == "aaa111"


# ---------------------------------------------------------------------------
# Bug 21: cleanup() exceptions in _retry_with_backoff mask original errors
# ---------------------------------------------------------------------------


class TestBug21CleanupExceptionMasking:
    """Regression tests for Bug 21.

    In ``_retry_with_backoff``, if ``cleanup()`` raised (e.g.
    ``PermissionError`` on Windows when a file is locked by antivirus),
    the cleanup exception propagated instead of the original ``NetworkError``,
    masking the real failure from the user.
    """

    def test_cleanup_exception_does_not_mask_http_error(self) -> None:
        """If cleanup() raises during HTTP error handling, NetworkError still propagates."""
        import asyncio
        import urllib.error

        from browserget.exceptions import NetworkError
        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=0)

        http_err = urllib.error.HTTPError(
            url="https://example.com/test",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

        def raising_cleanup() -> None:
            raise PermissionError("File locked by antivirus")

        async def failing_action() -> None:
            raise http_err

        async def run() -> None:
            await client._retry_with_backoff(
                url="https://example.com/test",
                action=failing_action,
                cleanup=raising_cleanup,
            )

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(run())
                raise AssertionError("Should have raised NetworkError")
            except NetworkError as exc:
                assert "HTTP 500" in exc.reason
            except PermissionError:
                raise AssertionError(
                    "PermissionError should not propagate over NetworkError"
                ) from None
        finally:
            loop.close()

    def test_cleanup_exception_does_not_mask_url_error(self) -> None:
        """If cleanup() raises during URLError handling, NetworkError still propagates."""
        import asyncio
        import urllib.error

        from browserget.exceptions import NetworkError
        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=0)

        url_err = urllib.error.URLError("Connection refused")

        def raising_cleanup() -> None:
            raise OSError("Permission denied")

        async def failing_action() -> None:
            raise url_err

        async def run() -> None:
            await client._retry_with_backoff(
                url="https://example.com/test",
                action=failing_action,
                cleanup=raising_cleanup,
            )

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(run())
                raise AssertionError("Should have raised NetworkError")
            except NetworkError:
                pass
            except OSError:
                raise AssertionError(
                    "OSError from cleanup should not propagate over NetworkError"
                ) from None
        finally:
            loop.close()

    def test_cleanup_exception_does_not_mask_base_exception(self) -> None:
        """If cleanup() raises during BaseException handling, original exception propagates."""
        import asyncio

        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=0)

        class CustomError(Exception):
            pass

        def raising_cleanup() -> None:
            raise OSError("File locked")

        async def failing_action() -> None:
            raise CustomError("Original failure")

        async def run() -> None:
            await client._retry_with_backoff(
                url="https://example.com/test",
                action=failing_action,
                cleanup=raising_cleanup,
            )

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(run())
                raise AssertionError("Should have raised CustomError")
            except CustomError:
                pass
            except OSError:
                raise AssertionError("OSError from cleanup should not mask CustomError") from None
        finally:
            loop.close()

    def test_cleanup_exception_does_not_prevent_retry(self) -> None:
        """If cleanup() raises during retry path, the retry should still proceed."""
        import asyncio
        import urllib.error

        from browserget.http import HttpClient

        client = HttpClient(timeout=5, max_retries=3)

        call_count = 0

        def raising_cleanup() -> None:
            raise OSError("File locked")

        async def action() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.URLError("Connection refused")
            return "success"

        async def run() -> str:
            return await client._retry_with_backoff(
                url="https://example.com/test",
                action=action,
                cleanup=raising_cleanup,
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run())
            assert result == "success"
            assert call_count == 3
        finally:
            loop.close()
            asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# Bug 22: get_cache_size follows symlinks causing infinite recursion
#          and incorrect size reporting
# ---------------------------------------------------------------------------


def _can_symlink(tmp_path: Path) -> bool:
    """Check if the platform supports creating symlinks."""
    import os

    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
        link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


def test_get_cache_size_ignores_symlink_to_file(tmp_path: Path) -> None:
    """Symlinks to files outside the cache must not be counted."""
    import os

    from browserget.cache import get_cache_size

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create a real file outside the cache
    external = tmp_path / "external.txt"
    external.write_bytes(b"X" * 1000)

    # Create a cache dir with a symlink to the external file
    cache = tmp_path / "cache"
    cache.mkdir()
    link = cache / "link.txt"
    os.symlink(external, link)

    # Also create a real file inside the cache
    real = cache / "real.txt"
    real.write_bytes(b"Y" * 500)

    # Monkey-patch load_config to return our cache dir
    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=cache)  # type: ignore[method-assign]
    try:
        size = get_cache_size()
    finally:
        cache_mod.load_config = original

    # Only the real file (500 bytes) should be counted, not the symlink target (1000)
    assert size == 500


def test_get_cache_size_ignores_symlink_to_directory(tmp_path: Path) -> None:
    """Symlinks to directories must not cause recursion into external dirs."""
    import os

    from browserget.cache import get_cache_size

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create an external directory with files
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "big.txt").write_bytes(b"Z" * 2000)

    # Create a cache dir with a symlink to the external directory
    cache = tmp_path / "cache"
    cache.mkdir()
    link = cache / "link_dir"
    os.symlink(external_dir, link, target_is_directory=True)

    # Create a real file inside the cache
    real = cache / "real.txt"
    real.write_bytes(b"Y" * 300)

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=cache)  # type: ignore[method-assign]
    try:
        size = get_cache_size()
    finally:
        cache_mod.load_config = original

    # Only the real file (300 bytes) should be counted
    assert size == 300


# ---------------------------------------------------------------------------
# Bug 23: cleanup_downloads calls rmtree on symlinks-to-directories
#          instead of unlinking the symlink itself
# ---------------------------------------------------------------------------


def test_cleanup_downloads_unlinks_symlink_to_directory(tmp_path: Path) -> None:
    """Symlinks to directories must be unlinked, not rmtree'd."""
    import os

    from browserget.cache import cleanup_downloads

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create an external directory with files
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "data.txt").write_text("important data")

    # Create a download dir with a symlink to the external directory
    download_dir = tmp_path / "cache" / "downloads"
    download_dir.mkdir(parents=True)
    link = download_dir / "evil_link"
    os.symlink(external_dir, link, target_is_directory=True)

    # Also create a normal file
    normal = download_dir / "normal.txt"
    normal.write_text("temp")

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path / "cache")  # type: ignore[method-assign]
    try:
        cleanup_downloads()
    finally:
        cache_mod.load_config = original

    # The symlink should be removed
    assert not link.exists()
    # The normal file should be removed
    assert not normal.exists()
    # The external directory must be untouched
    assert external_dir.exists()
    assert (external_dir / "data.txt").read_text() == "important data"


def test_cleanup_downloads_unlinks_symlink_to_file(tmp_path: Path) -> None:
    """Symlinks to files must be unlinked, not followed."""
    import os

    from browserget.cache import cleanup_downloads

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create an external file
    external = tmp_path / "external.txt"
    external.write_text("important")

    # Create a download dir with a symlink to the external file
    download_dir = tmp_path / "cache" / "downloads"
    download_dir.mkdir(parents=True)
    link = download_dir / "link.txt"
    os.symlink(external, link)

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path / "cache")  # type: ignore[method-assign]
    try:
        cleanup_downloads()
    finally:
        cache_mod.load_config = original

    # The symlink should be removed
    assert not link.exists()
    # The external file must be untouched
    assert external.exists()
    assert external.read_text() == "important"


# ---------------------------------------------------------------------------
# Bug 24: cleanup_downloads doesn't handle download_dir itself being a symlink
# ---------------------------------------------------------------------------


def test_cleanup_downloads_unlinks_symlinked_download_dir(tmp_path: Path) -> None:
    """If download_dir itself is a symlink, it should be unlinked, not recursed into."""
    import os

    from browserget.cache import cleanup_downloads

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create a real target directory with important files
    real_target = tmp_path / "real_downloads"
    real_target.mkdir()
    (real_target / "important.txt").write_text("do not delete")

    # Create the cache dir, and make "downloads" a symlink to real_target
    cache = tmp_path / "cache"
    cache.mkdir()
    download_symlink = cache / "downloads"
    os.symlink(real_target, download_symlink, target_is_directory=True)

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=cache)  # type: ignore[method-assign]
    try:
        cleanup_downloads()
    finally:
        cache_mod.load_config = original

    # The symlink itself should be gone
    assert not download_symlink.exists()
    # The real target directory and its contents must be untouched
    assert real_target.exists()
    assert (real_target / "important.txt").read_text() == "do not delete"


# ---------------------------------------------------------------------------
# Bug 25: get_cache_size uses rglob which follows symlinks into directories
#          on Python 3.11/3.12, causing incorrect size and infinite recursion
# ---------------------------------------------------------------------------


def test_get_cache_size_does_not_follow_symlinked_dirs_into_external(tmp_path: Path) -> None:
    """Files inside a symlinked-to-directory must not be counted in cache size."""
    import os

    from browserget.cache import get_cache_size

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create an external directory with a large file
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "big.txt").write_bytes(b"X" * 5000)

    # Create a cache dir with a real file and a symlink to the external dir
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "real.txt").write_bytes(b"Y" * 100)
    link_dir = cache / "link_dir"
    os.symlink(external_dir, link_dir, target_is_directory=True)

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=cache)  # type: ignore[method-assign]
    try:
        size = get_cache_size()
    finally:
        cache_mod.load_config = original

    # Only the real file (100 bytes) should be counted, not the 5000 bytes
    # from the external directory accessible via the symlink
    assert size == 100


def test_get_cache_size_counts_nested_directories(tmp_path: Path) -> None:
    """get_cache_size must correctly count files in nested subdirectories."""
    from browserget.cache import get_cache_size

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "top.txt").write_bytes(b"A" * 100)
    sub = cache / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"B" * 200)
    deeper = sub / "deeper"
    deeper.mkdir()
    (deeper / "deep.txt").write_bytes(b"C" * 300)

    from browserget import cache as cache_mod
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=cache)  # type: ignore[method-assign]
    try:
        size = get_cache_size()
    finally:
        cache_mod.load_config = original

    assert size == 600


# ---------------------------------------------------------------------------
# Bug 26: shutil.rmtree on symlinked artifact directories follows the symlink
#          and deletes target contents (Python 3.11) or raises OSError (3.12+)
# ---------------------------------------------------------------------------


def test_safe_rmtree_unlinks_symlinked_dir(tmp_path: Path) -> None:
    """safe_rmtree must unlink a symlinked directory, not delete its target."""
    import os

    from browserget.cache import safe_rmtree

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "important.txt").write_text("do not delete")

    link = tmp_path / "link"
    os.symlink(real_dir, link, target_is_directory=True)

    safe_rmtree(link)

    assert not link.exists()
    assert real_dir.exists()
    assert (real_dir / "important.txt").read_text() == "do not delete"


def test_safe_rmtree_removes_real_dir(tmp_path: Path) -> None:
    """safe_rmtree must remove a real (non-symlink) directory tree."""
    from browserget.cache import safe_rmtree

    target = tmp_path / "target"
    target.mkdir()
    (target / "file.txt").write_text("content")
    sub = target / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested")

    safe_rmtree(target)

    assert not target.exists()


def test_safe_rmtree_handles_missing_path(tmp_path: Path) -> None:
    """safe_rmtree should raise OSError for a non-existent path (delegated to rmtree)."""
    from browserget.cache import safe_rmtree

    missing = tmp_path / "does_not_exist"
    # safe_rmtree delegates to shutil.rmtree which raises on missing paths
    # (unless the caller checks .exists() first, which all callers do)
    with pytest.raises(OSError):
        safe_rmtree(missing)


# ---------------------------------------------------------------------------
# Bug 27: rglob("*") in _find_binary follows symlinks, causing infinite
#          recursion with circular symlinks in extracted archives
# ---------------------------------------------------------------------------


def test_find_file_by_name_finds_in_nested_dir(tmp_path: Path) -> None:
    """find_file_by_name must locate files in nested subdirectories."""
    from browserget.archive import find_file_by_name

    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    target = sub / "chrome"
    target.write_text("binary")

    result = find_file_by_name(tmp_path, "chrome")
    assert result is not None
    assert result == target


def test_find_file_by_name_returns_none_if_not_found(tmp_path: Path) -> None:
    """find_file_by_name must return None when no file matches."""
    from browserget.archive import find_file_by_name

    (tmp_path / "other.txt").write_text("not a match")
    assert find_file_by_name(tmp_path, "chrome") is None


def test_find_file_by_name_does_not_follow_symlinks(tmp_path: Path) -> None:
    """find_file_by_name must not follow symlinked directories."""
    import os

    from browserget.archive import find_file_by_name

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    # Create a circular symlink: dir1/link -> dir1
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "real_chrome").write_text("real")

    link = dir1 / "link"
    os.symlink(dir1, link, target_is_directory=True)

    # Should find real_chrome without infinite recursion
    result = find_file_by_name(tmp_path, "real_chrome")
    assert result is not None
    assert result.name == "real_chrome"


def test_find_file_by_name_ignores_symlinked_files(tmp_path: Path) -> None:
    """find_file_by_name must not return symlinked files."""
    import os

    from browserget.archive import find_file_by_name

    if not _can_symlink(tmp_path):
        pytest.skip("Symlinks not supported on this platform")

    real_file = tmp_path / "real"
    real_file.write_text("real content")

    link = tmp_path / "target_binary"
    os.symlink(real_file, link)

    # Should not return the symlink, only the real file
    result = find_file_by_name(tmp_path, "target_binary")
    assert result is None  # symlink is skipped

    result = find_file_by_name(tmp_path, "real")
    assert result is not None
    assert result == real_file


# ---------------------------------------------------------------------------
# Bug 28: tarfile.extractall() without filter parameter causes
#          DeprecationWarning on Python 3.12+
# ---------------------------------------------------------------------------


def test_extract_tar_no_deprecation_warning(tmp_path: Path) -> None:
    """extract_tar should not trigger DeprecationWarning on Python 3.12+."""
    import io
    import tarfile

    from browserget.archive import extract_tar

    archive = tmp_path / "test.tar"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo(name="hello.txt")
        content = b"hello world"
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))

    dest = tmp_path / "extracted"
    extract_tar(archive, dest)
    assert (dest / "hello.txt").read_text() == "hello world"


# ---------------------------------------------------------------------------
# Bug 29: get_artifact_dir doesn't validate name/version for path traversal
# ---------------------------------------------------------------------------


def test_get_artifact_dir_rejects_dotdot_version(tmp_path: Path) -> None:
    """get_artifact_dir must reject '..' in version parameter."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="Unsafe path component"):
            get_artifact_dir("chrome", "..")
    finally:
        cache_mod.load_config = original


def test_get_artifact_dir_rejects_slash_in_version(tmp_path: Path) -> None:
    """get_artifact_dir must reject '/' in version parameter."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="separator"):
            get_artifact_dir("chrome", "../../etc/passwd")
    finally:
        cache_mod.load_config = original


def test_get_artifact_dir_rejects_backslash_in_version(tmp_path: Path) -> None:
    """get_artifact_dir must reject backslash in version parameter."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="separator"):
            get_artifact_dir("chrome", "..\\..\\Windows")
    finally:
        cache_mod.load_config = original


def test_get_artifact_dir_rejects_empty_version(tmp_path: Path) -> None:
    """get_artifact_dir must reject empty version string."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="Unsafe path component"):
            get_artifact_dir("chrome", "")
    finally:
        cache_mod.load_config = original


def test_get_artifact_dir_rejects_dotdot_name(tmp_path: Path) -> None:
    """get_artifact_dir must reject '..' in name parameter."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="Unsafe path component"):
            get_artifact_dir("..", "131.0")
    finally:
        cache_mod.load_config = original


def test_get_artifact_dir_accepts_valid_components(tmp_path: Path) -> None:
    """get_artifact_dir must accept normal name and version strings."""
    from browserget import cache as cache_mod
    from browserget.cache import get_artifact_dir
    from browserget.config import Config

    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=tmp_path)  # type: ignore[method-assign]
    try:
        result = get_artifact_dir("chrome", "131.0.6778.87")
        assert result == tmp_path / "chrome" / "131.0.6778.87"
    finally:
        cache_mod.load_config = original


# ---------------------------------------------------------------------------
# Bug 30: download_dir / archive_name allows path traversal from malicious URLs
# ---------------------------------------------------------------------------


def test_safe_download_path_rejects_dotdot(tmp_path: Path) -> None:
    """safe_download_path must reject '..' in filename."""
    from browserget.cache import safe_download_path

    with pytest.raises(ValueError, match="Unsafe path component"):
        safe_download_path(tmp_path, "..")


def test_safe_download_path_rejects_slash(tmp_path: Path) -> None:
    """safe_download_path must reject '/' in filename."""
    from browserget.cache import safe_download_path

    with pytest.raises(ValueError, match="separator"):
        safe_download_path(tmp_path, "../../etc/passwd")


def test_safe_download_path_rejects_backslash(tmp_path: Path) -> None:
    """safe_download_path must reject backslash in filename."""
    from browserget.cache import safe_download_path

    with pytest.raises(ValueError, match="separator"):
        safe_download_path(tmp_path, "..\\evil")


def test_safe_download_path_rejects_empty(tmp_path: Path) -> None:
    """safe_download_path must reject empty filename."""
    from browserget.cache import safe_download_path

    with pytest.raises(ValueError, match="Unsafe path component"):
        safe_download_path(tmp_path, "")


def test_safe_download_path_accepts_valid_filename(tmp_path: Path) -> None:
    """safe_download_path must accept a normal filename."""
    from browserget.cache import safe_download_path

    result = safe_download_path(tmp_path, "chrome-linux64.zip")
    assert result == tmp_path / "chrome-linux64.zip"


# ---------------------------------------------------------------------------
# Bug 31: check_disk_space / get_available_disk_mb crash when cache_dir doesn't exist
# ---------------------------------------------------------------------------


def test_check_disk_space_nonexistent_cache_dir(tmp_path: Path) -> None:
    """check_disk_space must not crash when cache_dir does not exist."""
    from browserget import cache as cache_mod
    from browserget.cache import check_disk_space
    from browserget.config import Config

    nonexistent = tmp_path / "does_not_exist"
    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=nonexistent)  # type: ignore[method-assign]
    try:
        result = check_disk_space(100)
        assert isinstance(result, bool)
    finally:
        cache_mod.load_config = original


def test_get_available_disk_mb_nonexistent_cache_dir(tmp_path: Path) -> None:
    """get_available_disk_mb must not crash when cache_dir does not exist."""
    from browserget import cache as cache_mod
    from browserget.cache import get_available_disk_mb
    from browserget.config import Config

    nonexistent = tmp_path / "does_not_exist"
    original = cache_mod.load_config
    cache_mod.load_config = lambda: Config(cache_dir=nonexistent)  # type: ignore[method-assign]
    try:
        result = get_available_disk_mb()
        assert isinstance(result, int)
        assert result >= 0
    finally:
        cache_mod.load_config = original
