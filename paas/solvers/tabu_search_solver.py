import sys
import random
import heapq
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver
from paas.time_budget import TimeBudget


@dataclass
class Solution:
    """
    Represents a candidate solution in the search space.

    Attributes:
        task_order: Sequence defining the scheduling priority of tasks.
        team_assignment: Mapping from task ID to assigned team index.
        fitness: Cached objective values to avoid redundant computation.
    """

    task_order: List[int]
    team_assignment: List[int]
    fitness: Optional[Tuple[int, int, int]] = None


@dataclass
class Move:
    """
    Encapsulates a neighborhood transition for the tabu mechanism.

    Attributes:
        move_type: Either 'swap' (reorder tasks) or 'team' (reassign resource).
        task_id_1: Primary task involved in the move.
        task_id_2: Secondary task (for swap) or target team index (for reassignment).
    """

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


class TabuSearchSolver(Solver):
    """
    Metaheuristic solver implementing Tabu Search for task scheduling.

    Optimized for continuous indices (0..N-1 for tasks, 0..M-1 for teams).
    Removes dictionary lookups in critical paths and uses heap-based decoding.
    """

    def __init__(
        self,
        tabu_tenure: int = 10,
        max_neighbors: int = 50,
        seed: int = 42,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.tabu_tenure = tabu_tenure
        self.max_neighbors = max_neighbors
        self.seed = seed

        # Preallocated data structures
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
        """
        Convert problem data to flat arrays for O(1) access.
        Assumes tasks are 0..N-1 and teams are 0..M-1.
        """
        problem.assert_continuous_indices()
        self.num_tasks = problem.num_tasks
        self.num_teams = problem.num_teams

        # Team Data
        self.team_initial_availability = [0] * self.num_teams
        for tid, team in problem.teams.items():
            self.team_initial_availability[tid] = team.available_from

        # Task Data
        self.durations = [0] * self.num_tasks
        self.predecessors = [[] for _ in range(self.num_tasks)]
        self.successors = [[] for _ in range(self.num_tasks)]
        self.initial_in_degrees = [0] * self.num_tasks
        self.compatible_teams_indices = [[] for _ in range(self.num_tasks)]

        # Initialize costs with a large value (infinity)
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

    def _decode(self, solution: Solution) -> List[Assignment]:
        """
        Transform solution representation into executable schedule.
        Uses topological sort with a priority queue based on solution.task_order
        to resolve dependencies efficiently (O(N log N) vs O(N^2)).
        """
        # Map task_id -> priority (index in task_order)
        # Lower index = higher priority
        priority = [0] * self.num_tasks
        for rank, tid in enumerate(solution.task_order):
            priority[tid] = rank

        # Setup simulation state
        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        current_in_degrees = list(self.initial_in_degrees)

        assignments: List[Assignment] = []

        # Priority queue stores (rank, task_id)
        # We only add tasks that are ready (in_degree == 0)
        # We also need to ensure we only schedule tasks that are in the solution's order?
        # The solution.task_order includes ALL tasks (usually).
        # Even if it's a subset, the priority map handles it.
        # Tasks not in task_order shouldn't be scheduled?
        # For this solver, task_order is a permutation of tasks_with_teams.
        # Tasks without compatible teams are ignored.

        ready_heap = []
        for tid in self.tasks_with_teams:
            if current_in_degrees[tid] == 0:
                heapq.heappush(ready_heap, (priority[tid], tid))

        processed_count = 0

        while ready_heap:
            _, task_id = heapq.heappop(ready_heap)

            team_idx = solution.team_assignment[task_id]

            # Determine start time based on dependencies
            preds_complete_time = 0
            for p in self.predecessors[task_id]:
                # p must be finished because we only process when in_degree=0
                # and we process in dependency order.
                p_finish = task_finish_times[p]
                if p_finish > preds_complete_time:
                    preds_complete_time = p_finish

            start_time = max(team_available[team_idx], preds_complete_time)
            duration = self.durations[task_id]
            finish_time = start_time + duration

            task_finish_times[task_id] = finish_time
            team_available[team_idx] = finish_time

            assignments.append(Assignment(task_id, team_idx, start_time))
            processed_count += 1

            # Unlock successors
            for s in self.successors[task_id]:
                current_in_degrees[s] -= 1
                if current_in_degrees[s] == 0:
                    # Only add if it's a schedulable task (in tasks_with_teams)
                    # Use priority map for checking if it's in our scope effectively
                    # We can check if it has compatible teams.
                    if self.compatible_teams_indices[s]:
                        heapq.heappush(ready_heap, (priority[s], s))

        return assignments

    def _evaluate(self, solution: Solution) -> Tuple[int, int, int]:
        """
        Compute multi-objective fitness with memoization.
        """
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

            # a.team_id is an index here
            total_cost += self.team_costs[a.task_id][a.team_id]

        solution.fitness = (-task_count, completion_time, total_cost)
        return solution.fitness

    def _generate_initial_solution(
        self,
    ) -> Solution:
        """
        Construct initial solution via greedy dispatching rule using arrays.
        """
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
                # Check preds
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
                # Fill remaining arbitrarily to complete the permutation
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

    def _get_neighbors(
        self,
        current: Solution,
        tabu_list: Dict[Move, int],
        current_iter: int,
    ) -> List[Tuple[Solution, Move]]:
        """
        Generate candidate moves in the solution neighborhood.
        """
        neighbors = []
        task_order = current.task_order
        n = len(task_order)

        # Position exchange neighborhood
        swap_candidates = []
        for i in range(n):
            for j in range(i + 1, n):
                swap_candidates.append((i, j))

        # Limit neighborhood size via random sampling
        if len(swap_candidates) > self.max_neighbors // 2:
            swap_candidates = random.sample(swap_candidates, self.max_neighbors // 2)

        for i, j in swap_candidates:
            new_order = list(task_order)
            new_order[i], new_order[j] = new_order[j], new_order[i]

            move = Move("swap", task_order[i], task_order[j])
            # Reuse existing team assignment list (copy on write logic for Solution)
            neighbor = Solution(
                task_order=new_order, team_assignment=list(current.team_assignment)
            )
            neighbors.append((neighbor, move))

        # Resource reassignment neighborhood
        # Only iterate over tasks that have teams (tasks_with_teams)
        # And specifically those that have >1 compatible team
        reassign_candidates = []

        # We can optimize this by maintaining a list of tasks with >1 team
        # But iterating tasks_with_teams is reasonable.
        for tid in self.tasks_with_teams:
            opts = self.compatible_teams_indices[tid]
            if len(opts) > 1:
                current_team_idx = current.team_assignment[tid]
                for new_team_idx in opts:
                    if new_team_idx != current_team_idx:
                        reassign_candidates.append((tid, new_team_idx))

        # Bound exploration
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
        """Determine if the given move is currently forbidden."""
        if move not in tabu_list:
            return False
        return tabu_list[move] > current_iter

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        self._preprocess(problem)
        random.seed(self.seed)

        if not self.tasks_with_teams:
            return Schedule(assignments=[])

        with TimeBudget(time_limit) as budget:
            # Initialize with constructive heuristic
            current = self._generate_initial_solution()
            current_score = self._evaluate(current)

            best = current
            best_score = current_score

            # Short-term memory: maps moves to expiration iteration
            tabu_list: Dict[Move, int] = {}
            iteration = 0

            while not budget.is_expired():
                iteration += 1

                # Explore neighborhood
                neighbors = self._get_neighbors(current, tabu_list, iteration)

                if not neighbors:
                    break

                # Select best admissible move
                best_neighbor = None
                best_neighbor_score = (sys.maxsize, sys.maxsize, sys.maxsize)
                best_move = None

                for neighbor, move in neighbors:
                    if budget.is_expired():
                        break

                    score = self._evaluate(neighbor)
                    is_tabu = self._is_tabu(move, tabu_list, iteration)

                    # Aspiration: override tabu if global improvement achieved
                    if is_tabu:
                        if score < best_score:
                            pass  # Allow (Aspiration)
                        else:
                            continue  # Skip (Tabu)

                    if score < best_neighbor_score:
                        best_neighbor = neighbor
                        best_neighbor_score = score
                        best_move = move

                if best_neighbor is None:
                    # Diversification: random restart
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

                    # Reset tabu list? Usually yes or no, depends on strategy.
                    # Existing code didn't reset, just continued.
                    continue

                # Transition
                current = best_neighbor
                current_score = best_neighbor_score

                # Update memory
                if best_move:
                    tabu_list[best_move] = iteration + self.tabu_tenure

                    if best_move.move_type == "swap":
                        reverse = Move("swap", best_move.task_id_2, best_move.task_id_1)
                        tabu_list[reverse] = iteration + self.tabu_tenure
                    elif best_move.move_type == "team":
                        # For team move, reverse is assigning back to old team?
                        # We don't easily know old team here without looking at 'current' before update
                        # But typically we just forbid the move we just made?
                        # Or forbid changing this task again for a while?
                        # The original code didn't add reverse for team move explicitly
                        # (checked "if swap"). Wait, let me check original code.
                        pass

                # Track incumbent
                if current_score < best_score:
                    best = current
                    best_score = current_score

                # Maintenance
                if iteration % 100 == 0:
                    tabu_list = {
                        m: exp for m, exp in tabu_list.items() if exp > iteration
                    }

            return Schedule(assignments=self._decode(best))
