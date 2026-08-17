# Cache management

browserget stores all downloaded browser and driver binaries in a cache directory.
This page explains where the cache lives, how to configure it, and how to clean it up.

## Cache location

The default cache directory depends on your operating system:

| OS | Default path |
|-----|-------------|
| Windows | `%LOCALAPPDATA%\browserget` |
| macOS | `~/.browserget` |
| Linux | `~/.browserget` |

### Custom cache directory

Set the `BROWSERGET_CACHE_DIR` environment variable to override the default:

```bash
export BROWSERGET_CACHE_DIR=/opt/browserget-cache
browserget install chrome
```

This is useful for CI systems where you want to cache the directory between runs:

```yaml
# GitHub Actions example
- name: Cache browsers
  uses: actions/cache@v4
  with:
    path: ~/.browserget
    key: browserget-${{ runner.os }}

- name: Install browsers
  run: |
    pip install browserget
    browserget ensure chrome chromedriver
```

## Directory structure

```
~/.browserget/
├── registry.json              # JSON registry of all installed artifacts
├── chrome/
│   └── 131.0.6778.87/         # Extracted Chrome binary
│       ├── chrome             # (or chrome.exe on Windows)
│       └── ...
├── chromedriver/
│   └── 131.0.6778.87/         # Extracted ChromeDriver binary
│       ├── chromedriver
│       └── ...
├── firefox/
│   └── 131.0/                 # Extracted Firefox
│       └── ...
└── downloads/                 # Temporary download directory (cleaned up)
```

## Registry format

The `registry.json` file tracks every installed artifact. It is a JSON object
mapping artifact names to lists of installed versions:

```json
{
  "chrome": [
    {
      "name": "chrome",
      "version": "131.0.6778.87",
      "path": "/home/user/.browserget/chrome/131.0.6778.87",
      "installed_at": "2026-08-15T07:43:00+00:00",
      "checksum": "abc123..."
    }
  ],
  "chromedriver": [
    {
      "name": "chromedriver",
      "version": "131.0.6778.87",
      "path": "/home/user/.browserget/chromedriver/131.0.6778.87",
      "installed_at": "2026-08-15T07:43:30+00:00",
      "checksum": "def456..."
    }
  ]
}
```

Registry writes are atomic — browserget writes to a temporary file first, then
uses `os.replace` to swap it into place.

## Removing artifacts

### Remove a single target

```bash
browserget remove chrome
```

This deletes the artifact directory and removes the entry from the registry.

### Remove a specific version

```bash
browserget remove chrome --version 130.0.6723.69
```

### Remove all versions

```bash
browserget remove chrome --all
```

## Health checks

Run `doctor` to verify the cache is healthy:

```bash
browserget doctor
```

Output:

```
  ✓ Cache directory: /home/user/.browserget
  ✓ Registry: 2 artifacts
  ✓ Disk space: 45213MB free, 187MB cache
  ✓ System browsers: chrome 131.0.6778.87
  ✓ CfT API: reachable
  ✓ Firefox FTP: reachable
  ✓ Edge API: reachable
  ✓ GitHub API: reachable
```

!!! warning "Disk space"
    Browser binaries are large (150-200 MB each). If you install multiple
    browsers and drivers, the cache can grow quickly. Use `browserget remove`
    to clean up unused artifacts, or simply delete the cache directory and
    reinstall what you need.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSERGET_CACHE_DIR` | OS-specific | Cache directory path |
| `BROWSERGET_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `BROWSERGET_MAX_RETRIES` | `3` | Maximum HTTP retry attempts |
| `BROWSERGET_VERBOSE` | `false` | Enable verbose logging |
