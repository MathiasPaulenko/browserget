"""Regression tests for Phase 5 audit fixes.

Each test class corresponds to a specific bug fix:

1. Checksum comparison normalizes case and rejects non-ASCII safely.
2. Retry-After header values are capped to a bounded delay.
3. cleanup_downloads handles a regular file at the downloads path.
4. safe_rmtree handles regular files and missing paths.
5. Path component validation rejects Windows-hostile names.
6. install/ensure dedupe repeated target names.
7. remove --all combined with --version is rejected.
8. doctor reports a corrupted registry file as failed.
9. ensure falls back to existing install when offline.
10. Only http/https URL schemes are allowed.
11. Text fetches are size-capped.
12. UTF-32 BOMs decode correctly.
13. Firefox version pattern is anchored at the end.
14. Requesting an ESR version never resolves to a non-ESR build.
15. EdgeDriver version strings are validated before building URLs.
16. Zip extraction preserves executable bits on POSIX.
17. x86 (32-bit) machines detect Arch.X86 and map correctly.
18. Per-user Windows browser installs under LOCALAPPDATA are detected.
19. Windows registry versions like "140.0 (x64 en-US)" parse cleanly.
20. Linux detection knows chromium-browser and microsoft-edge-stable.
21. Edge pkg installs fail fast without interactive sudo and verify the path.
22. Failed installs clean up the partially-created artifact directory.
23. Registry add/remove are serialized via a file lock.
24. Registry save cleans up stale tmp files.
25. _exit_with_error prints a real traceback outside except blocks.
26. User-Agent reports the installed package version.
27. HttpClient validates timeout/max_retries.
28. Edge parser scans all artifacts for a valid Location.
29. load_config ignores a whitespace-only BROWSERGET_CACHE_DIR.
30. remove --all tolerates corrupted registry entries.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from browserget.cache import (
    _validate_path_component,
    cleanup_downloads,
    safe_rmtree,
)
from browserget.checksum import compute_checksum, verify_checksum, verify_or_raise
from browserget.exceptions import (
    ChecksumMismatchError,
    DriverMatchError,
    NetworkError,
    VersionNotFoundError,
)
from browserget.http import HttpClient
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.platform import OS, Arch, Platform, map_platform
from browserget.registry import Registry

# ---------------------------------------------------------------------------
# Bug 1: checksum comparison normalizes and never raises TypeError
# ---------------------------------------------------------------------------


class TestChecksumNormalization:
    def test_uppercase_expected_matches(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"data")
        expected = compute_checksum(f, "sha256").upper()
        assert verify_checksum(f, expected, "sha256") is True

    def test_surrounding_whitespace_matches(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"data")
        expected = compute_checksum(f, "sha256")
        assert verify_checksum(f, f"  {expected} \n", "sha256") is True

    def test_non_ascii_expected_returns_false_not_type_error(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"data")
        assert verify_checksum(f, "éàü", "sha256") is False

    def test_non_hex_expected_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"data")
        assert verify_checksum(f, "not-a-hex-string!", "sha256") is False

    def test_verify_or_raise_non_ascii_raises_mismatch(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"data")
        with pytest.raises(ChecksumMismatchError):
            verify_or_raise(f, "éàü", "sha256")


# ---------------------------------------------------------------------------
# Bug 2: Retry-After is capped
# ---------------------------------------------------------------------------


class TestRetryAfterCap:
    def test_retry_after_capped(self) -> None:
        client = HttpClient()
        exc = urllib.error.HTTPError("https://x", 429, "Too Many", {"Retry-After": "86400"}, None)
        delay = client._backoff_delay(1, exc)
        assert 0 <= delay <= 60.0

    def test_retry_after_negative_clamped(self) -> None:
        client = HttpClient()
        exc = urllib.error.HTTPError("https://x", 429, "Too Many", {"Retry-After": "-5"}, None)
        assert client._backoff_delay(1, exc) == 0.0

    def test_exponential_backoff_capped(self) -> None:
        client = HttpClient()
        assert client._backoff_delay(30) <= 60.0


# ---------------------------------------------------------------------------
# Bugs 3-4: cleanup_downloads and safe_rmtree handle regular files
# ---------------------------------------------------------------------------


class TestCleanupRegularFile:
    def test_cleanup_downloads_with_regular_file_at_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BROWSERGET_CACHE_DIR", str(tmp_path))
        (tmp_path / "downloads").write_text("not a dir")
        cleanup_downloads()
        assert not (tmp_path / "downloads").exists()

    def test_safe_rmtree_regular_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("x")
        safe_rmtree(f)
        assert not f.exists()

    def test_safe_rmtree_missing_path_still_raises(self, tmp_path: Path) -> None:
        # Contract preserved from phase 3: missing paths raise OSError.
        with pytest.raises(OSError):
            safe_rmtree(tmp_path / "missing")


# ---------------------------------------------------------------------------
# Bug 5: path component validation — Windows hostile names
# ---------------------------------------------------------------------------


class TestPathComponentWindowsHardening:
    @pytest.mark.parametrize(
        "bad",
        [
            "a:b",
            "a<b",
            "a>b",
            "a|b",
            "a?b",
            "a*b",
            "NUL",
            "nul",
            "CON.txt",
            "com1",
            "LPT3",
            "x.",
            "x ",
            "a\x01b",
        ],
    )
    def test_rejected(self, bad: str) -> None:
        with pytest.raises(ValueError):
            _validate_path_component(bad)

    @pytest.mark.parametrize(
        "good", ["131.0.6778.87", "128.0esr", "chrome", "Firefox Setup 131.0.exe", "v0.36.0"]
    )
    def test_accepted(self, good: str) -> None:
        assert _validate_path_component(good) == good


# ---------------------------------------------------------------------------
# Bug 6: duplicate targets are deduplicated
# ---------------------------------------------------------------------------


class TestDuplicateTargets:
    def test_install_dedupes(self, patched_installers: dict) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        result = CliRunner().invoke(app, ["install", "chrome", "chrome", "--json"])
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.output)) == 1

    def test_ensure_dedupes(self, patched_installers: dict) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        result = CliRunner().invoke(app, ["ensure", "firefox", "firefox", "--json"])
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.output)) == 1


@pytest.fixture
def patched_installers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    from browserget import cli as cli_module

    installed = InstalledArtifact(
        name="chrome",
        version="131.0.0.0",
        path=tmp_path / "chrome",
        installed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        checksum=None,
    )
    resolved = ResolvedVersion(
        name="chrome",
        version="131.0.0.0",
        url="https://example.com/x.zip",
        platform="win64",
        checksum=None,
        checksum_algorithm=None,
    )

    def make(target: str) -> MagicMock:
        m = MagicMock()
        m.name = target
        m.resolve = AsyncMock(return_value=resolved)
        m.match_browser = AsyncMock(return_value=resolved)
        m.install = AsyncMock(return_value=installed)
        return m

    instances = {
        t: make(t)
        for t in ("chrome", "chromedriver", "firefox", "geckodriver", "edge", "edgedriver")
    }
    monkeypatch.setattr(cli_module, "_create_installer", lambda t, h, r, c: instances[t])
    monkeypatch.setattr(
        cli_module,
        "load_config",
        lambda: MagicMock(cache_dir=tmp_path, timeout=30, max_retries=3),
    )
    return instances


# ---------------------------------------------------------------------------
# Bug 7: remove --all --version conflict
# ---------------------------------------------------------------------------


class TestRemoveConflictingFlags:
    def test_remove_all_with_version_errors(self) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        result = CliRunner().invoke(app, ["remove", "chrome", "--all", "--version", "1.2.3"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Bug 8: doctor detects corrupted registry
# ---------------------------------------------------------------------------


class TestDoctorCorruptedRegistry:
    def test_corrupted_registry_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "registry.json").write_text("{not valid json")

        monkeypatch.setattr(
            "browserget.cli.load_config",
            lambda: MagicMock(cache_dir=cache),
        )
        monkeypatch.setattr("browserget.cli._run_async", lambda f: [("x", True, "ok")])
        monkeypatch.setattr("browserget.system.SystemDetector.detect_all", lambda self: [])

        result = CliRunner().invoke(app, ["doctor"])
        assert "corrupted" in result.output


# ---------------------------------------------------------------------------
# Bug 9: ensure falls back to existing install offline
# ---------------------------------------------------------------------------


class TestEnsureOfflineFallback:
    async def test_ensure_returns_existing_when_network_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime

        from browserget import cli as cli_module
        from browserget.cli import _ensure_one

        installed = InstalledArtifact(
            name="chrome",
            version="130.0.0.0",
            path=tmp_path / "chrome",
            installed_at=datetime.datetime.now(datetime.UTC),
            checksum=None,
        )
        installer = MagicMock()
        installer.resolve = AsyncMock(side_effect=NetworkError(url="x", reason="offline"))
        registry = MagicMock()
        registry.find.return_value = installed

        monkeypatch.setattr(cli_module, "_create_installer", lambda t, h, r, c: installer)

        result = await _ensure_one("chrome", None, False, None, MagicMock(), registry, MagicMock())
        assert result == (installed, False)

    async def test_ensure_reraises_when_nothing_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from browserget import cli as cli_module
        from browserget.cli import _ensure_one

        installer = MagicMock()
        installer.resolve = AsyncMock(side_effect=NetworkError(url="x", reason="offline"))
        registry = MagicMock()
        registry.find.return_value = None

        monkeypatch.setattr(cli_module, "_create_installer", lambda t, h, r, c: installer)

        with pytest.raises(NetworkError):
            await _ensure_one("chrome", None, False, None, MagicMock(), registry, MagicMock())

    async def test_ensure_reraises_when_forced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime

        from browserget import cli as cli_module
        from browserget.cli import _ensure_one

        installed = InstalledArtifact(
            name="chrome",
            version="130.0.0.0",
            path=tmp_path / "chrome",
            installed_at=datetime.datetime.now(datetime.UTC),
            checksum=None,
        )
        installer = MagicMock()
        installer.resolve = AsyncMock(side_effect=NetworkError(url="x", reason="offline"))
        registry = MagicMock()
        registry.find.return_value = installed

        monkeypatch.setattr(cli_module, "_create_installer", lambda t, h, r, c: installer)

        with pytest.raises(NetworkError):
            await _ensure_one("chrome", None, True, None, MagicMock(), registry, MagicMock())


# ---------------------------------------------------------------------------
# Bug 10: URL scheme allowlist
# ---------------------------------------------------------------------------


class TestUrlSchemeAllowlist:
    @pytest.mark.parametrize("scheme", ["file", "ftp", "data", "gopher"])
    def test_non_http_schemes_rejected(self, scheme: str) -> None:
        client = HttpClient()
        with pytest.raises(NetworkError):
            client._encode_url(f"{scheme}:///etc/passwd")

    @pytest.mark.parametrize("scheme", ["http", "https", "HTTP", "HTTPS"])
    def test_http_schemes_allowed(self, scheme: str) -> None:
        client = HttpClient()
        assert client._encode_url(f"{scheme}://example.com/x").startswith("http")


# ---------------------------------------------------------------------------
# Bug 11: response size cap
# ---------------------------------------------------------------------------


class TestFetchTextSizeCap:
    def test_oversized_response_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        import browserget.http as http_module

        monkeypatch.setattr(http_module, "_MAX_TEXT_BYTES", 10)

        class FakeResp:
            def __enter__(self) -> FakeResp:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def read(self, n: int = -1) -> bytes:
                return b"x" * 11

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())
        client = HttpClient(max_retries=1)
        with pytest.raises(NetworkError):
            client._fetch_text_sync("https://example.com")


# ---------------------------------------------------------------------------
# Bug 12: UTF-32 BOM
# ---------------------------------------------------------------------------


class TestUtf32Bom:
    def test_utf32_le_decoded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        payload = '{"ok": true}'.encode("utf-32")

        class FakeResp:
            def __enter__(self) -> FakeResp:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def read(self, n: int = -1) -> bytes:
                return payload

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())
        client = HttpClient()
        assert client._fetch_text_sync("https://example.com") == '{"ok": true}'


# ---------------------------------------------------------------------------
# Bug 13: firefox version pattern anchored
# ---------------------------------------------------------------------------


class TestFirefoxPatternAnchor:
    def test_non_version_names_excluded(self) -> None:
        from browserget.parsers.firefox import parse_releases

        html = '<a href="131.0/">x</a><a href="1abc/">y</a><a href="2.5beta/">z</a>'
        versions = parse_releases(html)
        assert "131.0" in versions
        assert "1abc" not in versions
        assert "2.5beta" not in versions


# ---------------------------------------------------------------------------
# Bug 14: esr request never resolves to non-esr
# ---------------------------------------------------------------------------


class TestEsrDirection:
    async def test_esr_request_rejects_non_esr(self) -> None:
        from browserget.installers.firefox import FirefoxInstaller

        installer = FirefoxInstaller(MagicMock(), MagicMock(), MagicMock())
        html = '<a href="140.0/">x</a>'
        installer._http.get_text = AsyncMock(
            side_effect=[html, NetworkError(url="c", reason="skip")]
        )

        with pytest.raises(VersionNotFoundError):
            await installer.resolve("140.0esr")

    async def test_bare_version_can_match_esr(self) -> None:
        from browserget.installers.firefox import FirefoxInstaller

        installer = FirefoxInstaller(MagicMock(), MagicMock(), MagicMock())
        html = '<a href="140.0esr/">x</a>'
        installer._http.get_text = AsyncMock(
            side_effect=[html, NetworkError(url="c", reason="skip")]
        )

        resolved = await installer.resolve("140.0")
        assert resolved.version == "140.0esr"


# ---------------------------------------------------------------------------
# Bug 15: edgedriver version validation
# ---------------------------------------------------------------------------


class TestEdgedriverVersionValidation:
    async def test_resolve_rejects_garbage_version(self) -> None:
        from browserget.installers.edge import EdgeDriverInstaller

        installer = EdgeDriverInstaller(MagicMock(), MagicMock(), MagicMock())
        with pytest.raises(VersionNotFoundError):
            await installer.resolve("../evil")

    async def test_resolve_rejects_non_version(self) -> None:
        from browserget.installers.edge import EdgeDriverInstaller

        installer = EdgeDriverInstaller(MagicMock(), MagicMock(), MagicMock())
        with pytest.raises(VersionNotFoundError):
            await installer.resolve("abc")

    async def test_match_browser_rejects_garbage(self) -> None:
        from browserget.installers.edge import EdgeDriverInstaller

        installer = EdgeDriverInstaller(MagicMock(), MagicMock(), MagicMock())
        with pytest.raises(DriverMatchError):
            await installer.match_browser("../evil")


# ---------------------------------------------------------------------------
# Bug 16: zip extraction preserves exec bits (POSIX only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="exec bits are POSIX-only")
class TestZipExecBits:
    def test_executable_bit_preserved(self, tmp_path: Path) -> None:
        from browserget.archive import extract_zip

        zpath = tmp_path / "a.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            info = zipfile.ZipInfo("bin/tool")
            info.external_attr = 0o100755 << 16
            zf.writestr(info, b"#!/bin/sh\n")

        dest = tmp_path / "out"
        extract_zip(zpath, dest)
        mode = (dest / "bin" / "tool").stat().st_mode
        assert mode & stat.S_IXUSR


# ---------------------------------------------------------------------------
# Bug 17: x86 arch detection and mapping
# ---------------------------------------------------------------------------


class TestX86Detection:
    def test_i686_detects_x86(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import platform as _p

        from browserget.platform import detect_arch

        monkeypatch.setattr(_p, "machine", lambda: "i686")
        assert detect_arch() == Arch.X86

    def test_x86_maps_to_win32(self) -> None:
        p = Platform(os=OS.WINDOWS, arch=Arch.X86)
        assert map_platform(p, "cft") == "win32"
        assert map_platform(p, "firefox") == "win32"
        assert map_platform(p, "edgedriver") == "win32"

    def test_linux_x86_maps_i686(self) -> None:
        p = Platform(os=OS.LINUX, arch=Arch.X86)
        assert map_platform(p, "firefox") == "linux-i686"


# ---------------------------------------------------------------------------
# Bugs 18-20: system detection improvements
# ---------------------------------------------------------------------------


class TestSystemDetectionImprovements:
    def test_localappdata_browser_detected(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows-only")

        import browserget.system as system_module

        fake_exe = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
        fake_exe.parent.mkdir(parents=True)
        fake_exe.write_text("x")

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(system_module, "_WINDOWS_PATHS", {})
        detector = system_module.SystemDetector()
        monkeypatch.setattr(detector, "_get_version_windows", lambda *a: "1.0.0.0")

        found = detector.detect_chrome()
        assert found is not None
        assert found.path == fake_exe

    def test_version_string_parsed_from_registry_value(self) -> None:
        from browserget.system import SystemDetector

        assert SystemDetector._parse_version_output("140.0 (x64 en-US)") == "140.0"

    def test_linux_binary_lists(self) -> None:
        from browserget.system import _LINUX_BINARIES

        assert "chromium-browser" in _LINUX_BINARIES["chrome"]
        assert "microsoft-edge-stable" in _LINUX_BINARIES["edge"]


# ---------------------------------------------------------------------------
# Bug 21: sudo -n and post-install path verification (source inspection)
# ---------------------------------------------------------------------------


class TestEdgePkgInstallHardening:
    def test_sudo_non_interactive_flag_used(self) -> None:
        import inspect

        from browserget.installers import edge as edge_module

        source = inspect.getsource(edge_module)
        assert '"sudo", "-n"' in source

    def test_post_install_path_verified(self) -> None:
        import inspect

        from browserget.installers import edge as edge_module

        source = inspect.getsource(edge_module)
        assert "edge_path.exists()" in source


# ---------------------------------------------------------------------------
# Bug 22: artifact dir cleanup on failure
# ---------------------------------------------------------------------------


class TestArtifactDirCleanup:
    async def test_failed_extract_removes_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from browserget.installers.chrome import ChromeInstaller

        monkeypatch.setenv("BROWSERGET_CACHE_DIR", str(tmp_path))

        registry = MagicMock()
        registry.find.return_value = None
        http = MagicMock()
        http.download = AsyncMock()
        config = MagicMock()
        installer = ChromeInstaller(http, registry, config)

        resolved = ResolvedVersion(
            name="chrome",
            version="131.0.0.0",
            url="https://example.com/chrome.zip",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )

        # http.download writes nothing, so extract_zip hits a missing file.
        with pytest.raises(OSError):
            await installer.install(resolved, force=False)

        artifact_dir = tmp_path / "chrome" / "131.0.0.0"
        assert not artifact_dir.exists()


# ---------------------------------------------------------------------------
# Bug 23: registry add/remove serialized
# ---------------------------------------------------------------------------


class TestRegistryLocking:
    def test_concurrent_adds_both_persist(self, tmp_path: Path) -> None:
        import datetime

        registry = Registry(tmp_path)
        barrier = threading.Barrier(2)

        def add(version: str) -> None:
            barrier.wait()
            registry.add(
                InstalledArtifact(
                    name="chrome",
                    version=version,
                    path=tmp_path / version,
                    installed_at=datetime.datetime.now(datetime.UTC),
                    checksum=None,
                )
            )

        t1 = threading.Thread(target=add, args=("1.0",))
        t2 = threading.Thread(target=add, args=("2.0",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        versions = {a.version for a in registry.get("chrome")}
        assert versions == {"1.0", "2.0"}


# ---------------------------------------------------------------------------
# Bug 24: stale tmp cleanup on save
# ---------------------------------------------------------------------------


class TestRegistryTmpCleanup:
    def test_stale_tmp_removed_on_save(self, tmp_path: Path) -> None:
        import datetime

        registry = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        stale = tmp_path / "tmpabcdef.tmp"
        stale.write_text("stale")

        registry.add(
            InstalledArtifact(
                name="chrome",
                version="1.0",
                path=tmp_path / "x",
                installed_at=datetime.datetime.now(datetime.UTC),
                checksum=None,
            )
        )
        assert not stale.exists()


# ---------------------------------------------------------------------------
# Bug 25: _exit_with_error prints real traceback outside except
# ---------------------------------------------------------------------------


class TestExitWithErrorTraceback:
    def test_no_nonetype_noise_on_debug(self) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        result = CliRunner().invoke(app, ["install", "badtarget", "--debug"])
        assert "NoneType" not in result.output


# ---------------------------------------------------------------------------
# Bug 26: User-Agent reports real version
# ---------------------------------------------------------------------------


class TestUserAgent:
    def test_user_agent_uses_package_version(self) -> None:
        import browserget.http as http_module
        from browserget import __version__

        assert f"browserget/{__version__}" == http_module._USER_AGENT


# ---------------------------------------------------------------------------
# Bug 27: HttpClient init validation
# ---------------------------------------------------------------------------


class TestHttpClientValidation:
    def test_zero_timeout_rejected(self) -> None:
        with pytest.raises(ValueError):
            HttpClient(timeout=0)

    def test_negative_max_retries_rejected(self) -> None:
        with pytest.raises(ValueError):
            HttpClient(max_retries=-1)


# ---------------------------------------------------------------------------
# Bug 28: edge parser scans all artifacts
# ---------------------------------------------------------------------------


class TestEdgeArtifactScan:
    def test_second_artifact_used_when_first_invalid(self) -> None:
        from browserget.parsers.edge import parse_versions

        data = [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "131.0.0.1",
                        "Artifacts": [
                            {"ArtifactName": "bad"},
                            {
                                "ArtifactName": "good.msi",
                                "Location": "https://x/good.msi",
                                "Hash": "aa",
                                "HashAlgorithm": "SHA256",
                            },
                        ],
                    }
                ],
            }
        ]
        versions = parse_versions(data, "edge", "win64")
        assert len(versions) == 1
        assert versions[0].url == "https://x/good.msi"


# ---------------------------------------------------------------------------
# Bug 29: whitespace cache dir falls back to default
# ---------------------------------------------------------------------------


class TestWhitespaceCacheDir:
    def test_whitespace_env_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from browserget.config import _default_cache_dir, load_config

        monkeypatch.setenv("BROWSERGET_CACHE_DIR", "   ")
        assert load_config().cache_dir == _default_cache_dir()


# ---------------------------------------------------------------------------
# Bug 30: remove --all tolerates corrupted registry entries
# ---------------------------------------------------------------------------


class TestRemoveCorruptedRegistry:
    def test_remove_all_with_bad_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from browserget.cli import app

        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "registry.json").write_text(
            json.dumps(
                {
                    "chrome": [
                        {
                            "name": "chrome",
                            "version": "../evil",
                            "path": str(tmp_path),
                            "installed_at": "2025-01-01T00:00:00+00:00",
                            "checksum": None,
                        }
                    ]
                }
            )
        )
        monkeypatch.setattr("browserget.cli.load_config", lambda: MagicMock(cache_dir=cache))

        result = CliRunner().invoke(app, ["remove", "chrome", "--all"])
        assert result.exit_code == 0
        assert json.loads((cache / "registry.json").read_text()) == {}
