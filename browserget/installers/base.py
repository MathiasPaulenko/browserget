"""Abstract base classes for browser and driver installers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from browserget.config import Config
from browserget.http import HttpClient
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.registry import Registry


class AbstractBrowserInstaller(ABC):
    """Abstract base class for all browser installers.

    Subclasses must implement the ``name`` property, ``resolve``, and
    ``install`` methods.

    Attributes:
        _http: HTTP client for network requests.
        _registry: Registry for installed artifacts.
        _config: Runtime configuration.
    """

    def __init__(self, http: HttpClient, registry: Registry, config: Config) -> None:
        self._http = http
        self._registry = registry
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """The artifact name (e.g. "chrome", "firefox")."""

    @abstractmethod
    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve a version string to a ``ResolvedVersion`` ready for download.

        Args:
            version: Exact version, milestone, or ``None`` for latest.

        Returns:
            A resolved version with download URL and checksum.
        """

    @abstractmethod
    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, verify, and install a resolved version.

        Args:
            resolved: The resolved version to install.
            force: If True, reinstall even if already present.

        Returns:
            The installed artifact record.
        """

    async def get_installed(self) -> list[InstalledArtifact]:
        """Return all installed versions of this browser from the registry.

        Returns:
            A list of installed artifacts for this browser.
        """
        return self._registry.get(self.name)


class AbstractDriverInstaller(ABC):
    """Abstract base class for all driver installers.

    Subclasses must implement the ``name`` property, ``resolve``,
    ``install``, and ``match_browser`` methods.

    Attributes:
        _http: HTTP client for network requests.
        _registry: Registry for installed artifacts.
        _config: Runtime configuration.
    """

    def __init__(self, http: HttpClient, registry: Registry, config: Config) -> None:
        self._http = http
        self._registry = registry
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """The artifact name (e.g. "chromedriver", "geckodriver")."""

    @abstractmethod
    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve a version string to a ``ResolvedVersion`` ready for download.

        Args:
            version: Exact version, or ``None`` for latest.

        Returns:
            A resolved version with download URL and checksum.
        """

    @abstractmethod
    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, verify, and install a resolved version.

        Args:
            resolved: The resolved version to install.
            force: If True, reinstall even if already present.

        Returns:
            The installed artifact record.
        """

    @abstractmethod
    async def match_browser(self, browser_version: str) -> ResolvedVersion:
        """Find a driver version matching an installed browser version.

        Args:
            browser_version: The browser version to match against.

        Returns:
            A resolved version for the matching driver.
        """

    async def get_installed(self) -> list[InstalledArtifact]:
        """Return all installed versions of this driver from the registry.

        Returns:
            A list of installed artifacts for this driver.
        """
        return self._registry.get(self.name)
