"""Unit tests for system browser detection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from browserget.system import SystemDetector


class TestParseVersionOutput:
    """Tests for _parse_version_output static method."""

    @pytest.mark.parametrize(
        ("output", "expected"),
        [
            ("Google Chrome 131.0.6778.87", "131.0.6778.87"),
            ("Mozilla Firefox 129.0", "129.0"),
            ("Microsoft Edge 127.0.2651.74", "127.0.2651.74"),
            ("Chromium 120.0.6099.71 ", "120.0.6099.71"),
        ],
    )
    def test_parses_known_formats(self, output: str, expected: str) -> None:
        """_parse_version_output should extract version from known formats."""
        assert SystemDetector._parse_version_output(output) == expected

    def test_returns_none_on_empty(self) -> None:
        """_parse_version_output should return None on empty string."""
        assert SystemDetector._parse_version_output("") is None

    def test_returns_none_on_no_version(self) -> None:
        """_parse_version_output should return None when no version-like part exists."""
        assert SystemDetector._parse_version_output("no version here") is None


class TestDetectLinux:
    """Tests for Linux browser detection."""

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_chrome_found(self) -> None:
        """detect_chrome on Linux with which returning a path should return SystemBrowser."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Google Chrome 131.0.6778.87\n"
        with (
            patch("shutil.which", return_value="/usr/bin/google-chrome"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.name == "chrome"
        assert result.version == "131.0.6778.87"
        assert result.path == Path("/usr/bin/google-chrome")

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_chrome_not_found(self) -> None:
        """detect_chrome on Linux with which returning None should return None."""
        detector = SystemDetector()
        with patch("shutil.which", return_value=None):
            result = detector.detect_chrome()
        assert result is None

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_chrome_version_command_fails(self) -> None:
        """detect_chrome should return SystemBrowser with version=None when --version fails."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with (
            patch("shutil.which", return_value="/usr/bin/google-chrome"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.version is None

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_firefox_found(self) -> None:
        """detect_firefox on Linux should return SystemBrowser when found."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Mozilla Firefox 129.0\n"
        with (
            patch("shutil.which", return_value="/usr/bin/firefox"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_firefox()
        assert result is not None
        assert result.name == "firefox"
        assert result.version == "129.0"

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_edge_found(self) -> None:
        """detect_edge on Linux should return SystemBrowser when found."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Microsoft Edge 127.0.2651.74\n"
        with (
            patch("shutil.which", return_value="/usr/bin/microsoft-edge"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_edge()
        assert result is not None
        assert result.name == "edge"
        assert result.version == "127.0.2651.74"

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_chrome_falls_back_to_chromium(self) -> None:
        """detect_chrome should try google-chrome, google-chrome-stable, chromium in order."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Chromium 120.0.6099.71\n"
        with (
            patch("shutil.which", side_effect=[None, None, "/usr/bin/chromium"]),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.path == Path("/usr/bin/chromium")

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_all_filters_none(self) -> None:
        """detect_all should filter out None results."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Google Chrome 131.0\n"

        def _which(b: str) -> str | None:
            if b == "google-chrome":
                return "/usr/bin/google-chrome"
            return None

        with (
            patch("shutil.which", side_effect=_which),
            patch("subprocess.run", return_value=mock_result),
        ):
            results = detector.detect_all()
        assert len(results) == 1
        assert results[0].name == "chrome"

    @patch("browserget.system.sys.platform", "linux")
    def test_detection_never_raises_on_subprocess_error(self) -> None:
        """detect_chrome should return None when subprocess raises."""
        detector = SystemDetector()
        with (
            patch("shutil.which", return_value="/usr/bin/google-chrome"),
            patch("subprocess.run", side_effect=subprocess.SubprocessError("failed")),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.version is None


class TestDetectMacOS:
    """Tests for macOS browser detection."""

    @patch("browserget.system.sys.platform", "darwin")
    def test_detect_chrome_found(self) -> None:
        """detect_chrome on macOS should return SystemBrowser when app exists."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Google Chrome 131.0.6778.87\n"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.name == "chrome"

    @patch("browserget.system.sys.platform", "darwin")
    def test_detect_chrome_not_found(self) -> None:
        """detect_chrome on macOS should return None when app doesn't exist."""
        detector = SystemDetector()
        with patch("pathlib.Path.exists", return_value=False):
            result = detector.detect_chrome()
        assert result is None


@pytest.mark.skipif(sys.platform != "win32", reason="winreg is only available on Windows")
class TestDetectWindows:
    """Tests for Windows browser detection."""

    @patch("browserget.system.sys.platform", "win32")
    def test_detect_chrome_found(self) -> None:
        """detect_chrome on Windows should return SystemBrowser when exe exists."""
        detector = SystemDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Google Chrome 131.0.6778.87\n"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
            patch("winreg.OpenKey", side_effect=OSError("not found")),
        ):
            result = detector.detect_chrome()
        assert result is not None
        assert result.name == "chrome"

    @patch("browserget.system.sys.platform", "win32")
    def test_detect_chrome_not_found(self) -> None:
        """detect_chrome on Windows should return None when exe doesn't exist."""
        detector = SystemDetector()
        with patch("pathlib.Path.exists", return_value=False):
            result = detector.detect_chrome()
        assert result is None


class TestDetectAll:
    """Tests for detect_all()."""

    @patch("browserget.system.sys.platform", "linux")
    def test_detect_all_returns_only_found(self) -> None:
        """detect_all should only include found browsers."""
        detector = SystemDetector()
        with patch("shutil.which", return_value=None):
            results = detector.detect_all()
        assert results == []
