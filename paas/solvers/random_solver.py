import random
from typing import Dict, List

from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver


class RandomSolver(Solver):
    """
    Implements a random scheduling strategy.

    It guarantees that all tasks are scheduled by following a topological order,
    but the choice of which available task to schedule next and which team to assign
    is made randomly.
    """

    def __init__(self, time_factor: float = 0.0, seed: int = None):
        super().__init__(time_factor)
        if seed is not None:
            random.seed(seed)

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        tasks = problem.tasks
        teams = problem.teams

        # 1. Initialize State
        team_available_time = {
            t_id: team.available_from for t_id, team in teams.items()
        }
        task_completion_time: Dict[int, int] = {}
        assignments: List[Assignment] = []

        # 2. Calculate In-Degrees (number of unscheduled predecessors)
        in_degree: Dict[int, int] = {t_id: 0 for t_id in tasks}
        for t_id, task in tasks.items():
            for p in task.predecessors:
                in_degree[t_id] += 1

        # 3. Initialize Ready Tasks (tasks with in-degree 0)
        ready_tasks = [t_id for t_id, deg in in_degree.items() if deg == 0]

        scheduled_count = 0
        num_tasks = len(tasks)

        while scheduled_count < num_tasks:
            if not ready_tasks:
                # If we have no ready tasks but haven't scheduled everything,
                # it means there's a cycle or the graph isn't a DAG.
                # We break to avoid an infinite loop.
                break

            # 4. Pick Random Task
            # Select random index from ready_tasks
            idx = random.randrange(len(ready_tasks))
            # Efficient remove: swap with last and pop
            ready_tasks[idx], ready_tasks[-1] = ready_tasks[-1], ready_tasks[idx]
            task_id = ready_tasks.pop()

            task = tasks[task_id]

            # 5. Pick Random Team
            compatible_teams = list(task.compatible_teams.keys())
            if not compatible_teams:
                # If a task has no compatible teams, we can't schedule it.
                # Skip it (and its successors will never become ready).
                continue

            team_id = random.choice(compatible_teams)

            # 6. Calculate Start Time
            # Start time must be >= team availability
            # AND >= completion time of all predecessors
            min_start_from_preds = 0
            if task.predecessors:
                min_start_from_preds = max(
                    task_completion_time.get(p, 0) for p in task.predecessors
                )

            team_avail = team_available_time[team_id]
            start_time = max(team_avail, min_start_from_preds)
            finish_time = start_time + task.duration

            # 7. Commit Assignment
            assignments.append(Assignment(task_id, team_id, start_time))
            task_completion_time[task_id] = finish_time
            team_available_time[team_id] = finish_time
            scheduled_count += 1

            # 8. Unlock Successors
            for succ_id in task.successors:
                if succ_id in in_degree:
                    in_degree[succ_id] -= 1
                    if in_degree[succ_id] == 0:
                        ready_tasks.append(succ_id)

        return Schedule(assignments)
