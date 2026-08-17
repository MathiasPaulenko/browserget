"""Firefox FTP directory listing parser."""

from __future__ import annotations

import re

from browserget.parsers import version_tuple

_PLATFORM_PATHS: dict[str, str] = {
    "win64": "win64",
    "win32": "win32",
    "mac": "mac",
    "mac-arm64": "mac",
    "mac-x64": "mac",
    "os": "mac",
    "linux64": "linux-x86_64",
    "linux-x86_64": "linux-x86_64",
}

_VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)*(?:esr)?")


def _firefox_version_tuple(version: str) -> tuple[int, ...]:
    """Parse a Firefox version string, stripping the ``esr`` suffix.

    The ESR suffix is matched case-insensitively so that ``115.0esr``,
    ``115.0ESR``, and ``115.0Esr`` all parse identically.
    """
    lower = version.lower()
    stripped = version[: -len("esr")] if lower.endswith("esr") else version
    return version_tuple(stripped)


def parse_releases(html: str) -> list[str]:
    """Scrape a Mozilla FTP directory listing HTML for version strings.

    Extracts version-like directory names from ``<a href>`` tags, filtering
    out non-version entries such as ``latest/``, ``releases/``, and parent
    directory links.

    Args:
        html: Raw HTML from the FTP directory listing.

    Returns:
        A list of version strings (e.g. ``["131.0", "130.0.1"]``).
    """
    href_pattern = re.compile(r'href="([^"]+)"')
    matches = href_pattern.findall(html)

    versions: list[str] = []
    seen: set[str] = set()
    for match in matches:
        name = match.rstrip("/")
        name = name.split("/")[-1]
        if not name:
            continue
        if name in ("..", ".", "latest", "releases", "contrib", "partner-repacks"):
            continue
        if _VERSION_PATTERN.match(name) and name not in seen:
            versions.append(name)
            seen.add(name)
    return versions


def find_latest(versions: list[str]) -> str | None:
    """Return the highest version from a list of version strings.

    Args:
        versions: List of version strings.

    Returns:
        The highest version string, or ``None`` if the list is empty.
    """
    if not versions:
        return None
    return max(versions, key=_firefox_version_tuple)


def build_download_url(version: str, platform: str) -> str:
    """Build the Firefox download URL for a version and platform.

    Args:
        version: Firefox version string (e.g. "131.0").
        platform: Platform string (e.g. "win64", "mac", "linux64").

    Returns:
        The full download URL for the Firefox archive.
    """
    base = f"https://ftp.mozilla.org/pub/firefox/releases/{version}"
    platform_path = _PLATFORM_PATHS.get(platform, platform)
    if platform_path.startswith("win"):
        return f"{base}/{platform_path}/en-US/Firefox Setup {version}.exe"
    if platform_path.startswith("mac"):
        return f"{base}/{platform_path}/en-US/Firefox {version}.dmg"
    return f"{base}/{platform_path}/en-US/firefox-{version}.tar.bz2"


def build_checksum_url(version: str, platform: str) -> str | None:
    """Build the URL for the Firefox ``SHA512SUMS`` file.

    Mozilla publishes checksums at the release root as ``SHA512SUMS``,
    not in per-platform directories.  The file contains lines of
    ``<hash>  <relative_path>`` for all platforms and locales.

    Args:
        version: Firefox version string.
        platform: Platform string (unused, kept for API compatibility).

    Returns:
        The SHA512SUMS file URL, or ``None`` if the version is empty.
    """
    if not version:
        return None
    return f"https://ftp.mozilla.org/pub/firefox/releases/{version}/SHA512SUMS"
