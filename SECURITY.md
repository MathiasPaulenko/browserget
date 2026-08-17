# Security Policy

## Supported Versions

Only the latest release of browserget receives security updates.

| Version | Supported |
| ------- | --------- |
| latest   | ✅        |
| < latest | ❌        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately by emailing
**mathias.paulenko@outlook.com** with the subject line
`browserget Security Report`.

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce
- Affected versions (if known)
- Any suggested mitigations

You will receive a response within **48 hours** acknowledging receipt. A fix or
mitigation will be prioritized based on severity.

## Security Considerations Specific to browserget

browserget downloads and executes browser binaries from external sources. This
introduces specific security considerations:

### External Downloads

browserget fetches browser archives and drivers from:

- Google Chrome for Testing (`googlechromelabs.github.io`,
  `storage.googleapis.com`)
- Mozilla Firefox (`ftp.mozilla.org`)
- Microsoft Edge (`edgeupdates.microsoft.com`)
- GitHub Releases (`api.github.com`)

All downloads use HTTPS. If a download source is compromised, an attacker could
serve a malicious binary.

### Checksum Verification

browserget verifies checksums **when the upstream source provides them**:

- Chrome for Testing: SHA-256 verified
- Firefox: SHA-512 verified
- Edge: SHA-256 verified
- GeckoDriver: no checksums available — download is not verified (warning
  logged)

If a checksum mismatch is detected, the downloaded file is deleted and an error
is raised. The download is **not** retried automatically.

### Binary Execution

browserget does not execute downloaded binaries itself. It installs them to a
cache directory and provides paths for other tools to use. Those tools are
responsible for sandboxing and execution safety.

The installed binaries inherit the permissions of the user who runs them.
browserget does not run browsers with elevated privileges.

### Network Access

browserget makes outbound HTTP requests to the APIs listed above. No inbound
connections are opened. Proxy settings are respected via standard environment
variables (`HTTPS_PROXY`, `HTTP_PROXY`).
