# Contributing to browserget

Thanks for your interest in contributing to browserget! This document covers the
basics to get you up and running.

## Prerequisites

- Python 3.11 or higher
- Git
- A GitHub account

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/browserget.git
cd browserget

# Create a virtual environment
python -m venv .venv-dev
source .venv-dev/bin/activate  # Linux/macOS
# or: .venv-dev\Scripts\activate  # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

## Running Tests

```bash
# Unit tests only
pytest tests/unit/ -v --cov=browserget --cov-report=term-missing

# Integration tests (requires network)
pytest tests/integration/ -m "network and not e2e" -v

# All tests
pytest
```

## Linting and Type Checking

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy browserget/

# Or use the Makefile
make lint format typecheck
```

## Code Style

- **Formatter/Linter**: Ruff (line-length=100)
- **Type checker**: mypy (strict mode)
- **Style**: PEP 8, type hints on all public APIs
- **Docstrings**: Google style for all public functions and classes
- **Imports**: Sorted by ruff (isort-compatible)

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Description |
| --- | --- |
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Code change that neither fixes a bug nor adds a feature |
| `test:` | Adding or correcting tests |
| `chore:` | Build, CI, tooling, dependencies |

Examples:

```
feat: add Firefox ESR channel support
fix: correct platform mapping for Linux ARM64
docs: update install command examples
```

## Pull Request Process

1. **Fork** the repository and create your branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. **Write tests** for your changes. Unit tests go in `tests/unit/`, CLI tests in
   `tests/cli/`.
3. **Ensure all checks pass**:
   ```bash
   ruff check .
   ruff format --check .
   mypy browserget/
   pytest tests/unit/ tests/cli/ -v
   ```
4. **Keep PRs focused** — one feature or fix per PR.
5. **Update documentation** if your change affects user-facing behavior.
6. **Open a PR** with a clear description of what and why.

## Release Process

Releases are automated via GitHub Actions:

1. Update `version` in `pyproject.toml`
2. Update `CHANGELOG.md` with the new version and date
3. Commit: `git commit -am "release: vX.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin main --tags`
6. GitHub Actions builds the wheel, publishes to PyPI, and creates a GitHub Release.

## Questions?

Open an issue or email mathias.paulenko@outlook.com.
