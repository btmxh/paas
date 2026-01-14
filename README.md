# PaaS: Project Assignment and Scheduling

HUST K67 Combinatorial Optimization Project.

### Original Implementations
- [GA](https://github.com/NguyenHoangXuanSon/tulkh_2025.1)
- [PSO & ACO](https://github.com/hungmanhbui1604/project-assignment-and-scheduling)
- [CP](https://github.com/hongdangn/scheduling/blob/main/new_cp_model.py)

---

## 🚀 Commands
- **Run**: `python3 -m paas.main < input.txt`
- **Test**: `python3 -m unittest discover tests`
- **Type Check**: `ty check`
- **Setup**: `uv sync` (Recommended) or `direnv allow` (Legacy Nix support)

---

## 🏗️ Architecture

### 1. Models (`paas/models.py`)
`Task`, `Team`, `ProblemInstance`, `Schedule`. Uses Python 3.8 compatible type hints.

### 2. Solvers (`paas/solvers/`)
Any class with `run(problem) -> Schedule`.
- `CPSolver`: Optimal (OR-Tools).
- `GreedyMinStartTimeSolver`: Fast heuristic.
- `ACOSolver`, `PSOSolver`, `GASolver`: Metaheuristics.

### 3. Middlewares (`paas/middleware/`)
Preprocessing layers. **Order is critical.**
Current pipeline in `main.py`:
1. `CycleRemover`: Breaks dependency cycles.
2. `ImpossibleTaskRemover`: Removes tasks no team can do.
3. `DependencyPruner`: Cleans up tasks whose predecessors were removed in previous steps.

---

## 🛠️ Contributing

- **New Solver**: Implement `run(problem: ProblemInstance) -> Schedule` in `paas/solvers/`.
- **New Middleware**: Inherit from `MapProblem` or `MapResult` in `paas/middleware/base.py`.
- **Dependencies**: Use `uv`. Manage dependencies via `pyproject.toml`.
- **Formatting**: Handled by `ruff` on commit.
- **Python**: 3.8 compatibility is mandatory (`List[T]` not `list[T]`).
