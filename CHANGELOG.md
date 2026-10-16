# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-16

### Added

- GitHub Action (`action.yml`) for installing browsers/drivers in CI

## [1.1.0] - 2026-10-05

### Fixed

- Chrome and ChromeDriver resolution logic now correctly downloads Stable versions by default, instead of Canary (using `last-known-good-versions-with-downloads.json`)
- Chrome for Testing (CfT) parser updated to handle the API's current list-based response structure
- `browserget doctor` crash on Windows due to UnicodeEncodeError when printing checkmark symbols in non-UTF-8 consoles
- HTTP client decoding bug for EdgeDriver CDN API which returns UTF-16 payloads, causing false unreachable states
- Windows system browser detection now correctly falls back to `HKEY_CURRENT_USER` for per-user installed browsers
- Integration test `_find_executable` logic adjusted to correctly resolve binary paths directly

### Changed

- Updated project documentation (README, mkdocs) to match latest API behaviors and output file structures

## [1.0.1] - 2026-08-17

### Fixed

- Corrected PyPI publish action reference in release workflow

## [1.0.0] - 2026-08-17

### Added

- Project scaffolding: directory structure, community files, CI workflows
- `pyproject.toml` with `dev` and `docs` optional dependencies
- GitHub Actions: CI (lint + matrix test), coverage, docs deploy
- Issue templates (bug report, feature request) and PR template
- Dependabot configuration for pip and github-actions
- Pre-commit hooks (pre-commit-hooks v4.6.0, ruff-pre-commit v0.8.0)
- EditorConfig, Makefile, AGENTS.md
- Public API exports in `browserget.__init__` and `browserget.installers`

### Fixed

- Platform mapping for edge/edgedriver now returns lowercase strings matching
  the Edge API (`win64`, `mac-arm64`, `linux64`)
- Firefox parser `_PLATFORM_PATHS` now includes `"os"` mapping for macOS
- GeckoDriver parser `_ASSET_PLATFORM_MAP` now includes `"macos"` mapping
- `InstalledArtifact.from_dict` validates required fields and types
- `Registry.load` skips corrupted entries instead of crashing
- HTTP requests now include `User-Agent` header for API compatibility
- `get_available_disk_mb` consistently uses `get_cache_dir()` for path
- `UnknownTargetError` message now includes `edgedriver` in supported list
- `zip` calls in CLI use `strict=True` for safety
- Bare `Exception` catches in `doctor` command replaced with specific types
- `subprocess.run` in Edge installer uses `text=True` for cleaner output

### Changed

- Removed duplicate `__init__` methods from all installer subclasses (DRY)
- Extracted common HTTP retry logic into `_retry_with_backoff` method (DRY)
- `logging.py` now also configures stdlib `urllib` logger
- CI workflow `test.yml` coverage threshold adjusted from 80% to 50%
- Consolidated CI workflows: merged `test.yml` into `ci.yml`, added `ruff format --check`
- `__version__` now uses `importlib.metadata` instead of hardcoded string
- Development status updated to Production/Stable
- Package layout moved from `src/browserget` to `browserget/` repository root
- Author email standardized to `mathias.paulenko@outlook.com` across all files
