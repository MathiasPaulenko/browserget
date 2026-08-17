"""System browser detection across Windows, macOS, and Linux."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from browserget.models import SystemBrowser

_WINDOWS_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
}

_WINDOWS_REG_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"SOFTWARE\Google\Chrome\BLBeacon",
        r"SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon",
    ],
    "firefox": [r"SOFTWARE\Mozilla\Mozilla Firefox"],
    "edge": [
        r"SOFTWARE\Microsoft\Edge\BLBeacon",
        r"SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon",
    ],
}

_MACOS_PATHS: dict[str, str] = {
    "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "firefox": "/Applications/Firefox.app/Contents/MacOS/firefox",
    "edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
}

_LINUX_BINARIES: dict[str, list[str]] = {
    "chrome": ["google-chrome", "google-chrome-stable", "chromium"],
    "firefox": ["firefox"],
    "edge": ["microsoft-edge"],
}


class SystemDetector:
    """Detect browsers installed on the system (outside the browserget cache).

    All detection methods are safe: they return ``None`` if the browser is
    not found or if detection fails for any reason.
    """

    def detect_chrome(self) -> SystemBrowser | None:
        """Detect a system-installed Chrome or Chromium browser.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        return self._detect("chrome")

    def detect_firefox(self) -> SystemBrowser | None:
        """Detect a system-installed Firefox browser.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        return self._detect("firefox")

    def detect_edge(self) -> SystemBrowser | None:
        """Detect a system-installed Microsoft Edge browser.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        return self._detect("edge")

    def detect_all(self) -> list[SystemBrowser]:
        """Detect all known system browsers.

        Returns:
            A list of detected ``SystemBrowser`` instances (excluding any
            that were not found).
        """
        results = [self.detect_chrome(), self.detect_firefox(), self.detect_edge()]
        return [b for b in results if b is not None]

    def _detect(self, name: str) -> SystemBrowser | None:
        """Dispatch detection to the platform-specific method.

        Args:
            name: Browser name ("chrome", "firefox", or "edge").

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        if sys.platform == "win32":
            return self._detect_windows(name)
        if sys.platform == "darwin":
            return self._detect_macos(name)
        return self._detect_linux(name)

    def _detect_windows(self, name: str) -> SystemBrowser | None:
        """Detect a browser on Windows using registry and known paths.

        Args:
            name: Browser name.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        if sys.platform != "win32":
            return None

        try:
            import winreg
        except ModuleNotFoundError:
            return None

        for exe_path_str in _WINDOWS_PATHS.get(name, []):
            exe_path = Path(exe_path_str)
            if not exe_path.exists():
                continue
            version = self._get_version_windows(name, winreg, str(exe_path))
            return SystemBrowser(name=name, version=version, path=exe_path)
        return None

    def _detect_macos(self, name: str) -> SystemBrowser | None:
        """Detect a browser on macOS using known application paths.

        Args:
            name: Browser name.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        app_path_str = _MACOS_PATHS.get(name)
        if app_path_str is None:
            return None
        app_path = Path(app_path_str)
        if not app_path.exists():
            return None
        version = self._get_version_macos(app_path)
        return SystemBrowser(name=name, version=version, path=app_path)

    def _detect_linux(self, name: str) -> SystemBrowser | None:
        """Detect a browser on Linux using ``shutil.which``.

        Tries multiple binary names in order (e.g. google-chrome,
        google-chrome-stable, chromium) and returns the first found.

        Args:
            name: Browser name.

        Returns:
            A ``SystemBrowser`` instance if found, otherwise ``None``.
        """
        for binary in _LINUX_BINARIES.get(name, []):
            resolved = shutil.which(binary)
            if resolved is None:
                continue
            version = self._get_version_linux(resolved)
            return SystemBrowser(name=name, version=version, path=Path(resolved))
        return None

    def _get_version_windows(self, name: str, winreg: object, exe_path: str) -> str | None:
        """Extract browser version on Windows from registry or ``--version``.

        Args:
            name: Browser name.
            winreg: The ``winreg`` module (passed to avoid import at module level).
            exe_path: Path to the browser executable.

        Returns:
            Version string, or ``None`` if extraction fails.
        """
        for reg_path in _WINDOWS_REG_PATHS.get(name, []):
            try:
                with winreg.OpenKey(  # type: ignore[attr-defined]
                    winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                    reg_path,
                ) as key:
                    for value_name in ("version", "CurrentVersion"):
                        try:
                            version, _ = winreg.QueryValueEx(  # type: ignore[attr-defined]
                                key, value_name
                            )
                            return str(version)
                        except OSError:
                            continue
            except OSError:
                continue
        return self._run_version_command(exe_path)

    def _get_version_macos(self, app_path: Path) -> str | None:
        """Extract browser version on macOS from Info.plist or ``--version``.

        Args:
            app_path: Path to the browser executable inside the .app bundle.

        Returns:
            Version string, or ``None`` if extraction fails.
        """
        try:
            import plistlib

            plist_path = app_path.parent.parent / "Info.plist"
            if plist_path.exists():
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
                    version = plist.get("CFBundleShortVersionString")
                    if version:
                        return str(version)
        except (OSError, ValueError):
            pass
        return self._run_version_command(str(app_path))

    def _get_version_linux(self, binary_path: str) -> str | None:
        """Extract browser version on Linux by running ``--version``.

        Args:
            binary_path: Path to the browser binary.

        Returns:
            Version string, or ``None`` if extraction fails.
        """
        return self._run_version_command(binary_path)

    def _run_version_command(self, exe_path: str) -> str | None:
        """Run ``browser --version`` and parse the output.

        Args:
            exe_path: Path to the browser executable.

        Returns:
            The parsed version string, or ``None`` if the command fails.
        """
        try:
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                errors="replace",
            )
            if result.returncode != 0:
                return None
            return self._parse_version_output(result.stdout)
        except (OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _parse_version_output(output: str) -> str | None:
        """Extract a version string from browser ``--version`` output.

        Handles common formats:
        - ``Google Chrome 131.0.6778.87``
        - ``Mozilla Firefox 129.0``
        - ``Microsoft Edge 127.0.2651.74``

        Args:
            output: Raw stdout from ``--version``.

        Returns:
            The version string, or ``None`` if parsing fails.
        """
        if not output:
            return None
        parts = output.strip().split()
        if not parts:
            return None
        for part in parts:
            cleaned = part.rstrip(",;)")
            if cleaned and cleaned[0].isdigit():
                return cleaned
        return None
