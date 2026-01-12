import sys
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Runnable


class GreedyMinStartTimeSolver(Runnable):
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

    def run(self, problem: ProblemInstance) -> Schedule:
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

        # MAIN LOOP:
        # Greedily pick tasks based on
        while len(scheduled_task_ids) < len(tasks):
            global_best_finish = INF
            global_best_start = INF  # tie-breaking
            global_best_team = -1
            global_best_task = -1
            global_best_cost = INF

            found_candidate = False

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
                min_start_from_preds = max(
                    (task_completion_time[p] for p in task.predecessors), default=0
                )

                # Evaluate all compatible teams
                for team_id, cost in task.compatible_teams.items():
                    team_avail = team_available_time[team_id]

                    # The task can start only when the team is free AND dependencies are done.
                    start_time = max(team_avail, min_start_from_preds)
                    finish_time = start_time + task.duration

                    # Update global best if this option is better
                    if finish_time < global_best_finish:
                        global_best_finish = finish_time
                        global_best_start = start_time
                        global_best_team = team_id
                        global_best_task = task_id
                        global_best_cost = cost
                        found_candidate = True
                    # Tie-breaking
                    elif finish_time == global_best_finish:
                        # Minimize idle time!
                        # If two tasks finish at the same time, pick the one that
                        # starts EARLIER.
                        # Why? If Task A starts at 2 and finishes at 10,
                        # and Task B starts at 8 and finishes at 10...
                        # Picking Task B creates a wasted idle gap [2,8] on the team.
                        if start_time < global_best_start:
                            global_best_start = start_time
                            global_best_team = team_id
                            global_best_task = task_id
                            global_best_cost = cost
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
