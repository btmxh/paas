# PaaS: Project Assignment and Scheduling

HUST K67 Combinatorial Optimization Project.

### Original Implementations
- [GA](https://github.com/NguyenHoangXuanSon/tulkh_2025.1)
- [PSO & ACO](https://github.com/hungmanhbui1604/project-assignment-and-scheduling)
- [CP](https://github.com/hongdangn/scheduling/blob/main/new_cp_model.py)

---

## 🚀 Commands

### Environment Setup
We use **Docker** and **uv** for the runtime environment. Nix is used only for development tooling (LSPs, formatting).

- **Setup Tooling**: `direnv allow` (requires Nix).
- **Setup Runtime**: `docker build -t paas .`

### Running & Testing
Execution is handled via Docker:
- **Run**: `docker run -i paas < input.txt`
- **Test**: `docker run paas python -m unittest discover tests`

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

- **Dependencies**: Managed via `uv`. Edit `pyproject.toml` and rebuild the Docker image.
- **Python Compatibility**: Must maintain compatibility with **Python 3.8**.
- **Formatting**: Handled by `pre-commit` (Standalone).
- **New Solver/Middleware**: Follow the patterns in `paas/solvers/` and `paas/middleware/`.
