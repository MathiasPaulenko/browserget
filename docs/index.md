# browserget

**browserget** is a standalone CLI tool that downloads and installs browser binaries
and their corresponding WebDriver executables for automated testing. It works without
any framework dependency — no Selenium, no Playwright, no Puppeteer required.

## Why use it?

- **Minimal dependencies** — only requires Python 3.11+ and `typer`. No heavy frameworks.
- **Standalone** — installs real browser binaries into an isolated cache directory.
- **All browsers** — supports Chrome, Firefox, Edge, and their drivers from a single tool.

## Installation

```bash
pip install browserget
```

## Quick start

```bash
# Install the latest Chrome for Testing
browserget install chrome

# Install the matching ChromeDriver
browserget install chromedriver --for chrome

# Verify everything is ready
browserget doctor
```

## Common examples

### Idempotent CI setup

```bash
pip install browserget
browserget ensure chrome chromedriver
CHROME_PATH=$(browserget path chrome)
```

### Pin a version

```bash
browserget install chrome --version 131.0.6778.87
browserget install chromedriver --for chrome
```

### Manage the cache

```bash
browserget list
browserget remove chrome --version 130.0.6723.69
browserget doctor
```

### Machine-readable output

```bash
browserget list --json
```

## Features

- **7 commands**: `install`, `ensure`, `list`, `path`, `remove`, `versions`, `doctor`
- **Concurrent installs** — multiple targets install in parallel via `asyncio.gather`
- **Driver matching** — `--for chrome` auto-matches ChromeDriver to your Chrome version
- **Checksum verification** — SHA-256/SHA-512 verification for all downloads that provide checksums
- **Registry tracking** — JSON registry tracks every installed artifact and its path
- **JSON output** — every command supports `--json` for CI/CD integration
- **Platform detection** — auto-detects OS and architecture, maps to correct upstream binaries
- **Retry with backoff** — HTTP client retries failed requests with exponential backoff
- **Disk space checks** — verifies sufficient disk space before downloading
- **System browser detection** — `doctor` detects browsers installed outside the cache

## Next steps

- [Install command](usage/install.md) — detailed usage and examples
- [Ensure command](usage/ensure.md) — idempotent installs for CI pipelines
- [Cache management](usage/cache.md) — cache location, cleanup, and configuration
- [CLI reference](cli-reference/commands.md) — complete command and flag documentation
- [Architecture overview](architecture/overview.md) — module diagram and design decisions
- [Parsers](architecture/parsers.md) — how browserget talks to upstream APIs
