"""Chrome for Testing (CfT) JSON parser."""

from __future__ import annotations

from browserget.models import ResolvedVersion
from browserget.parsers import version_tuple


def parse_versions(
    json_data: dict[str, object], target: str, platform: str
) -> list[ResolvedVersion]:
    """Parse CfT JSON data into a list of ``ResolvedVersion`` instances.

    Args:
        json_data: The raw CfT JSON dictionary with a ``"versions"`` key.
        target: Download target name (``"chrome"`` or ``"chromedriver"``).
        platform: Platform string (e.g. ``"win64"``, ``"linux64"``).

    Returns:
        A list of ``ResolvedVersion`` sorted by version descending.
    """
    if not isinstance(json_data, dict):
        return []

    raw_versions = json_data.get("versions", [])
    if not isinstance(raw_versions, list):
        return []

    results: list[ResolvedVersion] = []
    for entry in raw_versions:
        if not isinstance(entry, dict):
            continue
        version_str = entry.get("version")
        if not isinstance(version_str, str):
            continue

        downloads = entry.get("downloads")
        if not isinstance(downloads, dict):
            continue
        target_downloads = downloads.get(target)
        if not isinstance(target_downloads, dict):
            continue
        platform_entry = target_downloads.get(platform)
        if not isinstance(platform_entry, dict):
            continue

        url = platform_entry.get("url")
        if not isinstance(url, str):
            continue

        checksums = platform_entry.get("checksums")
        checksum: str | None = None
        checksum_algorithm: str | None = None
        if isinstance(checksums, dict):
            sha256 = checksums.get("sha256")
            if isinstance(sha256, str):
                checksum = sha256
                checksum_algorithm = "sha256"

        results.append(
            ResolvedVersion(
                name=target,
                version=version_str,
                url=url,
                platform=platform,
                checksum=checksum,
                checksum_algorithm=checksum_algorithm,
            )
        )

    results.sort(key=lambda v: version_tuple(v.version), reverse=True)
    return results


def find_latest(versions: list[ResolvedVersion]) -> ResolvedVersion | None:
    """Return the highest version from a list.

    Args:
        versions: List of resolved versions (assumed sorted descending).

    Returns:
        The first (highest) version, or ``None`` if the list is empty.
    """
    if not versions:
        return None
    return versions[0]


def find_version(versions: list[ResolvedVersion], version: str) -> ResolvedVersion | None:
    """Find an exact version match in the list.

    Args:
        versions: List of resolved versions.
        version: Exact version string to find.

    Returns:
        The matching ``ResolvedVersion``, or ``None`` if not found.
    """
    for v in versions:
        if v.version == version:
            return v
    return None


def find_by_milestone(versions: list[ResolvedVersion], milestone: int) -> ResolvedVersion | None:
    """Find the highest version matching a major version milestone.

    Args:
        versions: List of resolved versions (sorted descending).
        milestone: Major version number (e.g. 131).

    Returns:
        The highest matching ``ResolvedVersion``, or ``None`` if none match.
    """
    for v in versions:
        parts = v.version.split(".")
        if parts and parts[0].isdigit() and int(parts[0]) == milestone:
            return v
    return None
