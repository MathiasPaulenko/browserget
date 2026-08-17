"""Unit tests for the Registry class."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from browserget.exceptions import VersionNotFoundError
from browserget.models import InstalledArtifact
from browserget.registry import Registry


def _make_artifact(
    name: str = "chrome",
    version: str = "131.0",
    path: Path | None = None,
    installed_at: datetime | None = None,
) -> InstalledArtifact:
    """Create a test InstalledArtifact."""
    return InstalledArtifact(
        name=name,
        version=version,
        path=path or Path("/fake/path"),
        installed_at=installed_at or datetime(2025, 1, 1, tzinfo=UTC),
        checksum="abc123",
    )


class TestLoad:
    """Tests for load()."""

    def test_load_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        """load() should return {} when the registry file doesn't exist."""
        reg = Registry(tmp_path)
        assert reg.load() == {}

    def test_load_returns_empty_on_corrupted_json(self, tmp_path: Path) -> None:
        """load() should return {} on corrupted JSON."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        reg.registry_path.write_text("{corrupted json", encoding="utf-8")
        assert reg.load() == {}


class TestSaveLoad:
    """Tests for save() + load() roundtrip."""

    def test_roundtrip_preserves_data(self, tmp_path: Path) -> None:
        """save() then load() should preserve all data."""
        reg = Registry(tmp_path)
        artifact = _make_artifact()
        reg.save({"chrome": [artifact]})
        loaded = reg.load()
        assert "chrome" in loaded
        assert len(loaded["chrome"]) == 1
        assert loaded["chrome"][0] == artifact

    def test_save_creates_directory_if_missing(self, tmp_path: Path) -> None:
        """save() should create the cache directory if it doesn't exist."""
        cache_dir = tmp_path / "newdir"
        reg = Registry(cache_dir)
        reg.save({"chrome": [_make_artifact()]})
        assert cache_dir.exists()
        assert reg.registry_path.exists()


class TestAdd:
    """Tests for add()."""

    def test_add_inserts_new_artifact(self, tmp_registry: Registry) -> None:
        """add() should insert a new artifact."""
        artifact = _make_artifact()
        tmp_registry.add(artifact)
        assert tmp_registry.find("chrome", "131.0") == artifact

    def test_add_replaces_existing_same_name_version(self, tmp_registry: Registry) -> None:
        """add() should replace an artifact with the same name+version."""
        old = _make_artifact(version="131.0", path=Path("/old/path"))
        tmp_registry.add(old)
        new = _make_artifact(version="131.0", path=Path("/new/path"))
        tmp_registry.add(new)
        entries = tmp_registry.get("chrome")
        assert len(entries) == 1
        assert entries[0].path == Path("/new/path")


class TestRemove:
    """Tests for remove()."""

    def test_remove_deletes_entry(self, tmp_registry: Registry) -> None:
        """remove() should delete the specified entry."""
        artifact = _make_artifact()
        tmp_registry.add(artifact)
        tmp_registry.remove("chrome", "131.0")
        assert tmp_registry.find("chrome", "131.0") is None

    def test_remove_raises_on_nonexistent(self, tmp_registry: Registry) -> None:
        """remove() should raise VersionNotFoundError for non-existent entries."""
        with pytest.raises(VersionNotFoundError):
            tmp_registry.remove("chrome", "999.0")


class TestGet:
    """Tests for get()."""

    def test_get_returns_list_for_target(self, tmp_registry: Registry) -> None:
        """get() should return a list of artifacts for a target."""
        tmp_registry.add(_make_artifact(version="1.0"))
        tmp_registry.add(_make_artifact(version="2.0"))
        entries = tmp_registry.get("chrome")
        assert len(entries) == 2

    def test_get_returns_empty_for_unknown_target(self, tmp_registry: Registry) -> None:
        """get() should return [] for an unknown target."""
        assert tmp_registry.get("firefox") == []


class TestFind:
    """Tests for find()."""

    def test_find_exact_version(self, tmp_registry: Registry) -> None:
        """find() with exact version should return the matching artifact."""
        tmp_registry.add(_make_artifact(version="1.0"))
        tmp_registry.add(_make_artifact(version="2.0"))
        result = tmp_registry.find("chrome", "1.0")
        assert result is not None
        assert result.version == "1.0"

    def test_find_none_version_returns_most_recent(self, tmp_registry: Registry) -> None:
        """find() with version=None should return the most recently installed."""
        old = _make_artifact(version="1.0", installed_at=datetime(2025, 1, 1, tzinfo=UTC))
        new = _make_artifact(version="2.0", installed_at=datetime(2025, 6, 1, tzinfo=UTC))
        tmp_registry.add(old)
        tmp_registry.add(new)
        result = tmp_registry.find("chrome")
        assert result is not None
        assert result.version == "2.0"

    def test_find_unknown_target_returns_none(self, tmp_registry: Registry) -> None:
        """find() on an unknown target should return None."""
        assert tmp_registry.find("firefox") is None

    def test_find_nonexistent_version_returns_none(self, tmp_registry: Registry) -> None:
        """find() with a non-existent version should return None."""
        tmp_registry.add(_make_artifact(version="1.0"))
        assert tmp_registry.find("chrome", "999.0") is None


class TestListAll:
    """Tests for list_all()."""

    def test_list_all_returns_everything(self, tmp_registry: Registry) -> None:
        """list_all() should return all artifacts."""
        tmp_registry.add(_make_artifact(name="chrome", version="1.0"))
        tmp_registry.add(_make_artifact(name="firefox", version="2.0"))
        result = tmp_registry.list_all()
        assert "chrome" in result
        assert "firefox" in result
        assert len(result["chrome"]) == 1
        assert len(result["firefox"]) == 1

    def test_list_all_empty_registry(self, tmp_registry: Registry) -> None:
        """list_all() on an empty registry should return {}."""
        assert tmp_registry.list_all() == {}


class TestAtomicSave:
    """Tests for atomic save behavior."""

    def test_no_temp_file_left_after_save(self, tmp_path: Path) -> None:
        """No .tmp files should remain after save()."""
        reg = Registry(tmp_path)
        reg.save({"chrome": [_make_artifact()]})
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0


class TestLoadRobustness:
    """Tests for load() robustness against malformed registry data."""

    def test_load_returns_empty_when_root_is_list(self, tmp_path: Path) -> None:
        """load() should return {} when JSON root is a list, not an object."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        reg.registry_path.write_text("[1, 2, 3]", encoding="utf-8")
        assert reg.load() == {}

    def test_load_returns_empty_when_root_is_string(self, tmp_path: Path) -> None:
        """load() should return {} when JSON root is a string."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        reg.registry_path.write_text('"hello"', encoding="utf-8")
        assert reg.load() == {}

    def test_load_skips_non_list_values(self, tmp_path: Path) -> None:
        """load() should skip entries whose values are not lists."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        import json

        reg.registry_path.write_text(
            json.dumps({"chrome": "not_a_list", "firefox": 42}),
            encoding="utf-8",
        )
        assert reg.load() == {}

    def test_load_skips_non_dict_entries(self, tmp_path: Path) -> None:
        """load() should skip individual entries that are not dicts."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        import json

        artifact = _make_artifact()
        reg.registry_path.write_text(
            json.dumps(
                {
                    "chrome": [artifact.to_dict(), "not_a_dict", 42, None],
                }
            ),
            encoding="utf-8",
        )
        loaded = reg.load()
        assert "chrome" in loaded
        assert len(loaded["chrome"]) == 1
        assert loaded["chrome"][0] == artifact

    def test_load_skips_entry_with_missing_key(self, tmp_path: Path) -> None:
        """load() should skip entries with missing required keys."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        import json

        artifact = _make_artifact()
        bad_entry = {"name": "chrome", "version": "1.0"}
        reg.registry_path.write_text(
            json.dumps({"chrome": [artifact.to_dict(), bad_entry]}),
            encoding="utf-8",
        )
        loaded = reg.load()
        assert len(loaded["chrome"]) == 1
        assert loaded["chrome"][0] == artifact

    def test_load_skips_entry_with_none_field(self, tmp_path: Path) -> None:
        """load() should skip entries with None for required fields."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        import json

        artifact = _make_artifact()
        bad_entry = artifact.to_dict()
        bad_entry["name"] = None
        reg.registry_path.write_text(
            json.dumps({"chrome": [bad_entry, artifact.to_dict()]}),
            encoding="utf-8",
        )
        loaded = reg.load()
        assert len(loaded["chrome"]) == 1
        assert loaded["chrome"][0] == artifact

    def test_load_skips_entry_with_invalid_datetime(self, tmp_path: Path) -> None:
        """load() should skip entries with invalid datetime strings."""
        reg = Registry(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        import json

        artifact = _make_artifact()
        bad_entry = artifact.to_dict()
        bad_entry["installed_at"] = "not-a-date"
        reg.registry_path.write_text(
            json.dumps({"chrome": [bad_entry, artifact.to_dict()]}),
            encoding="utf-8",
        )
        loaded = reg.load()
        assert len(loaded["chrome"]) == 1
        assert loaded["chrome"][0] == artifact
