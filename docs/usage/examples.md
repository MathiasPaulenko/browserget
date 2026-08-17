# Examples

This page shows common workflows and concrete command examples for browserget.

## Installation

Install from PyPI:

```bash
pip install browserget
```

## Basic workflows

### Install the latest versions

```bash
browserget install chrome
browserget install firefox
browserget install edge
```

### Install a specific version

```bash
browserget install chrome --version 131.0.6778.87
```

### Install by milestone

```bash
browserget install chrome --version 131
```

This installs the latest patch release within the `131` milestone.

### Install a browser and matching driver

```bash
browserget install chrome
browserget install chromedriver --for chrome
```

`--for chrome` resolves the installed Chrome version and installs the matching
ChromeDriver.

## CI/CD workflows

The `ensure` command is idempotent: it only downloads a target when it is not
already installed. This makes it ideal for CI pipelines.

```bash
pip install browserget
browserget ensure chrome chromedriver
```

Use `path` to locate the installed binary:

```bash
CHROME_PATH=$(browserget path chrome)
CHROMEDRIVER_PATH=$(browserget path chromedriver)
```

Or use JSON output for scripts:

```bash
browserget ensure chrome chromedriver --json
```

Example output:

```json
[
  {"name": "chrome", "version": "131.0.6778.87", "path": "/home/user/.browserget/chrome/131.0.6778.87", "status": "already_installed"},
  {"name": "chromedriver", "version": "131.0.6778.87", "path": "/home/user/.browserget/chromedriver/131.0.6778.87", "status": "already_installed"}
]
```

## Cache management

List installed artifacts:

```bash
browserget list
```

Remove a single version:

```bash
browserget remove chrome --version 130.0.6723.69
```

Remove all versions of a target:

```bash
browserget remove chrome --all
```

Use a custom cache directory for CI caching:

```bash
export BROWSERGET_CACHE_DIR=/opt/browserget-cache
browserget ensure chrome chromedriver
```

## Version discovery

List available versions from upstream:

```bash
browserget versions chrome
browserget versions firefox
browserget versions edge
browserget versions chromedriver
```

## System health

Run `doctor` to verify the cache, disk space, and upstream API reachability:

```bash
browserget doctor
```

Example output:

```text
  ✓ Cache directory: /home/user/.browserget
  ✓ Registry: 2 artifacts
  ✓ Disk space: 45213MB free, 187MB cache
  ✓ System browsers: chrome 131.0.6778.87
  ✓ CfT API: reachable
  ✓ Firefox FTP: reachable
  ✓ Edge API: reachable
  ✓ GitHub API: reachable
```

## Exit codes

browserget uses the following exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unexpected error or insufficient disk space |
| 2 | Unknown target, version not found, or driver match failure |
| 3 | Network error |
| 4 | Checksum mismatch |
| 5 | Already installed (use `--force`) |

Use these in scripts to decide the next step:

```bash
browserget ensure chrome
if [ $? -eq 5 ]; then
  browserget install chrome --force
fi
```
