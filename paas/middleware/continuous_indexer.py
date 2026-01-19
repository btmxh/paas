from sys import stderr
from typing import Dict, Iterable

from paas.middleware.base import Middleware, Runnable
from paas.models import ProblemInstance, Schedule, Task, Assignment


class ContinuousIndexMap:
    def __init__(self, indices: Iterable[int]):
        self.old_to_new: Dict[int, int] = {}
        self.new_to_old: Dict[int, int] = {}
        for new_id, old_id in enumerate(sorted(indices)):
            self.old_to_new[old_id] = new_id
            self.new_to_old[new_id] = old_id

    def to_continuous(self, old_id: int) -> int:
        return self.old_to_new[old_id]

    def from_continuous(self, new_id: int) -> int:
        return self.new_to_old[new_id]

    def __contains__(self, old_id: int) -> bool:
        return old_id in self.old_to_new


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
        task_ids = ContinuousIndexMap(problem.tasks.keys())
        team_ids = ContinuousIndexMap([team.id for team in problem.teams.values()])

        new_tasks: Dict[int, Task] = {}
        for old_id, old_task in problem.tasks.items():
            new_id = task_ids.to_continuous(old_id)

            # Remap dependencies
            # We filter out dependencies that are not in the current problem
            # (though they ideally shouldn't exist if problem is consistent)
            new_predecessors = [
                task_ids.to_continuous(p)
                for p in old_task.predecessors
                if p in task_ids
            ]
            new_successors = [
                task_ids.to_continuous(s) for s in old_task.successors if s in task_ids
            ]
            compatible_teams = {
                team_ids.to_continuous(tid): cost
                for tid, cost in old_task.compatible_teams.items()
                if tid in team_ids
            }

            new_task = Task(
                id=new_id,
                duration=old_task.duration,
                predecessors=new_predecessors,
                successors=new_successors,
                compatible_teams=compatible_teams,
            )
            new_tasks[new_id] = new_task

        new_problem = ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams={team_ids.to_continuous(t.id): t for t in problem.teams.values()},
        )

        # 3. Run next runnable
        schedule = next_runnable.run(new_problem, time_limit)

        # 4. Map result back
        new_assignments = []
        for assignment in schedule.assignments:
            # Task IDs in assignment are new IDs
            if assignment.task_id in task_ids.new_to_old:
                original_id = task_ids.from_continuous(assignment.task_id)
                original_team_id = team_ids.from_continuous(assignment.team_id)
                new_assignments.append(
                    Assignment(
                        task_id=original_id,
                        team_id=original_team_id,
                        start_time=assignment.start_time,
                    )
                )
            else:
                print(
                    f"Warning: Assignment for unknown task ID {assignment.task_id} ignored.",
                    file=stderr,
                )

        return Schedule(assignments=new_assignments)
