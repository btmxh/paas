# Gemini AI Agent - Project Reference

This document serves as a reference for the Gemini AI agent working on the PaaS project.

## Environment Setup

- **OS:** Linux
- **Dependency Management:** Nix with `direnv`.
- **Tooling:** The project uses `flake.nix` and `.envrc` to manage the development environment automatically. NOTE: once the environment change, the CLI AI agent will be manually reload, the AI agent should not reload and find any new binaries by itself.
- **Python:** Managed via `uv`.

## Development Workflow

### Python Dependencies
- **DO NOT** use `uv` anymore.
- **DO NOT** use raw `pip` calls if possible.
- **DO NOT** manually edit `pyproject.toml` for dependencies.
- **DO NOT** use the modern built-in typings such as `list[T]` and `dict[K, V]`.
  As this project maintains compatibility with Python 3.8.
- **DO** use typings as much as possible. Typechecks will be run on CI, so avoid
  writing typing-unsafe code as much as possible. Run `ty check` (which uses
  Astral's new `ty` type-checker) to check the project for potential typing
  errors.
- **DO** run unit tests via `python3 -m unittest discover tests`
- **DO** use the legacy types such as `list[T]` and `dict[K, V]` from the
  `typing` module.
- **DO** use `python3 -m paas.main` to execute the application.
- **NOTE:** `or-tools` and other major dependencies are now managed via the `nix-shell` environment.

### Code Quality
- Pre-commit checks (defined in flake.nix, which is then used to generate the .pre-commit-config.yaml file) are in place for formatting and linting. Fixable problems (formatting) are automatically fixed, so adding the new changes and rerunning `git commit` should address those.
- If a commit fails due to these checks, ensure the issues are fixed before attempting to commit again.
- Pushing to remote branches is handled manually by the user.

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
