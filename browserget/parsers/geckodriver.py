"""GeckoDriver GitHub releases parser."""

from __future__ import annotations

from browserget.models import ResolvedVersion
from browserget.parsers import version_tuple

_ASSET_PLATFORM_MAP: dict[str, str] = {
    "win64": "win64.zip",
    "win32": "win32.zip",
    "mac-arm64": "macos-aarch64.tar.gz",
    "mac-x64": "macos.tar.gz",
    "macos": "macos.tar.gz",
    "linux64": "linux64.tar.gz",
}


def parse_releases(json_data: list[dict[str, object]], platform: str) -> list[ResolvedVersion]:
    """Parse GitHub releases JSON into a list of ``ResolvedVersion``.

    Args:
        json_data: List of GitHub release dictionaries with ``tag_name``
            and ``assets`` keys.
        platform: Platform string (e.g. ``"win64"``, ``"mac-arm64"``,
            ``"linux64"``).

    Returns:
        A list of ``ResolvedVersion`` sorted by version descending.
    """
    asset_suffix = _ASSET_PLATFORM_MAP.get(platform, "")
    if not asset_suffix:
        return []

    if not isinstance(json_data, list):
        return []

    results: list[ResolvedVersion] = []
    for release in json_data:
        if not isinstance(release, dict):
            continue
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str):
            continue
        clean_version = tag_name.removeprefix("v")

        assets = release.get("assets")
        if not isinstance(assets, list):
            continue

        download_url: str | None = None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_name = asset.get("name")
            if not isinstance(asset_name, str):
                continue
            if asset_name.endswith(asset_suffix):
                url = asset.get("browser_download_url")
                if isinstance(url, str):
                    download_url = url
                    break

        if download_url is None:
            continue

        results.append(
            ResolvedVersion(
                name="geckodriver",
                version=clean_version,
                url=download_url,
                platform=platform,
                checksum=None,
                checksum_algorithm=None,
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
    """Find an exact version match, handling optional ``v`` prefix.

    Args:
        versions: List of resolved versions.
        version: Version string to find (with or without ``v`` prefix).

    Returns:
        The matching ``ResolvedVersion``, or ``None`` if not found.
    """
    clean = version.removeprefix("v")
    for v in versions:
        if v.version == clean:
            return v
    return None
