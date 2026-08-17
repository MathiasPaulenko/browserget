"""Firefox browser installer via Mozilla FTP."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import stat
import subprocess
import sys
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
from browserget.checksum import verify_or_raise
from browserget.exceptions import (
    AlreadyInstalledError,
    InsufficientDiskSpaceError,
    NetworkError,
    VersionNotFoundError,
)
from browserget.installers.base import AbstractBrowserInstaller
from browserget.models import InstalledArtifact, ResolvedVersion
from browserget.parsers.firefox import (
    build_checksum_url,
    build_download_url,
    find_latest,
    parse_releases,
)
from browserget.platform import detect_platform, map_platform

logger = logging.getLogger(__name__)

FIREFOX_FTP_URL = "https://ftp.mozilla.org/pub/firefox/releases/"

_FIREFOX_SIZE_MB = 200


class FirefoxInstaller(AbstractBrowserInstaller):
    """Installer for Firefox browser via Mozilla FTP."""

    @property
    def name(self) -> str:
        """The artifact name."""
        return "firefox"

    async def resolve(self, version: str | None) -> ResolvedVersion:
        """Resolve a Firefox version from the Mozilla FTP listing.

        Args:
            version: Exact version string, or ``None`` for the latest.

        Returns:
            A resolved version with download URL and checksum.

        Raises:
            VersionNotFoundError: If the requested version is not found.
            NetworkError: If the FTP listing cannot be reached.
        """
        platform = detect_platform()
        platform_str = map_platform(platform, "firefox")

        html = await self._http.get_text(FIREFOX_FTP_URL)
        versions = parse_releases(html)

        if not versions:
            raise VersionNotFoundError(
                version=version or "latest", name="firefox", top_3_versions="none"
            )

        target_version: str | None = None
        if version is None:
            target_version = find_latest(versions)
        elif version in versions:
            target_version = version
        else:
            for v in versions:
                if v.lower().removesuffix("esr") == version.lower().removesuffix("esr"):
                    target_version = v
                    break

        if target_version is None:
            top_3 = ", ".join(versions[:3])
            raise VersionNotFoundError(
                version=version or "latest", name="firefox", top_3_versions=top_3
            )

        download_url = build_download_url(target_version, platform_str)

        checksum: str | None = None
        checksum_algorithm: str | None = None
        checksum_url = build_checksum_url(target_version, platform_str)
        if checksum_url is not None:
            try:
                checksums_text = await self._http.get_text(checksum_url)
                # SHA512SUMS paths are relative to the release root,
                # e.g. "linux-x86_64/en-US/firefox-128.0.tar.bz2".
                # Extract the relative path from the download URL for matching.
                prefix = f"releases/{target_version}/"
                expected_path = (
                    download_url.split(prefix, 1)[1]
                    if prefix in download_url
                    else download_url.split("/")[-1]
                )
                checksum = self._parse_checksums(checksums_text, expected_path)
                if checksum is not None:
                    checksum_algorithm = "sha512"
            except NetworkError:
                pass

        return ResolvedVersion(
            name="firefox",
            version=target_version,
            url=download_url,
            platform=platform_str,
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
        )

    async def install(self, resolved: ResolvedVersion, force: bool) -> InstalledArtifact:
        """Download, verify, and install a resolved Firefox version.

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

        if not check_disk_space(_FIREFOX_SIZE_MB):
            raise InsufficientDiskSpaceError(
                required_mb=_FIREFOX_SIZE_MB, available_mb=get_available_disk_mb()
            )

        download_dir = get_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_name = resolved.url.split("/")[-1]
        archive_path = safe_download_path(download_dir, archive_name)

        logger.info("Downloading firefox %s...", resolved.version)
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
            if archive_path.suffix == ".exe":
                await asyncio.to_thread(self._extract_exe, archive_path, artifact_dir)
            elif archive_path.suffix == ".dmg":
                await asyncio.to_thread(self._extract_dmg, archive_path, artifact_dir)
            elif ".tar" in archive_path.name:
                await asyncio.to_thread(extract_tar, archive_path, artifact_dir)
            else:
                await asyncio.to_thread(extract_zip, archive_path, artifact_dir)

            binary_path = self._find_binary(artifact_dir)
            if binary_path is None:
                raise RuntimeError(
                    f"Firefox binary not found in extracted archive at {artifact_dir}"
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
    def _parse_checksums(text: str, expected_path: str | None = None) -> str | None:
        """Parse a Mozilla ``SHA512SUMS`` file for the SHA-512 hash.

        The file format is lines of: ``<hash>  <relative_path>``.
        The algorithm is implied by the file name (SHA512SUMS → sha512).

        When ``expected_path`` is provided, only entries whose path matches
        are considered. Otherwise the first entry is returned.

        Args:
            text: Raw SHA512SUMS file content.
            expected_path: The relative path to match (e.g.
                ``linux-x86_64/en-US/firefox-128.0.tar.bz2``).

        Returns:
            The SHA-512 hash string, or ``None`` if not found.
        """
        for line in text.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                hash_value, path = parts
                if expected_path is None:
                    return hash_value
                if path == expected_path:
                    return hash_value
        return None

    @staticmethod
    def _extract_exe(archive_path: Path, dest: Path) -> None:
        """Extract a Firefox self-extracting installer on Windows.

        Uses 7-Zip if available, otherwise attempts silent install.

        Args:
            archive_path: Path to the .exe installer.
            dest: Destination directory.

        Raises:
            RuntimeError: If extraction fails.
        """
        seven_zip = shutil.which("7z")
        if seven_zip is not None:
            result = subprocess.run(
                [seven_zip, "x", str(archive_path), f"-o{dest}", "-y"],
                capture_output=True,
                text=True,
                timeout=120,
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(f"7-Zip extraction failed: {result.stderr}")
            return
        try:
            extract_zip(archive_path, dest)
        except Exception as exc:
            raise RuntimeError(
                "Cannot extract Firefox .exe without 7-Zip. "
                "Install 7-Zip or use a different platform."
            ) from exc

    @staticmethod
    def _extract_dmg(archive_path: Path, dest: Path) -> None:
        """Mount and copy a macOS DMG.

        Uses ``hdiutil`` to mount the DMG, copies the Firefox.app bundle,
        then unmounts.

        Args:
            archive_path: Path to the .dmg file.
            dest: Destination directory.

        Raises:
            RuntimeError: If mounting or copying fails.
        """
        mount_point = dest / ".dmg_mount"
        mount_point.mkdir(exist_ok=True)
        try:
            result = subprocess.run(
                ["hdiutil", "attach", str(archive_path), "-mountpoint", str(mount_point)],
                capture_output=True,
                text=True,
                timeout=60,
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to mount DMG: {result.stderr}. "
                    "Check that the file is a valid Firefox DMG."
                )
            try:
                app_source = mount_point / "Firefox.app"
                if app_source.exists():
                    shutil.copytree(app_source, dest / "Firefox.app")
                else:
                    for item in mount_point.iterdir():
                        if item.suffix == ".app":
                            shutil.copytree(item, dest / item.name)
                            break
            finally:
                subprocess.run(
                    ["hdiutil", "detach", str(mount_point)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    errors="replace",
                )
        finally:
            if mount_point.exists():
                shutil.rmtree(mount_point, ignore_errors=True)

    @staticmethod
    def _find_binary(artifact_dir: Path) -> Path | None:
        """Find the Firefox executable in the extracted artifact directory.

        Args:
            artifact_dir: Root directory of the extracted archive.

        Returns:
            Path to the browser binary, or ``None`` if not found.
        """
        if os.name == "nt":
            binary_name = "firefox.exe"
        elif sys.platform == "darwin":
            binary_name = "Firefox.app/Contents/MacOS/firefox"
        else:
            binary_name = "firefox"

        candidate = artifact_dir / binary_name
        if candidate.exists():
            return candidate

        return find_file_by_name(artifact_dir, Path(binary_name).name)
