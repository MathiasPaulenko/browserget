.PHONY: install lint format typecheck test test-unit test-integration clean build docs

install:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .
	ruff check . --fix

typecheck:
	mypy browserget/

test: test-unit test-integration

test-unit:
	pytest tests/unit/ tests/cli/ -v --cov=browserget --cov-report=term-missing

test-integration:
	pytest tests/integration/ -m "network and not e2e" -v

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml

build:
	python -m build

docs:
	mkdocs serve
