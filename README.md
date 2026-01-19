# PaaS: Project Assignment and Scheduling

HUST K67 Combinatorial Optimization Project.

Project Assignment and Scheduling (PaaS) aims to schedule $N$ tasks to $M$ teams while satisfying precedence constraints, optimizing for:
1. **Maximal tasks scheduled.**
2. **Minimal completion time (makespan).**
3. **Minimal total cost.**

### Original Implementations
- [GA](https://github.com/NguyenHoangXuanSon/tulkh_2025.1)
- [PSO & ACO](https://github.com/hungmanhbui1604/project-assignment-and-scheduling)
- [CP](https://github.com/hongdangn/scheduling/blob/main/new_cp_model.py)

---

## Development Environment

The project uses `uv` for dependency management.

### Local Development (Recommended)

If `uv` is installed on your system (Linux FHS, macOS, Windows):

```bash
# Setup/Update dependencies
uv sync

# Run the solver on an input file
uv run -m paas.main < data/simple/example.txt

# Run all tests
uv run -m unittest discover tests
```

### NixOS users

Since Python support on NixOS can be complex, NixOS users are encouraged to use the provided Docker environment via wrappers in `bin/` (usually already in `PATH` via `direnv`):

```bash
# Setup/Update dependencies
uv sync

# Run the solver on an input file
uv run -m paas.main < data/simple/example.txt

# Run all tests
uv run -m unittest discover tests
```

> **Note**: Maintain compatibility with **Python 3.8** for Hustack submissions (use `typing.List` instead of `list`, etc.).

---

## Submission to Hustack

Hustack requires a single Python file for submission. Use `bundle.py` to merge the project into one script.

1. Create an `entry.py` (or similar) that uses the pipeline:

```python
import sys
from paas.parser import parse_input
from paas.middleware.base import Pipeline
from paas.middleware import (
    ImpossibleTaskRemover, CycleRemover, DependencyPruner,
    ContinuousIndexer, GAMiddleware, TabuSearchMiddleware
)
from paas.solvers import GreedyMinStartTimeSolver

def main():
    instance = parse_input(sys.stdin)
    middlewares = [
        ImpossibleTaskRemover(),
        CycleRemover(),
        DependencyPruner(),
        ContinuousIndexer(),
        GAMiddleware(),
        TabuSearchMiddleware(),
    ]
    # Set check=False to save time during submission
    pipeline = Pipeline(middlewares, GreedyMinStartTimeSolver(), check=False)
    solution = pipeline.run(instance)
    solution.print()

if __name__ == "__main__":
    main()
```

2. Generate the submission file:

```bash
uv run bundle.py entry.py --minify
```

This will create `submission.py` ready for upload to Hustack.

---

## Architecture

### 1. Models (`paas/models.py`)
Core data structures including `Task`, `Team`, `ProblemInstance`, and `Schedule`.

### 2. Solvers (`paas/solvers/`)
Algorithms that generate a schedule for a given problem:
- `CPSolver`: Optimal scheduling using Constraint Programming (OR-Tools).
- `GreedyMinStartTimeSolver`: Simple and fast heuristic.
- `ACOSolver` / `PSOSolver`: Ant Colony and Particle Swarm Optimization.
- `ILPSolver`: Integer Linear Programming approach.

### 3. Middlewares (`paas/middleware/`)
Layers for problem transformation and solution refinement:
- **Preprocessing**: `CycleRemover`, `ImpossibleTaskRemover`, `DependencyPruner`, `ContinuousIndexer`.
- **Optimization**: `GAMiddleware`, `TabuSearchMiddleware`, `HillClimbingMiddleware`.
