from typing import Dict, Tuple
from paas.models import ProblemInstance, Schedule, Assignment
from .base import MapResult


class LocalSearchMiddleware(MapResult):
    """
    Middleware that performs local search to improve the cost of a schedule
    without increasing its makespan.
    """

    def map_result(self, problem: ProblemInstance, result: Schedule) -> Schedule:
        if not result.assignments:
            return result

        return self.optimize(problem, result)

    def optimize(
        self, problem: ProblemInstance, initial_schedule: Schedule
    ) -> Schedule:
        tasks = problem.tasks

        # 1. Calculate Baseline Makespan
        current_makespan = self.calculate_makespan(problem, initial_schedule)

        # Map: task_id -> Assignment object (we'll modify it in place)
        assignment_map = {
            a.task_id: Assignment(a.task_id, a.team_id, a.start_time)
            for a in initial_schedule.assignments
        }

        improved = True
        while improved:
            improved = False

            # Sort tasks by cost (descending)
            task_ids_in_schedule = list(assignment_map.keys())
            sorted_task_ids = sorted(
                task_ids_in_schedule,
                key=lambda t_id: -tasks[t_id].compatible_teams.get(
                    assignment_map[t_id].team_id, 0
                ),
            )

            for task_id in sorted_task_ids:
                task = tasks[task_id]
                current_assignment = assignment_map[task_id]
                current_team = current_assignment.team_id
                current_cost = task.compatible_teams[current_team]

                # Try every OTHER compatible team
                for cand_team, cand_cost in task.compatible_teams.items():
                    if cand_team == current_team:
                        continue

                    if cand_cost < current_cost:
                        original_team = current_assignment.team_id
                        current_assignment.team_id = cand_team

                        # Backup start times in case recompute fails or doesn't improve
                        backup_start_times = {
                            tid: a.start_time for tid, a in assignment_map.items()
                        }

                        new_makespan, valid = self.recompute_schedule(
                            problem, assignment_map
                        )

                        if valid and new_makespan <= current_makespan:
                            improved = True
                            current_cost = cand_cost
                            # Success! assignment_map now has new team and new start times
                        else:
                            # Revert team and start times
                            current_assignment.team_id = original_team
                            for tid, st in backup_start_times.items():
                                assignment_map[tid].start_time = st

        final_assignments = list(assignment_map.values())
        return Schedule(final_assignments)

    def calculate_makespan(self, problem: ProblemInstance, schedule: Schedule) -> int:
        if not schedule.assignments:
            return 0
        return max(
            a.start_time + problem.tasks[a.task_id].duration
            for a in schedule.assignments
        )

    def recompute_schedule(
        self, problem: ProblemInstance, assignment_map: Dict[int, Assignment]
    ) -> Tuple[int, bool]:
        tasks = problem.tasks
        teams = problem.teams

        scheduled_task_ids = set(assignment_map.keys())

        # in_degree restricted to scheduled tasks
        in_degree = {}
        for t_id in scheduled_task_ids:
            task = tasks[t_id]
            deg = 0
            for p_id in task.predecessors:
                if p_id in scheduled_task_ids:
                    deg += 1
            in_degree[t_id] = deg

        # Initial ready queue
        ready_queue = [t_id for t_id in scheduled_task_ids if in_degree[t_id] == 0]
        # Heuristic: process tasks with earlier original start times as tie-breaker
        ready_queue.sort(key=lambda t_id: assignment_map[t_id].start_time)

        task_finish_time = {}
        team_free_time = {
            team_id: team.available_from for team_id, team in teams.items()
        }

        max_finish = 0
        processed_count = 0

        while ready_queue:
            task_id = ready_queue.pop(0)
            processed_count += 1

            task = tasks[task_id]
            assignment = assignment_map[task_id]

            earliest_start_by_deps = 0
            for p_id in task.predecessors:
                if p_id in scheduled_task_ids:
                    earliest_start_by_deps = max(
                        earliest_start_by_deps, task_finish_time[p_id]
                    )

            earliest_start_by_team = team_free_time[assignment.team_id]

            start_time = max(earliest_start_by_deps, earliest_start_by_team)
            assignment.start_time = start_time
            finish_time = start_time + task.duration
            task_finish_time[task_id] = finish_time
            team_free_time[assignment.team_id] = finish_time

            if finish_time > max_finish:
                max_finish = finish_time

            for s_id in task.successors:
                if s_id in scheduled_task_ids:
                    in_degree[s_id] -= 1
                    if in_degree[s_id] == 0:
                        ready_queue.append(s_id)
                        # Re-sort to maintain order based on start_time
                        # (Using original start_time here for stability)
                        ready_queue.sort(key=lambda tid: assignment_map[tid].start_time)

        if processed_count != len(scheduled_task_ids):
            return 0, False

        return max_finish, True
