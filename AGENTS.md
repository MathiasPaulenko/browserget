# AGENTS.md

Guidelines for AI agents working on the browserget repository.

## Output Artifacts

All design documents, prompts, and reference materials go under `ref/`. This
directory is gitignored and is not part of the published package.

## Development Environment

Use `.venv-dev/` for development:

```bash
python -m venv .venv-dev
source .venv-dev/bin/activate  # Linux/macOS
# or: .venv-dev\Scripts\activate  # Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit tests (no network, no real downloads)
pytest tests/unit -x -v

# CLI tests
pytest tests/cli -x -v

# Integration tests (real network, real downloads)
pytest tests/integration -m "network and not e2e" -v

# Everything except e2e
pytest -m "not e2e" -v
```

## Linting and Type Checking

```bash
ruff check .
ruff format --check .
mypy browserget/
```

## Async Tests

If writing async tests, pytest-asyncio is configured with
`asyncio_mode = "auto"`. No need for `@pytest.mark.asyncio` decorators.

## Project Structure

See `ref/DESIGN.md` section 29 for the complete directory structure and module
responsibilities.

## Conventions

- Python 3.11+ (target `py311`)
- Line length: 100 characters
- Type hints on all public APIs
- Google-style docstrings
- Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`)
- No bare `except`, no wildcard imports, no mutable default arguments
