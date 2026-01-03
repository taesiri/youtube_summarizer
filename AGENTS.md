# Agent Instructions

This repository uses `uv` for all Python environment and dependency management.

## Required

- Use `uv` for installing dependencies, running tools, and managing virtual environments.
- Do not use `pip`, `pipenv`, `poetry`, or `conda` in this repo.
- When adding dependencies, update `pyproject.toml` and use `uv add` or `uv add --dev`.

## Common commands

- Create env / install deps: `uv sync`
- Add a dependency: `uv add <package>`
- Add a dev dependency: `uv add --dev <package>`
- Run tools: `uv run <command>`

## Python version

- Target Python 3.11+ and keep `.python-version` in sync.
