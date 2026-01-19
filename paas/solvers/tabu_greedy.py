import sys
import heapq
from typing import List
from dataclasses import dataclass
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver


@dataclass
class Solution:
    task_order: List[int]
    team_assignment: List[int]


class TabuGreedySolver(Solver):
    """
    Greedy component extracted from TabuSearchSolver.
    Constructs a solution using a constructive heuristic.
    """

    def __init__(self, time_factor: float = 1.0):
        super().__init__(time_factor)
        self.num_tasks: int = 0
        self.num_teams: int = 0
        self.durations: List[int] = []
        self.predecessors: List[List[int]] = []
        self.successors: List[List[int]] = []
        self.initial_in_degrees: List[int] = []
        self.compatible_teams_indices: List[List[int]] = []
        self.team_costs: List[List[int]] = []
        self.team_initial_availability: List[int] = []
        self.tasks_with_teams: List[int] = []

    def _preprocess(self, problem: ProblemInstance):
        problem.assert_continuous_indices()
        self.num_tasks = problem.num_tasks
        self.num_teams = problem.num_teams

        self.team_initial_availability = [0] * self.num_teams
        for tid, team in problem.teams.items():
            self.team_initial_availability[tid] = team.available_from

        self.durations = [0] * self.num_tasks
        self.predecessors = [[] for _ in range(self.num_tasks)]
        self.successors = [[] for _ in range(self.num_tasks)]
        self.initial_in_degrees = [0] * self.num_tasks
        self.compatible_teams_indices = [[] for _ in range(self.num_tasks)]

        INF = 10**12
        self.team_costs = [[INF] * self.num_teams for _ in range(self.num_tasks)]
        self.tasks_with_teams = []

        for tid, task in problem.tasks.items():
            self.durations[tid] = task.duration
            self.predecessors[tid] = task.predecessors
            self.successors[tid] = task.successors
            self.initial_in_degrees[tid] = len(task.predecessors)

            if task.compatible_teams:
                self.tasks_with_teams.append(tid)

            for team_idx, cost in task.compatible_teams.items():
                self.compatible_teams_indices[tid].append(team_idx)
                self.team_costs[tid][team_idx] = cost

    def _generate_initial_solution(self) -> Solution:
        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks

        task_order: List[int] = []
        team_assignment: List[int] = [0] * self.num_tasks

        remaining = set(self.tasks_with_teams)

        while remaining:
            best_task = -1
            best_team_idx = -1
            best_start = sys.maxsize
            best_cost = sys.maxsize

            for tid in remaining:
                preds_done = True
                pred_done_time = 0
                for p in self.predecessors[tid]:
                    ft = task_finish_times[p]
                    if ft == -1:
                        preds_done = False
                        break
                    if ft > pred_done_time:
                        pred_done_time = ft

                if not preds_done:
                    continue

                for team_idx in self.compatible_teams_indices[tid]:
                    start = max(team_available[team_idx], pred_done_time)
                    cost = self.team_costs[tid][team_idx]

                    if start < best_start or (start == best_start and cost < best_cost):
                        best_start = start
                        best_task = tid
                        best_team_idx = team_idx
                        best_cost = cost

            if best_task == -1:
                for tid in remaining:
                    task_order.append(tid)
                    opts = self.compatible_teams_indices[tid]
                    if opts:
                        team_assignment[tid] = opts[0]
                break

            task_order.append(best_task)
            team_assignment[best_task] = best_team_idx
            finish = best_start + self.durations[best_task]
            task_finish_times[best_task] = finish
            team_available[best_team_idx] = finish
            remaining.remove(best_task)

        return Solution(task_order=task_order, team_assignment=team_assignment)

    def _decode(self, solution: Solution) -> List[Assignment]:
        priority = [0] * self.num_tasks
        for rank, tid in enumerate(solution.task_order):
            priority[tid] = rank

        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        current_in_degrees = list(self.initial_in_degrees)

        assignments: List[Assignment] = []
        ready_heap = []
        for tid in self.tasks_with_teams:
            if current_in_degrees[tid] == 0:
                heapq.heappush(ready_heap, (priority[tid], tid))

        while ready_heap:
            _, task_id = heapq.heappop(ready_heap)
            team_idx = solution.team_assignment[task_id]

            preds_complete_time = 0
            for p in self.predecessors[task_id]:
                p_finish = task_finish_times[p]
                if p_finish > preds_complete_time:
                    preds_complete_time = p_finish

            start_time = max(team_available[team_idx], preds_complete_time)
            duration = self.durations[task_id]
            finish_time = start_time + duration

            task_finish_times[task_id] = finish_time
            team_available[team_idx] = finish_time

            assignments.append(Assignment(task_id, team_idx, start_time))

            for s in self.successors[task_id]:
                current_in_degrees[s] -= 1
                if current_in_degrees[s] == 0:
                    if self.compatible_teams_indices[s]:
                        heapq.heappush(ready_heap, (priority[s], s))

        return assignments

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        self._preprocess(problem)

        if not self.tasks_with_teams:
            return Schedule(assignments=[])

        best = self._generate_initial_solution()
        return Schedule(assignments=self._decode(best))
