"""Edge updates API parser and EdgeDriver CDN URL builder.

The Edge browser versions are fetched from the Microsoft Edge Updates API
at ``https://edgeupdates.microsoft.com/api/products``.

EdgeDriver is **not** available through that API.  It is distributed via a
separate CDN at ``https://msedgedriver.microsoft.com`` using predictable
version-based URLs.
"""

from __future__ import annotations

from browserget.exceptions import UnsupportedPlatformError
from browserget.models import ResolvedVersion
from browserget.parsers import version_tuple

# Maps internal platform strings to (API Platform, API Architecture) tuples
# used by the Edge Updates API.
_EDGE_PLATFORM_MAP: dict[str, tuple[str, str]] = {
    "win64": ("Windows", "x64"),
    "win32": ("Windows", "x86"),
    "mac-arm64": ("MacOS", "universal"),
    "mac-x64": ("MacOS", "universal"),
    "linux64": ("Linux", "x64"),
}

# Maps internal platform strings to EdgeDriver CDN filename components.
# macOS uses a single universal ``mac64`` binary for both ARM64 and x64.
_EDGEDRIVER_CDN_PLATFORM_MAP: dict[str, str] = {
    "win64": "win64",
    "win32": "win32",
    "mac-arm64": "mac64",
    "mac-x64": "mac64",
    "linux64": "linux64",
}

EDGEDRIVER_CDN_URL = "https://msedgedriver.microsoft.com"
EDGEDRIVER_LATEST_URL = f"{EDGEDRIVER_CDN_URL}/LATEST_STABLE"


def parse_versions(
    json_data: list[dict[str, object]], target: str, platform: str
) -> list[ResolvedVersion]:
    """Parse Edge Updates API JSON data into a list of ``ResolvedVersion``.

    The new Edge API returns an **array** of products, each with a
    ``"Releases"`` list.  Each release has ``Platform``, ``Architecture``,
    ``ProductVersion``, and ``Artifacts`` fields.

    Only the ``"Stable"`` product and the ``"edge"`` target are supported.
    EdgeDriver is not available through this API — use
    :func:`build_edgedriver_url` instead.

    Args:
        json_data: The raw Edge API JSON list.
        target: Download target name (must be ``"edge"``).
        platform: Platform string (e.g. ``"win64"``, ``"mac-arm64"``).

    Returns:
        A list of ``ResolvedVersion`` sorted by version descending.

    Raises:
        UnsupportedPlatformError: If the platform is not recognized.
    """
    if platform not in _EDGE_PLATFORM_MAP:
        raise UnsupportedPlatformError(platform=platform, name=target)

    if not isinstance(json_data, list):
        return []

    api_platform, api_arch = _EDGE_PLATFORM_MAP[platform]

    results: list[ResolvedVersion] = []
    seen_versions: set[str] = set()
    for product in json_data:
        if not isinstance(product, dict):
            continue
        product_name = product.get("Product")
        if product_name != "Stable":
            continue

        releases = product.get("Releases")
        if not isinstance(releases, list):
            continue

        for release in releases:
            if not isinstance(release, dict):
                continue
            if release.get("Platform") != api_platform:
                continue
            if release.get("Architecture") != api_arch:
                continue

            version_str = release.get("ProductVersion")
            if not isinstance(version_str, str):
                continue

            if version_str in seen_versions:
                continue

            artifacts = release.get("Artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                continue

            artifact = artifacts[0]
            if not isinstance(artifact, dict):
                continue

            url = artifact.get("Location")
            if not isinstance(url, str):
                continue

            checksum: str | None = None
            checksum_algorithm: str | None = None
            hash_value = artifact.get("Hash")
            hash_algo = artifact.get("HashAlgorithm")
            if isinstance(hash_value, str) and isinstance(hash_algo, str):
                checksum = hash_value
                checksum_algorithm = hash_algo.lower()

            seen_versions.add(version_str)
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


def build_edgedriver_url(version: str, platform: str) -> str:
    """Build an EdgeDriver download URL for the given version and platform.

    EdgeDriver is distributed via ``https://msedgedriver.microsoft.com``
    using predictable version-based URLs.  No checksums are published.

    Args:
        version: Full EdgeDriver version string (e.g. ``"131.0.2903.86"``).
        platform: Internal platform string (e.g. ``"win64"``, ``"mac-arm64"``).

    Returns:
        The full download URL for the EdgeDriver zip archive.

    Raises:
        UnsupportedPlatformError: If the platform is not recognized.
    """
    if platform not in _EDGEDRIVER_CDN_PLATFORM_MAP:
        raise UnsupportedPlatformError(platform=platform, name="edgedriver")
    cdn_platform = _EDGEDRIVER_CDN_PLATFORM_MAP[platform]
    return f"{EDGEDRIVER_CDN_URL}/{version}/edgedriver_{cdn_platform}.zip"


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
