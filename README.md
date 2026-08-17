# browserget

[![CI](https://github.com/MathiasPaulenko/browserget/actions/workflows/ci.yml/badge.svg)](https://github.com/MathiasPaulenko/browserget/actions/workflows/ci.yml)
[![Docs](https://github.com/MathiasPaulenko/browserget/actions/workflows/docs.yml/badge.svg)](https://mathiaspaulenko.github.io/browserget/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/browserget.svg)](https://pypi.org/project/browserget/)

Standalone CLI to install browsers and drivers without any framework.

Chrome for Testing, Firefox, Edge, ChromeDriver, GeckoDriver, EdgeDriver —
all from a single tool. Python 3.11+, zero heavy dependencies.

## Why?

`playwright install` ties you to Playwright. `puppeteer install` ties you to
Puppeteer. `browserget` installs browsers for **any** use — automation,
scraping, testing, CDP, BiDi, whatever.

## Features

- **6 targets** — Chrome, Firefox, Edge + ChromeDriver, GeckoDriver, EdgeDriver
- **Concurrent installs** — multiple targets install in parallel
- **Driver matching** — `--for chrome` auto-matches ChromeDriver to your Chrome
- **Checksum verification** — SHA-256/SHA-512 when upstream provides checksums
- **Registry tracking** — JSON registry tracks every installed artifact
- **JSON output** — every command supports `--json` for CI/CD integration
- **Retry with backoff** — HTTP client retries failed requests automatically
- **Disk space checks** — verifies sufficient space before downloading
- **Platform detection** — auto-detects OS and architecture

## Installation

```bash
pip install browserget
```

## Quick start

```bash
# Install latest stable Chrome
browserget install chrome

# Install matching ChromeDriver
browserget install chromedriver --for chrome

# Ensure browsers are installed (idempotent — skips if present)
browserget ensure chrome chromedriver

# Verify system health
browserget doctor
```

## Usage

```bash
# Install specific version
browserget install chrome --version 131.0.6778.87

# Install by milestone (latest patch in 131)
browserget install chrome --version 131

# Install Firefox and Edge
browserget install firefox edge

# Install EdgeDriver
browserget install edgedriver --for edge

# List installed browsers
browserget list

# Get path to installed browser
browserget path chrome

# Remove a browser
browserget remove chrome

# Remove all versions of a target
browserget remove chrome --all

# List available versions for a target
browserget versions chrome

# Check system health
browserget doctor

# JSON output for CI/CD
browserget install chrome --json
```

## Supported targets

| Target | Type | Upstream source |
|--------|------|-----------------|
| `chrome` | Browser | Chrome for Testing API |
| `firefox` | Browser | Mozilla FTP |
| `edge` | Browser | Edge Updates API |
| `chromedriver` | Driver | Chrome for Testing API |
| `geckodriver` | Driver | GitHub Releases (mozilla/geckodriver) |
| `edgedriver` | Driver | Edge Updates API |

## Requirements

- Python 3.11, 3.12, or 3.13
- `typer` (installed automatically)
- Internet access to download browser binaries

## Documentation

Full documentation is available at
[https://mathiaspaulenko.github.io/browserget/](https://mathiaspaulenko.github.io/browserget/).

- [Install command](https://mathiaspaulenko.github.io/browserget/usage/install/) — detailed usage and examples
- [Ensure command](https://mathiaspaulenko.github.io/browserget/usage/ensure/) — idempotent installs for CI pipelines
- [Cache management](https://mathiaspaulenko.github.io/browserget/usage/cache/) — cache location, cleanup, and configuration
- [CLI reference](https://mathiaspaulenko.github.io/browserget/cli-reference/commands/) — complete command and flag documentation
- [Architecture](https://mathiaspaulenko.github.io/browserget/architecture/overview/) — module diagram and design decisions

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, testing, and pull request guidelines.

## License

MIT — see [LICENSE](LICENSE).
