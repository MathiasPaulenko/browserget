"""Unit tests for domain models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from browserget.models import InstalledArtifact, ResolvedVersion, SystemBrowser


class TestResolvedVersion:
    """Tests for the ResolvedVersion dataclass."""

    def test_is_frozen(self, sample_resolved_version: ResolvedVersion) -> None:
        """ResolvedVersion should be frozen — mutation raises FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            sample_resolved_version.version = "999"

    def test_equality_same_fields(self) -> None:
        """Two ResolvedVersion with same fields should be equal."""
        a = ResolvedVersion(
            name="chrome",
            version="131.0",
            url="http://x",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )
        b = ResolvedVersion(
            name="chrome",
            version="131.0",
            url="http://x",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )
        assert a == b

    def test_inequality_different_fields(self) -> None:
        """Two ResolvedVersion with different fields should not be equal."""
        a = ResolvedVersion(
            name="chrome",
            version="131.0",
            url="http://x",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )
        b = ResolvedVersion(
            name="chrome",
            version="132.0",
            url="http://x",
            platform="win64",
            checksum=None,
            checksum_algorithm=None,
        )
        assert a != b

    def test_repr_includes_key_fields(self, sample_resolved_version: ResolvedVersion) -> None:
        """repr should include name and version."""
        repr_str = repr(sample_resolved_version)
        assert "chrome" in repr_str
        assert "131.0.6778.87" in repr_str

    def test_checksum_none_allowed(self) -> None:
        """ResolvedVersion with checksum=None should be valid."""
        rv = ResolvedVersion(
            name="firefox",
            version="131.0",
            url="http://x",
            platform="linux64",
            checksum=None,
            checksum_algorithm=None,
        )
        assert rv.checksum is None
        assert rv.checksum_algorithm is None


class TestInstalledArtifact:
    """Tests for the InstalledArtifact dataclass."""

    def test_is_frozen(self, sample_installed_artifact: InstalledArtifact) -> None:
        """InstalledArtifact should be frozen — mutation raises FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            sample_installed_artifact.version = "999"

    def test_to_dict_stringifies_path_and_datetime(
        self, sample_installed_artifact: InstalledArtifact
    ) -> None:
        """to_dict should convert Path to str and datetime to ISO string."""
        d = sample_installed_artifact.to_dict()
        assert d["name"] == "chrome"
        assert d["version"] == "131.0.6778.87"
        assert d["path"] == str(Path("/fake/chrome"))
        assert d["installed_at"] == "2025-01-01T12:00:00"
        assert d["checksum"] == "abc123"

    def test_from_dict_roundtrip(self, sample_installed_artifact: InstalledArtifact) -> None:
        """from_dict(to_dict()) should equal the original."""
        d = sample_installed_artifact.to_dict()
        restored = InstalledArtifact.from_dict(d)
        assert restored == sample_installed_artifact

    def test_from_dict_with_none_checksum(self) -> None:
        """from_dict should handle checksum=None."""
        d = {
            "name": "chrome",
            "version": "1.0",
            "path": "/fake/chrome",
            "installed_at": "2025-01-01T12:00:00",
            "checksum": None,
        }
        artifact = InstalledArtifact.from_dict(d)
        assert artifact.checksum is None

    def test_from_dict_missing_key_raises_valueerror(self) -> None:
        """from_dict with missing required key should raise ValueError."""
        d = {"name": "chrome", "version": "1.0"}
        with pytest.raises(ValueError, match="Missing or null field"):
            InstalledArtifact.from_dict(d)

    def test_from_dict_none_value_raises_valueerror(self) -> None:
        """from_dict with None for a required field should raise ValueError."""
        d = {
            "name": None,
            "version": "1.0",
            "path": "/fake/chrome",
            "installed_at": "2025-01-01T12:00:00",
            "checksum": None,
        }
        with pytest.raises(ValueError, match="Missing or null field: 'name'"):
            InstalledArtifact.from_dict(d)

    def test_from_dict_non_string_value_raises_valueerror(self) -> None:
        """from_dict with non-string for a required field should raise ValueError."""
        d = {
            "name": 123,
            "version": "1.0",
            "path": "/fake/chrome",
            "installed_at": "2025-01-01T12:00:00",
            "checksum": None,
        }
        with pytest.raises(ValueError, match="must be a string"):
            InstalledArtifact.from_dict(d)

    def test_from_dict_invalid_datetime_raises_valueerror(self) -> None:
        """from_dict with invalid datetime string should raise ValueError."""
        d = {
            "name": "chrome",
            "version": "1.0",
            "path": "/fake/chrome",
            "installed_at": "not-a-date",
            "checksum": None,
        }
        with pytest.raises(ValueError):
            InstalledArtifact.from_dict(d)

    def test_to_dict_returns_str_or_none_values(
        self, sample_installed_artifact: InstalledArtifact
    ) -> None:
        """to_dict values should be str or None."""
        d = sample_installed_artifact.to_dict()
        for key, value in d.items():
            assert value is None or isinstance(value, str), f"{key} is {type(value)}"


class TestSystemBrowser:
    """Tests for the SystemBrowser dataclass."""

    def test_with_version_none(self) -> None:
        """SystemBrowser with version=None should be valid."""
        sb = SystemBrowser(name="chrome", version=None, path=Path("/usr/bin/chrome"))
        assert sb.version is None
        assert sb.name == "chrome"
        assert sb.path == Path("/usr/bin/chrome")

    def test_with_version_string(self) -> None:
        """SystemBrowser with a version string should be valid."""
        sb = SystemBrowser(name="firefox", version="131.0", path=Path("/usr/bin/firefox"))
        assert sb.version == "131.0"

    def test_equality_version_none_vs_string(self) -> None:
        """SystemBrowser with version=None should not equal one with a version."""
        a = SystemBrowser(name="chrome", version=None, path=Path("/usr/bin/chrome"))
        b = SystemBrowser(name="chrome", version="131.0", path=Path("/usr/bin/chrome"))
        assert a != b

    def test_equality_same_version_none(self) -> None:
        """Two SystemBrowser with version=None and same other fields should be equal."""
        a = SystemBrowser(name="chrome", version=None, path=Path("/usr/bin/chrome"))
        b = SystemBrowser(name="chrome", version=None, path=Path("/usr/bin/chrome"))
        assert a == b

    def test_is_frozen(self) -> None:
        """SystemBrowser should be frozen."""
        sb = SystemBrowser(name="chrome", version="131.0", path=Path("/usr/bin/chrome"))
        with pytest.raises(FrozenInstanceError):
            sb.version = "999"
