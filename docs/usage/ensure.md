# ensure

The `ensure` command checks whether a target is already installed and only
downloads it if missing. This makes it ideal for CI/CD pipelines and setup
scripts where you want idempotent behavior — run it every time without
re-downloading.

## ensure vs install

| | `install` | `ensure` |
|---|-----------|----------|
| Already installed | Exits with code 5 | No-op, exits 0 |
| Not installed | Downloads and installs | Downloads and installs |
| `--force` | Reinstalls | Reinstalls |
| Use case | Explicit installs | CI pipelines, setup scripts |

## Usage

```bash
browserget ensure [TARGETS]... [OPTIONS]
```

## Examples

### Basic ensure

Ensure Chrome and ChromeDriver are installed:

```bash
browserget ensure chrome chromedriver
```

If both are already installed, the output shows:

```
Already installed chrome 131.0.6778.87 -> /home/user/.browserget/chrome/131.0.6778.87
Already installed chromedriver 131.0.6778.87 -> /home/user/.browserget/chromedriver/131.0.6778.87
```

If they are missing, they are downloaded and installed just like `install`.

### GitHub Actions snippet

```yaml
- name: Install browsers
  run: |
    pip install browserget
    browserget ensure chrome chromedriver

- name: Get Chrome path
  run: echo "CHROME_PATH=$(browserget path chrome)" >> $GITHUB_ENV
```

### JSON output

```bash
browserget ensure chrome --json
```

Output when already installed:

```json
[
  {"name": "chrome", "version": "131.0.6778.87", "path": "/home/user/.browserget/chrome/131.0.6778.87", "status": "already_installed"}
]
```

Output when newly installed:

```json
[
  {"name": "chrome", "version": "131.0.6778.87", "path": "/home/user/.browserget/chrome/131.0.6778.87", "status": "installed"}
]
```

## Decision tree

```
ensure target
  │
  ├─ target in registry?
  │   │
  │   ├─ YES → --force?
  │   │   │
  │   │   ├─ YES → reinstall (download, verify, extract, register)
  │   │   └─ NO  → no-op (report "already installed")
  │   │
  │   └─ NO → resolve version from upstream API
  │       │
  │       ├─ --for browser?
  │       │   │
  │       │   ├─ browser in registry? → match driver to browser version
  │       │   └─ browser not in registry → DriverMatchError (exit 2)
  │       │
  │       └─ install (download, verify, extract, register)
  │
  └─ unknown target → UnknownTargetError (exit 2)
```

## Options

| Option | Description |
|--------|-------------|
| `--version VERSION` | Specific version or milestone |
| `--force` | Reinstall even if already present |
| `--for BROWSER` | Match driver to an installed browser |
| `--json` | Output results as JSON |
| `-q`, `--quiet` | Suppress all output except errors |
| `-v`, `--verbose` | Show informational messages |
| `--debug` | Show full tracebacks on error |

!!! tip "CI pipelines"
    Use `ensure` in CI pipelines to avoid re-downloading browsers on every run.
    Most CI systems cache the home directory, so `~/.browserget` persists between
    runs. Set `BROWSERGET_CACHE_DIR` to a CI-specific cache path for better
    control.
