"""Custom exception hierarchy for browserget."""

from __future__ import annotations


class BrowsergetError(Exception):
    """Base exception for all browserget errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class VersionNotFoundError(BrowsergetError):
    """Raised when a requested version is not found upstream."""

    def __init__(self, version: str, name: str, top_3_versions: str) -> None:
        message = (
            f"Version {version} not found for {name}. "
            f"Available: {top_3_versions}. "
            f"Run `browserget versions {name}` to see all."
        )
        super().__init__(message)
        self.version = version
        self.name = name
        self.top_3_versions = top_3_versions


class UnsupportedPlatformError(BrowsergetError):
    """Raised when the current platform is not supported for a target."""

    def __init__(self, platform: str, name: str) -> None:
        message = f"Platform {platform} is not supported for {name}."
        super().__init__(message)
        self.platform = platform
        self.name = name


class NetworkError(BrowsergetError):
    """Raised when a network request fails."""

    def __init__(self, url: str, reason: str) -> None:
        message = (
            f"Failed to connect to {url}: {reason}. Check your network connection and try again."
        )
        super().__init__(message)
        self.url = url
        self.reason = reason


class ChecksumMismatchError(BrowsergetError):
    """Raised when a downloaded file's checksum does not match the expected value."""

    def __init__(self, filename: str, expected: str, actual: str) -> None:
        message = (
            f"Checksum mismatch for {filename}. "
            f"Expected: {expected[:16]}... "
            f"Got: {actual[:16]}... "
            f"The download may be corrupted. Try again with --force."
        )
        super().__init__(message)
        self.filename = filename
        self.expected = expected
        self.actual = actual


class AlreadyInstalledError(BrowsergetError):
    """Raised when an artifact is already installed and --force was not used."""

    def __init__(self, name: str, version: str) -> None:
        message = f"{name} {version} is already installed. Use --force to reinstall."
        super().__init__(message)
        self.name = name
        self.version = version


class DriverMatchError(BrowsergetError):
    """Raised when a driver cannot be auto-matched to an installed browser."""

    def __init__(self, driver: str, browser: str) -> None:
        message = (
            f"Cannot match {driver} — no {browser} installation found. "
            f"Install {browser} first: `browserget install {browser}`, "
            f"or specify a version: `browserget install {driver} --version X`"
        )
        super().__init__(message)
        self.driver = driver
        self.browser = browser


class UnknownTargetError(BrowsergetError):
    """Raised when an unknown browser or driver name is given."""

    def __init__(self, target: str) -> None:
        message = (
            f"Unknown browser or driver: {target}. "
            f"Supported: chrome, firefox, edge, chromedriver, geckodriver, edgedriver."
        )
        super().__init__(message)
        self.target = target


class InsufficientDiskSpaceError(BrowsergetError):
    """Raised when there is not enough disk space for an installation."""

    def __init__(self, required_mb: int, available_mb: int) -> None:
        message = f"Not enough disk space. Need ~{required_mb}MB, available: {available_mb}MB."
        super().__init__(message)
        self.required_mb = required_mb
        self.available_mb = available_mb
