"""Edge browser and EdgeDriver installers."""

from __future__ import annotations

import asyncio
import logging
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from browserget.archive import extract_zip, find_file_by_name
from browserget.cache import (
    check_disk_space,
    get_artifact_dir,
    get_available_disk_mb,
    get_download_dir,
    safe_download_path,
    safe_rmtree,
)
from browserget.checksum import verify_or_raise
from browserget.exceptions import (
    AlreadyInstalledError,
    DriverMatchError,
    InsufficientDiskSpaceError,
    UnsupportedPlatformError,
    VersionNotFoundError,
)
from browserget.installers.base import AbstractBrowserInstaller, AbstractDriverInstaller
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.parsers.edge import (
    EDGEDRIVER_LATEST_URL,
    build_edgedriver_url,
    find_by_milestone,
    find_latest,
    find_version,
    parse_versions,
)
from browserget.platform import detect_platform, map_platform
from browserget.system import SystemDetector

logger = logging.getLogger(__name__)

EDGE_API_URL = "https://edgeupdates.microsoft.com/api/products"

_EDGE_SIZE_MB = 200
_EDGEDRIVER_SIZE_MB = 10


class EdgeInstaller(AbstractBrowserInstaller):
    """Installer for Microsoft Edge browser.

    On Windows, Edge is pre-installed and cannot be installed standalone
    via MSI. This installer detects the system Edge and registers it.
    On macOS and Linux, it attempts system detection first, then falls
    back to package download if needed.
    """

    @property
    def name(self) -> str:
        """The artifact name."""
        return "edge"

    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve an Edge version from the Edge API.

        Args:
            version: Exact version string, milestone number, or ``None``
                for the latest.

        Returns:
            A resolved version with download URL and checksum.

        Raises:
            VersionNotFoundError: If the requested version is not found.
            NetworkError: If the Edge API cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "edge")

        data = await self._http.get_json(EDGE_API_URL)
        versions = parse_versions(data, "edge", platform_str)

        if not versions:
            raise VersionNotFoundError(
                version=version or "latest", name="edge", top_3_versions="none"
            )

        resolved: ResolvedVersion | None = None
        if version is None:
            resolved = find_latest(versions)
        elif version.isdigit():
            resolved = find_by_milestone(versions, int(version))
        else:
            resolved = find_version(versions, version)

        if resolved is None:
            top_3 = ", ".join(v.version for v in versions[:3])
            raise VersionNotFoundError(
                version=version or "latest", name="edge", top_3_versions=top_3
            )

        return resolved

    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Install Edge browser.

        On Windows, Edge is pre-installed — this method detects and registers
        the system Edge. On macOS/Linux, it checks for system Edge first,
        then falls back to package installation.

        Args:
            resolved: The resolved version to install.
            force: If True, re-register even if already present.

        Returns:
            The installed artifact record.

        Raises:
            AlreadyInstalledError: If already installed and ``force`` is False.
            RuntimeError: On Windows if Edge is not installed on the system.
        """
        existing = self._registry.find(self.name, resolved.version)
        if existing is not None and not force:
            raise AlreadyInstalledError(name=self.name, version=resolved.version)

        if sys.platform == "win32":
            installed = await self._install_windows(resolved, force)
        elif sys.platform == "darwin":
            installed = await self._install_macos(resolved, force)
        else:
            installed = await self._install_linux(resolved, force)

        if force:
            # Remove ALL existing entries for Edge, not just the one matching
            # resolved.version.  The system Edge version may differ from the
            # resolved version (e.g. due to auto-updates), leaving stale
            # entries under old versions that no longer reflect reality.
            # This is done AFTER the installation succeeds to avoid losing
            # registry entries if the installation fails.
            for art in self._registry.get(self.name):
                if art.version != installed.version:
                    self._registry.remove(self.name, art.version)

        return installed

    async def _install_windows(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Install Edge on Windows by detecting the pre-installed system Edge.

        Args:
            resolved: The resolved version (used for registry metadata).
            force: If True, re-register even if already present.

        Returns:
            The installed artifact record pointing to the system Edge.

        Raises:
            RuntimeError: If Edge is not installed on the system.
        """
        detector = SystemDetector()
        system_edge = detector.detect_edge()

        if system_edge is None:
            raise RuntimeError(
                "Edge is not installed on this system. "
                "Edge MSI cannot be installed standalone. "
                "Please install Microsoft Edge from https://www.microsoft.com/edge"
            )

        logger.info("Using system Edge at %s", system_edge.path)
        version = system_edge.version or resolved.version

        installed = InstalledArtifact(
            name=self.name,
            version=version,
            path=system_edge.path,
            installed_at=datetime.now(UTC),
            checksum=None,
        )
        self._registry.add(installed)
        return installed

    async def _install_macos(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Install Edge on macOS.

        Checks for system Edge first. If not found, downloads and installs
        the ``.pkg`` package via the ``installer`` command.

        Args:
            resolved: The resolved version to install.
            force: If True, reinstall even if already present.

        Returns:
            The installed artifact record.
        """
        detector = SystemDetector()
        system_edge = detector.detect_edge()

        if system_edge is not None:
            logger.info("Using system Edge at %s", system_edge.path)
            version = system_edge.version or resolved.version
            installed = InstalledArtifact(
                name=self.name,
                version=version,
                path=system_edge.path,
                installed_at=datetime.now(UTC),
                checksum=None,
            )
            self._registry.add(installed)
            return installed

        if not check_disk_space(_EDGE_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_EDGE_SIZE_MB, available_mb=get_available_disk_mb()
            )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading edge %s...", resolved.version)
        await self._http.download(resolved.url, archive_path)

        try:
            if resolved.checksum is not None and resolved.checksum_algorithm is not None:
                logger.info("Verifying checksum...")
                verify_or_raise(archive_path, resolved.checksum, resolved.checksum_algorithm)

            logger.info("Installing Edge package...")
            result = await asyncio.to_thread(
                subprocess.run,
                ["sudo", "installer", "-pkg", str(archive_path), "-target", "/"],
                capture_output=True,
                text=True,
                timeout=120,
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(f"Edge package installation failed: {result.stderr}")

            edge_path = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
            installed = InstalledArtifact(
                name=self.name,
                version=resolved.version,
                path=edge_path,
                installed_at=datetime.now(UTC),
                checksum=resolved.checksum,
            )
            self._registry.add(installed)
            logger.info("Installed to %s", edge_path)
            return installed
        finally:
            archive_path.unlink(missing_ok=True)

    async def _install_linux(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Install Edge on Linux.

        Checks for system Edge first. If not found, downloads and installs
        the appropriate package format (``.deb`` or ``.rpm``).

        Args:
            resolved: The resolved version to install.
            force: If True, reinstall even if already present.

        Returns:
            The installed artifact record.
        """
        detector = SystemDetector()
        system_edge = detector.detect_edge()

        if system_edge is not None:
            logger.info("Using system Edge at %s", system_edge.path)
            version = system_edge.version or resolved.version
            installed = InstalledArtifact(
                name=self.name,
                version=version,
                path=system_edge.path,
                installed_at=datetime.now(UTC),
                checksum=None,
            )
            self._registry.add(installed)
            return installed

        if not check_disk_space(_EDGE_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_EDGE_SIZE_MB, available_mb=get_available_disk_mb()
            )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading edge %s...", resolved.version)
        await self._http.download(resolved.url, archive_path)

        try:
            if resolved.checksum is not None and resolved.checksum_algorithm is not None:
                logger.info("Verifying checksum...")
                verify_or_raise(archive_path, resolved.checksum, resolved.checksum_algorithm)

            is_debian = Path("/etc/debian_version").exists()
            if not is_debian and not Path("/etc/redhat-release").exists():
                logger.warning("Cannot detect Linux distribution, defaulting to .deb package")
                is_debian = True

            logger.info("Installing Edge package...")
            if is_debian:
                cmd = ["sudo", "dpkg", "-i", str(archive_path)]
            else:
                cmd = ["sudo", "rpm", "-i", str(archive_path)]

            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=120, errors="replace"
            )
            if result.returncode != 0:
                raise RuntimeError(f"Edge package installation failed: {result.stderr}")

            edge_path = Path("/usr/bin/microsoft-edge")
            installed = InstalledArtifact(
                name=self.name,
                version=resolved.version,
                path=edge_path,
                installed_at=datetime.now(UTC),
                checksum=resolved.checksum,
            )
            self._registry.add(installed)
            logger.info("Installed to %s", edge_path)
            return installed
        finally:
            archive_path.unlink(missing_ok=True)


class EdgeDriverInstaller(AbstractDriverInstaller):
    """Installer for Microsoft EdgeDriver."""

    @property
    def name(self) -> str:
        """The artifact name."""
        return "edgedriver"

    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve an EdgeDriver version from the CDN.

        EdgeDriver is not available through the Edge Updates API.  Instead,
        we fetch the latest stable version string from the CDN's
        ``LATEST_STABLE`` endpoint and build a download URL from it.

        Args:
            version: Exact version string, or ``None`` for the latest stable.
                Milestone numbers are not supported for EdgeDriver because
                the CDN does not expose a version list.

        Returns:
            A resolved version with download URL.  No checksum is available.

        Raises:
            VersionNotFoundError: If the requested version is not found.
            NetworkError: If the CDN cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "edgedriver")

        if version is None:
            text = await self._http.get_text(EDGEDRIVER_LATEST_URL)
            version = text.strip()
            if not version:
                raise VersionNotFoundError(
                    version="latest", name="edgedriver", top_3_versions="none"
                )

        url = build_edgedriver_url(version, platform_str)
        return ResolvedVersion(
            name="edgedriver",
            version=version,
            url=url,
            platform=platform_str,
            checksum=None,
            checksum_algorithm=None,
        )

    async def match_browser(self, browser_version: str) -> ResolvedVersion:
        """Find an EdgeDriver version matching an installed Edge version.

        Uses the exact browser version string to build a CDN URL.
        The EdgeDriver CDN serves specific versions, so an exact match
        is the only reliable strategy.

        Args:
            browser_version: The Edge browser version to match against.

        Returns:
            A resolved EdgeDriver version.

        Raises:
            DriverMatchError: If the version is invalid.
        """
        if not browser_version:
            raise DriverMatchError(driver="edgedriver", browser="edge")

        platform = detect_platform()
        platform_str = map_platform(platform, "edgedriver")

        try:
            url = build_edgedriver_url(browser_version, platform_str)
        except UnsupportedPlatformError as exc:
            raise DriverMatchError(driver="edgedriver", browser="edge") from exc

        return ResolvedVersion(
            name="edgedriver",
            version=browser_version,
            url=url,
            platform=platform_str,
            checksum=None,
            checksum_algorithm=None,
        )

    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, verify, and install a resolved EdgeDriver version.

        EdgeDriver is distributed as a zip archive and works on all platforms.

        Args:
            resolved: The resolved version to install.
            force: If True, reinstall even if already present.

        Returns:
            The installed artifact record.

        Raises:
            AlreadyInstalledError: If already installed and ``force`` is False.
            InsufficientDiskSpaceError: If there is not enough disk space.
        """
        existing = self._registry.find(self.name, resolved.version)
        if existing is not None and not force:
            raise AlreadyInstalledError(name=self.name, version=resolved.version)

        if not check_disk_space(_EDGEDRIVER_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_EDGEDRIVER_SIZE_MB, available_mb=get_available_disk_mb()
            )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading edgedriver %s...", resolved.version)
        await self._http.download(resolved.url, archive_path)

        try:
            if resolved.checksum is not None and resolved.checksum_algorithm is not None:
                logger.info("Verifying checksum...")
                verify_or_raise(archive_path, resolved.checksum, resolved.checksum_algorithm)

            artifact_dir = get_artifact_dir(self.name, resolved.version)
            if artifact_dir.exists():
                safe_rmtree(artifact_dir)
            artifact_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Extracting...")
            await asyncio.to_thread(extract_zip, archive_path, artifact_dir)

            binary_path = self._find_binary(artifact_dir)
            if binary_path is None:
                raise RuntimeError(
                    f"EdgeDriver binary not found in extracted archive at {artifact_dir}"
                )

            if os.name != "nt":
                current = binary_path.stat().st_mode
                binary_path.chmod(current | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            installed = InstalledArtifact(
                name=self.name,
                version=resolved.version,
                path=binary_path,
                installed_at=datetime.now(UTC),
                checksum=resolved.checksum,
            )
            self._registry.add(installed)

            logger.info("Installed to %s", binary_path)
            return installed
        finally:
            archive_path.unlink(missing_ok=True)

    @staticmethod
    def _find_binary(artifact_dir: Path) -> Path | None:
        """Find the EdgeDriver executable in the extracted artifact directory.

        Args:
            artifact_dir: Root directory of the extracted archive.

        Returns:
            Path to the driver binary, or ``None`` if not found.
        """
        binary_name = "msedgedriver.exe" if os.name == "nt" else "msedgedriver"

        candidate = artifact_dir / binary_name
        if candidate.exists():
            return candidate

        return find_file_by_name(artifact_dir, binary_name)
