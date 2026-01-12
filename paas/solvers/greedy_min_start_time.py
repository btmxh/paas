from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Runnable


class GreedyMinStartTimeSolver(Runnable):
    def run(self, problem: ProblemInstance) -> Schedule:
        # Prepare data structures
        tasks = problem.tasks
        teams = problem.teams

        # 1e9 is used as "infinity" in the original snippet, but for completion_time
        # of unscheduled tasks, it might be better to check for containment in scheduled set.
        # However, to stick close to the logic:
        INF = 1_000_000_000

        # available_time: team_id -> int
        available_time = {t_id: team.available_from for t_id, team in teams.items()}

        # completion_time: task_id -> int
        completion_time = {t_id: INF for t_id in tasks}

        # Track scheduled tasks to avoid reprocessing
        scheduled_tasks = set()
        assignments = []

        # Helper to get cost
        # cost(task, team)
        def get_cost(tid, mid):
            return tasks[tid].compatible_teams.get(mid, INF)

        # 1. Identify tasks with no predecessors
        # Sort for determinism
        roots = sorted([tid for tid, task in tasks.items() if not task.predecessors])

        # 2. Schedule roots eagerly
        for tid in roots:
            task = tasks[tid]

            min_avail_time = INF
            min_avail_team = -1
            min_cost = INF

            # Iterate through compatible teams for this task
            # Sort keys for determinism if needed, though compatible_teams is dict
            for team_id, cost in sorted(task.compatible_teams.items()):
                team_avail = available_time[team_id]

                # Logic from snippet:
                # if available_time[team] == min_available_time and Cost[(task, team)] < min_cost:
                # if available_time[team] < min_available_time:

                if team_avail < min_avail_time:
                    min_avail_time = team_avail
                    min_avail_team = team_id
                    min_cost = cost
                elif team_avail == min_avail_time and cost < min_cost:
                    min_avail_team = team_id
                    min_cost = cost

            if min_avail_team != -1:
                # Assign
                start = min_avail_time
                finish = start + task.duration

                available_time[min_avail_team] = finish
                completion_time[tid] = finish
                scheduled_tasks.add(tid)
                assignments.append(Assignment(tid, min_avail_team, start))

        # 3. Main loop for remaining tasks
        # The snippet iterates while there are unscheduled tasks (and time limit not hit)

        while len(scheduled_tasks) < len(tasks):
            best_start_time = INF
            best_team = -1
            best_task = -1
            best_cost = INF

            found_candidate = False

            # Iterate all unscheduled tasks
            # To match snippet: iterate tasks, then compatible teams
            unscheduled = [t for t in tasks if t not in scheduled_tasks]
            if not unscheduled:
                break

            for tid in unscheduled:
                task = tasks[tid]

                for team_id, cost in task.compatible_teams.items():
                    team_avail = available_time[team_id]

                    # Check dependencies
                    # snippet:
                    # continue_flag_if_pre_task_not_done = False
                    # pre_task_completion_time = []
                    # for task_1 in pre_tasks[task]:
                    #   if completion_time[task_1] > cur_time: ...

                    deps_finish_after_team = []
                    deps_incomplete = False

                    for pred_id in task.predecessors:
                        pred_finish = completion_time[pred_id]
                        if pred_finish == INF:
                            # Dependency not scheduled yet
                            deps_incomplete = True
                            break  # Optimization: can't schedule this task yet

                        if pred_finish > team_avail:
                            deps_finish_after_team.append(pred_finish)

                    if deps_incomplete:
                        continue

                    # Calculate Earliest Start Time (EST)
                    if deps_finish_after_team:
                        est = max(deps_finish_after_team)
                        # This corresponds to snippet's Case 1 logic
                        # "if max_pre_task_completion_time < min_available_time"
                        # logic handles cases where start time is dictated by dependencies
                    else:
                        est = team_avail
                        # This corresponds to snippet's Case 2 logic
                        # "if available_time[team] < min_available_time"

                    # Update global best
                    if est < best_start_time:
                        best_start_time = est
                        best_team = team_id
                        best_task = tid
                        best_cost = cost
                        found_candidate = True
                    elif est == best_start_time:
                        if cost < best_cost:
                            best_team = team_id
                            best_task = tid
                            best_cost = cost
                            found_candidate = True

            if found_candidate:
                # Assign best candidate
                task = tasks[best_task]
                start = best_start_time
                finish = start + task.duration

                available_time[best_team] = finish
                completion_time[best_task] = finish
                scheduled_tasks.add(best_task)
                assignments.append(Assignment(best_task, best_team, start))
            else:
                # If no candidate found (e.g. cycle or impossible constraints not pruned),
                # break to avoid infinite loop
                break

        return Schedule(assignments)
