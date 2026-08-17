"""End-to-end integration tests that perform real downloads.

All tests are decorated with ``@pytest.mark.network`` and ``@pytest.mark.e2e``.
They are skipped by default in CI. Run explicitly with::

    pytest tests/integration/ -v -m "e2e" --timeout=120

Each test uses an isolated temp cache directory (via ``BROWSERGET_CACHE_DIR``)
and cleans up installed artifacts in a finally block.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from browserget.cli import app
from browserget.registry import Registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_binary(binary_path: Path, timeout: int = 30) -> str:
    """Run a browser/driver binary with --version and capture output.

    Args:
        binary_path: Path to the executable.
        timeout: Maximum seconds to wait.

    Returns:
        The stripped stdout output.

    Raises:
        subprocess.TimeoutExpired: If the binary does not respond in time.
        subprocess.CalledProcessError: If the binary exits non-zero.
    """
    result = subprocess.run(
        [str(binary_path), "--version"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout.strip()


def _find_executable(artifact_path: Path, name: str) -> Path:
    """Find the actual executable inside an installed artifact directory.

    Args:
        artifact_path: The artifact directory (e.g. cache/chrome/131.0.6778.87/).
        name: Artifact name (e.g. "chrome", "chromedriver").

    Returns:
        Path to the executable file.

    Raises:
        FileNotFoundError: If no executable is found.
    """
    if sys.platform == "win32":
        candidates = list(artifact_path.rglob(f"{name}.exe"))
    else:
        candidates = list(artifact_path.rglob(name))
    if not candidates:
        candidates = list(artifact_path.rglob("*"))
        candidates = [c for c in candidates if c.is_file() and os.access(c, os.X_OK)]
    if not candidates:
        raise FileNotFoundError(f"No executable found in {artifact_path}")
    return candidates[0]


def _cleanup_target(cache_dir: Path, target: str) -> None:
    """Remove a target's cache directory and registry entries.

    Args:
        cache_dir: The browserget cache directory.
        target: Target name (e.g. "chrome").
    """
    registry = Registry(cache_dir)
    for artifact in registry.get(target):
        artifact_dir = cache_dir / target / artifact.version
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir, ignore_errors=True)
        with contextlib.suppress(Exception):
            registry.remove(target, artifact.version)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.e2e
class TestRealInstall:
    """End-to-end tests that download and verify real browser binaries."""

    def test_install_chrome_latest(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """install chrome → binary exists, --version works, registry updated."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            result = runner.invoke(app, ["install", "chrome"])
            assert result.exit_code == 0, f"install failed: {result.output}"

            # Verify registry has the artifact
            registry = Registry(cache_dir)
            artifact = registry.find("chrome")
            assert artifact is not None, "chrome not in registry"
            assert artifact.path.exists(), f"artifact path does not exist: {artifact.path}"

            # Verify binary runs
            executable = _find_executable(artifact.path, "chrome")
            version_output = _run_binary(executable)
            assert version_output, "chrome --version produced no output"

            # Verify registry data is correct
            milestone = artifact.version.split(".")[0]
            assert artifact.version in version_output or milestone in version_output
        finally:
            _cleanup_target(cache_dir, "chrome")

    def test_install_chromedriver_latest(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install ChromeDriver, verify chromedriver --version runs."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"install failed: {result.output}"

            registry = Registry(cache_dir)
            artifact = registry.find("chromedriver")
            assert artifact is not None, "chromedriver not in registry"
            assert artifact.path.exists(), f"artifact path does not exist: {artifact.path}"

            executable = _find_executable(artifact.path, "chromedriver")
            version_output = _run_binary(executable)
            assert "ChromeDriver" in version_output or artifact.version in version_output
        finally:
            _cleanup_target(cache_dir, "chromedriver")

    def test_install_chrome_specific_version(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install a known stable Chrome version, verify exact version."""
        cache_dir = isolated_cache["cache_dir"]
        known_version = "131.0.6778.87"
        try:
            result = runner.invoke(app, ["install", "chrome", "--version", known_version])
            assert result.exit_code == 0, f"install failed: {result.output}"

            registry = Registry(cache_dir)
            artifact = registry.find("chrome", known_version)
            assert artifact is not None, f"chrome {known_version} not in registry"
            assert artifact.version == known_version
            assert artifact.path.exists()
        finally:
            _cleanup_target(cache_dir, "chrome")

    def test_install_chrome_force_reinstall(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install, then reinstall with --force, verify replacement."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # First install
            result = runner.invoke(app, ["install", "chrome"])
            assert result.exit_code == 0, f"first install failed: {result.output}"

            registry = Registry(cache_dir)
            first_artifact = registry.find("chrome")
            assert first_artifact is not None

            # Reinstall with --force
            result = runner.invoke(app, ["install", "chrome", "--force"])
            assert result.exit_code == 0, f"force reinstall failed: {result.output}"

            # Verify registry still has the artifact
            second_artifact = registry.find("chrome")
            assert second_artifact is not None
            assert second_artifact.path.exists()
        finally:
            _cleanup_target(cache_dir, "chrome")

    def test_ensure_idempotent(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """ensure chrome twice — second call should not download."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # First ensure — should install
            result1 = runner.invoke(app, ["ensure", "chrome"])
            assert result1.exit_code == 0, f"first ensure failed: {result1.output}"
            assert "Installed" in result1.output

            # Second ensure — should be no-op
            result2 = runner.invoke(app, ["ensure", "chrome"])
            assert result2.exit_code == 0, f"second ensure failed: {result2.output}"
            assert "Already installed" in result2.output

            # Verify registry has exactly one entry
            registry = Registry(cache_dir)
            artifacts = registry.get("chrome")
            assert len(artifacts) == 1, f"expected 1 artifact, got {len(artifacts)}"
        finally:
            _cleanup_target(cache_dir, "chrome")

    def test_chromedriver_match_browser(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install Chrome, then chromedriver --for chrome, verify milestone match."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # Install Chrome first
            result = runner.invoke(app, ["install", "chrome"])
            assert result.exit_code == 0, f"chrome install failed: {result.output}"

            registry = Registry(cache_dir)
            chrome_artifact = registry.find("chrome")
            assert chrome_artifact is not None
            chrome_milestone = chrome_artifact.version.split(".")[0]

            # Install matching ChromeDriver
            result = runner.invoke(app, ["install", "chromedriver", "--for", "chrome"])
            assert result.exit_code == 0, f"chromedriver install failed: {result.output}"

            driver_artifact = registry.find("chromedriver")
            assert driver_artifact is not None
            driver_milestone = driver_artifact.version.split(".")[0]

            # Milestones should match
            assert chrome_milestone == driver_milestone, (
                f"milestone mismatch: chrome={chrome_milestone}, driver={driver_milestone}"
            )
        finally:
            _cleanup_target(cache_dir, "chrome")
            _cleanup_target(cache_dir, "chromedriver")

    def test_remove_cleans_cache(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install, remove, verify directory gone and registry empty."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # Install
            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"install failed: {result.output}"

            registry = Registry(cache_dir)
            artifact = registry.find("chromedriver")
            assert artifact is not None
            artifact_dir = cache_dir / "chromedriver" / artifact.version

            # Remove
            result = runner.invoke(app, ["remove", "chromedriver"])
            assert result.exit_code == 0, f"remove failed: {result.output}"
            assert "Removed" in result.output

            # Verify directory is gone
            assert not artifact_dir.exists(), f"directory still exists: {artifact_dir}"

            # Verify registry is empty
            assert registry.find("chromedriver") is None
        finally:
            _cleanup_target(cache_dir, "chromedriver")

    def test_doctor_with_artifacts(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install 2 targets, run doctor, verify output shows them."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # Install two targets
            result = runner.invoke(app, ["install", "chrome"])
            assert result.exit_code == 0, f"chrome install failed: {result.output}"

            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"chromedriver install failed: {result.output}"

            # Run doctor
            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0, f"doctor failed: {result.output}"

            # Doctor should show registry with artifacts
            assert "Registry" in result.output
            assert "2" in result.output  # 2 artifacts
        finally:
            _cleanup_target(cache_dir, "chrome")
            _cleanup_target(cache_dir, "chromedriver")

    def test_list_after_install(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install 2 targets, list shows both."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            result = runner.invoke(app, ["install", "chrome"])
            assert result.exit_code == 0, f"chrome install failed: {result.output}"

            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"chromedriver install failed: {result.output}"

            # List
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0, f"list failed: {result.output}"
            assert "chrome" in result.output
            assert "chromedriver" in result.output

            # List JSON
            result = runner.invoke(app, ["list", "--json"])
            assert result.exit_code == 0, f"list --json failed: {result.output}"
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 2
            names = {entry["name"] for entry in data}
            assert names == {"chrome", "chromedriver"}
        finally:
            _cleanup_target(cache_dir, "chrome")
            _cleanup_target(cache_dir, "chromedriver")

    def test_path_returns_executable(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Install, path chrome returns valid executable path."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"install failed: {result.output}"

            # Get path
            result = runner.invoke(app, ["path", "chromedriver"])
            assert result.exit_code == 0, f"path failed: {result.output}"

            path_str = result.output.strip()
            path = Path(path_str)
            assert path.exists(), f"path does not exist: {path}"

            # On Unix, verify executable permission
            if sys.platform != "win32":
                assert os.access(path, os.X_OK), f"not executable: {path}"
        finally:
            _cleanup_target(cache_dir, "chromedriver")


# ---------------------------------------------------------------------------
# Edge case tests (still e2e but testing error conditions)
# ---------------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.e2e
class TestRealInstallEdgeCases:
    """Edge case integration tests with real network."""

    def test_install_same_version_twice_without_force(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """Installing same version twice without --force → AlreadyInstalledError (exit 5)."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            # First install
            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 0, f"first install failed: {result.output}"

            # Second install without --force → exit 5
            result = runner.invoke(app, ["install", "chromedriver"])
            assert result.exit_code == 5, (
                f"expected exit 5, got {result.exit_code}: {result.output}"
            )
        finally:
            _cleanup_target(cache_dir, "chromedriver")

    def test_chromedriver_for_chrome_not_installed(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """install chromedriver --for chrome when Chrome not installed → exit 2."""
        cache_dir = isolated_cache["cache_dir"]
        try:
            result = runner.invoke(app, ["install", "chromedriver", "--for", "chrome"])
            assert result.exit_code == 2, (
                f"expected exit 2, got {result.exit_code}: {result.output}"
            )
        finally:
            _cleanup_target(cache_dir, "chromedriver")

    def test_versions_chrome_real(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """versions chrome hits real API and returns version list."""
        result = runner.invoke(app, ["versions", "chrome"])
        assert result.exit_code == 0, f"versions failed: {result.output}"
        assert "Available versions" in result.output
        # Should have at least one version number in output
        lines = result.output.strip().split("\n")
        version_lines = [line for line in lines if line.strip().startswith("  ")]
        assert len(version_lines) > 0, "no versions listed"

    def test_versions_chrome_json_real(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """versions chrome --json returns valid JSON array from real API."""
        result = runner.invoke(app, ["versions", "chrome", "--json"])
        assert result.exit_code == 0, f"versions --json failed: {result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert all(isinstance(v, str) for v in data)

    def test_doctor_connectivity_real(
        self,
        runner: CliRunner,
        isolated_cache: dict[str, Any],
    ) -> None:
        """doctor with real network → connectivity checks pass."""
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0, f"doctor failed: {result.output}"
        # At least some connectivity checks should pass
        assert "\u2713" in result.output
