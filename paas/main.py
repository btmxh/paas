import sys
from paas.parser import parse_input
from paas.solvers.cp_solver import CPSolver
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.dependency_pruner import DependencyPruner
from paas.middleware.base import Pipeline


def main():
    try:
        instance = parse_input(sys.stdin)

        # Setup middleware pipeline
        pipeline = Pipeline(
            middlewares=[
                ImpossibleTaskRemover(),
                CycleRemover(),
                DependencyPruner(),
            ],
            solver=CPSolver(),
        )

        # Run the pipeline
        schedule = pipeline.run(instance)

        # Output the results
        print(len(schedule.assignments))
        for assignment in schedule.assignments:
            print(f"{assignment.task_id} {assignment.team_id} {assignment.start_time}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
