# Parsers

browserget talks to four different upstream APIs to resolve browser and driver
versions. Each API has a different format, so browserget uses dedicated parsers
that transform raw responses into `ResolvedVersion` objects.

## Upstream APIs

### Chrome for Testing (CfT)

Chrome and ChromeDriver versions are resolved from the Chrome for Testing JSON API.

- **URL**: `https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json`
- **Format**: JSON
- **Structure**: A `versions` array, each entry contains a `version` string and a
  `downloads` object with platform-specific URLs for `chrome` and `chromedriver`.
- **Checksums**: Provided as `checksum` fields in the download entries.

The parser (`parsers/cft.py`) filters versions by target (chrome or chromedriver)
and platform string (e.g. `win64`, `linux64`, `mac-arm64`). Versions are sorted
in descending order so the first match is the latest.

### Firefox FTP

Firefox versions are scraped from the Mozilla FTP directory listing.

- **URL**: `https://ftp.mozilla.org/pub/firefox/releases/`
- **Format**: HTML directory listing
- **Structure**: The page contains `<a>` tags with version directory names (e.g.
  `131.0/`, `130.0/`, `128.0esr/`).
- **Checksums**: Available via separate checksum files in each version directory.

The parser (`parsers/firefox.py`) uses regex to extract version strings from the
HTML, handles `esr` (Extended Support Release) variants, and constructs download
and checksum URLs based on the version and platform.

### Edge Updates API

Edge browser versions are resolved from the Microsoft Edge Updates API.

- **URL**: `https://edgeupdates.microsoft.com/api/products`
- **Format**: JSON
- **Structure**: An array of products, each with a `Product` name and a
  `Releases` list. Each release contains `Platform`, `Architecture`,
  `ProductVersion`, and an `Artifacts` array. Each artifact has `Location`,
  `Hash`, and `HashAlgorithm` fields.
- **Checksums**: Provided as `Hash` and `HashAlgorithm` fields in the artifact
  entries.

The parser (`parsers/edge.py`) only supports the `Stable` product and the
`edge` target. It filters by the mapped `Platform` and `Architecture` and
returns the first artifact for each matching release.

### EdgeDriver CDN

EdgeDriver is **not** available from the Edge Updates API. It is distributed
from a separate CDN:

- **Latest version URL**: `https://msedgedriver.microsoft.com/LATEST_STABLE`
- **Download URL**: `https://msedgedriver.microsoft.com/{version}/edgedriver_{platform}.zip`
- **Format**: Zip archive, no checksums published.

### GeckoDriver GitHub releases

GeckoDriver versions are resolved from the GitHub Releases API.

- **URL**: `https://api.github.com/repos/mozilla/geckodriver/releases`
- **Format**: JSON
- **Structure**: An array of release objects, each with a `tag_name` (e.g.
  `v0.35.0`) and an `assets` array containing download URLs.
- **Checksums**: Not provided by GitHub releases. GeckoDriver downloads skip
  checksum verification.

The parser (`parsers/geckodriver.py`) maps GitHub asset names to internal
platform strings (e.g. `geckodriver-v0.35.0-win64.zip` to `win64`). The `v`
prefix in `tag_name` is stripped for version comparison.

## Platform mapping

browserget detects the current OS and architecture, then maps to the platform
string expected by each upstream API:

| Internal platform | CfT | Firefox FTP | Edge API | GeckoDriver |
|-------------------|-----|-------------|----------|-------------|
| `win64` | `win64` | `win64/` | `win64` | `win64.zip` |
| `win32` | `win32` | `win32/` | `win64` | `win32.zip` |
| `linux64` | `linux64` | `linux-x86_64/` | `linux64` | `linux64.tar.gz` |
| `linux-arm64` | `linux64` | `linux-aarch64/` | `linux64` | `linux-aarch64.tar.gz` |
| `mac-arm64` | `mac-arm64` | `mac/` | `mac-arm64` | `macos-aarch64.tar.gz` |
| `mac-x64` | `mac-x64` | `mac/` | `mac-x64` | `macos.tar.gz` |

The `map_platform()` function in `platform.py` handles this translation.

## Version resolution

browserget supports three version input modes:

| Mode | Example | Behavior |
|------|---------|----------|
| Latest | (no `--version`) | Returns the most recent version from the API |
| Exact | `131.0.6778.87` | Finds the exact matching version |
| Milestone | `131` | Returns the latest patch within the milestone |

### Resolution logic

```
parse input
  │
  ├─ no version → return latest (first in sorted descending list)
  │
  ├─ exact version (4 parts: X.Y.Z.W)
  │   └─ find exact match in version list
  │       └─ not found → VersionNotFoundError
  │
  └─ milestone (1 part: X)
      └─ filter versions starting with "X."
          └─ return first (latest patch)
              └─ none found → VersionNotFoundError
```

!!! note "GeckoDriver does not match Firefox"
    Unlike ChromeDriver, GeckoDriver does not version-match with Firefox. The
    `--for firefox` flag for `geckodriver` simply installs the latest GeckoDriver
    regardless of the Firefox version. This is by design — GeckoDriver maintains
    its own release cadence independent of Firefox versions.
