import random
import sys
from typing import List, Dict, Tuple

from paas.middleware.base import MapResult
from paas.models import ProblemInstance, Schedule, Assignment
from paas.time_budget import TimeBudget


class HillClimbingMiddleware(MapResult):
    """
    Middleware that applies Hill Climbing (Local Search) to refine a schedule.

    It reconstructs a task execution order from the schedule, then iteratively
    explores neighbors by:
    1. Swapping tasks in the execution order.
    2. Changing team assignments.

    It uses a First-Improvement strategy.
    """

    def __init__(
        self,
        iterations: int = 50,
        time_factor: float = 0.5,
        seed: int = 42,
    ):
        super().__init__(time_factor)
        self.iterations = iterations
        self.seed = seed

    def map_result(
        self,
        problem: ProblemInstance,
        result: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        """
        Apply Hill Climbing to the result schedule.
        """
        if not result.assignments:
            return result

        random.seed(self.seed)

        # 1. Convert Schedule to internal representation (Order + Team Map)
        # Sort assignments by start_time to get a valid execution order
        sorted_assignments = sorted(result.assignments, key=lambda a: a.start_time)

        task_order = [a.task_id for a in sorted_assignments]
        team_assignment = {a.task_id: a.team_id for a in sorted_assignments}

        # Include unscheduled tasks
        scheduled_ids = set(task_order)
        all_task_ids = set(problem.tasks.keys())
        missing_ids = list(all_task_ids - scheduled_ids)
        random.shuffle(missing_ids)

        full_task_order = task_order + missing_ids

        for tid in missing_ids:
            compat = list(problem.tasks[tid].compatible_teams.keys())
            if compat:
                team_assignment[tid] = random.choice(compat)

        current_order = full_task_order
        current_teams = team_assignment

        # Evaluate initial
        current_assignments, current_score = self._evaluate(
            problem, current_order, current_teams
        )

        with TimeBudget(time_limit) as budget:
            for _ in range(self.iterations):
                if budget.is_expired():
                    break
                improved = False

                # 1. Swap Neighbors
                n = len(current_order)
                if n >= 2:
                    swap_attempts = min(n, 20)
                    for _ in range(swap_attempts):
                        if budget.is_expired():
                            break
                        i, j = random.sample(range(n), 2)

                        neighbor_order = list(current_order)
                        neighbor_order[i], neighbor_order[j] = (
                            neighbor_order[j],
                            neighbor_order[i],
                        )

                        _, neighbor_score = self._evaluate(
                            problem, neighbor_order, current_teams
                        )

                        if neighbor_score < current_score:
                            current_order = neighbor_order
                            current_score = neighbor_score
                            improved = True
                            break

                if improved:
                    continue

                # 2. Team Change Neighbors
                tasks_to_try = random.sample(
                    list(current_teams.keys()), min(len(current_teams), 10)
                )
                for tid in tasks_to_try:
                    if budget.is_expired():
                        break
                    if tid not in problem.tasks:
                        continue

                    current_team = current_teams[tid]
                    compat = list(problem.tasks[tid].compatible_teams.keys())

                    better_found = False
                    for new_team in compat:
                        if budget.is_expired():
                            break
                        if new_team == current_team:
                            continue

                        neighbor_teams = dict(current_teams)
                        neighbor_teams[tid] = new_team

                        _, neighbor_score = self._evaluate(
                            problem, current_order, neighbor_teams
                        )

                        if neighbor_score < current_score:
                            current_teams = neighbor_teams
                            current_score = neighbor_score
                            improved = True
                            better_found = True
                            break

                    if better_found:
                        break

                if not improved:
                    break

        best_assignments, _ = self._evaluate(problem, current_order, current_teams)
        return Schedule(assignments=best_assignments)

    def _evaluate(
        self,
        problem: ProblemInstance,
        task_order: List[int],
        team_assignment: Dict[int, int],
    ) -> Tuple[List[Assignment], Tuple[int, int, int]]:
        """
        Decode and evaluate.
        Returns (assignments, (neg_count, makespan, cost))
        """
        assignments = self._decode(problem, task_order, team_assignment)

        if not assignments:
            return [], (0, sys.maxsize, sys.maxsize)

        count = len(assignments)
        makespan = 0
        cost = 0

        for a in assignments:
            task = problem.tasks[a.task_id]
            finish = a.start_time + task.duration
            if finish > makespan:
                makespan = finish

            c = task.compatible_teams.get(a.team_id, 10**12)
            cost += c

        return assignments, (-count, makespan, cost)

    def _decode(
        self,
        problem: ProblemInstance,
        task_order: List[int],
        team_assignment: Dict[int, int],
    ) -> List[Assignment]:
        """
        Greedy decoder respecting task_order priorities.
        """
        scheduled_finishes: Dict[int, int] = {}
        assignments: List[Assignment] = []

        # Track team availability
        team_available = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        # We iterate through task_order.
        # But we can only schedule a task if its predecessors are done.
        # Standard list scheduling with priority list:
        # Loop through list, pick first ready task, schedule it, repeat.

        pending = list(task_order)

        while pending:
            progress = False
            next_pending = []

            for task_id in pending:
                # Check if already scheduled (shouldn't happen with correct logic but safety)
                if task_id in scheduled_finishes:
                    continue

                task = problem.tasks.get(task_id)
                if not task:
                    continue

                # Check predecessors
                preds_ready = True
                preds_time = 0
                for p in task.predecessors:
                    if p not in scheduled_finishes:
                        preds_ready = False
                        break
                    if scheduled_finishes[p] > preds_time:
                        preds_time = scheduled_finishes[p]

                if not preds_ready:
                    next_pending.append(task_id)
                    continue

                # Schedule
                team_id = team_assignment.get(task_id)
                if team_id is None:
                    # Should not happen if initialized correctly
                    continue

                if team_id not in team_available:
                    # Invalid team?
                    continue

                start_time = max(team_available[team_id], preds_time)
                assignments.append(Assignment(task_id, team_id, start_time))

                finish = start_time + task.duration
                scheduled_finishes[task_id] = finish
                team_available[team_id] = finish

                progress = True

            if not progress:
                # Cycle or unresolvable dependencies (e.g. missing preds in list)
                break

            pending = next_pending

        return assignments
