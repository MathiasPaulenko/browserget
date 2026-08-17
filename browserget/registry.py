"""JSON registry of installed artifacts with atomic writes."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from browserget.exceptions import VersionNotFoundError
from browserget.models import InstalledArtifact

logger = logging.getLogger(__name__)


class Registry:
    """Persistent registry of installed artifacts backed by a JSON file.

    The registry file is located at ``{cache_dir}/registry.json`` and uses
    atomic writes (write to temp, then ``os.replace``).

    Attributes:
        cache_dir: The cache directory containing the registry file.
        registry_path: The full path to the registry JSON file.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.registry_path = cache_dir / "registry.json"

    def load(self) -> dict[str, list[InstalledArtifact]]:
        """Load the registry from disk.

        Returns an empty dictionary if the registry file does not exist or
        contains corrupted JSON (a warning is logged in the latter case).

        Returns:
            A mapping of artifact name to lists of installed artifacts.
        """
        if not self.registry_path.exists():
            return {}
        try:
            raw = self.registry_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupted registry file %s: %s", self.registry_path, exc)
            return {}

        if not isinstance(data, dict):
            logger.warning("Registry root is not a JSON object, ignoring")
            return {}

        result: dict[str, list[InstalledArtifact]] = {}
        for name, entries in data.items():
            if not isinstance(entries, list):
                continue
            artifacts: list[InstalledArtifact] = []
            for e in entries:
                if not isinstance(e, dict):
                    logger.warning("Skipping non-object entry in registry for %s", name)
                    continue
                try:
                    artifacts.append(InstalledArtifact.from_dict(e))
                except (ValueError, KeyError, TypeError) as exc:
                    logger.warning("Skipping corrupted entry in registry for %s: %s", name, exc)
                    continue
            result[name] = artifacts
        return result

    def save(self, data: dict[str, list[InstalledArtifact]]) -> None:
        """Save the registry to disk atomically.

        Writes to a temporary file first, then renames it to the registry
        path using ``os.replace`` (atomic on all platforms).

        Args:
            data: The registry data to write.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        serializable: dict[str, list[dict[str, str | None]]] = {
            name: [a.to_dict() for a in artifacts] for name, artifacts in data.items()
        }
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".tmp",
                dir=self.cache_dir,
                delete=False,
                encoding="utf-8",
            ) as tmp:
                tmp_path = Path(tmp.name)
                json.dump(serializable, tmp, indent=2)
            os.replace(tmp_path, self.registry_path)
        except Exception:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            raise

    def add(self, artifact: InstalledArtifact) -> None:
        """Add or replace an artifact in the registry.

        If an artifact with the same name and version already exists, it is
        replaced rather than duplicated.

        Args:
            artifact: The artifact to add or update.
        """
        data = self.load()
        entries = data.get(artifact.name, [])
        entries = [
            e for e in entries if not (e.name == artifact.name and e.version == artifact.version)
        ]
        entries.append(artifact)
        data[artifact.name] = entries
        self.save(data)

    def remove(self, name: str, version: str) -> None:
        """Remove an artifact from the registry.

        Args:
            name: Artifact name.
            version: Artifact version.

        Raises:
            VersionNotFoundError: If no artifact with the given name and
                version exists in the registry.
        """
        data = self.load()
        entries = data.get(name, [])
        filtered = [e for e in entries if e.version != version]
        if len(filtered) == len(entries):
            raise VersionNotFoundError(
                version=version,
                name=name,
                top_3_versions=", ".join(e.version for e in entries[:3]) or "none",
            )
        if filtered:
            data[name] = filtered
        else:
            data.pop(name, None)
        self.save(data)

    def get(self, name: str) -> list[InstalledArtifact]:
        """Return all installed versions of a target.

        Args:
            name: Artifact name.

        Returns:
            A list of installed artifacts with the given name (empty if none).
        """
        return self.load().get(name, [])

    def find(self, name: str, version: str | None = None) -> InstalledArtifact | None:
        """Find a specific artifact or the most recently installed one.

        Args:
            name: Artifact name.
            version: Exact version to find, or None to return the most
                recently installed (by ``installed_at``).

        Returns:
            The matching artifact, or None if not found.
        """
        entries = self.get(name)
        if not entries:
            return None
        if version is not None:
            for e in entries:
                if e.version == version:
                    return e
            return None
        try:
            return max(entries, key=lambda e: e.installed_at)
        except TypeError:
            return entries[0]

    def list_all(self) -> dict[str, list[InstalledArtifact]]:
        """Return the entire registry contents.

        Returns:
            A mapping of artifact name to lists of installed artifacts.
        """
        return self.load()
