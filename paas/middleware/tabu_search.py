import sys
import random
import heapq
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import MapResult
from paas.time_budget import TimeBudget


@dataclass
class Solution:
    task_order: List[int]
    team_assignment: List[int]
    fitness: Optional[Tuple[int, int, int]] = None


@dataclass
class Move:
    move_type: str
    task_id_1: int
    task_id_2: int = -1

    def __hash__(self):
        return hash((self.move_type, self.task_id_1, self.task_id_2))

    def __eq__(self, other):
        return (self.move_type, self.task_id_1, self.task_id_2) == (
            other.move_type,
            other.task_id_1,
            other.task_id_2,
        )


class TabuSearchMiddleware(MapResult):
    """
    Tabu Search Middleware.
    Refines a solution using Tabu Search.
    """

    def __init__(
        self,
        tabu_tenure: int = 20,
        max_neighbors: int = 500,
        seed: int = 42,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.tabu_tenure = tabu_tenure
        self.max_neighbors = max_neighbors
        self.seed = seed

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

    def _schedule_to_solution(self, schedule: Schedule) -> Solution:
        team_assignment = [0] * self.num_tasks

        sorted_assignments = sorted(schedule.assignments, key=lambda a: a.start_time)
        task_order = [a.task_id for a in sorted_assignments]

        scheduled_ids = set(task_order)
        remaining = [tid for tid in self.tasks_with_teams if tid not in scheduled_ids]
        random.shuffle(remaining)
        task_order.extend(remaining)

        for a in schedule.assignments:
            team_assignment[a.task_id] = a.team_id

        for tid in remaining:
            opts = self.compatible_teams_indices[tid]
            if opts:
                team_assignment[tid] = random.choice(opts)

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

    def _evaluate(self, solution: Solution) -> Tuple[int, int, int]:
        if solution.fitness is not None:
            return solution.fitness

        assignments = self._decode(solution)

        if not assignments:
            return (0, sys.maxsize, sys.maxsize)

        task_count = len(assignments)
        completion_time = 0
        total_cost = 0

        for a in assignments:
            duration = self.durations[a.task_id]
            finish = a.start_time + duration
            if finish > completion_time:
                completion_time = finish
            total_cost += self.team_costs[a.task_id][a.team_id]

        solution.fitness = (-task_count, completion_time, total_cost)
        return solution.fitness

    def _get_neighbors(
        self,
        current: Solution,
        tabu_list: Dict[Move, int],
        current_iter: int,
    ) -> List[Tuple[Solution, Move]]:
        neighbors = []
        task_order = current.task_order
        n = len(task_order)

        swap_candidates = []
        for i in range(n):
            for j in range(i + 1, n):
                swap_candidates.append((i, j))

        if len(swap_candidates) > self.max_neighbors // 2:
            swap_candidates = random.sample(swap_candidates, self.max_neighbors // 2)

        for i, j in swap_candidates:
            new_order = list(task_order)
            new_order[i], new_order[j] = new_order[j], new_order[i]

            move = Move("swap", task_order[i], task_order[j])
            neighbor = Solution(
                task_order=new_order, team_assignment=list(current.team_assignment)
            )
            neighbors.append((neighbor, move))

        reassign_candidates = []
        for tid in self.tasks_with_teams:
            opts = self.compatible_teams_indices[tid]
            if len(opts) > 1:
                current_team_idx = current.team_assignment[tid]
                for new_team_idx in opts:
                    if new_team_idx != current_team_idx:
                        reassign_candidates.append((tid, new_team_idx))

        if len(reassign_candidates) > self.max_neighbors // 2:
            reassign_candidates = random.sample(
                reassign_candidates, self.max_neighbors // 2
            )

        for tid, new_team_idx in reassign_candidates:
            new_assignment = list(current.team_assignment)
            new_assignment[tid] = new_team_idx

            move = Move("team", tid, new_team_idx)
            neighbor = Solution(
                task_order=list(current.task_order), team_assignment=new_assignment
            )
            neighbors.append((neighbor, move))

        return neighbors

    def _is_tabu(
        self, move: Move, tabu_list: Dict[Move, int], current_iter: int
    ) -> bool:
        if move not in tabu_list:
            return False
        return tabu_list[move] > current_iter

    def map_result(
        self,
        problem: ProblemInstance,
        result: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        self._preprocess(problem)
        random.seed(self.seed)

        if not self.tasks_with_teams:
            return result

        with TimeBudget(time_limit) as budget:
            current = self._schedule_to_solution(result)
            current_score = self._evaluate(current)

            best = current
            best_score = current_score

            tabu_list: Dict[Move, int] = {}
            iteration = 0

            while not budget.is_expired():
                iteration += 1

                neighbors = self._get_neighbors(current, tabu_list, iteration)
                if not neighbors:
                    break

                best_neighbor = None
                best_neighbor_score = (sys.maxsize, sys.maxsize, sys.maxsize)
                best_move = None

                for neighbor, move in neighbors:
                    if budget.is_expired():
                        break

                    score = self._evaluate(neighbor)
                    is_tabu = self._is_tabu(move, tabu_list, iteration)

                    if is_tabu:
                        if score < best_score:
                            pass
                        else:
                            continue

                    if score < best_neighbor_score:
                        best_neighbor = neighbor
                        best_neighbor_score = score
                        best_move = move

                if best_neighbor is None:
                    # Diversification
                    task_order = list(self.tasks_with_teams)
                    random.shuffle(task_order)
                    team_assignment = [0] * self.num_tasks
                    for tid in self.tasks_with_teams:
                        team_assignment[tid] = random.choice(
                            self.compatible_teams_indices[tid]
                        )
                    current = Solution(
                        task_order=task_order, team_assignment=team_assignment
                    )
                    current_score = self._evaluate(current)
                    continue

                current = best_neighbor
                current_score = best_neighbor_score

                if best_move:
                    tabu_list[best_move] = iteration + self.tabu_tenure
                    if best_move.move_type == "swap":
                        reverse = Move("swap", best_move.task_id_2, best_move.task_id_1)
                        tabu_list[reverse] = iteration + self.tabu_tenure

                if current_score < best_score:
                    best = current
                    best_score = current_score

                if iteration % 100 == 0:
                    tabu_list = {
                        m: exp for m, exp in tabu_list.items() if exp > iteration
                    }

        return Schedule(assignments=self._decode(best))
