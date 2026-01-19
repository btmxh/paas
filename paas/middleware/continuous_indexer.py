from typing import Dict

from paas.middleware.base import Middleware, Runnable
from paas.models import ProblemInstance, Schedule, Task, Assignment


class ContinuousIndexer(Middleware):
    """
    Middleware that relabels task indices to be continuous (0 to N-1).
    This is useful after other middlewares (like ImpossibleTaskRemover) have removed tasks,
    leaving gaps in the task IDs. Solvers that rely on array indexing need continuous IDs.
    It maps the problem to new indices, runs the solver, and then maps the result back to original indices.
    """

    def run(
        self,
        problem: ProblemInstance,
        next_runnable: Runnable,
        time_limit: float = float("inf"),
    ) -> Schedule:
        # 1. Create mappings
        # Sort keys to ensure deterministic mapping
        original_ids = sorted(problem.tasks.keys())
        old_to_new = {old_id: new_id for new_id, old_id in enumerate(original_ids)}
        new_to_old = {new_id: old_id for new_id, old_id in enumerate(original_ids)}

        # 2. Create new ProblemInstance
        new_tasks: Dict[int, Task] = {}
        for old_id in original_ids:
            original_task = problem.tasks[old_id]
            new_id = old_to_new[old_id]

            # Remap dependencies
            # We filter out dependencies that are not in the current problem
            # (though they ideally shouldn't exist if problem is consistent)
            new_predecessors = [
                old_to_new[p] for p in original_task.predecessors if p in old_to_new
            ]
            new_successors = [
                old_to_new[s] for s in original_task.successors if s in old_to_new
            ]

            new_task = Task(
                id=new_id,
                duration=original_task.duration,
                predecessors=new_predecessors,
                successors=new_successors,
                compatible_teams=original_task.compatible_teams.copy(),
            )
            new_tasks[new_id] = new_task

        new_problem = ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams=problem.teams,  # Teams are not modified
        )

        # 3. Run next runnable
        schedule = next_runnable.run(new_problem, time_limit)

        # 4. Map result back
        new_assignments = []
        for assignment in schedule.assignments:
            # Task IDs in assignment are new IDs
            if assignment.task_id in new_to_old:
                original_id = new_to_old[assignment.task_id]
                new_assignments.append(
                    Assignment(
                        task_id=original_id,
                        team_id=assignment.team_id,
                        start_time=assignment.start_time,
                    )
                )
            else:
                # This could happen if the solver returns IDs that were not in the problem
                # (e.g. if it invented tasks). We just ignore or pass through?
                # Safest is to ignore or log warning. Here we ignore.
                pass

        return Schedule(assignments=new_assignments)
