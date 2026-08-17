# Architecture overview

browserget is designed as a modular, minimal-dependency CLI tool. Every module has
a single responsibility and can be tested in isolation.

## Module diagram

```
┌────────────────────────────────────────────────────────────┐
│                         cli.py                             │
│      Typer app, command parsing, output formatting           │
└────────────┬───────────────────────────┬───────────────────┘
             │                           │
     ┌───────▼────────┐        ┌─────────▼──────────┐
     │  installers/   │        │    registry.py     │
     │  chrome.py     │        │   (JSON store)     │
     │  firefox.py    │        └────────────────────┘
     │  edge.py       │
     │  chromedriver  │
     │  geckodriver   │
     │  edgedriver    │
     └───┬───┬───┬────┘
         │   │    │
  ┌──────▼┐  │  ┌─▼───────┐  ┌─────────────┐
  │http.py│  │  │parsers/ │  │  cache.py   │
  │(async)│  │  │ cft.py  │  │   (paths)   │
  └───────┘  │  │firefox  │  └─────────────┘
             │  │edge.py  │
             │  │gecko.py │
             │  └─────────┘
        ┌────┴────┐
        │ system.py │
        │ platform.py
        └───────────┘
```

## Install flow

Every install follows the same pipeline:

```
resolve → download → verify checksum → extract → register
```

1. **Resolve** — Query the upstream API to find the requested version and get
   a direct download URL. Parsers are pure functions that transform API
   responses into `ResolvedVersion` objects.

2. **Download** — The `HttpClient` downloads the archive to a temporary
   directory inside the cache. Failed downloads are retried with exponential
   backoff.

3. **Verify checksum** — If the upstream provides a checksum (SHA-256 or
   SHA-512), the downloaded archive is verified before extraction. A mismatch
   raises `ChecksumMismatchError` and the partial download is cleaned up.

4. **Extract** — The archive is extracted into the final cache directory
   (`{cache_dir}/{name}/{version}/`). The executable is located within the
   extracted files.

5. **Register** — The artifact is added to the JSON registry with its name,
   version, path, install timestamp, and checksum.

## Separation: parsers vs installers

| Layer | Responsibility | I/O? |
|-------|---------------|------|
| `parsers/` | Parse upstream API responses into `ResolvedVersion` objects | No — pure functions |
| `installers/` | Orchestrate resolve → download → verify → extract → register | Yes — network + disk |

Parsers are pure functions that take API response data (JSON or HTML) and return
`ResolvedVersion` objects. They never make HTTP requests themselves. This makes
them trivially testable with fixture files.

Installers own the full I/O lifecycle. They call parsers, use `HttpClient` for
downloads, interact with the `Registry`, and manage the cache filesystem.

## Registry format

The registry is a single JSON file at `{cache_dir}/registry.json`:

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
  ]
}
```

- Keys are artifact names (`chrome`, `chromedriver`, etc.)
- Values are arrays of `InstalledArtifact` entries (supports multiple versions)
- Writes are atomic via `tempfile` + `os.replace`
- Corrupted JSON is handled gracefully — the registry loads as empty and logs a warning

## Cache layout

```
{cache_dir}/
├── registry.json
├── {name}/
│   └── {version}/
│       └── (extracted binary + supporting files)
└── downloads/
    └── (temporary download directory, cleaned after extraction)
```

Each artifact gets its own subdirectory keyed by name and version. This allows
multiple versions of the same target to coexist. The `downloads/` directory is
used for temporary archive files and is cleaned up after each install.

## Key design decisions

- **Async HTTP with `urllib`** — Uses `urllib.request` wrapped in
  `asyncio.to_thread` to avoid adding `httpx` or `aiohttp` as dependencies.
- **Typer for CLI** — Provides type-safe argument parsing with minimal overhead.
- **Dynamic installer creation** — Installers are created on demand via
  `_create_installer()` to avoid importing all installer modules at startup.
- **Event loop management** — The `_run_async()` helper creates a fresh event
  loop for each command invocation, ensuring compatibility with `pytest-asyncio`.
