"""Domain models for browserget."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResolvedVersion:
    """A version resolved from an upstream API, ready to download.

    Attributes:
        name: Artifact name (e.g. "chrome", "chromedriver").
        version: Concrete version string (e.g. "131.0.6778.87").
        url: Direct download URL for the archive.
        platform: Platform string (e.g. "win64", "linux64").
        checksum: Checksum hash if the upstream provides one, otherwise None.
        checksum_algorithm: Algorithm name (e.g. "sha256") if checksum is set.
    """

    name: str
    version: str
    url: str
    platform: str
    checksum: str | None
    checksum_algorithm: str | None


@dataclass(frozen=True, slots=True)
class InstalledArtifact:
    """An artifact installed in the browserget cache.

    Attributes:
        name: Artifact name (e.g. "chrome", "chromedriver").
        version: Installed version string.
        path: Path to the installed artifact directory.
        installed_at: UTC datetime when the artifact was installed.
        checksum: Checksum hash of the downloaded archive, if available.
    """

    name: str
    version: str
    path: Path
    installed_at: datetime
    checksum: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize to a JSON-safe dictionary for registry storage.

        Returns:
            A dictionary with all fields as strings (or None).
        """
        return {
            "name": self.name,
            "version": self.version,
            "path": str(self.path),
            "installed_at": self.installed_at.isoformat(),
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> InstalledArtifact:
        """Deserialize from a registry dictionary.

        Args:
            data: Dictionary with string values as produced by ``to_dict``.

        Returns:
            A new ``InstalledArtifact`` instance.

        Raises:
            ValueError: If required fields are missing or have invalid types.
        """
        required_keys = ("name", "version", "path", "installed_at")
        for key in required_keys:
            val = data.get(key)
            if val is None:
                raise ValueError(f"Missing or null field: {key!r}")
            if not isinstance(val, str):
                raise ValueError(f"Field {key!r} must be a string, got {type(val).__name__}")

        checksum = data.get("checksum")
        if checksum is not None and not isinstance(checksum, str):
            raise ValueError(
                f"Field 'checksum' must be a string or None, got {type(checksum).__name__}"
            )

        return cls(
            name=data["name"],  # type: ignore[arg-type]
            version=data["version"],  # type: ignore[arg-type]
            path=Path(data["path"]),  # type: ignore[arg-type]
            installed_at=datetime.fromisoformat(data["installed_at"]),  # type: ignore[arg-type]
            checksum=checksum,
        )


@dataclass(frozen=True, slots=True)
class SystemBrowser:
    """A browser detected on the system (outside the browserget cache).

    Attributes:
        name: Browser name (e.g. "chrome", "firefox").
        version: Detected version string, or None if undetectable.
        path: Path to the browser executable.
    """

    name: str
    version: str | None
    path: Path
