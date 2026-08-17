"""Upstream API parsers for version resolution."""

from __future__ import annotations


def version_tuple(version: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison.

    Non-numeric segments are treated as 0.

    Args:
        version: Version string (e.g. "131.0.6778.87").

    Returns:
        Tuple of integers (e.g. (131, 0, 6778, 87)).
    """
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)
