import sys
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver


class GreedyMinStartTimeSolver(Solver):
    """
    Implements a greedy scheduling strategy that prioritizes minimizing the start time of tasks.

    The algorithm proceeds in two phases:
    1.  **Root Tasks**: Immediately schedule all tasks that have no dependencies (roots).
        For each root task, choose the team that allows the earliest start time (minimizing cost as a tie-breaker).
    2.  **Dependent Tasks**: Iteratively select the next best (task, team) pair.
        In each iteration, consider all unscheduled tasks whose dependencies are fully satisfied.
        Calculate the earliest possible start time for each compatible team (constrained by both
        team availability and predecessor completion times).
        Select the assignment that yields the global minimum start time.
    """

    def __init__(self, time_factor: float = 0.0):
        super().__init__(time_factor)

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        tasks = problem.tasks
        teams = problem.teams
        INF = sys.maxsize

        # Track when each team becomes free.
        # team_available_time: team_id -> time
        team_available_time = {
            t_id: team.available_from for t_id, team in teams.items()
        }

        # Track when each task finishes.
        # task_completion_time: task_id -> time
        task_completion_time = {}

        scheduled_task_ids = set()
        assignments = []

        # --- Phase 1: Schedule Root Tasks ---
        # We explicitly handle tasks with no predecessors first.
        # Sort by ID to ensure deterministic behavior.
        root_task_ids = sorted(
            [tid for tid, task in tasks.items() if not task.predecessors]
        )

        for task_id in root_task_ids:
            task = tasks[task_id]

            # Find the best team for this root task.
            # Since there are no predecessors, start time is determined solely by team availability.
            best_team_id = min(
                task.compatible_teams.keys(),
                key=lambda tid: (
                    team_available_time[tid],  # prefer earlier start time, and then
                    task.compatible_teams[tid],  # prefer lower cost
                ),
                default=None,
            )

            if best_team_id is not None:
                best_start_time = team_available_time[best_team_id]
                # Commit the assignment
                start = best_start_time
                finish = start + task.duration

                team_available_time[best_team_id] = finish
                task_completion_time[task_id] = finish
                scheduled_task_ids.add(task_id)
                assignments.append(Assignment(task_id, best_team_id, start))

        # --- Phase 2: Schedule Remaining Tasks ---
        # Repeatedly find the best (task, team) pair among all currently valid options.
        while len(scheduled_task_ids) < len(tasks):
            global_best_start = INF
            global_best_team = -1
            global_best_task = -1
            global_best_cost = INF

            found_candidate = False

            # Identify candidates: tasks that are not yet scheduled but have all predecessors done.
            # Note: This linear scan in the loop makes the complexity O(N^2 * M).
            # Optimization: We could maintain a "ready set", but for now, we stick to the
            # straightforward logic for clarity.
            unscheduled_ids = [tid for tid in tasks if tid not in scheduled_task_ids]

            if not unscheduled_ids:
                break

            for task_id in unscheduled_ids:
                task = tasks[task_id]

                # Check if dependencies are satisfied
                # If any predecessor is not in task_completion_time, we can't schedule this yet.
                if not all(p in task_completion_time for p in task.predecessors):
                    continue

                # Calculate the earliest time dependencies allow the task to start.
                # It must start after *all* predecessors are finished.
                min_start_from_preds = 0
                if task.predecessors:
                    min_start_from_preds = max(
                        task_completion_time[p] for p in task.predecessors
                    )

                # Evaluate all compatible teams
                for team_id, cost in task.compatible_teams.items():
                    team_avail = team_available_time[team_id]

                    # The task can start only when the team is free AND dependencies are done.
                    start_time = max(team_avail, min_start_from_preds)

                    # Update global best if this option is better
                    if start_time < global_best_start:
                        global_best_start = start_time
                        global_best_team = team_id
                        global_best_task = task_id
                        global_best_cost = cost
                        found_candidate = True
                    elif start_time == global_best_start:
                        if cost < global_best_cost:
                            global_best_team = team_id
                            global_best_task = task_id
                            global_best_cost = cost
                            found_candidate = True

            if found_candidate:
                # Commit the best assignment found in this iteration
                task = tasks[global_best_task]
                start = global_best_start
                finish = start + task.duration

                team_available_time[global_best_team] = finish
                task_completion_time[global_best_task] = finish
                scheduled_task_ids.add(global_best_task)
                assignments.append(
                    Assignment(global_best_task, global_best_team, start)
                )
            else:
                # No valid candidate found.
                # This can happen if there are cycles (deadlock) or impossible constraints
                # (e.g., a task with no compatible teams) that weren't pruned.
                break

        return Schedule(assignments)
