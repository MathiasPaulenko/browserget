"""CLI for browserget — install browsers and drivers for automated testing."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any, cast

import typer

from browserget.cache import get_artifact_dir, get_cache_size, safe_rmtree
from browserget.config import Config, load_config
from browserget.exceptions import (
    AlreadyInstalledError,
    ChecksumMismatchError,
    DriverMatchError,
    InsufficientDiskSpaceError,
    NetworkError,
    UnknownTargetError,
    UnsupportedPlatformError,
    VersionNotFoundError,
)
from browserget.http import HttpClient
from browserget.installers.base import AbstractBrowserInstaller, AbstractDriverInstaller
from browserget.logging import setup_logging
from browserget.models import InstalledArtifact
from browserget.platform import detect_platform, map_platform
from browserget.registry import Registry
from browserget.system import SystemDetector

app = typer.Typer(
    name="browserget",
    help="Install browsers and drivers for automated testing.",
    no_args_is_help=True,
)

_KNOWN_TARGETS: set[str] = {
    "chrome",
    "firefox",
    "edge",
    "chromedriver",
    "geckodriver",
    "edgedriver",
}
_BROWSER_TARGETS: set[str] = {"chrome", "firefox", "edge"}
_DRIVER_TARGETS: set[str] = {"chromedriver", "geckodriver", "edgedriver"}
_DRIVER_BROWSER_MAP: dict[str, str] = {
    "chromedriver": "chrome",
    "geckodriver": "firefox",
    "edgedriver": "edge",
}

_EXIT_CODE_MAP: dict[type[Exception], int] = {
    UnknownTargetError: 2,
    VersionNotFoundError: 2,
    DriverMatchError: 2,
    UnsupportedPlatformError: 2,
    NetworkError: 3,
    ChecksumMismatchError: 4,
    AlreadyInstalledError: 5,
    InsufficientDiskSpaceError: 1,
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _create_installer(
    target: str,
    http: HttpClient,
    registry: Registry,
    config: Config,
) -> AbstractBrowserInstaller | AbstractDriverInstaller:
    """Create the appropriate installer for a target name.

    Args:
        target: One of the known target names.
        http: HTTP client instance.
        registry: Registry instance.
        config: Runtime configuration.

    Returns:
        An installer instance for the given target.

    Raises:
        UnknownTargetError: If the target is not recognized.
    """
    if target == "chrome":
        from browserget.installers.chrome import ChromeInstaller

        return ChromeInstaller(http, registry, config)
    if target == "chromedriver":
        from browserget.installers.chromedriver import ChromeDriverInstaller

        return ChromeDriverInstaller(http, registry, config)
    if target == "firefox":
        from browserget.installers.firefox import FirefoxInstaller

        return FirefoxInstaller(http, registry, config)
    if target == "geckodriver":
        from browserget.installers.geckodriver import GeckoDriverInstaller

        return GeckoDriverInstaller(http, registry, config)
    if target == "edge":
        from browserget.installers.edge import EdgeInstaller

        return EdgeInstaller(http, registry, config)
    if target == "edgedriver":
        from browserget.installers.edge import EdgeDriverInstaller

        return EdgeDriverInstaller(http, registry, config)
    raise UnknownTargetError(target)


def _run_async(coro_factory: Any) -> Any:
    """Run a coroutine to completion, handling event loop edge cases.

    Accepts either a coroutine or a callable that returns a coroutine.
    A new event loop is created and set as current before the coroutine
    is instantiated, so that ``asyncio.gather()`` can find the running loop.

    Args:
        coro_factory: A coroutine object or a callable returning one.

    Returns:
        The result of the coroutine.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        coro = coro_factory() if callable(coro_factory) else coro_factory
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _get_exit_code(exc: Exception) -> int:
    """Return the exit code for an exception, using isinstance for subclass support.

    Args:
        exc: The exception to look up.

    Returns:
        The mapped exit code, or 1 if no mapping matches.
    """
    for exc_type, code in _EXIT_CODE_MAP.items():
        if isinstance(exc, exc_type):
            return code
    return 1


def _exit_with_error(exc: Exception, json_output: bool, debug: bool) -> None:
    """Print an error message and exit with the appropriate code.

    Args:
        exc: The exception that caused the error.
        json_output: Whether to output JSON format.
        debug: Whether to show full tracebacks.
    """
    exit_code = _get_exit_code(exc)
    if json_output:
        error_type = type(exc).__name__.removesuffix("Error").lower()
        print(json.dumps({"error": error_type, "message": str(exc)}))
    else:
        print(f"Error: {exc}", file=sys.stderr)
    if debug:
        import traceback

        traceback.print_exc(file=sys.stderr)
    raise typer.Exit(code=exit_code)


async def _install_one(
    target: str,
    version: str | None,
    force: bool,
    for_browser: str | None,
    http: HttpClient,
    registry: Registry,
    config: Config,
) -> InstalledArtifact:
    """Install a single target.

    Args:
        target: Target name to install.
        version: Optional exact version or milestone.
        force: Whether to reinstall if already present.
        for_browser: Browser name for driver matching, or None.
        http: HTTP client instance.
        registry: Registry instance.
        config: Runtime configuration.

    Returns:
        The installed artifact record.
    """
    installer = _create_installer(target, http, registry, config)
    if for_browser and target in _DRIVER_TARGETS:
        browser_artifact = registry.find(for_browser)
        if browser_artifact is None:
            raise DriverMatchError(driver=target, browser=for_browser)
        assert target in _DRIVER_TARGETS
        driver_installer = cast(AbstractDriverInstaller, installer)
        resolved = await driver_installer.match_browser(browser_artifact.version)
    else:
        resolved = await installer.resolve(version)
    return await installer.install(resolved, force)


async def _ensure_one(
    target: str,
    version: str | None,
    force: bool,
    for_browser: str | None,
    http: HttpClient,
    registry: Registry,
    config: Config,
) -> tuple[InstalledArtifact, bool]:
    """Ensure a single target is installed, installing if missing.

    Args:
        target: Target name to ensure.
        version: Optional exact version or milestone.
        force: Whether to reinstall if already present.
        for_browser: Browser name for driver matching, or None.
        http: HTTP client instance.
        registry: Registry instance.
        config: Runtime configuration.

    Returns:
        A tuple of (installed artifact, whether it was newly installed).
    """
    installer = _create_installer(target, http, registry, config)
    if for_browser and target in _DRIVER_TARGETS:
        browser_artifact = registry.find(for_browser)
        if browser_artifact is None:
            raise DriverMatchError(driver=target, browser=for_browser)
        assert target in _DRIVER_TARGETS
        driver_installer = cast(AbstractDriverInstaller, installer)
        resolved = await driver_installer.match_browser(browser_artifact.version)
    else:
        resolved = await installer.resolve(version)

    existing = registry.find(target, resolved.version)
    if existing is not None and not force:
        return (existing, False)
    return (await installer.install(resolved, force), True)


async def _gather_with_dependencies(
    action_func: Any,
    targets: list[str],
    version: str | None,
    force: bool,
    for_browser: str | None,
    http: HttpClient,
    registry: Registry,
    config: Config,
) -> list[Any]:
    """Run install/ensure actions with proper browser-driver ordering.

    When ``for_browser`` is specified and browser targets are in the list,
    browser targets are installed first so that driver targets can find
    them in the registry. Otherwise all targets run concurrently.

    Args:
        action_func: ``_install_one`` or ``_ensure_one``.
        targets: List of target names.
        version: Optional version string.
        force: Whether to reinstall if already present.
        for_browser: Browser name for driver matching, or None.
        http: HTTP client instance.
        registry: Registry instance.
        config: Runtime configuration.

    Returns:
        List of results (or exceptions) in the same order as ``targets``.
    """
    if for_browser and any(t in _BROWSER_TARGETS for t in targets):
        browser_targets = [t for t in targets if t in _BROWSER_TARGETS]
        other_targets = [t for t in targets if t not in _BROWSER_TARGETS]

        browser_results = await asyncio.gather(
            *[
                action_func(t, version, force, None, http, registry, config)
                for t in browser_targets
            ],
            return_exceptions=True,
        )

        if other_targets:
            other_results = await asyncio.gather(
                *[
                    action_func(t, version, force, for_browser, http, registry, config)
                    for t in other_targets
                ],
                return_exceptions=True,
            )
        else:
            other_results = []

        results_map: dict[str, Any] = {}
        for t, r in zip(browser_targets, browser_results, strict=True):
            results_map[t] = r
        for t, r in zip(other_targets, other_results, strict=True):
            results_map[t] = r
        return [results_map[t] for t in targets]

    return list(
        await asyncio.gather(
            *[action_func(t, version, force, for_browser, http, registry, config) for t in targets],
            return_exceptions=True,
        )
    )


async def _fetch_available_versions(target: str, http: HttpClient) -> list[str]:
    """Fetch available version strings for a target from its upstream API.

    Args:
        target: Target name to query.
        http: HTTP client instance.

    Returns:
        A list of version strings sorted descending.
    """
    platform = detect_platform()

    if target in ("chrome", "chromedriver"):
        from browserget.installers.chrome import CFT_URL
        from browserget.parsers.cft import parse_versions as parse_cft

        platform_str = map_platform(platform, "cft")
        data = await http.get_json(CFT_URL)
        versions = parse_cft(data, target, platform_str)
        return [v.version for v in versions]

    if target == "firefox":
        from browserget.installers.firefox import FIREFOX_FTP_URL
        from browserget.parsers.firefox import _firefox_version_tuple, parse_releases

        html = await http.get_text(FIREFOX_FTP_URL)
        firefox_versions = parse_releases(html)
        firefox_versions.sort(key=_firefox_version_tuple, reverse=True)
        return firefox_versions

    if target == "geckodriver":
        from browserget.installers.geckodriver import GITHUB_API_URL
        from browserget.parsers.geckodriver import parse_releases as parse_gecko

        platform_str = map_platform(platform, "geckodriver")
        data = await http.get_json(GITHUB_API_URL)
        versions = parse_gecko(data, platform_str)
        return [v.version for v in versions]

    if target == "edge":
        from browserget.installers.edge import EDGE_API_URL
        from browserget.parsers.edge import parse_versions as parse_edge

        platform_str = map_platform(platform, "edge")
        data = await http.get_json(EDGE_API_URL)
        versions = parse_edge(data, "edge", platform_str)
        return [v.version for v in versions]

    if target == "edgedriver":
        from browserget.parsers.edge import EDGEDRIVER_LATEST_URL

        text = await http.get_text(EDGEDRIVER_LATEST_URL)
        version = text.strip()
        return [version] if version else []

    return []


async def _check_connectivity(http: HttpClient) -> list[tuple[str, bool, str]]:
    """Check connectivity to all upstream APIs.

    Args:
        http: HTTP client instance.

    Returns:
        A list of (name, ok, detail) tuples for each API check.
    """
    urls = [
        (
            "CfT API",
            "https://googlechromelabs.github.io/chrome-for-testing/"
            "known-good-versions-with-downloads.json",
        ),
        ("Firefox FTP", "https://ftp.mozilla.org/pub/firefox/releases/"),
        ("Edge API", "https://edgeupdates.microsoft.com/api/products"),
        ("EdgeDriver CDN", "https://msedgedriver.microsoft.com/LATEST_STABLE"),
        ("GitHub API", "https://api.github.com/repos/mozilla/geckodriver/releases"),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, url in urls:
        try:
            await http.get_text(url)
            results.append((name, True, "reachable"))
        except Exception:
            results.append((name, False, "unreachable"))
    return results


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def install(
    targets: list[str] = typer.Argument(None, help="Browsers/drivers to install."),  # noqa: B008
    version: str | None = typer.Option(None, "--version", help="Specific version."),
    force: bool = typer.Option(False, "--force", help="Reinstall if already present."),
    for_browser: str | None = typer.Option(
        None, "--for", help="Match driver to installed browser."
    ),
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Install browsers or drivers."""
    setup_logging(verbose=verbose, debug=debug, quiet=quiet)

    if not targets:
        print("Usage: browserget install [TARGETS]...")
        print("\nSupported: chrome, firefox, edge, chromedriver, geckodriver, edgedriver")
        raise typer.Exit(code=1)

    for target in targets:
        if target not in _KNOWN_TARGETS:
            _exit_with_error(UnknownTargetError(target), json_output, debug)

    if for_browser and for_browser not in _BROWSER_TARGETS:
        _exit_with_error(UnknownTargetError(for_browser), json_output, debug)

    config = load_config()
    http = HttpClient(timeout=config.timeout, max_retries=config.max_retries)
    registry = Registry(config.cache_dir)

    try:
        results = _run_async(
            lambda: _gather_with_dependencies(
                _install_one, targets, version, force, for_browser, http, registry, config
            )
        )
    except Exception as exc:
        _exit_with_error(exc, json_output, debug)

    artifacts: list[InstalledArtifact] = []
    errors: list[tuple[str, Exception]] = []
    for target, result in zip(targets, results, strict=True):
        if isinstance(result, Exception):
            errors.append((target, result))
        else:
            artifacts.append(result)

    if errors:
        if json_output:
            output: list[dict[str, Any]] = [
                {"name": a.name, "version": a.version, "path": str(a.path), "status": "installed"}
                for a in artifacts
            ]
            for tgt, error in errors:
                output.append(
                    {
                        "name": tgt,
                        "status": "error",
                        "error": type(error).__name__.removesuffix("Error").lower(),
                        "message": str(error),
                    }
                )
            print(json.dumps(output))
        else:
            for a in artifacts:
                print(f"Installed {a.name} {a.version} -> {a.path}")
            for tgt, error in errors:
                print(f"Error installing {tgt}: {error}", file=sys.stderr)
            if debug:
                import traceback

                traceback.print_exception(
                    type(errors[0][1]), errors[0][1], errors[0][1].__traceback__, file=sys.stderr
                )
        exit_code = _get_exit_code(errors[0][1])
        raise typer.Exit(code=exit_code)

    if json_output:
        print(json.dumps([a.to_dict() for a in artifacts]))
    else:
        for a in artifacts:
            print(f"Installed {a.name} {a.version} -> {a.path}")


@app.command()
def ensure(
    targets: list[str] = typer.Argument(None, help="Browsers/drivers to ensure."),  # noqa: B008
    version: str | None = typer.Option(None, "--version", help="Specific version."),
    force: bool = typer.Option(False, "--force", help="Reinstall if already present."),
    for_browser: str | None = typer.Option(
        None, "--for", help="Match driver to installed browser."
    ),
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Ensure browsers or drivers are installed (install if missing)."""
    setup_logging(verbose=verbose, debug=debug, quiet=quiet)

    if not targets:
        print("Usage: browserget ensure [TARGETS]...")
        print("\nSupported: chrome, firefox, edge, chromedriver, geckodriver, edgedriver")
        raise typer.Exit(code=1)

    for target in targets:
        if target not in _KNOWN_TARGETS:
            _exit_with_error(UnknownTargetError(target), json_output, debug)

    if for_browser and for_browser not in _BROWSER_TARGETS:
        _exit_with_error(UnknownTargetError(for_browser), json_output, debug)

    config = load_config()
    http = HttpClient(timeout=config.timeout, max_retries=config.max_retries)
    registry = Registry(config.cache_dir)

    try:
        results = _run_async(
            lambda: _gather_with_dependencies(
                _ensure_one, targets, version, force, for_browser, http, registry, config
            )
        )
    except Exception as exc:
        _exit_with_error(exc, json_output, debug)

    artifacts: list[tuple[InstalledArtifact, bool]] = []
    errors: list[tuple[str, Exception]] = []
    for target, result in zip(targets, results, strict=True):
        if isinstance(result, Exception):
            errors.append((target, result))
        else:
            artifacts.append(result)

    if errors:
        if json_output:
            output: list[dict[str, Any]] = [
                {
                    "name": a.name,
                    "version": a.version,
                    "path": str(a.path),
                    "status": "installed" if newly else "already_installed",
                }
                for a, newly in artifacts
            ]
            for tgt, error in errors:
                output.append(
                    {
                        "name": tgt,
                        "status": "error",
                        "error": type(error).__name__.removesuffix("Error").lower(),
                        "message": str(error),
                    }
                )
            print(json.dumps(output))
        else:
            for a, newly in artifacts:
                status = "Installed" if newly else "Already installed"
                print(f"{status} {a.name} {a.version} -> {a.path}")
            for tgt, error in errors:
                print(f"Error ensuring {tgt}: {error}", file=sys.stderr)
            if debug:
                import traceback

                traceback.print_exception(
                    type(errors[0][1]), errors[0][1], errors[0][1].__traceback__, file=sys.stderr
                )
        exit_code = _get_exit_code(errors[0][1])
        raise typer.Exit(code=exit_code)

    if json_output:
        output = [
            {**a.to_dict(), "status": "installed" if newly else "already_installed"}
            for a, newly in artifacts
        ]
        print(json.dumps(output))
    else:
        for a, newly in artifacts:
            status = "Installed" if newly else "Already installed"
            print(f"{status} {a.name} {a.version} -> {a.path}")


@app.command("list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """List all installed browsers and drivers."""
    setup_logging()
    config = load_config()
    registry = Registry(config.cache_dir)
    data = registry.list_all()

    total = sum(len(v) for v in data.values())
    if total == 0:
        if json_output:
            print("[]")
        else:
            print("No artifacts installed")
        return

    if json_output:
        all_artifacts: list[dict[str, str | None]] = []
        for artifacts in data.values():
            all_artifacts.extend(a.to_dict() for a in artifacts)
        print(json.dumps(all_artifacts))
    else:
        print(f"{'Name':<15} {'Version':<20} {'Path':<40} {'Installed At'}")
        print(f"{'-' * 15} {'-' * 20} {'-' * 40} {'-' * 20}")
        for artifacts in data.values():
            for a in artifacts:
                print(
                    f"{a.name:<15} {a.version:<20} {str(a.path):<40} {a.installed_at.isoformat()}"
                )


@app.command("path")
def path_cmd(
    target: str = typer.Argument(..., help="Browser or driver name."),
    version: str | None = typer.Option(None, "--version", help="Specific version."),
) -> None:
    """Print the path to an installed browser or driver."""
    setup_logging()

    if target not in _KNOWN_TARGETS:
        print(f"Error: Unknown target: {target}", file=sys.stderr)
        raise typer.Exit(code=2)

    config = load_config()
    registry = Registry(config.cache_dir)
    artifact = registry.find(target, version)

    if artifact is None:
        print(f"Error: {target} is not installed.", file=sys.stderr)
        raise typer.Exit(code=2)

    print(artifact.path)


@app.command()
def remove(
    target: str = typer.Argument(..., help="Browser or driver name."),
    version: str | None = typer.Option(None, "--version", help="Specific version."),
    all_versions: bool = typer.Option(False, "--all", help="Remove all versions of the target."),
) -> None:
    """Remove an installed browser or driver."""
    setup_logging()

    if target not in _KNOWN_TARGETS:
        print(f"Error: Unknown target: {target}", file=sys.stderr)
        raise typer.Exit(code=2)

    config = load_config()
    registry = Registry(config.cache_dir)

    if all_versions:
        artifacts = registry.get(target)
        if not artifacts:
            print(f"Error: {target} is not installed.", file=sys.stderr)
            raise typer.Exit(code=2)
        for a in artifacts:
            artifact_dir = get_artifact_dir(target, a.version)
            if artifact_dir.exists():
                try:
                    safe_rmtree(artifact_dir)
                except OSError as exc:
                    print(
                        f"Warning: Failed to remove {artifact_dir}: {exc}",
                        file=sys.stderr,
                    )
            registry.remove(target, a.version)
        print(f"Removed all versions of {target}")
        return

    artifact = registry.find(target, version)
    if artifact is None:
        print(f"Error: {target} is not installed.", file=sys.stderr)
        raise typer.Exit(code=2)

    artifact_dir = get_artifact_dir(target, artifact.version)
    if artifact_dir.exists():
        try:
            safe_rmtree(artifact_dir)
        except OSError as exc:
            print(f"Warning: Failed to remove {artifact_dir}: {exc}", file=sys.stderr)
    registry.remove(target, artifact.version)
    print(f"Removed {target} {artifact.version}")


@app.command()
def versions(
    target: str = typer.Argument(..., help="Browser or driver name."),
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """List available versions for a target."""
    setup_logging()

    if target not in _KNOWN_TARGETS:
        print(f"Error: Unknown target: {target}", file=sys.stderr)
        raise typer.Exit(code=2)

    config = load_config()
    http = HttpClient(timeout=config.timeout, max_retries=config.max_retries)

    try:
        available = _run_async(lambda: _fetch_available_versions(target, http))
    except Exception as exc:
        _exit_with_error(exc, json_output, False)

    if json_output:
        print(json.dumps(available))
    else:
        print(f"Available versions for {target}:")
        for v in available[:20]:
            print(f"  {v}")
        if len(available) > 20:
            print(f"  ... and {len(available) - 20} more (use --json for all)")


@app.command()
def doctor() -> None:
    """Check system health and configuration."""
    setup_logging()
    config = load_config()

    checks: list[tuple[str, bool, str]] = []

    cache_dir = config.cache_dir
    if cache_dir.exists() and cache_dir.is_dir():
        try:
            test_file = cache_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            checks.append(("Cache directory", True, str(cache_dir)))
        except OSError:
            checks.append(("Cache directory", False, "not writable"))
    else:
        checks.append(("Cache directory", False, "does not exist"))

    try:
        registry = Registry(cache_dir)
        data = registry.load()
        count = sum(len(v) for v in data.values())
        checks.append(("Registry", True, f"{count} artifacts"))
    except (OSError, ValueError, json.JSONDecodeError):
        checks.append(("Registry", False, "corrupted"))

    try:
        cache_size = get_cache_size()
        usage = shutil.disk_usage(cache_dir if cache_dir.exists() else Path.home())
        free_mb = usage.free // (1024 * 1024)
        size_mb = cache_size // (1024 * 1024)
        checks.append(("Disk space", True, f"{free_mb}MB free, {size_mb}MB cache"))
    except OSError:
        checks.append(("Disk space", False, "unknown"))

    detector = SystemDetector()
    browsers = detector.detect_all()
    if browsers:
        names = ", ".join(f"{b.name} {b.version or '?'}" for b in browsers)
        checks.append(("System browsers", True, names))
    else:
        checks.append(("System browsers", False, "none detected"))

    http = HttpClient(timeout=10, max_retries=1)
    try:
        connectivity = _run_async(lambda: _check_connectivity(http))
    except Exception:
        connectivity = [
            ("CfT API", False, "unreachable"),
            ("Firefox FTP", False, "unreachable"),
            ("Edge API", False, "unreachable"),
            ("EdgeDriver CDN", False, "unreachable"),
            ("GitHub API", False, "unreachable"),
        ]
    checks.extend(connectivity)

    for name, ok, detail in checks:
        symbol = "\u2713" if ok else "\u2717"
        print(f"  {symbol} {name}: {detail}")


def main() -> None:
    """Entry point for the browserget CLI."""
    app()
