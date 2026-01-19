from paas.middleware import ContinuousIndexer
from paas.middleware.base import Pipeline
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.dependency_pruner import DependencyPruner
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.parser import parse_input
from paas.solvers import CPSolver
import sys


def main():
    instance = parse_input(sys.stdin)
    middlewares = [
        ImpossibleTaskRemover(),
        CycleRemover(),
        DependencyPruner(),
        ContinuousIndexer(),
    ]
    pipeline = Pipeline(middlewares, CPSolver())
    solution = pipeline.run(instance)
    solution.print()


if __name__ == "__main__":
    main()
