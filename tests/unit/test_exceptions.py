"""Unit tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from browserget.exceptions import (
    AlreadyInstalledError,
    BrowsergetError,
    ChecksumMismatchError,
    DriverMatchError,
    InsufficientDiskSpaceError,
    NetworkError,
    UnknownTargetError,
    UnsupportedPlatformError,
    VersionNotFoundError,
)

_ALL_EXCEPTIONS = [
    VersionNotFoundError,
    UnsupportedPlatformError,
    NetworkError,
    ChecksumMismatchError,
    AlreadyInstalledError,
    DriverMatchError,
    UnknownTargetError,
    InsufficientDiskSpaceError,
]


class TestExceptionHierarchy:
    """Tests for the exception class hierarchy."""

    @pytest.mark.parametrize("exc_class", _ALL_EXCEPTIONS)
    def test_all_inherit_from_browserget_error(self, exc_class: type) -> None:
        """All exceptions should inherit from BrowsergetError."""
        assert issubclass(exc_class, BrowsergetError)

    @pytest.mark.parametrize("exc_class", _ALL_EXCEPTIONS)
    def test_all_inherit_from_exception(self, exc_class: type) -> None:
        """All exceptions should inherit from Exception."""
        assert issubclass(exc_class, Exception)

    def test_raisable_and_catchable_by_own_class(self) -> None:
        """Each exception should be catchable by its own class."""
        instances: list[BrowsergetError] = [
            VersionNotFoundError("v1", "chrome", "none"),
            UnsupportedPlatformError("solaris", "edge"),
            NetworkError("http://x", "timeout"),
            ChecksumMismatchError("file.zip", "abc", "def"),
            AlreadyInstalledError("chrome", "1.0"),
            DriverMatchError("chromedriver", "chrome"),
            UnknownTargetError("safari"),
            InsufficientDiskSpaceError(200, 50),
        ]
        for exc in instances:
            with pytest.raises(type(exc)):
                raise exc


class TestVersionNotFoundError:
    """Tests for VersionNotFoundError."""

    def test_message_contains_version_and_name(self) -> None:
        """Message should contain the version and name."""
        exc = VersionNotFoundError(
            version="999.0", name="chrome", top_3_versions="131.0, 130.0, 129.0"
        )
        assert "999.0" in exc.message
        assert "chrome" in exc.message

    def test_message_contains_top_3_versions(self) -> None:
        """Message should contain the top 3 versions."""
        exc = VersionNotFoundError(
            version="999.0", name="chrome", top_3_versions="131.0, 130.0, 129.0"
        )
        assert "131.0, 130.0, 129.0" in exc.message

    def test_message_with_empty_top_3(self) -> None:
        """Message should be well-formed even with empty top_3_versions."""
        exc = VersionNotFoundError(version="999.0", name="chrome", top_3_versions="none")
        assert "none" in exc.message
        assert "999.0" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters as attributes."""
        exc = VersionNotFoundError(version="999.0", name="chrome", top_3_versions="131.0, 130.0")
        assert exc.version == "999.0"
        assert exc.name == "chrome"
        assert exc.top_3_versions == "131.0, 130.0"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise VersionNotFoundError("v1", "chrome", "none")

    def test_catchable_by_exception(self) -> None:
        """Should be catchable by Exception."""
        try:
            raise VersionNotFoundError("v1", "chrome", "none")
        except Exception as exc:  # noqa: BLE001
            assert isinstance(exc, VersionNotFoundError)


class TestUnsupportedPlatformError:
    """Tests for UnsupportedPlatformError."""

    def test_message_contains_platform_and_name(self) -> None:
        """Message should contain the platform and name."""
        exc = UnsupportedPlatformError(platform="linux-arm64", name="cft")
        assert "linux-arm64" in exc.message
        assert "cft" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = UnsupportedPlatformError(platform="solaris", name="edge")
        assert exc.platform == "solaris"
        assert exc.name == "edge"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise UnsupportedPlatformError("solaris", "edge")


class TestNetworkError:
    """Tests for NetworkError."""

    def test_message_contains_url_and_reason(self) -> None:
        """Message should contain the URL and reason."""
        exc = NetworkError(url="https://example.com", reason="timeout")
        assert "https://example.com" in exc.message
        assert "timeout" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = NetworkError(url="https://example.com", reason="timeout")
        assert exc.url == "https://example.com"
        assert exc.reason == "timeout"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise NetworkError("https://example.com", "timeout")


class TestChecksumMismatchError:
    """Tests for ChecksumMismatchError."""

    def test_message_truncates_to_16_chars(self) -> None:
        """Message should truncate expected and actual to 16 chars."""
        long_expected = "a" * 64
        long_actual = "b" * 64
        exc = ChecksumMismatchError(
            filename="chrome.zip", expected=long_expected, actual=long_actual
        )
        assert "aaaaaaaaaaaaaaaa..." in exc.message
        assert "bbbbbbbbbbbbbbbb..." in exc.message

    def test_message_contains_filename(self) -> None:
        """Message should contain the filename."""
        exc = ChecksumMismatchError(filename="chrome.zip", expected="abc", actual="def")
        assert "chrome.zip" in exc.message

    def test_attributes_stored_untruncated(self) -> None:
        """Attributes should store the full values, not truncated."""
        long_expected = "a" * 64
        long_actual = "b" * 64
        exc = ChecksumMismatchError(
            filename="chrome.zip", expected=long_expected, actual=long_actual
        )
        assert exc.expected == long_expected
        assert exc.actual == long_actual
        assert exc.filename == "chrome.zip"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise ChecksumMismatchError("file.zip", "abc", "def")


class TestAlreadyInstalledError:
    """Tests for AlreadyInstalledError."""

    def test_message_contains_name_and_version(self) -> None:
        """Message should contain the name and version."""
        exc = AlreadyInstalledError(name="chrome", version="131.0")
        assert "chrome" in exc.message
        assert "131.0" in exc.message
        assert "--force" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = AlreadyInstalledError(name="chrome", version="131.0")
        assert exc.name == "chrome"
        assert exc.version == "131.0"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise AlreadyInstalledError("chrome", "131.0")


class TestDriverMatchError:
    """Tests for DriverMatchError."""

    def test_message_contains_driver_and_browser(self) -> None:
        """Message should contain the driver and browser names."""
        exc = DriverMatchError(driver="chromedriver", browser="chrome")
        assert "chromedriver" in exc.message
        assert "chrome" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = DriverMatchError(driver="geckodriver", browser="firefox")
        assert exc.driver == "geckodriver"
        assert exc.browser == "firefox"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise DriverMatchError("chromedriver", "chrome")


class TestUnknownTargetError:
    """Tests for UnknownTargetError."""

    def test_message_contains_target(self) -> None:
        """Message should contain the unknown target name."""
        exc = UnknownTargetError(target="safari")
        assert "safari" in exc.message

    def test_message_lists_supported_targets(self) -> None:
        """Message should list all supported targets."""
        exc = UnknownTargetError(target="safari")
        assert "chrome" in exc.message
        assert "firefox" in exc.message
        assert "edge" in exc.message
        assert "chromedriver" in exc.message
        assert "geckodriver" in exc.message
        assert "edgedriver" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = UnknownTargetError(target="safari")
        assert exc.target == "safari"

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise UnknownTargetError("safari")


class TestInsufficientDiskSpaceError:
    """Tests for InsufficientDiskSpaceError."""

    def test_message_contains_required_and_available(self) -> None:
        """Message should contain required and available MB values."""
        exc = InsufficientDiskSpaceError(required_mb=200, available_mb=50)
        assert "200" in exc.message
        assert "50" in exc.message

    def test_attributes_stored(self) -> None:
        """Constructor should store all parameters."""
        exc = InsufficientDiskSpaceError(required_mb=500, available_mb=100)
        assert exc.required_mb == 500
        assert exc.available_mb == 100

    def test_catchable_by_browserget_error(self) -> None:
        """Should be catchable by BrowsergetError."""
        with pytest.raises(BrowsergetError):
            raise InsufficientDiskSpaceError(200, 50)
