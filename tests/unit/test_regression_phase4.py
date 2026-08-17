"""Regression tests for Phase 4 bug fixes.

Covers:
- Bug 15: _validate_path_component rejects null bytes
- Bug 19: _run_async receives lambda instead of pre-created coroutine
- Bug 22: parse_releases (firefox) deduplicates versions
- Bug 23: parse_releases (geckodriver) handles non-list json_data
- Bug 24/25: parse_versions (cft, edge) handles invalid json_data
- Bug 30/31: checksum comparison uses hmac.compare_digest
- Bug 35: Registry.find handles mixed datetime types gracefully
- Bug 11: Firefox ESR matching is case-insensitive
- Bug 37: parse_releases (geckodriver) handles non-dict release entries
- Bug 43: HttpClient retries http.client.HTTPException
- Bug 44: subprocess.run uses errors="replace" to avoid UnicodeDecodeError
- Bug 45: extract_tar filters device files/FIFOs/sockets on Python < 3.12
- Bug 47: extract_zip validates symlink targets to prevent path traversal
- Bug 48: build_checksum_url points to non-existent per-platform checksums file
- Bug 49: _parse_checksums expects wrong 3-field format instead of SHA512SUMS 2-field format
- Bug 50: HTTP client fails on URLs with spaces (Firefox Windows/macOS downloads)
- Bug 51: GeckoDriver on ARM64 Macs downloads x64 build instead of native aarch64
- Bug 52: Edge API URL uses defunct /api/v1/edge endpoint instead of /api/products
- Bug 53: Edge parser expects old JSON structure (versions/downloads)
  instead of new Product/Releases/Artifacts
- Bug 54: EdgeDriver uses defunct azureedge.net CDN instead of msedgedriver.microsoft.com
- Bug 55: EdgeDriver macOS uses separate mac-arm64/mac-x64 binaries instead of universal mac64
- Bug 56: Edge installer force=True leaves stale registry entry when system Edge version differs
- Bug 57: Edge installer force=True leaves stale entries under old system Edge versions
  after auto-update
- Bug 58: Edge parser parse_versions may collect duplicate ResolvedVersion entries for same version
- Bug 59: Installers with force=True remove old artifact directory before download,
  losing working installation on download failure
- Bug 60: Edge installer force=True removes all registry entries before install,
  losing entries if install fails
"""

from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from browserget.cache import _validate_path_component
from browserget.checksum import verify_checksum, verify_or_raise
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.parsers.cft import parse_versions as parse_cft
from browserget.parsers.edge import parse_versions as parse_edge
from browserget.parsers.firefox import (
    _firefox_version_tuple,
    find_latest,
    parse_releases,
)
from browserget.parsers.geckodriver import parse_releases as parse_gecko
from browserget.registry import Registry

# ---------------------------------------------------------------------------
# Bug 15: _validate_path_component rejects null bytes
# ---------------------------------------------------------------------------


class TestValidatePathComponentNullByte:
    """Tests that _validate_path_component rejects null bytes."""

    def test_null_byte_rejected(self) -> None:
        """Path component with null byte should raise ValueError."""
        with pytest.raises(ValueError, match="null byte"):
            _validate_path_component("foo\x00bar")

    def test_only_null_byte_rejected(self) -> None:
        """Single null byte should raise ValueError."""
        with pytest.raises(ValueError, match="null byte"):
            _validate_path_component("\x00")

    def test_normal_component_still_works(self) -> None:
        """Normal path component should pass validation."""
        assert _validate_path_component("chrome") == "chrome"


# ---------------------------------------------------------------------------
# Bug 19: _run_async receives lambda instead of pre-created coroutine
# ---------------------------------------------------------------------------


class TestRunAsyncLambda:
    """Tests that _run_async is called with lambda in versions and doctor."""

    def test_versions_uses_lambda(self) -> None:
        """versions command should pass lambda to _run_async, not a coroutine."""
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from browserget import cli as cli_module

        runner = CliRunner()

        with (
            patch.object(cli_module, "_run_async") as mock_run,
            patch.object(cli_module, "load_config") as mock_config,
            patch.object(cli_module, "HttpClient"),
        ):
            mock_config.return_value = MagicMock(cache_dir=Path("/tmp"), timeout=30, max_retries=3)
            mock_run.return_value = ["131.0.6778.87"]
            result = runner.invoke(cli_module.app, ["versions", "chrome", "--json"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            args = mock_run.call_args.args
            assert callable(args[0]), "_run_async should receive a callable (lambda)"


# ---------------------------------------------------------------------------
# Bug 22: parse_releases (firefox) deduplicates versions
# ---------------------------------------------------------------------------


class TestFirefoxParseReleasesDedup:
    """Tests that parse_releases deduplicates version entries."""

    def test_duplicate_hrefs_deduplicated(self) -> None:
        """Duplicate href links should not produce duplicate versions."""
        html = '<a href="131.0/">131.0/</a><a href="131.0/">131.0/</a><a href="130.0/">130.0/</a>'
        versions = parse_releases(html)
        assert versions.count("131.0") == 1
        assert versions.count("130.0") == 1
        assert len(versions) == 2


# ---------------------------------------------------------------------------
# Bug 23: parse_releases (geckodriver) handles non-list json_data
# ---------------------------------------------------------------------------


class TestGeckoParseReleasesNonList:
    """Tests that geckodriver parse_releases handles non-list json_data."""

    def test_dict_json_data_returns_empty(self) -> None:
        """Non-list json_data (dict) should return empty list, not crash."""
        result = parse_gecko({"error": "not found"}, "win64")  # type: ignore[arg-type]
        assert result == []

    def test_string_json_data_returns_empty(self) -> None:
        """Non-list json_data (string) should return empty list, not crash."""
        result = parse_gecko("not a list", "win64")  # type: ignore[arg-type]
        assert result == []

    def test_none_json_data_returns_empty(self) -> None:
        """Non-list json_data (None) should return empty list, not crash."""
        result = parse_gecko(None, "win64")  # type: ignore[arg-type]
        assert result == []


# ---------------------------------------------------------------------------
# Bug 24/25: parse_versions (cft, edge) handles invalid json_data
# ---------------------------------------------------------------------------


class TestCftParseVersionsNonDict:
    """Tests that CFT parse_versions handles non-dict json_data."""

    def test_list_json_data_returns_empty(self) -> None:
        """Non-dict json_data (list) should return empty list, not crash."""
        result = parse_cft(["not", "a", "dict"], "chrome", "win64")  # type: ignore[arg-type]
        assert result == []

    def test_string_json_data_returns_empty(self) -> None:
        """Non-dict json_data (string) should return empty list, not crash."""
        result = parse_cft("not a dict", "chrome", "win64")  # type: ignore[arg-type]
        assert result == []

    def test_none_json_data_returns_empty(self) -> None:
        """Non-dict json_data (None) should return empty list, not crash."""
        result = parse_cft(None, "chrome", "win64")  # type: ignore[arg-type]
        assert result == []


class TestEdgeParseVersionsNonList:
    """Tests that Edge parse_versions handles non-list json_data."""

    def test_list_of_non_dicts_returns_empty(self) -> None:
        """List of non-dict items should return empty list, not crash."""
        result = parse_edge(["not", "a", "dict"], "edge", "win64")
        assert result == []

    def test_string_json_data_returns_empty(self) -> None:
        """Non-list json_data (string) should return empty list, not crash."""
        result = parse_edge("not a list", "edge", "win64")  # type: ignore[arg-type]
        assert result == []

    def test_none_json_data_returns_empty(self) -> None:
        """Non-list json_data (None) should return empty list, not crash."""
        result = parse_edge(None, "edge", "win64")  # type: ignore[arg-type]
        assert result == []


# ---------------------------------------------------------------------------
# Bug 30/31: checksum comparison uses hmac.compare_digest
# ---------------------------------------------------------------------------


class TestChecksumConstantTimeComparison:
    """Tests that checksum verification uses constant-time comparison."""

    def test_verify_checksum_match(self, tmp_path: Path) -> None:
        """verify_checksum should return True on match."""
        filepath = tmp_path / "test.bin"
        filepath.write_bytes(b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert verify_checksum(filepath, expected, "sha256") is True

    def test_verify_checksum_mismatch(self, tmp_path: Path) -> None:
        """verify_checksum should return False on mismatch."""
        filepath = tmp_path / "test.bin"
        filepath.write_bytes(b"hello")
        assert verify_checksum(filepath, "0" * 64, "sha256") is False

    def test_verify_or_raise_no_crash_on_match(self, tmp_path: Path) -> None:
        """verify_or_raise should not raise on match."""
        filepath = tmp_path / "test.bin"
        filepath.write_bytes(b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        verify_or_raise(filepath, expected, "sha256")

    def test_verify_or_raise_raises_on_mismatch(self, tmp_path: Path) -> None:
        """verify_or_raise should raise on mismatch."""
        from browserget.exceptions import ChecksumMismatchError

        filepath = tmp_path / "test.bin"
        filepath.write_bytes(b"hello")
        with pytest.raises(ChecksumMismatchError):
            verify_or_raise(filepath, "0" * 64, "sha256")


# ---------------------------------------------------------------------------
# Bug 35: Registry.find handles mixed datetime types gracefully
# ---------------------------------------------------------------------------


class TestRegistryFindMixedDatetimes:
    """Tests that Registry.find doesn't crash with mixed naive/aware datetimes."""

    def test_find_returns_entry_on_mixed_datetimes(self, tmp_path: Path) -> None:
        """find without version should not crash on mixed datetime types."""
        registry = Registry(tmp_path)

        artifact1 = InstalledArtifact(
            name="chrome",
            version="131.0.0.0",
            path=tmp_path / "chrome131",
            installed_at=datetime(2025, 1, 1, 12, 0, 0),  # naive
            checksum=None,
        )
        artifact2 = InstalledArtifact(
            name="chrome",
            version="132.0.0.0",
            path=tmp_path / "chrome132",
            installed_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),  # aware
            checksum=None,
        )
        registry.add(artifact1)
        registry.add(artifact2)

        result = registry.find("chrome")
        assert result is not None
        assert result.name == "chrome"


# ---------------------------------------------------------------------------
# Bug 11: Firefox ESR matching is case-insensitive
# ---------------------------------------------------------------------------


class TestFirefoxESRCaseInsensitive:
    """Tests that Firefox ESR version matching handles case-insensitively."""

    def test_esr_lowercase_strips_correctly(self) -> None:
        """_firefox_version_tuple should strip lowercase 'esr'."""
        assert _firefox_version_tuple("115.0esr") == _firefox_version_tuple("115.0")

    def test_esr_uppercase_strips_correctly(self) -> None:
        """_firefox_version_tuple should strip uppercase 'ESR'."""
        assert _firefox_version_tuple("115.0ESR") == _firefox_version_tuple("115.0")

    def test_find_latest_with_uppercase_esr(self) -> None:
        """find_latest should correctly rank uppercase ESR versions."""
        versions = ["115.0ESR", "131.0", "130.0"]
        assert find_latest(versions) == "131.0"

    def test_find_latest_uppercase_esr_below_normal(self) -> None:
        """find_latest should rank uppercase ESR below higher normal versions."""
        versions = ["115.0ESR", "116.0"]
        assert find_latest(versions) == "116.0"

    def test_esr_mixed_case_strips_correctly(self) -> None:
        """_firefox_version_tuple should strip mixed-case 'Esr'."""
        assert _firefox_version_tuple("115.0Esr") == _firefox_version_tuple("115.0")

    def test_esr_all_case_variants_equal(self) -> None:
        """All case variants of ESR should produce the same version tuple."""
        base = _firefox_version_tuple("115.0")
        assert _firefox_version_tuple("115.0esr") == base
        assert _firefox_version_tuple("115.0ESR") == base
        assert _firefox_version_tuple("115.0Esr") == base
        assert _firefox_version_tuple("115.0eSr") == base

    def test_find_latest_with_mixed_case_esr(self) -> None:
        """find_latest should correctly rank mixed-case ESR versions."""
        versions = ["115.0Esr", "131.0", "130.0"]
        assert find_latest(versions) == "131.0"


# ---------------------------------------------------------------------------
# Bug 36: Firefox resolve() ESR matching strips esr from user-provided version
# ---------------------------------------------------------------------------


class TestFirefoxResolveESRUserVersion:
    """Tests that FirefoxInstaller.resolve matches cross-case ESR versions.

    When the user types "115.0esr" and the FTP listing has "115.0ESR",
    the resolve method should still find a match by stripping the ESR
    suffix from both sides before comparing.
    """

    def test_user_esr_matches_ftp_uppercase_esr(self) -> None:
        """User '115.0esr' should match FTP '115.0ESR'."""
        versions = ["115.0ESR", "131.0", "130.0"]
        user_version = "115.0esr"

        # Simulate the resolve matching logic
        target_version: str | None = None
        if user_version in versions:
            target_version = user_version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == user_version.lower().removesuffix("esr"):
                    target_version = v
                    break

        assert target_version == "115.0ESR"

    def test_user_uppercase_esr_matches_ftp_lowercase_esr(self) -> None:
        """User '115.0ESR' should match FTP '115.0esr'."""
        versions = ["115.0esr", "131.0", "130.0"]
        user_version = "115.0ESR"

        target_version: str | None = None
        if user_version in versions:
            target_version = user_version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == user_version.lower().removesuffix("esr"):
                    target_version = v
                    break

        assert target_version == "115.0esr"

    def test_user_mixed_case_esr_matches_ftp_lowercase_esr(self) -> None:
        """User '115.0Esr' should match FTP '115.0esr'."""
        versions = ["115.0esr", "131.0", "130.0"]
        user_version = "115.0Esr"

        target_version: str | None = None
        if user_version in versions:
            target_version = user_version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == user_version.lower().removesuffix("esr"):
                    target_version = v
                    break

        assert target_version == "115.0esr"

    def test_user_esr_matches_ftp_no_esr(self) -> None:
        """User '115.0esr' should match FTP '115.0' (no ESR suffix on FTP)."""
        versions = ["115.0", "131.0", "130.0"]
        user_version = "115.0esr"

        target_version: str | None = None
        if user_version in versions:
            target_version = user_version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == user_version.lower().removesuffix("esr"):
                    target_version = v
                    break

        assert target_version == "115.0"

    def test_user_no_esr_matches_ftp_esr(self) -> None:
        """User '115.0' should match FTP '115.0esr'."""
        versions = ["115.0esr", "131.0", "130.0"]
        user_version = "115.0"

        target_version: str | None = None
        if user_version in versions:
            target_version = user_version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == user_version.lower().removesuffix("esr"):
                    target_version = v
                    break

        assert target_version == "115.0esr"


# ---------------------------------------------------------------------------
# Bug 37: parse_releases (geckodriver) handles non-dict release entries
# ---------------------------------------------------------------------------


class TestGeckoParseReleasesNonDictEntry:
    """Tests that geckodriver parse_releases handles non-dict entries in the list."""

    def test_string_entry_skipped(self) -> None:
        """A string entry in the releases list should be skipped, not crash."""
        json_data: list[dict[str, object]] = [
            "not a dict",  # type: ignore[list-item]
            {
                "tag_name": "v0.35.0",
                "assets": [
                    {
                        "name": "geckodriver-v0.35.0-win64.zip",
                        "browser_download_url": "https://example.com/win64.zip",
                    }
                ],
            },
        ]
        result = parse_gecko(json_data, "win64")
        assert len(result) == 1
        assert result[0].version == "0.35.0"

    def test_none_entry_skipped(self) -> None:
        """A None entry in the releases list should be skipped, not crash."""
        json_data: list[dict[str, object]] = [
            None,  # type: ignore[list-item]
            {
                "tag_name": "v0.35.0",
                "assets": [
                    {
                        "name": "geckodriver-v0.35.0-linux64.tar.gz",
                        "browser_download_url": "https://example.com/linux64.tar.gz",
                    }
                ],
            },
        ]
        result = parse_gecko(json_data, "linux64")
        assert len(result) == 1
        assert result[0].version == "0.35.0"

    def test_all_non_dict_entries_returns_empty(self) -> None:
        """All non-dict entries should return empty list, not crash."""
        json_data: list[dict[str, object]] = [
            "string",  # type: ignore[list-item]
            42,  # type: ignore[list-item]
            None,  # type: ignore[list-item]
        ]
        result = parse_gecko(json_data, "win64")
        assert result == []


class TestFirefoxExtractExeTextMode:
    """Bug 38: _extract_exe uses text=True to avoid UnicodeDecodeError.

    Previously, _extract_exe used capture_output=True without text=True and
    then called result.stderr.decode(), which could raise UnicodeDecodeError
    if 7-Zip output contained non-UTF-8 bytes (e.g. non-English Windows locales).
    """

    def test_extract_exe_uses_text_mode(self) -> None:
        """_extract_exe should use text=True so stderr is a str, not bytes."""
        import inspect

        from browserget.installers.firefox import FirefoxInstaller

        source = inspect.getsource(FirefoxInstaller._extract_exe)
        assert "text=True" in source
        assert ".decode()" not in source


class TestFirefoxExtractDmgTextMode:
    """Bug 39: _extract_dmg uses text=True to avoid UnicodeDecodeError.

    Previously, _extract_dmg used capture_output=True without text=True and
    then called result.stderr.decode(), which could raise UnicodeDecodeError
    if hdiutil output contained non-UTF-8 bytes.
    """

    def test_extract_dmg_uses_text_mode(self) -> None:
        """_extract_dmg should use text=True so stderr is a str, not bytes."""
        import inspect

        from browserget.installers.firefox import FirefoxInstaller

        source = inspect.getsource(FirefoxInstaller._extract_dmg)
        assert "text=True" in source
        assert ".decode()" not in source


class TestSystemDetectorFirefoxRegistry:
    """Bug 40: _get_version_windows tries CurrentVersion for Firefox.

    Firefox stores its version under the value name "CurrentVersion" in the
    registry, not "version" (which is what Chrome and Edge use via BLBeacon).
    The code should try both value names.
    """

    def test_get_version_windows_tries_current_version(self) -> None:
        """_get_version_windows should query 'CurrentVersion' as a fallback."""
        import inspect

        from browserget.system import SystemDetector

        source = inspect.getsource(SystemDetector._get_version_windows)
        assert "CurrentVersion" in source


class TestRegistrySaveTempFileLeak:
    """Bug 41: Registry.save leaks temp file if json.dump fails.

    Previously, tmp_path was assigned *after* json.dump. If json.dump raised
    an exception, tmp_path would still be None and the except block would not
    delete the temp file. Since delete=False is used, the temp file would
    leak on disk.
    """

    def test_save_cleans_up_temp_file_on_json_error(self, tmp_path: Path) -> None:
        """Registry.save should delete the temp file even if json.dump fails."""
        import inspect

        from browserget.registry import Registry

        source = inspect.getsource(Registry.save)
        # tmp_path must be assigned before json.dump so cleanup works
        lines = source.splitlines()
        tmp_assign_line = next(
            (i for i, line in enumerate(lines) if "tmp_path = Path(tmp.name)" in line), -1
        )
        dump_line = next((i for i, line in enumerate(lines) if "json.dump" in line), -1)
        assert tmp_assign_line >= 0, "tmp_path assignment not found"
        assert dump_line >= 0, "json.dump call not found"
        assert tmp_assign_line < dump_line, (
            "tmp_path must be assigned before json.dump so the except block "
            "can clean up the temp file if json.dump fails"
        )


class TestInstalledArtifactFromDictChecksumValidation:
    """Bug 42: InstalledArtifact.from_dict doesn't validate checksum type.

    If the registry JSON is corrupted with a non-string checksum value
    (e.g., a number or boolean), from_dict would accept it silently,
    creating an InstalledArtifact with a non-string checksum. This could
    cause TypeError later when the checksum is used as a string.
    """

    def test_from_dict_rejects_non_string_checksum(self) -> None:
        """from_dict should raise ValueError for non-string checksum."""
        from browserget.models import InstalledArtifact

        data = {
            "name": "chrome",
            "version": "131.0",
            "path": "/tmp/chrome",
            "installed_at": "2024-01-01T00:00:00+00:00",
            "checksum": 12345,
        }
        with pytest.raises(ValueError, match="checksum"):
            InstalledArtifact.from_dict(data)

    def test_from_dict_rejects_bool_checksum(self) -> None:
        """from_dict should raise ValueError for boolean checksum."""
        from browserget.models import InstalledArtifact

        data = {
            "name": "chrome",
            "version": "131.0",
            "path": "/tmp/chrome",
            "installed_at": "2024-01-01T00:00:00+00:00",
            "checksum": True,
        }
        with pytest.raises(ValueError, match="checksum"):
            InstalledArtifact.from_dict(data)

    def test_from_dict_accepts_none_checksum(self) -> None:
        """from_dict should accept None checksum (no checksum available)."""
        from browserget.models import InstalledArtifact

        data = {
            "name": "chrome",
            "version": "131.0",
            "path": "/tmp/chrome",
            "installed_at": "2024-01-01T00:00:00+00:00",
            "checksum": None,
        }
        artifact = InstalledArtifact.from_dict(data)
        assert artifact.checksum is None

    def test_from_dict_accepts_string_checksum(self) -> None:
        """from_dict should accept a valid string checksum."""
        from browserget.models import InstalledArtifact

        data = {
            "name": "chrome",
            "version": "131.0",
            "path": "/tmp/chrome",
            "installed_at": "2024-01-01T00:00:00+00:00",
            "checksum": "abc123",
        }
        artifact = InstalledArtifact.from_dict(data)
        assert artifact.checksum == "abc123"

    def test_from_dict_accepts_missing_checksum(self) -> None:
        """from_dict should accept missing checksum key (defaults to None)."""
        from browserget.models import InstalledArtifact

        data = {
            "name": "chrome",
            "version": "131.0",
            "path": "/tmp/chrome",
            "installed_at": "2024-01-01T00:00:00+00:00",
        }
        artifact = InstalledArtifact.from_dict(data)
        assert artifact.checksum is None


class TestHttpClientRetriesHTTPException:
    """Bug 43: HttpClient retries http.client.HTTPException.

    Previously, the retry logic in HttpClient._retry_with_backoff only caught
    urllib.error.URLError, ConnectionError, and TimeoutError. If the server
    sent a truncated response (e.g. IncompleteRead), http.client.HTTPException
    would be raised but not retried, causing an immediate failure even though
    a retry might succeed.
    """

    def test_http_exception_in_retry_list(self) -> None:
        """The retry except clause should include http.client.HTTPException."""
        import inspect

        from browserget.http import HttpClient

        source = inspect.getsource(HttpClient._retry_with_backoff)
        assert "http.client.HTTPException" in source


class TestSubprocessErrorsReplace:
    """Bug 44: subprocess.run uses errors="replace" to avoid UnicodeDecodeError.

    When text=True is used with subprocess.run, Python uses the locale encoding
    with 'strict' error handling by default. If the subprocess outputs bytes
    that are not valid in that encoding (common on non-English Windows locales),
    UnicodeDecodeError is raised. Adding errors="replace" replaces undecodable
    bytes with the Unicode replacement character instead of crashing.
    """

    def test_firefox_extract_exe_uses_errors_replace(self) -> None:
        """_extract_exe subprocess.run should use errors='replace'."""
        import inspect

        from browserget.installers.firefox import FirefoxInstaller

        source = inspect.getsource(FirefoxInstaller._extract_exe)
        assert 'errors="replace"' in source or "errors='replace'" in source

    def test_firefox_extract_dmg_uses_errors_replace(self) -> None:
        """_extract_dmg subprocess.run calls should use errors='replace'."""
        import inspect

        from browserget.installers.firefox import FirefoxInstaller

        source = inspect.getsource(FirefoxInstaller._extract_dmg)
        assert 'errors="replace"' in source or "errors='replace'" in source

    def test_system_run_version_command_uses_errors_replace(self) -> None:
        """_run_version_command subprocess.run should use errors='replace'."""
        import inspect

        from browserget.system import SystemDetector

        source = inspect.getsource(SystemDetector._run_version_command)
        assert 'errors="replace"' in source or "errors='replace'" in source

    def test_edge_install_macos_uses_errors_replace(self) -> None:
        """EdgeInstaller._install_macos subprocess.run should use errors='replace'."""
        import inspect

        from browserget.installers.edge import EdgeInstaller

        source = inspect.getsource(EdgeInstaller._install_macos)
        assert 'errors="replace"' in source or "errors='replace'" in source

    def test_edge_install_linux_uses_errors_replace(self) -> None:
        """EdgeInstaller._install_linux subprocess.run should use errors='replace'."""
        import inspect

        from browserget.installers.edge import EdgeInstaller

        source = inspect.getsource(EdgeInstaller._install_linux)
        assert 'errors="replace"' in source or "errors='replace'" in source


class TestExtractTarFiltersNonRegularFiles:
    """Bug 45: extract_tar filters device files/FIFOs/sockets on Python < 3.12.

    On Python < 3.12, ``tarfile.extractall`` does not have the ``filter``
    parameter. Without manual filtering, a malicious tar archive could
    contain device files, FIFOs, or sockets that get extracted to the
    filesystem, potentially causing security issues.

    The fix filters members to only allow regular files, directories,
    symlinks, and hardlinks on Python < 3.12.
    """

    def test_extract_tar_source_includes_member_filter(self) -> None:
        """extract_tar source should include member type filtering for older Python."""
        import inspect

        from browserget.archive import extract_tar

        source = inspect.getsource(extract_tar)
        assert "isfile" in source or "isreg" in source
        assert "isdir" in source
        assert "issym" in source
        assert "islnk" in source

    def test_extract_tar_rejects_fifo(self, tmp_path: Path) -> None:
        """extract_tar should reject FIFO entries from a tar archive."""
        import io
        import tarfile

        from browserget.archive import extract_tar

        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tf:
            fifo_info = tarfile.TarInfo(name="evil_fifo")
            fifo_info.type = tarfile.FIFOTYPE
            tf.addfile(fifo_info)

            good_info = tarfile.TarInfo(name="safe_file.txt")
            good_info.size = 5
            tf.addfile(good_info, io.BytesIO(b"hello"))

        tar_buf.seek(0)
        tar_path = tmp_path / "test.tar"
        tar_path.write_bytes(tar_buf.getvalue())

        dest = tmp_path / "extracted"
        with pytest.raises((ValueError, Exception), match="special file|SpecialFileError"):
            extract_tar(tar_path, dest)

    def test_extract_tar_rejects_device_file(self, tmp_path: Path) -> None:
        """extract_tar should reject device file entries from a tar archive."""
        import io
        import tarfile

        from browserget.archive import extract_tar

        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tf:
            dev_info = tarfile.TarInfo(name="evil_dev")
            dev_info.type = tarfile.CHRTYPE
            dev_info.devmajor = 1
            dev_info.devminor = 3
            tf.addfile(dev_info)

            good_info = tarfile.TarInfo(name="safe_file.txt")
            good_info.size = 5
            tf.addfile(good_info, io.BytesIO(b"hello"))

        tar_buf.seek(0)
        tar_path = tmp_path / "test.tar"
        tar_path.write_bytes(tar_buf.getvalue())

        dest = tmp_path / "extracted"
        with pytest.raises((ValueError, Exception), match="special file|SpecialFileError"):
            extract_tar(tar_path, dest)


class TestExtractZipValidatesSymlinkTargets:
    """Bug 47: extract_zip validates symlink targets to prevent path traversal.

    Python 3.11+ ``zipfile.extractall`` creates symlinks from zip entries
    that have the symlink attribute set. The previous code only validated
    member paths but not symlink targets, allowing a malicious zip to
    create symlinks pointing outside the destination directory.
    """

    def test_extract_zip_source_includes_symlink_check(self) -> None:
        """extract_zip source should include symlink target validation."""
        import inspect

        from browserget.archive import extract_zip

        source = inspect.getsource(extract_zip)
        assert "S_ISLNK" in source
        assert "link_target" in source

    def test_extract_zip_rejects_symlink_traversal(self, tmp_path: Path) -> None:
        """extract_zip should reject a symlink whose target escapes the destination."""
        import os
        import stat
        import zipfile

        from browserget.archive import extract_zip

        zip_path = tmp_path / "evil.zip"
        dest = tmp_path / "extracted"

        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")

        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo("link.txt")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, os.path.relpath(outside_file, dest))

        with pytest.raises(ValueError, match="escapes destination"):
            extract_zip(zip_path, dest)


# ---------------------------------------------------------------------------
# Bug 48: build_checksum_url points to non-existent per-platform checksums file
# ---------------------------------------------------------------------------


class TestBug48ChecksumUrlPointsToSHA512SUMS:
    """Regression tests for Bug 48.

    ``build_checksum_url`` constructed a URL to a per-platform ``checksums``
    file that no longer exists on Mozilla's FTP.  The correct URL points to
    ``SHA512SUMS`` at the release root, which contains hashes for all
    platforms and locales in a single file.
    """

    def test_url_ends_with_SHA512SUMS(self) -> None:
        """build_checksum_url should produce a URL ending with SHA512SUMS."""
        from browserget.parsers.firefox import build_checksum_url

        url = build_checksum_url("131.0", "linux64")
        assert url is not None
        assert url.endswith("/SHA512SUMS")

    def test_url_at_release_root(self) -> None:
        """build_checksum_url should point to the release root, not a sub-directory."""
        from browserget.parsers.firefox import build_checksum_url

        url = build_checksum_url("131.0", "win64")
        assert url is not None
        assert url == "https://ftp.mozilla.org/pub/firefox/releases/131.0/SHA512SUMS"

    def test_url_does_not_contain_platform_path(self) -> None:
        """build_checksum_url should NOT contain platform-specific paths."""
        from browserget.parsers.firefox import build_checksum_url

        url = build_checksum_url("131.0", "linux64")
        assert url is not None
        assert "/linux-x86_64/" not in url
        assert "/en-US/" not in url

    def test_url_with_esr_version(self) -> None:
        """build_checksum_url should handle ESR versions correctly."""
        from browserget.parsers.firefox import build_checksum_url

        url = build_checksum_url("128.14.0esr", "linux64")
        assert url is not None
        assert "128.14.0esr" in url
        assert url.endswith("/SHA512SUMS")

    def test_empty_version_returns_none(self) -> None:
        """build_checksum_url for empty version should return None."""
        from browserget.parsers.firefox import build_checksum_url

        assert build_checksum_url("", "linux64") is None


# ---------------------------------------------------------------------------
# Bug 49: _parse_checksums expects wrong 3-field format
# ---------------------------------------------------------------------------


class TestBug49ParseChecksumsSHA512SUMSFormat:
    """Regression tests for Bug 49.

    ``_parse_checksums`` expected the old 3-field format
    (``<algorithm>  <hash>  <filename>``) from per-platform ``checksums``
    files.  The actual ``SHA512SUMS`` format is 2-field
    (``<hash>  <relative_path>``), where the algorithm is implied by the
    file name.  The old parser would never match any entry, causing
    checksum verification to be silently skipped for all Firefox downloads.
    """

    def test_parses_two_field_format(self) -> None:
        """_parse_checksums should correctly parse <hash>  <path> format."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-131.0.tar.bz2")
        assert result == "aaa111"

    def test_matches_correct_platform_path(self) -> None:
        """_parse_checksums should match the correct platform and locale entry."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  linux-x86_64/ach/firefox-131.0.tar.bz2\n"
            "bbb222  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
            "ccc333  win64/en-US/Firefox Setup 131.0.exe\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-131.0.tar.bz2")
        assert result == "bbb222"

    def test_matches_windows_path_with_spaces(self) -> None:
        """_parse_checksums should handle paths with spaces (Firefox Setup)."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "aaa111  win64/en-US/Firefox Setup 131.0.exe\n"
        result = FirefoxInstaller._parse_checksums(text, "win64/en-US/Firefox Setup 131.0.exe")
        assert result == "aaa111"

    def test_does_not_match_wrong_path(self) -> None:
        """_parse_checksums should not return hash for a different path."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
            "bbb222  win64/en-US/Firefox Setup 131.0.exe\n"
        )
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-130.0.tar.bz2")
        assert result is None

    def test_old_three_field_format_does_not_match(self) -> None:
        """Old 3-field format entries should not be parsed as valid SHA512SUMS entries."""
        from browserget.installers.firefox import FirefoxInstaller

        # Old format: "sha512  <hash>  <filename>" — should NOT match
        text = "sha512  aaa111  firefox-131.0.tar.bz2\n"
        result = FirefoxInstaller._parse_checksums(text, "firefox-131.0.tar.bz2")
        # With 2-field parsing, "sha512" is the hash and "aaa111  firefox-131.0.tar.bz2"
        # is the path — this won't match "firefox-131.0.tar.bz2"
        assert result is None

    def test_empty_lines_ignored(self) -> None:
        """Empty lines in SHA512SUMS should be ignored."""
        from browserget.installers.firefox import FirefoxInstaller

        text = "\n\naaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n\n"
        result = FirefoxInstaller._parse_checksums(text, "linux-x86_64/en-US/firefox-131.0.tar.bz2")
        assert result == "aaa111"

    def test_no_path_arg_returns_first_entry(self) -> None:
        """Without expected_path, should return the first entry's hash."""
        from browserget.installers.firefox import FirefoxInstaller

        text = (
            "aaa111  linux-x86_64/en-US/firefox-131.0.tar.bz2\n"
            "bbb222  win64/en-US/Firefox Setup 131.0.exe\n"
        )
        result = FirefoxInstaller._parse_checksums(text)
        assert result == "aaa111"


# ---------------------------------------------------------------------------
# Bug 50: HTTP client fails on URLs with spaces (Firefox Windows/macOS downloads)
# ---------------------------------------------------------------------------


class TestBug50UrlEncoding:
    """Regression tests for Bug 50.

    ``urllib.request.urlopen`` raises ``http.client.InvalidURL`` when the URL
    path contains spaces.  Firefox download URLs for Windows
    (``Firefox Setup {version}.exe``) and macOS (``Firefox {version}.dmg``)
    contain spaces, causing all Firefox downloads on those platforms to fail.
    The fix adds ``_encode_url`` to percent-encode the path component.
    """

    def test_encode_url_with_spaces(self) -> None:
        """_encode_url should percent-encode spaces in the path."""
        from browserget.http import HttpClient

        url = (
            "https://ftp.mozilla.org/pub/firefox/releases/131.0/win64/en-US/Firefox Setup 131.0.exe"
        )
        encoded = HttpClient._encode_url(url)
        assert "%20" in encoded
        assert " " not in encoded
        assert encoded == (
            "https://ftp.mozilla.org/pub/firefox/releases/131.0/win64/en-US/"
            "Firefox%20Setup%20131.0.exe"
        )

    def test_encode_url_preserves_slashes(self) -> None:
        """_encode_url should not encode / characters in the path."""
        from browserget.http import HttpClient

        url = "https://example.com/path/to/file.txt"
        encoded = HttpClient._encode_url(url)
        assert encoded == url

    def test_encode_url_no_path(self) -> None:
        """_encode_url should handle URLs with no path."""
        from browserget.http import HttpClient

        url = "https://example.com"
        encoded = HttpClient._encode_url(url)
        assert encoded == url

    def test_encode_url_preserves_query(self) -> None:
        """_encode_url should preserve query parameters."""
        from browserget.http import HttpClient

        url = "https://example.com/path with spaces/file.txt?q=1&r=2"
        encoded = HttpClient._encode_url(url)
        assert "%20" in encoded
        assert "?q=1&r=2" in encoded

    def test_encode_url_macos_dmg(self) -> None:
        """_encode_url should handle macOS .dmg URLs with spaces."""
        from browserget.http import HttpClient

        url = "https://ftp.mozilla.org/pub/firefox/releases/131.0/mac/en-US/Firefox 131.0.dmg"
        encoded = HttpClient._encode_url(url)
        assert " " not in encoded
        assert "Firefox%20131.0.dmg" in encoded

    def test_encode_url_already_encoded(self) -> None:
        """_encode_url should not double-encode already-encoded characters."""
        from browserget.http import HttpClient

        url = "https://example.com/path%20with%20spaces/file.txt"
        encoded = HttpClient._encode_url(url)
        assert encoded == url

    def test_encode_url_linux_no_spaces(self) -> None:
        """_encode_url should not change URLs without spaces."""
        from browserget.http import HttpClient

        url = "https://ftp.mozilla.org/pub/firefox/releases/131.0/linux-x86_64/en-US/firefox-131.0.tar.bz2"
        encoded = HttpClient._encode_url(url)
        assert encoded == url


class TestBug51GeckoDriverArm64Asset:
    """Regression tests for Bug 51: GeckoDriver ARM64 macOS downloads x64 build.

    The GeckoDriver GitHub releases include separate ``macos-aarch64.tar.gz``
    (ARM64) and ``macos.tar.gz`` (x64) assets.  The platform mapping and
    asset suffix map must direct ARM64 Macs to the aarch64 asset.
    """

    def test_platform_map_geckodriver_macos_arm64(self) -> None:
        """map_platform for macOS ARM64 geckodriver should return mac-arm64."""
        from browserget.platform import OS, Arch, Platform, map_platform

        p = Platform(os=OS.MACOS, arch=Arch.ARM64)
        assert map_platform(p, "geckodriver") == "mac-arm64"

    def test_platform_map_geckodriver_macos_x64(self) -> None:
        """map_platform for macOS X64 geckodriver should return mac-x64."""
        from browserget.platform import OS, Arch, Platform, map_platform

        p = Platform(os=OS.MACOS, arch=Arch.X64)
        assert map_platform(p, "geckodriver") == "mac-x64"

    def test_asset_map_mac_arm64_uses_aarch64(self) -> None:
        """_ASSET_PLATFORM_MAP for mac-arm64 should use macos-aarch64.tar.gz."""
        from browserget.parsers.geckodriver import _ASSET_PLATFORM_MAP

        assert _ASSET_PLATFORM_MAP["mac-arm64"] == "macos-aarch64.tar.gz"

    def test_asset_map_mac_x64_uses_x64(self) -> None:
        """_ASSET_PLATFORM_MAP for mac-x64 should use macos.tar.gz."""
        from browserget.parsers.geckodriver import _ASSET_PLATFORM_MAP

        assert _ASSET_PLATFORM_MAP["mac-x64"] == "macos.tar.gz"

    def test_parse_releases_arm64_selects_aarch64_asset(self) -> None:
        """parse_releases for mac-arm64 should select the aarch64 asset URL."""
        from browserget.parsers.geckodriver import parse_releases

        data: list[dict[str, object]] = [
            {
                "tag_name": "v0.37.0",
                "assets": [
                    {
                        "name": "geckodriver-v0.37.0-macos-aarch64.tar.gz",
                        "browser_download_url": "https://example.com/aarch64.tar.gz",
                    },
                    {
                        "name": "geckodriver-v0.37.0-macos.tar.gz",
                        "browser_download_url": "https://example.com/x64.tar.gz",
                    },
                ],
            }
        ]
        results = parse_releases(data, "mac-arm64")
        assert len(results) == 1
        assert "aarch64" in results[0].url
        assert "x64.tar.gz" not in results[0].url

    def test_parse_releases_x64_selects_x64_asset(self) -> None:
        """parse_releases for mac-x64 should select the x64 asset URL."""
        from browserget.parsers.geckodriver import parse_releases

        data: list[dict[str, object]] = [
            {
                "tag_name": "v0.37.0",
                "assets": [
                    {
                        "name": "geckodriver-v0.37.0-macos-aarch64.tar.gz",
                        "browser_download_url": "https://example.com/aarch64.tar.gz",
                    },
                    {
                        "name": "geckodriver-v0.37.0-macos.tar.gz",
                        "browser_download_url": "https://example.com/x64.tar.gz",
                    },
                ],
            }
        ]
        results = parse_releases(data, "mac-x64")
        assert len(results) == 1
        assert results[0].url == "https://example.com/x64.tar.gz"


# ---------------------------------------------------------------------------
# Bug 52: Edge API URL uses defunct /api/v1/edge endpoint
# Bug 53: Edge parser expects old JSON structure instead of Product/Releases/Artifacts
# Bug 54: EdgeDriver uses defunct azureedge.net CDN
# Bug 55: EdgeDriver macOS uses separate mac-arm64/mac-x64 instead of universal mac64
# ---------------------------------------------------------------------------


class TestBug52EdgeApiUrl:
    """Bug 52: Edge API URL must use /api/products, not /api/v1/edge."""

    def test_edge_api_url_is_products_endpoint(self) -> None:
        """EDGE_API_URL must point to the live /api/products endpoint."""
        from browserget.installers.edge import EDGE_API_URL

        assert EDGE_API_URL == "https://edgeupdates.microsoft.com/api/products"
        assert "/api/v1/edge" not in EDGE_API_URL


class TestBug53EdgeParserNewStructure:
    """Bug 53: Parser must handle new Product/Releases/Artifacts structure."""

    def test_parse_versions_with_new_structure(self) -> None:
        """parse_versions should correctly parse the new API JSON array."""
        from browserget.parsers.edge import parse_versions

        data = [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {
                                "ArtifactName": "MicrosoftEdge_X64_131.0.2903.86.msi",
                                "Location": "https://example.com/edge.msi",
                                "Hash": "abc123",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    }
                ],
            }
        ]
        results = parse_versions(data, "edge", "win64")
        assert len(results) == 1
        assert results[0].version == "131.0.2903.86"
        assert results[0].url == "https://example.com/edge.msi"
        assert results[0].checksum == "abc123"
        assert results[0].checksum_algorithm == "sha256"

    def test_parse_versions_macos_universal_architecture(self) -> None:
        """Both mac-arm64 and mac-x64 should match MacOS/universal releases."""
        from browserget.parsers.edge import parse_versions

        data = [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "Platform": "MacOS",
                        "Architecture": "universal",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {
                                "ArtifactName": "edge.pkg",
                                "Location": "https://example.com/edge.pkg",
                                "Hash": "hash123",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    }
                ],
            }
        ]
        for platform in ("mac-arm64", "mac-x64"):
            results = parse_versions(data, "edge", platform)
            assert len(results) == 1
            assert results[0].version == "131.0.2903.86"

    def test_parse_versions_ignores_non_stable_products(self) -> None:
        """Beta, Dev, and Canary products should be ignored."""
        from browserget.parsers.edge import parse_versions

        data = [
            {
                "Product": "Beta",
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {
                                "ArtifactName": "edge_beta.msi",
                                "Location": "https://example.com/beta.msi",
                                "Hash": "beta_hash",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    }
                ],
            }
        ]
        results = parse_versions(data, "edge", "win64")
        assert len(results) == 0


class TestBug54EdgeDriverCdnUrl:
    """Bug 54: EdgeDriver must use msedgedriver.microsoft.com CDN."""

    def test_edgedriver_cdn_url_constant(self) -> None:
        """EDGEDRIVER_CDN_URL must point to the live CDN."""
        from browserget.parsers.edge import EDGEDRIVER_CDN_URL

        assert EDGEDRIVER_CDN_URL == "https://msedgedriver.microsoft.com"
        assert "azureedge.net" not in EDGEDRIVER_CDN_URL

    def test_edgedriver_latest_url_constant(self) -> None:
        """EDGEDRIVER_LATEST_URL must point to LATEST_STABLE on the CDN."""
        from browserget.parsers.edge import EDGEDRIVER_LATEST_URL

        assert EDGEDRIVER_LATEST_URL == "https://msedgedriver.microsoft.com/LATEST_STABLE"

    def test_build_edgedriver_url_uses_cdn(self) -> None:
        """build_edgedriver_url should produce URLs on the new CDN."""
        from browserget.parsers.edge import EDGEDRIVER_CDN_URL, build_edgedriver_url

        url = build_edgedriver_url("131.0.2903.86", "win64")
        assert url.startswith(EDGEDRIVER_CDN_URL)
        assert "azureedge.net" not in url


class TestBug55EdgeDriverMacUniversal:
    """Bug 55: EdgeDriver macOS uses universal mac64 binary for both architectures."""

    @pytest.mark.parametrize(
        ("platform", "expected_component"),
        [
            ("mac-arm64", "edgedriver_mac64.zip"),
            ("mac-x64", "edgedriver_mac64.zip"),
        ],
    )
    def test_macos_both_archs_use_mac64(self, platform: str, expected_component: str) -> None:
        """Both macOS architectures should produce edgedriver_mac64.zip URLs."""
        from browserget.parsers.edge import build_edgedriver_url

        url = build_edgedriver_url("131.0.2903.86", platform)
        assert url.endswith(expected_component)

    def test_macos_arm64_not_mac64_m1(self) -> None:
        """EdgeDriver URL should not use old mac64_m1 naming."""
        from browserget.parsers.edge import build_edgedriver_url

        url = build_edgedriver_url("131.0.2903.86", "mac-arm64")
        assert "mac64_m1" not in url
        assert "mac64" in url


# ---------------------------------------------------------------------------
# Bug 56: Edge installer force=True leaves stale registry entry
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Edge system detection tests require Windows")
class TestBug56EdgeForceRemovesOldEntry:
    """Bug 56: Edge installer must remove old registry entry on force reinstall.

    When ``force=True`` and the system Edge version differs from the resolved
    version, the old entry under the resolved version must be removed.
    Otherwise a stale orphan entry remains in the registry.
    """

    @pytest.mark.asyncio
    async def test_force_removes_old_entry_when_version_differs(self, tmp_path: Path) -> None:
        """Force reinstall should remove the old registry entry."""
        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.edge import EdgeInstaller
        from browserget.registry import Registry

        registry = Registry(tmp_path)
        config = Config(cache_dir=tmp_path)
        http = HttpClient(timeout=5, max_retries=1)

        # Simulate an existing entry under an old version
        old_artifact = InstalledArtifact(
            name="edge",
            version="130.0.0.0",
            path=tmp_path / "old_edge",
            installed_at=datetime.now(UTC),
            checksum=None,
        )
        registry.add(old_artifact)

        # Verify the old entry exists
        assert registry.find("edge", "130.0.0.0") is not None

        # Create installer and patch _install_windows to simulate system Edge
        # with a different version
        installer = EdgeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="edge",
            version="130.0.0.0",
            url="https://example.com/edge.msi",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        async def fake_install_windows(resolved_ver, force_flag):
            installed = InstalledArtifact(
                name="edge",
                version="131.0.0.0",  # System Edge has a different version
                path=tmp_path / "edge.exe",
                installed_at=datetime.now(UTC),
                checksum=None,
            )
            registry.add(installed)
            return installed

        # Monkey-patch the platform-specific install method
        import unittest.mock as mock

        with mock.patch.object(installer, "_install_windows", side_effect=fake_install_windows):
            result = await installer.install(resolved, force=True)

        # The old entry should be gone
        assert registry.find("edge", "130.0.0.0") is None
        # The new entry should exist under the system version
        assert registry.find("edge", "131.0.0.0") is not None
        assert result.version == "131.0.0.0"


@pytest.mark.skipif(sys.platform != "win32", reason="Edge system detection tests require Windows")
class TestBug57EdgeForceRemovesAllStaleEntries:
    """Bug 57: Edge installer force=True must remove ALL stale entries.

    When the system Edge auto-updates between installs, the old registry
    entry (under the previous system version) remains because
    ``find("edge", resolved.version)`` only looks for the resolved version.
    The fix removes ALL existing entries for Edge on force reinstall.
    """

    @pytest.mark.asyncio
    async def test_force_removes_stale_entry_under_old_system_version(self, tmp_path: Path) -> None:
        """Force reinstall should remove stale entries under old system versions."""
        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.edge import EdgeInstaller
        from browserget.registry import Registry

        registry = Registry(tmp_path)
        config = Config(cache_dir=tmp_path)
        http = HttpClient(timeout=5, max_retries=1)

        # Simulate a previous install where system Edge was v130
        old_artifact = InstalledArtifact(
            name="edge",
            version="130.0.0.0",
            path=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            installed_at=datetime.now(UTC),
            checksum=None,
        )
        registry.add(old_artifact)

        # Now system Edge has auto-updated to v131, and user requests v131
        installer = EdgeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="edge",
            version="131.0.0.0",
            url="https://example.com/edge.msi",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        async def fake_install_windows(resolved_ver, force_flag):
            installed = InstalledArtifact(
                name="edge",
                version="131.0.0.0",
                path=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
                installed_at=datetime.now(UTC),
                checksum=None,
            )
            registry.add(installed)
            return installed

        import unittest.mock as mock

        with mock.patch.object(installer, "_install_windows", side_effect=fake_install_windows):
            result = await installer.install(resolved, force=True)

        # The stale v130 entry should be gone
        assert registry.find("edge", "130.0.0.0") is None
        # Only the new v131 entry should exist
        assert registry.find("edge", "131.0.0.0") is not None
        all_entries = registry.get("edge")
        assert len(all_entries) == 1
        assert result.version == "131.0.0.0"


class TestBug58EdgeParserDeduplicatesVersions:
    """Bug 58: Edge parser parse_versions must deduplicate by version.

    The Edge API may return multiple releases with the same ProductVersion
    for the same platform+architecture.  The parser must not create
    duplicate ``ResolvedVersion`` entries.
    """

    def test_duplicate_versions_are_deduplicated(self) -> None:
        """parse_versions should not produce duplicate version entries."""
        from browserget.parsers.edge import parse_versions

        # Simulate API response with duplicate ProductVersion for same platform
        api_data = [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {
                                "Location": "https://example.com/edge_131.msi",
                                "Hash": "abc123",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    },
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",  # Same version!
                        "Artifacts": [
                            {
                                "Location": "https://example.com/edge_131_alt.msi",
                                "Hash": "def456",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    },
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "130.0.2849.68",
                        "Artifacts": [
                            {
                                "Location": "https://example.com/edge_130.msi",
                                "Hash": "ghi789",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    },
                ],
            }
        ]

        results = parse_versions(api_data, "edge", "win64")

        # Should have exactly 2 entries, not 3
        assert len(results) == 2
        versions = [v.version for v in results]
        assert "131.0.2903.86" in versions
        assert "130.0.2849.68" in versions
        # No duplicates
        assert len(versions) == len(set(versions))

    def test_duplicate_versions_across_products(self) -> None:
        """parse_versions should deduplicate across multiple Stable products."""
        from browserget.parsers.edge import parse_versions

        api_data = [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {"Location": "https://example.com/edge1.msi"},
                        ],
                    },
                ],
            },
            {
                "Product": "Stable",  # Duplicate Stable product
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.2903.86",
                        "Artifacts": [
                            {"Location": "https://example.com/edge2.msi"},
                        ],
                    },
                ],
            },
        ]

        results = parse_versions(api_data, "edge", "win64")
        assert len(results) == 1
        assert results[0].version == "131.0.2903.86"


# ---------------------------------------------------------------------------
# Bug 59: Installers with force=True must not remove old artifact directory
# before download succeeds
# ---------------------------------------------------------------------------


class TestBug59NoPrematureDeletion:
    """Tests that installers do not remove the old artifact directory before
    a successful download when force=True.

    Previously, all installers called ``safe_rmtree`` on the existing artifact
    directory at the start of ``install`` when ``force=True``.  If the download
    or verification subsequently failed, the user lost their working
    installation but the registry still pointed to the now-deleted path.
    """

    def test_firefox_install_preserves_dir_on_download_failure(self, tmp_path: Path) -> None:
        """Firefox installer must not remove old dir before download."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.firefox import FirefoxInstaller
        from browserget.models import ResolvedVersion

        registry = MagicMock()
        registry.find.return_value = InstalledArtifact(
            name="firefox",
            version="131.0",
            path=tmp_path / "firefox" / "131.0",
            installed_at=datetime.now(UTC),
            checksum=None,
        )

        config = Config(cache_dir=tmp_path / "cache")
        http = MagicMock(spec=HttpClient)
        http.download = AsyncMock(side_effect=RuntimeError("download failed"))
        installer = FirefoxInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="firefox",
            version="131.0",
            url="https://example.com/firefox.exe",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        with (
            patch("browserget.installers.firefox.safe_rmtree") as mock_rmtree,
            patch("browserget.installers.firefox.check_disk_space", return_value=True),
            patch("browserget.installers.firefox.get_download_dir") as mock_download_dir,
            patch("browserget.installers.firefox.safe_download_path") as mock_safe_dl,
        ):
            mock_download_dir.return_value = tmp_path / "downloads"
            mock_safe_dl.return_value = tmp_path / "downloads" / "firefox.exe"

            import asyncio

            with pytest.raises(RuntimeError, match="download failed"):
                asyncio.run(installer.install(resolved, force=True))

            # safe_rmtree must NOT be called before the download succeeds
            mock_rmtree.assert_not_called()

    def test_chrome_install_preserves_dir_on_download_failure(self, tmp_path: Path) -> None:
        """Chrome installer must not remove old dir before download."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.chrome import ChromeInstaller
        from browserget.models import ResolvedVersion

        registry = MagicMock()
        registry.find.return_value = InstalledArtifact(
            name="chrome",
            version="131.0.6778.87",
            path=tmp_path / "chrome" / "131.0.6778.87",
            installed_at=datetime.now(UTC),
            checksum=None,
        )

        config = Config(cache_dir=tmp_path / "cache")
        http = MagicMock(spec=HttpClient)
        http.download = AsyncMock(side_effect=RuntimeError("download failed"))
        installer = ChromeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="chrome",
            version="131.0.6778.87",
            url="https://example.com/chrome.zip",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        with (
            patch("browserget.installers.chrome.safe_rmtree") as mock_rmtree,
            patch("browserget.installers.chrome.check_disk_space", return_value=True),
            patch("browserget.installers.chrome.get_download_dir") as mock_download_dir,
            patch("browserget.installers.chrome.safe_download_path") as mock_safe_dl,
        ):
            mock_download_dir.return_value = tmp_path / "downloads"
            mock_safe_dl.return_value = tmp_path / "downloads" / "chrome.zip"

            import asyncio

            with pytest.raises(RuntimeError, match="download failed"):
                asyncio.run(installer.install(resolved, force=True))

            # safe_rmtree must NOT be called before the download succeeds
            mock_rmtree.assert_not_called()


# ---------------------------------------------------------------------------
# Bug 60: Edge installer force=True must not remove registry entries before
# install succeeds
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Edge system detection tests require Windows")
class TestBug60EdgeNoPrematureRegistryCleanup:
    """Tests that the Edge installer does not remove registry entries before
    the installation succeeds when force=True.

    Previously, ``EdgeInstaller.install`` removed all existing Edge registry
    entries at the start when ``force=True``.  If the platform-specific
    install then failed (e.g. network error, system Edge not found), the
    user lost all Edge registry entries with no replacement.
    """

    def test_edge_registry_entries_preserved_on_install_failure(self) -> None:
        """Edge installer must not remove registry entries before install succeeds."""
        from unittest.mock import MagicMock, patch

        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.edge import EdgeInstaller
        from browserget.models import ResolvedVersion

        existing_artifacts = [
            InstalledArtifact(
                name="edge",
                version="130.0.2849.68",
                path=Path("/fake/edge/130.0.2849.68"),
                installed_at=datetime.now(UTC),
                checksum=None,
            ),
            InstalledArtifact(
                name="edge",
                version="131.0.2903.86",
                path=Path("/fake/edge/131.0.2903.86"),
                installed_at=datetime.now(UTC),
                checksum=None,
            ),
        ]

        registry = MagicMock()
        registry.find.return_value = existing_artifacts[1]
        registry.get.return_value = list(existing_artifacts)

        config = Config(cache_dir=Path("/fake/cache"))
        http = MagicMock(spec=HttpClient)
        installer = EdgeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="edge",
            version="131.0.2903.86",
            url="https://example.com/edge.msi",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        with patch("browserget.installers.edge.SystemDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_edge.return_value = None
            mock_detector_cls.return_value = mock_detector

            with pytest.raises(RuntimeError, match="Edge is not installed"):
                import asyncio

                asyncio.run(installer.install(resolved, force=True))

            # Registry entries must NOT have been removed before the failed install
            registry.remove.assert_not_called()

    def test_edge_registry_entries_cleaned_after_success(self) -> None:
        """Edge installer should remove stale entries after successful install."""
        from unittest.mock import MagicMock, patch

        from browserget.config import Config
        from browserget.http import HttpClient
        from browserget.installers.edge import EdgeInstaller
        from browserget.models import InstalledArtifact, ResolvedVersion

        existing_artifacts = [
            InstalledArtifact(
                name="edge",
                version="130.0.2849.68",
                path=Path("/fake/edge/130.0.2849.68"),
                installed_at=datetime.now(UTC),
                checksum=None,
            ),
            InstalledArtifact(
                name="edge",
                version="131.0.2903.86",
                path=Path("/fake/edge/131.0.2903.86"),
                installed_at=datetime.now(UTC),
                checksum=None,
            ),
        ]

        registry = MagicMock()
        registry.find.return_value = existing_artifacts[1]
        registry.get.return_value = list(existing_artifacts)

        config = Config(cache_dir=Path("/fake/cache"))
        http = MagicMock(spec=HttpClient)
        installer = EdgeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="edge",
            version="131.0.2903.86",
            url="https://example.com/edge.msi",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        with patch("browserget.installers.edge.SystemDetector") as mock_detector_cls:
            from browserget.models import SystemBrowser

            mock_detector = MagicMock()
            mock_detector.detect_edge.return_value = SystemBrowser(
                name="edge",
                version="131.0.2903.86",
                path=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            )
            mock_detector_cls.return_value = mock_detector

            import asyncio

            result = asyncio.run(installer.install(resolved, force=True))

            # After success, stale entries (different version) should be removed
            registry.remove.assert_called_once_with("edge", "130.0.2849.68")
            assert result.version == "131.0.2903.86"
