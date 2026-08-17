# install

The `install` command downloads and installs browser or driver binaries into the
browserget cache directory. It resolves the requested version from the upstream API,
downloads the archive, verifies the checksum (when available), extracts it, and
registers the artifact.

## Usage

```bash
browserget install [TARGETS]... [OPTIONS]
```

## Examples

### Basic install

Install the latest stable Chrome for Testing:

```bash
browserget install chrome
```

### Specific version

Install a known stable version:

```bash
browserget install chrome --version 131.0.6778.87
```

### Milestone install

Install the latest patch within a milestone:

```bash
browserget install chrome --version 131
```

### Multiple targets

Install Chrome and ChromeDriver concurrently:

```bash
browserget install chrome chromedriver
```

### Driver matching

Install ChromeDriver matched to an installed Chrome browser:

```bash
browserget install chromedriver --for chrome
```

This resolves the installed Chrome version from the registry and finds the
matching ChromeDriver version (same milestone).

### Force reinstall

Reinstall an already-installed target:

```bash
browserget install chrome --force
```

Without `--force`, installing an existing version exits with code 5
(`AlreadyInstalledError`).

### JSON output

Get machine-readable output for CI/CD pipelines:

```bash
browserget install chrome --json
```

Output:

```json
[
  {"name": "chrome", "version": "131.0.6778.87", "path": "/home/user/.browserget/chrome/131.0.6778.87", "status": "installed"}
]
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

## Options

| Option | Description |
|--------|-------------|
| `--version VERSION` | Specific version or milestone (e.g. `131.0.6778.87` or `131`) |
| `--force` | Reinstall if already present |
| `--for BROWSER` | Match driver to an installed browser (`chrome`, `firefox`, `edge`) |
| `--json` | Output results as JSON |
| `-q`, `--quiet` | Suppress all output except errors |
| `-v`, `--verbose` | Show informational messages |
| `--debug` | Show full tracebacks on error |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Insufficient disk space or unexpected error |
| 2 | Unknown target, version not found, or driver match failure |
| 3 | Network error |
| 4 | Checksum mismatch |
| 5 | Already installed (use `--force` to reinstall) |

!!! note "No targets provided"
    Running `browserget install` without any targets prints usage and exits with
    code 1.
