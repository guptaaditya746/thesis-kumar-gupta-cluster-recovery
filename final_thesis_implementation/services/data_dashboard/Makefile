.PHONY: install catalog refresh serve validate test lint clean

install:
	uv sync --all-extras

catalog:
	uv run data-dashboard catalog build

refresh:
	uv run data-dashboard catalog refresh

serve:
	uv run data-dashboard serve

validate:
	uv run data-dashboard validate

test:
	uv run pytest

lint:
	uv run ruff check .

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
