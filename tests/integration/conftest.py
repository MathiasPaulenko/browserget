"""Fixtures for integration tests with real network and temp cache dirs."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def isolated_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Provide an isolated cache directory via BROWSERGET_CACHE_DIR env var.

    This ensures integration tests do not pollute the real browserget cache.
    All artifacts, registry, and downloads go into a temp directory that is
    cleaned up automatically by pytest's tmp_path fixture.

    Returns:
        A dict with 'cache_dir' (Path) and 'env' (the env var name).
    """
    cache_dir = tmp_path / "browserget-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BROWSERGET_CACHE_DIR", str(cache_dir))
    return {"cache_dir": cache_dir, "env": "BROWSERGET_CACHE_DIR"}


@pytest.fixture
def cleanup_artifacts(
    isolated_cache: dict[str, Any],
) -> Any:
    """Fixture that cleans up all installed artifacts after each test.

    Yields a set of (name, version) tuples to track what was installed.
    After the test, removes each from the cache and registry.
    """
    installed: set[tuple[str, str]] = set()
    yield installed

    cache_dir = isolated_cache["cache_dir"]
    from browserget.registry import Registry

    registry = Registry(cache_dir)
    data = registry.load()
    for name, artifacts in data.items():
        for artifact in artifacts:
            artifact_dir = cache_dir / name / artifact.version
            if artifact_dir.exists():
                import shutil

                shutil.rmtree(artifact_dir, ignore_errors=True)
            with contextlib.suppress(Exception):
                registry.remove(name, artifact.version)
