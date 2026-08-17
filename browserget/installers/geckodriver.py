"""GeckoDriver installer via GitHub releases."""

from __future__ import annotations

import asyncio
import logging
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from browserget.archive import extract_tar, extract_zip, find_file_by_name
from browserget.cache import (
    check_disk_space,
    get_artifact_dir,
    get_available_disk_mb,
    get_download_dir,
    safe_download_path,
    safe_rmtree,
)
from browserget.exceptions import (
    AlreadyInstalledError,
    InsufficientDiskSpaceError,
    VersionNotFoundError,
)
from browserget.installers.base import AbstractDriverInstaller
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.parsers.geckodriver import find_latest, find_version, parse_releases
from browserget.platform import detect_platform, map_platform

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/mozilla/geckodriver/releases"

_GECKODRIVER_SIZE_MB = 10


class GeckoDriverInstaller(AbstractDriverInstaller):
    """Installer for GeckoDriver via GitHub releases."""

    @property
    def name(self) -> str:
        """The artifact name."""
        return "geckodriver"

    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve a GeckoDriver version from GitHub releases.

        Args:
            version: Exact version string (with or without ``v`` prefix),
                or ``None`` for the latest.

        Returns:
            A resolved version with download URL.

        Raises:
            VersionNotFoundError: If the requested version is not found.
            NetworkError: If the GitHub API cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "geckodriver")

        data = await self._http.get_json(GITHUB_API_URL)
        versions = parse_releases(data, platform_str)

        if not versions:
            raise VersionNotFoundError(
                version=version or "latest",
                name="geckodriver",
                top_3_versions="none",
            )

        resolved: ResolvedVersion | None = (
            find_latest(versions) if version is None else find_version(versions, version)
        )

        if resolved is None:
            top_3 = ", ".join(v.version for v in versions[:3])
            raise VersionNotFoundError(
                version=version or "latest",
                name="geckodriver",
                top_3_versions=top_3,
            )

        return resolved

    async def match_browser(self, browser_version: str) -> ResolvedVersion:
        """Return the latest GeckoDriver (no version matching with Firefox).

        GeckoDriver does not version-match with Firefox the way ChromeDriver
        does with Chrome. This method always returns the latest available
        GeckoDriver.

        Args:
            browser_version: The Firefox browser version (ignored).

        Returns:
            The latest resolved GeckoDriver version.

        Raises:
            VersionNotFoundError: If no GeckoDriver releases are found.
            NetworkError: If the GitHub API cannot be reached.
        """
        logger.debug("GeckoDriver does not version-match with Firefox, returning latest")
        return await self.resolve(None)

    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, extract, and install a resolved GeckoDriver version.

        No checksum verification is performed (GitHub releases don't publish
        checksums for GeckoDriver).

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

        if not check_disk_space(_GECKODRIVER_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_GECKODRIVER_SIZE_MB, available_mb=get_available_disk_mb()
            )

        logger.warning(
            "No checksum available for geckodriver %s, skipping verification",
            resolved.version,
        )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading geckodriver %s...", resolved.version)
        await self._http.download(resolved.url, archive_path)

        try:
            artifact_dir = get_artifact_dir(self.name, resolved.version)
            if artifact_dir.exists():
                safe_rmtree(artifact_dir)
            artifact_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Extracting...")
            if archive_path.suffix == ".zip":
                await asyncio.to_thread(extract_zip, archive_path, artifact_dir)
            elif ".tar" in archive_path.name:
                await asyncio.to_thread(extract_tar, archive_path, artifact_dir)
            else:
                raise RuntimeError(f"Unsupported archive format: {archive_path.name}")

            binary_path = self._find_binary(artifact_dir)
            if binary_path is None:
                raise RuntimeError(
                    f"GeckoDriver binary not found in extracted archive at {artifact_dir}"
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
        """Find the GeckoDriver executable in the extracted artifact directory.

        Args:
            artifact_dir: Root directory of the extracted archive.

        Returns:
            Path to the driver binary, or ``None`` if not found.
        """
        binary_name = "geckodriver.exe" if os.name == "nt" else "geckodriver"

        candidate = artifact_dir / binary_name
        if candidate.exists():
            return candidate

        return find_file_by_name(artifact_dir, binary_name)
