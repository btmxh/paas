from paas.middleware.base import MapProblem
from paas.models import ProblemInstance


class ImpossibleTaskRemover(MapProblem):
    """
    Middleware that removes tasks with no compatible teams.
    """

    def map_problem(self, problem: ProblemInstance) -> ProblemInstance:
        tasks = problem.tasks
        to_remove = set()

        for t_id, task in tasks.items():
            if not task.compatible_teams:
                to_remove.add(t_id)

        if not to_remove:
            return problem

        new_tasks = {
            t_id: task for t_id, task in tasks.items() if t_id not in to_remove
        }

        print(
            f"ImpossibleTaskRemover: Removed {len(to_remove)} tasks (no compatible teams)."
        )

        return ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams=problem.teams,
        )
