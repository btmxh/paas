# PaaS: Project Assignment and Scheduling

HUST K67 Combinatorial Optimization Project.

### Original Implementations
- [GA](https://github.com/NguyenHoangXuanSon/tulkh_2025.1)
- [PSO & ACO](https://github.com/hungmanhbui1604/project-assignment-and-scheduling)
- [CP](https://github.com/hongdangn/scheduling/blob/main/new_cp_model.py)

---

## Commands
- **Run**: `uv run -m paas.main < input.txt`
- **Test**: `uv run -m unittest discover tests`
- **Setup**: `uv sync`

### NixOS-specific details (skip this if you don't know what that means)

Since Python support on NixOS is pretty cancer, and that of Google dependencies
is 100x worse, NixOS users should use some form of containerization like Docker.
A docker compose file is provided for convenience.

To run commands on the Docker environment, run:
```
docker compose run --rm dev [COMMAND]

# e.g.
docker compose run --rm dev uv run -m paas.main < data/simple/example.txt
```

To run the `ty` LSP, run it through Docker. The provided `docker-compose.yaml`
files make sure that the source files are mounted to the same exact path as on
your system, however dependency Python files currently are not available since
they only exist on the Docker environment. One could make some custom handling
on Neovim to address this problem.

## Recommended tooling (VSCode)

_(Neo)Vim users should know which tooling to use by now._

- [ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)
- [ty](https://marketplace.visualstudio.com/items?itemName=astral-sh.ty)

The default like Python extensions are not really necessary here, might
even cause like conflicts with CI even.

---

## Submission to Hustack

Since Hustack only accept one singular file for submissions, to submit code
based on this project to the site, there exists a Python script to merge a
file along with its dependencies. This tool is completely written by an AI,
so it might break under certain circumstances.

First, create an `entry.py` file as follows:
```py
from paas.middleware.base import Pipeline
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.dependency_pruner import DependencyPruner
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.continuous_indexer import ContinuousIndexer
from paas.middleware.ga_search import GAMiddleware
from paas.parser import parse_input
from paas.solvers.ga_greedy import GAGreedySolver
import sys


def main():
    instance = parse_input(sys.stdin)
    middlewares = [
        ImpossibleTaskRemover(),
        CycleRemover(),
        DependencyPruner(),
        ContinuousIndexer(),
        GAMiddleware(),
    ]
    # avoid checking when submitting to Hustack
    pipeline = Pipeline(middlewares, GAGreedySolver(), check=False)
    solution = pipeline.run(instance)
    solution.print()
```

This file uses GA to solve the problem, along with three pre-processing
middlewares. Then, run:
```sh
uv run bundle.py entry.py
```

To generate a `submission.py` to be submitted to Hustack.

## Architecture

### 1. Models (`paas/models.py`)
`Task`, `Team`, `ProblemInstance`, `Schedule`. Uses Python 3.8 compatible type hints.

### 2. Solvers (`paas/solvers/`)
Any class with `run(problem) -> Schedule`.
- `CPSolver`: Optimal (OR-Tools).
- `GreedyMinStartTimeSolver`: Fast heuristic.
- `ACOSolver`, `PSOSolver`: Metaheuristics.
- `GAGreedySolver`, `TabuGreedySolver`: Greedy constructive heuristics (optimized).

### 3. Middlewares (`paas/middleware/`)
Preprocessing and postprocessing layers. **Order is critical.**

Two main middleware base implementations:
- `MapProblem`: transform a problem into a more simple one, e.g.
  1. `CycleRemover`: Breaks dependency cycles.
  2. `ImpossibleTaskRemover`: Removes tasks no team can do.
  3. `DependencyPruner`: Cleans up tasks whose predecessors were removed in previous steps.
  4. `ContinuousIndexer`: Re-indexes tasks/teams to 0..N-1 for optimized solvers.
- `MapResult`: improve a solution further (e.g. local search)
  - `GAMiddleware`: Genetic Algorithm refinement.
  - `TabuSearchMiddleware`: Tabu Search refinement.

---

## Contributing

- **New Solver**: Implement `run(problem: ProblemInstance) -> Schedule` in `paas/solvers/`.
- **New Middleware**: Inherit from `MapProblem` or `MapResult` in `paas/middleware/base.py`.
- **Dependencies**: Use `uv`. Manage dependencies via `pyproject.toml`.
- **Formatting**: Handled by `ruff` on commit.
- **Python**: 3.8 compatibility is mandatory if you want to submit code to
  Hustack (`List[T]` not `list[T]`).