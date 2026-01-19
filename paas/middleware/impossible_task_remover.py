import sys
from paas.middleware.base import MapProblem
from paas.models import ProblemInstance, Task


class ImpossibleTaskRemover(MapProblem):
    """
    Middleware that removes tasks with no compatible teams.
    It also cleans up dependencies: if a task is removed, it is removed
    from the predecessor/successor lists of other tasks (Soft Dependency).
    """

    def map_problem(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> ProblemInstance:
        tasks = problem.tasks
        to_remove = set()

        for t_id, task in tasks.items():
            if not task.compatible_teams:
                to_remove.add(t_id)

        new_tasks = {}

        for t_id, task in tasks.items():
            if t_id in to_remove:
                continue

            # Create a new task instance to avoid modifying the original
            # Filter out removed tasks from dependencies
            new_preds = [p for p in task.predecessors if p not in to_remove]
            new_succs = [s for s in task.successors if s not in to_remove]

            new_task = Task(
                id=task.id,
                duration=task.duration,
                predecessors=new_preds,
                successors=new_succs,
                compatible_teams=task.compatible_teams.copy(),
            )
            new_tasks[t_id] = new_task

        print(
            f"ImpossibleTaskRemover: Removed {len(to_remove)} tasks (no compatible teams).",
            file=sys.stderr,
        )

        return ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams=problem.teams,
        )
