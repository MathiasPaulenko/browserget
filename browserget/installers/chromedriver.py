"""ChromeDriver installer using the CfT API."""

from __future__ import annotations

import asyncio
import logging
import os
import stat
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
    VersionNotFoundError,
)
from browserget.installers.base import AbstractDriverInstaller
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.parsers.cft import (
    find_by_milestone,
    find_latest,
    find_version,
    parse_versions,
)
from browserget.platform import detect_platform, map_platform

logger = logging.getLogger(__name__)

CFT_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
)

_CHROMEDRIVER_SIZE_MB = 10


class ChromeDriverInstaller(AbstractDriverInstaller):
    """Installer for ChromeDriver via the CfT API."""

    @property
    def name(self) -> str:
        """The artifact name."""
        return "chromedriver"

    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve a ChromeDriver version from the CfT API.

        Args:
            version: Exact version string, milestone number, or ``None``
                for the latest stable version.

        Returns:
            A resolved version with download URL and checksum.

        Raises:
            VersionNotFoundError: If the requested version is not found.
            NetworkError: If the CfT API cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "cft")

        data = await self._http.get_json(CFT_URL)
        versions = parse_versions(data, "chromedriver", platform_str)

        if not versions:
            raise VersionNotFoundError(
                version=version or "latest", name="chromedriver", top_3_versions="none"
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
                version=version or "latest", name="chromedriver", top_3_versions=top_3
            )

        return resolved

    async def match_browser(self, browser_version: str) -> ResolvedVersion:
        """Find a ChromeDriver version matching an installed Chrome version.

        Tries an exact version match first, then falls back to the highest
        driver with the same major version (milestone).

        Args:
            browser_version: The Chrome browser version to match against.

        Returns:
            A resolved ChromeDriver version.

        Raises:
            DriverMatchError: If no matching ChromeDriver is found.
            NetworkError: If the CfT API cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "cft")

        data = await self._http.get_json(CFT_URL)
        versions = parse_versions(data, "chromedriver", platform_str)

        exact = find_version(versions, browser_version)
        if exact is not None:
            return exact

        milestone_str = browser_version.split(".")[0]
        if milestone_str.isdigit():
            by_milestone = find_by_milestone(versions, int(milestone_str))
            if by_milestone is not None:
                return by_milestone

        raise DriverMatchError(driver="chromedriver", browser="chrome")

    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, verify, and install a resolved ChromeDriver version.

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

        if not check_disk_space(_CHROMEDRIVER_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_CHROMEDRIVER_SIZE_MB, available_mb=get_available_disk_mb()
            )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading chromedriver %s...", resolved.version)
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
                    f"ChromeDriver binary not found in extracted archive at {artifact_dir}"
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
        """Find the ChromeDriver executable in the extracted artifact directory.

        Args:
            artifact_dir: Root directory of the extracted archive.

        Returns:
            Path to the driver binary, or ``None`` if not found.
        """
        binary_name = "chromedriver.exe" if os.name == "nt" else "chromedriver"

        candidate = artifact_dir / binary_name
        if candidate.exists():
            return candidate

        return find_file_by_name(artifact_dir, binary_name)
