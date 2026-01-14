# Gemini AI Agent - Project Reference

This document serves as a reference for the Gemini AI agent working on the PaaS project.

## Environment Setup

- **OS:** Linux
- **Dependency Management:** Managed via `uv` within Docker (`Dockerfile` provided).
- **Tooling:** Nix with `direnv` is used for **tooling only** (LSPs, formatting, linting).
- **NOTE:** The Nix environment **no longer provides a Python runtime or `uv`**. These must be accessed via Docker or an external environment.

## Development Workflow

### Python Execution & Dependencies
- **NO RUNTIME:** You currently do **not** have access to a Python interpreter or `uv` in the Nix development shell.
- **SKIP TESTS/TYPECHECKS:** Do not attempt to run `python3 -m unittest` or `ty check` locally unless a runtime environment (like Docker) is explicitly provided.
- **Dependencies:** Managed via `pyproject.toml` and `uv.lock`. `uv` is used inside the Docker image.
- **Typing:** Maintain compatibility with Python 3.8. Use legacy types from the `typing` module (e.g., `List[T]`, `Dict[K, V]`).

### Code Quality
- **Pre-commit:** Standalone configuration in `.pre-commit-config.yaml`. It runs `ruff`, `check-yaml`, and other formatters.
- **Linting:** `ruff` is still available in the Nix environment for quick checks.
- If a commit fails due to pre-commit checks, fix the issues and re-commit.

### Git Strategy
- Always work on a separate feature branch, prefixed with `ai/*`.
- Before finishing your work, commit your changes (if any, make sure to commit
  to a feature branch and not the master branch).
- Keep the feature branch updated by pulling changes from the `master` branch.
- Commit messages should follow the project's style (e.g., conventional commits).

## Problem Statement
The project involves Project Assignment and Scheduling (PaaS), optimizing:
1. Maximal number of tasks scheduled.
2. Minimal completion time.
3. Minimal total cost.

Refer to `STATEMENT.md` for full details.
