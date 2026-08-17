# CLI reference

Complete reference for all browserget commands, flags, and behaviors.

## Global options

These options are available on `install` and `ensure` commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output results as JSON |
| `--quiet` | `-q` | Suppress all output except errors |
| `--verbose` | `-v` | Show informational messages |
| `--debug` | | Show full tracebacks on error |

## Commands

### install

Downloads and installs one or more browser or driver binaries.

```bash
browserget install chrome
browserget install chrome --version 131.0.6778.87
browserget install chromedriver --for chrome
```

::: browserget.cli.install

### ensure

Idempotent version of `install`: only downloads if the target is missing.

```bash
browserget ensure chrome chromedriver
```

::: browserget.cli.ensure

### list

Lists all installed artifacts in the registry.

```bash
browserget list
browserget list --json
```

::: browserget.cli.list_cmd

### path

Prints the absolute path to an installed artifact.

```bash
browserget path chrome
browserget path chromedriver --version 131.0.6778.87
```

::: browserget.cli.path_cmd

### remove

Removes an installed artifact from the cache and registry.

```bash
browserget remove chrome
browserget remove chrome --version 130.0.6723.69
browserget remove chrome --all
```

::: browserget.cli.remove

### versions

Lists available versions for a target from the upstream API.

```bash
browserget versions chrome
```

::: browserget.cli.versions

### doctor

Checks cache, disk space, and upstream API reachability.

```bash
browserget doctor
```

::: browserget.cli.doctor

## Exit codes

| Code | Exception | Description |
|------|-----------|-------------|
| 0 | — | Success |
| 1 | `InsufficientDiskSpaceError` | Not enough disk space for download |
| 1 | (unexpected) | Any unhandled exception |
| 2 | `UnknownTargetError` | Target name not recognized |
| 2 | `VersionNotFoundError` | Requested version does not exist |
| 2 | `DriverMatchError` | No matching driver found for browser |
| 2 | `UnsupportedPlatformError` | Platform not supported by upstream |
| 3 | `NetworkError` | Network failure after all retries |
| 4 | `ChecksumMismatchError` | Downloaded file failed checksum verification |
| 5 | `AlreadyInstalledError` | Target already installed (use `--force`) |

## Verbosity levels

| Level | Flag | What you see |
|-------|------|-------------|
| Quiet | `-q` / `--quiet` | Only error messages |
| Default | (none) | Command output and warnings |
| Verbose | `-v` / `--verbose` | Info-level logs (HTTP requests, extraction progress) |
| Debug | `--debug` | Debug-level logs + full tracebacks on error |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSERGET_CACHE_DIR` | OS-specific | Cache directory for downloaded artifacts |
| `BROWSERGET_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `BROWSERGET_MAX_RETRIES` | `3` | Maximum HTTP retry attempts on failure |
| `BROWSERGET_VERBOSE` | `false` | Enable verbose logging globally |

!!! note "JSON error output"
    When `--json` is passed and an error occurs, the output is a JSON array
    containing both successful entries and error entries. Each error entry
    includes `status: "error"`, the error type, and the message.
